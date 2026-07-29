"""C7.6-AUTO-B1-HARNESS — orquestador de readiness de publicación de un release.

    python -m scripts.publication_readiness local --disease <id> --release-target <ruta>
    python -m scripts.publication_readiness external-readonly --local-evidence <manifest>

Por qué existe: la preparación de un release ya estaba entera en el código, pero repartida entre dos
CLI y un manual de 288 líneas. Un procedimiento que vive en un manual se ejecuta distinto cada vez y
no deja evidencia comparable. Aquí se ejecuta una vez, en un orden fijo, y deja un manifiesto.

Los dos flujos están separados a propósito:

* `local` **no lee ninguna variable de Google, no importa `gspread` y no abre nada**. Cierra todo lo
  que puede cerrarse sin provisionar nada, y termina en `PASS_LOCAL` + `BLOCKED_EXTERNAL`.
* `external-readonly` exige las tres variables y sólo mira: dos inventarios, el plan en seco y el
  workbook. No existe subcomando, bandera ni llamada equivalente a aplicar, recuperar, promover o
  borrar; la única función del namespace que se invoca —`promotion_plan`— sólo lee.

`BLOCKED_EXTERNAL` no es un fallo del carril local ni un PASS de B1: es el nombre honesto de lo que
falta, que es provisionar Google una vez.

Genérico: padecimiento, release, conteos y canales salen del registry y de los manifiestos. Ni un
nombre de padecimiento, ni un motor, ni un conteo escritos aquí.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
from typing import Any

from epiforecast import registry
from epiforecast.publication.compiler import MODE_CANDIDATE, compile_release
from epiforecast.publication.recovery import table_inventory
from epiforecast.publication.shards import emit_shards
from epiforecast.publication.sheets_sink import (
    PRODUCTION_ID_ENV,
    SERVICE_ACCOUNT_ENV,
    STAGING_ID_ENV,
    staging_ids,
)
from epiforecast.publication.status import load_declared_status
from epiforecast.publication.tableau_adapter import (
    PROMOTION_PLAN_SCHEMA,
    TABLES,
    TableauAdapterError,
    build_tables,
    managed_tables,
    promotion_plan,
)
from epiforecast.publication.tableau_workbook import build_workbook_xml, verify_workbook
from epiforecast.runner.artifact_identity import ArtifactValidationError, equal, require
from epiforecast.runner.release_contract import canonical_json, sha256_bytes
from epiforecast.runner.release_store import diff_trees, release_path

READINESS_SCHEMA = "readiness_manifest.v1"
EXTERNAL_SCHEMA = "external_preflight.v2"
# v1 no se migra ni se acepta por fallback: no existe ninguno productivo, y mantener dos
# lectores es como se acaba aceptando en silencio una evidencia sin identidad de hoja.
EXTERNAL_SCHEMA_RETIRADO = "external_preflight.v1"
READINESS_FILE = "readiness_manifest.json"
EXTERNAL_FILE = "external_preflight.json"

CMD_LOCAL = "local"
CMD_EXTERNAL = "external-readonly"

RC_OK = 0
RC_FAIL = 1
RC_BLOCKED = 3  # falta el entorno externo: no es un fallo del carril local

STATUS_PASS_LOCAL = "PASS_LOCAL"
STATUS_BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
STATUS_READY_EXTERNAL = "PASS_EXTERNAL_READONLY"
STATUS_FAIL = "FAIL"

# Identidad del workbook local. No es un id de hoja y se nota: nadie puede confundirla con una.
LOCAL_SHEET_IDENTITY = "local-readiness-no-remote-spreadsheet"

# Lo que ninguna automatización puede cerrar. Se declara para que nadie lo lea como PASS.
MANUAL_REQUIREMENTS: tuple[str, ...] = (
    "netlify_branch_preview_inventory",
    "staging_spreadsheet_created",
    "service_account_shared_with_staging",
    "staging_and_production_ids_exported",
    "tableau_desktop_open_and_refresh",
    "write_authorization_over_staging",
    "lifecycle_and_pointer_activation",
    "merge_deploy_and_public_smoke",
)

# Forma CERRADA del manifiesto local. Ni una clave más, ni una menos.
READINESS_KEYS: tuple[str, ...] = (
    "artifact_backend",
    "declared_channels",
    "disease_id",
    "external_status",
    "failures",
    "gallery_enabled",
    "manifest_digest",
    "manual_requirements",
    "manual_requirements_status",
    "public_writes",
    "release_id",
    "reproducible",
    "schema",
    "selection_policy",
    "shard",
    "shard_files",
    "shard_manifest_digest",
    "shard_relative_root",
    "shard_tree_digest",
    "status",
    "table_digests",
    "tables",
    "versions",
    "workbook",
)

# Forma CERRADA del preflight externo.
EXTERNAL_KEYS: tuple[str, ...] = (
    "disease_id",
    "environment_present",
    "foreign_tabs",
    "inventory_digest",
    "local_manifest_digest",
    "manual_requirements_status",
    "preflight_digest",
    "production_identity_digest",
    "promotion_plan",
    "release_id",
    "schema",
    "staging_identity_digest",
    "status",
    "workbook",
)

# Forma CERRADA del plan sellado: el contrato entero de `promotion_plan`, no sólo sus pasos.
PLAN_KEYS: tuple[str, ...] = ("digests", "namespace", "rows", "schema", "steps")
WORKBOOK_KEYS: tuple[str, ...] = ("digest", "tables", "tableau_desktop_validated")

# Separación de contexto: el mismo id no puede producir el mismo fingerprint en los dos papeles.
PURPOSE_STAGING = "c7-staging"
PURPOSE_PRODUCTION = "c7-production"

# Gramática CERRADA de un paso del plan. Se parsea, no se indexa el resultado de un `split`.
_PASO = re.compile(
    r"^(?P<verbo>write|rename|drop):(?P<origen>[A-Za-z0-9_]+)(?:->(?P<destino>[A-Za-z0-9_]+))?$"
)

# Claves que el manifiesto local y el shard tienen que declarar IGUAL. Copiar sin cruzar es lo que
# deja pasar una identidad fabricada (R120-P0-2).
IDENTIDAD_CRUZADA: tuple[str, ...] = (
    "lifecycle",
    "rows",
    "products",
    "channels_emitted",
    "publication_label",
)

_LARGO_SOSPECHOSO = re.compile(r"[A-Za-z0-9_\-]{32,}")
# Forma de un digest. Más estricta que medir el largo: también rechaza 64 caracteres que no sean hex.
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _digest_de_arbol(raiz: Path) -> str:
    """Digest del árbol ENTERO: rutas relativas ordenadas con su digest. Identidad, no muestreo."""
    archivos = {
        p.relative_to(raiz).as_posix(): sha256_bytes(p.read_bytes())
        for p in sorted(raiz.rglob("*"))
        if p.is_file()
    }
    return sha256_bytes(canonical_json(archivos))


def _ruta_relativa_segura(relativa: str, base: Path) -> Path:
    """Resuelve una ruta declarada dentro de la evidencia, o falla.

    Una ruta absoluta no es portable; `..` sale de la evidencia; un symlink puede apuntar a
    cualquier parte. Se comprueban las tres, y sobre la ruta ya resuelta.
    """
    require(bool(relativa), "readiness: el manifiesto no declara shard_relative_root")
    candidata = Path(relativa)
    require(not candidata.is_absolute(), f"readiness: {relativa!r} es una ruta absoluta")
    require(
        all(parte not in ("..", ".") for parte in candidata.parts),
        f"readiness: {relativa!r} contiene componentes relativos",
    )
    raiz = base.resolve()
    destino = (raiz / candidata).resolve()
    require(
        destino.is_relative_to(raiz),
        f"readiness: {relativa!r} resuelve fuera del directorio de evidencia",
    )
    require(destino.is_dir(), f"readiness: {relativa!r} no existe bajo la evidencia")
    return destino


# ── Validadores de forma: tipos y VALORES, no sólo nombres de clave ────────────────────────────
# La forma cerrada por claves no basta. `namespace=null` o `rows="bad"` pasaban el control de claves
# y reventaban después en el primer `sorted`, `.items` o `dict`, saliendo como TypeError,
# AttributeError o ValueError: errores incidentales del intérprete, no rechazos de dominio
# (R126-P1). Aquí el tipo se demuestra ANTES de tocar el valor.


def _exige_texto(valor: Any, etiqueta: str) -> str:
    require(isinstance(valor, str), f"readiness: {etiqueta} no es texto")
    return str(valor)


def _exige_sha256(valor: Any, etiqueta: str) -> str:
    texto = _exige_texto(valor, etiqueta)
    require(bool(_SHA256.fullmatch(texto)), f"readiness: {etiqueta} no es un sha256")
    return texto


def _exige_bool(valor: Any, etiqueta: str) -> bool:
    # `0`, `"false"` y `None` no son booleanos: en un contrato, «casi» es «no».
    require(isinstance(valor, bool), f"readiness: {etiqueta} no es un booleano")
    return bool(valor)


def _exige_entero_no_negativo(valor: Any, etiqueta: str) -> int:
    require(
        isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0,
        f"readiness: {etiqueta} no es un entero no negativo",
    )
    return int(valor)


def _exige_lista_unica_de_texto(valor: Any, etiqueta: str) -> list[str]:
    require(isinstance(valor, list), f"readiness: {etiqueta} no es una lista")
    for i, elemento in enumerate(valor):
        _exige_texto(elemento, f"{etiqueta}[{i}]")
    require(len(set(valor)) == len(valor), f"readiness: {etiqueta} trae elementos repetidos")
    return [str(v) for v in valor]


def _exige_claves_exactas(valor: Any, claves: Sequence[str], etiqueta: str) -> dict[str, Any]:
    require(isinstance(valor, dict), f"readiness: {etiqueta} no es un mapeo")
    _exige_forma_cerrada(valor, sorted(claves), etiqueta)
    return dict(valor)


def _check_forma_del_plan(plan: Any) -> None:
    """Forma del plan sellado: tipos y valores de cada campo, antes de cruzarlo con nada."""
    _exige_claves_exactas(plan, PLAN_KEYS, "promotion_plan")
    equal("readiness: schema del plan", plan["schema"], PROMOTION_PLAN_SCHEMA)
    namespace = _exige_lista_unica_de_texto(plan["namespace"], "promotion_plan.namespace")
    equal("readiness: namespace del plan", sorted(namespace), sorted(TABLES))
    require(isinstance(plan["steps"], list), "readiness: promotion_plan.steps no es una lista")
    for paso in plan["steps"]:
        _check_paso(paso)
    filas = _exige_claves_exactas(plan["rows"], TABLES, "promotion_plan.rows")
    for tabla, cuenta in sorted(filas.items()):
        _exige_entero_no_negativo(cuenta, f"promotion_plan.rows[{tabla}]")
    digests = _exige_claves_exactas(plan["digests"], TABLES, "promotion_plan.digests")
    for tabla, digest in sorted(digests.items()):
        _exige_sha256(digest, f"promotion_plan.digests[{tabla}]")


def _check_forma_del_workbook(workbook: Any) -> None:
    _exige_claves_exactas(workbook, WORKBOOK_KEYS, "workbook")
    _exige_sha256(workbook["digest"], "workbook.digest")
    tablas = _exige_lista_unica_de_texto(workbook["tables"], "workbook.tables")
    equal("readiness: tablas del workbook", sorted(tablas), sorted(TABLES))
    require(
        _exige_bool(workbook["tableau_desktop_validated"], "workbook.tableau_desktop_validated")
        is False,
        "readiness: el preflight se declara validado en Tableau Desktop, y eso es un gate manual",
    )


def check_external_shape(payload: Any) -> None:
    """Forma COMPLETA de `external_preflight.v2`. La usan el productor y el consumidor.

    Una sola definición: si el productor validara con un criterio y el loader con otro, el que
    escribe podría emitir algo que el que lee rechaza, o —peor— al revés.
    """
    _exige_claves_exactas(payload, EXTERNAL_KEYS, EXTERNAL_FILE)
    equal("readiness: schema del preflight externo", payload["schema"], EXTERNAL_SCHEMA)
    equal("readiness: estado del preflight externo", payload["status"], STATUS_READY_EXTERNAL)
    equal(
        "readiness: manual_requirements_status del preflight",
        payload["manual_requirements_status"],
        "PENDING",
    )
    for clave in ("disease_id", "release_id"):
        require(bool(_exige_texto(payload[clave], clave)), f"readiness: {clave} vacío")
    for clave in (
        "local_manifest_digest",
        "inventory_digest",
        "preflight_digest",
        "staging_identity_digest",
        "production_identity_digest",
    ):
        _exige_sha256(payload[clave], clave)
    _exige_lista_unica_de_texto(payload["foreign_tabs"], "foreign_tabs")
    entorno = _exige_claves_exactas(
        payload["environment_present"],
        (STAGING_ID_ENV, PRODUCTION_ID_ENV, SERVICE_ACCOUNT_ENV),
        "environment_present",
    )
    for variable, presente in sorted(entorno.items()):
        _exige_bool(presente, f"environment_present[{variable}]")
    _check_forma_del_plan(payload["promotion_plan"])
    _check_forma_del_workbook(payload["workbook"])


def identity_digest(purpose: str, identificador: str) -> str:
    """Huella de una hoja SIN el id.

    La evidencia tiene que poder decir qué hoja inspeccionó, y no puede decirlo escribiendo el id.
    El `purpose` separa contextos: la misma hoja usada como staging y como producción no produce la
    misma huella, así que confundir las variables no pasa desapercibido.
    """
    require(bool(identificador), f"readiness: no hay identificador para {purpose}")
    return sha256_bytes(canonical_json({"purpose": purpose, "id": identificador}))


def _check_paso(paso: Any) -> None:
    """Valida un paso contra una gramática cerrada.

    Antes se hacía `p.split(":")[1].split("->")[0]`: un paso malformado salía como `IndexError`, y
    un artefacto inválido no puede escapar como fallo accidental del parser (R124-P1).
    """
    require(isinstance(paso, str), f"readiness: paso del plan que no es texto: {paso!r}")
    encaje = _PASO.match(paso)
    require(encaje is not None, f"readiness: paso fuera de la gramática del plan: {paso!r}")
    assert encaje is not None  # noqa: S101 — para mypy
    verbo, origen, destino = encaje.group("verbo"), encaje.group("origen"), encaje.group("destino")
    require(
        (verbo == "rename") == (destino is not None),
        f"readiness: {paso!r} usa la flecha de forma incompatible con «{verbo}»",
    )
    gestionadas = managed_tables()
    for tabla in (origen, destino):
        require(
            tabla is None or tabla in gestionadas,
            f"readiness: {paso!r} nombra una tabla fuera del namespace administrado",
        )


def _archivo_del_inventario(relativo: str, raiz: Path) -> Path:
    """Resuelve una entrada del inventario dentro del shard, o falla.

    Un inventario es una lista de rutas relativas canónicas. Una ruta absoluta, un `..` o un symlink
    convierten «verificar el shard» en «verificar lo que haya al otro lado del enlace».
    """
    require(bool(relativo), "readiness: el inventario del shard trae una ruta vacía")
    candidata = Path(relativo)
    require(not candidata.is_absolute(), f"readiness: {relativo!r} es una ruta absoluta")
    require(
        all(parte not in ("..", ".") for parte in candidata.parts),
        f"readiness: {relativo!r} contiene componentes relativos",
    )
    # La clave del inventario tiene que ser la forma canónica: `./x`, `a//b` o `a/` describen el
    # mismo archivo con otra cadena, y un inventario que admite dos grafías de una ruta no es un
    # inventario exacto.
    require(
        candidata.as_posix() == relativo,
        f"readiness: {relativo!r} no es la forma canónica de la ruta",
    )
    base = raiz.resolve()
    destino = base / candidata
    require(
        not destino.is_symlink(), f"readiness: {relativo!r} es un symlink, no un archivo del shard"
    )
    require(destino.resolve().is_relative_to(base), f"readiness: {relativo!r} escapa del shard")
    require(destino.is_file(), f"readiness: el shard no trae {relativo}")
    return destino


def _exige_inventario_exacto(declarado: Mapping[str, Any], sellado: Mapping[str, Any]) -> None:
    """El inventario local declara TODOS y SÓLO los archivos que el shard sella.

    Comprobar cada entrada declarada no basta: quitar una del inventario local y volver a sellar la
    capa exterior dejaba pasar un manifiesto que afirmaba menos de lo que el shard contiene
    (R122-P1). El `shard_tree_digest` impide sustituir bytes, no corrige una afirmación falsa.
    """
    require(
        isinstance(declarado, dict) and isinstance(sellado, dict),
        "readiness: los inventarios tienen que ser mapeos ruta → sha256",
    )
    faltan = sorted(set(sellado) - set(declarado))
    sobran = sorted(set(declarado) - set(sellado))
    require(
        not faltan and not sobran,
        "readiness: el inventario local no coincide con el del shard"
        + (f" · faltan {faltan}" if faltan else "")
        + (f" · sobran {sobran}" if sobran else ""),
    )
    for ruta in sorted(declarado):
        equal(f"readiness: digest declarado de {ruta}", declarado[ruta], sellado[ruta])


def _exige_forma_cerrada(objeto: Mapping[str, Any], claves: Sequence[str], etiqueta: str) -> None:
    vistas = sorted(objeto)
    sobran = [k for k in vistas if k not in claves]
    faltan = [k for k in claves if k not in vistas]
    # El prefijo `readiness:` no es cosmético: es lo que permite distinguir de un vistazo un rechazo
    # de este contrato de un error incidental del intérprete.
    require(
        not sobran and not faltan,
        f"readiness: {etiqueta}: forma inesperada"
        + (f" · faltan {faltan}" if faltan else "")
        + (f" · sobran {sobran}" if sobran else ""),
    )


def _redactar_local(valor: str) -> str:
    """Redacción del carril local.

    Aquí no puede haber un secreto de Google: el flujo local no lee ninguna de las tres variables.
    Lo que sí puede colarse es un correo o una credencial pegada por error, y eso se borra. Las rutas
    se conservan legibles a propósito: un mensaje de error que no dice qué ruta falló no sirve.
    """
    salida = re.sub(r"[^\s@]+@[^\s@]+\.[^\s@]+", "«redactado»", valor)
    salida = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*", "«redactado»", salida, flags=re.S)
    return re.sub(r'"type"\s*:\s*"service_account".*', "«redactado»", salida, flags=re.S)


def _redactar(valor: str, sensibles: Sequence[str] = ()) -> str:
    """Redacción ESTRICTA del carril externo: ahí sí hay secretos en el proceso.

    Se redacta por dos vías: los valores conocidos, y cualquier cadena larga que pudiera serlo. Un
    digest de 64 hex sí se conserva —es evidencia, no secreto— y por eso se exceptúa explícitamente.
    """
    salida = valor
    for sensible in sensibles:
        if sensible:
            salida = salida.replace(sensible, "«redactado»")

    def _quizas(match: re.Match[str]) -> str:
        texto = match.group(0)
        if _SHA256.fullmatch(texto):
            return texto  # digest: evidencia reproducible
        return "«redactado»"

    salida = re.sub(r"[^\s@]+@[^\s@]+\.[^\s@]+", "«redactado»", salida)
    return _LARGO_SOSPECHOSO.sub(_quizas, salida)


def _raiz_repo() -> Path:
    return Path(__file__).resolve().parents[1]


def _esta_ignorado(ruta: Path, raiz_repo: Path) -> bool:
    try:
        return (
            subprocess.run(  # noqa: S603 — argumentos fijos, sin shell
                ["git", "check-ignore", "-q", str(ruta)],  # noqa: S607
                cwd=str(raiz_repo),
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
    except OSError:
        return False  # sin git no se puede demostrar; no demostrado es no


def check_evidence_root(destino: Path, raiz_repo: Path | None = None) -> Path:
    """La evidencia no entra al repositorio.

    Se aceptan sólo descendientes resueltos de ``<repo>/runs/`` —comprobando con git que de verdad
    está ignorado— o de la raíz temporal real del sistema. Se resuelve antes de decidir, para que un
    symlink no cuele el manifiesto dentro del árbol versionado.
    """
    raiz = _raiz_repo() if raiz_repo is None else raiz_repo
    resuelto = destino.expanduser().resolve()
    runs = (raiz / "runs").resolve()
    temporal = Path(tempfile.gettempdir()).resolve()
    if resuelto.is_relative_to(runs):
        require(
            _esta_ignorado(runs, raiz),
            "runs/ no está ignorado por git en este árbol; la evidencia entraría al repositorio",
        )
        return resuelto
    if resuelto.is_relative_to(temporal):
        return resuelto
    raise ArtifactValidationError(
        f"--evidence-root {resuelto} no desciende de {runs} ni de {temporal}: "
        "la evidencia no se versiona"
    )


def resolve_release_target(objetivo: Path, disease_id: str, release_id: str) -> Path:
    """Acepta el bundle o su puntero ``.dvc`` y devuelve la SEDE, nunca una ruta escrita a mano."""
    ruta = objetivo.expanduser().resolve()
    bundle = ruta.with_suffix("") if ruta.suffix == ".dvc" else ruta
    raiz = bundle.parent.parent
    esperado = release_path(raiz, disease_id, release_id)
    equal("readiness: la sede derivada del objetivo", esperado.resolve(), bundle)
    require(bundle.is_dir(), f"readiness: el bundle no está en disco: {bundle.name}")
    return raiz


def _escribir_atomico(destino: Path, datos: bytes) -> str:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".writing")
    try:
        temporal.write_bytes(datos)
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)
    return sha256_bytes(datos)


def _versiones() -> dict[str, str]:
    import pandas  # noqa: PLC0415 — sólo para registrar su versión

    return {
        "python": platform.python_version(),
        "pandas": str(pandas.__version__),
    }


def _hechos_del_shard(manifiesto: Mapping[str, Any]) -> dict[str, Any]:
    """Conteos y estados DERIVADOS del manifiesto. Ninguno escrito aquí."""
    estado = manifiesto["publication_status"]
    return {
        "rows": int(manifiesto["rows"]),
        "products": int(manifiesto["products"]),
        "base_series": int(manifiesto["base_series"]),
        "derived_products": int(manifiesto["derived_products"]),
        "models": int(manifiesto["models"]),
        "horizon_weeks": int(manifiesto["horizon_weeks"]),
        "interval_method": str(manifiesto["interval_method"]),
        "uncertainty_available": bool(manifiesto["uncertainty_available"]),
        "lifecycle": str(manifiesto["lifecycle"]),
        "channels_emitted": list(manifiesto["channels_emitted"]),
        "channels_without_bridge": list(manifiesto["channels_without_bridge"]),
        "verdict": str(estado["verdict"]),
        "weeks_available": int(estado["weeks_available"]),
        "weeks_required": int(estado["weeks_required"]),
        "gate_digest": str(estado["gate_digest"]),
        "evaluation_digest": str(estado["evaluation_digest"]),
        "status_digest": str(estado["status_digest"]),
        "publication_label": str(manifiesto["publication_label"]),
    }


def _comprobar_invariantes(hechos: Mapping[str, Any], disease: Any) -> list[str]:
    """Las condiciones que un candidate tiene que cumplir. Se derivan; no se dan por supuestas."""
    fallos: list[str] = []
    if hechos["lifecycle"] != disease.lifecycle:
        fallos.append(f"lifecycle del shard {hechos['lifecycle']} != registry {disease.lifecycle}")
    if hechos["uncertainty_available"]:
        fallos.append("el release declara incertidumbre y esta cadena es point-only")
    if hechos["channels_without_bridge"]:
        fallos.append(f"canales declarados sin puente: {hechos['channels_without_bridge']}")
    if hechos["weeks_available"] >= hechos["weeks_required"] and hechos["verdict"] == "INCOMPLETE":
        fallos.append("INCOMPLETE con las semanas completas: el estado no describe la evidencia")
    if hechos["rows"] <= 0 or hechos["products"] <= 0:
        fallos.append("conteos no positivos en el manifiesto del shard")
    if hechos["base_series"] + hechos["derived_products"] != hechos["products"]:
        fallos.append("base + derivados no suman los productos declarados")
    if not hechos["publication_label"].strip():
        fallos.append("el release viaja sin etiqueta de validación")
    return fallos


def run_local(
    *, disease_id: str, release_target: Path, evidence_root: Path, raiz_repo: Path | None = None
) -> dict[str, Any]:
    """Cierra el carril local entero y deja el manifiesto. No toca red ni credenciales."""
    raiz = _raiz_repo() if raiz_repo is None else raiz_repo
    evidencia = check_evidence_root(evidence_root, raiz)

    disease = registry.require(disease_id)
    estado = load_declared_status(disease_id)
    release_id = estado.status.release_id
    sede = resolve_release_target(release_target, disease_id, release_id)

    # Dos compilaciones bajo raíces distintas: la reproducibilidad se mide, no se afirma.
    arboles: list[Path] = []
    manifiestos: list[dict[str, Any]] = []
    for nombre in ("compile_a", "compile_b"):
        compilacion = compile_release(
            disease_id=disease_id,
            mode=MODE_CANDIDATE,
            releases_root=sede,
            status=estado,
        )
        shards = emit_shards(compilacion, evidencia / nombre, repo_root_path=raiz)
        arboles.append(shards.root)
        import json  # noqa: PLC0415

        manifiestos.append(json.loads((shards.root / "shard_manifest.json").read_text("utf-8")))

    diferencias = diff_trees(arboles[0], arboles[1])
    require(not diferencias, f"readiness: dos compilaciones difieren en {diferencias[:5]}")
    equal("readiness: los dos manifiestos", manifiestos[0], manifiestos[1])

    manifiesto = manifiestos[0]
    hechos = _hechos_del_shard(manifiesto)
    fallos = _comprobar_invariantes(hechos, disease)

    tablas = build_tables(arboles[0])
    xml = build_workbook_xml(
        tablas, spreadsheet_id=LOCAL_SHEET_IDENTITY, label=hechos["publication_label"]
    )
    workbook = verify_workbook(xml, forbidden_ids=[])
    ruta_workbook = evidencia / "runner_staging_local.twb"
    digest_workbook = _escribir_atomico(ruta_workbook, xml)
    if sorted(workbook["tables"]) != sorted(TABLES):
        fallos.append(f"el workbook no declara el namespace administrado: {workbook['tables']}")

    cuerpo: dict[str, Any] = {
        "schema": READINESS_SCHEMA,
        "disease_id": disease_id,
        "release_id": release_id,
        "artifact_backend": disease.artifact_backend,
        "selection_policy": disease.selection_policy,
        "gallery_enabled": bool(disease.gallery_enabled),
        "declared_channels": sorted(disease.channels),
        "shard": hechos,
        "shard_files": dict(sorted(manifiesto["files"].items())),
        "shard_manifest_digest": sha256_bytes(canonical_json(manifiesto)),
        # Ruta RELATIVA a la evidencia: el manifiesto tiene que ser portable y localizar su shard
        # sin que nadie se lo pase por bandera (R120-P0-1). Nunca una ruta absoluta.
        "shard_relative_root": arboles[0].relative_to(evidencia).as_posix(),
        "shard_tree_digest": _digest_de_arbol(arboles[0]),
        "reproducible": {"compilations": len(arboles), "tree_differences": len(diferencias)},
        "tables": {n: int(len(f)) for n, f in sorted(tablas.as_mapping().items())},
        "table_digests": tablas.digests(),
        "workbook": {
            "digest": digest_workbook,
            "bytes": len(xml),
            "spreadsheet_identity": LOCAL_SHEET_IDENTITY,
            "tables": workbook["tables"],
            "tableau_desktop_validated": False,
        },
        "versions": _versiones(),
        "public_writes": 0,
        "manual_requirements": list(MANUAL_REQUIREMENTS),
        "manual_requirements_status": "PENDING",
        "external_status": STATUS_BLOCKED_EXTERNAL,
        "status": STATUS_FAIL if fallos else STATUS_PASS_LOCAL,
        "failures": [_redactar_local(f) for f in fallos],
    }
    destino = evidencia / READINESS_FILE
    cuerpo["manifest_digest"] = sha256_bytes(canonical_json(cuerpo))
    _exige_forma_cerrada(cuerpo, READINESS_KEYS, READINESS_FILE)
    _escribir_atomico(destino, canonical_json(cuerpo))
    # `evidence_path` viaja de vuelta al llamador pero NO se persiste: una ruta absoluta en un
    # artefacto lo ata a la máquina que lo escribió.
    return {**cuerpo, "evidence_path": str(destino)}


def _entorno_externo(entorno: Mapping[str, str] | None) -> tuple[dict[str, bool], list[str]]:
    """Sólo PRESENCIA y no-colisión. Ni valor, ni longitud, ni prefijo."""
    env = dict(os.environ if entorno is None else entorno)
    presencia = {
        v: bool((env.get(v) or "").strip())
        for v in (STAGING_ID_ENV, PRODUCTION_ID_ENV, SERVICE_ACCOUNT_ENV)
    }
    faltan = sorted(v for v, hay in presencia.items() if not hay)
    if not faltan:
        staging = (env.get(STAGING_ID_ENV) or "").strip()
        produccion = (env.get(PRODUCTION_ID_ENV) or "").strip()
        if staging == produccion:
            faltan.append("staging_and_production_ids_are_the_same")
    return presencia, faltan


def load_local_evidence(
    local_evidence: Path, *, shard_root: Path | None = None
) -> tuple[dict[str, Any], Path, Any]:
    """Carga la evidencia local y la CRUZA con el shard que dice describir.

    Copiar el digest sin recomputarlo, y no comparar la identidad contra el shard que de verdad se
    consume, dejaba pasar un manifiesto con `disease_id` y `release_id` fabricados: el plan y el
    workbook salían del shard real y el reporte afirmaba otra cosa (R120-P0-2). Aquí toda
    discrepancia falla **antes** de que exista un borde externo que abrir.
    """
    import json  # noqa: PLC0415

    # La política de ubicación es la misma que la de escritura. Copiar un árbol de evidencia válido
    # bajo `reports/` no puede convertir una ruta versionable en destino legítimo (R122-P0).
    check_evidence_root(local_evidence.parent)

    payload = json.loads(local_evidence.read_text("utf-8"))
    _exige_forma_cerrada(payload, READINESS_KEYS, READINESS_FILE)
    equal("readiness: schema de la evidencia local", payload.get("schema"), READINESS_SCHEMA)
    require(
        payload.get("status") == STATUS_PASS_LOCAL,
        f"readiness: la evidencia local no está en {STATUS_PASS_LOCAL}",
    )

    # 1. El digest se RECOMPUTA sobre el payload sin su propio campo de digest.
    declarado = payload["manifest_digest"]
    cuerpo = {k: v for k, v in payload.items() if k != "manifest_digest"}
    equal(
        "readiness: digest del manifiesto local", sha256_bytes(canonical_json(cuerpo)), declarado
    )

    # 2. La raíz del shard sale del propio manifiesto, con containment.
    raiz = _ruta_relativa_segura(payload["shard_relative_root"], local_evidence.parent)
    if shard_root is not None:
        equal(
            "readiness: --shard-root contradice la raíz sellada",
            shard_root.expanduser().resolve(),
            raiz,
        )

    # 3. El shard entero: su manifiesto y TODOS sus archivos.
    manifiesto = json.loads((raiz / "shard_manifest.json").read_text("utf-8"))
    equal(
        "readiness: digest del manifiesto del shard",
        sha256_bytes(canonical_json(manifiesto)),
        payload["shard_manifest_digest"],
    )
    _exige_inventario_exacto(payload["shard_files"], manifiesto["files"])
    for relativo, esperado in sorted(payload["shard_files"].items()):
        archivo = _archivo_del_inventario(relativo, raiz)
        equal(f"readiness: digest de {relativo}", sha256_bytes(archivo.read_bytes()), esperado)
    equal(
        "readiness: digest del árbol del shard",
        _digest_de_arbol(raiz),
        payload["shard_tree_digest"],
    )

    # 4. Identidad cruzada: no basta con que el manifiesto sea coherente consigo mismo.
    for clave in ("disease_id", "release_id"):
        equal(f"readiness: {clave} del shard", manifiesto[clave], payload[clave])
    for clave in IDENTIDAD_CRUZADA:
        equal(f"readiness: {clave} del shard", manifiesto[clave], payload["shard"][clave])

    # 5. Las tablas se reconstruyen y se comparan contra los digests sellados.
    tablas = build_tables(raiz)
    equal("readiness: digests de las tablas", tablas.digests(), payload["table_digests"])
    return payload, raiz, tablas


def run_external_readonly(
    *,
    local_evidence: Path,
    entorno: Mapping[str, str] | None = None,
    sink_factory: Any = None,
    shard_root: Path | None = None,
) -> dict[str, Any]:
    """Preflight externo de sólo lectura. Dos inventarios, plan en seco y workbook. Nada más."""
    local, raiz_shard, tablas = load_local_evidence(local_evidence, shard_root=shard_root)

    presencia, faltan = _entorno_externo(entorno)
    base: dict[str, Any] = {
        "schema": EXTERNAL_SCHEMA,
        "disease_id": local["disease_id"],
        "release_id": local["release_id"],
        "local_manifest_digest": local["manifest_digest"],
        "environment_present": presencia,
        "manual_requirements_status": "PENDING",
    }
    if faltan:
        # Se sale ANTES de autenticar: no se abre nada que no se pueda demostrar que es staging.
        return {**base, "status": STATUS_BLOCKED_EXTERNAL, "missing": faltan}

    env = dict(os.environ if entorno is None else entorno)
    staging = (env.get(STAGING_ID_ENV) or "").strip()
    sensibles = tuple(
        v for v in (staging, env.get(PRODUCTION_ID_ENV), env.get(SERVICE_ACCOUNT_ENV)) if v
    )

    try:
        sink = _abrir_sink(staging, sink_factory)
        primero = table_inventory(sink, TABLES)
        segundo = table_inventory(sink, TABLES)
        equal(
            "readiness: dos inventarios seguidos difieren",
            primero["inventory_digest"],
            segundo["inventory_digest"],
        )
        residuos = [t for t in primero["tables"] if t.endswith(("__next", "__backup"))]
        require(not residuos, f"readiness: el sink conserva residuos {residuos}")

        plan = promotion_plan(sink, tablas)  # sólo lee: enseña el plan, no lo ejecuta
        for paso in plan["steps"]:
            _check_paso(paso)

        xml = build_workbook_xml(
            tablas, spreadsheet_id=staging, label=local["shard"]["publication_label"]
        )
        workbook = verify_workbook(xml, forbidden_ids=[env.get(PRODUCTION_ID_ENV) or ""])
    except (ArtifactValidationError, TableauAdapterError) as exc:
        return {**base, "status": STATUS_FAIL, "failure": _redactar(str(exc), sensibles)}
    except Exception as exc:  # noqa: BLE001 — cualquier fallo del proveedor se redacta igual
        return {
            **base,
            "status": STATUS_FAIL,
            "failure": _redactar(f"{type(exc).__name__}: {exc}", sensibles),
        }

    reporte = {
        **base,
        "status": STATUS_READY_EXTERNAL,
        "inventory_digest": primero["inventory_digest"],
        "foreign_tabs": [_redactar(t, sensibles) for t in primero["foreign"]],
        # El plan ENTERO, no sólo sus pasos: conservar la lista y tirar schema, conteos y digests
        # deja al consumidor sin con qué comparar el plan vivo.
        "promotion_plan": {clave: plan[clave] for clave in PLAN_KEYS},
        # Qué hojas se inspeccionaron, sin decir cuáles: la evidencia queda atada a ellas.
        "staging_identity_digest": identity_digest(PURPOSE_STAGING, staging),
        "production_identity_digest": identity_digest(
            PURPOSE_PRODUCTION, (env.get(PRODUCTION_ID_ENV) or "").strip()
        ),
        "workbook": {
            "digest": sha256_bytes(xml),
            "tables": workbook["tables"],
            "tableau_desktop_validated": False,
        },
    }
    reporte["preflight_digest"] = sha256_bytes(canonical_json(reporte))
    # El productor valida con el MISMO validador que usará el consumidor: no se escribe nada que
    # después no se pueda cargar.
    check_external_shape(reporte)
    # Se revalida la ubicación JUSTO antes de escribir: entre la carga y aquí pudo cambiar el
    # destino —un symlink reapuntado, por ejemplo— y lo que importa es dónde caen los bytes.
    destino = check_evidence_root(local_evidence.parent) / EXTERNAL_FILE
    # Sólo un PASS deja artefacto. Un FAIL o un bloqueo no pueden borrar la evidencia de un
    # preflight anterior que sí pasó: destruirla sería perder lo único que gobierna el gate.
    _escribir_atomico(destino, canonical_json(reporte))
    return {**reporte, "evidence_path": str(destino)}


def load_external_preflight(
    external_evidence: Path, *, entorno: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Carga y VERIFICA un `external_preflight.v2` contra el entorno vigente.

    Función pura: no abre Google y no escribe. El entorno es **explícito y obligatorio**: aceptar un
    PASS sin saber para qué hoja se produjo es exactamente la brecha de trazabilidad que cierra esta
    versión (R124-P0). Dos hojas vacías tienen el mismo inventario y el mismo plan; lo único que las
    distingue es su huella.
    """
    import json  # noqa: PLC0415

    require(
        entorno is not None,
        "readiness: el loader externo exige el entorno explícito; no hay contexto implícito",
    )
    env = dict(entorno or {})
    staging, produccion = staging_ids(env, require_production=True)

    check_evidence_root(external_evidence.parent)
    payload = json.loads(external_evidence.read_text("utf-8"))
    require(
        payload.get("schema") != EXTERNAL_SCHEMA_RETIRADO,
        f"readiness: {EXTERNAL_SCHEMA_RETIRADO} no se migra ni se acepta; regenera el preflight",
    )
    check_external_shape(payload)

    declarado = payload["preflight_digest"]
    cuerpo = {k: v for k, v in payload.items() if k != "preflight_digest"}
    equal(
        "readiness: digest del preflight externo", sha256_bytes(canonical_json(cuerpo)), declarado
    )
    equal("readiness: estado del preflight externo", payload["status"], STATUS_READY_EXTERNAL)

    # ── identidad de las dos hojas, recomputada desde el entorno vigente ──
    equal(
        "readiness: el preflight se produjo para otra hoja de staging",
        payload["staging_identity_digest"],
        identity_digest(PURPOSE_STAGING, staging),
    )
    equal(
        "readiness: el preflight declara otra hoja productiva",
        payload["production_identity_digest"],
        identity_digest(PURPOSE_PRODUCTION, produccion or ""),
    )

    # ── evidencia local: se carga con su propio loader, no se lee a mano ──
    sellado, _, tablas = load_local_evidence(external_evidence.parent / READINESS_FILE)
    for clave in ("disease_id", "release_id"):
        equal(f"readiness: {clave} del preflight", payload[clave], sellado[clave])
    equal(
        "readiness: local_manifest_digest del preflight",
        payload["local_manifest_digest"],
        sellado["manifest_digest"],
    )

    _check_plan_sellado(payload["promotion_plan"], tablas, sellado)

    # ── el workbook se REPRODUCE con el id vigente: si no coincide, la evidencia es de otra hoja ──
    xml = build_workbook_xml(
        tablas, spreadsheet_id=staging, label=sellado["shard"]["publication_label"]
    )
    equal(
        "readiness: el workbook sellado no se reproduce con la hoja vigente",
        sha256_bytes(xml),
        payload["workbook"]["digest"],
    )
    equal("readiness: tablas del workbook", sorted(payload["workbook"]["tables"]), sorted(TABLES))
    return dict(payload)


def _check_plan_sellado(plan: Any, tablas: Any, sellado: Mapping[str, Any]) -> None:
    """El plan sellado, entero y cruzado contra las tablas que la evidencia local describe."""
    require(isinstance(plan, dict), "readiness: promotion_plan no es un mapeo")
    _exige_forma_cerrada(plan, PLAN_KEYS, "promotion_plan")
    equal("readiness: schema del plan", plan["schema"], PROMOTION_PLAN_SCHEMA)
    equal("readiness: namespace del plan", sorted(plan["namespace"]), sorted(TABLES))
    equal(
        "readiness: conteos del plan",
        {k: int(v) for k, v in sorted(plan["rows"].items())},
        {n: int(len(f)) for n, f in sorted(tablas.as_mapping().items())},
    )
    equal("readiness: digests del plan", dict(plan["digests"]), dict(sellado["table_digests"]))
    require(isinstance(plan["steps"], list), "readiness: los pasos del plan no son una lista")
    for paso in plan["steps"]:
        _check_paso(paso)


def verify_external_preflight_live(
    external_evidence: Path,
    *,
    entorno: Mapping[str, str] | None = None,
    sink_factory: Any = None,
) -> dict[str, Any]:
    """Revalida, SÓLO LEYENDO, que la hoja y el plan siguen siendo los del preflight.

    Éste es el gate que una futura orden de escritura tendrá que ejecutar inmediatamente antes de la
    primera mutación: un preflight de ayer no dice nada de la hoja de hoy. No escribe, no renombra,
    no borra y no crea nada; aquí no se implementa ningún apply.
    """
    payload = load_external_preflight(external_evidence, entorno=entorno)
    env = dict(entorno or {})
    staging, _ = staging_ids(env, require_production=True)
    _, _, tablas = load_local_evidence(external_evidence.parent / READINESS_FILE)

    sink = _abrir_sink(staging, sink_factory)
    # Si el sink sabe decir sobre qué hoja opera, se le exige que sea la solicitada.
    declarada = getattr(sink, "spreadsheet_id", None)
    require(
        declarada is None or declarada == staging,
        "readiness: el sink abierto opera sobre otra hoja distinta de la solicitada",
    )

    primero = table_inventory(sink, TABLES)
    segundo = table_inventory(sink, TABLES)
    equal(
        "readiness: la hoja se movió entre dos inventarios consecutivos",
        primero["inventory_digest"],
        segundo["inventory_digest"],
    )
    equal(
        "readiness: el inventario vivo no es el del preflight",
        primero["inventory_digest"],
        payload["inventory_digest"],
    )

    vivo = promotion_plan(sink, tablas)
    equal(
        "readiness: el plan vivo no es el sellado",
        {clave: vivo[clave] for clave in PLAN_KEYS},
        dict(payload["promotion_plan"]),
    )
    return {
        "schema": EXTERNAL_SCHEMA,
        "status": STATUS_READY_EXTERNAL,
        "mutating": False,
        "disease_id": payload["disease_id"],
        "release_id": payload["release_id"],
        "inventory_digest": primero["inventory_digest"],
        "preflight_digest": payload["preflight_digest"],
    }


def _abrir_sink(staging: str, sink_factory: Any) -> Any:
    """Único borde que autentica, y sólo en el flujo externo. En local nunca se llama."""
    if sink_factory is not None:
        return sink_factory(staging)
    from epiforecast.publication.sheets_sink import (  # noqa: PLC0415 — perezoso a propósito
        GoogleSheetsTableSink,
        open_spreadsheet,
    )

    return GoogleSheetsTableSink(open_spreadsheet(staging), spreadsheet_id=staging)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.publication_readiness",
        description="Prepara y evidencia la publicación de un release. Nunca escribe fuera.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    local = sub.add_parser(CMD_LOCAL, help="carril local completo, sin red ni credenciales")
    local.add_argument("--disease", required=True, help="id del registry")
    local.add_argument("--release-target", required=True, type=Path, help="bundle o su .dvc")
    local.add_argument("--evidence-root", required=True, type=Path, help="runs/ o temporal")

    externo = sub.add_parser(CMD_EXTERNAL, help="preflight externo de SÓLO LECTURA")
    externo.add_argument("--local-evidence", required=True, type=Path, help="readiness_manifest")
    externo.add_argument("--shard-root", default=None, type=Path, help="raíz del shard compilado")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    entorno: Mapping[str, str] | None = None,
    salida: Any = None,
    sink_factory: Any = None,
) -> int:
    """`sink_factory` se inyecta en pruebas; no existe como bandera del CLI."""
    destino = sys.stdout if salida is None else salida
    args = build_parser().parse_args(argv)
    try:
        if args.comando == CMD_LOCAL:
            reporte = run_local(
                disease_id=args.disease,
                release_target=args.release_target,
                evidence_root=args.evidence_root,
            )
        else:
            reporte = run_external_readonly(
                local_evidence=args.local_evidence,
                entorno=entorno,
                shard_root=args.shard_root,
                sink_factory=sink_factory,
            )
    except (ArtifactValidationError, TableauAdapterError, KeyError, OSError) as exc:
        redactar = _redactar_local if args.comando == CMD_LOCAL else _redactar
        destino.write(f"FAIL: {redactar(str(exc))}\n")
        return RC_FAIL

    destino.write(canonical_json(reporte).decode("utf-8") + "\n")
    if reporte["status"] == STATUS_FAIL:
        return RC_FAIL
    if reporte["status"] == STATUS_BLOCKED_EXTERNAL:
        return RC_BLOCKED
    return RC_OK


if __name__ == "__main__":  # pragma: no cover - entrada de proceso
    raise SystemExit(main())


__all__ = [
    "EXTERNAL_KEYS",
    "EXTERNAL_SCHEMA",
    "LOCAL_SHEET_IDENTITY",
    "MANUAL_REQUIREMENTS",
    "RC_BLOCKED",
    "RC_FAIL",
    "RC_OK",
    "READINESS_KEYS",
    "READINESS_SCHEMA",
    "STATUS_BLOCKED_EXTERNAL",
    "STATUS_FAIL",
    "STATUS_PASS_LOCAL",
    "build_parser",
    "check_evidence_root",
    "check_external_shape",
    "identity_digest",
    "load_external_preflight",
    "load_local_evidence",
    "main",
    "resolve_release_target",
    "run_external_readonly",
    "run_local",
    "verify_external_preflight_live",
]
