"""Ejecución de los gates de la política sobre la composición candidata.

Antes, ``seal`` aceptaba ``--resultados-pruebas <json>``: un archivo que decía «PASS».
Bastaba escribirlo. Aquí el veredicto no se declara: se **deriva** de ejecutar el ``argv``
exacto que la política versiona, dentro del árbol candidato completo, y de que termine con
código 0. Todo lo demás —tiempo agotado, señal, ejecutable ausente, excepción, un byte
mutado en la composición— es FAIL, y un FAIL no sella.

Lo que este módulo garantiza:

- el comando es el ``argv`` de la política, sin shell y sin reinterpretación;
- el directorio de trabajo resuelve dentro del staging, sin enlaces, y nunca dentro de un
  destino vivo;
- el entorno es exactamente el que la política permite heredar o fija;
- la composición se inventaría antes y después de cada gate: un gate que muta un byte
  queda FAIL por «mutación», y los siguientes no se ejecutan porque medirían otro árbol;
- la evidencia (índice gobernante, stdout, stderr) se escribe en exclusiva fuera de
  ``outputs/`` y se relee desde disco antes de devolverla.

Lo que NO garantiza: esto no es un sandbox. El gate corre con el usuario, el sistema de
archivos y la red del operador; sus procesos hijos no están confinados. Aquí se cierra la
**interfaz** —qué comando, dónde, con qué entorno, durante cuánto y qué se registra—; el
confinamiento real sigue siendo P0.6.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
from typing import Any

from epiforecast.publication.weekly_staging import (
    ARCHIVO_INDICE,
    ARCHIVO_OBSERVACIONAL,
    DIR_EVIDENCIA,
    ESQUEMA_EVIDENCIA,
    ESQUEMA_OBSERVACIONAL,
    VEREDICTO_FAIL,
    VEREDICTO_REQUERIDO,
    EvidenciaGates,
    GateSpec,
    PoliticaCenso,
    RegistroGate,
    StagingError,
    _escribe_exclusivo,
    _exige_directorio_real,
    calcula_composicion,
    inventaria,
    valida_ruta_sellable,
)


def _ahora() -> str:
    """Marca temporal observacional. Aislada para que las pruebas puedan fijarla."""
    return datetime.now(UTC).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class _Ejecucion:
    """Lo que de verdad pasó al intentar correr un gate."""

    exit_code: int | None
    senal: int | None
    causa: str
    detalle: str
    stdout: bytes
    stderr: bytes
    ejecutable: str


def _resuelve_cwd(outputs_real: Path, spec: GateSpec, vivos: tuple[Path, ...]) -> Path:
    """El cwd lógico de la política, traducido al staging y sin salirse de él.

    Se recorre componente a componente con ``lstat``: un enlace en cualquier tramo haría
    que el gate midiera otro directorio. Y aunque resuelva dentro del staging, nunca puede
    caer en un destino vivo: los gates certifican el candidato, no el sitio real.
    """
    actual = outputs_real
    for parte in spec.cwd.rstrip("/").split("/"):
        actual = actual / parte
        try:
            estado = actual.lstat()
        except FileNotFoundError as exc:
            raise StagingError(
                f"el cwd {spec.cwd!r} del gate {spec.id} no existe en la composición candidata"
            ) from exc
        if stat.S_ISLNK(estado.st_mode):
            raise StagingError(
                f"un componente del cwd {spec.cwd!r} del gate {spec.id} es un enlace simbólico"
            )
        if not stat.S_ISDIR(estado.st_mode):
            raise StagingError(f"el cwd {spec.cwd!r} del gate {spec.id} no es un directorio")
    real = actual.resolve()
    try:
        real.relative_to(outputs_real)
    except ValueError as exc:  # pragma: no cover - el recorrido con lstat ya lo impide
        raise StagingError(f"el cwd {spec.cwd!r} escaparía del staging") from exc
    for vivo in vivos:
        vivo_real = vivo.resolve()
        if real == vivo_real or vivo_real in real.parents:
            raise StagingError(
                f"el cwd {spec.cwd!r} del gate {spec.id} resuelve dentro de un destino vivo "
                f"({vivo}); los gates corren sobre el candidato, nunca sobre el sitio real"
            )
    return real


def _construye_entorno(spec: GateSpec) -> dict[str, str]:
    """Sólo lo que la política permite: heredado por nombre, o fijado con su valor."""
    entorno = {nombre: os.environ[nombre] for nombre in spec.heredar if nombre in os.environ}
    entorno.update(dict(spec.fijar))
    return entorno


def _resuelve_ejecutable(spec: GateSpec, entorno: dict[str, str]) -> Path:
    """Localiza ``argv[0]`` con el PATH **permitido**, no con el del operador."""
    ejecutable = spec.argv[0]
    if ejecutable.startswith("/"):
        ruta = Path(ejecutable)
        if not ruta.is_file() or not os.access(ruta, os.X_OK):
            raise StagingError(f"no hay un archivo ejecutable en {ejecutable!r} (gate {spec.id})")
        return ruta
    encontrado = shutil.which(ejecutable, path=entorno.get("PATH", ""))
    if encontrado is None:
        raise StagingError(
            f"no hay ejecutable {ejecutable!r} en el PATH permitido del gate {spec.id}"
        )
    return Path(encontrado)


def _mata_grupo(proceso: subprocess.Popen[bytes]) -> None:
    """El gate corre en su propia sesión: al vencer el plazo se mata el grupo entero."""
    try:
        os.killpg(proceso.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proceso.kill()


def _corre(spec: GateSpec, cwd: Path, ejecutable: Path, entorno: dict[str, str]) -> _Ejecucion:
    """Ejecuta el argv exacto y traduce lo ocurrido a un resultado, sin juzgarlo todavía."""
    argv = [str(ejecutable), *spec.argv[1:]]
    try:
        proceso = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=entorno,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        return _Ejecucion(None, None, "excepcion", f"{type(exc).__name__}: {exc}", b"", b"", "")

    try:
        salida, errores = proceso.communicate(timeout=spec.timeout_s)
    except subprocess.TimeoutExpired:
        _mata_grupo(proceso)
        salida, errores = proceso.communicate()
        return _Ejecucion(
            None,
            -proceso.returncode if proceso.returncode < 0 else None,
            "timeout",
            f"venció el límite de {spec.timeout_s} s; se envió SIGKILL al grupo de procesos",
            salida or b"",
            errores or b"",
            str(ejecutable),
        )

    codigo = proceso.returncode
    if codigo < 0:
        numero = -codigo
        try:
            nombre = signal.Signals(numero).name
        except ValueError:
            nombre = "desconocida"
        return _Ejecucion(
            None,
            numero,
            "senal",
            f"terminó por la señal {numero} ({nombre})",
            salida,
            errores,
            str(ejecutable),
        )
    if codigo != 0:
        return _Ejecucion(
            codigo,
            None,
            "exit_code",
            f"terminó con código {codigo}",
            salida,
            errores,
            str(ejecutable),
        )
    return _Ejecucion(0, None, "", "", salida, errores, str(ejecutable))


def _ejecuta_uno(spec: GateSpec, outputs_real: Path, vivos: tuple[Path, ...]) -> _Ejecucion:
    try:
        cwd = _resuelve_cwd(outputs_real, spec, vivos)
    except StagingError as exc:
        return _Ejecucion(None, None, "cwd_invalido", str(exc), b"", b"", "")
    entorno = _construye_entorno(spec)
    try:
        ejecutable = _resuelve_ejecutable(spec, entorno)
    except StagingError as exc:
        return _Ejecucion(None, None, "ejecutable_ausente", str(exc), b"", b"", "")
    try:
        return _corre(spec, cwd, ejecutable, entorno)
    except Exception as exc:  # cualquier cosa inesperada es FAIL, nunca un PASS por omisión
        return _Ejecucion(
            None, None, "excepcion", f"{type(exc).__name__}: {exc}", b"", b"", str(ejecutable)
        )


def _describe_mutacion(antes: dict[str, str], despues: dict[str, str]) -> str:
    anadidos = sorted(set(despues) - set(antes))
    retirados = sorted(set(antes) - set(despues))
    alterados = sorted(rel for rel in antes if rel in despues and antes[rel] != despues[rel])
    return (
        f"el gate mutó la composición: {len(anadidos)} añadido(s) {anadidos[:3]}, "
        f"{len(retirados)} retirado(s) {retirados[:3]}, {len(alterados)} alterado(s) "
        f"{alterados[:3]}; repite TODOS los gates sobre la composición nueva"
    )


def _sha256(crudo: bytes) -> str:
    return hashlib.sha256(crudo).hexdigest()


def _json_canonico(objeto: dict[str, Any]) -> bytes:
    return json.dumps(objeto, indent=2, ensure_ascii=False, sort_keys=True).encode() + b"\n"


def ejecuta_gates(
    raiz_staging: Path,
    politica: PoliticaCenso,
    *,
    destinos_vivos: Iterable[Path] = (),
) -> EvidenciaGates:
    """Corre todos los gates de la política sobre ``<staging>/outputs`` y sella la evidencia.

    Se ejecuta **antes** de podar el staging: la composición que certifican los gates es la
    del árbol completo, que es exactamente lo que ``seal`` recompone después como
    ``semilla + cambiados − lápidas``. Si un gate muta la composición, ese gate queda FAIL y
    los siguientes no se ejecutan.

    Devuelve la evidencia **releída desde disco**, con las mismas comprobaciones que hará
    ``seal``: lo que se devuelve es lo que quedó escrito, no lo que se pensaba escribir.
    """
    outputs = raiz_staging / "outputs"
    _exige_directorio_real(outputs, "el directorio de artefactos")
    carpeta = raiz_staging / DIR_EVIDENCIA
    if carpeta.is_symlink() or carpeta.exists():
        raise StagingError(
            f"ya existe evidencia de gates en {carpeta}; una corrida no se sobrescribe. "
            "Revísala y retírala a mano, o prepara otro staging"
        )

    vivos = tuple(Path(v) for v in destinos_vivos)
    outputs_real = outputs.resolve()
    for vivo in vivos:
        vivo_real = vivo.resolve()
        if (
            outputs_real == vivo_real
            or vivo_real in outputs_real.parents
            or outputs_real in vivo_real.parents
        ):
            raise StagingError(
                f"el staging {outputs} y el destino vivo {vivo} se solapan; los gates no "
                "corren sobre el sitio real"
            )

    arbol = inventaria(outputs)
    for rel in arbol:
        valida_ruta_sellable(rel)
    composicion, _ = calcula_composicion({}, arbol, ())

    try:
        carpeta.mkdir()
    except FileExistsError as exc:
        raise StagingError(
            f"la carpeta de evidencia apareció a mitad de camino: {carpeta}"
        ) from exc

    registros: dict[str, RegistroGate] = {}
    observaciones: dict[str, dict[str, Any]] = {}
    mutador: str | None = None
    for spec in politica.gates:
        (carpeta / spec.id).mkdir()
        inicio = _ahora()
        if mutador is not None:
            ejecucion = _Ejecucion(
                None,
                None,
                "no_ejecutado",
                f"no se ejecutó: el gate {mutador!r} mutó la composición y este habría medido "
                "otro árbol",
                b"",
                b"",
                "",
            )
        else:
            ejecucion = _ejecuta_uno(spec, outputs_real, vivos)
            despues = inventaria(outputs)
            if despues != arbol:
                ejecucion = replace(
                    ejecucion, causa="mutacion", detalle=_describe_mutacion(arbol, despues)
                )
                mutador = spec.id
        fin = _ahora()

        _escribe_exclusivo(carpeta / spec.id / "stdout.bin", ejecucion.stdout)
        _escribe_exclusivo(carpeta / spec.id / "stderr.bin", ejecucion.stderr)
        registros[spec.id] = RegistroGate(
            gate=spec.id,
            veredicto=VEREDICTO_REQUERIDO if ejecucion.causa == "" else VEREDICTO_FAIL,
            causa=ejecucion.causa,
            detalle=ejecucion.detalle,
            politica_sha256=politica.sha256,
            composicion=composicion,
            spec=spec,
            exit_code=ejecucion.exit_code,
            senal=ejecucion.senal,
            stdout_bytes=len(ejecucion.stdout),
            stdout_sha256=_sha256(ejecucion.stdout),
            stderr_bytes=len(ejecucion.stderr),
            stderr_sha256=_sha256(ejecucion.stderr),
        )
        observaciones[spec.id] = {"inicio": inicio, "fin": fin, "ejecutable": ejecucion.ejecutable}

    todos_pasan = all(r.veredicto == VEREDICTO_REQUERIDO for r in registros.values())
    indice = {
        "esquema": ESQUEMA_EVIDENCIA,
        "politica": {"version": politica.version, "sha256": politica.sha256},
        "composicion": composicion,
        "veredicto": VEREDICTO_REQUERIDO if todos_pasan else VEREDICTO_FAIL,
        "gates": {nombre: registro.como_dict() for nombre, registro in registros.items()},
    }
    crudo = _json_canonico(indice)
    _escribe_exclusivo(carpeta / ARCHIVO_INDICE, crudo)
    _escribe_exclusivo(
        carpeta / (Path(ARCHIVO_INDICE).stem + ".sha256"), _sha256(crudo).encode() + b"\n"
    )
    _escribe_exclusivo(
        carpeta / ARCHIVO_OBSERVACIONAL,
        _json_canonico({"esquema": ESQUEMA_OBSERVACIONAL, "gates": observaciones}),
    )
    return EvidenciaGates.lee(raiz_staging)
