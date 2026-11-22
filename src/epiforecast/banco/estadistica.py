"""Pruebas estadísticas para comparar motores entre padecimientos (sólo métricas de desarrollo).

Unidad de análisis: el padecimiento. Cada padecimiento aporta una cifra pareada por motor (la media
de su sMAPE nacional de desarrollo), así que las pruebas son no paramétricas y pareadas:

- Wilcoxon de rangos con signo (Pratt para los empates en cero) con tamaño de efecto de
  correlación biserial de rangos y corrección de Holm para comparaciones múltiples.
- Prueba del signo (binomial exacta) como respaldo sin supuesto de simetría.
- IC bootstrap percentil de la mediana de la mejora relativa.
- Friedman con la corrección de Iman y Davenport, rangos medios y diferencia crítica de Nemenyi
  (Demšar, 2006) para el diagrama de diferencias críticas.
Diebold-Mariano se retiró por dictamen de la mesa de expertos: con un solo origen por pliegue la
serie de pérdidas mezcla horizontes de 1 a 52 semanas y no es estacionaria.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

Arr = np.ndarray[Any, Any]


def holm(pvalores: list[float]) -> list[float]:
    """p ajustados de Holm-Bonferroni (monótonos y acotados en 1), en el orden de entrada."""
    p = np.asarray(pvalores, dtype=float)
    m = len(p)
    orden = np.argsort(p)
    ajustados = np.empty(m)
    acumulado = 0.0
    for rango, i in enumerate(orden):
        acumulado = max(acumulado, min(1.0, (m - rango) * p[i]))
        ajustados[i] = acumulado
    return ajustados.tolist()


def wilcoxon_pareado(a: Arr, b: Arr) -> dict[str, float]:
    """Wilcoxon bilateral de ``a`` frente a ``b`` (diferencia a - b; negativo = a mejor)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    d = a[ok] - b[ok]
    n = int(len(d))
    if n < 6 or np.all(d == 0):
        return {"n": n, "W": np.nan, "p": np.nan, "r_rb": np.nan, "mediana_dif": np.nan}
    res = stats.wilcoxon(d, zero_method="pratt", alternative="two-sided", method="auto")
    nz = d[d != 0]
    rangos = stats.rankdata(np.abs(nz))
    r_rb = float((rangos[nz > 0].sum() - rangos[nz < 0].sum()) / rangos.sum())
    return {
        "n": n,
        "W": float(res.statistic),
        "p": float(res.pvalue),
        "r_rb": r_rb,
        "mediana_dif": float(np.median(d)),
    }


def prueba_signo(a: Arr, b: Arr) -> dict[str, float]:
    """Binomial exacta bilateral sobre cuántos padecimientos ``a`` < ``b`` (empates fuera)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    gana, pierde = int((a[ok] < b[ok]).sum()), int((a[ok] > b[ok]).sum())
    if gana + pierde == 0:
        return {"gana": 0, "pierde": 0, "p": np.nan}
    p = float(stats.binomtest(gana, gana + pierde, 0.5).pvalue)
    return {"gana": gana, "pierde": pierde, "p": p}


def bootstrap_mejora(
    a: Arr, b: Arr, repeticiones: int = 10_000, semilla: int = 20261122, nivel: float = 0.95
) -> dict[str, float]:
    """IC percentil de la mediana de (a / b - 1) en %, remuestreando padecimientos."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b) & (b > 0)
    r = (a[ok] / b[ok] - 1.0) * 100.0
    if len(r) < 6:
        return {"mediana_pct": np.nan, "ic_bajo": np.nan, "ic_alto": np.nan}
    rng = np.random.default_rng(semilla)
    meds = np.median(rng.choice(r, size=(repeticiones, len(r)), replace=True), axis=1)
    cola = (1 - nivel) / 2 * 100
    lo, hi = np.percentile(meds, [cola, 100 - cola])
    return {"mediana_pct": float(np.median(r)), "ic_bajo": float(lo), "ic_alto": float(hi)}


def friedman_nemenyi(tabla: pd.DataFrame, alfa: float = 0.05) -> dict[str, Any]:
    """Friedman sobre padecimientos (filas) × motores (columnas) completos; menor es mejor."""
    t = tabla.dropna(axis=0, how="any")
    n, k = t.shape
    if n < 2 or k < 3:
        raise ValueError("Friedman requiere al menos 2 padecimientos y 3 motores completos")
    rangos = t.rank(axis=1, method="average")
    medios = rangos.mean(axis=0).sort_values()
    chi2 = 12 * n / (k * (k + 1)) * (np.sum(medios.to_numpy() ** 2) - k * (k + 1) ** 2 / 4)
    empates = sum(
        float(((c**3) - c).sum())
        for c in (pd.Series(fila).value_counts().to_numpy() for fila in t.to_numpy())
    )
    chi2 /= 1 - empates / (n * k * (k**2 - 1))  # corrección por empates (Conover)
    p_chi2 = float(stats.chi2.sf(chi2, k - 1))
    f_id = (n - 1) * chi2 / (n * (k - 1) - chi2) if n * (k - 1) != chi2 else np.inf
    p_id = float(stats.f.sf(f_id, k - 1, (k - 1) * (n - 1)))
    q = float(stats.studentized_range.ppf(1 - alfa, k, np.inf)) / np.sqrt(2)
    cd = q * np.sqrt(k * (k + 1) / (6 * n))
    return {
        "padecimientos": int(n),
        "motores": int(k),
        "chi2": float(chi2),
        "p_chi2": p_chi2,
        "F_iman_davenport": float(f_id),
        "p_iman_davenport": p_id,
        "q_alfa": q,
        "diferencia_critica": float(cd),
        "rangos_medios": {str(e): round(float(v), 4) for e, v in medios.items()},
    }


def contra_referencia(tabla: pd.DataFrame, referencia: str, alfa: float = 0.05) -> pd.DataFrame:
    """Cada motor frente a ``referencia``: Wilcoxon + Holm, signo e IC bootstrap de la mejora."""
    filas = []
    for e in tabla.columns:
        a, b = tabla[e].to_numpy(), tabla[referencia].to_numpy()
        ok = np.isfinite(a) & np.isfinite(b)
        if e == referencia or ok.sum() == 0 or np.array_equal(a[ok], b[ok]):
            continue  # la referencia misma, un motor sin datos o idéntico a ella
        w, s, bs = wilcoxon_pareado(a, b), prueba_signo(a, b), bootstrap_mejora(a, b)
        fila: dict[str, Any] = {"engine": str(e), "referencia": referencia}
        filas.append(
            fila
            | {f"wilcoxon_{k}": v for k, v in w.items()}
            | {f"signo_{k}": v for k, v in s.items()}
            | bs
        )
    df = pd.DataFrame(filas)
    validos = df["wilcoxon_p"].notna()
    df["wilcoxon_p_holm"] = np.nan
    df.loc[validos, "wilcoxon_p_holm"] = holm(df.loc[validos, "wilcoxon_p"].tolist())
    df["significativo_holm"] = df["wilcoxon_p_holm"] < alfa
    df["veredicto"] = np.select(
        [
            df["significativo_holm"] & (df["wilcoxon_r_rb"] < 0),
            df["significativo_holm"] & (df["wilcoxon_r_rb"] > 0),
        ],
        ["mejor", "peor"],
        default="sin diferencia",
    )
    return df.sort_values("wilcoxon_mediana_dif").reset_index(drop=True)
