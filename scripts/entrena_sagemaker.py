# scripts/entrena_sagemaker.py
"""
Entry point para entrenamiento DeepAR en SageMaker.

Adapta el entorno SageMaker (/opt/ml/) al pipeline existente de scripts.entrena:
1. Detecta si esta corriendo en SageMaker
2. Copia datos de /opt/ml/input/data/training/ al path esperado por config
3. Fuerza modelo_activo='deepar' via sys.argv (OmegaConf CLI override)
4. Invoca scripts.entrena.main()
5. Copia modelos entrenados a /opt/ml/model/ para que SageMaker los suba a S3
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys

from loguru import logger

SAGEMAKER_DATA_DIR = Path("/opt/ml/input/data/training")
SAGEMAKER_MODEL_DIR = Path("/opt/ml/model")
LOCAL_DATA_DIR = Path("data/processed")
LOCAL_MODELS_DIR = Path("models/deepar")


def detectar_entorno() -> str:
    """Detecta si esta corriendo en SageMaker o local."""
    if SAGEMAKER_DATA_DIR.exists():
        return "sagemaker"
    return "local"


def copiar_datos_sagemaker() -> str | None:
    """Copia CSVs de /opt/ml/input/data/training/ a data/processed/.

    Returns:
        Tipo de padecimiento extraido del nombre del CSV (e.g. "Depresion"),
        o None si no se pudo detectar.
    """
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

    csvs = list(SAGEMAKER_DATA_DIR.glob("*.csv"))
    if not csvs:
        logger.error("No se encontraron CSVs en {}", SAGEMAKER_DATA_DIR)
        sys.exit(1)

    import re

    tipo_padecimiento = None
    for csv in csvs:
        destino = LOCAL_DATA_DIR / csv.name
        shutil.copy2(csv, destino)
        logger.debug("Copiado: {} -> {}", csv, destino)

        # Extraer tipo de padecimiento del nombre: data_inegi_Depresión.csv -> Depresión
        match = re.search(r"data_inegi_(.+)\.csv", csv.name)
        if match:
            tipo_padecimiento = match.group(1)

    return tipo_padecimiento


def copiar_modelos_salida() -> None:
    """Copia modelos entrenados de models/deepar/ a /opt/ml/model/."""
    if not LOCAL_MODELS_DIR.exists():
        logger.warning("No se encontro directorio de modelos: {}", LOCAL_MODELS_DIR)
        return

    SAGEMAKER_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    archivos = list(LOCAL_MODELS_DIR.rglob("*"))
    copiados = 0
    for archivo in archivos:
        if archivo.is_file():
            rel = archivo.relative_to(LOCAL_MODELS_DIR)
            destino = SAGEMAKER_MODEL_DIR / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archivo, destino)
            copiados += 1

    logger.debug("Copiados {} archivos a {}", copiados, SAGEMAKER_MODEL_DIR)


def main() -> None:
    entorno = detectar_entorno()
    logger.debug("Entorno detectado: {}", entorno)

    tipo_padecimiento = None
    if entorno == "sagemaker":
        tipo_padecimiento = copiar_datos_sagemaker()

    # Forzar modelo_activo=deepar via CLI override de OmegaConf
    # (debe estar en sys.argv ANTES de que config.py se importe)
    if "modelo_activo=deepar" not in sys.argv:
        sys.argv.append("modelo_activo=deepar")

    # PADECIMIENTO_TIPO env var tiene prioridad (jobs paralelos por padecimiento)
    pad_env = os.environ.get("PADECIMIENTO_TIPO")
    if pad_env:
        tipo_padecimiento = pad_env
        logger.debug("PADECIMIENTO_TIPO desde env: {}", pad_env)

    # Forzar padecimiento.tipo para que coincida con el CSV subido
    if tipo_padecimiento:
        override = f"padecimiento.tipo={tipo_padecimiento}"
        if override not in sys.argv:
            sys.argv.append(override)
            logger.debug("Override padecimiento.tipo={}", tipo_padecimiento)

    if entorno == "sagemaker":
        # Paralelizar entrenamiento (4 vCPUs en ml.g4dn.xlarge)
        sys.argv.append("n_jobs_train=4")
        # Skip CV para modelos estatales (DeepAR no hace HP tuning en CV)
        sys.argv.append("deepar.skip_cv_estatal=true")

    from scripts.entrena import main as entrena_main

    entrena_main()

    if entorno == "sagemaker":
        copiar_modelos_salida()
        logger.debug("Entrenamiento SageMaker finalizado. Modelos en {}", SAGEMAKER_MODEL_DIR)


if __name__ == "__main__":
    main()
