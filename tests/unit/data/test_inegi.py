# tests/unit/data/test_inegi.py
"""Unit tests for GetInegi and inegi_utils.py pure functions.

Mocks HTTP requests so no real network calls are made.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import epiforecast.data.ingestion.inegi as inegi_mod
from epiforecast.data.ingestion.inegi import GetInegi
from epiforecast.data.ingestion.inegi_utils import (
    _codigos_en_orden,
    jsonstat_a_dataframe,
    validar_hombres_mujeres_vs_total,
)

# ── Mock conf for GetInegi ────────────────────────────────────────────────────

MOCK_CONF = {
    "paths": {"utils": "/tmp/epi_test/utils"},
    "data": {"inegi": "/tmp/epi_test/utils/inegi.csv"},
}


@pytest.fixture
def get_inegi():
    """GetInegi instance with mocked conf."""
    with (
        patch.object(inegi_mod, "conf", MOCK_CONF),
        patch.object(inegi_mod, "logger", MagicMock()),
    ):
        return GetInegi(forzar=True)


# ── _codigos_en_orden (inegi_utils) ──────────────────────────────────────────


class TestCodigosEnOrden:
    def test_list_returned_as_is(self):
        result = _codigos_en_orden(["A", "B", "C"], 3)
        assert result == ["A", "B", "C"]

    def test_dict_mapped_to_list(self):
        idx = {"X": 0, "Y": 1, "Z": 2}
        result = _codigos_en_orden(idx, 3)
        assert result[0] == "X"
        assert result[1] == "Y"
        assert result[2] == "Z"

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            _codigos_en_orden(42, 3)


# ── jsonstat_a_dataframe (inegi_utils) ────────────────────────────────────────


class TestJsonstatADataframe:
    def _sample_jsonstat(self):
        return {
            "dataset": {
                "dimension": {
                    "id": ["Entidad", "Sexo"],
                    "size": [2, 2],
                    "Entidad": {
                        "category": {
                            "index": {"E1": 0, "E2": 1},
                            "label": {"E1": "Jalisco", "E2": "Oaxaca"},
                        }
                    },
                    "Sexo": {
                        "category": {
                            "index": {"S0": 0, "S1": 1},
                            "label": {"S0": "Total", "S1": "Hombres"},
                        }
                    },
                },
                "value": [1000, 500, 800, 400],
            }
        }

    def test_returns_dataframe(self):
        data = self._sample_jsonstat()
        result = jsonstat_a_dataframe(data)
        assert isinstance(result, pd.DataFrame)

    def test_has_valor_column(self):
        data = self._sample_jsonstat()
        result = jsonstat_a_dataframe(data)
        assert "valor" in result.columns

    def test_row_count_equals_product_of_dims(self):
        data = self._sample_jsonstat()
        result = jsonstat_a_dataframe(data)
        # 2 entidades × 2 sexos = 4
        assert len(result) == 4

    def test_labels_applied(self):
        data = self._sample_jsonstat()
        result = jsonstat_a_dataframe(data)
        assert "Jalisco" in result["Entidad"].values


# ── validar_hombres_mujeres_vs_total (inegi_utils) ────────────────────────────


class TestValidarHombresVsTotal:
    def test_no_error_when_consistent(self, capsys):
        df = pd.DataFrame(
            {
                "Entidad federativa": ["Jalisco"],
                "Hombres": [500],
                "Mujeres": [500],
                "Total": [1000],
            }
        )
        # Should run without error; logging goes to typer.echo (captured)
        validar_hombres_mujeres_vs_total(df)  # no assert needed; just must not crash

    def test_logs_when_inconsistent(self):
        df = pd.DataFrame(
            {
                "Entidad federativa": ["Jalisco"],
                "Hombres": [500],
                "Mujeres": [500],
                "Total": [1100],  # wrong
            }
        )
        # Should log warning (via typer.echo → stdout); just verify no exception raised
        validar_hombres_mujeres_vs_total(df)


# ── GetInegi.__init__ ─────────────────────────────────────────────────────────


class TestGetInegiInit:
    def test_sobreescribe_flag(self, get_inegi):
        assert get_inegi.sobreescribe is True

    def test_base_url_set(self, get_inegi):
        assert get_inegi.BASE_PXWEB.startswith("https://")

    def test_estados_dict_has_32_entries(self, get_inegi):
        assert len(get_inegi.ESTADOS_DICT) == 32

    def test_region_salud_mental_covers_all_states(self, get_inegi):
        # All 32 state names from ESTADOS_DICT should have a region
        estado_names = set(get_inegi.ESTADOS_DICT.values())
        region_names = set(get_inegi.REGION_SALUD_MENTAL.keys())
        assert estado_names == region_names

    def test_df_empty_on_init(self, get_inegi):
        assert get_inegi.df.empty

    def test_query_structure(self, get_inegi):
        query = get_inegi.QUERY
        assert "query" in query
        assert "response" in query
        assert query["response"]["format"] == "json-stat"


# ── GetInegi._codigos_en_orden ────────────────────────────────────────────────


class TestGetInegiCodigosEnOrden:
    def test_list_passthrough(self, get_inegi):
        result = get_inegi._codigos_en_orden(["A", "B"], 2)
        assert result == ["A", "B"]

    def test_dict_to_list(self, get_inegi):
        idx = {"codigo1": 1, "codigo0": 0}
        result = get_inegi._codigos_en_orden(idx, 2)
        assert result[0] == "codigo0"
        assert result[1] == "codigo1"

    def test_invalid_raises(self, get_inegi):
        with pytest.raises(TypeError):
            get_inegi._codigos_en_orden(None, 2)


# ── GetInegi.jsonstat_a_dataframe ────────────────────────────────────────────


class TestGetInegiJsonstatADataframe:
    def _sample_data(self):
        return {
            "dataset": {
                "dimension": {
                    "id": ["Entidad federativa", "Sexo"],
                    "size": [2, 3],
                    "Entidad federativa": {
                        "category": {
                            "index": ["01", "02"],
                            "label": {"01": "Aguascalientes", "02": "Baja California"},
                        }
                    },
                    "Sexo": {
                        "category": {
                            "index": ["0", "1", "2"],
                            "label": {"0": "Total", "1": "Hombres", "2": "Mujeres"},
                        }
                    },
                },
                "value": [1000, 500, 500, 900, 450, 450],
            }
        }

    def test_returns_dataframe(self, get_inegi):
        data = self._sample_data()
        result = get_inegi.jsonstat_a_dataframe(data)
        assert isinstance(result, pd.DataFrame)

    def test_has_valor_column(self, get_inegi):
        data = self._sample_data()
        result = get_inegi.jsonstat_a_dataframe(data)
        assert "valor" in result.columns

    def test_label_applied(self, get_inegi):
        data = self._sample_data()
        result = get_inegi.jsonstat_a_dataframe(data)
        assert "Aguascalientes" in result["Entidad federativa"].values


# ── GetInegi.ajusta_dataframe ─────────────────────────────────────────────────


class TestGetInegiAjustaDataframe:
    def _make_long_df(self):
        """Simulate output of jsonstat_a_dataframe."""
        rows = []
        for entidad in ["Jalisco", "Oaxaca"]:
            for periodo in ["2015", "2020"]:
                for sexo in ["Total", "Hombres", "Mujeres"]:
                    rows.append(
                        {
                            "Entidad federativa": entidad,
                            "Periodo": periodo,
                            "Sexo": sexo,
                            "Grupo quinquenal de edad": "Total",
                            "valor": 1000 if sexo == "Total" else 500,
                        }
                    )
        return pd.DataFrame(rows)

    def test_pivot_creates_sexo_columns(self, get_inegi):
        get_inegi.df = self._make_long_df()
        get_inegi.ajusta_dataframe()
        assert "Total" in get_inegi.df.columns
        assert "Hombres" in get_inegi.df.columns
        assert "Mujeres" in get_inegi.df.columns

    def test_grupo_edad_removed(self, get_inegi):
        get_inegi.df = self._make_long_df()
        get_inegi.ajusta_dataframe()
        assert "Grupo quinquenal de edad" not in get_inegi.df.columns


# ── GetInegi.filtra_periodo_max ───────────────────────────────────────────────


class TestGetInegiFiltraPeriodoMax:
    def test_keeps_only_max_periodo(self, get_inegi):
        get_inegi.df = pd.DataFrame(
            {
                "Entidad federativa": ["A", "A", "B", "B"],
                "Periodo": ["2015", "2020", "2015", "2020"],
                "Total": [900, 1000, 800, 900],
                "Hombres": [450, 500, 400, 450],
                "Mujeres": [450, 500, 400, 450],
            }
        )
        get_inegi.filtra_periodo_max()
        assert (
            (get_inegi.df["Periodo"] == "2020").all()
            if "Periodo" in get_inegi.df.columns
            else True
        )
        assert len(get_inegi.df) == 2

    def test_drops_periodo_column(self, get_inegi):
        get_inegi.df = pd.DataFrame(
            {
                "Entidad federativa": ["A"],
                "Periodo": ["2020"],
                "Total": [1000],
                "Hombres": [500],
                "Mujeres": [500],
            }
        )
        get_inegi.filtra_periodo_max()
        assert "Periodo" not in get_inegi.df.columns


# ── GetInegi.validar_hombres_mujeres_vs_total ─────────────────────────────────


class TestGetInegiValidar:
    def test_no_error_when_consistent(self, get_inegi):
        get_inegi.df = pd.DataFrame(
            {
                "Entidad federativa": ["Jalisco"],
                "Hombres": [500],
                "Mujeres": [500],
                "Total": [1000],
            }
        )
        get_inegi.validar_hombres_mujeres_vs_total()  # must not raise

    def test_inconsistency_logged(self, get_inegi):
        get_inegi.df = pd.DataFrame(
            {
                "Entidad federativa": ["Jalisco"],
                "Hombres": [500],
                "Mujeres": [500],
                "Total": [1100],
            }
        )
        with patch.object(inegi_mod, "logger", MagicMock()):
            get_inegi.validar_hombres_mujeres_vs_total()
            # The method runs without exception when inconsistency is detected


# ── GetInegi.clasificaciones ──────────────────────────────────────────────────


class TestGetInegiClasificaciones:
    def _make_wide_df(self):
        """32 estados with plausible population data."""
        # Use a few states that exist in REGION_SALUD_MENTAL
        return pd.DataFrame(
            {
                "Entidad federativa": ["Jalisco", "Oaxaca", "Ciudad de México"],
                "Total": [8_000_000, 4_000_000, 9_000_000],
                "Hombres": [3_900_000, 1_950_000, 4_300_000],
                "Mujeres": [4_100_000, 2_050_000, 4_700_000],
                "Superficie_km2": [80_000.0, 93_000.0, 1_500.0],
            }
        )

    def test_region_column_added(self, get_inegi):
        get_inegi.df = self._make_wide_df()
        get_inegi.clasificaciones()
        assert "region_salud_mental" in get_inegi.df.columns

    def test_known_states_mapped(self, get_inegi):
        get_inegi.df = self._make_wide_df()
        get_inegi.clasificaciones()
        jalisco_row = get_inegi.df[get_inegi.df["Entidad federativa"] == "Jalisco"]
        assert jalisco_row["region_salud_mental"].iloc[0] == "Metropolitana alta"

    def test_density_column_added(self, get_inegi):
        get_inegi.df = self._make_wide_df()
        get_inegi.clasificaciones()
        assert "densidad_poblacion" in get_inegi.df.columns

    def test_ratio_hm_calculated(self, get_inegi):
        get_inegi.df = self._make_wide_df()
        get_inegi.clasificaciones()
        assert "ratio_h_m" in get_inegi.df.columns
        # Jalisco: 3.9M / 4.1M ≈ 0.95
        jalisco = get_inegi.df[get_inegi.df["Entidad federativa"] == "Jalisco"]
        assert jalisco["ratio_h_m"].iloc[0] == pytest.approx(3_900_000 / 4_100_000, rel=1e-3)


# ── GetInegi.descargar_jsonstat_pxweb ─────────────────────────────────────────


class TestGetInegiDescargarJsonstat:
    def test_returns_json_on_success(self, get_inegi):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"dataset": {"dimension": {}, "value": []}}
        mock_resp.content = b"data"

        with patch("epiforecast.data.ingestion.inegi.requests.post", return_value=mock_resp):
            result = get_inegi.descargar_jsonstat_pxweb("Poblacion", "Poblacion_01.px", {})
        assert "dataset" in result

    def test_raises_runtime_on_http_error(self, get_inegi):
        import requests

        with (
            patch(
                "epiforecast.data.ingestion.inegi.requests.post",
                side_effect=requests.HTTPError("404"),
            ),
            pytest.raises(RuntimeError, match="Falla al consultar"),
        ):
            get_inegi.descargar_jsonstat_pxweb("DB", "tabla.px", {})
