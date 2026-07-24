"""F1/C1 — reconciliación PURA del target semanal E66 (contrato cerrado + ajustes C1-2c).

Determinista, **causal** (nunca usa datos futuros) y **order-invariant** (ordena internamente por
``(epi_year, epi_week, cve_ent)``). Produce el frame ESTATAL reconciliado (una fila por periodo
objetivo × entidad) con el total reconciliado, la partición por sexo entera (mayor residuo,
``hombres+mujeres=total``) y las ``quality_flags``.

Reglas:

1. Calendario ya aplicado aguas arriba; aquí se calculan deltas por entidad y epi_year objetivo.
2. Delta sexual válido ⇔ snapshots actual y anterior consecutivos y válidos (en W01 baseline=0),
   ``dH``/``dM`` finitos y no negativos, ``dH+dM>0``.
3. Si ``dH+dM != Casos_semana`` se usa igualmente ``dH/(dH+dM)`` y se anota ``sex_delta_total``,
   ``sex_delta_residual`` y la flag ``sex_delta_total_mismatch`` (NO se descarta la observación).
4. ``source_missing`` requiere POLÍTICA (no basta el cero nacional): todas las entidades esperadas
   presentes + todos los totales en cero + colapso simultáneo de acumulados + no ser W01. La semana
   siguiente hereda ``predecessor_snapshot_invalid`` → fallback sexual; luego se reanuda.
5. ``Casos_semana`` faltante ⇒ total imputado + fallback sexual (snapshot acumulado conservado).
6. Totales: enteros finitos no negativos. Un negativo se PRESERVA como fuente/flag pero se trata por
   imputación (``y_cases`` nunca < 0); un fraccionario FALLA el gate. Imputación causal: mediana de
   la misma semana epi en años previos → mediana de los 13 PERIODOS CALENDARIO previos observados →
   si no hay base causal, falla. Redondeo half-up determinista (no ``round`` bancario).
7. Fallback sexual causal: mediana de proporciones válidas en los 13 PERIODOS CALENDARIO previos →
   proporción nacional del PERIODO INMEDIATAMENTE ANTERIOR (deltas válidos) → 0.5 sin historia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

import pandas as pd

from epiforecast.data.epi_dataset_spec import QualityFlag

_WINDOW = 13  # periodos calendario para las medianas de fallback/imputación

IN_COLS = (
    "cve_ent",
    "source_year",
    "source_week",
    "epi_year",
    "epi_week",
    "period_start",
    "ds",
    "casos_source",
    "acum_h",
    "acum_m",
)


class ReconcileError(ValueError):
    """Entrada inválida (columna faltante, total fraccionario/no finito) o sin base causal."""


def largest_remainder_split(total: int, prop_h: float) -> tuple[int, int]:
    """Reparte ``total`` en ``(h, m)`` por mayor residuo; garantiza ``h+m==total`` (2 partes).

    Determinista: en empate de fracción, el residuo va a ``h``. Preserva la suma incluso si
    ``total`` fuese negativo (no ocurre en el flujo: los negativos se imputan a ≥0).
    """
    if total == 0:
        return 0, 0
    raw_h = total * prop_h
    raw_m = total - raw_h
    fh, fm = math.floor(raw_h), math.floor(raw_m)
    for _ in range(total - (fh + fm)):
        if (raw_h - fh) >= (raw_m - fm):
            fh += 1
        else:
            fm += 1
    return fh, fm


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _round_half_up(x: float) -> int:
    """Half-up determinista para valores no negativos (imputaciones)."""
    return math.floor(x + 0.5)


def _is_finite_nonneg(x: float) -> bool:
    return math.isfinite(x) and x >= 0


@dataclass
class _EntState:
    prev_acum_h: float | None = None
    prev_acum_m: float | None = None
    prev_valid: bool = False  # ¿el periodo inmediatamente anterior fue snapshot válido?
    props_at: dict[int, float] = field(default_factory=dict)  # period_index -> prop cruda VÁLIDA
    obs_at: dict[int, int] = field(default_factory=dict)  # period_index -> total OBSERVADO
    by_week: dict[int, list[int]] = field(
        default_factory=dict
    )  # epi_week -> totales de años previos


def _window_values(store: dict[int, float], i: int) -> list[float]:
    return [store[j] for j in range(max(0, i - _WINDOW), i) if j in store]


def _impute_total(epi_week: int, i: int, st: _EntState) -> int:
    """Mediana de la misma semana epi en años previos → mediana de 13 periodos previos → falla."""
    prior_same_week = st.by_week.get(epi_week, [])
    if prior_same_week:
        return _round_half_up(_median([float(x) for x in prior_same_week]))
    window = [float(st.obs_at[j]) for j in range(max(0, i - _WINDOW), i) if j in st.obs_at]
    if window:
        return _round_half_up(_median(window))
    raise ReconcileError(f"sin base causal para imputar total (epi_week={epi_week}, i={i})")


def _sex_fallback(i: int, st: _EntState, nat_prev: tuple[float, float]) -> tuple[float, str]:
    """Proporción masculina de fallback + flag (13 periodos del estado → nacional previa → 0.5)."""
    window = _window_values(st.props_at, i)
    if window:
        return _median(window), QualityFlag.SEX_FALLBACK_STATE_13W
    n_dh, n_dhm = nat_prev
    if n_dhm > 0:
        return n_dh / n_dhm, QualityFlag.SEX_FALLBACK_NATIONAL
    return 0.5, QualityFlag.SEX_FALLBACK_HALF


def _detect_source_missing(
    periods: list[tuple[int, int]],
    blocks: dict[tuple[int, int], pd.DataFrame],
    expected: set[str],
) -> dict[tuple[int, int], bool]:
    """Política de fuente faltante: esperadas presentes + todos en cero + colapso de acumulados +
    no W01. Solo periodo actual + inmediatamente anterior (causal)."""
    acum_total: dict[tuple[int, str], float] = {}
    present: list[set[str]] = []
    for i, p in enumerate(periods):
        b = blocks[p]
        present.append(set(b["cve_ent"].astype(str)))
        for r in b.itertuples(index=False):
            acum_total[(i, str(r.cve_ent))] = float(r.acum_h) + float(r.acum_m)  # type: ignore[arg-type]
    out: dict[tuple[int, int], bool] = {}
    for i, p in enumerate(periods):
        b = blocks[p]
        casos = b["casos_source"]
        all_zero = bool(casos.notna().all() and (casos == 0).all())
        expected_present = present[i] == expected
        not_w1 = p[1] != 1
        collapse = i > 0 and all(
            cve in present[i - 1] and acum_total[(i, cve)] < acum_total[(i - 1, cve)]
            for cve in present[i]
        )
        out[p] = not_w1 and expected_present and all_zero and collapse
    return out


def reconcile_state(prep: pd.DataFrame, expected_cve_ents: set[str]) -> pd.DataFrame:
    """Reconcilia el frame estatal (una fila por periodo objetivo × entidad).

    ``expected_cve_ents`` = el conjunto de entidades esperadas del padecimiento (política de
    ``source_missing``); nunca se infiere de los datos.
    """
    missing = [c for c in IN_COLS if c not in prep.columns]
    if missing:
        raise ReconcileError(f"faltan columnas de entrada: {missing}")

    df = prep.sort_values(["epi_year", "epi_week", "cve_ent"]).reset_index(drop=True)
    periods = [
        tuple(x) for x in df[["epi_year", "epi_week"]].drop_duplicates().to_numpy().tolist()
    ]
    blocks = {p: df[(df["epi_year"] == p[0]) & (df["epi_week"] == p[1])] for p in periods}
    source_missing = _detect_source_missing(periods, blocks, set(expected_cve_ents))

    states: dict[str, _EntState] = {}
    national_at: dict[int, tuple[float, float]] = {}
    out_rows: list[dict[str, object]] = []

    for i, p in enumerate(periods):
        epi_week = p[1]
        sm = source_missing[p]
        nat_prev = national_at.get(i - 1, (0.0, 0.0))
        pend_dh = pend_dhm = 0.0
        for r in blocks[p].itertuples(index=False):
            cve = str(r.cve_ent)
            st = states.setdefault(cve, _EntState())
            flags: list[str] = []

            # ── baseline y delta ──
            if epi_week == 1:
                base_h, base_m, base_valid = 0.0, 0.0, True
            else:
                base_h = st.prev_acum_h if st.prev_acum_h is not None else float("nan")
                base_m = st.prev_acum_m if st.prev_acum_m is not None else float("nan")
                base_valid = st.prev_valid
            acum_h, acum_m = float(r.acum_h), float(r.acum_m)
            acum_valid = not sm and _is_finite_nonneg(acum_h) and _is_finite_nonneg(acum_m)
            if base_valid and acum_valid:
                dh, dm = acum_h - base_h, acum_m - base_m
                delta_valid = _is_finite_nonneg(dh) and _is_finite_nonneg(dm) and (dh + dm) > 0
            else:
                dh = dm = float("nan")
                delta_valid = False
            if not base_valid and epi_week != 1:
                flags.append(QualityFlag.PREDECESSOR_SNAPSHOT_INVALID)

            # ── total: entero finito no negativo; negativo/NA/colapso → imputado ──
            casos = r.casos_source
            impute = sm or bool(pd.isna(casos))
            if not impute:
                c = float(casos)
                if not math.isfinite(c):
                    raise ReconcileError(f"Casos_semana no finito en {cve} {p}: {casos!r}")
                if not c.is_integer():
                    raise ReconcileError(f"Casos_semana fraccionario en {cve} {p}: {casos!r}")
                if c < 0:
                    impute = True
                    flags.append(QualityFlag.NEGATIVE_SOURCE)
            if impute:
                total = _impute_total(epi_week, i, st)
                observed = False
                flags.append(QualityFlag.TOTAL_IMPUTED)
                if sm:
                    flags.append(QualityFlag.SOURCE_MISSING)
            else:
                total = int(float(casos))
                observed = True

            # ── proporción sexual ──
            use_delta = delta_valid and observed
            sex_delta_total = float(dh + dm) if delta_valid else float("nan")
            if use_delta:
                prop_source = dh / (dh + dm)
                prop_applied = prop_source
                sex_delta_residual = float((dh + dm) - total)
                if (dh + dm) != total:
                    flags.append(QualityFlag.SEX_DELTA_TOTAL_MISMATCH)
                st.props_at[i] = prop_source  # solo válidas, no imputadas
                pend_dh += dh
                pend_dhm += dh + dm
            else:
                prop_source = float("nan")
                sex_delta_residual = float("nan")
                prop_applied, fb = _sex_fallback(i, st, nat_prev)
                flags.append(fb)

            y_h, y_m = largest_remainder_split(total, prop_applied)

            # ── actualizar estado (causal) ──
            if acum_valid:
                st.prev_acum_h, st.prev_acum_m, st.prev_valid = acum_h, acum_m, True
            else:
                st.prev_valid = False  # colapso: el snapshot no sirve de baseline
            if observed:
                st.obs_at[i] = total
                st.by_week.setdefault(epi_week, []).append(total)

            out_rows.append(
                {
                    "cve_ent": cve,
                    "source_year": int(r.source_year),
                    "source_week": int(r.source_week),
                    "epi_year": p[0],
                    "epi_week": p[1],
                    "period_start": r.period_start,
                    "ds": r.ds,
                    "total_source": (None if pd.isna(casos) else int(float(casos))),
                    "total_reconciled": int(total),
                    "observed": bool(observed),
                    "y_hombres": int(y_h),
                    "y_mujeres": int(y_m),
                    "sex_prop_source": prop_source,
                    "sex_prop_applied": float(prop_applied),
                    "sex_delta_total": sex_delta_total,
                    "sex_delta_residual": sex_delta_residual,
                    "quality_flags": "|".join(flags),
                }
            )
        national_at[i] = (pend_dh, pend_dhm)

    return pd.DataFrame(out_rows)
