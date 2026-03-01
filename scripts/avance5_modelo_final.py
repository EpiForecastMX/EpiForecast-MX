# scripts/avance5_modelo_final.py
"""Avance 5 — Modelo Final: Prophet Base vs Ensemble (Prophet + XGBoost).

Target = conteos absolutos (incrementos), NO tasa por 100k.
El ensemble con XGBoost captura volatilidad y picos que Prophet pierde.

Uso:
    python -m scripts.avance5_modelo_final
    python -m scripts.avance5_modelo_final padecimiento.tipo='Alzheimer'
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table
from xgboost import XGBRegressor

from epiforecast.constants import VIZ_DPI_SCREEN
from epiforecast.models.factory import create_model
from epiforecast.utils.config import conf, logger
from epiforecast.visualization.chart_annotations import (
    _TZ_CDMX,
    _anotar_divisores,
)

# ---------------------------------------------------------------------------
# Constantes (desde config)
# ---------------------------------------------------------------------------
PADECIMIENTOS = ["Alzheimer", "Depresion", "Parkinson"]
IMSS = conf.get("IMSS_COLORS", {})

# Colores derivados de la paleta IMSS (plots.yaml)
COLORES = {
    "real": IMSS.get("neutral_black", "#231F20"),
    "prophet": IMSS.get("teal", "#00524E"),
    "ensemble": IMSS.get("burgundy", "#9B2242"),
    "gold": IMSS.get("gold", "#B58500"),
    "cutoff": IMSS.get("cool_gray", "#97999B"),
}

# COVID desde config
_COVID_CONF = conf.get("COVID", {})
_COVID_INICIO = _COVID_CONF.get("inicio", "2020-03-15")
_COVID_FIN = _COVID_CONF.get("fin", "2022-09-22")

console = Console()

# Colores COVID (alineados con forecast_chart.py)
_COVID_SPAN_COLOR = "#E53935"
_COVID_TEXT_COLOR = "#C62828"
_COVID_BAND_ALPHA = 0.05


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------
def _cargar_datos() -> pd.DataFrame:
    """Lee CSV nacional y retorna DataFrame completo (todos los padecimientos)."""
    ruta = Path(conf["paths"]["processed"]) / "data_inegi_General.csv"
    logger.info("Cargando datos desde {}", ruta)
    df = pd.read_csv(ruta, parse_dates=["Fecha"])
    df.columns = df.columns.str.strip()
    return df


# ---------------------------------------------------------------------------
# Tabla Rich
# ---------------------------------------------------------------------------
def _imprimir_tabla_rich(metricas: list[dict], padecimiento: str) -> None:
    """Imprime tabla comparativa en consola con Rich."""
    tabla = Table(
        title=f"Evaluacion de modelos — {padecimiento} (Nivel Nacional)",
        show_lines=True,
    )
    tabla.add_column("Modelo", style="bold cyan")
    tabla.add_column("RMSE", justify="right")
    tabla.add_column("MAE", justify="right")
    tabla.add_column("SMAPE (%)", justify="right")
    tabla.add_column("MASE", justify="right")
    tabla.add_column("Tiempo (s)", justify="right")

    metricas_sorted = sorted(metricas, key=lambda m: m["rmse"])

    for m in metricas_sorted:
        mase_str = f"{m['mase']:.4f}" if m["mase"] is not None else "N/A"
        tabla.add_row(
            m["modelo"],
            f"{m['rmse']:.2f}",
            f"{m['mae']:.2f}",
            f"{m['smape']:.2f}",
            mase_str,
            f"{m['tiempo']:.1f}",
        )

    console.print(tabla)


# ---------------------------------------------------------------------------
# Helpers de graficos
# ---------------------------------------------------------------------------
def _decorar_ejes(
    ax: plt.Axes,
    fig: plt.Figure,
    cutoff_date: pd.Timestamp,
    last_real: pd.Timestamp,
    futuro_df: pd.DataFrame,
    padecimiento: str,
    subtitulo: str,
) -> None:
    """Aplica zonas sombreadas, lineas divisoras, formato y timestamp CDMX."""
    # Franja COVID (desde config — unica fuente de verdad)
    covid_inicio = pd.Timestamp(_COVID_INICIO)
    covid_fin = pd.Timestamp(_COVID_FIN)
    ax.axvspan(covid_inicio, covid_fin, alpha=_COVID_BAND_ALPHA, color=_COVID_SPAN_COLOR, zorder=0)
    ax.axvline(
        covid_inicio, color=_COVID_SPAN_COLOR, linestyle=":", linewidth=0.8, alpha=0.5, zorder=2
    )
    ax.axvline(
        covid_fin, color=_COVID_SPAN_COLOR, linestyle=":", linewidth=0.8, alpha=0.5, zorder=2
    )
    ax.text(
        covid_inicio + (covid_fin - covid_inicio) / 2,
        0.96,
        "COVID-19",
        ha="center",
        fontsize=8,
        color=_COVID_TEXT_COLOR,
        alpha=0.7,
        transform=ax.get_xaxis_transform(),
    )

    # Zonas sombreadas backtesting/futuro
    ax.axvspan(
        cutoff_date,
        last_real,
        alpha=0.08,
        color=COLORES["prophet"],
        label="Ajuste del Modelo (Backtesting)",
    )
    if not futuro_df.empty:
        ax.axvspan(
            last_real,
            futuro_df["ds"].max(),
            alpha=0.08,
            color=COLORES["ensemble"],
            label="Prediccion de Casos",
        )

    # Divisores (reutiliza annotations compartidas — colores diferenciados)
    _anotar_divisores(ax, cutoff_date, COLORES["cutoff"], COLORES["ensemble"])

    # Linea de ultimo dato real
    ax.axvline(last_real, color=COLORES["cutoff"], linestyle="--", linewidth=1.0, alpha=0.7)
    ax.text(
        last_real,
        ax.get_ylim()[1] * 0.97,
        " Ultimo dato real",
        fontsize=8,
        color=COLORES["cutoff"],
        va="top",
    )

    # Formato
    ax.set_title(
        f"Pronostico Epidemiologico: {padecimiento} — {subtitulo}",
        fontsize=16,
        fontweight="bold",
        pad=15,
    )
    ax.set_xlabel("Fecha", fontsize=12)
    ax.set_ylabel("Casos semanales (conteo absoluto)", fontsize=12)
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(axis="y", alpha=0.3)

    now_cdmx = datetime.now(tz=_TZ_CDMX).strftime("%Y-%m-%d %H:%M CDMX")
    fig.text(0.99, 0.01, f"Generado: {now_cdmx}", ha="right", fontsize=7, color="grey")


def _plot_real(ax: plt.Axes, train_df: pd.DataFrame, test_df: pd.DataFrame) -> None:
    """Dibuja la serie de datos reales (train + test)."""
    ax.plot(
        train_df["ds"],
        train_df["y"],
        color=COLORES["real"],
        linewidth=2.5,
        alpha=0.7,
        label="Datos reales",
    )
    ax.plot(
        test_df["ds"],
        test_df["y"],
        color=COLORES["real"],
        linewidth=2.5,
        alpha=0.7,
    )


# ---------------------------------------------------------------------------
# Grafico individual (un solo modelo)
# ---------------------------------------------------------------------------
def _graficar_individual(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    yhat_train: np.ndarray,
    yhat_test: np.ndarray,
    yhat_futuro: np.ndarray,
    futuro_df: pd.DataFrame,
    padecimiento: str,
    modelo_nombre: str,
    color: str,
    linestyle: str,
    output_path: Path,
    cutoff: str,
) -> None:
    """Genera grafico de pronostico para un solo modelo."""
    fig, ax = plt.subplots(figsize=(20, 8))
    cutoff_date = pd.Timestamp(cutoff)
    last_real = test_df["ds"].max()

    _plot_real(ax, train_df, test_df)

    # Modelo — ajuste historico
    ax.plot(
        train_df["ds"],
        yhat_train,
        color=color,
        linewidth=1.2,
        linestyle=linestyle,
        alpha=0.45,
        label=modelo_nombre,
    )
    # Modelo — backtesting
    ax.plot(
        test_df["ds"],
        yhat_test,
        color=color,
        linewidth=2.0,
        linestyle=linestyle,
    )
    # Modelo — futuro
    ax.plot(
        futuro_df["ds"],
        yhat_futuro,
        color=color,
        linewidth=2.0,
        linestyle=linestyle,
        alpha=0.6,
    )

    _decorar_ejes(ax, fig, cutoff_date, last_real, futuro_df, padecimiento, modelo_nombre)

    plt.tight_layout()
    if not futuro_df.empty:
        ax.set_xlim(
            left=pd.Timestamp("2020-01-01"),
            right=pd.Timestamp(futuro_df["ds"].max()) + pd.Timedelta(weeks=4),
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=VIZ_DPI_SCREEN, bbox_inches="tight")
    plt.close(fig)
    logger.info("  Grafico guardado: {}", output_path)


# ---------------------------------------------------------------------------
# Grafico comparativo (ambos modelos)
# ---------------------------------------------------------------------------
def _graficar_comparativa(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    pred_train: pd.DataFrame,
    pred_test: pd.DataFrame,
    futuro_df: pd.DataFrame,
    padecimiento: str,
    output_path: Path,
    cutoff: str,
    *,
    xlim_left: str | None = None,
) -> None:
    """Genera grafico comparativo Prophet vs Ensemble estilo IMSS."""
    fig, ax = plt.subplots(figsize=(20, 8))
    cutoff_date = pd.Timestamp(cutoff)
    last_real = test_df["ds"].max()

    _plot_real(ax, train_df, test_df)

    # Prophet — ajuste historico
    ax.plot(
        pred_train["ds"],
        pred_train["yhat_prophet"],
        color=COLORES["prophet"],
        linewidth=1.2,
        linestyle="dashdot",
        alpha=0.45,
        label="Prophet Base",
    )
    # Prophet — backtesting
    ax.plot(
        pred_test["ds"],
        pred_test["yhat_prophet"],
        color=COLORES["prophet"],
        linewidth=1.5,
        linestyle="dashdot",
    )
    # Ensemble — ajuste historico
    ax.plot(
        pred_train["ds"],
        pred_train["yhat_ensemble"],
        color=COLORES["ensemble"],
        linewidth=1.2,
        linestyle="solid",
        alpha=0.45,
        label="Ensemble (Prophet + XGBoost)",
    )
    # Ensemble — backtesting
    ax.plot(
        pred_test["ds"],
        pred_test["yhat_ensemble"],
        color=COLORES["ensemble"],
        linewidth=2.0,
        linestyle="solid",
    )
    # Futuro — Prophet
    ax.plot(
        futuro_df["ds"],
        futuro_df["yhat_prophet"],
        color=COLORES["prophet"],
        linewidth=1.5,
        linestyle="dashdot",
        alpha=0.6,
    )
    # Futuro — Ensemble
    ax.plot(
        futuro_df["ds"],
        futuro_df["yhat_ensemble"],
        color=COLORES["ensemble"],
        linewidth=2.0,
        linestyle="solid",
        alpha=0.6,
    )

    _decorar_ejes(ax, fig, cutoff_date, last_real, futuro_df, padecimiento, "Prophet vs Ensemble")

    plt.tight_layout()
    if not futuro_df.empty:
        right = pd.Timestamp(futuro_df["ds"].max()) + pd.Timedelta(weeks=4)
        left = pd.Timestamp(xlim_left) if xlim_left else None
        ax.set_xlim(left=left, right=right)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=VIZ_DPI_SCREEN, bbox_inches="tight")
    plt.close(fig)
    logger.info("  Grafico guardado: {}", output_path)


# ---------------------------------------------------------------------------
# Grafico importancia features
# ---------------------------------------------------------------------------
def _graficar_importancia(
    xgb_model: XGBRegressor,
    feature_names: list[str],
    padecimiento: str,
    output_dir: Path,
) -> None:
    """Genera grafico de importancia de features del XGBoost."""
    importances = xgb_model.feature_importances_
    sorted_idx = np.argsort(importances)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.barh(
        [feature_names[i] for i in sorted_idx],
        importances[sorted_idx],
        color=COLORES["gold"],
    )
    ax.set_title(
        f"Importancia de Variables — XGBoost Residual: {padecimiento}",
        fontsize=14,
        fontweight="bold",
        pad=12,
    )
    ax.set_xlabel("Importancia (gain)", fontsize=11)

    now_cdmx = datetime.now(tz=_TZ_CDMX).strftime("%Y-%m-%d %H:%M CDMX")
    fig.text(0.99, 0.01, f"Generado: {now_cdmx}", ha="right", fontsize=7, color="grey")

    plt.tight_layout()
    output_path = output_dir / f"importancia_features_{padecimiento}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=VIZ_DPI_SCREEN, bbox_inches="tight")
    plt.close(fig)
    logger.info("  Grafico guardado: {}", output_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    """Pipeline principal del Avance 5."""
    logger.info("=" * 70)
    logger.info("Avance 5 — Modelo Final: Prophet Base vs Ensemble")
    logger.info("=" * 70)

    # Determinar padecimientos a procesar
    tipo = conf.get("padecimiento", {}).get("tipo", "General")
    if tipo == "General":
        padecimientos = PADECIMIENTOS
    else:
        tipo_norm = tipo.replace("\u00e9", "e").replace("\u00f3", "o")
        padecimientos = [p for p in PADECIMIENTOS if p.lower() == tipo_norm.lower()]
        if not padecimientos:
            logger.error("Padecimiento '{}' no reconocido. Opciones: {}", tipo, PADECIMIENTOS)
            return

    base_dir = Path("reports/forecasts")
    dir_prophet = base_dir / "prophet"
    dir_ensemble = base_dir / "ensemble"
    dir_comparacion = base_dir / "comparacion_modelos"
    models_dir = Path("models/ensemble")

    for padecimiento in padecimientos:
        logger.info("-" * 50)
        logger.info("Procesando: {}", padecimiento)
        logger.info("-" * 50)

        # 1. Cargar datos
        df = _cargar_datos()

        # 2. Factory pattern (SOLID) — entrena Prophet base + XGBoost
        forecaster = create_model(
            "ensemble",
            df=df,
            padecimiento=padecimiento,
            sexo="incrementos_total",
        )
        _, metrics_ensemble, params = forecaster.run()

        # 3. Guardar modelo (MLOps) -> models/ensemble/{pad}/Ensemble_{pad}_general.pkl
        pad = padecimiento
        ruta_modelo = models_dir / pad / f"Ensemble_{pad}_general.pkl"
        forecaster.save(ruta_modelo)

        # 4. Guardar serie sidecar + metadata CSV
        ruta_csv = ruta_modelo.with_suffix(".csv")
        forecaster.serie.to_csv(ruta_csv, index=False)
        logger.info("  Serie sidecar guardada: {}", ruta_csv)

        ruta_completo = models_dir / pad / f"Ensemble_{pad}_completo.csv"
        pd.DataFrame([metrics_ensemble]).to_csv(ruta_completo, index=False)
        logger.info("  Metadata guardada: {}", ruta_completo)

        # 5. Metricas Prophet base (comparar sub-modelos)
        metrics_prophet = forecaster.get_prophet_metrics()

        # 6. Tabla Rich
        _imprimir_tabla_rich([metrics_prophet, metrics_ensemble], pad)

        # 7. Generar futuro
        full = forecaster.predict(forecaster.horizon)
        cutoff_ts = (
            forecaster.serie["ds"].max()
            if not forecaster.serie.empty
            else pd.Timestamp(forecaster.prophet_model.history["ds"].max())
        )
        futuro_df = full[full["ds"] > cutoff_ts].reset_index(drop=True)

        # 8. Acceso a datos internos para graficos
        train_df = forecaster.train_data
        test_df = forecaster.test_data
        pred_train = forecaster.pred_train
        pred_test = forecaster.pred_test
        cutoff = forecaster.cutoff

        # 9. Prophet individual
        _graficar_individual(
            train_df,
            test_df,
            pred_train["yhat_prophet"].values,
            pred_test["yhat_prophet"].values,
            futuro_df["yhat_prophet"].values,
            futuro_df,
            pad,
            modelo_nombre="Prophet Base",
            color=COLORES["prophet"],
            linestyle="dashdot",
            output_path=dir_prophet / pad / f"pronostico_{pad}.png",
            cutoff=cutoff,
        )

        # 10. Ensemble individual + feature importance
        _graficar_individual(
            train_df,
            test_df,
            pred_train["yhat_ensemble"].values,
            pred_test["yhat_ensemble"].values,
            futuro_df["yhat_ensemble"].values,
            futuro_df,
            pad,
            modelo_nombre="Ensemble (Prophet + XGBoost)",
            color=COLORES["ensemble"],
            linestyle="solid",
            output_path=dir_ensemble / pad / f"pronostico_{pad}.png",
            cutoff=cutoff,
        )
        _graficar_importancia(
            forecaster.xgb_model,
            forecaster.feature_names,
            pad,
            dir_ensemble / pad,
        )

        # 11. Comparativa — historico completo
        _graficar_comparativa(
            train_df,
            test_df,
            pred_train,
            pred_test,
            futuro_df,
            pad,
            output_path=dir_comparacion / pad / f"comparativa_{pad}.png",
            cutoff=cutoff,
        )

        # 12. Comparativa — reciente (2020-2027)
        _graficar_comparativa(
            train_df,
            test_df,
            pred_train,
            pred_test,
            futuro_df,
            pad,
            output_path=dir_comparacion / pad / f"comparativa_{pad}_reciente.png",
            cutoff=cutoff,
            xlim_left="2020-01-01",
        )

    logger.success("Avance 5 completado.")
    logger.success("  Prophet     → {}", dir_prophet)
    logger.success("  Ensemble    → {}", dir_ensemble)
    logger.success("  Comparativa → {}", dir_comparacion)
    logger.success("  Modelos     → {}", models_dir)


if __name__ == "__main__":
    main()
