"""F2/C5.3-C5.4 — contrato de modelo final: envelope sellado y round-trip exacto por adapter."""

from __future__ import annotations

import numpy as np
import pytest

from epiforecast.data.epi_calendar import shift
from epiforecast.data.epi_dataset_spec import SeriesKey
from epiforecast.runner import contracts as ct
from epiforecast.runner import final_models as fm
from epiforecast.runner import forecasting
from epiforecast.runner import orchestrator as orch
from epiforecast.runner.engines import ets, prophet_engine, ridge_harmonic, seasonal_naive
from epiforecast.runner.engines.seasonal_window import SeasonalWindowAdapter

_DISEASE = "obesidad"
_N_TRAIN = 653  # 2014-W01..2026-W26
_HORIZON = 6
_EXPOSICION = 500_000.0


def _periods(n: int, start: tuple[int, int] = (2014, 1)) -> list[tuple[int, int]]:
    out = [start]
    for _ in range(n - 1):
        out.append(shift(out[-1][0], out[-1][1], 1))
    return out


def _window(engine: str, transform=ct.identity_transform) -> fm.FinalWindow:
    periods = _periods(_N_TRAIN)
    days = np.arange(len(periods), dtype=float)
    valores = 100.0 + 20.0 * np.sin(2 * np.pi * days / 52.0) + 0.02 * days
    spec = ct.TrainingSpec(
        key=SeriesKey(_DISEASE, "estado", "05", "hombres"),
        engine=engine,
        dataset_digest="d" * 64,
        policy_name="rolling_cv_v1",
        policy_digest="p" * 64,
        fold_id=fm.FINAL_FOLD_ID,
        seed=20260724,
        horizon=_HORIZON,
        transform=transform(_DISEASE, engine),
    )
    return fm.FinalWindow(
        spec,
        {p: float(v) for p, v in zip(periods, valores, strict=True)},
        {p: _EXPOSICION for p in periods},
    )


def _request(window: fm.FinalWindow) -> fm.ForecastRequest:
    futuros = tuple(forecasting.horizon_periods(max(window.train), _HORIZON))
    return fm.ForecastRequest(window.spec.transform, futuros, {p: _EXPOSICION for p in futuros})


def _round_trip(tmp_path, window, fit_fn, forecast_fn) -> tuple[dict, dict]:
    """Ajusta → serializa → recarga verificando digests → vuelve a pronosticar."""
    state = fit_fn(window)
    request = _request(window)
    directo = forecast_fn(state, request)
    fm.write_model(tmp_path / "models" / window.spec.engine, window, state, {"p": 1}, {"v": "1"})
    entry_dir = tmp_path / "models" / window.spec.engine
    stem = fm.model_stem(window.spec.key)
    fm.write_index(
        tmp_path,
        window.spec.engine,
        [
            {
                "geography_id": window.spec.key.geography_id,
                "sex": window.spec.key.sex,
                "envelope_path": f"{stem}.envelope.json",
                "envelope_digest": __import__("hashlib")
                .sha256((entry_dir / f"{stem}.envelope.json").read_bytes())
                .hexdigest(),
            }
        ],
        {},
    )
    ((envelope, cargado),) = fm.load_models(tmp_path, window.spec.engine)
    recargado = forecast_fn(cargado, request)
    return directo, recargado, envelope


def test_estado_declara_su_formato():
    with pytest.raises(fm.FinalModelError, match="no soportado"):
        fm.FinalState(fmt="pickle_libre", data=b"x")
    with pytest.raises(fm.FinalModelError, match="texto"):
        fm.FinalState(fmt=fm.FMT_JSON, data=b"x")
    with pytest.raises(fm.FinalModelError, match="no concuerdan"):
        fm.FinalState(fmt=fm.FMT_STATSMODELS_PICKLE, text="x")
    with pytest.raises(fm.FinalModelError, match="bytes"):
        fm.FinalState(fmt=fm.FMT_STATSMODELS_PICKLE)


def test_envelope_lleva_identidad_explicita(tmp_path):
    window = _window(seasonal_naive.ENGINE)
    _, _, envelope = _round_trip(
        tmp_path, window, seasonal_naive.fit_final, seasonal_naive.forecast_final
    )
    assert envelope["series_key"] == {
        "geography_level": "estado",
        "geography_id": "05",
        "sex": "hombres",
        "frequency": "epi_week",
    }
    assert envelope["final_refit"] is True and envelope["n_train"] == _N_TRAIN
    assert envelope["train_start"] == [2014, 1] and envelope["train_end"] == [2026, 26]
    assert envelope["engine"] == seasonal_naive.ENGINE and envelope["state_digest"]


def test_estado_alterado_invalida_la_carga(tmp_path):
    window = _window(seasonal_naive.ENGINE)
    _round_trip(tmp_path, window, seasonal_naive.fit_final, seasonal_naive.forecast_final)
    estado = tmp_path / "models" / seasonal_naive.ENGINE / "05_hombres.state.json"
    estado.write_text('{"history": []}', encoding="utf-8")
    with pytest.raises(fm.FinalModelError, match="alterado"):
        fm.load_models(tmp_path, seasonal_naive.ENGINE)


def test_round_trip_seasonal_naive(tmp_path):
    window = _window(seasonal_naive.ENGINE)
    directo, recargado, _ = _round_trip(
        tmp_path, window, seasonal_naive.fit_final, seasonal_naive.forecast_final
    )
    assert directo == recargado and len(directo) == _HORIZON


def test_round_trip_ventana_estacional(tmp_path):
    adapter = SeasonalWindowAdapter("seasonal_mean_5y", 5, "mean", 1, "seasonal_naive_lag52")
    window = _window("seasonal_mean_5y")
    directo, recargado, _ = _round_trip(
        tmp_path, window, adapter.fit_final, adapter.forecast_final
    )
    assert directo == recargado and len(directo) == _HORIZON


def test_round_trip_ridge(tmp_path):
    cfg = ridge_harmonic.load_ridge_config()
    window = _window(ridge_harmonic.ENGINE, ct.log1p_transform)
    directo, recargado, envelope = _round_trip(
        tmp_path, window, lambda w: ridge_harmonic.fit_final(cfg, w), ridge_harmonic.forecast_final
    )
    assert directo == recargado
    assert envelope["config"]["fourier_order"] in (2, 4, 6)


def test_round_trip_ets(tmp_path):
    cfg = ets.load_ets_config()
    window = _window(ets.ENGINE, ct.log1p_transform)
    directo, recargado, envelope = _round_trip(
        tmp_path, window, lambda w: ets.fit_final(cfg, w), ets.forecast_final
    )
    assert directo == recargado
    assert envelope["state_format"] == fm.FMT_STATSMODELS_PICKLE


def test_round_trip_prophet_tasa(tmp_path):
    cfg = prophet_engine.load_prophet_config()
    frozen = cfg["engines"]["prophet_rate_log1p"]["frozen"]
    window = _window("prophet_rate_log1p", ct.rate_log1p_transform)
    directo, recargado, envelope = _round_trip(
        tmp_path,
        window,
        lambda w: prophet_engine.fit_final(cfg["common"], frozen, w),
        prophet_engine.forecast_final,
    )
    assert directo == recargado
    assert envelope["state_format"] == fm.FMT_PROPHET_JSON
    assert envelope["transform"]["forward_steps"] == ["rate_per_exposure", "log1p"]


def test_horizonte_arranca_una_semana_despues_del_origen():
    periodos = forecasting.horizon_periods((2026, 26), 52)
    assert periodos[0] == (2026, 27) and periodos[-1] == (2027, 26) and len(periodos) == 52
    for prev, cur in zip(periodos, periodos[1:], strict=False):
        assert shift(prev[0], prev[1], 1) == cur  # consecutivos en el calendario MMWR


def test_exposicion_futura_obligatoria_para_tasa():
    request = fm.ForecastRequest(
        ct.rate_log1p_transform(_DISEASE, "prophet_rate_log1p"), ((2026, 27),), {}
    )
    with pytest.raises(fm.FinalModelError, match="exposición futura ausente"):
        request.exposure_array()


def test_refit_y_forecast_exigen_su_run_gobernante():
    with pytest.raises(orch.RunnerError, match="--acceptance-run"):
        orch.run_command("Obesidad", "refit")
    with pytest.raises(orch.RunnerError, match="--refit-run"):
        orch.run_command("Obesidad", "forecast", horizon=52)


def test_refit_y_forecast_rechazan_motores_manuales():
    with pytest.raises(orch.RunnerError, match="no de --engines"):
        orch.run_command("Obesidad", "refit", acceptance_run_id="x", engines=["seasonal_mean_5y"])
