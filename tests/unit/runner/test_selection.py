"""F2/C5.1 — selector por SeriesKey: umbral exacto de 5%, bandas, desempates y congelado."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from epiforecast.runner import contracts as ct
from epiforecast.runner import selection
from epiforecast.runner.policy import load_policy

_RULE = selection.SelectionRule.from_policy(load_policy("rolling_cv_v1"))
_INCUMBENT = "seasonal_mean_5y"
_CHALLENGER = "prophet_rate_log1p"


def _rows(valores: dict[str, tuple[float, float, float]]) -> pd.DataFrame:
    """Una fila agregada por motor: (sMAPE, MASE, RMSE)."""
    return pd.DataFrame(
        [
            {
                ct.COL_ENGINE: engine,
                ct.COL_SMAPE: smape,
                ct.COL_MASE: mase,
                ct.COL_RMSE: rmse,
            }
            for engine, (smape, mase, rmse) in valores.items()
        ]
    )


def _todos_los_incumbents(smape: float) -> dict[str, tuple[float, float, float]]:
    return {e: (smape, 1.0, 10.0) for e in _RULE.incumbents}


def _incumbentes(
    **explicitos: tuple[float, float, float],
) -> dict[str, tuple[float, float, float]]:
    """Incumbents irrelevantes MUY lejos, para que solo compitan los declarados en el test."""
    valores = {e: (999.0, 9.0, 999.0) for e in _RULE.incumbents}
    valores.update(explicitos)
    return valores


def test_regla_declarada_en_la_politica():
    assert _RULE.challenger_min_improvement_pct == 5.0 and _RULE.band_pct == 5.0
    assert _RULE.tie_break == ("mase", "rmse", "cost", "engine")
    assert len(_RULE.incumbents) == 7 and len(_RULE.challengers) == 2
    assert _RULE.cost["seasonal_mean_5y"] < _RULE.cost["ets_add_damped_log1p"]
    assert _RULE.cost["ets_add_damped_log1p"] < _RULE.cost[_CHALLENGER]


def test_challenger_con_499_por_ciento_no_entra():
    valores = _todos_los_incumbents(100.0)
    valores[_INCUMBENT] = (100.0, 1.0, 10.0)
    valores[_CHALLENGER] = (95.01, 0.1, 1.0)  # mejora 4.99% → NO abre el tier
    out = selection.select_for_series(_rows(valores), _RULE)
    assert out["challenger_improvement_pct"] == pytest.approx(4.99)
    assert out["tier"] == "incumbent" and out["selected_engine"] in _RULE.incumbents


def test_challenger_con_500_por_ciento_exacto_si_entra():
    valores = _todos_los_incumbents(100.0)
    valores[_CHALLENGER] = (95.0, 0.1, 1.0)  # mejora exactamente 5.00% → abre el tier
    out = selection.select_for_series(_rows(valores), _RULE)
    assert out["challenger_improvement_pct"] == pytest.approx(5.0)
    assert out["tier"] == "challenger" and out["selected_engine"] == _CHALLENGER


def test_abierto_el_tier_solo_compiten_challengers():
    valores = _todos_los_incumbents(100.0)
    valores["prophet_count_log1p"] = (80.0, 0.5, 5.0)
    valores["prophet_rate_log1p"] = (81.0, 0.9, 9.0)
    out = selection.select_for_series(_rows(valores), _RULE)
    # banda = 80 * 1.05 = 84 → los dos Prophet; ningún incumbent puede colarse.
    assert out["band_engines"] == "prophet_count_log1p|prophet_rate_log1p"
    assert out["selected_engine"] == "prophet_count_log1p"  # menor MASE


def test_banda_de_5_por_ciento_y_desempate_por_mase():
    valores = _incumbentes(
        seasonal_mean_5y=(100.0, 0.9, 10.0),  # el mejor sMAPE
        ets_add_damped_log1p=(104.9, 0.4, 10.0),  # dentro de la banda, mejor MASE
        ridge_harmonic_log1p=(105.1, 0.1, 1.0),  # FUERA de la banda pese a su MASE
    )
    out = selection.select_for_series(_rows(valores), _RULE)
    assert out["band_size"] == 2 and out["selected_engine"] == "ets_add_damped_log1p"
    assert out["band_engines"] == "ets_add_damped_log1p|seasonal_mean_5y"


def test_desempate_por_rmse_y_luego_costo():
    valores = _incumbentes(
        seasonal_mean_5y=(100.0, 0.5, 12.0),
        ets_add_damped_log1p=(100.0, 0.5, 11.0),  # mismo MASE, mejor RMSE
    )
    assert selection.select_for_series(_rows(valores), _RULE)["selected_engine"] == (
        "ets_add_damped_log1p"
    )
    valores["seasonal_mean_5y"] = (100.0, 0.5, 11.0)  # empate total → gana el más barato
    assert selection.select_for_series(_rows(valores), _RULE)["selected_engine"] == (
        "seasonal_mean_5y"
    )


def test_metrica_degenerada_nunca_gana_el_desempate():
    valores = _incumbentes(
        seasonal_mean_5y=(100.0, float("nan"), 10.0),  # MASE no calculable
        ets_add_damped_log1p=(100.0, 2.0, 10.0),
    )
    out = selection.select_for_series(_rows(valores), _RULE)
    assert out["selected_engine"] == "ets_add_damped_log1p"


def test_challenger_ausente_no_rompe_la_seleccion():
    out = selection.select_for_series(_rows(_todos_los_incumbents(50.0)), _RULE)
    assert out["tier"] == "incumbent" and out["best_challenger"] == ""
    assert out["challenger_improvement_pct"] == 0.0


def test_incumbent_faltante_falla_cerrado():
    valores = _todos_los_incumbents(100.0)
    del valores["ridge_harmonic_log1p"]
    with pytest.raises(selection.SelectionError, match="faltan incumbents"):
        selection.select_for_series(_rows(valores), _RULE)


def test_agregado_ignora_folds_que_no_son_development():
    filas = []
    for split, smape in (("development", 10.0), ("test", 99.0), ("stress", 99.0)):
        for fold in ("a", "b"):
            filas.append(
                {
                    "geography_level": "estado",
                    "geography_id": "05",
                    "sex": "hombres",
                    ct.COL_ENGINE: _INCUMBENT,
                    ct.COL_SPLIT: split,
                    ct.COL_FOLD: fold,
                    ct.COL_SMAPE: smape,
                    ct.COL_MASE: 1.0,
                    ct.COL_RMSE: 1.0,
                }
            )
    agg = selection.aggregate_metrics(pd.DataFrame(filas), _RULE)
    assert len(agg) == 1 and agg[ct.COL_SMAPE].iloc[0] == 10.0  # 2025/2020 NO influyen


def test_agregado_solo_toma_las_64_bases():
    filas = [
        {
            "geography_level": nivel,
            "geography_id": geo,
            "sex": sexo,
            ct.COL_ENGINE: _INCUMBENT,
            ct.COL_SPLIT: "development",
            ct.COL_FOLD: "a",
            ct.COL_SMAPE: 1.0,
            ct.COL_MASE: 1.0,
            ct.COL_RMSE: 1.0,
        }
        for nivel, geo, sexo in (
            ("estado", "05", "hombres"),
            ("estado", "05", "general"),  # derivado: NO se elige motor
            ("region", "norte", "hombres"),
            ("nacional", "mx", "general"),
        )
    ]
    agg = selection.aggregate_metrics(pd.DataFrame(filas), _RULE)
    assert len(agg) == 1 and agg["sex"].iloc[0] == "hombres"


def _selection_frame(engine: str = _INCUMBENT) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"geography_id": f"{i:02d}", "sex": sexo, "selected_engine": engine}
            for i in range(1, 33)
            for sexo in ("hombres", "mujeres")
        ]
    )


def test_selection_digest_cambia_con_el_mapa_y_con_la_regla():
    prov = {"benchmark_run_id": "r1"}
    base = selection.selection_digest(_RULE, prov, _selection_frame())
    assert base == selection.selection_digest(_RULE, prov, _selection_frame())
    assert base != selection.selection_digest(
        _RULE, {"benchmark_run_id": "r2"}, _selection_frame()
    )
    otro = _selection_frame()
    otro.loc[0, "selected_engine"] = "ets_add_damped_log1p"
    assert base != selection.selection_digest(_RULE, prov, otro)
    dura = selection.SelectionRule.from_policy(load_policy("rolling_cv_v1"))
    dura = selection.SelectionRule(**{**dura.__dict__, "challenger_min_improvement_pct": 10.0})
    assert base != selection.selection_digest(dura, prov, _selection_frame())


def test_carga_congelada_rechaza_artefactos_alterados(tmp_path):
    sel = _selection_frame()
    arts, _ = selection.write_selection(
        tmp_path,
        sel,
        pd.DataFrame([{"engine": "portfolio"}]),
        "# reporte\n",
        {"selection_digest": "x"},
    )
    cargada, manifest = selection.load_frozen_selection(tmp_path)
    assert len(cargada) == 64 and manifest["selection_digest"] == "x"
    assert len(arts) == 4

    (tmp_path / "selection.csv").write_text("geography_id,sex,selected_engine\n", encoding="utf-8")
    with pytest.raises(selection.SelectionError, match="alterado"):
        selection.load_frozen_selection(tmp_path)


def test_carga_congelada_exige_manifiesto(tmp_path):
    with pytest.raises(selection.SelectionError, match="no hay selection_manifest"):
        selection.load_frozen_selection(tmp_path)
    (tmp_path / "selection_manifest.json").write_text(json.dumps({"schema": "otro"}))
    with pytest.raises(selection.SelectionError, match="schema"):
        selection.load_frozen_selection(tmp_path)
