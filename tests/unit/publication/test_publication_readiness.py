"""C7.6-AUTO-B1-HARNESS — el orquestador de readiness.

Lo que protege: que el carril local se cierre entero **sin red ni credenciales** y deje evidencia
reproducible; que el flujo externo sea de sólo lectura de verdad —ni una llamada de escritura, ni
una bandera equivalente a aplicar—; que ningún secreto llegue a un archivo; y que el estado se
reporte honesto: `PASS_LOCAL` no es PASS de B1.

Nada aquí toca la red. El sink externo se inyecta, y el `sede` se construye en `tmp_path`.
"""

from __future__ import annotations

import ast
import dataclasses
import io
import json
from pathlib import Path
import re

import pandas as pd
import pytest
from scripts.publication_readiness import (
    EXTERNAL_KEYS,
    EXTERNAL_SCHEMA,
    LOCAL_SHEET_IDENTITY,
    MANUAL_REQUIREMENTS,
    RC_BLOCKED,
    RC_FAIL,
    RC_OK,
    READINESS_KEYS,
    READINESS_SCHEMA,
    STATUS_BLOCKED_EXTERNAL,
    STATUS_FAIL,
    STATUS_PASS_LOCAL,
    check_evidence_root,
    main,
    resolve_release_target,
    run_external_readonly,
    run_local,
)

from epiforecast import registry
from epiforecast.publication.sheets_sink import (
    PRODUCTION_ID_ENV,
    SERVICE_ACCOUNT_ENV,
    STAGING_ID_ENV,
)
from epiforecast.publication.tableau_adapter import (
    SUFFIX_BACKUP,
    SUFFIX_NEXT,
    TABLE_FORECAST,
    TABLE_RELEASES,
    MemorySink,
)
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.release_store import promote_release
from tests.unit.runner import artifact_fixtures as af
from tests.unit.runner import release_fixtures as rf

pytestmark = pytest.mark.skipif(
    not af.hay_runs(), reason="los runs sellados de C5 no están en este entorno (runs/ gitignored)"
)

FUENTE = Path(__file__).resolve().parents[3] / "scripts" / "publication_readiness.py"
CENTINELA_ID = "CENTINELA-ID-DE-HOJA-QUE-NO-DEBE-APARECER-JAMAS"
CENTINELA_JSON = '{"type":"service_account","private_key":"CENTINELA-CLAVE-PRIVADA"}'
ID_PRODUCCION = "CENTINELA-ID-PRODUCTIVO-DISTINTO-DEL-STAGING"


@pytest.fixture(scope="module")
def sede(tmp_path_factory) -> Path:
    """Sede propia con el release promovido: nunca la del repo."""
    raiz = tmp_path_factory.mktemp("readiness")
    bundle = rf.construir(raiz).path
    destino = raiz / "releases"
    promote_release(bundle, releases_root=destino, disease_id=af.DISEASE)
    return destino


def _objetivo(sede: Path) -> Path:
    """El bundle concreto, tal como lo recibiría el CLI."""
    return next((sede / af.DISEASE).iterdir())


def _local(sede: Path, destino: Path) -> dict:
    return run_local(disease_id=af.DISEASE, release_target=_objetivo(sede), evidence_root=destino)


def _archivos(raiz: Path) -> list[Path]:
    return [p for p in raiz.rglob("*") if p.is_file()]


# ── Carril local ──────────────────────────────────────────────────────────────────────────────
def test_el_carril_local_se_cierra_entero_y_declara_lo_que_falta(sede, tmp_path):
    reporte = _local(sede, tmp_path / "ev")

    assert reporte["status"] == STATUS_PASS_LOCAL
    assert reporte["failures"] == []
    assert reporte["external_status"] == STATUS_BLOCKED_EXTERNAL
    assert reporte["manual_requirements_status"] == "PENDING"
    assert reporte["manual_requirements"] == list(MANUAL_REQUIREMENTS)
    assert reporte["public_writes"] == 0
    assert reporte["schema"] == READINESS_SCHEMA
    # Dos compilaciones, cero diferencias: la reproducibilidad se mide.
    assert reporte["reproducible"] == {"compilations": 2, "tree_differences": 0}


def test_los_conteos_salen_del_manifiesto_no_de_una_constante(sede, tmp_path):
    reporte = _local(sede, tmp_path / "ev")
    shard = reporte["shard"]
    manifiesto = json.loads(
        (
            tmp_path
            / "ev"
            / "compile_a"
            / af.DISEASE
            / reporte["release_id"]
            / "shard_manifest.json"
        ).read_text("utf-8")
    )
    for clave in ("rows", "products", "base_series", "derived_products", "models"):
        assert shard[clave] == manifiesto[clave], clave
    assert shard["base_series"] + shard["derived_products"] == shard["products"]
    assert reporte["tables"][TABLE_FORECAST] == shard["rows"]
    assert reporte["tables"][TABLE_RELEASES] == 1


def test_el_release_sigue_siendo_un_candidate_point_only(sede, tmp_path):
    shard = _local(sede, tmp_path / "ev")["shard"]
    assert shard["lifecycle"] == registry.require(af.DISEASE).lifecycle == "trained"
    assert shard["interval_method"] == "none"
    assert shard["uncertainty_available"] is False
    assert shard["channels_without_bridge"] == []
    assert shard["verdict"] == "INCOMPLETE"
    assert shard["weeks_available"] < shard["weeks_required"]
    assert "(0/4 semanas)" in shard["publication_label"]


def test_dos_corridas_dan_el_mismo_manifiesto(sede, tmp_path):
    """La única diferencia admitida es la ruta de evidencia, excluida de la identidad."""
    uno = _local(sede, tmp_path / "a")
    otro = _local(sede, tmp_path / "b")

    assert uno["manifest_digest"] == otro["manifest_digest"]
    assert uno["evidence_path"] != otro["evidence_path"], "las rutas sí difieren"
    assert {k: v for k, v in uno.items() if k != "evidence_path"} == {
        k: v for k, v in otro.items() if k != "evidence_path"
    }
    # Y el manifiesto en disco también es byte-idéntico entre las dos raíces.
    assert (tmp_path / "a" / "readiness_manifest.json").read_bytes() == (
        tmp_path / "b" / "readiness_manifest.json"
    ).read_bytes()


def test_el_workbook_local_no_lleva_ninguna_identidad_de_hoja_real(sede, tmp_path):
    reporte = _local(sede, tmp_path / "ev")
    assert reporte["workbook"]["spreadsheet_identity"] == LOCAL_SHEET_IDENTITY
    assert reporte["workbook"]["tableau_desktop_validated"] is False
    twb = (tmp_path / "ev" / "runner_staging_local.twb").read_text("utf-8")
    assert LOCAL_SHEET_IDENTITY in twb
    assert "public.tableau.com" not in twb
    assert reporte["workbook"]["tables"] == [TABLE_FORECAST, TABLE_RELEASES]


def test_local_no_lee_las_variables_de_google_aunque_esten_sembradas(sede, tmp_path, monkeypatch):
    """El carril local no puede depender de un secreto: si lo leyera, aparecería en la evidencia."""
    monkeypatch.setenv(STAGING_ID_ENV, CENTINELA_ID)
    monkeypatch.setenv(PRODUCTION_ID_ENV, ID_PRODUCCION)
    monkeypatch.setenv(SERVICE_ACCOUNT_ENV, CENTINELA_JSON)

    reporte = _local(sede, tmp_path / "ev")
    assert reporte["status"] == STATUS_PASS_LOCAL

    for archivo in _archivos(tmp_path / "ev"):
        texto = archivo.read_bytes().decode("utf-8", errors="replace")
        for centinela in (CENTINELA_ID, ID_PRODUCCION, "CENTINELA-CLAVE-PRIVADA"):
            assert centinela not in texto, f"{archivo.name} filtró {centinela}"
    assert CENTINELA_ID not in json.dumps(reporte)


def test_local_funciona_sin_gspread_instalado(sede, tmp_path):
    reporte = _local(sede, tmp_path / "ev")
    assert reporte["status"] == STATUS_PASS_LOCAL
    # Lo que importa no es si gspread está instalado, sino que el módulo no lo importe.
    fuente = FUENTE.read_text("utf-8")
    for linea in fuente.splitlines():
        assert not linea.startswith(("import gspread", "from gspread", "from google")), linea


def test_un_shard_alterado_falla_antes_de_cualquier_borde_externo(sede, tmp_path, monkeypatch):
    """Si las dos compilaciones no coinciden, no se sigue: no hay nada que llevar a ningún sitio."""
    import scripts.publication_readiness as mod

    original = mod.emit_shards
    llamadas = {"n": 0}

    def emitir(compilacion, raiz, **kw):
        salida = original(compilacion, raiz, **kw)
        llamadas["n"] += 1
        if llamadas["n"] == 2:  # el segundo árbol sale distinto
            (salida.root / "reports" / "report.md").write_text("alterado\n", encoding="utf-8")
        return salida

    monkeypatch.setattr(mod, "emit_shards", emitir)
    with pytest.raises(ArtifactValidationError, match="dos compilaciones difieren"):
        _local(sede, tmp_path / "ev")
    assert not (tmp_path / "ev" / "readiness_manifest.json").exists(), "no se emitió evidencia"


# ── Contención de la evidencia ────────────────────────────────────────────────────────────────
def test_la_evidencia_no_puede_caer_dentro_del_repositorio(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    for prohibida in ("reports/tmp/ev", "reports/runs/ev", "src/ev"):
        with pytest.raises(ArtifactValidationError, match="no se versiona"):
            check_evidence_root(repo / prohibida, repo)
    assert check_evidence_root(repo / "runs" / "_ev", repo)
    assert check_evidence_root(tmp_path / "ev", repo)


def test_el_objetivo_del_release_se_deriva_y_no_se_escribe_a_mano(sede):
    bundle = _objetivo(sede)
    raiz = resolve_release_target(bundle, af.DISEASE, bundle.name)
    assert raiz == sede.resolve()
    assert resolve_release_target(bundle.with_suffix(".dvc"), af.DISEASE, bundle.name) == raiz
    with pytest.raises(ArtifactValidationError):
        resolve_release_target(bundle, af.DISEASE, "otro_release_000000000000")


# ── Carril externo: sólo lectura ──────────────────────────────────────────────────────────────
def _evidencia(sede: Path, tmp_path: Path) -> tuple[Path, Path]:
    reporte = _local(sede, tmp_path / "ev")
    manifiesto = tmp_path / "ev" / "readiness_manifest.json"
    shard = tmp_path / "ev" / "compile_a" / af.DISEASE / reporte["release_id"]
    return manifiesto, shard


def _entorno(**cambios) -> dict[str, str]:
    base = {
        STAGING_ID_ENV: CENTINELA_ID,
        PRODUCTION_ID_ENV: ID_PRODUCCION,
        SERVICE_ACCOUNT_ENV: CENTINELA_JSON,
    }
    base.update(cambios)
    return base


class _SinkTrazado(MemorySink):
    """Sink que registra si alguien intentó escribir. En este flujo nadie debe intentarlo."""

    def write_table(self, name, frame):
        raise AssertionError(f"escritura prohibida en el flujo externo: {name}")

    def rename_table(self, origen, destino):
        raise AssertionError(f"rename prohibido en el flujo externo: {origen}")

    def drop_table(self, name):
        raise AssertionError(f"drop prohibido en el flujo externo: {name}")


@pytest.mark.parametrize("ausente", [STAGING_ID_ENV, PRODUCTION_ID_ENV, SERVICE_ACCOUNT_ENV])
def test_sin_una_variable_el_externo_queda_bloqueado_sin_autenticar(sede, tmp_path, ausente):
    manifiesto, shard = _evidencia(sede, tmp_path)
    abierto = {"n": 0}

    def fabrica(_):
        abierto["n"] += 1
        return _SinkTrazado()

    reporte = run_external_readonly(
        local_evidence=manifiesto,
        entorno=_entorno(**{ausente: ""}),
        sink_factory=fabrica,
        shard_root=shard,
    )
    assert reporte["status"] == STATUS_BLOCKED_EXTERNAL
    assert ausente in reporte["missing"]
    assert abierto["n"] == 0, "no se autenticó"


def test_ids_iguales_se_rechazan_antes_de_autenticar(sede, tmp_path):
    manifiesto, shard = _evidencia(sede, tmp_path)
    abierto = {"n": 0}

    def fabrica(_):
        abierto["n"] += 1
        return _SinkTrazado()

    reporte = run_external_readonly(
        local_evidence=manifiesto,
        entorno=_entorno(**{PRODUCTION_ID_ENV: CENTINELA_ID}),
        sink_factory=fabrica,
        shard_root=shard,
    )
    assert reporte["status"] == STATUS_BLOCKED_EXTERNAL
    assert "staging_and_production_ids_are_the_same" in reporte["missing"]
    assert abierto["n"] == 0


def test_el_externo_lee_dos_veces_y_no_escribe_nunca(sede, tmp_path):
    manifiesto, shard = _evidencia(sede, tmp_path)
    sink = _SinkTrazado({TABLE_FORECAST: pd.DataFrame([{"x": "vieja"}])})

    reporte = run_external_readonly(
        local_evidence=manifiesto,
        entorno=_entorno(),
        sink_factory=lambda _: sink,
        shard_root=shard,
    )
    assert reporte["status"] == "PASS_EXTERNAL_READONLY"
    assert len(reporte["inventory_digest"]) == 64
    assert reporte["planned_steps"], "el plan se enseña"
    assert reporte["workbook"]["tableau_desktop_validated"] is False
    assert sink.operaciones == [], "ni una operación de escritura"


def test_dos_inventarios_distintos_fallan_y_no_hay_plan(sede, tmp_path):
    manifiesto, shard = _evidencia(sede, tmp_path)

    class Movediza(_SinkTrazado):
        def __init__(self):
            super().__init__({TABLE_FORECAST: pd.DataFrame([{"x": 1}])})
            self.lecturas = 0

        def read_table(self, name):
            self.lecturas += 1
            if self.lecturas > 1 and name == TABLE_FORECAST:
                return pd.DataFrame([{"x": 2}])  # la hoja se movió entre los dos inventarios
            return super().read_table(name)

    reporte = run_external_readonly(
        local_evidence=manifiesto,
        entorno=_entorno(),
        sink_factory=lambda _: Movediza(),
        shard_root=shard,
    )
    assert reporte["status"] == STATUS_FAIL
    assert "inventarios" in reporte["failure"]
    assert "planned_steps" not in reporte


@pytest.mark.parametrize("residuo", [SUFFIX_NEXT, SUFFIX_BACKUP])
def test_residuos_en_el_sink_fallan(sede, tmp_path, residuo):
    manifiesto, shard = _evidencia(sede, tmp_path)
    sink = _SinkTrazado(
        {
            TABLE_FORECAST: pd.DataFrame([{"x": 1}]),
            f"{TABLE_RELEASES}{residuo}": pd.DataFrame([{"x": 2}]),
        }
    )
    reporte = run_external_readonly(
        local_evidence=manifiesto,
        entorno=_entorno(),
        sink_factory=lambda _: sink,
        shard_root=shard,
    )
    assert reporte["status"] == STATUS_FAIL
    assert "residuos" in reporte["failure"]


def test_un_proveedor_que_filtra_el_secreto_sale_redactado(sede, tmp_path):
    """El sink revienta arrastrando el id de la hoja. No puede llegar a ningún archivo."""
    manifiesto, shard = _evidencia(sede, tmp_path)

    def fabrica(_):
        raise RuntimeError(f"no pude abrir la hoja {CENTINELA_ID} con {CENTINELA_JSON}")

    reporte = run_external_readonly(
        local_evidence=manifiesto,
        entorno=_entorno(),
        sink_factory=fabrica,
        shard_root=shard,
    )
    assert reporte["status"] == STATUS_FAIL
    texto = json.dumps(reporte, ensure_ascii=False)
    for centinela in (CENTINELA_ID, ID_PRODUCCION, "CENTINELA-CLAVE-PRIVADA"):
        assert centinela not in texto, f"{centinela} sobrevivió en el reporte"
    assert "«redactado»" in reporte["failure"]
    for archivo in _archivos(tmp_path):
        crudo = archivo.read_bytes().decode("utf-8", errors="replace")
        assert CENTINELA_ID not in crudo, f"{archivo.name} filtró el id"


def test_el_externo_exige_evidencia_local_aprobada(sede, tmp_path):
    manifiesto, shard = _evidencia(sede, tmp_path)
    roto = json.loads(manifiesto.read_text("utf-8"))
    roto["status"] = STATUS_FAIL
    manifiesto.write_text(json.dumps(roto), encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match=STATUS_PASS_LOCAL):
        run_external_readonly(
            local_evidence=manifiesto,
            entorno=_entorno(),
            sink_factory=lambda _: _SinkTrazado(),
            shard_root=shard,
        )


# ── El contrato del código: sólo lectura, y genérico ──────────────────────────────────────────
ESCRITURAS_PROHIBIDAS = {
    "apply",
    "apply_recovery",
    "recover",
    "promote",
    "rollback",
    "delete",
    "write_table",
    "rename_table",
    "drop_table",
    "del_worksheet",
    "update_title",
    "installShard",
}


def test_el_orquestador_no_llama_a_ninguna_operacion_de_escritura():
    """AST, no grep: lo que importa es qué se LLAMA, no qué palabra aparece en un comentario."""
    arbol = ast.parse(FUENTE.read_text("utf-8"))
    llamadas = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call):
            f = nodo.func
            llamadas.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
    prohibidas = llamadas & ESCRITURAS_PROHIBIDAS
    assert not prohibidas, f"el orquestador llama a {prohibidas}"


def test_no_existe_bandera_ni_subcomando_equivalente_a_aplicar():
    fuente = FUENTE.read_text("utf-8")
    for prohibido in ('"--apply"', "'--apply'", '"apply"', '"recover"'):
        assert prohibido not in fuente, f"{prohibido} declarado en el CLI"
    from scripts.publication_readiness import build_parser

    ayuda = build_parser().format_help()
    assert "--apply" not in ayuda
    for accion in build_parser()._actions:  # noqa: SLF001 — se inspecciona el parser a propósito
        assert getattr(accion, "dest", "") != "apply"


def test_el_orquestador_no_conoce_ningun_padecimiento_ni_conteo():
    """Genericidad: sin nombres de padecimiento, sin motores y sin los conteos del release actual."""
    arbol = ast.parse(FUENTE.read_text("utf-8"))
    literales = [
        n.value
        for n in ast.walk(arbol)
        if isinstance(n, ast.Constant) and isinstance(n.value, (str, int))
    ]
    docstrings = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(nodo)
            if doc:
                docstrings.add(doc)
    textos = [v for v in literales if isinstance(v, str) and v not in docstrings]

    # Por palabra completa: `channels_without_bridge` contiene «ridge» y no es un motor.
    for prohibido in (
        "obesidad",
        "e66",
        "anorexia",
        "dengue",
        "prophet",
        "deepar",
        "ridge",
        "ets",
    ):
        patron = re.compile(rf"\b{prohibido}\b", re.IGNORECASE)
        culpables = [t for t in textos if patron.search(t)]
        assert not culpables, f"{prohibido} escrito en el orquestador: {culpables[:2]}"
    for conteo in (64, 111, 5772, 52, 47):
        assert conteo not in literales, f"el conteo {conteo} está hardcodeado"


def test_es_generico_frente_a_un_padecimiento_distinto(sede, tmp_path, monkeypatch):
    """N+1: los invariantes se comprueban contra el disease INYECTADO, no contra una constante."""
    from scripts.publication_readiness import _comprobar_invariantes

    real = registry.require(af.DISEASE)
    sintetico = dataclasses.replace(real, id="padecimiento_sintetico", lifecycle="configured")
    hechos = _local(sede, tmp_path / "ev")["shard"]

    assert _comprobar_invariantes(hechos, real) == []
    fallos = _comprobar_invariantes(hechos, sintetico)
    assert any("lifecycle" in f for f in fallos), "el lifecycle se compara con el disease dado"


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────
def test_el_cli_local_devuelve_cero_y_emite_json_canonico(sede, tmp_path):
    salida = io.StringIO()
    rc = main(
        [
            "local",
            "--disease",
            af.DISEASE,
            "--release-target",
            str(_objetivo(sede)),
            "--evidence-root",
            str(tmp_path / "ev"),
        ],
        salida=salida,
    )
    assert rc == RC_OK
    datos = json.loads(salida.getvalue())
    assert datos["status"] == STATUS_PASS_LOCAL
    assert datos["external_status"] == STATUS_BLOCKED_EXTERNAL
    # Canónico: claves ordenadas y sin espacios.
    assert salida.getvalue().startswith('{"artifact_backend"')


def test_el_cli_externo_sin_entorno_devuelve_el_codigo_de_bloqueo(sede, tmp_path):
    manifiesto, shard = _evidencia(sede, tmp_path)
    salida = io.StringIO()
    rc = main(
        ["external-readonly", "--local-evidence", str(manifiesto), "--shard-root", str(shard)],
        entorno={},
        salida=salida,
    )
    assert rc == RC_BLOCKED, "bloqueado no es fallo"
    assert json.loads(salida.getvalue())["status"] == STATUS_BLOCKED_EXTERNAL


def test_el_cli_local_falla_con_un_destino_versionable(sede, tmp_path):
    salida = io.StringIO()
    rc = main(
        [
            "local",
            "--disease",
            af.DISEASE,
            "--release-target",
            str(_objetivo(sede)),
            "--evidence-root",
            "reports/tmp/ev",
        ],
        salida=salida,
    )
    assert rc == RC_FAIL
    assert "no se versiona" in salida.getvalue()
    assert not re.search(r"«redactado»", salida.getvalue()), "una ruta local no es un secreto"


# ── Regresiones de la auditoría R120 ──────────────────────────────────────────────────────────
def _contador():
    """Fábrica de sink que cuenta aperturas: si el rechazo es previo, tiene que quedar en cero."""
    estado = {"n": 0}

    def fabrica(_):
        estado["n"] += 1
        return _SinkTrazado({TABLE_FORECAST: pd.DataFrame([{"x": "vieja"}])})

    return fabrica, estado


def _resellar(ruta: Path, **cambios) -> Path:
    """Altera el manifiesto y vuelve a sellar SÓLO la capa exterior: el digest propio."""
    from epiforecast.runner.release_contract import canonical_json, sha256_bytes

    payload = json.loads(ruta.read_text("utf-8"))
    for clave, valor in cambios.items():
        if "." in clave:
            padre, hijo = clave.split(".", 1)
            payload[padre] = {**payload[padre], hijo: valor}
        else:
            payload[clave] = valor
    payload.pop("manifest_digest", None)
    payload["manifest_digest"] = sha256_bytes(canonical_json(payload))
    ruta.write_text(json.dumps(payload), encoding="utf-8")
    return ruta


def test_el_manifiesto_sella_la_ruta_relativa_y_el_arbol(sede, tmp_path):
    """R120-P0-1: sin esto, el manifiesto no sabe dónde está su propio shard."""
    reporte = _local(sede, tmp_path / "ev")
    persistido = json.loads((tmp_path / "ev" / "readiness_manifest.json").read_text("utf-8"))

    assert persistido["shard_relative_root"] == f"compile_a/{af.DISEASE}/{reporte['release_id']}"
    assert len(persistido["shard_tree_digest"]) == 64
    assert "evidence_path" not in persistido, "una ruta absoluta ata el artefacto a su máquina"
    assert sorted(persistido) == sorted(READINESS_KEYS)


def test_el_comando_del_manual_llega_al_sink_sin_shard_root(sede, tmp_path):
    """R120-P0-1: el contrato de usuario es el CLI documentado, no el helper con parámetros."""
    _local(sede, tmp_path / "ev")
    fabrica, estado = _contador()
    salida = io.StringIO()

    rc = main(
        [
            "external-readonly",
            "--local-evidence",
            str(tmp_path / "ev" / "readiness_manifest.json"),
        ],
        entorno=_entorno(),
        salida=salida,
        sink_factory=fabrica,
    )
    datos = json.loads(salida.getvalue())
    assert rc == RC_OK, salida.getvalue()
    assert datos["status"] == "PASS_EXTERNAL_READONLY"
    assert estado["n"] == 1, "se autenticó exactamente una vez"
    assert datos["planned_steps"]


def test_el_comando_documentado_en_el_manual_es_el_que_existe():
    """Anti-deriva: el comando se extrae del propio manual, no se transcribe aquí."""
    manual = (
        Path(__file__).resolve().parents[3] / "docs" / "MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md"
    ).read_text("utf-8")
    bloques = re.findall(r"```zsh\n(.*?)```", manual, re.S)
    externos = [b for b in bloques if "publication_readiness external-readonly" in b]
    assert externos, "el manual ya no documenta el comando externo"

    crudo = " ".join(externos[0].replace("\\\n", " ").split())
    argv = crudo.split()[crudo.split().index("external-readonly") :]
    assert argv[0] == "external-readonly"
    assert "--shard-root" not in argv, (
        "el manual no puede depender de una bandera de compatibilidad"
    )
    assert "--apply" not in crudo
    # Y el parser real acepta exactamente esa forma.
    from scripts.publication_readiness import build_parser

    args = build_parser().parse_args(["external-readonly", "--local-evidence", "x.json"])
    assert args.comando == "external-readonly"


@pytest.mark.parametrize(
    "ruta",
    ["", "/etc/passwd", "../fuera", "compile_a/./x", "no_existe/aqui"],
)
def test_una_raiz_de_shard_insegura_o_ausente_se_rechaza_antes_del_sink(sede, tmp_path, ruta):
    _local(sede, tmp_path / "ev")
    manifiesto = _resellar(tmp_path / "ev" / "readiness_manifest.json", shard_relative_root=ruta)
    fabrica, estado = _contador()

    with pytest.raises(ArtifactValidationError):
        run_external_readonly(local_evidence=manifiesto, entorno=_entorno(), sink_factory=fabrica)
    assert estado["n"] == 0


def test_un_symlink_que_sale_de_la_evidencia_se_rechaza(sede, tmp_path):
    _local(sede, tmp_path / "ev")
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    (tmp_path / "ev" / "puente").symlink_to(fuera, target_is_directory=True)
    manifiesto = _resellar(
        tmp_path / "ev" / "readiness_manifest.json", shard_relative_root="puente"
    )
    fabrica, estado = _contador()

    with pytest.raises(ArtifactValidationError, match="fuera del directorio de evidencia"):
        run_external_readonly(local_evidence=manifiesto, entorno=_entorno(), sink_factory=fabrica)
    assert estado["n"] == 0


def test_shard_root_distinto_del_sellado_se_rechaza(sede, tmp_path):
    reporte = _local(sede, tmp_path / "ev")
    otro = tmp_path / "ev" / "compile_b" / af.DISEASE / reporte["release_id"]
    fabrica, estado = _contador()

    with pytest.raises(ArtifactValidationError, match="contradice la raíz sellada"):
        run_external_readonly(
            local_evidence=tmp_path / "ev" / "readiness_manifest.json",
            entorno=_entorno(),
            sink_factory=fabrica,
            shard_root=otro,
        )
    assert estado["n"] == 0, "ni siquiera con un shard idéntico: la identidad la manda el sello"


@pytest.mark.parametrize(
    "cambio",
    [
        {"disease_id": "padecimiento_fabricado"},
        {"release_id": "release_fabricado"},
        {"shard_manifest_digest": "0" * 64},
        {"shard_tree_digest": "0" * 64},
        {"shard.publication_label": "otra etiqueta"},
        {"shard.lifecycle": "published"},
        {"shard.rows": 1},
        {"shard.products": 1},
        {"shard.channels_emitted": ["web"]},
        {"table_digests": {"runner_forecast": "0" * 64, "runner_releases": "0" * 64}},
    ],
)
def test_una_identidad_fabricada_no_gobierna_el_preflight(sede, tmp_path, cambio):
    """R120-P0-2: resellar la capa exterior no basta; se cruza contra el shard que se consume."""
    _local(sede, tmp_path / "ev")
    manifiesto = _resellar(tmp_path / "ev" / "readiness_manifest.json", **cambio)
    fabrica, estado = _contador()

    with pytest.raises(ArtifactValidationError):
        run_external_readonly(local_evidence=manifiesto, entorno=_entorno(), sink_factory=fabrica)
    assert estado["n"] == 0, f"{cambio} llegó al borde externo"


def test_el_digest_del_manifiesto_se_recomputa_no_se_copia(sede, tmp_path):
    _local(sede, tmp_path / "ev")
    ruta = tmp_path / "ev" / "readiness_manifest.json"
    payload = json.loads(ruta.read_text("utf-8"))
    payload["disease_id"] = "padecimiento_fabricado"  # sin volver a sellar
    ruta.write_text(json.dumps(payload), encoding="utf-8")
    fabrica, estado = _contador()

    with pytest.raises(ArtifactValidationError, match="digest del manifiesto local"):
        run_external_readonly(local_evidence=ruta, entorno=_entorno(), sink_factory=fabrica)
    assert estado["n"] == 0


def test_un_archivo_del_shard_alterado_se_rechaza_antes_del_sink(sede, tmp_path):
    reporte = _local(sede, tmp_path / "ev")
    informe = (
        tmp_path
        / "ev"
        / "compile_a"
        / af.DISEASE
        / reporte["release_id"]
        / "reports"
        / "report.md"
    )
    informe.write_text("# informe alterado\n", encoding="utf-8")
    fabrica, estado = _contador()

    with pytest.raises(ArtifactValidationError, match="digest de reports/report.md"):
        run_external_readonly(
            local_evidence=tmp_path / "ev" / "readiness_manifest.json",
            entorno=_entorno(),
            sink_factory=fabrica,
        )
    assert estado["n"] == 0


# ── Evidencia externa persistida (R120-P1) ────────────────────────────────────────────────────
def test_un_pass_externo_deja_un_artefacto_cargable_y_recomputable(sede, tmp_path):
    _local(sede, tmp_path / "ev")
    fabrica, _ = _contador()
    reporte = run_external_readonly(
        local_evidence=tmp_path / "ev" / "readiness_manifest.json",
        entorno=_entorno(),
        sink_factory=fabrica,
    )
    assert reporte["status"] == "PASS_EXTERNAL_READONLY"

    ruta = tmp_path / "ev" / "external_preflight.json"
    persistido = json.loads(ruta.read_text("utf-8"))
    assert sorted(persistido) == sorted(EXTERNAL_KEYS)
    assert persistido["schema"] == EXTERNAL_SCHEMA

    from epiforecast.runner.release_contract import canonical_json, sha256_bytes

    cuerpo = {k: v for k, v in persistido.items() if k != "preflight_digest"}
    assert sha256_bytes(canonical_json(cuerpo)) == persistido["preflight_digest"]
    # Identidad cruzada con el local.
    local = json.loads((tmp_path / "ev" / "readiness_manifest.json").read_text("utf-8"))
    assert persistido["local_manifest_digest"] == local["manifest_digest"]
    assert persistido["disease_id"] == local["disease_id"]


@pytest.mark.parametrize("modo", ["bloqueado", "fallo"])
def test_ni_un_fallo_ni_un_bloqueo_destruyen_un_pass_externo_previo(sede, tmp_path, modo):
    _local(sede, tmp_path / "ev")
    manifiesto = tmp_path / "ev" / "readiness_manifest.json"
    fabrica, _ = _contador()
    run_external_readonly(local_evidence=manifiesto, entorno=_entorno(), sink_factory=fabrica)

    ruta = tmp_path / "ev" / "external_preflight.json"
    antes = ruta.read_bytes()

    if modo == "bloqueado":
        reporte = run_external_readonly(
            local_evidence=manifiesto,
            entorno=_entorno(**{STAGING_ID_ENV: ""}),
            sink_factory=fabrica,
        )
        assert reporte["status"] == STATUS_BLOCKED_EXTERNAL
    else:

        def revienta(_):
            raise RuntimeError(f"la hoja {CENTINELA_ID} no abre")

        reporte = run_external_readonly(
            local_evidence=manifiesto, entorno=_entorno(), sink_factory=revienta
        )
        assert reporte["status"] == STATUS_FAIL
        assert CENTINELA_ID not in json.dumps(reporte)

    assert ruta.read_bytes() == antes, "la evidencia del PASS anterior se conservó intacta"


def test_ningun_centinela_aparece_en_stdout_ni_en_ningun_archivo(sede, tmp_path):
    """Gate 10: se busca en la salida del CLI y en todo lo que quedó en disco."""
    _local(sede, tmp_path / "ev")
    salida = io.StringIO()

    def revienta(_):
        raise RuntimeError(f"fallo con {CENTINELA_ID} y {CENTINELA_JSON}")

    main(
        [
            "external-readonly",
            "--local-evidence",
            str(tmp_path / "ev" / "readiness_manifest.json"),
        ],
        entorno=_entorno(),
        salida=salida,
        sink_factory=revienta,
    )
    centinelas = (CENTINELA_ID, ID_PRODUCCION, "CENTINELA-CLAVE-PRIVADA")
    for centinela in centinelas:
        assert centinela not in salida.getvalue(), f"{centinela} en stdout"
    for archivo in _archivos(tmp_path):
        crudo = archivo.read_bytes().decode("utf-8", errors="replace")
        for centinela in centinelas:
            assert centinela not in crudo, f"{centinela} en {archivo.name}"
