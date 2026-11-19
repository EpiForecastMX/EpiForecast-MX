"""Bloques sin desglose por sexo del extractor de cuadros (separado por el límite de 300 líneas)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from epiforecast import registry
from epiforecast.data.extraction.pdf_extractor import normalize_number


def extrae_sin_sexo(
    out: dict[str, Any],
    df_clean: pd.DataFrame,
    spec: dict[str, Any],
    disease_id: str,
    year: int,
    week: int,
) -> dict[str, Any]:
    """Bloques sin desglose por sexo: Sem, acumulado del año y acumulado del anterior.

    El cuadro puede traer varios padecimientos sin sexo en bloques de 3 columnas; se toma el bloque
    del padecimiento por su ``block_index``. ``anchos_sin_sexo`` declara otros anchos por bloque
    (2 = Sem y acumulado, sin año anterior, como en los boletines de 2014 del Cuadro 13.5).
    """
    bloques = spec.get("diseases") or [{"id": disease_id, "block_index": 0}]
    anchos = [int(a) for a in spec.get("anchos_sin_sexo") or [3] * len(bloques)]
    if len(anchos) != len(bloques) or any(a not in (2, 3) for a in anchos):
        out["reason"] = f"anchos_sin_sexo inválidos: {anchos} para {len(bloques)} bloques"
        return out
    if df_clean.shape[1] - 1 != sum(anchos):
        out["reason"] = (
            f"columnas inesperadas: {df_clean.shape[1] - 1} (esperaba {sum(anchos)}, sin sexo)"
        )
        return out
    bloque = next((int(d["block_index"]) for d in bloques if d["id"] == disease_id), 0)
    inicio = 1 + sum(anchos[:bloque])
    ancho = anchos[bloque]
    anterior = (
        [normalize_number(v) for v in df_clean.iloc[:, inicio + 2]]
        if ancho == 3
        else [None] * len(df_clean)
    )
    out["layout"] = "3col_total" if ancho == 3 else "2col_total_noprev"
    df_dis = pd.DataFrame(
        {
            "Anio": year,
            "Semana": f"{week:02d}",
            "Entidad": df_clean.iloc[:, 0].to_numpy(),
            "Padecimiento": registry.require(disease_id).data_name,
            "Casos_semana": [normalize_number(v) for v in df_clean.iloc[:, inicio]],
            "Acumulado_total": [normalize_number(v) for v in df_clean.iloc[:, inicio + 1]],
            "Acumulado_anio_anterior": anterior,
        }
    )
    n_states = int(df_dis["Entidad"].nunique())
    out["df"] = df_dis.reset_index(drop=True)
    out["n_states"] = n_states
    out["valid"] = n_states == int(spec.get("n_states_expected", 32))
    out["reason"] = "ok" if out["valid"] else f"{n_states} estados (esperaba 32)"
    return out
