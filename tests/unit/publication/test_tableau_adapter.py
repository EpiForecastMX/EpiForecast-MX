"""C7.6-ADAPTERS-A — el adaptador de Tableau y su sink transaccional.

Lo que se protege: que un release del runner llegue a Tableau **sin tocar las cinco tablas legacy** y
sin que una promoción a medias deje el destino roto. El sink es un doble en memoria: esta ronda no
autentica ni escribe en Google Sheets.

El grueso usa un shard SINTÉTICO —un padecimiento inventado, con conteos propios—, porque un
adaptador que sólo funcionara con Obesidad no sería genérico. Las pruebas contra el shard real se
saltan si `runs/` no está en el entorno.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from epiforecast.publication.tableau_adapter import (
    SUFFIX_NEXT,
    SUFFIX_PREVIOUS,
    TABLE_FORECAST,
    TABLE_RELEASES,
    MemorySink,
    build_tables,
    promote,
    read_local,
    rollback,
    upsert_releases,
    write_local,
)
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.release_contract import canonical_json
from tests.unit.runner import artifact_fixtures as af

COLUMNAS = [
    "release_id",
    "disease_id",
    "geography_level",
    "geography_id",
    "sex",
    "frequency",
    "epi_year",
    "epi_week",
    "ds",
    "yhat_cases",
    "engine",
    "derived",
    "origin_epi_year",
    "origin_epi_week",
    "horizon",
    "forecast_run_id",
    "refit_digest",
    "interval_method",
    "yhat_lower",
    "yhat_upper",
    "uncertainty_label",
]
OTRO = "padecimiento_x"
OTRO_RELEASE = "padecimiento_x_release_abc123456789"
ETIQUETA = "Validación prospectiva en curso (0/4 semanas) · pronóstico puntual sin intervalos"


def _estado(**cambios) -> dict:
    base = {
        "schema": "prospective_status.v2",
        "gate_digest": "a" * 64,
        "evaluation_digest": "b" * 64,
        "status_digest": "c" * 64,
        "observation_dataset_id": "obs_dataset",
        "verdict": "INCOMPLETE",
        "weeks_required": 4,
        "weeks_available": 0,
        "completed_weeks": [],
        "target_weeks": [[2026, 27], [2026, 28], [2026, 29], [2026, 30]],
        "label": ETIQUETA,
    }
    base.update(cambios)
    return base


def _shard(tmp_path: Path, *, filas: int = 3, limites: bool = False, **manifiesto) -> Path:
    """Shard sintético mínimo con la forma que emite el compilador."""
    root = tmp_path / OTRO / OTRO_RELEASE
    (root / "tableau").mkdir(parents=True, exist_ok=True)

    cuerpo = []
    for i in range(filas):
        fila = dict.fromkeys(COLUMNAS, "")
        fila.update(
            {
                "release_id": OTRO_RELEASE,
                "disease_id": OTRO,
                "geography_level": "estado",
                "geography_id": f"{i + 1:02d}",
                "sex": "general",
                "frequency": "epi_week",
                "epi_year": "2026",
                "epi_week": str(27 + i),
                "ds": f"2026-07-0{i + 1}",
                "yhat_cases": str(10 + i),
                "engine": "portfolio",
                "derived": "True",
                "origin_epi_year": "2026",
                "origin_epi_week": "26",
                "horizon": "52",
                "forecast_run_id": "run_x",
                "refit_digest": "d" * 64,
                "interval_method": "none",
                "yhat_lower": "9" if limites else "",
                "yhat_upper": "11" if limites else "",
                "uncertainty_label": "Pronóstico puntual; sin intervalo de incertidumbre",
            }
        )
        cuerpo.append(fila)
    pd.DataFrame(cuerpo, columns=COLUMNAS).to_csv(
        root / "tableau" / "forecast_shard.csv", index=False
    )

    comun = {
        "schema": "publication_shard.v1",
        "disease_id": OTRO,
        "release_id": OTRO_RELEASE,
        "display_name": "Padecimiento X",
        "lifecycle": "trained",
        "origin": [2026, 26],
        "horizon_weeks": 52,
        "rows": filas,
        "models": 7,
        "products": 9,
        "interval_method": "none",
        "uncertainty_available": False,
        "publication_status": _estado(),
        "publication_label": ETIQUETA,
    }
    comun.update(manifiesto)
    (root / "shard_manifest.json").write_bytes(canonical_json(comun))
    (root / "tableau" / "schema.json").write_bytes(
        canonical_json({**comun, "channel": "tableau", "columns": [{"name": c} for c in COLUMNAS]})
    )
    return root


# ── Construcción de las dos tablas ────────────────────────────────────────────────────────────
def test_las_dos_tablas_salen_del_manifiesto_no_de_constantes(tmp_path):
    tablas = build_tables(_shard(tmp_path, filas=5))
    assert list(tablas.forecast.columns) == COLUMNAS
    assert len(tablas.forecast) == 5  # el conteo lo declara el shard, no el código
    assert len(tablas.releases) == 1
    fila = tablas.releases.iloc[0]
    assert (fila.disease_id, fila.release_id) == (OTRO, OTRO_RELEASE)
    assert fila.publication_label == ETIQUETA
    assert (fila.verdict, fila.weeks_available, fila.weeks_required) == ("INCOMPLETE", 0, 4)
    assert fila.uncertainty_available is False or fila.uncertainty_available == False  # noqa: E712
    assert fila.refit_digest == "d" * 64
    for clave in ("gate_digest", "evaluation_digest", "status_digest"):
        assert len(fila[clave]) == 64


def _codigo_del_adaptador() -> tuple[list[str], list[object]]:
    """Nombres importados y constantes del AST, SIN docstrings ni comentarios.

    Se inspecciona el árbol y no el texto: la prosa del módulo explica por qué no usa `filter_neuro`
    ni los conteos de Obesidad, y buscar cadenas sueltas confundiría la explicación con el defecto.
    """
    import ast

    arbol = ast.parse(
        Path("src/epiforecast/publication/tableau_adapter.py").read_text(encoding="utf-8")
    )
    importados: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom):
            importados += [f"{nodo.module}.{a.name}" for a in nodo.names]
        elif isinstance(nodo, ast.Import):
            importados += [a.name for a in nodo.names]

    docstrings = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(nodo, clean=False)
            if doc is not None:
                docstrings.add(doc)
    constantes = [
        n.value
        for n in ast.walk(arbol)
        if isinstance(n, ast.Constant) and n.value not in docstrings
    ]
    return importados, constantes


def test_el_adaptador_no_conoce_la_cohorte_neuro():
    """No importa `filter_neuro`: el universo lo define el shard, no una lista de padecimientos."""
    importados, constantes = _codigo_del_adaptador()
    assert not any("filter_neuro" in i or "cohorts" in i for i in importados), importados
    textos = [c for c in constantes if isinstance(c, str)]
    numeros = [c for c in constantes if isinstance(c, (int, float)) and not isinstance(c, bool)]
    for prohibido in ("Obesidad", "obesidad", "E66"):
        assert not any(prohibido in t for t in textos), f"{prohibido} escrito en la lógica"
    for conteo in (64, 111, 5772):
        assert conteo not in numeros, (
            f"el conteo {conteo} no puede estar escrito: sale del manifiesto"
        )


@pytest.mark.parametrize(
    ("cambio", "patron"),
    [
        ({"rows": 99}, "filas"),
        ({"uncertainty_available": True}, "incertidumbre"),
        ({"publication_label": "otra"}, "etiqueta contra el estado"),
        ({"publication_status": None}, "publication_status"),
        ({"schema": "publication_shard.v2"}, "schema"),
    ],
)
def test_rechazos_del_shard(tmp_path, cambio, patron):
    with pytest.raises(ArtifactValidationError, match=patron):
        build_tables(_shard(tmp_path, **cambio))


def test_un_limite_de_intervalo_rompe_el_contrato_point_only(tmp_path):
    with pytest.raises(ArtifactValidationError, match="point-only"):
        build_tables(_shard(tmp_path, limites=True))


def test_una_clave_serie_periodo_duplicada_se_rechaza(tmp_path):
    root = _shard(tmp_path, filas=2)
    csv = root / "tableau" / "forecast_shard.csv"
    lineas = csv.read_text(encoding="utf-8").splitlines(keepends=True)
    csv.write_text("".join([*lineas, lineas[1]]), encoding="utf-8")
    (root / "shard_manifest.json").write_bytes(
        canonical_json({**json.loads((root / "shard_manifest.json").read_text()), "rows": 3})
    )
    with pytest.raises(ArtifactValidationError, match="duplicadas"):
        build_tables(root)


# ── Upsert y serialización ────────────────────────────────────────────────────────────────────
def test_el_upsert_reemplaza_su_release_y_respeta_los_demas(tmp_path):
    nuevas = build_tables(_shard(tmp_path)).releases
    ajena = pd.DataFrame(
        [{**nuevas.iloc[0].to_dict(), "disease_id": "otro", "release_id": "otro_r"}]
    )
    vieja = pd.DataFrame([{**nuevas.iloc[0].to_dict(), "verdict": "PASS"}])

    resultado = upsert_releases(pd.concat([ajena, vieja], ignore_index=True), nuevas)
    assert len(resultado) == 2, "ni duplica el propio ni borra el ajeno"
    propia = resultado[resultado.release_id == OTRO_RELEASE].iloc[0]
    assert propia.verdict == "INCOMPLETE", "la fila propia se REEMPLAZA"
    assert (resultado.release_id == "otro_r").sum() == 1, "el release ajeno sobrevive"


def test_serializacion_local_determinista_y_round_trip(tmp_path):
    tablas = build_tables(_shard(tmp_path, filas=4))
    a, b = tmp_path / "a", tmp_path / "b"
    assert write_local(tablas, a) == write_local(tablas, b), "dos escrituras, los mismos digests"
    leido = read_local(a)
    pd.testing.assert_frame_equal(leido[TABLE_FORECAST], tablas.forecast)
    assert list(leido[TABLE_RELEASES].columns) == list(tablas.releases.columns)
    assert (a / "runner_tables.xlsx").is_file()
    assert json.loads((a / "adapter_manifest.json").read_text())["tables"] == {
        TABLE_FORECAST: 4,
        TABLE_RELEASES: 1,
    }


# ── Sink transaccional ────────────────────────────────────────────────────────────────────────
def test_la_promocion_escribe_next_valida_y_luego_intercambia(tmp_path):
    tablas = build_tables(_shard(tmp_path))
    sink = MemorySink({TABLE_FORECAST: pd.DataFrame([{"x": 1}]), TABLE_RELEASES: tablas.releases})
    resultado = promote(sink, tablas)

    orden = [op for op in sink.operaciones if op.startswith(("write:", "rename:"))]
    assert orden[0].startswith(f"write:{TABLE_FORECAST}{SUFFIX_NEXT}"), "primero las __next"
    assert all(SUFFIX_NEXT in op for op in orden if op.startswith("write:"))
    assert any(f"rename:{TABLE_FORECAST}->{TABLE_FORECAST}{SUFFIX_PREVIOUS}" == op for op in orden)
    assert sorted(resultado["promoted"]) == [TABLE_FORECAST, TABLE_RELEASES]
    assert f"{TABLE_FORECAST}{SUFFIX_PREVIOUS}" in sink.list_tables()
    assert f"{TABLE_FORECAST}{SUFFIX_NEXT}" not in sink.list_tables()


def test_las_tablas_legacy_no_se_tocan(tmp_path):
    legacy = {
        n: pd.DataFrame([{"x": 1}])
        for n in ("scaffold", "real", "forecast", "metricas", "entidades")
    }
    sink = MemorySink(legacy)
    promote(sink, build_tables(_shard(tmp_path)))
    for nombre, frame in legacy.items():
        pd.testing.assert_frame_equal(sink.read_table(nombre), frame)
    assert not any(op.split(":")[1].split("->")[0] in legacy for op in sink.operaciones)


def test_un_fallo_a_media_promocion_no_reemplaza_las_activas(tmp_path):
    tablas = build_tables(_shard(tmp_path))
    activas = {TABLE_FORECAST: pd.DataFrame([{"x": "activa"}])}

    class SinkQueFalla(MemorySink):
        def write_table(self, name, frame):
            if name == f"{TABLE_RELEASES}{SUFFIX_NEXT}":
                raise RuntimeError("la hoja rechazó la escritura")
            super().write_table(name, frame)

    sink = SinkQueFalla(activas)
    with pytest.raises(RuntimeError, match="rechazó"):
        promote(sink, tablas)
    pd.testing.assert_frame_equal(sink.read_table(TABLE_FORECAST), activas[TABLE_FORECAST])
    assert not [t for t in sink.list_tables() if t.endswith(SUFFIX_NEXT)], (
        "sin temporales colgando"
    )


def test_el_rollback_es_el_swap_inverso(tmp_path):
    tablas = build_tables(_shard(tmp_path))
    previa = pd.DataFrame([{"x": "la de antes"}])
    sink = MemorySink({TABLE_FORECAST: previa})
    promote(sink, tablas)
    assert len(sink.read_table(TABLE_FORECAST)) == len(tablas.forecast)

    restauradas = rollback(sink)
    assert TABLE_FORECAST in restauradas
    pd.testing.assert_frame_equal(sink.read_table(TABLE_FORECAST), previa)
    assert f"{TABLE_FORECAST}{SUFFIX_PREVIOUS}" not in sink.list_tables()


def test_sin_previa_el_rollback_no_inventa_nada(tmp_path):
    sink = MemorySink()
    promote(sink, build_tables(_shard(tmp_path)))
    assert rollback(sink) == [], "sin __previous no hay a qué volver"
    assert sorted(sink.list_tables()) == [TABLE_FORECAST, TABLE_RELEASES]


def test_el_adaptador_no_autentica_ni_escribe_en_sheets():
    """Esta ronda no toca la hoja: ni cliente, ni credenciales, ni variable de entorno."""
    fuente = Path("src/epiforecast/publication/tableau_adapter.py").read_text(encoding="utf-8")
    for prohibido in (
        "gspread",
        "GSHEETS_SPREADSHEET_ID",
        "GOOGLE_SERVICE_ACCOUNT",
        "Credentials",
    ):
        assert prohibido not in fuente


# ── Contra el shard real ──────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(not af.hay_runs(), reason="los runs sellados de C5 no están en este entorno")
def test_el_shard_real_produce_las_dos_tablas(tmp_path):
    from epiforecast.publication.compiler import MODE_CANDIDATE, compile_release
    from epiforecast.publication.shards import emit_shards
    from epiforecast.publication.status import load_declared_status
    from epiforecast.runner.release_store import default_releases_root

    c = compile_release(
        disease_id=af.DISEASE,
        mode=MODE_CANDIDATE,
        releases_root=default_releases_root(),
        status=load_declared_status(af.DISEASE),
    )
    shards = emit_shards(c, tmp_path / "staging")
    tablas = build_tables(shards.root)

    assert len(tablas.forecast) == int(c.verified.counts["products_forecast"])
    assert len(tablas.releases) == 1
    fila = tablas.releases.iloc[0]
    assert fila.release_id == c.release_id
    assert fila.lifecycle == "trained"
    assert fila.verdict == "INCOMPLETE"
    assert fila.publication_label.endswith("pronóstico puntual sin intervalos")

    sink = MemorySink()
    promote(sink, tablas)
    assert sorted(sink.list_tables()) == [TABLE_FORECAST, TABLE_RELEASES]
    assert len(sink.read_table(TABLE_FORECAST)) == len(tablas.forecast)
