# scripts/predice.py
from pathlib import Path
import re
import unicodedata

import pandas as pd

from epiforecast.models.prediction import ForecastModelLoader
from epiforecast.utils import paths as directory_manager
from epiforecast.utils.cohorts import is_count_log_cohort
from epiforecast.utils.config import conf, logger
from epiforecast.visualization.forecast_plots import generar_graficos_pronostico


def _normalizar(s: str) -> str:
    """Normaliza para nombres de archivo (debe coincidir con entrena.normalizar)."""
    out = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    out = out.replace("/", "-")
    return re.sub(r"\s+", "_", out)


def parse_nombre_modelo(stem: str) -> dict:
    """Extrae metadatos del nombre del archivo .pkl.

    Formato esperado: {Modelo}_{padecimiento}[_{entidad}]_{modo}
    Ejemplo: Prophet_Alzheimer_Nuevo_Leon_hombres
    """
    parts = stem.split("_")
    if len(parts) < 3:
        raise ValueError(f"Nombre de modelo inesperado: {stem!r}")

    modelo = parts[0]
    padecimiento = parts[1]
    modo = parts[-1]
    entidad = " ".join(parts[2:-1]) if len(parts) > 3 else "Nacional"

    return {
        "meta_modelo": modelo,
        "meta_padecimiento": padecimiento,
        "meta_entidad": entidad,
        "meta_modo": modo,
    }


def estandarizar_valores(df: pd.DataFrame) -> pd.DataFrame:
    import unicodedata

    # Normaliza texto para poder comparar minúsculas, sin acentos, sin espacios extra
    def key(x) -> str:
        s = "" if x is None else str(x).strip().lower()
        s = unicodedata.normalize("NFKD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))
        return " ".join(s.split())

    # Diccionario de estandarización de padecimientos
    # clave: forma normalizada
    # valor: forma final deseada
    padecimientos_map = {
        "depresion": "Depresión",
    }

    # Diccionario de estandarización de entidades
    entidades_map = {
        "ciudad de mexico": "Ciudad de México",
        "mexico": "México",
        "michoacan": "Michoacán",
        "nuevo leon": "Nuevo León",
        "queretaro": "Querétaro",
        "san luis potosi": "San Luis Potosí",
        "yucatan": "Yucatán",
    }

    # Aplica la estandarización a las columnas relevantes
    # Solo modifica el valor si existe en el diccionario
    for col, mapping in [
        ("meta_padecimiento", padecimientos_map),
        ("Padecimiento", padecimientos_map),
        ("meta_entidad", entidades_map),
        ("Entidad", entidades_map),
    ]:
        if col in df.columns:
            df[col] = df[col].map(lambda v, m=mapping: m.get(key(v), v))

    return df


def _parse_regional(stem: str) -> dict:
    """Extrae metadatos de un modelo regional.

    Formato: {Modelo}_{padecimiento}_region_{region_parts}_{modo}
    Ejemplo: Prophet_Alzheimer_region_Sur-Sureste_vulnerable_general
    Returns: {"meta_padecimiento": ..., "meta_entidad": "Region ...", "meta_modo": ...}
    """
    parts = stem.split("_")
    padecimiento = parts[1]
    modo = parts[-1]
    # Todo entre "region" y el último part es el nombre de la región
    idx_region = parts.index("region")
    region_parts = parts[idx_region + 1 : -1]
    region_name = " ".join(region_parts).replace("- ", "/ ")
    return {
        "meta_padecimiento": padecimiento,
        "meta_entidad": f"Region {region_name}",
        "meta_modo": modo,
    }


def _cargar_mapeo_hibrido(base_models: Path, padecimiento_sin_acento: str = "") -> dict:
    """Lee _completo.csv de cada padecimiento y construye mapeo hibrido.

    Returns:
        dict: {stem_insuficiente: {"pkl_regional": str, "poblacion": float, "entidad": str}}
              Solo incluye modelos insuficientes que tienen usar_regional asignado.
    """
    mapeo = {}
    folder_pad = (
        base_models / padecimiento_sin_acento
        if padecimiento_sin_acento and (base_models / padecimiento_sin_acento).exists()
        else base_models
    )

    for csv_path in sorted(folder_pad.rglob("*_completo.csv")):
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            continue
        if "usar_regional" not in df.columns:
            continue
        for _, row in df.iterrows():
            if pd.notna(row.get("usar_regional")) and row.get("confianza") == "insuficiente":
                stem = row["archivo_modelo"].replace(".pkl", "")
                mapeo[stem] = {
                    "pkl_regional": row["usar_regional"],
                    "poblacion": row.get("poblacion"),
                    "entidad": row.get("Entidad"),
                    "padecimiento": row.get("padecimiento"),
                    "sexo": row.get("sexo"),
                }
    return mapeo


def _cargar_metricas_completos(
    base_models: Path, padecimiento_sin_acento: str = ""
) -> pd.DataFrame:
    frames = []
    folder_pad = (
        base_models / padecimiento_sin_acento
        if padecimiento_sin_acento and (base_models / padecimiento_sin_acento).exists()
        else base_models
    )

    for csv_path in sorted(folder_pad.rglob("*_completo.csv")):
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            continue
        if "archivo_modelo" not in df.columns:
            continue
        df["archivo_modelo"] = df["archivo_modelo"].astype(str)

        cols = [
            c
            for c in [
                "archivo_modelo",
                "rmse",
                "mae",
                "mape",
                "smape",
                "mase",
                "confianza",
                "normalizado",
                "poblacion",
            ]
            if c in df.columns
        ]
        frames.append(df[cols].copy())

    if not frames:
        return pd.DataFrame(columns=["archivo_modelo"])

    return pd.concat(frames, ignore_index=True).drop_duplicates("archivo_modelo")


def main():
    periodo = conf["prediccion"]["periodo"]
    base_models = Path(conf["paths"]["models"])
    out_file = Path(conf["data"]["forecast"])
    modelado_hibrido = bool(conf["padecimiento"].get("modelado_hibrido", False))

    directory_manager.asegurar_ruta(out_file.parent)

    # Filtrar por padecimiento si no es General
    padecimiento_tipo = str(conf["padecimiento"]["tipo"]).replace(" ", "_")
    padecimiento_sin_acento = "".join(
        c
        for c in unicodedata.normalize("NFD", padecimiento_tipo)
        if unicodedata.category(c) != "Mn"
    )

    if padecimiento_tipo == "General":
        modelos = sorted(base_models.rglob("*.pkl"))
    else:
        # En caso de estar particionado por directorios
        folder_pad = base_models / padecimiento_sin_acento
        if folder_pad.exists():
            modelos = sorted(folder_pad.rglob("*.pkl"))
        else:
            # Fallback en caso de que estén en la raíz (ej. Prophet_Depresión_...)
            modelos = [
                p
                for p in base_models.rglob("*.pkl")
                if padecimiento_sin_acento
                in "".join(
                    c
                    for c in unicodedata.normalize("NFD", p.stem)
                    if unicodedata.category(c) != "Mn"
                )
            ]
    total = len(modelos)
    if total == 0:
        raise FileNotFoundError(f"No se encontraron modelos .pkl en: {base_models}")

    # Cargar mapeo híbrido si aplica
    mapeo_hibrido = (
        _cargar_mapeo_hibrido(
            base_models, padecimiento_sin_acento if padecimiento_tipo != "General" else ""
        )
        if modelado_hibrido
        else {}
    )
    stems_insuf = set(mapeo_hibrido.keys())
    # Modelos region_* — se identifican para predicción standalone
    modelo_activo = conf.get("modelo_activo", "prophet").capitalize()
    pkls_regional = [
        pkl
        for pkl in modelos
        if pkl.stem.startswith(f"{modelo_activo}_") and "_region_" in pkl.stem
    ]
    stems_regional = {pkl.stem for pkl in pkls_regional}

    if mapeo_hibrido:
        logger.info(
            "Modo híbrido activo: {} modelos insuficientes con fallback regional",
            len(mapeo_hibrido),
        )

    logger.info(
        "Modelos detectados: {} | periodo: {} semanas | salida: {}", total, periodo, out_file
    )

    frames = []
    errores = []

    for i, pkl in enumerate(modelos, start=1):
        pct = int(i * 100 / total)

        # Skip modelos insuficientes (se reemplazan con fallback regional)
        if pkl.stem in stems_insuf:
            logger.info(
                "[{}/{}] {}% → SKIP insuficiente (fallback): {}",
                i,
                total,
                pct,
                pkl.name,
            )
            continue

        # Skip modelos region_* (solo se usan como fallback, no directamente)
        if pkl.stem in stems_regional:
            logger.info("[{}/{}] {}% → SKIP regional (solo fallback): {}", i, total, pct, pkl.name)
            continue

        logger.info("[{}/{}] {}% → {}", i, total, pct, pkl.name)

        try:
            meta = parse_nombre_modelo(pkl.stem)
            # La cohorte de conteos-log (Dengue) entrena en log1p: el forecaster debe conocer
            # el padecimiento para invertir (expm1) en predict. La cohorte neuro conserva su
            # path histórico (padecimiento=None), cuya salida productiva está validada.
            pad_meta = meta.get("meta_padecimiento")
            pad_loader = pad_meta if is_count_log_cohort(pad_meta) else None
            df = ForecastModelLoader(
                periodo=periodo, model_path=pkl, padecimiento=pad_loader
            ).run()
            for k, v in meta.items():
                df[k] = v
            df["archivo_modelo_usado"] = pkl.name
            df["archivo_modelo_original"] = pkl.name
            frames.append(df)
        except Exception as e:
            logger.warning("Error en {}: {}", pkl.name, e)
            errores.append(pkl.name)

    # --- Fallback regional: predecir con modelo regional, desnormalizar con población estatal ---
    if mapeo_hibrido:
        logger.info("Generando {} predicciones con fallback regional...", len(mapeo_hibrido))
        for stem_insuf, info in mapeo_hibrido.items():
            pkl_regional_name = info["pkl_regional"]
            padecimiento = info["padecimiento"]
            pad_norm = _normalizar(padecimiento)
            pkl_regional = base_models / pad_norm / pkl_regional_name

            if not pkl_regional.exists():
                logger.warning("Modelo regional no encontrado: {}", pkl_regional)
                errores.append(f"fallback:{stem_insuf}")
                continue

            try:
                # Inversión de log solo para la cohorte de conteos-log; neuro -> None (legacy).
                pad_fb = padecimiento if is_count_log_cohort(padecimiento) else None
                loader = ForecastModelLoader(
                    periodo=periodo, model_path=pkl_regional, padecimiento=pad_fb
                )
                loader.load()
                # Reemplazar población regional por la del estado individual
                if info.get("poblacion") and hasattr(loader.forecaster, "poblacion_valor"):
                    loader.forecaster.poblacion_valor = info["poblacion"]
                df = loader.predict()

                # Metadatos del estado (no de la región)
                meta = parse_nombre_modelo(stem_insuf)
                for k, v in meta.items():
                    df[k] = v
                df["archivo_modelo_usado"] = pkl_regional_name
                df["archivo_modelo_original"] = f"{stem_insuf}.pkl"
                frames.append(df)
                logger.info(
                    "Fallback regional: {} → {} (pob={:,.0f})",
                    stem_insuf,
                    pkl_regional_name,
                    info.get("poblacion") or 0,
                )
            except Exception as e:
                logger.warning("Error en fallback {}: {}", stem_insuf, e)
                errores.append(f"fallback:{stem_insuf}")

    # --- Predicciones standalone para modelos regionales ---
    if pkls_regional:
        logger.info("Generando {} predicciones regionales standalone...", len(pkls_regional))
        for pkl in pkls_regional:
            try:
                meta = _parse_regional(pkl.stem)
                pad_reg = meta.get("meta_padecimiento")
                pad_reg = pad_reg if is_count_log_cohort(pad_reg) else None
                df = ForecastModelLoader(
                    periodo=periodo, model_path=pkl, padecimiento=pad_reg
                ).run()
                for k, v in meta.items():
                    df[k] = v
                df["archivo_modelo_usado"] = pkl.name
                df["archivo_modelo_original"] = pkl.name
                frames.append(df)
                logger.info("Regional standalone: {} → {}", pkl.name, meta["meta_entidad"])
            except Exception as e:
                logger.warning("Error en regional {}: {}", pkl.name, e)
                errores.append(f"regional:{pkl.name}")

    if not frames:
        raise RuntimeError("Ninguna predicción generada.")

    out = pd.concat(frames, ignore_index=True)
    out = estandarizar_valores(out)

    logger.info(
        ">>> Forecast: Cargando métricas del modelo desde *_completo.csv (rmse, mae, mape, mase, confianza, normalizado, población)"
    )
    met = _cargar_metricas_completos(
        base_models, padecimiento_sin_acento if padecimiento_tipo != "General" else ""
    )

    logger.info(">>> Forecast: Seccionando métricas en ORIGINAL y USADO")
    # 1) Trae valores del modelo ORIGINAL
    met_orig = met.rename(
        columns={
            "rmse": "rmse_original",
            "mae": "mae_original",
            "mape": "mape_original",
            "smape": "smape_original",
            "mase": "mase_original",
            "confianza": "confianza_original",
            "normalizado": "normalizado_original",
            "poblacion": "poblacion_original",
        }
    )
    out = out.merge(
        met_orig,
        how="left",
        left_on="archivo_modelo_original",
        right_on="archivo_modelo",
        validate="m:1",
    ).drop(columns=["archivo_modelo"])

    # 2) Trae métricas del modelo USADO
    met_used = met.rename(
        columns={
            "rmse": "rmse_usado",
            "mae": "mae_usado",
            "mape": "mape_usado",
            "smape": "smape_usado",
            "mase": "mase_usado",
            "confianza": "confianza_usado",
            "normalizado": "normalizado_usado",
            "poblacion": "poblacion_usado",
        }
    )
    logger.info(
        ">>> Forecast: Procesando merge de métricas modelo ORIGINAL y modelo USADO desde *_completo.csv"
    )
    out = out.merge(
        met_used,
        how="left",
        left_on="archivo_modelo_usado",
        right_on="archivo_modelo",
        validate="m:1",
    ).drop(columns=["archivo_modelo"])
    logger.info(
        ">>> Forecast: Listo. yhat generado (directo/fallback) + métricas del modelo original y del modelo usado"
    )
    logger.info(
        ">>> Forecast: Detalles | filas={} | columnas={} | yhat={} | rmse_usado={} | mae_usado={} | mape_usado={} | mase_usado={} | conf_orig_nulls={} | conf_usado_nulls={}",
        len(out),
        out.shape[1],
        out["yhat"].notna().sum() if "yhat" in out.columns else 0,
        out["rmse_usado"].notna().sum() if "rmse_usado" in out.columns else 0,
        out["mae_usado"].notna().sum() if "mae_usado" in out.columns else 0,
        out["mape_usado"].notna().sum() if "mape_usado" in out.columns else 0,
        out["mase_usado"].notna().sum() if "mase_usado" in out.columns else 0,
        out["confianza_original"].isna().sum() if "confianza_original" in out.columns else 0,
        out["confianza_usado"].isna().sum() if "confianza_usado" in out.columns else 0,
    )

    # Los conteos de casos no pueden ser negativos: recorte defensivo a >= 0. En la práctica
    # es no-op (Prophet usa log_transform tanto en neuro como en Dengue -> expm1 >= 0; DeepAR
    # acota con nonnegative_pred_samples; Ensemble/Stacking operan sobre conteos clip>=0). Se
    # mantiene como red de seguridad ante cualquier motor que llegara a emitir negativos.
    yhat_cols = [c for c in out.columns if c == "yhat" or c.startswith("yhat_")]
    for col in yhat_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce").clip(lower=0)

    out.to_csv(out_file, index=False)

    logger.success(
        "Predicciones guardadas: {} | modelos: {} | errores: {}",
        out_file,
        len(frames),
        len(errores),
    )
    if errores:
        for nombre in errores:
            logger.warning("  Falló: {}", nombre)

    generar_graficos_pronostico()


if __name__ == "__main__":
    main()
