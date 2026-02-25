"""viz_forecast.py — Graficador rápido del forecast all_forecast.csv.

Uso:
    from scripts.viz_forecast import plot_forecast

    plot_forecast("Alzheimer", "Jalisco")
    plot_forecast("Depresión", "Nacional", modo="mujeres")
    plot_forecast("Parkinson", "Ciudad de México", modo="general", tasa=True)
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

FORECAST_CSV = Path("forecast/all_forecast.csv")
_df_cache: pd.DataFrame | None = None


def _cargar() -> pd.DataFrame:
    global _df_cache
    if _df_cache is None:
        _df_cache = pd.read_csv(FORECAST_CSV, parse_dates=["ds"])
    return _df_cache


def plot_forecast(
    padecimiento: str,
    entidad: str = "Nacional",
    modo: str = "general",
    tasa: bool = True,
    ax: plt.Axes | None = None,
) -> plt.Axes:
    """Grafica el forecast de un modelo específico.

    Args:
        padecimiento: "Alzheimer" | "Depresión" | "Parkinson"
        entidad:      Nombre del estado o "Nacional" (default).
        modo:         "general" | "hombres" | "mujeres" (default: "general").
        tasa:         True  → grafica yhat_tasa (casos / 100K hab.)
                      False → grafica yhat (espacio log-rate interno de Prophet).
        ax:           Axes existente; si None crea figura nueva.

    Returns:
        El Axes con la gráfica.
    """
    df = _cargar()

    mask = (
        (df["meta_padecimiento"].str.lower() == padecimiento.lower())
        & (df["meta_entidad"].str.lower() == entidad.lower())
        & (df["meta_modo"].str.lower() == modo.lower())
    )
    sub = df[mask].sort_values("ds")
    sub = sub[sub["ds"] >= "2025-01-01"]

    if sub.empty:
        disponibles = df[["meta_padecimiento", "meta_entidad", "meta_modo"]].drop_duplicates()
        raise ValueError(
            f"No hay datos para ({padecimiento!r}, {entidad!r}, {modo!r}).\n"
            f"Disponibles:\n{disponibles.to_string(index=False)}"
        )

    col_y = "yhat_tasa" if tasa and "yhat_tasa" in sub.columns else "yhat"
    unidad = "casos / 100K hab." if col_y == "yhat_tasa" else "log-rate (Prophet)"

    if ax is None:
        _, ax = plt.subplots(figsize=(12, 4))

    ax.plot(sub["ds"], sub[col_y], color="#005A9C", lw=1.8, label="Pronóstico")
    ax.fill_between(
        sub["ds"],
        sub["yhat_lower"],
        sub["yhat_upper"],
        alpha=0.18,
        color="#005A9C",
        label="IC 80%",
    )

    # Métrica en el título si está disponible
    rmse = sub["rmse_usado"].iloc[0] if "rmse_usado" in sub.columns else None
    mase = sub["mase_usado"].iloc[0] if "mase_usado" in sub.columns else None
    metricas = ""
    if rmse is not None and pd.notna(rmse):
        metricas = f"  |  RMSE={rmse:.3f}  MASE={mase:.2f}" if pd.notna(mase) else f"  |  RMSE={rmse:.3f}"

    ax.set_title(f"{padecimiento} · {entidad} · {modo}{metricas}", fontsize=11)
    ax.set_xlabel("Semana")
    ax.set_ylabel(unidad)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    return ax


def plot_estados(
    padecimiento: str,
    modo: str = "general",
    tasa: bool = True,
    top_n: int = 9,
) -> None:
    """Grilla de los top_n estados por promedio de yhat_tasa.

    Args:
        padecimiento: Condición a graficar.
        modo:         "general" | "hombres" | "mujeres".
        tasa:         Usar yhat_tasa (True) o yhat (False).
        top_n:        Número de estados a mostrar (máx 9 por legibilidad).
    """
    df = _cargar()
    col_y = "yhat_tasa" if tasa and "yhat_tasa" in df.columns else "yhat"

    mask = (
        (df["meta_padecimiento"].str.lower() == padecimiento.lower())
        & (df["meta_modo"].str.lower() == modo.lower())
    )
    sub = df[mask]

    top_entidades = (
        sub.groupby("meta_entidad")[col_y].mean().nlargest(top_n).index.tolist()
    )

    cols = min(3, top_n)
    rows = (top_n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 3.5 * rows), squeeze=False)
    fig.suptitle(f"{padecimiento} · {modo} — Top {top_n} estados", fontsize=13)

    for idx, entidad in enumerate(top_entidades):
        ax = axes[idx // cols][idx % cols]
        try:
            plot_forecast(padecimiento, entidad, modo=modo, tasa=tasa, ax=ax)
            ax.set_title(entidad, fontsize=9)
        except ValueError:
            ax.set_visible(False)

    # Ocultar ejes vacíos
    for idx in range(len(top_entidades), rows * cols):
        axes[idx // cols][idx % cols].set_visible(False)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    # Demo rápido
    plot_forecast("Depresión", "Nacional")
    plt.show()
