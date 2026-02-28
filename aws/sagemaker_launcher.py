# aws/sagemaker_launcher.py
"""
Lanza Training Jobs DeepAR en SageMaker con GPU (ml.g4dn.xlarge).

Uso:
    python aws/sagemaker_launcher.py --build --launch   # Build imagen + lanzar job
    python aws/sagemaker_launcher.py --build            # Solo build + push a ECR
    python aws/sagemaker_launcher.py --launch           # Lanzar job (imagen ya en ECR)
    python aws/sagemaker_launcher.py --local            # Test local con Docker

Requisitos:
    - AWS CLI configurado (aws configure)
    - Docker instalado (para --build)
    - IAM role con permisos de SageMaker
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import sys

# ---------------------------------------------------------------------------
# Configuracion AWS (cuenta del proyecto)
# ---------------------------------------------------------------------------
AWS_CONFIG = {
    "role_arn": "arn:aws:iam::564141855321:role/SageMakerExecutionRole",
    "region": "us-east-1",
    "instance_type": "ml.g4dn.xlarge",
    "instance_count": 1,
    "max_runtime_seconds": 64800,
    "volume_size_gb": 50,
    "output_s3": "s3://epiforecast-mx-data/training/",
    "ecr_repository": "epiforecast-mx-deepar",
    "image_tag": "latest",
}


def build_and_push_image() -> str:
    """Construye la imagen Docker (amd64) y la sube a ECR."""
    region = AWS_CONFIG["region"]
    repo = AWS_CONFIG["ecr_repository"]
    tag = AWS_CONFIG["image_tag"]

    # Obtener account ID
    result = subprocess.run(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
        capture_output=True,
        text=True,
        check=True,
    )
    account_id = result.stdout.strip()
    image_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}"

    print(f"Construyendo imagen: {image_uri}")

    # Login a ECR
    subprocess.run(
        f"aws ecr get-login-password --region {region} | "
        f"docker login --username AWS --password-stdin "
        f"{account_id}.dkr.ecr.{region}.amazonaws.com",
        shell=True,
        check=True,
    )

    # Crear repositorio si no existe
    subprocess.run(
        ["aws", "ecr", "create-repository", "--repository-name", repo, "--region", region],
        capture_output=True,
    )

    # Build (forzar amd64 para SageMaker) y push
    subprocess.run(
        [
            "docker",
            "build",
            "--platform",
            "linux/amd64",
            "-t",
            repo,
            "-f",
            "aws/Dockerfile",
            ".",
        ],
        check=True,
    )
    subprocess.run(["docker", "tag", f"{repo}:{tag}", image_uri], check=True)
    subprocess.run(["docker", "push", image_uri], check=True)

    print(f"Imagen subida: {image_uri}")
    return image_uri


def launch_training_job(image_uri: str | None = None) -> None:
    """Lanza un SageMaker Training Job con GPU."""
    try:
        import sagemaker
        from sagemaker.estimator import Estimator
    except ImportError:
        print("ERROR: pip install 'sagemaker>=2.200'")
        sys.exit(1)

    role = AWS_CONFIG["role_arn"]
    region = AWS_CONFIG["region"]

    # Si no se proporciono image_uri, construirla del config
    if image_uri is None:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
            capture_output=True,
            text=True,
            check=True,
        )
        account_id = result.stdout.strip()
        repo = AWS_CONFIG["ecr_repository"]
        tag = AWS_CONFIG["image_tag"]
        image_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}"

    session = sagemaker.Session()

    # Metricas que SageMaker parsea de los logs del entrenamiento
    metric_definitions = [
        {"Name": "rmse", "Regex": r"RMSE=([0-9.]+)"},
        {"Name": "mase", "Regex": r"MASE=([0-9.]+)"},
        {"Name": "tiempo_seg", "Regex": r"Total=([0-9.]+)s"},
    ]

    estimator = Estimator(
        image_uri=image_uri,
        role=role,
        instance_count=AWS_CONFIG["instance_count"],
        instance_type=AWS_CONFIG["instance_type"],
        volume_size=AWS_CONFIG["volume_size_gb"],
        max_run=AWS_CONFIG["max_runtime_seconds"],
        output_path=AWS_CONFIG["output_s3"],
        sagemaker_session=session,
        metric_definitions=metric_definitions,
        enable_sagemaker_metrics=True,
        environment={
            "PYTHONPATH": "/opt/ml/code/src:/opt/ml/code",
            "PYTHONUNBUFFERED": "1",
            "AWS_DEFAULT_REGION": region,
        },
    )

    # Canal de datos: buscar CSV de entrenamiento (preferir General = todos los padecimientos)
    data_path = Path("data/processed")
    general_csv = data_path / "data_inegi_General.csv"
    if general_csv.exists():
        csv_to_upload = general_csv
    else:
        csvs = list(data_path.glob("data_inegi_*.csv"))
        if not csvs:
            print(f"ERROR: No se encontraron archivos data_inegi_*.csv en {data_path}")
            sys.exit(1)
        csv_to_upload = csvs[0]

    print(f"CSV seleccionado: {csv_to_upload.name}")

    # Subir datos a S3
    training_input = session.upload_data(
        path=str(csv_to_upload),
        key_prefix="training/input",
    )

    print(f"Datos subidos a: {training_input}")
    print(f"Lanzando Training Job con {AWS_CONFIG['instance_type']}...")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_name = f"epiforecast-deepar-{timestamp}"

    estimator.fit(
        inputs={"training": training_input},
        job_name=job_name,
        wait=False,
    )

    print(f"Training Job lanzado: {estimator.latest_training_job.name}")
    print(
        f"Monitorear en: https://{region}.console.aws.amazon.com/sagemaker/home"
        f"?region={region}#/jobs/{estimator.latest_training_job.name}"
    )
    print(
        f"\nDescargar modelos cuando termine:\n"
        f"  aws s3 sync {AWS_CONFIG['output_s3']}{job_name}/output/ ./models/deepar/"
    )


def test_local() -> None:
    """Prueba local con Docker (simula entorno SageMaker)."""
    print("Ejecutando prueba local con Docker...")

    data_dir = Path("data/processed")
    csvs = list(data_dir.glob("data_inegi_*.csv"))
    if not csvs:
        print(f"ERROR: No se encontraron data_inegi_*.csv en {data_dir}")
        sys.exit(1)

    repo = AWS_CONFIG["ecr_repository"]
    model_dir = Path("models/deepar")
    model_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{csvs[0].resolve()}:/opt/ml/input/data/training/{csvs[0].name}",
        "-v",
        f"{model_dir.resolve()}:/opt/ml/model",
        repo,
    ]

    print(f"Comando: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lanzar entrenamiento DeepAR en SageMaker")
    parser.add_argument("--build", action="store_true", help="Build y push imagen a ECR")
    parser.add_argument("--launch", action="store_true", help="Lanzar Training Job")
    parser.add_argument("--local", action="store_true", help="Test local con Docker")
    args = parser.parse_args()

    if args.local:
        test_local()
        return

    image_uri = None
    if args.build:
        image_uri = build_and_push_image()

    if args.launch:
        launch_training_job(image_uri)
    elif not args.build:
        parser.print_help()


if __name__ == "__main__":
    main()
