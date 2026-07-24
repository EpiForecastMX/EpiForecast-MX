"""F2/C4.2 — tuning genérico: centinelas deterministas y clave de selección declarada."""

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast.data import epi_dataset_spec as spec
from epiforecast.runner import tuning
from epiforecast.runner.policy import load_policy

_FOLD = load_policy("rolling_cv_v1").development_folds()[-1]  # development_2024


def _base_truth(medias: dict[str, dict[str, float]]) -> pd.DataFrame:
    """Serie plana por (estado, sexo) con la media pedida en train y basura en el holdout."""
    filas = []
    for sexo, por_estado in medias.items():
        for cve, media in por_estado.items():
            for year in (2022, 2023):
                for w in range(1, 53):
                    filas.append(
                        {
                            spec.COL_GEO_ID: cve,
                            spec.COL_SEX: sexo,
                            spec.COL_EPI_YEAR: year,
                            spec.COL_EPI_WEEK: w,
                            spec.COL_Y_CASES: media,
                        }
                    )
            for w in range(1, 53):  # holdout 2024: NO debe influir en la elección
                filas.append(
                    {
                        spec.COL_GEO_ID: cve,
                        spec.COL_SEX: sexo,
                        spec.COL_EPI_YEAR: 2024,
                        spec.COL_EPI_WEEK: w,
                        spec.COL_Y_CASES: 10_000.0,
                    }
                )
    return pd.DataFrame(filas)


def test_centinelas_min_mediana_superior_y_max_por_sexo():
    medias = {
        "hombres": {"01": 10.0, "02": 20.0, "03": 30.0, "04": 40.0},
        "mujeres": {"01": 400.0, "02": 300.0, "03": 200.0, "04": 100.0},
    }
    elegidos = tuning.select_sentinels(_base_truth(medias), _FOLD)
    assert [(c[spec.COL_SEX], c["position"], c[spec.COL_GEO_ID]) for c in elegidos] == [
        ("hombres", "min", "01"),
        ("hombres", "median_upper", "03"),  # n=4 → índice 2 = mediana SUPERIOR
        ("hombres", "max", "04"),
        ("mujeres", "min", "04"),
        ("mujeres", "median_upper", "02"),
        ("mujeres", "max", "01"),
    ]


def test_centinelas_no_dependen_del_holdout():
    medias = {
        "hombres": {"01": 10.0, "02": 20.0, "03": 30.0},
        "mujeres": {"01": 10.0, "02": 20.0, "03": 30.0},
    }
    base = _base_truth(medias)
    alterado = base.copy()
    alterado.loc[alterado[spec.COL_EPI_YEAR] == 2024, spec.COL_Y_CASES] = 1.0
    assert tuning.select_sentinels(base, _FOLD) == tuning.select_sentinels(alterado, _FOLD)


def test_centinelas_desempatan_por_geography_id():
    empatadas = {"09": 5.0, "02": 5.0, "31": 5.0}
    elegidos = tuning.select_sentinels(
        _base_truth({"hombres": empatadas, "mujeres": empatadas}), _FOLD
    )
    hombres = [c[spec.COL_GEO_ID] for c in elegidos if c[spec.COL_SEX] == "hombres"]
    assert hombres == ["02", "09", "31"]  # todo empatado → orden estable por geography_id


def test_series_insuficientes_levanta():
    with pytest.raises(tuning.TuningError, match="insuficientes"):
        tuning.select_sentinels(
            _base_truth({"hombres": {"01": 1.0}, "mujeres": {"01": 1.0}}), _FOLD
        )


def _fila(median, mean):
    return {"median_smape": median, "mean_smape": mean}


def test_clave_de_orden_prioriza_mediana_y_luego_media():
    tie = []
    assert tuning._sort_key(_fila(10.0, 99.0), {}, tie) < tuning._sort_key(
        _fila(11.0, 1.0), {}, tie
    )
    assert tuning._sort_key(_fila(10.0, 5.0), {}, tie) < tuning._sort_key(
        _fila(10.0, 6.0), {}, tie
    )


def test_desempate_numerico_y_categorico_declarados():
    tie = [
        {"param": "fourier_order", "order": "asc"},
        {"param": "seasonality_mode", "order": ["additive", "multiplicative"]},
    ]
    empate = _fila(10.0, 10.0)
    menor = tuning._sort_key(empate, {"fourier_order": 5, "seasonality_mode": "additive"}, tie)
    mayor = tuning._sort_key(empate, {"fourier_order": 10, "seasonality_mode": "additive"}, tie)
    aditivo = tuning._sort_key(empate, {"fourier_order": 5, "seasonality_mode": "additive"}, tie)
    multi = tuning._sort_key(
        empate, {"fourier_order": 5, "seasonality_mode": "multiplicative"}, tie
    )
    assert menor < mayor and aditivo < multi


def test_desempate_mal_declarado_levanta():
    empate = _fila(1.0, 1.0)
    with pytest.raises(tuning.TuningError, match="no es un parámetro"):
        tuning._sort_key(empate, {"fourier_order": 5}, [{"param": "ausente", "order": "asc"}])
    with pytest.raises(tuning.TuningError, match="no declarado"):
        tuning._sort_key(empate, {"modo": "x"}, [{"param": "modo", "order": ["a", "b"]}])
    with pytest.raises(tuning.TuningError, match="no soportado"):
        tuning._sort_key(empate, {"k": 1}, [{"param": "k", "order": "raro"}])
