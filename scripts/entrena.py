# scripts/entrena.py

import time

import pandas as pd
import pickle
import re
import unicodedata
import os
from pathlib import Path

from src.modelado.prophet import SerieTiempoProphet
from src.configuraciones.config_params import conf, logger
from src.utils import directory_manager


def normalizar(region: str) -> str:
    formato = unicodedata.normalize("NFKD", region).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", "_", formato)


def entrenar(df, padecimiento, sexo, ruta_base, mapeo, region=None, force=False):
    ruta_padecimiento = os.path.join(ruta_base, normalizar(padecimiento))
    directory_manager.asegurar_ruta(ruta_padecimiento)

    nombre_extra = f"_{normalizar(region)}" if region else ""
    nombre_modelo = f"Prophet_{normalizar(padecimiento)}{nombre_extra}_{mapeo.get(sexo, sexo)}.pkl"
    ruta_modelo = os.path.join(ruta_padecimiento, nombre_modelo)

    if not force:
        if Path(ruta_modelo).exists():
            logger.info("Modelo ya existe, omitiendo: {}", Path(ruta_modelo).name)
            return None, ruta_padecimiento

    t_start = time.time()

    stp = SerieTiempoProphet(df, sexo=sexo, entidad=region, padecimiento=padecimiento)
    stp.agrupa()
    stp.crea_train_test()

    # Verificar umbral mínimo de casos por semana (marca confianza, pero entrena de todos modos)
    umbral = conf.get('umbral_minimo_semanal', 0)
    promedio = stp.promedio_semanal()
    es_insuficiente = umbral and promedio < umbral
    if es_insuficiente:
        logger.warning(
            "Serie de baja confianza: promedio {:.2f} casos/semana < umbral {:.1f} | {} | {} | {}",
            promedio, umbral, padecimiento, region or "Nacional", sexo,
        )

    parametros, metrics = stp.prophet_cross_val()
    t_cv = time.time()

    modelo = stp.train(parametros)
    t_train = time.time()

    fila = {
        "padecimiento": padecimiento, "sexo": sexo,
        "rmse": metrics["rmse"], "mae": metrics["mae"], "mape": metrics["mape"],
        **parametros,
    }
    fila["nivel"] = "nacional" if region is None else "regional"
    fila["confianza"] = "insuficiente" if es_insuficiente else "normal"
    fila["promedio_semanal"] = round(promedio, 2)
    fila["tiempo_cv_seg"] = round(t_cv - t_start, 1)
    fila["tiempo_train_seg"] = round(t_train - t_cv, 1)
    fila["tiempo_total_seg"] = round(t_train - t_start, 1)
    if region:
        fila["Entidad"] = region
    if stp.normalizar_tasa and stp.poblacion_valor:
        fila["poblacion"] = stp.poblacion_valor
        fila["normalizado"] = True

    with open(ruta_modelo, "wb") as f:
        pickle.dump(modelo, f)

    ruta_csv = os.path.join(ruta_padecimiento, nombre_modelo.replace(".pkl", ".csv"))
    stp.train_data.to_csv(ruta_csv, index=False, encoding="utf-8")
    logger.info("Datos de entrenamiento guardados: {}", os.path.basename(ruta_csv))

    fila["archivo_modelo"] = nombre_modelo
    logger.info(
        "Métricas: RMSE={:.4f} | MAE={:.4f} | MAPE={:.2f}% | CV={:.1f}s | Train={:.1f}s | Confianza: {}",
        metrics["rmse"], metrics["mae"], metrics["mape"],
        fila["tiempo_cv_seg"], fila["tiempo_train_seg"], fila["confianza"],
    )

    return fila, ruta_padecimiento


def main():
    t_inicio_global = time.time()

    modelado_estados = conf["padecimiento"]["modelado_estados"]
    force = conf["padecimiento"]["entrena_modelo"]
    model_path = conf["paths"]["models"]
    valores_sexo = conf["valores_sexo"]
    mapeo = conf["mapeo_columnas"]

    ruta_datos = conf["data"]["data_inegi"]
    df_entrenamiento = pd.read_csv(ruta_datos)

    agrupador = "Entidad" if modelado_estados else "region_salud_mental"
    regiones = sorted(df_entrenamiento[agrupador].unique())
    padecimientos = sorted(df_entrenamiento["Padecimiento"].unique())

    # Total = por cada padecimiento: len(sexos) nacional + len(regiones)*len(sexos) regional
    total = len(padecimientos) * len(valores_sexo) * (1 + len(regiones))
    contador = 0

    logger.info(
        "Iniciando entrenamiento | padecimientos: {} | regiones: {} | sexo: {} | total modelos: {}",
        len(padecimientos), len(regiones), len(valores_sexo), total,
    )

    for padecimiento in padecimientos:
        logger.info("Padecimiento: {}", padecimiento)
        df_padecimiento = df_entrenamiento[df_entrenamiento["Padecimiento"] == padecimiento]
        resultados = []
        ruta_padecimiento = None

        # Nacional
        for sexo in valores_sexo:
            contador += 1
            pct = contador / total * 100
            logger.info(
                "[{}/{}] {:.0f}% | CV Prophet | {} | Nacional | Sexo: {}",
                contador, total, pct, padecimiento, sexo,
            )
            fila, ruta_padecimiento = entrenar(df_padecimiento, padecimiento, sexo, model_path, mapeo, force=force)
            logger.success(
                "[{}/{}] {:.0f}% | Completado | {} | Nacional | Sexo: {}",
                contador, total, pct, padecimiento, sexo,
            )
            resultados.append(fila)

        # Regional
        for region in regiones:
            df_region = df_padecimiento[df_padecimiento[agrupador] == region]
            for sexo in valores_sexo:
                contador += 1
                pct = contador / total * 100
                logger.info(
                    "[{}/{}] {:.0f}% | CV Prophet | {} | Regional | Región: {} | Sexo: {}",
                    contador, total, pct, padecimiento, region, sexo,
                )
                fila, _ = entrenar(df_region, padecimiento, sexo, model_path, mapeo, region=region, force=force)
                logger.success(
                    "[{}/{}] {:.0f}% | Completado | {} | Regional | Región: {} | Sexo: {}",
                    contador, total, pct, padecimiento, region, sexo,
                )
                resultados.append(fila)

        # Guardar resultados del padecimiento
        resultados = [f for f in resultados if f is not None]
        if ruta_padecimiento and resultados:
            ruta_rmse = os.path.join(ruta_padecimiento, f"Prophet_{normalizar(padecimiento)}_completo.csv")
            pd.DataFrame(resultados).to_csv(ruta_rmse, index=False, encoding="utf-8")
            insuficientes = sum(1 for f in resultados if f.get("confianza") == "insuficiente")
            if insuficientes:
                logger.warning("Series de baja confianza: {}/{}", insuficientes, len(resultados))
            logger.success("Resultados guardados: {}", ruta_rmse)

    t_total = time.time() - t_inicio_global
    logger.success(
        "Entrenamiento completado. {} modelos procesados en {:.1f} min ({:.1f} h).",
        total, t_total / 60, t_total / 3600,
    )


if __name__ == "__main__":
    main()
