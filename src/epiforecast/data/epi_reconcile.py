"""F1/C1 — reconciliación PURA del target semanal E66 (contrato cerrado).

Determinista, **causal** (nunca usa datos futuros) y **order-invariant** (ordena internamente por
``(epi_year, epi_week, cve_ent)``). Produce el frame ESTATAL reconciliado (una fila por periodo
objetivo × entidad) con el total reconciliado, la partición por sexo entera (mayor residuo,
``hombres+mujeres=total``) y las ``quality_flags``.

Reglas (plan §"Contrato cerrado de reconciliación"):

1. Calendario ya aplicado aguas arriba; aquí se calculan deltas por entidad y epi_year objetivo.
2. Delta sexual válido ⇔ snapshots actual y anterior consecutivos y válidos (en W01 baseline=0),
   ``dH``/``dM`` finitos y no negativos, ``dH+dM>0``.
3. Si ``dH+dM != Casos_semana`` se usa igualmente ``dH/(dH+dM)`` y se anota ``sex_delta_total``,
   ``sex_delta_residual`` y la flag ``sex_delta_total_mismatch`` (NO se descarta la observación).
4. Colapso 32/32 en cero entre semanas nacionales no nulas ⇒ ``source_missing`` (total imputado);
   la semana siguiente hereda ``predecessor_snapshot_invalid`` (delta inválido → fallback sexual);
   luego se reanuda. Detección solo con el periodo actual + historia previa.
5. ``Casos_semana`` faltante (p.ej. Querétaro) ⇒ total imputado + fallback sexual; el acumulado se
   conserva como snapshot válido para reanudar.
6. Imputación causal del total: mediana de la misma entidad y semana epidemiológica en años
   previos → fallback mediana de las 13 semanas observadas previas → si no hay base causal, falla.
7. Fallback sexual: mediana de las últimas 13 proporciones crudas VÁLIDAS del estado → proporción
   nacional previa (deltas válidos) → 0.5 sin historia. No se alimenta el historial con imputadas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

import pandas as pd

from epiforecast.data.epi_dataset_spec import QualityFlag

# Columnas de entrada esperadas (una fila por periodo objetivo × entidad).
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


def largest_remainder_split(total: int, prop_h: float) -> tuple[int, int]:
    """Reparte ``total`` en ``(h, m)`` por mayor residuo; garantiza ``h+m==total`` (2 partes).

    Determinista: en empate de fracción, el residuo va a ``h``. Soporta ``total`` negativo
    (revisiones conservadas) preservando la suma.
    """
    if total == 0:
        return 0, 0
    raw_h = total * prop_h
    raw_m = total - raw_h
    fh, fm = math.floor(raw_h), math.floor(raw_m)
    remainder = total - (fh + fm)  # 0 o 1
    for _ in range(remainder):
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


class ReconcileError(ValueError):
    """No hay base causal para imputar un total (falla el gate)."""


@dataclass
class _EntState:
    prev_acum_h: float | None = None
    prev_acum_m: float | None = None
    prev_valid: bool = False  # ¿el periodo inmediatamente anterior fue snapshot válido?
    prop_history: list[float] = field(default_factory=list)  # proporciones crudas VÁLIDAS
    obs_by_week: dict[int, list[int]] = field(
        default_factory=dict
    )  # epi_week -> totales de años previos
    last_obs: list[int] = field(default_factory=list)  # últimos totales observados (rolling)


def _impute_total(epi_week: int, st: _EntState) -> int:
    """Mediana de la misma semana epi en años previos → mediana de 13 obs previas → falla."""
    prior_same_week = st.obs_by_week.get(epi_week, [])
    if prior_same_week:
        return int(round(_median([float(x) for x in prior_same_week])))
    if st.last_obs:
        return int(round(_median([float(x) for x in st.last_obs[-13:]])))
    raise ReconcileError(f"sin base causal para imputar total (epi_week={epi_week})")


def _sex_fallback(st: _EntState, nat_dh: float, nat_dhm: float) -> tuple[float, str]:
    """Proporción masculina de fallback + la flag correspondiente."""
    valid = st.prop_history[-13:]
    if valid:
        return _median(valid), QualityFlag.SEX_FALLBACK_STATE_13W
    if nat_dhm > 0:
        return nat_dh / nat_dhm, QualityFlag.SEX_FALLBACK_NATIONAL
    return 0.5, QualityFlag.SEX_FALLBACK_HALF


def _is_finite_nonneg(x: float) -> bool:
    return math.isfinite(x) and x >= 0


def reconcile_state(prep: pd.DataFrame) -> pd.DataFrame:
    """Reconcilia el frame estatal (una fila por periodo objetivo × entidad)."""
    missing = [c for c in IN_COLS if c not in prep.columns]
    if missing:
        raise ReconcileError(f"faltan columnas de entrada: {missing}")

    df = prep.sort_values(["epi_year", "epi_week", "cve_ent"]).reset_index(drop=True)

    # source_missing por periodo: total nacional 0 (32/32 en cero) con periodo previo > 0 (causal).
    nat = (
        df.assign(_c=df["casos_source"].fillna(0.0))
        .groupby(["epi_year", "epi_week"], sort=True)["_c"]
        .sum()
    )
    periods = list(nat.index)
    source_missing: dict[tuple[int, int], bool] = {}
    prev_nat = None
    for p in periods:
        source_missing[p] = bool(nat[p] == 0 and prev_nat is not None and prev_nat > 0)
        prev_nat = nat[p]

    states: dict[str, _EntState] = {}
    nat_dh = nat_dhm = 0.0  # deltas válidos de periodos ESTRICTAMENTE previos (order-invariant)
    out_rows: list[dict[str, object]] = []

    for p in periods:
        block = df[(df["epi_year"] == p[0]) & (df["epi_week"] == p[1])]
        pend_dh = pend_dhm = 0.0  # deltas válidos de ESTE periodo (se funden tras terminarlo)
        for r in block.itertuples(index=False):
            cve = str(r.cve_ent)
            st = states.setdefault(cve, _EntState())
            epi_week = int(r.epi_week)
            flags: list[str] = []

            # ── baseline y delta ──
            if epi_week == 1:
                base_h, base_m, base_valid = 0.0, 0.0, True
            else:
                base_h = st.prev_acum_h if st.prev_acum_h is not None else float("nan")
                base_m = st.prev_acum_m if st.prev_acum_m is not None else float("nan")
                base_valid = st.prev_valid
            acum_h, acum_m = float(r.acum_h), float(r.acum_m)
            acum_valid = (
                not source_missing[p] and _is_finite_nonneg(acum_h) and _is_finite_nonneg(acum_m)
            )
            if base_valid and acum_valid:
                dh, dm = acum_h - base_h, acum_m - base_m
                delta_valid = _is_finite_nonneg(dh) and _is_finite_nonneg(dm) and (dh + dm) > 0
            else:
                dh = dm = float("nan")
                delta_valid = False
            if not base_valid and epi_week != 1:
                flags.append(QualityFlag.PREDECESSOR_SNAPSHOT_INVALID)

            # ── total (observado o imputado causalmente) ──
            casos = r.casos_source
            if source_missing[p] or pd.isna(casos):
                total = _impute_total(epi_week, st)
                observed = False
                flags.append(QualityFlag.TOTAL_IMPUTED)
                if source_missing[p]:
                    flags.append(QualityFlag.SOURCE_MISSING)
            else:
                total = int(casos)
                observed = True
                if total < 0:
                    flags.append(QualityFlag.NEGATIVE_SOURCE)

            # ── proporción sexual ──
            use_delta = delta_valid and observed
            sex_delta_total = float(dh + dm) if delta_valid else float("nan")
            if use_delta:
                prop_source = dh / (dh + dm)
                prop_applied = prop_source
                sex_delta_residual = float((dh + dm) - total)
                if (dh + dm) != total:
                    flags.append(QualityFlag.SEX_DELTA_TOTAL_MISMATCH)
                st.prop_history.append(prop_source)  # solo válidas, no imputadas
                pend_dh += dh
                pend_dhm += dh + dm
            else:
                prop_source = float("nan")
                sex_delta_residual = float("nan")
                prop_applied, fb = _sex_fallback(st, nat_dh, nat_dhm)
                flags.append(fb)

            y_h, y_m = largest_remainder_split(total, prop_applied)

            # ── actualizar estado (causal) ──
            if acum_valid:
                st.prev_acum_h, st.prev_acum_m, st.prev_valid = acum_h, acum_m, True
            else:
                st.prev_valid = False  # colapso: el snapshot no sirve de baseline
            if observed:
                st.obs_by_week.setdefault(epi_week, []).append(total)
                st.last_obs.append(total)

            out_rows.append(
                {
                    "cve_ent": cve,
                    "source_year": int(r.source_year),
                    "source_week": int(r.source_week),
                    "epi_year": p[0],
                    "epi_week": p[1],
                    "period_start": r.period_start,
                    "ds": r.ds,
                    "total_source": (None if pd.isna(casos) else int(casos)),
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
        nat_dh += pend_dh
        nat_dhm += pend_dhm

    return pd.DataFrame(out_rows)
