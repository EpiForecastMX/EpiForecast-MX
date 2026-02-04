# -*- coding: utf-8 -*-
"""
scrape_boletines.py - Scraper automatizado de boletines SINAVE.

Ubicacion: scripts/scrape_boletines.py

Uso local (sin S3):
  cd EpiForecast-MX
  python scripts/scrape_boletines.py

Variables de entorno (para CI/CD):
  S3_BUCKET, S3_PREFIX, AWS_REGION, SNS_TOPIC_ARN
"""

import os
import re
import sys
import json
import logging
import requests
import boto3
from pathlib import Path
from datetime import datetime, timezone

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
BASE_URL = "https://www.gob.mx"
TARGET_URL = (
    f"{BASE_URL}/salud/documentos/"
    "boletinepidemiologico-sistema-nacional-de-vigilancia-"
    "epidemiologica-sistema-unico-de-informacion-417103"
)

# Directorio raiz del proyecto (un nivel arriba de scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Paths relativos al repo
REGISTRY_PATH = PROJECT_ROOT / "data" / "registry.json"
LOCAL_PDF_DIR = PROJECT_ROOT / "data" / "raw_PDFs"

# AWS
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_PREFIX = os.getenv("S3_PREFIX", "raw/boletines/")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────
def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH, "r") as f:
            return json.load(f)
    return {"bulletins": {}}


def save_registry(registry: dict) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    log.info("Registry actualizado: %s", REGISTRY_PATH)


# ──────────────────────────────────────────────
# Scraper
# ──────────────────────────────────────────────
def scrape_bulletins() -> list[dict]:
    """
    Estructura real de la pagina:
      <li class="clearfix documents">
        <div>Semana Epidemiologica 03</div>
        <div>
          <a class="btn btn-default"
             href="/cms/uploads/attachment/file/.../Boletin-0326.pdf"
             onclick="a_onClick('salud', 'Semana Epidemiologica 03')">
          </a>
        </div>
      </li>
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # User-agent para evitar bloqueos en headless
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)
    bulletins = []

    try:
        log.info("Navegando a %s", TARGET_URL)
        driver.get(TARGET_URL)

        # Esperar a que carguen los <li> de boletines
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "li.clearfix.documents")
            )
        )

        # Cada <li class="clearfix documents"> es un boletin
        items = driver.find_elements(
            By.CSS_SELECTOR, "li.clearfix.documents"
        )
        log.info("Encontrados %d boletines en la pagina", len(items))

        for item in items:
            # Texto del div: "Semana Epidemiologica 03"
            text = item.text.strip()
            match = re.search(r"(\d+)", text)
            semana = match.group(1).zfill(2) if match else None

            # Link de descarga dentro del <li>
            try:
                link = item.find_element(
                    By.CSS_SELECTOR, "a.btn.btn-default"
                )
                href = link.get_attribute("href") or ""
            except Exception:
                href = ""

            # URL completa
            if href.startswith("/"):
                full_url = BASE_URL + href
            else:
                full_url = href

            # Filename: YYYY_semWW.pdf
            year = datetime.now().year
            filename = f"{year}_sem{semana}.pdf" if semana else None

            if semana and full_url and filename:
                bulletins.append({
                    "semana": semana,
                    "url": full_url,
                    "filename": filename,
                })

    finally:
        driver.quit()

    return bulletins


# ──────────────────────────────────────────────
# Download + S3
# ──────────────────────────────────────────────
def download_pdf(url: str) -> bytes:
    log.info("Descargando: %s", url)
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    chunks = []
    for chunk in r.iter_content(8192):
        if chunk:
            chunks.append(chunk)
    return b"".join(chunks)


def upload_to_s3(data: bytes, filename: str) -> str:
    s3 = boto3.client("s3", region_name=AWS_REGION)
    key = f"{S3_PREFIX}{filename}"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=data,
        ContentType="application/pdf",
    )
    log.info("Subido a s3://%s/%s", S3_BUCKET, key)
    return key


# ──────────────────────────────────────────────
# Notificacion SNS
# ──────────────────────────────────────────────
def notify(new_bulletins: list[dict]) -> None:
    if not SNS_TOPIC_ARN:
        log.info("SNS_TOPIC_ARN no configurado, skip notificacion")
        return

    sns = boto3.client("sns", region_name=AWS_REGION)
    lines = [
        f"  - Semana {b['semana']}: {b['filename']}"
        for b in new_bulletins
    ]
    message = (
        f"Se detectaron {len(new_bulletins)} boletines nuevos "
        f"({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}):\n\n"
        + "\n".join(lines)
        + f"\n\nSubidos a s3://{S3_BUCKET}/{S3_PREFIX}"
    )
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"SINAVE: {len(new_bulletins)} boletin(es) nuevo(s)",
        Message=message,
    )
    log.info("Notificacion SNS enviada")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main() -> int:
    log.info("=== Inicio scraping boletines SINAVE ===")
    log.info("Proyecto raiz: %s", PROJECT_ROOT)

    # 1. Cargar historial
    registry = load_registry()
    known = set(registry["bulletins"].keys())
    log.info("Boletines conocidos: %d", len(known))

    # 2. Scrape
    bulletins = scrape_bulletins()
    if not bulletins:
        log.warning("No se encontraron boletines en la pagina")
        return 1

    log.info("Boletines en pagina: %d", len(bulletins))

    # 3. Detectar nuevos (no en registry Y no existe el archivo)
    new_bulletins = []
    for b in bulletins:
        already_in_registry = b["semana"] in known
        already_on_disk = (LOCAL_PDF_DIR / b["filename"]).exists()
        if not already_in_registry and not already_on_disk:
            new_bulletins.append(b)
        elif not already_in_registry and already_on_disk:
            # Archivo existe pero no esta en registry, solo registrar
            log.info("Ya existe en disco, registrando: %s", b["filename"])
            registry["bulletins"][b["semana"]] = {
                "url": b["url"],
                "filename": b["filename"],
                "s3_key": str(LOCAL_PDF_DIR / b["filename"]),
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
            }

    if not new_bulletins:
        log.info("No hay boletines nuevos para descargar.")
        # Guardar registry por si se registraron archivos existentes
        save_registry(registry)
        return 0

    log.info("Boletines NUEVOS: %d", len(new_bulletins))

    # 4. Descargar y subir/guardar
    for b in new_bulletins:
        pdf_data = download_pdf(b["url"])

        if S3_BUCKET:
            s3_key = upload_to_s3(pdf_data, b["filename"])
        else:
            LOCAL_PDF_DIR.mkdir(parents=True, exist_ok=True)
            local_path = LOCAL_PDF_DIR / b["filename"]
            with open(local_path, "wb") as f:
                f.write(pdf_data)
            s3_key = str(local_path)
            log.info("Guardado local: %s", local_path)

        registry["bulletins"][b["semana"]] = {
            "url": b["url"],
            "filename": b["filename"],
            "s3_key": s3_key,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }

    # 5. Guardar registry
    save_registry(registry)

    # 6. Notificar
    notify(new_bulletins)

    # 7. Resumen
    for b in new_bulletins:
        print(f"NUEVO: Semana {b['semana']} -> {b['filename']}")

    log.info("=== Fin: %d nuevos boletines procesados ===", len(new_bulletins))
    return 0


if __name__ == "__main__":
    sys.exit(main())