"""Entry point de entrenamiento.

Entrena el motor indicado por ``modelo_activo`` (o el override CLI) sobre todas
las series del padecimiento configurado, fijando ``PYTHONHASHSEED`` para
reproducibilidad y registrando cada run en MLflow si esta disponible. Uso:
``python -m scripts.entrena [modelo_activo=deepar] [padecimiento.tipo=Dengue]``
o via ``make train`` / ``make train-<motor>``.
"""

from contextlib import contextmanager
import os
from pathlib import Path
import platform
import random
import re
import time
import unicodedata

import joblib
from joblib import Parallel, delayed
from loguru import logger as _logger_pre_import
import pandas as pd
from tqdm import tqdm

# Silenciar "Logging inicializado" de config.py antes de que cualquier import
# del paquete lo dispare (model.py también importa config transitivamente).
_logger_pre_import.disable("epiforecast.utils.config")

from epiforecast.constants import RANDOM_SEED  # noqa: E402
from epiforecast.models import create_model  # noqa: E402
from epiforecast.utils import paths as directory_manager  # noqa: E402
from epiforecast.utils.cohorts import is_neuro  # noqa: E402
from epiforecast.utils.config import conf, logger  # noqa: E402

_logger_pre_import.enable("epiforecast.utils.config")

# Reproducibilidad: fijar semillas de todos los generadores
os.environ.setdefault("PYTHONHASHSEED", str(RANDOM_SEED))
random.seed(RANDOM_SEED)


@contextmanager
def _tqdm_joblib(tqdm_object):
    """Permite que joblib.Parallel actualice una barra de tqdm."""

    class _TqdmBatchCallback(joblib.parallel.BatchCompletionCallBack):
        def __call__(self, *args, **kwargs):
            tqdm_object.update(n=self.batch_size)
            return super().__call__(*args, **kwargs)

    old = joblib.parallel.BatchCompletionCallBack
    joblib.parallel.BatchCompletionCallBack = _TqdmBatchCallback
    try:
        yield tqdm_object
    finally:
        joblib.parallel.BatchCompletionCallBack = old
        tqdm_object.close()


def normalizar(region: str) -> str:
    formato = unicodedata.normalize("NFKD", region).encode("ascii", "ignore").decode("ascii")
    formato = formato.replace("/", "-")
    return re.sub(r"\s+", "_", formato)


def entrenar(df, padecimiento, sexo, ruta_base, mapeo, region=None, force=False):
    # Imports locales: evita que cloudpickle (loky) intente serializar estos objetos
    # cada worker re-importa los módulos frescos.
    from epiforecast.utils import paths as directory_manager
    from epiforecast.utils.config import conf, logger

    modelo_activo = conf.get("modelo_activo", "prophet")
    ruta_padecimiento = os.path.join(ruta_base, normalizar(padecimiento))
    directory_manager.asegurar_ruta(ruta_padecimiento)

    nombre_extra = f"_{normalizar(region)}" if region else ""
    # El nombre del archivo ahora incluye el prefijo del modelo activo
    nombre_modelo = f"{modelo_activo.capitalize()}_{normalizar(padecimiento)}{nombre_extra}_{mapeo.get(sexo, sexo)}.pkl"
    ruta_modelo = os.path.join(ruta_padecimiento, nombre_modelo)

    if not force:
        if Path(ruta_modelo).exists():
            logger.debug("Modelo ya existe, omitiendo: {}", Path(ruta_modelo).name)
            return None

    t_start = time.time()

    # Instanciar modelo vía Factory
    forecaster = create_model(
        modelo_activo, df=df, sexo=sexo, entidad=region, padecimiento=padecimiento
    )

    # Ejecutar pipeline completo del modelo
    # Se espera que todos los modelos implementen .run() que retorna (model_obj, metrics, params)
    # Si no tiene .run(), fallará, lo cual es correcto bajo este nuevo contrato.
    try:
        _, metrics, parametros = forecaster.run()
    except Exception as e:
        logger.error("Error ejecutando pipeline para {}: {}", nombre_modelo, e)
        return None

    t_end = time.time()

    mape_raw = metrics.get("mape")
    mape_clipped = mape_raw is not None and mape_raw >= 999.0

    # Determinar si es insuficiente (Prophet lo reporta en metrics o podemos inferirlo)
    confianza = metrics.get("confianza", "normal")
    promedio = metrics.get("promedio_semanal", 0)

    fila = {
        "padecimiento": padecimiento,
        "sexo": sexo,
        "rmse": metrics.get("rmse"),
        "mae": metrics.get("mae"),
        "mape": mape_raw,
        "smape": metrics.get("smape"),
        "mase": metrics.get("mase"),
        "rmse_train": metrics.get("rmse_train"),
        "smape_train": metrics.get("smape_train"),
        "mape_confiable": not mape_clipped,
        **parametros,
    }
    fila["archivo_modelo"] = nombre_modelo
    fila["nivel"] = "nacional" if region is None else "regional"
    fila["confianza"] = confianza
    fila["promedio_semanal"] = round(promedio, 2)
    fila["tiempo_total_seg"] = round(t_end - t_start, 1)

    if region:
        fila["Entidad"] = region
    if hasattr(forecaster, "poblacion_valor") and forecaster.poblacion_valor:
        fila["poblacion"] = forecaster.poblacion_valor
        fila["normalizado"] = True

    # Guardar modelo
    forecaster.save(Path(ruta_modelo))

    # Guardar serie de tiempo procesada (sidecar para desnormalización)
    if hasattr(forecaster, "serie") and not forecaster.serie.empty:
        ruta_csv = os.path.join(ruta_padecimiento, nombre_modelo.replace(".pkl", ".csv"))
        forecaster.serie.to_csv(ruta_csv, index=False, encoding="utf-8")
        logger.debug("Serie histórica guardada: {}", Path(ruta_csv).name)
    else:
        logger.warning("No se pudo guardar la serie histórica para {}", nombre_modelo)
    mase_str = f"{metrics['mase']:.3f}" if metrics.get("mase") is not None else "N/A"
    logger.debug(
        "Completado: {} | {} | {} | RMSE={} | MASE={} | Total={:.1f}s | {}",
        padecimiento,
        region or "Nacional",
        mapeo.get(sexo, sexo),
        f"{metrics['rmse']:.4f}" if metrics.get("rmse") is not None else "N/A",
        mase_str,
        fila["tiempo_total_seg"],
        fila["confianza"],
    )

    # MLflow (no-op si no esta instalado)
    from epiforecast.utils.mlflow_logger import log_training_run

    log_training_run(
        model_name=modelo_activo,
        entity=region,
        disease=padecimiento,
        params=parametros,
        metrics=metrics,
        elapsed=t_end - t_start,
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
    # Stacking + Windows/Linux: forzar secuencial para evitar deadlocks
    # por multiprocessing anidado (loky + cmdstanpy/statsmodels en OOF)
    if conf.get("modelo_activo") == "stacking" and n_jobs != 1 and platform.system() != "Darwin":
        logger.info("Stacking: forzando n_jobs=1 (evita deadlock en {})", platform.system())
        n_jobs = 1

    ruta_datos = conf["data"]["data_inegi"]
    df_entrenamiento = pd.read_csv(ruta_datos)

    agrupador = "Entidad" if modelado_estados else "region_salud_mental"
    regiones = [] if solo_nacional else sorted(df_entrenamiento[agrupador].unique())
    padecimientos = sorted(df_entrenamiento["Padecimiento"].unique())

    # Filtrar padecimientos según configuración si no es "General"
    tipo_pad = str(conf["padecimiento"].get("tipo", "General"))
    if tipo_pad != "General":
        padecimientos = [p for p in padecimientos if p == tipo_pad]
        if not padecimientos:
            logger.warning("Padecimiento '{}' no encontrado en el dataset.", tipo_pad)
            return
    else:
        # Guard: el modo "General" entrena solo la cohorte neurológica de producción.
        # Dengue (y otros padecimientos no productizados) NO deben entrenarse aquí con la
        # configuración neuro; se entrenan explícitamente con padecimiento.tipo='Dengue',
        # con su propia config. Evita generar artefactos .pkl espurios desde el consolidado.
        omitidos = [p for p in padecimientos if not is_neuro(p)]
        if omitidos:
            logger.info(
                "Modo General: se omiten padecimientos fuera de la cohorte neuro: {}", omitidos
            )
        padecimientos = [p for p in padecimientos if is_neuro(p)]

    total = len(padecimientos) * len(valores_sexo) * (1 + len(regiones))
    modelo_activo = conf.get("modelo_activo", "prophet")

    logger.debug(
        "Iniciando entrenamiento | modelo: {} | padecimientos: {} | regiones: {} | sexo: {} | "
        "total modelos: {} | n_jobs: {} | solo_nacional: {}",
        modelo_activo,
        len(padecimientos),
        len(regiones),
        len(valores_sexo),
        total,
        n_jobs,
        solo_nacional,
    )

    for padecimiento in padecimientos:
        t_pad = time.time()
        logger.debug("═══ Padecimiento: {} ═══", padecimiento)
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

        total_jobs = len(jobs)
        logger.debug("{} modelos a procesar para {}", total_jobs, padecimiento)

        with tqdm(
            total=total_jobs,
            desc=padecimiento,
            unit="modelo",
            dynamic_ncols=True,
            position=0,
            leave=True,
        ) as pbar:
            if n_jobs != 1:
                with _tqdm_joblib(pbar):
                    resultados_raw = Parallel(n_jobs=n_jobs, backend="loky", verbose=0)(
                        delayed(entrenar)(*job) for job in jobs
                    )
            else:
                resultados_raw = []
                for job in jobs:
                    resultados_raw.append(entrenar(*job))
                    pbar.update(1)

        resultados = [f for f in resultados_raw if f is not None]

        # --- Modo híbrido: entrenar regionales siempre + fallback insuficientes ---
        # Solo para la cohorte neuro. Dengue NO usa fallback regional (decisión: "si es 0,
        # es 0"; una entidad sin transmisión no hereda la curva de un estado tropical).
        # NOTA (auditoría 2026-06-06): se probó entrenar modelos regionales NATIVOS de Dengue
        # (Prophet/NBGLM por region_salud_mental) y se comparó vs la agregación bottom-up (suma
        # de estados). La agregación ganó en las 4 regiones (SMAPE ~35-45 vs 52-86). Por eso la
        # galería sigue agregando estados y NO se entrenan regionales nativos de Dengue.
        # Ver docs/research/hallazgos/DENGUE_REGIONALES_NATIVOS_AUDITORIA.md.
        modelado_hibrido = bool(conf["padecimiento"].get("modelado_hibrido", False))
        if modelado_hibrido and modelado_estados and is_neuro(padecimiento):
            # Mapear estado → región INEGI
            mapa_region = (
                df_padecimiento[["Entidad", "region_salud_mental"]]
                .drop_duplicates()
                .set_index("Entidad")["region_salud_mental"]
                .to_dict()
            )
            todas_las_regiones = sorted(set(mapa_region.values()))

            # 1) Entrenar modelos regionales para TODAS las regiones (incondicional)
            jobs_regional = []
            for region in todas_las_regiones:
                df_region = df_padecimiento[df_padecimiento["region_salud_mental"] == region]
                for sexo in valores_sexo:
                    region_tag = f"region_{region}"
                    jobs_regional.append(
                        (
                            df_region,
                            padecimiento,
                            sexo,
                            model_path,
                            mapeo,
                            region_tag,
                            force,
                        )
                    )

            total_reg = len(jobs_regional)
            logger.debug(
                "Entrenando {} modelos regionales para {} ({} regiones)",
                total_reg,
                padecimiento,
                len(todas_las_regiones),
            )

            with tqdm(
                total=total_reg,
                desc=f"{padecimiento} regional",
                unit="modelo",
                dynamic_ncols=True,
                position=0,
                leave=True,
            ) as pbar_reg:
                if n_jobs != 1:
                    with _tqdm_joblib(pbar_reg):
                        res_reg_raw = Parallel(n_jobs=n_jobs, backend="loky", verbose=0)(
                            delayed(entrenar)(*job) for job in jobs_regional
                        )
                else:
                    res_reg_raw = []
                    for job in jobs_regional:
                        res_reg_raw.append(entrenar(*job))
                        pbar_reg.update(1)

            res_regional = [f for f in res_reg_raw if f is not None]
            resultados.extend(res_regional)

            # 2) Si hay insuficientes, mapear usar_regional
            if resultados:
                insuf = [
                    f
                    for f in resultados
                    if f.get("confianza") == "insuficiente" and f.get("nivel") == "regional"
                ]
                if insuf:
                    for fila in resultados:
                        if (
                            fila.get("confianza") == "insuficiente"
                            and fila.get("nivel") == "regional"
                            and fila.get("Entidad") in mapa_region
                        ):
                            region = mapa_region[fila["Entidad"]]
                            region_tag = f"region_{region}"
                            sexo = fila["sexo"]
                            pkl_regional = (
                                f"{modelo_activo.capitalize()}_{normalizar(padecimiento)}"
                                f"_{normalizar(region_tag)}"
                                f"_{mapeo.get(sexo, sexo)}.pkl"
                            )
                            fila["usar_regional"] = pkl_regional
                        else:
                            fila.setdefault("usar_regional", None)

                    logger.debug(
                        "Modo hibrido: {} insuficientes mapeados a regional en {}",
                        len(insuf),
                        padecimiento,
                    )

            logger.debug(
                "Modo hibrido: {} modelos regionales entrenados para {}",
                len(res_regional),
                padecimiento,
            )

        if resultados:
            ruta_rmse = os.path.join(
                ruta_padecimiento,
                f"{modelo_activo.capitalize()}_{normalizar(padecimiento)}_completo.csv",
            )
            pd.DataFrame(resultados).to_csv(ruta_rmse, index=False, encoding="utf-8")
            entrenados = len(resultados)
            insuficientes = sum(1 for f in resultados if f.get("confianza") == "insuficiente")
            t_elapsed = time.time() - t_pad
            logger.info(
                "{}: {} modelos en {:.1f} min ({} baja confianza)",
                padecimiento,
                entrenados,
                t_elapsed / 60,
                insuficientes,
            )

    t_total = time.time() - t_inicio_global
    logger.info(
        "Entrenamiento completado. {} modelos en {:.1f} min ({:.1f} h).",
        total,
        t_total / 60,
        t_total / 3600,
    )


if __name__ == "__main__":
    main()
