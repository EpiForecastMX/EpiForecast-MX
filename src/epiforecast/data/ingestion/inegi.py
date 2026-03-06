"""INEGI API client: demographic and population data ingestion."""

# src/datos/get_inegi.py
from typing import Any

import pandas as pd
import requests

from epiforecast.data.ingestion.inegi_constants import ESTADOS_DICT, REGION_SALUD_MENTAL
from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger


class GetInegi:
    def __init__(self, forzar: bool = False, config: dict[str, Any] | None = None):
        """Inicializa el cliente INEGI con URLs de API y catálogos de estados.

        Args:
            forzar: Si True, regenera el archivo aunque ya exista.
            config: Dict de configuración (default: conf global de YAML).
        """
        _conf = config if config is not None else conf
        self.sobreescribe = forzar
        self.utils_path = _conf["paths"]["utils"]
        self.inegi_path = _conf["data"]["inegi"]

        self.BASE_PXWEB = "https://www.inegi.org.mx/app/tabulados/pxwebv2/api/v1/es"
        self.DB = "Poblacion"
        self.TABLA_PX = "Poblacion_01.px"

        self.df = pd.DataFrame()
        self.df_superficie = pd.DataFrame()

        self.QUERY = {
            "query": [
                # 0 = Total nacional, 1..32 = estados
                {
                    "code": "Entidad federativa",
                    "selection": {"filter": "item", "values": [str(i) for i in range(1, 33)]},
                },
                {"code": "Periodo", "selection": {"filter": "item", "values": ["4", "5", "3"]}},
                {"code": "Sexo", "selection": {"filter": "item", "values": ["0", "1", "2"]}},
            ],
            "response": {"format": "json-stat"},
        }

        self.URL_SUPERFICIE = (
            "https://www.inegi.org.mx/app/api/indicadores/interna_v1_3/API.svc/"
            "ValorIndicador/1001000001/"
            "01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32/"
            "null/es/null/null/3/n/0/1/null/null/1/6/json/"
            "563cbaa8-58bb-fef8-6763-1f1dae318f99"
        )

        self.ESTADOS_DICT = ESTADOS_DICT
        self.REGION_SALUD_MENTAL = REGION_SALUD_MENTAL

    # ========= Descarga en memoria =========

    def descargar_jsonstat_pxweb(
        self, db: str, tabla_px: str, consulta: dict[str, Any], timeout: int = 60
    ) -> dict[str, Any]:
        """Delegate to inegi_utils.descargar_jsonstat_pxweb with error handling."""
        from epiforecast.data.ingestion.inegi_utils import (
            descargar_jsonstat_pxweb as _descargar,
        )

        url = f"{self.BASE_PXWEB.rstrip('/')}/{db.strip('/')}/{tabla_px.lstrip('/')}"
        logger.info(
            "PxWeb POST | url={} | db={} | tabla={} | timeout={}s", url, db, tabla_px, timeout
        )
        try:
            data = _descargar(db, tabla_px, consulta, timeout)
            logger.info("PxWeb OK")
            return data
        except requests.RequestException as ex:
            logger.exception("PxWeb error HTTP/red: {}", ex)
            raise RuntimeError(f"Falla al consultar PxWeb: {ex}") from ex
        except ValueError as ex:
            logger.exception("PxWeb respuesta no-JSON: {}", ex)
            raise RuntimeError("La respuesta de PxWeb no es JSON válido.") from ex

    # ========= Conversión JSON-STAT v2 -> DataFrame =========

    def _codigos_en_orden(self, indice_categoria: Any, n: int) -> list[Any]:
        """Delegate to inegi_utils._codigos_en_orden."""
        from epiforecast.data.ingestion.inegi_utils import _codigos_en_orden

        return _codigos_en_orden(indice_categoria, n)

    def jsonstat_a_dataframe(self, data: dict[str, Any]) -> pd.DataFrame:
        """Delegate to inegi_utils.jsonstat_a_dataframe."""
        from epiforecast.data.ingestion.inegi_utils import jsonstat_a_dataframe

        logger.info("Convirtiendo JSON-stat a DataFrame...")
        df = jsonstat_a_dataframe(data)
        logger.info("JSON-stat convertido | filas={}", len(df))
        return df

    def ajusta_dataframe(self) -> None:
        """Pivotea y filtra el DataFrame: elimina grupos de edad, unstacks por sexo."""

        self.df["valor"] = pd.to_numeric(self.df["valor"], errors="coerce")

        if "Grupo quinquenal de edad" not in self.df.columns:
            self.df["Grupo quinquenal de edad"] = "Total"

        self.df = self.df[self.df["Grupo quinquenal de edad"] == "Total"].copy()
        self.df = self.df.drop(columns=["Grupo quinquenal de edad"])
        self.df = self.df.set_index(["Entidad federativa", "Periodo", "Sexo"])
        self.df = self.df["valor"].unstack("Sexo").reset_index()

        logger.debug(
            "DataFrame ajustado | filas={} | columnas={}", len(self.df), list(self.df.columns)
        )

    def validar_hombres_mujeres_vs_total(self) -> None:
        """Delegate to inegi_utils.validar_hombres_mujeres_vs_total."""
        from epiforecast.data.ingestion.inegi_utils import validar_hombres_mujeres_vs_total

        validar_hombres_mujeres_vs_total(self.df)
        logger.debug("Validación OK: Hombres + Mujeres = Total en todos los registros.")

    def filtra_periodo_max(self) -> None:
        """Filtra el DataFrame para conservar solo el periodo censal más reciente."""

        periodo_max = self.df["Periodo"].max()
        self.df = (
            self.df[self.df["Periodo"] == periodo_max]
            .copy()
            .reset_index(drop=True)
            .drop(columns=["Periodo"])
        )
        self.df.columns.name = None
        logger.info(
            "Periodo máximo seleccionado: {} | filas resultantes: {}", periodo_max, len(self.df)
        )

    def get_superficie_estados(self) -> None:
        """Delegate HTTP + DataFrame creation to inegi_utils; handle merge locally."""
        from epiforecast.data.ingestion.inegi_utils import get_superficie_estados as _get_sup

        logger.info("Descargando superficies estatales desde API INEGI...")
        try:
            self.df_superficie = _get_sup(self.URL_SUPERFICIE, self.ESTADOS_DICT)
        except requests.RequestException as ex:
            logger.exception("Error al descargar superficie estatal: {}", ex)
            raise RuntimeError(f"Falla al descargar superficie estatal: {ex}") from ex

        self.df_superficie["Superficie_km2"] = pd.to_numeric(
            self.df_superficie["Superficie_km2"].str.replace(",", "", regex=False),
            errors="coerce",
        )

        self.df = (
            self.df_superficie.merge(self.df, on="Entidad federativa", how="inner")
            .sort_values("Entidad federativa")
            .reset_index(drop=True)
        )

        logger.info("Superficie estatal obtenida | entidades={}", len(self.df_superficie))

    def clasificaciones(self) -> None:
        """Agrega clasificaciones demográficas al DataFrame: región, ratio H/M, tamaño, densidad."""

        self.df["region_salud_mental"] = self.df["Entidad federativa"].map(
            self.REGION_SALUD_MENTAL
        )
        faltantes = self.df[self.df["region_salud_mental"].isna()]["Entidad federativa"].unique()
        if len(faltantes) > 0:
            logger.warning(
                "Estados sin región de salud mental asignada: {}", ", ".join(sorted(faltantes))
            )

        self.df["ratio_h_m"] = self.df["Hombres"] / self.df["Mujeres"]
        self.df["ratio_h_m_cat"] = pd.cut(
            self.df["ratio_h_m"],
            bins=[-float("inf"), 0.99, 1.01, float("inf")],
            labels=["Mayormente mujeres", "Balanceado", "Mayormente hombres"],
        )
        self.df["tamano_poblacional_predefinido"] = pd.cut(
            self.df["Total"],
            bins=[0, 1_000_000, 3_000_000, 6_000_000, self.df["Total"].max()],
            labels=["0-1M", "1-3M", "3-6M", "6M+"],
        )
        self.df["tamano_poblacional_grupo_percentil"] = pd.qcut(
            self.df["Total"],
            q=4,
            labels=["Población baja", "Media-baja", "Media-alta", "Alta"],
        )
        self.df["densidad_poblacion"] = self.df["Total"] / self.df["Superficie_km2"]
        self.df["extension_territorial_percentil"] = pd.qcut(
            self.df["Superficie_km2"],
            q=4,
            labels=["Territorio pequeño", "Medio-pequeño", "Medio-grande", "Grande"],
        )
        self.df["densidad_poblacional_percentil"] = pd.qcut(
            self.df["densidad_poblacion"],
            q=4,
            labels=["Baja", "Media-baja", "Media-alta", "Alta"],
        )

        logger.debug(
            "Clasificaciones calculadas | columnas nuevas: region, ratios, tamaños, densidad."
        )

    def run(self) -> None:
        """Pipeline completo INEGI: descarga, transforma, valida, clasifica y guarda CSV."""

        if directory_manager.existe_archivo(self.inegi_path) and not self.sobreescribe:
            logger.info("Archivo INEGI ya existe, omitiendo descarga: {}", self.inegi_path)
            return

        logger.info("Generando archivo INEGI: {}", self.inegi_path)

        data = self.descargar_jsonstat_pxweb(self.DB, self.TABLA_PX, self.QUERY)
        self.df = self.jsonstat_a_dataframe(data)
        self.ajusta_dataframe()
        self.validar_hombres_mujeres_vs_total()
        self.filtra_periodo_max()
        self.get_superficie_estados()
        self.clasificaciones()

        directory_manager.asegurar_ruta(self.utils_path)

        directory_manager.advertir_sobrescritura(self.inegi_path)

        self.df.to_csv(self.inegi_path, index=False, encoding="utf-8")
        logger.success("Archivo INEGI guardado: {}", self.inegi_path)
