"""E0-S1: catálogo canónico de producción (baseline 432, no el 435 inflado)."""

from __future__ import annotations

import json

import pytest
from scripts.build_catalogo_canonico import escribe_salidas

from epiforecast import catalog
from epiforecast.catalog import DENGUE_ELIGIBLE, build_production_catalog, validate_catalog


def _sources_present() -> bool:
    return catalog._neuro_table_path().exists() and catalog._dengue_table_path().exists()


pytestmark = pytest.mark.skipif(
    not _sources_present(),
    reason="requiere reports/ProdDetails/{tabla_333_modelos_produccion.xlsx,produccion_dengue.csv}",
)


@pytest.fixture(scope="module")
def catalog_data():
    return build_production_catalog()


def test_sin_duplicados_ni_motores_invalidos(catalog_data):
    df, _ = catalog_data
    assert validate_catalog(df) == []


def test_clave_unica_disease_entidad_sexo(catalog_data):
    df, _ = catalog_data
    assert not df.duplicated(subset=["disease_id", "entidad", "sexo"]).any()


def test_cohorte_neuro_es_333(catalog_data):
    _, counts = catalog_data
    assert counts.por_cohorte["neuro"] == 333
    # 3 padecimientos × 37 geografías × 3 sexos
    for pad in ("Alzheimer", "Depresion", "Parkinson"):
        assert counts.por_padecimiento[pad] == 111


def test_dengue_autoritativo_99_solo_motores_elegibles(catalog_data):
    df, counts = catalog_data
    assert counts.por_cohorte["dengue"] == 99
    den_engines = set(df[df["cohorte"] == "dengue"]["motor_productivo"])
    assert den_engines <= set(DENGUE_ELIGIBLE)


def test_produccion_es_432_no_435(catalog_data):
    _, counts = catalog_data
    assert counts.production_series_count == 432
    assert counts.production_series_count != 435  # el inflado con dup + inválidos


def _galeria_falsa(raiz, items):
    """Un dashboard mínimo: ``Reports/index.html`` con la línea ``const DATA = [...]``."""
    rep = raiz / "Reports"
    rep.mkdir(parents=True)
    data = json.dumps(items, ensure_ascii=False)
    (rep / "index.html").write_text(f"<script>\nconst DATA = {data};\n</script>\n", "utf-8")
    return raiz


def test_galeria_se_cuenta_en_lo_publicado(tmp_path, monkeypatch):
    """Ronda W37: la galería son 432 gráficos (sin las 4 regiones de Dengue), contados en la
    lista que la galería pinta. Antes se leía `_gallery_items.json` de Dengue ANTES de regenerarlo
    y, si no se encontraba, se suponía 111: el candidato W37 publicó 444 con 432 gráficos."""
    items = [{"p": "Depresión", "f": f"Depresión/x/{i}.png"} for i in range(333)]
    items += [{"p": "Dengue", "f": f"dengue/x/{i}.png"} for i in range(99)]
    monkeypatch.setenv(catalog.DASHBOARD_ENV, str(_galeria_falsa(tmp_path, items)))
    _, counts = build_production_catalog()
    assert counts.gallery_item_count == 432 == counts.production_series_count


def test_sin_galeria_no_se_supone_un_conteo(tmp_path, monkeypatch):
    monkeypatch.setenv(catalog.DASHBOARD_ENV, str(tmp_path / "no_existe"))
    _, counts = build_production_catalog()
    assert counts.gallery_item_count is None


def test_galeria_sin_lista_data_falla(tmp_path, monkeypatch):
    (tmp_path / "Reports").mkdir()
    (tmp_path / "Reports" / "index.html").write_text("<html></html>", "utf-8")
    monkeypatch.setenv(catalog.DASHBOARD_ENV, str(tmp_path))
    with pytest.raises(ValueError, match="const DATA"):
        build_production_catalog()


def test_diagnostico_documenta_dengue_stale(catalog_data):
    _, counts = catalog_data
    d = counts.diagnostics
    # El Dengue de tabla_333 trae 99 filas (los 3 nacionales duplicados se repararon el
    # 2026-09-02 con la autoridad de produccion_dengue.csv), sigue sin NBGLM y con
    # Ensemble/Stacking: por eso NO se usa.
    assert d.get("dengue_en_tabla_333") == 99
    assert d.get("nacionales_duplicados") == 0
    assert d.get("tiene_nbglm") is False
    assert d.get("selecciones_invalidas_ensemble_stacking", 0) > 0


# --------------------------------------------------------------------------------------
# Gate de vocabulario público (2026-08-24). Ver docs/CONTRATO_VOCABULARIO_CIFRAS.md.
# Añadido tras encontrar que el sitio publicado respondía 435 donde las diapositivas
# decían 333 y el manifiesto decía 432.
# --------------------------------------------------------------------------------------


def test_dengue_sale_de_la_asignacion_autoritativa(catalog_data):
    """No basta con que los motores sean elegibles: cada serie lleva el motor de la asignación.

    El Dengue de `tabla_333` también pasa «solo motores elegibles» si se le quitan Ensemble y
    Stacking, y aun así sería la selección vieja. Antes la huella era «NBGLM está presente»;
    desde la ronda W37 NBGLM está suspendido (ENMIENDA_DENGUE_NBGLM_W37) y la huella es
    coincidir serie por serie con `produccion_dengue.csv`.
    """
    import pandas as pd

    df, _ = catalog_data
    den = df[df["cohorte"] == "dengue"].set_index(["entidad", "sexo"])["motor_productivo"]
    prod = pd.read_csv(catalog._dengue_table_path()).set_index(["entidad", "sexo"])
    assert den.sort_index().to_dict() == prod["motor_productivo"].sort_index().to_dict()
    assert not ({"Ensemble", "Stacking"} & set(den))


def test_por_sexo_es_144_cada_uno(catalog_data):
    """432 / 3. Si sale 145, alguien volvió a contar desde la tabla inflada."""
    df, _ = catalog_data
    assert df["sexo"].value_counts().to_dict() == {
        "hombres": 144,
        "mujeres": 144,
        "general": 144,
    }


def test_nacional_es_12_y_no_15(catalog_data):
    """9 neuro (3 padecimientos × 3 sexos) + 3 dengue.

    El 15 del catálogo inflado son estos 12 más las 3 series `Dengue · Nacional`
    contadas una segunda vez, por el otro motor.
    """
    df, _ = catalog_data
    nac = df[df["entidad"].astype(str).str.lower().str.contains("nacional", na=False)]
    assert len(nac) == 12
    assert nac["cohorte"].value_counts().to_dict() == {"neuro": 9, "dengue": 3}


def test_distribucion_de_motores_suma_432(catalog_data):
    """Un desglose por motor es una distribución: siempre suma el total de su cohorte."""
    _, counts = catalog_data
    assert sum(counts.motor_dist["neuro"].values()) == 333
    assert sum(counts.motor_dist["dengue"].values()) == 99
    total = sum(sum(v.values()) for v in counts.motor_dist.values())
    assert total == counts.production_series_count == 432


def test_manifiesto_en_disco_no_esta_rancio(catalog_data):
    """El manifiesto publicado tiene que decir lo mismo que las fuentes de hoy.

    Este control existe por un caso real: el 24-ago-2026 el
    `catalogo_canonico_counts.json` vigente se había construido el 18-ago a las 15:31 y
    `produccion_dengue.csv` se regeneró ese mismo día a las 22:30. El manifiesto seguía
    publicando `DeepAR 30 · NBGLM 30 · Prophet 39` cuando la distribución real era
    `Prophet 46 · DeepAR 27 · NBGLM 26`. **Los totales coincidían**, así que ningún
    conteo lo delataba: sólo el desglose.
    """
    import json

    _, counts = catalog_data
    ruta = catalog._proddetails_dir() / "catalogo_canonico_counts.json"
    if not ruta.exists():
        pytest.skip("no hay manifiesto en disco; se genera con scripts.build_catalogo_canonico")
    disco = json.loads(ruta.read_text(encoding="utf-8"))
    assert disco["production_series_count"] == counts.production_series_count
    if counts.gallery_item_count is not None:  # sin galería a mano no hay con qué contrastar
        assert disco["gallery_item_count"] == counts.gallery_item_count
    assert disco["por_cohorte"] == counts.por_cohorte
    assert disco["motor_dist"] == counts.motor_dist, (
        "el manifiesto en disco quedó más viejo que sus fuentes: "
        "corre `python -m scripts.build_catalogo_canonico`"
    )


def test_el_generador_escribe_json_con_salto_final(tmp_path):
    """Sin el «\\n» final, el hook end-of-file-fixer reescribe el archivo y el commit deja de
    coincidir byte a byte con el sello (lo delató la corrida 5 de P1, 2-sep-2026)."""
    df, counts = build_production_catalog()
    csv_path, json_path = escribe_salidas(df, counts, tmp_path)
    crudo = json_path.read_bytes()
    assert crudo.endswith(b"}\n") and not crudo.endswith(b"\n\n")
    assert json.loads(crudo)["production_series_count"] == 432
    assert csv_path.read_bytes().endswith(b"\n")
