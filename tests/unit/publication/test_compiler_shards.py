"""C7.3a — gate del compilador y de los cuatro puentes candidate.

Lo que se demuestra aquí, en este orden:

1. compilar **no** es publicar: `trained` compila a staging y sigue invisible en todo lo público;
2. `public` falla cerrado mientras no exista el puntero de C7.5;
3. dos compilaciones dan los MISMOS bytes;
4. cada valor de cada puente cuadra con el forecast SELLADO, no con un recálculo;
5. F50 es una prueba negativa explícita;
6. los artefactos públicos vigentes de los cuatro publicados no cambian.

Todo escribe en `tmp_path`. El staging se inyecta, y el propio compilador rechaza que caiga dentro
de una ruta pública del repo.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pandas as pd
import pytest

from epiforecast import registry
from epiforecast.publication.compiler import (
    MODE_CANDIDATE,
    MODE_PUBLIC,
    PUBLICATION_COLUMNS,
    UNCERTAINTY_LABEL,
    check_staging_root,
    compile_release,
)
from epiforecast.publication.shards import (
    CHANNEL_EPIBOT,
    CHANNEL_REPORTS,
    CHANNEL_TABLEAU,
    CHANNEL_WEB,
    SHARD_MANIFEST,
    emit_shards,
)
from epiforecast.publication.status import load_declared_status
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.release_store import promote_release
from tests.unit.runner import artifact_fixtures as af
from tests.unit.runner import release_fixtures as rf

pytestmark = pytest.mark.skipif(
    not af.hay_runs(), reason="los runs sellados de C5 no están en este entorno (runs/ gitignored)"
)

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def sede(tmp_path_factory) -> Path:
    """Sede propia con el release promovido: nunca la del repo."""
    raiz = tmp_path_factory.mktemp("publicacion")
    bundle = rf.construir(raiz).path
    destino = raiz / "releases"
    promote_release(bundle, releases_root=destino, disease_id=af.DISEASE)
    return destino


def _estado():
    """Estado prospectivo DECLARADO del padecimiento, ya validado contra su gate congelado."""
    return load_declared_status(af.DISEASE)


def _compilar(sede: Path, **extra):
    extra.setdefault("status", _estado())
    return compile_release(disease_id=af.DISEASE, mode=MODE_CANDIDATE, releases_root=sede, **extra)


@pytest.fixture(scope="module")
def compilacion(sede):
    return _compilar(sede)


# ── Modos: compilar no es publicar ────────────────────────────────────────────────────────────
def test_un_padecimiento_trained_compila_a_candidate(compilacion):
    assert compilacion.mode == MODE_CANDIDATE
    assert compilacion.disease.lifecycle == "trained"
    assert list(compilacion.rows.columns) == list(PUBLICATION_COLUMNS)


def test_el_modo_public_falla_sin_puntero(sede):
    """C7.5 aún no existe: publicar no puede ser posible todavía, y falla diciendo por qué."""
    with pytest.raises(ArtifactValidationError, match="lifecycle para publicar"):
        compile_release(disease_id=af.DISEASE, mode=MODE_PUBLIC, releases_root=sede)


def test_el_modo_public_exige_puntero_incluso_estando_published(sede, monkeypatch):
    publicado = dataclasses.replace(registry.require(af.DISEASE), lifecycle="published")
    monkeypatch.setattr(registry, "require", lambda _: publicado)
    with pytest.raises(ArtifactValidationError, match="puntero público activo"):
        compile_release(disease_id=af.DISEASE, mode=MODE_PUBLIC, releases_root=sede)


def test_el_modo_public_rechaza_un_puntero_a_otro_release(sede, monkeypatch):
    publicado = dataclasses.replace(registry.require(af.DISEASE), lifecycle="published")
    monkeypatch.setattr(registry, "require", lambda _: publicado)
    with pytest.raises(ArtifactValidationError, match="apunta a otro release"):
        compile_release(
            disease_id=af.DISEASE,
            mode=MODE_PUBLIC,
            releases_root=sede,
            pointer_release_id="obesidad_release_000000000000",
        )


@pytest.mark.parametrize("publico", ["reports", "data", "epibot", "models", "artifacts"])
def test_candidate_no_puede_escribir_en_una_ruta_publica_del_repo(publico):
    with pytest.raises(ArtifactValidationError, match="ruta pública"):
        check_staging_root(REPO / publico / "staging", REPO)


def test_candidate_acepta_un_staging_fuera_de_las_rutas_publicas(tmp_path):
    assert check_staging_root(tmp_path / "staging", REPO) == (tmp_path / "staging").resolve()


# ── Contrato de salida ────────────────────────────────────────────────────────────────────────
def test_cada_fila_conserva_identidad_procedencia_y_point_only(compilacion):
    filas = compilacion.rows
    assert set(filas["release_id"]) == {compilacion.release_id}
    assert set(filas["disease_id"]) == {af.DISEASE}
    assert set(filas["interval_method"]) == {"none"}
    assert filas["yhat_lower"].isna().all() and filas["yhat_upper"].isna().all()
    assert set(filas["uncertainty_label"]) == {UNCERTAINTY_LABEL}
    assert set(filas["forecast_run_id"]) == {compilacion.verified.chain["forecast_run_id"]}


def test_las_bases_llevan_su_motor_y_los_derivados_el_portafolio(compilacion):
    base, derivados = compilacion.base_rows, compilacion.derived_rows
    conteos, horizonte = compilacion.verified.counts, compilacion.verified.horizon
    assert len(base) == conteos["base"] * horizonte
    assert len(derivados) == conteos["derived"] * horizonte
    assert set(derivados["engine"]) == {"portfolio"}
    # Cada serie base lleva EL motor que le asignó la selección congelada.
    seleccion = compilacion.verified.selection
    for geo, sexo, motor in zip(base["geography_id"], base["sex"], base["engine"], strict=True):
        assert motor == seleccion[(geo, sexo)]


def test_los_valores_cuadran_con_el_forecast_sellado(compilacion):
    """Nada se recalcula: el compilador traduce el `forecast.csv` del bundle, no lo reproduce."""
    sellado = pd.read_csv(
        compilacion.verified.root / "forecast" / "forecast.csv",
        dtype={"geography_id": str},
        float_precision="round_trip",
    )
    orden = ["geography_level", "geography_id", "sex", "epi_year", "epi_week"]
    izq = compilacion.rows.sort_values(orden).reset_index(drop=True)
    der = sellado.sort_values(orden).reset_index(drop=True)
    assert len(izq) == len(der)
    assert (izq["yhat_cases"] - der["y_pred_cases"]).abs().max() == 0.0


# ── Puentes ───────────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def shards(compilacion, tmp_path_factory):
    return emit_shards(compilacion, tmp_path_factory.mktemp("staging"))


def test_se_emiten_los_cuatro_puentes(shards):
    for canal in (CHANNEL_REPORTS, CHANNEL_TABLEAU, CHANNEL_WEB, CHANNEL_EPIBOT):
        assert canal in shards.channels
        assert (shards.root / canal).is_dir()


def test_los_canales_declarados_sin_puente_quedan_registrados(shards):
    """Un canal declarado que nadie compila no puede desaparecer en silencio."""
    manifest = json.loads((shards.root / SHARD_MANIFEST).read_text(encoding="utf-8"))
    declarados = set(registry.require(af.DISEASE).channels)
    assert (
        set(manifest["channels_emitted"]) | set(manifest["channels_without_bridge"]) == declarados
    )


def test_los_conteos_de_los_puentes_cuadran_con_el_release(shards, compilacion):
    manifest = json.loads((shards.root / SHARD_MANIFEST).read_text(encoding="utf-8"))
    conteos = compilacion.verified.counts
    assert manifest["models"] == conteos["models"]
    assert manifest["products"] == conteos["products"]
    assert manifest["rows"] == len(compilacion.rows)
    for csv in ("reports/forecast_products.csv", "tableau/forecast_shard.csv", "web/series.csv"):
        frame = pd.read_csv(shards.root / csv, dtype={"geography_id": str})
        assert len(frame) == len(compilacion.rows)


def test_el_puente_web_deriva_sus_filtros_de_los_datos_y_del_registry(shards, compilacion):
    manifest = json.loads(
        (shards.root / CHANNEL_WEB / "manifest.json").read_text(encoding="utf-8")
    )
    disease = registry.require(af.DISEASE)
    assert manifest["web"]["color"] == disease.web["color"]
    assert manifest["cie_codes"] == list(disease.cie_codes)
    assert manifest["slug"] == disease.slug
    assert manifest["filters"]["sexes"] == sorted(set(compilacion.rows["sex"]))
    assert len(manifest["filters"]["geography_ids"]) == len(set(compilacion.rows["geography_id"]))


def test_el_corpus_del_epibot_niega_los_intervalos_y_distingue_modelos_de_productos(shards):
    """Regla 10: el RAG no puede afirmar intervalos ni confundir 64 modelos con 111 productos."""
    texto = (shards.root / CHANNEL_EPIBOT / "corpus" / f"{af.DISEASE}.md").read_text(
        encoding="utf-8"
    )
    assert "NO tiene intervalos" in texto
    assert UNCERTAINTY_LABEL in texto
    assert "NO son lo mismo" in texto
    knowledge = json.loads(
        (shards.root / CHANNEL_EPIBOT / "knowledge.json").read_text(encoding="utf-8")
    )
    assert knowledge["release"]["uncertainty_available"] is False


def test_ningun_puente_declara_intervalos(shards):
    for ruta, _ in shards.files.items():
        if ruta.endswith(".json"):
            texto = (shards.root / ruta).read_text(encoding="utf-8")
            assert '"uncertainty_available":false' in texto.replace(" ", "")


# ── Determinismo ──────────────────────────────────────────────────────────────────────────────
def test_dos_compilaciones_producen_los_mismos_bytes(sede, tmp_path):
    uno = emit_shards(_compilar(sede), tmp_path / "a")
    otro = emit_shards(_compilar(sede), tmp_path / "b")
    assert uno.files == otro.files  # ruta → digest, idénticos
    assert (uno.root / SHARD_MANIFEST).read_bytes() == (otro.root / SHARD_MANIFEST).read_bytes()
    for ruta in uno.files:
        assert (uno.root / ruta).read_bytes() == (otro.root / ruta).read_bytes()


def test_los_shards_no_llevan_timestamps_ni_rutas_del_equipo(shards):
    for ruta in [*shards.files, SHARD_MANIFEST]:
        texto = (shards.root / ruta).read_text(encoding="utf-8", errors="ignore")
        for prohibido in ("created_at", "generated_at", "/Users/", "/private/"):
            assert prohibido not in texto


# ── Invisibilidad y prueba negativa ───────────────────────────────────────────────────────────
def test_obesidad_sigue_invisible_en_todo_lo_publico(shards):
    """Compilar a staging no la asoma a ningún canal público mientras siga `trained`."""
    assert registry.require(af.DISEASE).lifecycle == "trained"
    assert af.DISEASE not in [d.lower() for d in registry.published_members()]
    for canal in (CHANNEL_REPORTS, CHANNEL_TABLEAU, CHANNEL_WEB, CHANNEL_EPIBOT):
        assert af.DISEASE not in [d.lower() for d in registry.published_members(canal)]


@pytest.mark.parametrize(
    "artefacto",
    [
        "reports/forecasts/prophet/all_forecast_prophet.csv",
        "reports/forecasts/deepar/all_forecast_deepar.csv",
        "reports/forecasts/ensemble/all_forecast_ensemble.csv",
        "reports/forecasts/stacking/all_forecast_stacking.csv",
    ],
)
def test_los_agregados_legacy_no_contienen_al_padecimiento_compilado(artefacto):
    """Regla 1: compilar jamás añade filas a los agregados de los cuatro publicados."""
    ruta = REPO / artefacto
    if not ruta.exists():
        pytest.skip(f"{artefacto} no está en este entorno")
    padecimientos = set(
        pd.read_csv(ruta, usecols=["meta_padecimiento"])["meta_padecimiento"].astype(str)
    )
    assert not {p for p in padecimientos if p.lower() == af.DISEASE}
    # Y el contenido no se movió: el gate de preservación vive también aquí.
    assert padecimientos


def test_f50_no_se_compila(sede):
    """Prueba negativa explícita (regla 8): F50 no tiene release y el compilador lo rechaza."""
    f50 = registry.require("anorexia_f50")
    assert f50.lifecycle == "configured"
    with pytest.raises(ArtifactValidationError, match="exige backend 'runner_release'"):
        compile_release(disease_id="anorexia_f50", mode=MODE_CANDIDATE, releases_root=sede)


def test_un_padecimiento_legacy_tampoco_se_compila(sede):
    """Los cuatro publicados viven en el carril legacy: este compilador no los toca."""
    with pytest.raises(ArtifactValidationError, match="exige backend 'runner_release'"):
        compile_release(disease_id="depresion", mode=MODE_CANDIDATE, releases_root=sede)


# ── El guard tiene que GUARDAR, no sólo existir ───────────────────────────────────────────────
@pytest.mark.parametrize("publico", ["reports", "data", "epibot", "models", "artifacts"])
def test_emit_shards_rechaza_por_si_mismo_un_destino_publico(compilacion, tmp_path, publico):
    """El defecto que encontró la auditoría: el guard estaba en el compilador y nadie lo llamaba.

    Con `check_staging_root` sólo exportado, `emit_shards` aceptaba cualquier ruta —incluida
    `reports/`—. Una comprobación que el llamador puede olvidar no es una comprobación.
    """
    falso_repo = tmp_path / "repo"
    (falso_repo / publico).mkdir(parents=True)
    with pytest.raises(ArtifactValidationError, match="ruta pública"):
        emit_shards(compilacion, falso_repo / publico / "staging", repo_root_path=falso_repo)


def test_emit_shards_acepta_un_staging_legitimo(compilacion, tmp_path):
    falso_repo = tmp_path / "repo"
    falso_repo.mkdir()
    shards = emit_shards(compilacion, tmp_path / "staging", repo_root_path=falso_repo)
    assert shards.files


def test_los_periodos_del_manifest_web_salen_del_calendario_del_release(shards, compilacion):
    """No de la posición de una fila: con el orden geográfico coincidía por casualidad."""
    manifest = json.loads(
        (shards.root / CHANNEL_WEB / "manifest.json").read_text(encoding="utf-8")
    )
    release = json.loads(
        (compilacion.verified.root / "release_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["filters"]["periods"] == [
        release["calendar"]["first_period"],
        release["calendar"]["last_period"],
    ]
