"""El .gitignore no debe esconderle a DVC los punteros de data/.

dulwich >= 1.1 (el que instala `pip install dvc` en los workflows) da por ignorado un
directorio cuando el contenido lo describe un patrón terminado en `/*` o `/**`, y DVC poda
ese directorio sin leer sus `.dvc`. Con `/data/*` el scraper dejó de restaurar los PDFs y
selló durante seis semanas una carpeta de un solo boletín (sep-oct 2026).
"""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


@pytest.mark.contract
def test_ningun_patron_de_data_termina_en_barra_asterisco() -> None:
    patrones = [
        linea.strip()
        for linea in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.lstrip().startswith(("#", "!"))
    ]
    culpables = [p for p in patrones if "data/" in p and p.rstrip("/").endswith(("/*", "/**"))]
    assert culpables == [], f"usar `?*` en lugar de `*` en: {culpables}"
