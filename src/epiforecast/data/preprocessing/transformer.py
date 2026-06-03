"""Data transformation pipeline: feature engineering, outlier correction, and INEGI demographic merge."""

# src/datos/preparacion.py
from collections.abc import Callable
from typing import Any

from loguru import logger
import numpy as np
import pandas as pd

from epiforecast.utils.config import conf


class DataTransformation:
    """Pipeline de transformación de datos: ajuste de semanas, incrementos y outliers."""

    def __init__(self, df: pd.DataFrame, config: dict[str, Any] | None = None):
        """Inicializa el transformador con el DataFrame preprocesado.

        Args:
            df: DataFrame con columnas Anio, Semana, Entidad, Padecimiento,
                Acumulado_hombres, Acumulado_mujeres.
            config: Dict de configuración (default: conf global de YAML).
        """
        _conf = config if config is not None else conf
        self.df = df.copy()
        self.df_agrupado: pd.DataFrame = pd.DataFrame()
        self.opciones = _conf.get("opciones_FE", [])
        self.regiones = _conf.get("regiones", [])

        self.raw_data_filter = _conf.get("data", {}).get("data_prepare")
        _agrupa = self.get_opcion("agrupa")
        self.agrupamiento = str(_agrupa.get("valor", "")).strip().lower() if _agrupa else ""

    def get_opcion(self, nombre: str) -> dict[str, Any] | None:
        """Busca y retorna una opción de feature engineering por nombre.

        Args:
            nombre: Clave de la opción a buscar en ``opciones_FE``.

        Returns:
            Dict de la opción encontrada, o None si no existe.
        """
        for item in self.opciones:
            if nombre in item:
                return item[nombre]  # type: ignore[no-any-return]
        return None

    def _ajusta_semanas(self) -> None:
        if not self.df["Semana"].between(1, 53).all():
            raise ValueError("Se encontraron semanas fuera del rango")

        filas_semana_1 = self.df["Semana"] == 1
        filas_no_semana_1 = ~filas_semana_1

        logger.debug(f"{filas_semana_1.sum()} registros identificados con semana = 1.")
        filas_semana_53 = self.df["Semana"] == 53
        logger.debug(f"{filas_semana_53.sum()} registros identificados con semana = 53.")

        # Para los que NO son semana 1: restar 1
        self.df.loc[filas_no_semana_1, "Semana"] = self.df.loc[filas_no_semana_1, "Semana"] - 1

        # Preparar el máximo de semana por año
        agg_por_anio = self.df.groupby("Anio", as_index=False).agg(max_semana=("Semana", "max"))

        # Construir mapa: año -> max_semana observado
        mapa_max_semana = dict(zip(agg_por_anio["Anio"], agg_por_anio["max_semana"]))

        # Calcular el año anterior para las filas con semana 1
        anio_prev = self.df.loc[filas_semana_1, "Anio"] - 1

        # Obtener el máximo del año anterior y sumarle +1
        max_global_sem = self.df["Semana"].max()
        max_prev_anio = anio_prev.map(mapa_max_semana)

        # Si el año anterior no existe en los datos (NaN), usar el máximo global
        max_prev_anio = max_prev_anio.fillna(max_global_sem)

        # La nueva semana para las filas de semana 1 será (max_prev_anio + 1)
        nueva_semana_para_sem1 = (max_prev_anio + 1).astype(int)

        # Asignar
        self.df.loc[filas_semana_1, "Anio"] = anio_prev.values
        self.df.loc[filas_semana_1, "Semana"] = nueva_semana_para_sem1.values

        # Ordenar
        self.df = self.df.sort_values(
            by=["Padecimiento", "Anio", "Entidad", "Semana"]
        ).reset_index(drop=True)

        logger.info("Ordenando el dataset.")

    def _prepara_series_tiempo(self) -> None:
        logger.info("Inicializando preparación de series temporales.")

        # El acumulado se reinicia cada año, por lo que el "previo" debe agruparse también
        # por Anio: si no, el incremento de la primera semana presente de un año se calcula
        # contra el acumulado (grande) del año anterior, generando un negativo que
        # `_ajusta_negativos` tendría que parchear con una media móvil (fabricando casos).
        # En series completas (neuro) la regla "Semana 1 = acumulado" de abajo YA cubría la
        # frontera, así que agrupar por Anio da un resultado idéntico; en series parciales
        # (p.ej. Dengue: empieza a mitad de año o tiene huecos) evita el cruce de año.
        grupo = ["Padecimiento", "Entidad", "Anio"]
        self.df["Prev_hombres"] = self.df.groupby(grupo)["Acumulado_hombres"].shift()
        self.df["Prev_mujeres"] = self.df.groupby(grupo)["Acumulado_mujeres"].shift()

        # Calcular incrementos usando el valor anterior
        self.df["Incremento_hombres"] = self.df["Acumulado_hombres"] - self.df["Prev_hombres"]
        self.df["Incremento_mujeres"] = self.df["Acumulado_mujeres"] - self.df["Prev_mujeres"]

        # Regla especial: SOLO la verdadera Semana 1 (acumulado ≈ casos de esa semana) toma
        # el acumulado como incremento. NO se aplica a la primera semana presente de un año
        # que empieza a mitad (p.ej. Dengue 2018 desde W27): ahí el acumulado es la suma de
        # muchas semanas y volcarlo sería un pico falso; esas filas quedan en NaN -> 0 vía
        # `_ajusta_negativos` (no se fabrica el incremento que no se puede medir).
        semana_1 = self.df["Semana"] == 1
        self.df.loc[semana_1, "Incremento_hombres"] = self.df.loc[semana_1, "Acumulado_hombres"]
        self.df.loc[semana_1, "Incremento_mujeres"] = self.df.loc[semana_1, "Acumulado_mujeres"]

        # incluye fecha para poder realizar serie de tiempo
        # Cálculo robusto ISO-8601 (semana 1 inicia el lunes que contiene el primer jueves).
        # Evita bugs en el parseador C-strtime de MacOS/Windows con semanas 53.
        from datetime import date

        fechas_base = pd.to_datetime([date.fromisocalendar(y, 1, 1) for y in self.df["Anio"]])
        self.df["Fecha"] = fechas_base + pd.to_timedelta(self.df["Semana"] - 1, unit="W")

        # Ajusta el año a aquellas fechas de la semana 1 que caen en año anterior
        # filas_anio = (self.df['Semana'] == 1) & (self.df['Fecha'].dt.year < self.df['Anio'])
        # self.df.loc[filas_anio, 'Fecha'] = pd.to_datetime(self.df.loc[filas_anio, 'Anio'].astype(str) + '-01-01')
        # self.df.loc[filas_anio, 'Fecha'] = (pd.to_datetime(self.df.loc[filas_anio, 'Anio'].astype(str) + '-01-01')+ pd.offsets.Week(weekday=0))  # primer lunes

    def _ajusta_incrementos(self) -> None:
        for columna in ["Incremento_hombres", "Incremento_mujeres"]:
            # 1) Identificar negativos
            mascara_neg = self.df[columna] < 0

            # 2) Consecutividad con la fila previa (misma Entidad, mismo Año, y Semana == Semana_prev + 1)
            padecimiento = self.df["Padecimiento"].shift(1)
            anio_prev = self.df["Anio"].shift(1)
            semana_prev = self.df["Semana"].shift(1)
            entidad_prev = self.df["Entidad"].shift(1)
            valor_prev = self.df[columna].shift(1)

            es_consec = (
                (self.df["Padecimiento"] == padecimiento)
                & (self.df["Entidad"] == entidad_prev)
                & (self.df["Anio"] == anio_prev)
                & (self.df["Semana"] == semana_prev + 1)
            )

            # Negativo actual + previo positivo + consecutivo
            mascara_act = mascara_neg & es_consec & (valor_prev > 0)

            # 3) AJUSTAR EL PREVIO (t-1) con "previo + actual_negativo"
            #    - Recorte a >= 0
            #    - Redondeo a entero
            nuevo_prev = (valor_prev + self.df[columna]).where(mascara_act).clip(lower=0)

            # Índices del previo (t-1) donde escribir
            prev_index = self.df.index.to_series().shift(1)
            targets_prev = prev_index[mascara_act].dropna().astype(int)

            # Escribir en el PREVIO (solo en las filas válidas)
            self.df.loc[targets_prev, columna] = nuevo_prev[mascara_act].astype(int).values

            # 4) EXTRAPOLACIÓN CON 3 SEMANAS PREVIAS (t-1, t-2, t-3) usando la COLUMNA YA ACTUALIZADA
            #    shift(1): excluye la semana actual
            #    rolling(3): últimas 3 semanas previas dentro del mismo (Entidad, Anio)
            prev3_mean = self.df.groupby(["Padecimiento", "Entidad", "Anio"])[columna].transform(
                lambda s: s.shift(1).rolling(window=3, min_periods=1).mean()
            )

            # Redondear el promedio a entero y reemplazar NaN por 0 (si no hay historial)
            prev3_mean = np.rint(prev3_mean).astype("Int64").fillna(0).astype(int)

            # 5) Escribir la EXTRAPOLACIÓN en la fila ACTUAL (negativa + consecutiva + previo>0)
            self.df.loc[mascara_act, columna] = prev3_mean[mascara_act].values

            # 6) Asegurar que TODA la columna quede en enteros (por si quedan floats por mezclas pandas)
            self.df[columna] = np.rint(self.df[columna]).astype(int)

    def _ajusta_negativos(self) -> None:
        for columna in ["Incremento_hombres", "Incremento_mujeres"]:
            neg = self.df[columna] < 0

            # Retrospectiva: media movil de 3 semanas previas (sin mirar futuro)
            prev3_mean = self.df.groupby(["Padecimiento", "Entidad"])[columna].transform(
                lambda s: s.shift(1).rolling(window=3, min_periods=1).mean()
            )

            extrap = prev3_mean.clip(lower=0)
            extrap = extrap.replace([np.inf, -np.inf], np.nan).fillna(0)
            extrap = np.rint(extrap).astype(int)

            self.df.loc[neg, columna] = extrap[neg].values

            self.df[columna] = (
                pd.Series(self.df[columna], index=self.df.index)
                .replace([np.inf, -np.inf], np.nan)
                .fillna(0)
                .round()
                .astype(int)
            )

    def _padecimientos_excluidos_outliers(self) -> list[str]:
        """Padecimientos exentos del tratamiento de outliers (config)."""
        cfg = self.get_opcion("tratamiento_outliers") or {}
        return list(cfg.get("excluir_padecimientos", []) or [])

    def _tratar_outliers(self, func: "Callable[[pd.DataFrame], pd.DataFrame]") -> pd.DataFrame:
        """Aplica el tratamiento de outliers ``func`` preservando intactos los
        padecimientos excluidos (p. ej. Dengue: el pico epidémico ES la señal a
        pronosticar, no ruido a recortar). Funciona en modo General (mixto) y por
        padecimiento."""
        excluir = self._padecimientos_excluidos_outliers()
        if not excluir or "Padecimiento" not in self.df.columns:
            return func(self.df)
        mask = self.df["Padecimiento"].isin(excluir)
        if not mask.any():
            return func(self.df)
        preservados = self.df[mask].copy()
        tratados = func(self.df[~mask].copy())
        logger.info(
            "Outliers: se preservan {} fila(s) de padecimientos excluidos {} (sin recorte)",
            int(mask.sum()),
            excluir,
        )
        combinado = pd.concat([tratados, preservados], ignore_index=True)
        return combinado.sort_values(["Padecimiento", "Anio", "Entidad", "Semana"]).reset_index(
            drop=True
        )

    def _ajusta_outliers(self, columnas: list[str], agrupacion: list[str]) -> None:
        from epiforecast.data.preprocessing.imputation import ajusta_outliers

        self.df = self._tratar_outliers(lambda d: ajusta_outliers(d, columnas, agrupacion))

    def _ajusta_outliers_zscore(
        self, columnas: list[str], agrupacion: list[str], umbral: int, reemplazo: str
    ) -> None:
        from epiforecast.data.preprocessing.imputation import ajusta_outliers_zscore

        self.df = self._tratar_outliers(
            lambda d: ajusta_outliers_zscore(d, columnas, agrupacion, umbral, reemplazo)
        )

    def agrupar(self) -> None:
        """Agrupa incrementos por Padecimiento, Semana, Fecha y Entidad, y asigna regiones."""

        logger.info("Aplicando agrupamiento")

        self.df_agrupado = (
            self.df.groupby(["Padecimiento", "Semana", "Fecha", "Entidad"])
            .agg(
                incrementos_hombres=("Incremento_hombres", "sum"),
                incrementos_mujeres=("Incremento_mujeres", "sum"),
            )
            .reset_index()
            .sort_values(["Padecimiento", "Fecha", "Entidad"])
        )
        logger.info(f"Se obtuvieron {len(self.df_agrupado)} registros agrupados.")

        mapa_regiones = {
            estado: r["nombre"] for r in self.regiones for estado in r.get("estados", [])
        }

        self.df_agrupado["Region"] = self.df_agrupado["Entidad"].map(mapa_regiones)

    def genera_todos(self) -> None:
        """Calcula el total de incrementos (hombres + mujeres) como nueva columna."""

        self.df_agrupado["incrementos_total"] = (
            self.df_agrupado["incrementos_hombres"] + self.df_agrupado["incrementos_mujeres"]
        )

    def run(self) -> pd.DataFrame:
        """Ejecuta el pipeline completo: ajuste de semanas, incrementos, outliers y agrupación.

        Returns:
            DataFrame agrupado con incrementos por sexo, totales y regiones.
        """
        outlier_cfg = self.get_opcion("tratamiento_outliers")

        self._ajusta_semanas()
        self._prepara_series_tiempo()
        # self._ajusta_incrementos()  Procedimiento para el tratamiento de datos semana 20 2016
        #                            Se retira este ajuste
        self._ajusta_negativos()

        if outlier_cfg and outlier_cfg["IQR"]:
            if (
                outlier_cfg["metodo"].lower() == "iqr"
            ):  # Se recomienda no usar este metodo, agrega muchos datos no validos
                logger.info(
                    f"Imputación habilitada: método: '{outlier_cfg['metodo']}' | "
                    f"columnas: {outlier_cfg['columnas']}, | "
                    f"umbral: {outlier_cfg['umbral']}"
                )
                self._ajusta_outliers(outlier_cfg["columnas"], outlier_cfg["agrupacion"])

            elif outlier_cfg["metodo"].lower() == "zscore":
                logger.info(
                    f"Imputación habilitada: método: '{outlier_cfg['metodo']}' | "
                    f"columnas: {outlier_cfg['columnas']} | "
                    f"umbral: {outlier_cfg['umbral']} | "
                    f"reemplazo: {outlier_cfg['reemplazo']}"
                )
                self._ajusta_outliers_zscore(
                    outlier_cfg["columnas"],
                    outlier_cfg["agrupacion"],
                    outlier_cfg["umbral"],
                    outlier_cfg["reemplazo"],
                )
            else:
                logger.error(f"Opcion no válida: {outlier_cfg.get('metodo')}")
                raise ValueError(f"Opcion no válida: {outlier_cfg.get('metodo')}")

        self.agrupar()
        self.genera_todos()

        return self.df_agrupado
