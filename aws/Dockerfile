# aws/Dockerfile
# Imagen de entrenamiento DeepAR (GluonTS + PyTorch + CUDA) para SageMaker Training Jobs
#
# Build:
#   docker build --platform linux/amd64 -t epiforecast-mx-deepar -f aws/Dockerfile .
#
# Test local:
#   docker run --gpus all \
#              -v $(pwd)/data/processed:/opt/ml/input/data/training \
#              -v $(pwd)/models:/opt/ml/model \
#              epiforecast-mx-deepar
#
# Imagen base: PyTorch 2.5 con CUDA 12.4 + cuDNN (nvidia/cuda no trae Python)
# SageMaker ml.g4dn.xlarge tiene NVIDIA T4 compatible con CUDA 12.x

FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

# Dependencias del sistema (gcc para cmdstanpy/Prophet)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/ml/code

# Instalar dependencias Python (cache de capas Docker)
# torch ya viene en la imagen base, no reinstalar
COPY aws/requirements_sagemaker.txt .
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r requirements_sagemaker.txt

# Copiar codigo fuente
COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/

# Crear directorios necesarios
RUN mkdir -p /opt/ml/model /opt/ml/output

ENV SAGEMAKER_PROGRAM=scripts/entrena_sagemaker.py
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/opt/ml/code/src:/opt/ml/code

ENTRYPOINT ["python", "-m", "scripts.entrena_sagemaker"]
