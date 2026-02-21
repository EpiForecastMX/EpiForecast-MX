# scripts/entrena.py

import time

import pandas as pd
import pickle
import re
import unicodedata
import os
from pathlib import Path

from joblib import Parallel, delayed

from src.modelado.prophet import SerieTiempoProphet
from src.configuraciones.config_params import conf, logger
from src.utils import directory_manager


def normalizar(region: str) -> str:
    formato = unicodedata.normalize("NFKD", region).encode("ascii", "ignore").decode("ascii")
    formato = formato.replace("/", "-")
    return re.sub(r"\s+", "_", formato)


def entrenar(df, padecimiento, sexo, ruta_base, mapeo, region=None, force=False, progreso=None):
    # Imports locales: evita que cloudpickle (loky) intente serializar estos objetos
    # como globals de __main__. OmegaConf y loguru no son pickle-safe.
    # Cada worker re-importa los módulos frescos.
    from src.configuraciones.config_params import conf, logger
    from src.modelado.prophet import SerieTiempoProphet
    from src.utils import directory_manager

    if progreso:
        i, total = progreso
        logger.info("[{}/{}] {:.0f}% | {} | {} | {}", i, total, i / total * 100,
                    padecimiento, region or "Nacional", mapeo.get(sexo, sexo))

    ruta_padecimiento = os.path.join(ruta_base, normalizar(padecimiento))
    directory_manager.asegurar_ruta(ruta_padecimiento)

    nombre_extra = f"_{normalizar(region)}" if region else ""
    nombre_modelo = f"Prophet_{normalizar(padecimiento)}{nombre_extra}_{mapeo.get(sexo, sexo)}.pkl"
    ruta_modelo = os.path.join(ruta_padecimiento, nombre_modelo)

    if not force:
        if Path(ruta_modelo).exists():
            logger.info("Modelo ya existe, omitiendo: {}", Path(ruta_modelo).name)
            return None

    t_start = time.time()

    stp = SerieTiempoProphet(df, sexo=sexo, entidad=region, padecimiento=padecimiento)
    stp.agrupa()
    stp.crea_train_test()

    # Verificar umbral mínimo de casos por semana
    umbral = conf.get('umbral_minimo_semanal', 0)
    promedio = stp.promedio_semanal()
    es_insuficiente = umbral and promedio < umbral

    if es_insuficiente:
        # Skip CV: usar primer combo del grid como default (serie casi plana, HP da igual)
        parametros = {k: v[0] for k, v in stp.param_grid.items()}
        metrics = {"rmse": None, "mae": None, "mape": None}
        logger.warning(
            "Baja confianza: skip CV, params default | {:.2f} casos/sem | {} | {} | {}",
            promedio, padecimiento, region or "Nacional", sexo,
        )
        t_cv = time.time()
        modelo = stp.train(parametros)
        t_train = time.time()
    else:
        parametros, metrics = stp.prophet_cross_val()
        t_cv = time.time()
        modelo = stp.train(parametros)
        t_train = time.time()

    mape_raw = metrics["mape"]
    mape_clipped = mape_raw is not None and mape_raw >= 999.0

    fila = {
        "padecimiento": padecimiento, "sexo": sexo,
        "rmse": metrics["rmse"], "mae": metrics["mae"], "mape": mape_raw,
        "mape_confiable": not mape_clipped,
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

    fila["archivo_modelo"] = nombre_modelo
    logger.info(
        "Completado: {} | {} | {} | RMSE={} | CV={:.1f}s | Train={:.1f}s | {}",
        padecimiento, region or "Nacional", mapeo.get(sexo, sexo),
        f"{metrics['rmse']:.4f}" if metrics["rmse"] is not None else "N/A",
        fila["tiempo_cv_seg"], fila["tiempo_train_seg"], fila["confianza"],
    )

    return fila


def main():
    t_inicio_global = time.time()

    modelado_estados = bool(conf["padecimiento"]["modelado_estados"])
    solo_nacional = bool(conf["padecimiento"].get("solo_nacional", False))
    force = bool(conf["padecimiento"]["entrena_modelo"])
    model_path = str(conf["paths"]["models"])
    valores_sexo = [str(s) for s in conf["valores_sexo"]]
    mapeo = {str(k): str(v) for k, v in conf["mapeo_columnas"].items()}
    n_jobs = int(conf.get("n_jobs_train", 1))

    ruta_datos = conf["data"]["data_inegi"]
    df_entrenamiento = pd.read_csv(ruta_datos)

    agrupador = "Entidad" if modelado_estados else "region_salud_mental"
    regiones = [] if solo_nacional else sorted(df_entrenamiento[agrupador].unique())
    padecimientos = sorted(df_entrenamiento["Padecimiento"].unique())

    total = len(padecimientos) * len(valores_sexo) * (1 + len(regiones))

    logger.info(
        "Iniciando entrenamiento | padecimientos: {} | regiones: {} | sexo: {} | "
        "total modelos: {} | n_jobs: {} | solo_nacional: {}",
        len(padecimientos), len(regiones), len(valores_sexo), total, n_jobs, solo_nacional,
    )

    for padecimiento in padecimientos:
        t_pad = time.time()
        logger.info("═══ Padecimiento: {} ═══", padecimiento)
        df_padecimiento = df_entrenamiento[df_entrenamiento["Padecimiento"] == padecimiento]

        ruta_padecimiento = os.path.join(model_path, normalizar(padecimiento))
        directory_manager.asegurar_ruta(ruta_padecimiento)

        # Construir lista de jobs: (df, padecimiento, sexo, ruta_base, mapeo, region, force)
        jobs = []

        # Nacional
        for sexo in valores_sexo:
            jobs.append((df_padecimiento, padecimiento, sexo, model_path, mapeo, None, force))

        # Regional
        for region in regiones:
            df_region = df_padecimiento[df_padecimiento[agrupador] == region]
            for sexo in valores_sexo:
                jobs.append((df_region, padecimiento, sexo, model_path, mapeo, region, force))

        # Agregar índice de progreso a cada job
        total_jobs = len(jobs)
        jobs = [(*job, (i, total_jobs)) for i, job in enumerate(jobs, 1)]

        logger.info("{} modelos a procesar para {}", total_jobs, padecimiento)

        if n_jobs != 1:
            resultados_raw = Parallel(n_jobs=n_jobs, backend="loky", verbose=10)(
                delayed(entrenar)(*job) for job in jobs
            )
        else:
            resultados_raw = [entrenar(*job) for job in jobs]

        resultados = [f for f in resultados_raw if f is not None]

        if resultados:
            ruta_rmse = os.path.join(
                ruta_padecimiento, f"Prophet_{normalizar(padecimiento)}_completo.csv"
            )
            pd.DataFrame(resultados).to_csv(ruta_rmse, index=False, encoding="utf-8")
            entrenados = len(resultados)
            insuficientes = sum(1 for f in resultados if f.get("confianza") == "insuficiente")
            t_elapsed = time.time() - t_pad
            logger.success(
                "{}: {} modelos en {:.1f} min ({} baja confianza)",
                padecimiento, entrenados, t_elapsed / 60, insuficientes,
            )

    t_total = time.time() - t_inicio_global
    logger.success(
        "Entrenamiento completado. {} modelos en {:.1f} min ({:.1f} h).",
        total, t_total / 60, t_total / 3600,
    )


if __name__ == "__main__":
    main()
