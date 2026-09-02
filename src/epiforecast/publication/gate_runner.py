"""Ejecución de los gates de la política sobre la composición candidata.

Antes, ``seal`` aceptaba ``--resultados-pruebas <json>``: un archivo que decía «PASS».
Bastaba escribirlo. Aquí el veredicto no se declara: se **deriva** de ejecutar el ``argv``
exacto que la política versiona, dentro del árbol candidato completo, y de que termine con
código 0. Todo lo demás —tiempo agotado, señal, ejecutable ausente, excepción, un byte
mutado en la composición— es FAIL, y un FAIL no sella.

Lo que este módulo garantiza:

- el comando es el ``argv`` de la política, sin shell y sin reinterpretación;
- el directorio de trabajo resuelve dentro del staging, sin enlaces;
- el staging no cae dentro de ningún **prefijo administrado** de un destino vivo ni de su
  ``.git``, y ningún destino vivo cae dentro del staging. Sí puede vivir bajo el
  repositorio del backend (``runs/_refresh``, ignorado por git): ahí es donde el
  orquestador lo crea, y prohibirlo dejaba el flujo real sin poder correr;
- el entorno es exactamente el que la política permite heredar o fijar; el digest del
  ejecutable resuelto entra en el registro gobernante;
- la composición se inventaría antes y después de cada gate: un gate que muta un byte
  queda FAIL por «mutación», y los siguientes no se ejecutan porque medirían otro árbol;
- la evidencia (índice gobernante, stdout, stderr) se escribe en exclusiva fuera de
  ``outputs/``, primero en ``gates.en_curso/`` con un marcador de corrida y sólo al
  terminar se renombra a ``gates/``; se relee desde disco antes de devolverla;
- una corrida interrumpida deja ``gates.en_curso/`` con el marcador: la siguiente mata el
  grupo de procesos huérfano que registró, aparta la evidencia parcial (nunca la borra) y
  arranca limpia. Una evidencia completa en FAIL o de otra composición también se aparta;
  sólo un PASS completo para la MISMA composición se conserva y no se repite.

Lo que NO garantiza: esto no es un sandbox. El gate corre con el usuario, el sistema de
archivos y la red del operador; sus procesos hijos no están confinados. Aquí se cierra la
**interfaz** —qué comando, dónde, con qué entorno, durante cuánto y qué se registra—; el
confinamiento real sigue siendo P0.6.
"""

from __future__ import annotations

from collections.abc import Mapping
import contextlib
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
    sha256_de,
    valida_ruta_sellable,
)

DIR_EN_CURSO = f"{DIR_EVIDENCIA}.en_curso"
ARCHIVO_RUNNER = "runner.json"
ESQUEMA_RUNNER = "gates_runner/1"
# `ps` por ruta absoluta: el runner no depende del PATH del operador (que una prueba, o
# un gate con PATH restringido, puede haber dejado sin /bin).
_PS = next((r for r in ("/bin/ps", "/usr/bin/ps") if os.access(r, os.X_OK)), "ps")


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
    ejecutable_sha256: str = ""


# ── solape con destinos vivos ────────────────────────────────────────────────


def _dentro(ruta: Path, raiz: Path) -> bool:
    return ruta == raiz or raiz in ruta.parents


def exige_sin_solape(
    outputs_real: Path, politica: PoliticaCenso, vivos: Mapping[str, Path]
) -> None:
    """El staging no toca lo administrado de ningún destino vivo, y ningún vivo cae en él.

    La regla ya no es «fuera del repositorio»: el flujo real crea el staging bajo
    ``<backend>/runs/_refresh``, y el backend sólo tiene administrado ``reports/ProdDetails/``.
    Lo que sí se prohíbe: el staging dentro de un prefijo administrado (los gates medirían
    el sitio real), dentro de ``.git`` (corrompería el repositorio) o conteniendo al propio
    destino (instalar sobre el staging). Para el dashboard el prefijo administrado es
    ``dashboard/`` entero, así que ahí sigue sin caber nada.
    """
    for espacio, vivo in vivos.items():
        vivo_real = Path(vivo).resolve()
        if _dentro(vivo_real, outputs_real):
            raise StagingError(
                f"el destino vivo {espacio} ({vivo}) está dentro del staging {outputs_real}; "
                "los gates no corren sobre el sitio real"
            )
        if _dentro(outputs_real, vivo_real / ".git"):
            raise StagingError(
                f"el staging {outputs_real} está dentro del .git del destino vivo {espacio}"
            )
        for prefijo in politica.prefijos_administrados:
            esp, _, subruta = prefijo.rstrip("/").partition("/")
            if esp != espacio:
                continue
            administrado = vivo_real / subruta if subruta else vivo_real
            if _dentro(outputs_real, administrado):
                raise StagingError(
                    f"el staging {outputs_real} cae dentro del prefijo administrado "
                    f"{prefijo!r} del destino vivo {espacio} ({vivo}); los gates medirían "
                    "el sitio real"
                )


# ── cwd, entorno y ejecutable ────────────────────────────────────────────────


def _resuelve_cwd(outputs_real: Path, spec: GateSpec) -> Path:
    """El cwd lógico de la política, traducido al staging y sin salirse de él.

    Se recorre componente a componente con ``lstat``: un enlace en cualquier tramo haría
    que el gate midiera otro directorio. Que el cwd no caiga en un destino vivo ya lo
    garantiza ``exige_sin_solape`` sobre ``outputs`` entero, del que el cwd es parte.
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


# ── procesos ─────────────────────────────────────────────────────────────────


def _mata_grupo(pgid: int) -> None:
    """El gate corre en su propia sesión: se mata el grupo entero, nunca sólo el hijo."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, signal.SIGKILL)


def _proceso_vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _identidad_de(pid: int) -> tuple[int, str] | None:
    """(pgid, instante de arranque) del proceso según `ps`, o None si no existe.

    Es lo que distingue al hijo registrado de un proceso ajeno que heredó su pid: el
    grupo lo creó el runner (`start_new_session`) y el instante de arranque no se repite.
    La línea de órdenes no sirve: el Python de macOS se re-ejecuta con otra ruta.
    """
    try:
        salida = subprocess.run(
            [_PS, "-o", "pgid=,lstart=", "-p", str(pid)], capture_output=True, text=True
        )
    except OSError:
        return None
    partes = salida.stdout.split(None, 1)
    if salida.returncode != 0 or len(partes) != 2 or not partes[0].isdigit():
        return None
    return int(partes[0]), partes[1].strip()


class _Marcador:
    """``runner.json`` dentro de ``gates.en_curso/``: quién corre y qué hijo tiene vivo."""

    def __init__(self, carpeta: Path) -> None:
        self.ruta = carpeta / ARCHIVO_RUNNER
        self.hijo: dict[str, Any] | None = None

    def escribe(self, gate: str | None = None) -> None:
        cuerpo = {
            "esquema": ESQUEMA_RUNNER,
            "runner_pid": os.getpid(),
            # No usa `_ahora()`: el marcador no es evidencia y no comparte el reloj fijable.
            "inicio": datetime.now(UTC).isoformat(timespec="microseconds"),
            "gate_en_curso": gate,
            "hijo": self.hijo,
        }
        crudo = _json_canonico(cuerpo)
        temporal = self.ruta.with_name(self.ruta.name + ".part")
        temporal.write_bytes(crudo)
        temporal.replace(self.ruta)

    def registra_hijo(self, gate: str, pid: int, ejecutable: str) -> None:
        identidad = _identidad_de(pid)
        self.hijo = {
            "gate": gate,
            "pid": pid,
            "pgid": pid,
            "arranque": identidad[1] if identidad else None,
            "ejecutable": ejecutable,
        }
        self.escribe(gate)

    def olvida_hijo(self) -> None:
        self.hijo = None
        self.escribe(None)


def _lee_marcador(carpeta: Path) -> dict[str, Any] | None:
    ruta = carpeta / ARCHIVO_RUNNER
    if ruta.is_symlink() or not ruta.is_file():
        return None
    try:
        crudo = json.loads(ruta.read_bytes())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return crudo if isinstance(crudo, dict) and crudo.get("esquema") == ESQUEMA_RUNNER else None


def _mata_huerfano(marcador: dict[str, Any]) -> str:
    """Mata el grupo del hijo que dejó una corrida interrumpida, si sigue siendo ese hijo.

    Un pid se reutiliza: sólo se mata si el proceso existe, sigue en el grupo que el runner
    le creó y arrancó en el instante registrado. Si no coincide, no es nuestro y no se toca.
    """
    hijo = marcador.get("hijo")
    if not isinstance(hijo, dict):
        return "sin hijo registrado"
    pid, pgid, ejecutable = hijo.get("pid"), hijo.get("pgid"), hijo.get("ejecutable")
    if not isinstance(pid, int) or not isinstance(pgid, int) or pid <= 1 or pgid <= 1:
        return "hijo registrado sin pid válido"
    if not _proceso_vivo(pid):
        return f"el hijo {pid} ya no existe"
    identidad = _identidad_de(pid)
    arranque = hijo.get("arranque")
    if identidad is None or identidad[0] != pgid or (arranque and identidad[1] != arranque):
        return f"el pid {pid} ya es otro proceso ({identidad!r}); no se toca"
    _mata_grupo(pgid)
    return f"grupo huérfano {pgid} del gate {hijo.get('gate')!r} ({ejecutable}) eliminado"


def _aparta(origen: Path, etiqueta: str) -> Path:
    """Renombra ``origen`` a ``<nombre>.<etiqueta>-N`` con el primer N libre. Nunca borra."""
    n = 1
    while True:
        destino = origen.with_name(f"{origen.name}.{etiqueta}-{n}")
        if not os.path.lexists(destino):
            origen.rename(destino)
            return destino
        n += 1


def _recoge_residuos(raiz_staging: Path, composicion: str) -> list[str]:
    """Limpia lo que dejó una corrida anterior; devuelve lo que hizo, para el operador.

    - ``gates.en_curso/`` con marcador: si su runner sigue vivo, otra corrida está en
      marcha y se aborta; si no, se mata el hijo huérfano registrado y se aparta la
      evidencia parcial.
    - ``gates/`` completa: un PASS de ESTA composición se conserva y se aborta (repetirlo
      no añade nada y sobrescribirlo destruiría evidencia revisada); cualquier otra cosa
      —FAIL, otra composición, ilegible— se aparta.
    """
    acciones: list[str] = []
    en_curso = raiz_staging / DIR_EN_CURSO
    if en_curso.is_symlink():
        raise StagingError(f"{en_curso} es un enlace simbólico; no se usa ni se retira")
    if en_curso.exists():
        marcador = _lee_marcador(en_curso)
        if marcador is not None:
            runner = marcador.get("runner_pid")
            if isinstance(runner, int) and runner != os.getpid() and _proceso_vivo(runner):
                raise StagingError(
                    f"otra corrida de gates sigue en marcha sobre {raiz_staging} "
                    f"(runner pid {runner}); no se compite"
                )
            acciones.append(_mata_huerfano(marcador))
        apartado = _aparta(en_curso, "parcial")
        acciones.append(f"evidencia parcial apartada en {apartado.name}")

    carpeta = raiz_staging / DIR_EVIDENCIA
    if carpeta.is_symlink():
        raise StagingError(
            f"ya existe evidencia de gates en {carpeta} y es un enlace simbólico; no se usa"
        )
    if carpeta.exists():
        try:
            previa = EvidenciaGates.lee(raiz_staging)
        except StagingError as exc:
            apartado = _aparta(carpeta, "ilegible")
            acciones.append(f"evidencia previa ilegible apartada en {apartado.name}: {exc}")
        else:
            if previa.veredicto == VEREDICTO_REQUERIDO and previa.composicion == composicion:
                raise StagingError(
                    f"ya existe evidencia de gates en {carpeta} con PASS para esta misma "
                    "composición; una corrida no se sobrescribe. Revísala y retírala a mano, "
                    "o prepara otro staging"
                )
            motivo = "fail" if previa.veredicto != VEREDICTO_REQUERIDO else "otra-composicion"
            apartado = _aparta(carpeta, motivo)
            acciones.append(f"evidencia previa ({motivo}) apartada en {apartado.name}")
    return acciones


def _corre(
    spec: GateSpec,
    cwd: Path,
    ejecutable: Path,
    entorno: dict[str, str],
    marcador: _Marcador,
) -> _Ejecucion:
    """Ejecuta el argv exacto y traduce lo ocurrido a un resultado, sin juzgarlo todavía."""
    argv = [str(ejecutable), *spec.argv[1:]]
    digest = sha256_de(ejecutable)
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

    marcador.registra_hijo(spec.id, proceso.pid, str(ejecutable))
    try:
        try:
            salida, errores = proceso.communicate(timeout=spec.timeout_s)
        except subprocess.TimeoutExpired:
            _mata_grupo(proceso.pid)
            salida, errores = proceso.communicate()
            return _Ejecucion(
                None,
                -proceso.returncode if proceso.returncode < 0 else None,
                "timeout",
                f"venció el límite de {spec.timeout_s} s; se envió SIGKILL al grupo de procesos",
                salida or b"",
                errores or b"",
                str(ejecutable),
                digest,
            )
        except BaseException:
            # Interrupción del runner (Ctrl-C, SIGTERM): el hijo no se queda huérfano.
            _mata_grupo(proceso.pid)
            proceso.wait()
            raise
    finally:
        marcador.olvida_hijo()

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
            digest,
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
            digest,
        )
    return _Ejecucion(0, None, "", "", salida, errores, str(ejecutable), digest)


def _ejecuta_uno(spec: GateSpec, outputs_real: Path, marcador: _Marcador) -> _Ejecucion:
    try:
        cwd = _resuelve_cwd(outputs_real, spec)
    except StagingError as exc:
        return _Ejecucion(None, None, "cwd_invalido", str(exc), b"", b"", "")
    entorno = _construye_entorno(spec)
    try:
        ejecutable = _resuelve_ejecutable(spec, entorno)
    except StagingError as exc:
        return _Ejecucion(None, None, "ejecutable_ausente", str(exc), b"", b"", "")
    try:
        return _corre(spec, cwd, ejecutable, entorno, marcador)
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


@dataclass(frozen=True)
class ResultadoRunner:
    evidencia: EvidenciaGates
    acciones: tuple[str, ...]


def ejecuta_gates(
    raiz_staging: Path,
    politica: PoliticaCenso,
    *,
    destinos_vivos: Mapping[str, Path] | None = None,
) -> EvidenciaGates:
    """Corre todos los gates de la política sobre ``<staging>/outputs`` y sella la evidencia.

    Se ejecuta **antes** de podar el staging: la composición que certifican los gates es la
    del árbol completo, que es exactamente lo que ``seal`` recompone después como
    ``semilla + cambiados − lápidas``. Si un gate muta la composición, ese gate queda FAIL y
    los siguientes no se ejecutan.

    Devuelve la evidencia **releída desde disco**, con las mismas comprobaciones que hará
    ``seal``: lo que se devuelve es lo que quedó escrito, no lo que se pensaba escribir.
    """
    return ejecuta_gates_con_acciones(
        raiz_staging, politica, destinos_vivos=destinos_vivos
    ).evidencia


def ejecuta_gates_con_acciones(
    raiz_staging: Path,
    politica: PoliticaCenso,
    *,
    destinos_vivos: Mapping[str, Path] | None = None,
) -> ResultadoRunner:
    """Como ``ejecuta_gates``, devolviendo además qué residuos de corridas previas retiró."""
    outputs = raiz_staging / "outputs"
    _exige_directorio_real(outputs, "el directorio de artefactos")
    outputs_real = outputs.resolve()
    exige_sin_solape(outputs_real, politica, dict(destinos_vivos or {}))

    arbol = inventaria(outputs)
    for rel in arbol:
        valida_ruta_sellable(rel)
    composicion, _ = calcula_composicion({}, arbol, ())

    acciones = _recoge_residuos(raiz_staging, composicion)
    carpeta = raiz_staging / DIR_EN_CURSO
    try:
        carpeta.mkdir()
    except FileExistsError as exc:
        raise StagingError(
            f"la carpeta de evidencia apareció a mitad de camino: {carpeta}"
        ) from exc
    marcador = _Marcador(carpeta)
    marcador.escribe()

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
            ejecucion = _ejecuta_uno(spec, outputs_real, marcador)
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
            ejecutable_sha256=ejecucion.ejecutable_sha256,
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
    # El marcador no es evidencia: se retira y la carpeta pasa a su nombre final de una vez.
    marcador.ruta.unlink()
    destino = raiz_staging / DIR_EVIDENCIA
    if os.path.lexists(destino):
        raise StagingError(f"{destino} apareció mientras corrían los gates; no se pisa")
    carpeta.rename(destino)
    return ResultadoRunner(EvidenciaGates.lee(raiz_staging), tuple(acciones))
