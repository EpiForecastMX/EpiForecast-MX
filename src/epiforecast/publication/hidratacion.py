"""Hidratación por allowlist: un sandbox del backend con exactamente las entradas declaradas.

Los generadores del refresh leen del árbol real: consolidado, forecasts, tablas de
producción, Tableau, PDFs. Copiar el árbol entero no es una frontera (34 GB, `.git`,
caches, WIP ajeno) y un clon de git no trae nada de eso (lo materializa DVC). El sandbox
es el término medio honesto: el código rastreado del HEAD que se sella, más **sólo** las
entradas que la lista versionada `config/publication/entradas_semanales.json` declara,
cada una copiada como archivo regular con tamaño y SHA256 en un inventario.

Y la parte que evita el fallo silencioso: antes de generar nada, el contrato de cobertura
(`contratos_datos`) exige sobre esas entradas los conjuntos exactos —entidades, series,
paridad de corte—. Una allowlist corta no hace reventar a los generadores; los hace
producir un candidato más pequeño y plausible. Aquí revienta antes.

El sandbox vive junto al directorio de trabajo (`<trabajo>.sandbox/`), con el backend en
`EpiForecast-MX/` y un enlace `EpiForecast-IMSS-Dashboard -> <trabajo>/outputs/dashboard`,
porque hay generadores que resuelven el repositorio del dashboard como hermano del
backend. El enlace está fuera de `outputs/`, así que el inventario del candidato no lo ve.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
from typing import Any

from epiforecast.publication.contratos_datos import (
    Cobertura,
    ContratoCobertura,
    revisa_consolidado,
    revisa_forecasts_listados,
    revisa_produccion_dengue,
    revisa_tabla_produccion,
    slug,
)
from epiforecast.publication.materializa import _archiva, _extrae, exige_materializacion
from epiforecast.publication.weekly_staging import (
    ARCHIVO_ENTRADAS,
    DIR_INPUTS,
    RUTA_LISTA_ENTRADAS,
    Boletin,
    RegistroHidratacion,
    StagingError,
    _sin_duplicados,
    sha256_de,
)

NOMBRE_BACKEND = "EpiForecast-MX"
NOMBRE_DASHBOARD = "EpiForecast-IMSS-Dashboard"
VERSION_LISTA = "entradas/2"
ROLES = (
    "consolidado",
    "forecast",
    "forecast_conteo",
    "tabla_produccion",
    "produccion_dengue",
    "tabla",
    "tableau",
    "inegi",
    "contexto",
    "metricas",  # métricas CV de los modelos congelados (entrada de tabla-produccion)
    "dengue_interim",  # serie extraída y manifiesto de Dengue: la extracción incremental parte de ahí
    "geo",  # geometría de entidades para los mapas
)
# Roles que ningún generador del refresh reescribe: si al sellar difieren de lo hidratado,
# algo escribió sobre una entrada y el candidato no salió de las entradas selladas.
ROLES_INMUTABLES = frozenset(
    {"forecast", "forecast_conteo", "inegi", "contexto", "metricas", "geo", "pdf"}
)
_RE_NOMBRE_PDF = re.compile(r"[A-Za-z0-9_.-]{1,120}\.pdf")
_CARACTERES_PATRON = frozenset("*?[")


@dataclass(frozen=True)
class Entrada:
    ruta: str
    rol: str
    obligatoria: bool

    @property
    def es_patron(self) -> bool:
        return any(c in self.ruta for c in _CARACTERES_PATRON)


@dataclass(frozen=True)
class ListaEntradas:
    """La allowlist versionada, leída del HEAD que se sella y comparada con el worktree."""

    version: str
    sha256: str
    directorio_boletines: str
    profundidad_minima: int
    entradas: tuple[Entrada, ...]
    # Directorios que los generadores usan como scratch (intermedios regenerables) y que el
    # `git archive` no trae porque están ignorados. El ensayo real abortó en `dengue-prep`
    # por «Cannot save file into a non-existent directory: 'data/raw'».
    directorios_scratch: tuple[str, ...] = ()

    @staticmethod
    def del_head(repo: Path, head: str) -> ListaEntradas:
        salida = subprocess.run(
            ["git", "-C", str(repo), "show", f"{head}:{RUTA_LISTA_ENTRADAS}"], capture_output=True
        )
        if salida.returncode != 0:
            raise StagingError(
                f"la lista de entradas {RUTA_LISTA_ENTRADAS} no está en {head[:12]}: "
                f"{salida.stderr.decode(errors='replace').strip()}"
            )
        ruta = repo / RUTA_LISTA_ENTRADAS
        if ruta.is_symlink() or not ruta.is_file():
            raise StagingError(f"la lista de entradas {ruta} no existe en el árbol de trabajo")
        if ruta.read_bytes() != salida.stdout:
            raise StagingError(
                f"la lista de entradas {RUTA_LISTA_ENTRADAS} difiere de la versión de {head[:12]}"
            )
        return ListaEntradas.desde_bytes(salida.stdout)

    @staticmethod
    def desde_bytes(crudo_bytes: bytes) -> ListaEntradas:
        try:
            crudo = json.loads(crudo_bytes, object_pairs_hook=_sin_duplicados)
        except json.JSONDecodeError as exc:
            raise StagingError(f"lista de entradas ilegible: {exc}") from exc
        if not isinstance(crudo, dict) or set(crudo) != {
            "version",
            "directorio_boletines",
            "profundidad_minima_semanas",
            "directorios_scratch",
            "entradas",
        }:
            raise StagingError(
                "lista de entradas malformada: claves {version, directorio_boletines, "
                "profundidad_minima_semanas, directorios_scratch, entradas}"
            )
        scratch = crudo["directorios_scratch"]
        if not isinstance(scratch, list) or len(set(scratch)) != len(scratch):
            raise StagingError("directorios_scratch tiene que ser una lista sin repetidos")
        for directorio_scratch in scratch:
            _valida_ruta_relativa(directorio_scratch, "directorio scratch")
        if crudo["version"] != VERSION_LISTA:
            raise StagingError(f"lista de entradas de otra versión: {crudo['version']!r}")
        directorio = crudo["directorio_boletines"]
        _valida_ruta_relativa(directorio, "directorio de boletines")
        profundidad = crudo["profundidad_minima_semanas"]
        if isinstance(profundidad, bool) or not isinstance(profundidad, int) or profundidad < 1:
            raise StagingError("profundidad_minima_semanas tiene que ser un entero >= 1")
        if not isinstance(crudo["entradas"], list) or not crudo["entradas"]:
            raise StagingError("la lista de entradas no declara ninguna entrada")
        entradas: list[Entrada] = []
        for item in crudo["entradas"]:
            if not isinstance(item, dict) or set(item) != {"ruta", "rol", "obligatoria"}:
                raise StagingError(f"entrada malformada: {item!r}")
            _valida_ruta_relativa(item["ruta"], "ruta de entrada")
            if item["rol"] not in ROLES:
                raise StagingError(f"rol de entrada desconocido: {item['rol']!r}")
            if not isinstance(item["obligatoria"], bool):
                raise StagingError(f"'obligatoria' tiene que ser booleano en {item['ruta']}")
            entrada = Entrada(item["ruta"], item["rol"], item["obligatoria"])
            if entrada.es_patron and entrada.rol in ("consolidado", "tabla_produccion"):
                raise StagingError(
                    f"un patrón no puede tener el rol {entrada.rol!r}: {item['ruta']}"
                )
            entradas.append(entrada)
        rutas = [e.ruta for e in entradas]
        if len(set(rutas)) != len(rutas):
            raise StagingError("la lista de entradas repite rutas")
        consolidados = [e for e in entradas if e.rol == "consolidado"]
        if len(consolidados) != 1 or not consolidados[0].obligatoria:
            raise StagingError(
                "la lista tiene que declarar exactamente un consolidado obligatorio"
            )
        return ListaEntradas(
            version=crudo["version"],
            sha256=hashlib.sha256(crudo_bytes).hexdigest(),
            directorio_boletines=directorio,
            profundidad_minima=profundidad,
            entradas=tuple(entradas),
            directorios_scratch=tuple(scratch),
        )

    @property
    def consolidado(self) -> str:
        return next(e.ruta for e in self.entradas if e.rol == "consolidado")


def _valida_ruta_relativa(valor: Any, que: str) -> None:
    if not isinstance(valor, str) or not valor or valor != valor.strip():
        raise StagingError(f"{que} inválida: {valor!r}")
    if valor.startswith("/") or "\\" in valor or "\x00" in valor:
        raise StagingError(f"{que} tiene que ser relativa POSIX: {valor!r}")
    if any(p in ("", ".", "..") for p in valor.split("/")):
        raise StagingError(f"{que} con componente vacío, '.' o '..': {valor!r}")


def _copia_regular(origen: Path, destino: Path) -> tuple[int, str]:
    """Copia un archivo regular (no enlace, no especial) en exclusiva; devuelve bytes y SHA256."""
    try:
        estado = origen.lstat()
    except FileNotFoundError as exc:
        raise StagingError(f"no existe la entrada {origen}") from exc
    if stat.S_ISLNK(estado.st_mode):
        raise StagingError(f"la entrada es un enlace simbólico: {origen}")
    if not stat.S_ISREG(estado.st_mode):
        raise StagingError(f"la entrada no es un archivo regular: {origen}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.is_symlink() or destino.exists():
        raise StagingError(f"la copia de entrada ya existe: {destino}")
    # El digest del ORIGEN se toma antes de copiar: es lo que se declara haber hidratado.
    # Tomarlo después dejaba pasar un origen que cambió durante la copia como si la copia
    # fuera fiel (los dos digests salían del mismo estado final).
    digest = sha256_de(origen)
    with origen.open("rb") as f, destino.open("xb") as g:
        shutil.copyfileobj(f, g, 1 << 20)
    # Se vuelve a leer el origen DESPUÉS: si cambió durante la copia (aunque conserve el
    # tamaño), la copia no es fiel a lo que se declara. Cuesta una lectura más por entrada.
    if (
        destino.stat().st_size != estado.st_size
        or sha256_de(destino) != digest
        or origen.lstat().st_size != estado.st_size
        or sha256_de(origen) != digest
    ):
        raise StagingError(f"la copia de {origen} no coincide con el original")
    # La copia conserva las marcas de tiempo del origen: `build_web_knowledge.py` deriva
    # «último entrenamiento» del mtime del forecast, y una copia fresca lo convertía en la
    # fecha de la hidratación (P1, 2-sep-2026: publicaba un entrenamiento que no existió).
    os.utime(destino, ns=(estado.st_atime_ns, estado.st_mtime_ns))
    return estado.st_size, digest


def _hidrata_entrada(origen: Path, destino: Path) -> tuple[int, str]:
    """Copia la entrada al sandbox o, si es un archivo RASTREADO, exige que coincida.

    `git archive` ya deja en el sandbox lo que el HEAD rastrea (por ejemplo las tablas de
    producción). Para esas entradas la fuente es el HEAD, no el árbol de trabajo: si el
    archivo del worktree difiere, hay un cambio de datos sin confirmar y no se hidrata a
    ciegas con ninguno de los dos. El inventario registra el digest del sandbox.
    """
    if not os.path.lexists(destino):
        return _copia_regular(origen, destino)
    if destino.is_symlink() or not destino.is_file():
        raise StagingError(
            f"la entrada rastreada en el sandbox no es un archivo regular: {destino}"
        )
    estado = origen.lstat()
    if stat.S_ISLNK(estado.st_mode) or not stat.S_ISREG(estado.st_mode):
        raise StagingError(f"la entrada no es un archivo regular: {origen}")
    digest_head = sha256_de(destino)
    if sha256_de(origen) != digest_head:
        raise StagingError(
            f"la entrada rastreada {origen.name} difiere del HEAD en el árbol de trabajo; "
            "confírmala o descártala antes de hidratar"
        )
    return destino.stat().st_size, digest_head


def _expande(repo_real: Path, entrada: Entrada) -> list[str]:
    """Rutas concretas de una entrada: la suya, o lo que casa con su patrón (ordenado).

    Un patrón obligatorio sin coincidencias es una entrada obligatoria ausente. Lo que casa
    tiene que ser un archivo regular y respetar la gramática de rutas de entrada.
    """
    if not entrada.es_patron:
        if not os.path.lexists(repo_real / entrada.ruta):
            if entrada.obligatoria:
                raise StagingError(f"falta la entrada obligatoria {entrada.ruta}")
            return []
        return [entrada.ruta]
    coincidencias: list[str] = []
    for ruta in sorted(repo_real.glob(entrada.ruta)):
        rel = ruta.relative_to(repo_real).as_posix()
        _valida_ruta_relativa(rel, "ruta de entrada")
        # `*` sigue enlaces de directorio: un `models/prophet -> /fuera` haría que el
        # inventario declarara como intra-repo lo que vive en otro sitio.
        actual = repo_real
        for parte in rel.split("/"):
            actual = actual / parte
            if actual.is_symlink():
                raise StagingError(
                    f"el patrón {entrada.ruta} casó a través de un enlace simbólico: {rel}"
                )
        if not ruta.is_file():
            raise StagingError(f"el patrón {entrada.ruta} casó con algo que no es archivo: {rel}")
        coincidencias.append(rel)
    if not coincidencias and entrada.obligatoria:
        raise StagingError(f"el patrón obligatorio {entrada.ruta} no casa con ningún archivo")
    return coincidencias


@dataclass(frozen=True)
class Hidratacion:
    trabajo: Path
    sandbox: Path
    registro: RegistroHidratacion
    coberturas: tuple[Cobertura, ...]


def hidrata(
    trabajo: Path,
    repo_backend: Path,
    head_backend: str,
    *,
    padecimientos_autorizados: tuple[str, ...],
    boletines: tuple[Boletin, ...] = (),
    contrato: ContratoCobertura,
) -> Hidratacion:
    """Construye el sandbox, copia las entradas declaradas y exige el contrato de cobertura.

    `trabajo` tiene que existir ya con `outputs/` (lo crea `materialize`): el sandbox enlaza
    ahí el dashboard candidato. El sandbox se crea nuevo; `inputs/` y `entradas.json` se
    escriben en exclusiva dentro del trabajo. Si algo falla, el sandbox se retira entero.
    """
    outputs = trabajo / "outputs"
    if (
        trabajo.is_symlink()
        or not trabajo.is_dir()
        or outputs.is_symlink()
        or not outputs.is_dir()
    ):
        raise StagingError(f"el trabajo {trabajo} no está materializado (falta outputs/)")
    if (trabajo / DIR_INPUTS).exists() or (trabajo / ARCHIVO_ENTRADAS).exists():
        raise StagingError(f"{trabajo} ya está hidratado; un trabajo no se hidrata dos veces")
    sandbox = trabajo.parent / f"{trabajo.name}.sandbox"
    if sandbox.is_symlink() or sandbox.exists():
        raise StagingError(f"ya existe el sandbox {sandbox}; no se pisa")
    # El HEAD que se hidrata es el HEAD del que se materializó el candidato.
    exige_materializacion(trabajo, head_backend=head_backend)
    lista = ListaEntradas.del_head(repo_backend, head_backend)
    if lista.profundidad_minima != contrato.profundidad_minima:
        raise StagingError(
            f"la profundidad mínima de la lista ({lista.profundidad_minima}) no es la del "
            f"contrato ({contrato.profundidad_minima})"
        )
    repo_real = repo_backend.resolve()

    sandbox.mkdir()
    try:
        backend = sandbox / NOMBRE_BACKEND
        backend.mkdir()
        _extrae(_archiva(repo_real, head_backend, None), backend)
        # Hermano del backend, como en el workspace real: apunta al dashboard candidato.
        (sandbox / NOMBRE_DASHBOARD).symlink_to(
            os.path.relpath(outputs / "dashboard", sandbox), target_is_directory=True
        )

        # Scratch de los generadores: existen vacíos; lo que escriban ahí es intermedio y
        # no entra en el inventario de entradas ni en el candidato.
        for directorio_scratch in lista.directorios_scratch:
            (backend / directorio_scratch).mkdir(parents=True, exist_ok=True)

        inventario: dict[str, dict[str, Any]] = {}
        for entrada in lista.entradas:
            for rel in _expande(repo_real, entrada):
                if rel in inventario:
                    raise StagingError(f"la entrada {rel} la declaran dos patrones/rutas")
                tamano, digest = _hidrata_entrada(repo_real / rel, backend / rel)
                inventario[rel] = {"rol": entrada.rol, "bytes": tamano, "sha256": digest}

        inputs = trabajo / DIR_INPUTS
        inputs.mkdir()
        (inputs / "boletines").mkdir()
        vistos: set[str] = set()
        for boletin in boletines:
            if not _RE_NOMBRE_PDF.fullmatch(boletin.nombre) or boletin.nombre in vistos:
                raise StagingError(f"nombre de boletín inválido o repetido: {boletin.nombre!r}")
            vistos.add(boletin.nombre)
            origen = repo_real / lista.directorio_boletines / boletin.nombre
            tamano, digest = _copia_regular(
                origen, backend / lista.directorio_boletines / boletin.nombre
            )
            if tamano != boletin.bytes or digest != boletin.sha256:
                raise StagingError(
                    f"el boletín {boletin.nombre} no coincide con lo declarado "
                    f"(bytes {tamano} vs {boletin.bytes}, sha {digest[:12]}… vs {boletin.sha256[:12]}…)"
                )
            _copia_regular(origen, inputs / "boletines" / boletin.nombre)
            inventario[f"{lista.directorio_boletines}/{boletin.nombre}"] = {
                "rol": "pdf",
                "bytes": tamano,
                "sha256": digest,
            }
        _copia_regular(repo_real / lista.consolidado, inputs / "consolidado_base.csv")

        coberturas = _revisa(backend, inventario, contrato, padecimientos_autorizados)
        registro = RegistroHidratacion(
            head_backend=head_backend,
            lista={"version": lista.version, "sha256": lista.sha256},
            sandbox=str(backend.resolve()),
            consolidado=lista.consolidado,
            entradas=dict(sorted(inventario.items())),
            boletines=tuple(boletines),
            cobertura={c.fuente: dict(c.cifras) for c in coberturas},
        )
        registro.escribe(trabajo)
    except BaseException:
        shutil.rmtree(sandbox, ignore_errors=True)
        shutil.rmtree(trabajo / DIR_INPUTS, ignore_errors=True)
        (trabajo / ARCHIVO_ENTRADAS).unlink(missing_ok=True)
        (trabajo / "entradas.sha256").unlink(missing_ok=True)
        raise
    return Hidratacion(trabajo=trabajo, sandbox=sandbox, registro=registro, coberturas=coberturas)


def _revisa(
    backend: Path,
    inventario: dict[str, dict[str, Any]],
    contrato: ContratoCobertura,
    padecimientos_autorizados: tuple[str, ...],
) -> tuple[Cobertura, ...]:
    """El contrato, sobre lo hidratado y según el rol de cada entrada. Falla cerrado."""
    por_rol: dict[str, list[str]] = {}
    for ruta, meta in inventario.items():
        por_rol.setdefault(str(meta["rol"]), []).append(ruta)
    # Lo autorizado tiene que estar en el contrato, pero el contrato se exige sobre TODOS
    # los publicados: autorizar sólo «Dengue» no reduce la profundidad ni la paridad a Dengue.
    autorizados = {slug(p) for p in padecimientos_autorizados}
    if fuera := sorted(autorizados - set(contrato.padecimientos)):
        raise StagingError(f"padecimientos autorizados fuera del contrato: {fuera}")
    coberturas: list[Cobertura] = [
        revisa_consolidado(backend / por_rol["consolidado"][0], contrato, contrato.padecimientos)
    ]
    if forecasts := por_rol.get("forecast"):
        coberturas.append(revisa_forecasts_listados([backend / r for r in forecasts], contrato))
    if conteo := por_rol.get("forecast_conteo"):
        # Motores de la cohorte de conteo (NBGLM para Dengue): sólo sus series, exactas.
        coberturas.append(
            revisa_forecasts_listados(
                [backend / r for r in conteo],
                contrato,
                esperadas=frozenset().union(*(contrato.productos(p) for p in contrato.conteo)),
                fuente="forecasts_conteo",
            )
        )
    for ruta in por_rol.get("tabla_produccion", []):
        coberturas.append(revisa_tabla_produccion(backend / ruta, contrato))
    for ruta in por_rol.get("produccion_dengue", []):
        coberturas.append(revisa_produccion_dengue(backend / ruta, contrato))
    problemas = [p for c in coberturas for p in c.problemas]
    if problemas:
        raise StagingError(
            "la hidratación no cubre el contrato; no se genera con entradas cortas:\n  - "
            + "\n  - ".join(problemas)
        )
    return tuple(coberturas)
