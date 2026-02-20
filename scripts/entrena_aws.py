# scripts/entrena_aws.py
"""
Entry point para comparación de modelos.
Funciona tanto en ejecución local como en SageMaker Training Jobs.

Uso local:
    python -m scripts.entrena_aws

En SageMaker:
    Se ejecuta automáticamente como SAGEMAKER_PROGRAM dentro del contenedor.
    - Lee datos desde /opt/ml/input/data/training/
    - Guarda resultados en /opt/ml/model/
"""

import json
import os
import unicodedata
import re

import pandas as pd
from omegaconf import OmegaConf
from pathlib import Path

from src.configuraciones.config_params import conf, logger
from src.modelado.comparacion_modelos import ComparadorModelos


def normalizar(texto: str) -> str:
    formato = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", "_", formato)


def detectar_entorno():
    """Detecta si estamos en SageMaker o en local."""
    sagemaker_dir = Path("/opt/ml/input/data/training")
    if sagemaker_dir.exists():
        return "sagemaker"
    return "local"


def cargar_datos(entorno):
    """Carga datos según el entorno de ejecución."""
    if entorno == "sagemaker":
        data_dir = Path("/opt/ml/input/data/training")
        archivos_csv = list(data_dir.glob("*.csv"))
        if not archivos_csv:
            raise FileNotFoundError(f"No se encontraron CSVs en {data_dir}")
        ruta = archivos_csv[0]
        logger.info(f"[SageMaker] Cargando datos desde: {ruta}")
    else:
        ruta = conf["data"]["data_inegi"]
        logger.info(f"[Local] Cargando datos desde: {ruta}")

    return pd.read_csv(ruta)


def cargar_config_experimentos(entorno):
    """Carga la configuración de experimentos."""
    if entorno == "sagemaker":
        # En SageMaker, los hiperparámetros vienen como JSON
        hp_path = Path("/opt/ml/input/config/hyperparameters.json")
        if hp_path.exists():
            with open(hp_path) as f:
                hp = json.load(f)
            if "config_experimentos" in hp:
                return json.loads(hp["config_experimentos"])

    # Default: cargar desde YAML
    conf_exp = OmegaConf.load("config/experimentos.yaml")
    config = OmegaConf.to_container(conf_exp, resolve=True)

    # Si estamos en SageMaker, activar tracking de SageMaker Experiments
    if entorno == "sagemaker":
        config["experimentos"]["tracking"]["sagemaker"] = True
        config["experimentos"]["tracking"]["directorio_resultados"] = "/opt/ml/model/experiments"

    return config["experimentos"]


def obtener_ruta_salida(entorno):
    """Retorna la ruta de salida según el entorno."""
    if entorno == "sagemaker":
        return Path("/opt/ml/model")
    return Path("./experiments")


def main():
    entorno = detectar_entorno()
    logger.info(f"Entorno detectado: {entorno}")

    # Cargar datos y configuración
    df_entrenamiento = cargar_datos(entorno)
    config_exp = cargar_config_experimentos(entorno)
    ruta_salida = obtener_ruta_salida(entorno)
    ruta_salida.mkdir(parents=True, exist_ok=True)

    # Configuración del pipeline
    modelado_estados = conf["padecimiento"]["modelado_estados"]
    mapeo = conf["mapeo_columnas"]
    valores_sexo = list(conf["valores_sexo"])

    agrupador = "Entidad" if modelado_estados else "region_salud_mental"
    regiones = sorted(df_entrenamiento[agrupador].unique())
    padecimientos = sorted(df_entrenamiento["Padecimiento"].unique())

    # ── Aplicar scope (filtrar para pruebas rápidas) ──
    scope = config_exp.get("scope", {})

    if scope.get("padecimientos"):
        padecimientos = [p for p in padecimientos if p in scope["padecimientos"]]

    if scope.get("sexos"):
        valores_sexo = [s for s in valores_sexo if s in scope["sexos"]]

    if scope.get("max_regiones"):
        regiones = regiones[: scope["max_regiones"]]

    solo_regional = scope.get("solo_regional", False)

    # Periodos atípicos (desde config de experimentos, más completo)
    periodos_atipicos_raw = config_exp.get("periodos_atipicos", [])
    if not periodos_atipicos_raw:
        # Fallback a config principal
        periodos_atipicos_raw = conf.get("peridos_atipicos", [])
    periodos_atipicos = periodos_atipicos_raw

    # Crear comparador
    comparador = ComparadorModelos(config_exp)

    # Calcular total de combinaciones según scope
    combos_nacional = 0 if solo_regional else len(padecimientos) * len(valores_sexo)
    combos_regional = len(padecimientos) * len(regiones) * len(valores_sexo)
    total_combinaciones = combos_nacional + combos_regional
    contador = 0

    logger.info(
        f"Iniciando comparación de modelos | "
        f"padecimientos: {len(padecimientos)} | regiones: {len(regiones)} | "
        f"sexo: {len(valores_sexo)} | solo_regional: {solo_regional} | "
        f"combinaciones totales: {total_combinaciones}"
    )

    modelos_activos = [k for k, v in config_exp.get("modelos", {}).items() if v.get("activo")]
    logger.info(f"Modelos activos: {modelos_activos}")

    for padecimiento in padecimientos:
        logger.info(f"═══ Padecimiento: {padecimiento} ═══")
        df_padecimiento = df_entrenamiento[df_entrenamiento["Padecimiento"] == padecimiento]

        # ── Nacional (omitir si solo_regional) ──
        if not solo_regional:
            for sexo in valores_sexo:
                contador += 1
                pct = contador / total_combinaciones * 100
                logger.info(
                    f"[{contador}/{total_combinaciones}] {pct:.0f}% | "
                    f"{padecimiento} | Nacional | {sexo}"
                )

                serie = (
                    df_padecimiento
                    .groupby("Fecha")[sexo]
                    .sum()
                    .rename_axis("ds")
                    .reset_index()
                    .rename(columns={sexo: "y"})
                )
                serie["ds"] = pd.to_datetime(serie["ds"])

                comparador.ejecutar(
                    serie,
                    padecimiento=padecimiento,
                    sexo=mapeo.get(sexo, sexo),
                    region=None,
                    periodos_atipicos=periodos_atipicos,
                )

        # ── Regional ──
        for region in regiones:
            df_region = df_padecimiento[df_padecimiento[agrupador] == region]

            for sexo in valores_sexo:
                contador += 1
                pct = contador / total_combinaciones * 100
                logger.info(
                    f"[{contador}/{total_combinaciones}] {pct:.0f}% | "
                    f"{padecimiento} | {region} | {sexo}"
                )

                serie = (
                    df_region
                    .groupby("Fecha")[sexo]
                    .sum()
                    .rename_axis("ds")
                    .reset_index()
                    .rename(columns={sexo: "y"})
                )
                serie["ds"] = pd.to_datetime(serie["ds"])

                comparador.ejecutar(
                    serie,
                    padecimiento=padecimiento,
                    sexo=mapeo.get(sexo, sexo),
                    region=normalizar(region),
                    periodos_atipicos=periodos_atipicos,
                )

    # Guardar todos los resultados
    resultados = comparador.guardar_resultados()

    logger.success(
        f"Comparación completada. {len(resultados)} trials evaluados "
        f"en {total_combinaciones} combinaciones."
    )


if __name__ == "__main__":
    main()
