"""NB-GLM: Negative-Binomial GLM + Fourier(anual) + lags + ENSO (El Niño).

Motor de conteos para Dengue. Validado en backtest leave-one-epidemic-out (nacional):
SMAPE medio 52.0 vs Prophet+ENSO 76.4 vs Prophet actual 102.4. Es count-correcto
(NegBin sobre conteos enteros), extrapola limpio (estacionalidad de Fourier + tendencia,
sin la divergencia de los árboles), determinista (sin la estocasticidad de DeepAR) y usa
el índice ONI rezagado para anticipar el ciclo inter-anual (que no vive en los conteos
recientes). Pensado para la cohorte de conteos (Dengue); el regresor ENSO se activa solo
para esa cohorte (``is_count_log_cohort``).
"""

from __future__ import annotations

from pathlib import Path
import pickle
from typing import Any

import numpy as np
import pandas as pd

from epiforecast.evaluation.metrics import compute_forecast_metrics
from epiforecast.models.base import ForecastModel
from epiforecast.models.factory import register_model
from epiforecast.models.prophet.data_prep import agrupa
from epiforecast.utils.cohorts import is_count_log_cohort
from epiforecast.utils.config import conf, logger


def _fourier(ds: pd.Series, k: int) -> np.ndarray[Any, Any]:
    """Términos de Fourier para el ciclo anual (semana ISO)."""
    wk = pd.DatetimeIndex(ds).isocalendar().week.astype(float).to_numpy()
    cols = []
    for i in range(1, k + 1):
        cols.append(np.sin(2 * np.pi * i * wk / 52.0))
        cols.append(np.cos(2 * np.pi * i * wk / 52.0))
    return np.column_stack(cols)


@register_model("nbglm")
class NBGLMForecaster(ForecastModel):
    """Negative-Binomial GLM con Fourier + lags + ENSO para series de conteos."""

    def __init__(
        self,
        df: pd.DataFrame | None = None,
        sexo: str | None = None,
        entidad: str | None = None,
        padecimiento: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        self._conf = config if config is not None else conf
        self.df = df.copy() if df is not None else pd.DataFrame()
        if not self.df.empty and "Fecha" in self.df.columns:
            self.df["Fecha"] = pd.to_datetime(self.df["Fecha"])
        self.sexo = sexo
        self.entidad = entidad
        self.padecimiento = padecimiento

        nb = self._conf.get("nbglm", {})
        self.fourier_k: int = int(nb.get("fourier_k", 4))
        self.alpha: float = float(nb.get("alpha", 1.0))
        self.clip_max: float = float(nb.get("clip_max", 50000.0))
        self.enso_regressor: bool = bool(nb.get("enso_regressor", True)) and is_count_log_cohort(
            self.padecimiento
        )
        self.enso_lag_weeks: int = int(nb.get("enso_lag_weeks", 16))
        self.col_poblacion: str = self._conf.get("columna_poblacion", "Total")
        self.freq: str = "W-MON"

        self.serie: pd.DataFrame = pd.DataFrame()
        self._res: Any = None  # statsmodels GLMResults
        self._last_ds: pd.Timestamp | None = None
        self._y_hist: np.ndarray[Any, Any] = np.array([])
        self._const: float = 0.0  # fallback constante para series degeneradas (CDMX, Tlaxcala)
        self._train_ds: pd.Series = pd.Series(dtype="datetime64[ns]")

    # ── Datos ────────────────────────────────────────────────────────────────
    def agrupar(self) -> None:
        """Serie (ds, y) de conteos para la (entidad, sexo) dada."""
        g = agrupa(self.df, self.sexo, normalizar_tasa=False, col_poblacion=self.col_poblacion)
        s = g.rename_axis("ds").reset_index().rename(columns={self.sexo: "y"})
        s = s[["ds", "y"]].sort_values("ds").reset_index(drop=True)
        s["ds"] = pd.to_datetime(s["ds"])
        self.serie = s

    def _design(
        self, ds: pd.Series, y_for_lags: np.ndarray[Any, Any], as_of: pd.Timestamp | None
    ) -> np.ndarray[Any, Any]:
        """Matriz de diseño: 1 + Fourier + tendencia + lag1 + lag52 [+ ONI]."""
        n = len(ds)
        four = _fourier(ds, self.fourier_k)
        trend = (np.arange(n) / 52.0).reshape(-1, 1)
        lag1 = np.log1p(np.concatenate([[y_for_lags[0]], y_for_lags[:-1]]))
        lag52 = np.log1p(
            np.concatenate([np.full(min(52, n), y_for_lags[0]), y_for_lags[:-52]])[:n]
        )
        feats = [np.ones(n), four, trend, lag1, lag52]
        if self.enso_regressor:
            from epiforecast.data import enso

            feats.append(
                enso.oni_for_dates(ds, lag_weeks=self.enso_lag_weeks, as_of=as_of).reshape(-1, 1)
            )
        return np.column_stack(feats)

    # ── Interfaz ForecastModel ────────────────────────────────────────────────
    def fit(self, train_data: pd.DataFrame, parametros: dict[str, Any] | None = None) -> None:
        import statsmodels.api as sm

        y = train_data["y"].clip(lower=0).to_numpy(dtype=float)
        self._y_hist = y
        self._train_ds = pd.to_datetime(train_data["ds"]).reset_index(drop=True)
        self._last_ds = pd.Timestamp(train_data["ds"].iloc[-1])
        self._const = float(np.mean(y)) if len(y) else 0.0
        # Series degeneradas (sin transmisión o casi-cero, p.ej. CDMX/Tlaxcala): el GLM NegBin
        # es infactible -> fallback a pronóstico constante (la media, ~0). No revienta el fleet.
        if y.sum() < 5:
            self._res = None
            return
        try:
            x = self._design(train_data["ds"], y, as_of=None)
            self._res = sm.GLM(y, x, family=sm.families.NegativeBinomial(alpha=self.alpha)).fit()
        except Exception as e:  # noqa: BLE001 — GLM infeasible en series degeneradas
            logger.warning("NB-GLM fit falló ({}); fallback constante={:.1f}", e, self._const)
            self._res = None

    def _frame(self, ds: Any, yhat: np.ndarray[Any, Any]) -> pd.DataFrame:
        """DataFrame (ds, yhat, intervalos NegBin) con yhat acotado a >= 0."""
        yhat = np.clip(yhat.astype(float), 0, self.clip_max)
        sd = np.sqrt(yhat + self.alpha * yhat**2)
        return pd.DataFrame(
            {
                "ds": ds,
                "yhat": yhat,
                "yhat_lower": np.clip(yhat - 1.96 * sd, 0, None),
                "yhat_upper": yhat + 1.96 * sd,
            }
        )

    def predict(
        self,
        horizon: int = 52,
        freeze_trend: bool = False,
        future_oni: np.ndarray[Any, Any] | None = None,
        trend_anchor_weeks: float | None = None,
    ) -> pd.DataFrame:
        """Ajuste in-sample + futuro. ``freeze_trend=True`` congela la tendencia lineal en su
        último nivel observado para el tramo futuro: útil en proyecciones ilustrativas de varios
        años, donde extrapolar la tendencia (inflada por la epidemia de 2024) sobreestimaría los
        años no epidémicos. Muestra el patrón estacional + ENSO a nivel estable, no la magnitud
        de la próxima gran epidemia. El default (False) conserva el comportamiento productivo.

        ``future_oni`` (longitud ``horizon``) inyecta un ESCENARIO de ONI futuro ya rezagado por
        semana (p.ej. el próximo El Niño climatológico) en lugar de la persistencia amortiguada
        hacia neutral. Permite pronosticar el próximo brote condicionado a un El Niño esperado.

        ``trend_anchor_weeks`` (implica ``freeze_trend``) fija el nivel base de la tendencia en
        ese índice semanal en vez del último (``n0``): anclar a una semana anterior a la epidemia
        de 2024 baja el piso para que los años SIN El Niño queden bajos y solo el clima los suba.
        """
        if self._last_ds is None:
            raise RuntimeError("Modelo no entrenado. Llama fit() primero.")
        fut_ds = pd.date_range(
            self._last_ds + pd.Timedelta(weeks=1), periods=horizon, freq=self.freq
        )
        # Ajuste in-sample: el CSV de forecast debe incluir el ajuste del histórico (p.ej.
        # 2026 H1), que es lo que la selección de producción compara contra la realidad. El
        # futuro empieza tras la última semana real, así que por sí solo no solapa con 2026.
        if self._res is None:  # fallback constante (series degeneradas)
            c = max(0.0, self._const)
            in_df = self._frame(self._train_ds, np.full(len(self._train_ds), c))
            fut_df = self._frame(fut_ds, np.full(horizon, c))
            return pd.concat([in_df, fut_df], ignore_index=True)
        yhat_in = self._res.predict(self._design(self._train_ds, self._y_hist, as_of=None))
        in_df = self._frame(self._train_ds, np.asarray(yhat_in))
        four_f = _fourier(pd.Series(fut_ds), self.fourier_k)
        oni_f = None
        if self.enso_regressor:
            if future_oni is not None:
                oni_f = np.asarray(future_oni, dtype=float)[:horizon]
            else:
                from epiforecast.data import enso

                oni_f = enso.oni_for_dates(
                    pd.Series(fut_ds), lag_weeks=self.enso_lag_weeks, as_of=self._last_ds
                )
        hist = list(self._y_hist)
        n0 = len(self._y_hist)
        if trend_anchor_weeks is not None:
            freeze_trend = True
        anchor = trend_anchor_weeks if trend_anchor_weeks is not None else n0
        preds = []
        for i in range(horizon):
            tr = (anchor if freeze_trend else n0 + i) / 52.0
            l1 = np.log1p(hist[-1])
            l52 = np.log1p(hist[-52]) if len(hist) >= 52 else np.log1p(hist[0])
            row = [1.0, *four_f[i], tr, l1, l52]
            if oni_f is not None:
                row.append(float(oni_f[i]))
            mu = float(self._res.predict(np.array(row).reshape(1, -1))[0])
            mu = max(0.0, min(mu, self.clip_max))
            preds.append(mu)
            hist.append(mu)
        fut_df = self._frame(fut_ds, np.array(preds))
        return pd.concat([in_df, fut_df], ignore_index=True)

    def cross_validate(self, data: pd.DataFrame | None = None) -> dict[str, float]:
        """CV expansiva ligera (2 folds de 26 sem) para métricas comparables."""
        s = self.serie if data is None else data
        n_splits, test_size = 2, 26
        metrics_acc: dict[str, list[float]] = {"rmse": [], "mae": [], "smape": [], "mase": []}
        for k in range(n_splits, 0, -1):
            cut = len(s) - k * test_size
            if cut < 60:
                continue
            tr, val = s.iloc[:cut], s.iloc[cut : cut + test_size]
            try:
                self.fit(tr)
                pred = self.predict(len(val))
                m = compute_forecast_metrics(
                    val["y"].to_numpy(float),
                    pred["yhat"].to_numpy(float)[: len(val)],
                    tr["y"].to_numpy(float),
                )
                for key in metrics_acc:
                    val_k = m.get(key)
                    if val_k is not None:
                        metrics_acc[key].append(float(val_k))
            except (ValueError, np.linalg.LinAlgError):
                continue
        return {k: float(np.mean(v)) if v else float("nan") for k, v in metrics_acc.items()}

    def run(self) -> tuple[Any, dict[str, Any], dict[str, Any]]:
        self.agrupar()
        metrics: dict[str, Any] = dict(self.cross_validate())
        self.fit(self.serie)  # ajuste final sobre toda la serie
        metrics["confianza"] = "normal"
        metrics["promedio_semanal"] = (
            float(self.serie["y"].mean()) if not self.serie.empty else 0.0
        )
        logger.info(
            "NB-GLM {} | {} | SMAPE_cv={:.1f}%",
            self.entidad or "Nacional",
            self.sexo,
            metrics.get("smape", float("nan")),
        )
        return self._res, metrics, self.get_params()

    def get_params(self) -> dict[str, Any]:
        return {
            "modelo": "nbglm",
            "fourier_k": self.fourier_k,
            "alpha": self.alpha,
            "enso_regressor": self.enso_regressor,
            "enso_lag_weeks": self.enso_lag_weeks,
        }

    def save(self, path: Path) -> None:
        from epiforecast.utils.model_metadata import build_model_metadata

        if self._last_ds is None:
            raise RuntimeError("No hay modelo que guardar. Llama fit() primero.")
        payload = {
            "model": {
                "res": self._res,
                "y_hist": self._y_hist,
                "last_ds": self._last_ds,
                "const": self._const,
                "train_ds": self._train_ds,
                "params": self.get_params(),
            },
            "_metadata": build_model_metadata(),
        }
        with path.open("wb") as f:
            pickle.dump(payload, f)

    def load(self, path: Path) -> None:
        with path.open("rb") as f:
            payload = pickle.load(f)  # noqa: S301
        m = payload["model"]
        self._res = m["res"]
        self._y_hist = m["y_hist"]
        self._last_ds = m["last_ds"]
        self._const = float(m.get("const", 0.0) or 0.0)
        self._train_ds = m.get("train_ds", pd.Series(dtype="datetime64[ns]"))
        p: dict[str, Any] = m.get("params", {})
        self.fourier_k = int(p.get("fourier_k") or self.fourier_k)
        self.alpha = float(p.get("alpha") or self.alpha)
        self.enso_regressor = bool(p.get("enso_regressor", self.enso_regressor))
        self.enso_lag_weeks = int(p.get("enso_lag_weeks") or self.enso_lag_weeks)
