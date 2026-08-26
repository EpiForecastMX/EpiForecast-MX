"""Comprobaciones previas de la suite del bundle de MICAI.

Cinco pruebas de esta carpeta leen el PDF entregado con `pdftotext` (poppler). Cuando la
herramienta falta, pytest escupia cinco `FileNotFoundError: 'pdftotext'` sin decir que hacia
falta instalar — asi fallo el CI durante cuatro corridas tras entrar el camera-ready a `main`.

Aqui se falla UNA vez y con instrucciones. Deliberadamente **no se saltan** las pruebas: una
comprobacion que no se puede correr no es una comprobacion que pasa, y estas vigilan que el
PDF entregado no contradiga al .tex.
"""

from __future__ import annotations

import shutil

import pytest


@pytest.fixture(scope="session", autouse=True)
def exige_pdftotext() -> None:
    if shutil.which("pdftotext") is None:
        pytest.fail(
            "falta `pdftotext`, que estas pruebas necesitan para leer el PDF entregado.\n"
            "  · Debian/Ubuntu (y el runner de CI):  sudo apt-get install -y poppler-utils\n"
            "  · macOS:                              brew install poppler\n"
            "No se saltan: comprueban que el PDF no contradiga al .tex del camera-ready.",
            pytrace=False,
        )
