"""Completa el ``Deepar_Dengue_completo.csv`` sin re-entrenar ni churnear los .pkl.

El entrenamiento estatal de DeepAR Dengue se hizo en dos fases (64 + 35 por reanudación
tras un corte de macOS), y cada corrida SOBREESCRIBE el ``_completo.csv`` con solo las
series que procesó. Resultado: el CSV quedó con 35 de 99 filas (las 64 primeras se
perdieron del CSV, aunque sus .pkl existen). Esto deja 64 series con ``smape_usado`` NaN
en el forecast (no afecta la selección productiva, que usa SMAPE 2026 real, pero el CSV
queda incompleto).

Este parche recomputa las métricas de las series faltantes con ``_eval_rapida`` (el MISMO
hold-out de 75 epochs que usó el entrenamiento), SIN el fit de producción de 300 epochs y
SIN guardar los .pkl: los modelos y forecasts quedan idénticos. Luego basta re-predecir
DeepAR para rellenar ``smape_usado``.

Uso:
    python -m scripts.patch_deepar_completo_dengue [--limit N]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import time

from omegaconf import OmegaConf
import pandas as pd
from scripts.entrena import normalizar

from epiforecast.models import create_model
from epiforecast.utils.config import conf, logger


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Procesar solo N series (prueba)")
    args = ap.parse_args()

    c = OmegaConf.merge(
        conf, OmegaConf.create({"modelo_activo": "deepar", "padecimiento": {"tipo": "Dengue"}})
    )
    # Rutas derivadas de config (no hardcodeadas): models/<modelo_activo>/Dengue y data_inegi.
    completo = Path(c["paths"]["models"]) / "Dengue" / "Deepar_Dengue_completo.csv"
    data = Path(c["data"]["data_inegi"])
    df = pd.read_csv(data)
    dfp = df[df["Padecimiento"] == "Dengue"]
    valores_sexo = [str(s) for s in c["valores_sexo"]]
    mapeo = {str(k): str(v) for k, v in c["mapeo_columnas"].items()}
    entidades = sorted(dfp["Entidad"].unique())

    existing = pd.read_csv(completo)
    have = set(existing["archivo_modelo"].astype(str))
    logger.info("_completo actual: {} filas", len(existing))

    # (region, sexo) faltantes: Nacional (region=None) + cada entidad, por cada sexo.
    pendientes: list[tuple[str | None, str]] = []
    for region in [None, *entidades]:
        extra = f"_{normalizar(region)}" if region else ""
        for sexo in valores_sexo:
            nombre = f"Deepar_Dengue{extra}_{mapeo.get(sexo, sexo)}.pkl"
            if nombre not in have:
                pendientes.append((region, sexo))
    logger.info("Series faltantes: {}", len(pendientes))
    if args.limit:
        pendientes = pendientes[: args.limit]

    nuevas: list[dict] = []
    for i, (region, sexo) in enumerate(pendientes, 1):
        t0 = time.time()
        extra = f"_{normalizar(region)}" if region else ""
        nombre = f"Deepar_Dengue{extra}_{mapeo.get(sexo, sexo)}.pkl"
        try:
            fc = create_model(
                "deepar", df=dfp, sexo=sexo, entidad=region, padecimiento="Dengue", config=c
            )
            fc.agrupa()
            fc.crea_train_test()
            promedio = fc.promedio_semanal()
            metrics = fc._eval_rapida()
            params = fc.get_params()
        except Exception as e:  # noqa: BLE001 — una serie no debe romper el lote
            logger.warning("Falló {} | {}: {}", region or "Nacional", sexo, e)
            continue

        mape_raw = metrics.get("mape")
        fila = {
            "padecimiento": "Dengue",
            "sexo": sexo,
            "rmse": metrics.get("rmse"),
            "mae": metrics.get("mae"),
            "mape": mape_raw,
            "smape": metrics.get("smape"),
            "mase": metrics.get("mase"),
            "rmse_train": metrics.get("rmse_train"),
            "smape_train": metrics.get("smape_train"),
            "mape_confiable": not (mape_raw is not None and mape_raw >= 999.0),
            **params,
            "archivo_modelo": nombre,
            "nivel": "nacional" if region is None else "regional",
            "confianza": metrics.get("confianza", "normal"),
            "promedio_semanal": round(promedio, 2),
            "tiempo_total_seg": round(time.time() - t0, 1),
            "Entidad": region if region else "Nacional",
        }
        nuevas.append(fila)
        # Escritura incremental: cada serie tarda ~5 min; persistir tras cada una hace el
        # parche resumible (re-correr salta las ya presentes vía `have`).
        merged = pd.concat([existing, pd.DataFrame(nuevas)], ignore_index=True)
        merged = merged.drop_duplicates("archivo_modelo", keep="last").reset_index(drop=True)
        merged.to_csv(completo, index=False, encoding="utf-8")
        logger.info(
            "[{}/{}] {} | {} | SMAPE={} ({:.0f}s) → _completo {} filas",
            i,
            len(pendientes),
            region or "Nacional",
            sexo,
            f"{metrics['smape']:.1f}" if metrics.get("smape") is not None else "N/A",
            fila["tiempo_total_seg"],
            len(merged),
        )

    if not nuevas:
        logger.info("Nada que agregar.")
        return 0
    logger.success(
        "_completo actualizado: +{} filas ({} total)", len(nuevas), len(existing) + len(nuevas)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
