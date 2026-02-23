# aws/sagemaker_launcher.py
"""
Lanza Training Jobs en SageMaker con tracking de experimentos.

Uso:
    python aws/sagemaker_launcher.py                    # Usa config/experimentos.yaml
    python aws/sagemaker_launcher.py --local            # Test local con Docker
    python aws/sagemaker_launcher.py --build             # Build + push imagen a ECR
    python aws/sagemaker_launcher.py --build --launch    # Build + lanzar job

Requisitos:
    - AWS CLI configurado (aws configure)
    - Docker instalado (para --build)
    - IAM role con permisos de SageMaker (config/experimentos.yaml → aws.sagemaker.role_arn)
"""

import argparse
import json
import subprocess
import sys

from omegaconf import OmegaConf
from pathlib import Path


def cargar_config(config_path="config/experimentos.yaml"):
    config = OmegaConf.load(config_path)
    return OmegaConf.to_container(config, resolve=True)


def build_and_push_image(config):
    """Construye la imagen Docker y la sube a ECR."""
    aws_config = config["aws"]["sagemaker"]
    region = aws_config["region"]
    repo = aws_config["ecr_repository"]
    tag = aws_config["image_tag"]

    # Obtener account ID
    result = subprocess.run(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
        capture_output=True, text=True, check=True,
    )
    account_id = result.stdout.strip()
    image_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}"

    print(f"Construyendo imagen: {image_uri}")

    # Login a ECR
    subprocess.run(
        f"aws ecr get-login-password --region {region} | "
        f"docker login --username AWS --password-stdin {account_id}.dkr.ecr.{region}.amazonaws.com",
        shell=True, check=True,
    )

    # Crear repositorio si no existe
    subprocess.run(
        ["aws", "ecr", "describe-repositories", "--repository-names", repo, "--region", region],
        capture_output=True,
    )
    subprocess.run(
        ["aws", "ecr", "create-repository", "--repository-name", repo, "--region", region],
        capture_output=True,
    )

    # Build y push (forzar amd64 para SageMaker)
    subprocess.run(
        ["docker", "build", "--platform", "linux/amd64",
         "-t", repo, "-f", "aws/Dockerfile", "."],
        check=True,
    )
    subprocess.run(["docker", "tag", f"{repo}:{tag}", image_uri], check=True)
    subprocess.run(["docker", "push", image_uri], check=True)

    print(f"Imagen subida: {image_uri}")
    return image_uri


def launch_training_job(config, image_uri=None):
    """Lanza un SageMaker Training Job."""
    try:
        import sagemaker
        from sagemaker.estimator import Estimator
    except ImportError:
        print("ERROR: pip install sagemaker")
        sys.exit(1)

    aws_config = config["aws"]["sagemaker"]
    exp_config = config["experimentos"]

    role = aws_config["role_arn"]
    if not role:
        print("ERROR: Configura aws.sagemaker.role_arn en config/experimentos.yaml")
        sys.exit(1)

    region = aws_config["region"]

    # Si no se proporcionó image_uri, construirla del config
    if image_uri is None:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
            capture_output=True, text=True, check=True,
        )
        account_id = result.stdout.strip()
        repo = aws_config["ecr_repository"]
        tag = aws_config["image_tag"]
        image_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}"

    session = sagemaker.Session()

    # Métricas que SageMaker parsea de los logs en tiempo real
    metric_definitions = [
        # --- Cross-validation ---
        {"Name": "cv_rmse",          "Regex": r"cv_rmse:\s+([0-9.]+)"},
        {"Name": "cv_rmse_std",      "Regex": r"cv_rmse_std:\s+([0-9.]+)"},
        # --- Test set (escala log) ---
        {"Name": "test_rmse",        "Regex": r"test_rmse:\s+([0-9.]+)"},
        {"Name": "test_mae",         "Regex": r"test_mae:\s+([0-9.]+)"},
        {"Name": "test_mape",        "Regex": r"test_mape:\s+([0-9.]+)"},
        # --- Test set (escala original) ---
        {"Name": "test_rmse_orig",   "Regex": r"test_rmse_original_scale:\s+([0-9.]+)"},
        {"Name": "test_mae_orig",    "Regex": r"test_mae_original_scale:\s+([0-9.]+)"},
        {"Name": "test_mape_orig",   "Regex": r"test_mape_original_scale:\s+([0-9.]+)"},
        # --- Timing ---
        {"Name": "duracion_seg",     "Regex": r"duracion_segundos:\s+([0-9.]+)"},
        # --- Per-fold breakdown ---
        {"Name": "fold1_rmse",       "Regex": r"best_fold1_rmse:\s+([0-9.]+)"},
        {"Name": "fold2_rmse",       "Regex": r"best_fold2_rmse:\s+([0-9.]+)"},
        {"Name": "fold3_rmse",       "Regex": r"best_fold3_rmse:\s+([0-9.]+)"},
        {"Name": "fold4_rmse",       "Regex": r"best_fold4_rmse:\s+([0-9.]+)"},
    ]

    # Crear Estimator
    estimator = Estimator(
        image_uri=image_uri,
        role=role,
        instance_count=aws_config.get("instance_count", 1),
        instance_type=aws_config.get("instance_type", "ml.m5.xlarge"),
        volume_size=aws_config.get("volume_size_gb", 30),
        max_run=aws_config.get("max_runtime_seconds", 86400),
        output_path=aws_config.get("output_s3", "s3://epiforecast-mx-data/experiments/"),
        sagemaker_session=session,
        metric_definitions=metric_definitions,
        enable_sagemaker_metrics=True,
        environment={
            "PYTHONPATH": "/opt/ml/code",
            "PYTHONUNBUFFERED": "1",
            "AWS_DEFAULT_REGION": region,
        },
        # Config ya está baked en la imagen Docker (config/experimentos.yaml)
    )

    # Canal de datos: subir CSV de entrenamiento a S3
    data_path = "data/processed/"
    print(f"Buscando datos en: {data_path}")

    csvs = list(Path(data_path).glob("data_inegi_*.csv"))
    if not csvs:
        print(f"ERROR: No se encontraron archivos data_inegi_*.csv en {data_path}")
        sys.exit(1)

    # Subir datos a S3 y lanzar
    training_input = session.upload_data(
        path=str(csvs[0]),
        key_prefix="experiments/input",
    )

    print(f"Datos subidos a: {training_input}")
    print(f"Lanzando Training Job con {aws_config['instance_type']}...")

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_name = f"epiforecast-{timestamp}"

    estimator.fit(
        inputs={"training": training_input},
        job_name=job_name,
        wait=False,  # No bloquear — monitorear desde consola de SageMaker
    )

    print(f"Training Job lanzado: {estimator.latest_training_job.name}")
    print(f"Monitorear en: https://{region}.console.aws.amazon.com/sagemaker/home"
          f"?region={region}#/jobs/{estimator.latest_training_job.name}")

    return estimator


def test_local(config):
    """Prueba local con Docker (simula entorno SageMaker)."""
    print("Ejecutando prueba local con Docker...")

    data_dir = Path("data/processed")
    csvs = list(data_dir.glob("data_inegi_*.csv"))
    if not csvs:
        print(f"ERROR: No se encontraron data_inegi_*.csv en {data_dir}")
        sys.exit(1)

    repo = config["aws"]["sagemaker"]["ecr_repository"]

    cmd = [
        "docker", "run",
        "--rm",
        "-v", f"{csvs[0].resolve()}:/opt/ml/input/data/training/{csvs[0].name}",
        "-v", f"{Path('experiments').resolve()}:/opt/ml/model",
        repo,
    ]

    print(f"Comando: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description="Lanzar entrenamiento en SageMaker")
    parser.add_argument("--build", action="store_true", help="Build y push imagen a ECR")
    parser.add_argument("--launch", action="store_true", help="Lanzar Training Job")
    parser.add_argument("--local", action="store_true", help="Test local con Docker")
    parser.add_argument(
        "--config", default="config/experimentos.yaml",
        help="Ruta al YAML de configuración (default: config/experimentos.yaml)",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: No existe {config_path}")
        sys.exit(1)

    # Si se usa un config distinto al default, copiarlo como experimentos.yaml
    # (Docker bake: COPY config/ config/ → lee config/experimentos.yaml)
    default_path = Path("config/experimentos.yaml")
    if config_path.resolve() != default_path.resolve():
        import shutil
        print(f"📋 Copiando {config_path} → {default_path} (para Docker bake)")
        shutil.copy2(config_path, default_path)

    config = cargar_config(str(default_path))

    if args.local:
        test_local(config)
        return

    image_uri = None
    if args.build:
        image_uri = build_and_push_image(config)

    if args.launch:
        launch_training_job(config, image_uri)
    elif not args.build:
        parser.print_help()


if __name__ == "__main__":
    main()
