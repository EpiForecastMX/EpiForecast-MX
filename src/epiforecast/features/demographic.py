"""Demographic feature engineering: INEGI population merge and rate normalization."""

# src/modelado/mapea_inegi.py
from typing import Any

import pandas as pd

from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger


class MapeaInegi:
    """Combina datos epidemiológicos con datos demográficos INEGI por entidad federativa."""

    def __init__(self, df: pd.DataFrame, config: dict[str, Any] | None = None):
        """Inicializa con el DataFrame epidemiológico y rutas de configuración.

        Args:
            df: DataFrame con columna ``Entidad`` para el merge con INEGI.
            config: Dict de configuración (default: conf global de YAML).
        """
        _conf = config if config is not None else conf
        self.df = df.copy()
        conf_paths = _conf["data"]
        self.inegi_path = conf_paths["inegi"]
        self.final_path = conf_paths["data_inegi"]
        self.xlsx_path = conf_paths["xlsx_inegi"]
        self.inegi = pd.DataFrame()
        self.df_merge = pd.DataFrame()

    def renombra(self) -> None:
        """Renombra entidades INEGI para alinear con nomenclatura del proyecto."""

        map_entidades = {
            "Coahuila de Zaragoza": "Coahuila",
            "Michoacán de Ocampo": "Michoacán",
            "Veracruz de Ignacio de la Llave": "Veracruz",
        }

        self.inegi = self.inegi.rename(columns={"Entidad federativa": "Entidad"})
        self.inegi["Entidad"] = self.inegi["Entidad"].replace(map_entidades)

    def combina(self) -> None:
        """Ejecuta left join del DataFrame epidemiológico con datos INEGI por Entidad."""

        cols_extra = [c for c in self.inegi.columns if c != "Entidad"]

        self.df_merge = self.df.merge(
            self.inegi[["Entidad"] + cols_extra],
            on="Entidad",
            how="left",
        )

    def run(self) -> None:
        """Pipeline completo: carga INEGI, renombra, combina y guarda CSV + Excel."""

        if not directory_manager.existe_archivo(self.inegi_path):
            raise FileNotFoundError(f"No se pudo localizar el archivo de INEGI: {self.inegi_path}")

        self.inegi = pd.read_csv(self.inegi_path)

        self.renombra()
        self.combina()

        if self.df_merge.empty:
            raise RuntimeError("El merge con INEGI produjo un DataFrame vacío.")

        directory_manager.advertir_sobrescritura(self.final_path)

        self.df_merge.to_csv(self.final_path, index=False)
        logger.success("Archivo CSV guardado: {}", self.final_path)

        self.df_merge.to_excel(self.xlsx_path, sheet_name="data", index=False)
        logger.success("Archivo Excel guardado: {}", self.xlsx_path)
