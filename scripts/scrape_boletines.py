"""
scrape_boletines.py - Scraper automatizado de boletines SINAVE.

Ubicacion: scripts/scrape_boletines.py

Descarga boletines nuevos a data/raw_PDFs/ (versionados con DVC).
Escribe /tmp/sinave_new_files.txt con los nombres de archivos nuevos
para que el workflow de GitHub Actions sepa si debe correr dvc add/push.

Uso local:
  cd EpiForecast-MX
  python scripts/scrape_boletines.py

Variables de entorno (opcionales, para CI/CD):
  SNS_TOPIC_ARN   - ARN del topic SNS para notificaciones
  AWS_REGION       - Region AWS (default: us-east-1)
"""

from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import re
import sys
import time

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By

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

# Flag file para CI/CD: lista de archivos nuevos descargados
NEW_FILES_FLAG = Path("/tmp/sinave_new_files.txt")

# AWS (solo para SNS)
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
        with open(REGISTRY_PATH) as f:
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
DOC_SELECTOR = "li.clearfix.documents"


def _is_challenge(driver) -> bool:
    """True si la pagina actual es el muro anti-bot (reto JS), no el contenido real."""
    title = (driver.title or "").lower()
    if "challenge" in title or "validation" in title or "just a moment" in title:
        return True
    # El reto de gob.mx usa estos contenedores.
    return bool(driver.find_elements(By.CSS_SELECTOR, "#sec-container, #sec-cpt-if"))


def _load_with_challenge(driver, attempts: int = 3, per_attempt: int = 75) -> list:
    """Navega al TARGET_URL y espera a que el reto anti-bot se resuelva y aparezcan los
    documentos. El reto se resuelve solo en JS y RECARGA la pagina; por eso sondeamos el
    DOM en vez de un unico WebDriverWait. Reintenta si expira."""
    for attempt in range(1, attempts + 1):
        log.info("Navegando a %s (intento %d/%d)", TARGET_URL, attempt, attempts)
        driver.get(TARGET_URL)
        deadline = time.time() + per_attempt
        challenge_logged = False
        while time.time() < deadline:
            items = driver.find_elements(By.CSS_SELECTOR, DOC_SELECTOR)
            if items:
                return items
            if _is_challenge(driver):
                if not challenge_logged:
                    log.info("Muro anti-bot detectado; esperando a que el reto se resuelva...")
                    challenge_logged = True
            time.sleep(3)
        log.warning(
            "Intento %d expiro tras %ds (reto sin resolver o DOM cambiado)", attempt, per_attempt
        )

    # Diagnostico para depurar en CI.
    try:
        Path("/tmp/sinave_page.html").write_text(driver.page_source, encoding="utf-8")
        driver.save_screenshot("/tmp/sinave_page.png")
        log.error(
            "Guardado /tmp/sinave_page.html y .png para diagnostico. Titulo: %r", driver.title
        )
    except Exception as e:  # noqa: BLE001
        log.error("No se pudo guardar diagnostico: %s", e)
    return []


def scrape_bulletins() -> list[dict]:
    """
    Estructura real de la pagina:
      <li class="clearfix documents">
        <div>Semana Epidemiologica 03</div>
        <div>
          <a class="btn btn-default"
             href="/cms/uploads/attachment/file/.../Boletin-0326.pdf">
          </a>
        </div>
      </li>
    """
    # gob.mx agrego (jun 2026) un muro anti-bot con reto JavaScript de prueba-de-trabajo
    # ("Challenge Validation"): la pagina carga un reto, lo resuelve en JS y se RECARGA sola
    # con el contenido real. Selenium debe (1) parecer un navegador real (sin huellas de
    # automatizacion) y (2) ESPERAR a que el reto se resuelva antes de buscar los documentos.
    headless = os.getenv("SCRAPER_HEADLESS", "1") != "0"
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=es-MX")
    # Anti-deteccion: oculta las huellas tipicas de Selenium que dispara el muro anti-bot.
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)
    # Borra navigator.webdriver antes de que cargue cualquier script de la pagina.
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
    )
    bulletins = []

    try:
        items = _load_with_challenge(driver)
        log.info("Encontrados %d boletines en la pagina", len(items))

        for item in items:
            text = item.text.strip()
            match = re.search(r"(\d+)", text)
            semana = match.group(1).zfill(2) if match else None

            try:
                link = item.find_element(By.CSS_SELECTOR, "a.btn.btn-default")
                href = link.get_attribute("href") or ""
            except Exception:
                href = ""

            full_url = BASE_URL + href if href.startswith("/") else href

            year = datetime.now().year
            filename = f"{year}_sem{semana}.pdf" if semana else None

            if semana and full_url and filename:
                bulletins.append(
                    {
                        "semana": semana,
                        "url": full_url,
                        "filename": filename,
                    }
                )

    finally:
        driver.quit()

    return bulletins


def download_pdf(url: str, dest: Path) -> None:
    log.info("Descargando: %s", url)
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)
    log.info("Guardado: %s", dest)


# ──────────────────────────────────────────────
# Notificacion SNS
# ──────────────────────────────────────────────
def notify(new_bulletins: list[dict]) -> None:
    if not SNS_TOPIC_ARN:
        log.info("SNS_TOPIC_ARN no configurado, skip notificacion")
        return

    import boto3

    sns = boto3.client("sns", region_name=AWS_REGION)
    lines = [f"  - Semana {b['semana']}: {b['filename']}" for b in new_bulletins]
    message = (
        f"Se detectaron {len(new_bulletins)} boletines nuevos "
        f"({datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}):\n\n"
        + "\n".join(lines)
        + "\n\nVersionados con DVC en EpiForecast-MX."
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
            log.info("Ya existe en disco, registrando: %s", b["filename"])
            registry["bulletins"][b["semana"]] = {
                "url": b["url"],
                "filename": b["filename"],
                "downloaded_at": datetime.now(UTC).isoformat(),
            }

    if not new_bulletins:
        log.info("No hay boletines nuevos para descargar.")
        save_registry(registry)
        return 0

    log.info("Boletines NUEVOS: %d", len(new_bulletins))

    # 4. Descargar localmente a data/raw_PDFs/
    new_filenames = []
    for b in new_bulletins:
        dest = LOCAL_PDF_DIR / b["filename"]
        download_pdf(b["url"], dest)

        registry["bulletins"][b["semana"]] = {
            "url": b["url"],
            "filename": b["filename"],
            "downloaded_at": datetime.now(UTC).isoformat(),
        }
        new_filenames.append(b["filename"])

    # 5. Guardar registry
    save_registry(registry)

    # 6. Escribir flag de archivos nuevos (para CI/CD)
    NEW_FILES_FLAG.write_text("\n".join(new_filenames))
    log.info("Flag de archivos nuevos: %s (%d archivos)", NEW_FILES_FLAG, len(new_filenames))

    # 7. Escribir GITHUB_OUTPUT si estamos en CI
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"new_count={len(new_filenames)}\n")

    # 8. Notificar
    notify(new_bulletins)

    # 9. Resumen
    for b in new_bulletins:
        print(f"NUEVO: Semana {b['semana']} -> {b['filename']}")

    log.info("=== Fin: %d nuevos boletines procesados ===", len(new_bulletins))
    return 0


if __name__ == "__main__":
    sys.exit(main())
