# aws/Dockerfile
# Imagen de entrenamiento para SageMaker Training Jobs
#
# Build:
#   docker build -t epiforecast-mx-training -f aws/Dockerfile .
#
# Test local:
#   docker run -v $(pwd)/data/processed:/opt/ml/input/data/training \
#              -v $(pwd)/experiments:/opt/ml/model \
#              epiforecast-mx-training

FROM python:3.12-slim

# Dependencias del sistema (gcc para cmdstanpy/Prophet)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/ml/code

# Instalar dependencias Python (cache de capas Docker)
COPY aws/requirements_train.txt .
COPY aws/requirements_aws.txt .
COPY aws/requirements_dl.txt .
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r requirements_train.txt \
    && pip install --no-cache-dir -r requirements_aws.txt \
    && pip install --no-cache-dir -r requirements_dl.txt

# Copiar código fuente
COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/

# Crear directorios necesarios
RUN mkdir -p /opt/ml/model /opt/ml/output logs experiments

# SageMaker Training Toolkit ejecuta el script definido en SAGEMAKER_PROGRAM
ENV SAGEMAKER_PROGRAM=scripts/entrena_aws.py
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/opt/ml/code

# Entry point compatible con SageMaker y ejecución directa
ENTRYPOINT ["python", "-m", "scripts.entrena_aws"]
