# src/epiforecast/models/prophet/tuner.py
"""Prophet hyperparameter tuner with anti-Newton protection (SRP: HP optimization only).

Three-layer Newton fallback protection:
1. Sort HP combos by changepoint_prior_scale descending (high cp = fast L-BFGS)
2. Per-fold timeout via ThreadPoolExecutor
3. Newton-prone threshold: if cp=X times out, skip all cp < X
"""

from __future__ import annotations

import itertools
import time
from typing import TYPE_CHECKING, Any

from tqdm import tqdm

from epiforecast.models.prophet.cross_validator import ProphetCrossValidator
from epiforecast.utils.config import conf, logger

if TYPE_CHECKING:
    from epiforecast.models.prophet.model import ProphetForecaster

# Grid key mapping: Spanish condition name → YAML key
_GRID_KEY_MAP: dict[str, str] = {
    "Alzheimer": "alzheimer",
    "Depresión": "depresion",
    "Parkinson": "parkinson",
    "Dengue": "dengue",
}


class ProphetTuner:
    """Hyperparameter optimizer for Prophet models.

    Searches over a condition-specific parameter grid using temporal
    cross-validation, with Newton optimizer fallback protection.
    """

    def __init__(self, forecaster: ProphetForecaster, config: dict[str, Any] | None = None):
        """Inicializa el tuner con un forecaster y carga el grid de hiperparámetros.

        Args:
            forecaster: Instancia de ProphetForecaster con datos y configuración.
            config:     Dict de configuración (default: conf global de YAML).
        """
        self._conf = config if config is not None else conf
        self.forecaster = forecaster
        self.param_grid = self._load_grid()
        self.cv_timeout = self._conf.get("cv_timeout_por_combo", 0)

    def run(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Execute HP search and return (best_params, best_metrics).

        Returns:
            best_params: dict with best HP combination.
            best_metrics: dict with rmse, mae, mape, mase.
        """
        combos = self._build_sorted_combos()
        logger.debug(
            "Se probarán {} combinaciones de HP (ordenadas por cp desc).",
            len(combos),
        )

        best_rmse = float("inf")
        best_params: dict[str, Any] | None = None
        best_metrics: dict[str, Any] = {}
        newton_cp_threshold: float | None = None

        pbar = tqdm(
            enumerate(combos),
            total=len(combos),
            desc="CV",
            unit="combo",
            leave=False,
            dynamic_ncols=True,
            position=1,
        )
        for idx, params in pbar:
            result = self._evaluate_single_combo(
                idx,
                params,
                len(combos),
                newton_cp_threshold,
                pbar,
            )

            if result is None:
                continue

            metrics, new_threshold = result

            if new_threshold is not None:
                newton_cp_threshold = new_threshold
                continue

            mean_rmse = metrics.get("rmse", float("inf"))
            if mean_rmse < best_rmse:
                best_rmse = mean_rmse
                best_params = params
                best_metrics = metrics

        return self._finalize(best_params, best_metrics)

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _evaluate_single_combo(
        self,
        idx: int,
        params: dict[str, Any],
        total: int,
        newton_cp_threshold: float | None,
        pbar: tqdm[Any],
    ) -> tuple[dict[str, Any], float | None] | None:
        """Evalúa una combinación de HP. Retorna (metrics, new_threshold) o None si skip."""
        cp = params.get("changepoint_prior_scale", 0)
        resumen = ", ".join(f"{k}={v}" for k, v in params.items())

        # Layer 3: skip combos below Newton threshold
        if newton_cp_threshold is not None and cp < newton_cp_threshold:
            logger.debug(
                "Skip combo (Newton-prone): cp={} < umbral {} | {}",
                cp,
                newton_cp_threshold,
                resumen,
            )
            return None

        t_start = time.time()
        cv = ProphetCrossValidator(self.forecaster)
        metrics, timed_out, timeout_cp = cv.evaluate_combo(params)
        elapsed = time.time() - t_start

        if timed_out and timeout_cp is not None:
            return metrics, timeout_cp

        if self.cv_timeout and elapsed > self.cv_timeout:
            logger.debug(
                "Timeout CV combo: {:.0f}s > {}s | {}",
                elapsed,
                self.cv_timeout,
                resumen,
            )
            return metrics, cp

        mean_rmse = metrics.get("rmse", float("inf"))
        pbar.set_postfix(rmse=f"{mean_rmse:.4f}", cp=cp)
        logger.debug(
            "[CV] Iter {}/{} – RMSE={:.4f} | {}",
            idx + 1,
            total,
            mean_rmse,
            resumen,
        )

        return metrics, None

    def _finalize(
        self, best_params: dict[str, Any] | None, best_metrics: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Finaliza la búsqueda: aplica fallback si todos los combos fallaron."""
        if best_params is None:
            best_params = self._fallback_params()
            best_metrics = {"rmse": None, "mae": None, "mape": None, "mase": None}
            logger.debug(
                "Todos los combos timeout (Newton). Params default: {}",
                best_params,
            )
        else:
            logger.debug(
                "Mejor RMSE: {:.4f} | MAE: {:.4f} | MAPE: {:.2f}%",
                best_metrics.get("rmse", 0),
                best_metrics.get("mae", 0),
                best_metrics.get("mape", 0),
            )
            logger.debug("Mejor conjunto de parámetros: {}", best_params)

        return best_params, best_metrics

    def _load_grid(self) -> dict[str, Any]:
        """Load condition-specific HP grid from config."""
        df = self.forecaster.df
        tipo = df["Padecimiento"].iloc[0] if "Padecimiento" in df.columns else None
        grid_key = _GRID_KEY_MAP.get(tipo)  # type: ignore[arg-type]
        if grid_key is None:
            raise ValueError(
                f"param_grid_prophet no definido para padecimiento='{tipo}'. "
                f"Valores válidos: {list(_GRID_KEY_MAP)}"
            )
        logger.debug("Grid de hiperparámetros: {} ({})", tipo, grid_key)
        return self._conf["param_grid_prophet"][grid_key]  # type: ignore[no-any-return]

    def _build_sorted_combos(self) -> list[dict[str, Any]]:
        """Build all HP combinations, sorted by cp descending (Layer 1)."""
        keys = self.param_grid.keys()
        combos = [
            dict(zip(keys, v, strict=False)) for v in itertools.product(*self.param_grid.values())
        ]
        combos.sort(key=lambda p: p.get("changepoint_prior_scale", 0), reverse=True)
        return combos

    def _fallback_params(self) -> dict[str, Any]:
        """Generate fallback params: defaults with highest cp."""
        params = {k: v[0] for k, v in self.param_grid.items()}
        if "changepoint_prior_scale" in self.param_grid:
            params["changepoint_prior_scale"] = max(self.param_grid["changepoint_prior_scale"])
        return params
