"""AGENTS.md y GEMINI.md no pueden divergir de CLAUDE.md."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.sync_instrucciones import ESPEJOS, FUENTE, TITULO_FUENTE, divergentes, espejo


@pytest.mark.contract
def test_espejos_sincronizados_con_claude_md() -> None:
    assert divergentes() == [], "Corre make sync-instrucciones tras editar CLAUDE.md"


@pytest.mark.unit
def test_espejo_solo_cambia_titulo_y_aviso() -> None:
    texto = f"## Orden\n\n{TITULO_FUENTE}\n\ncuerpo con {FUENTE}\n"
    salida = espejo(texto, "AGENTS.md")
    assert salida.startswith("## Orden\n\n# AGENTS.md: Guia de Desarrollo EpiForecast-MX\n\n> ")
    assert salida.endswith(f"cuerpo con {FUENTE}\n")


@pytest.mark.unit
def test_detecta_espejo_divergente(tmp_path: Path) -> None:
    (tmp_path / FUENTE).write_text(f"{TITULO_FUENTE}\nx\n", encoding="utf-8")
    for nombre in ESPEJOS:
        (tmp_path / nombre).write_text(espejo(f"{TITULO_FUENTE}\nx\n", nombre), encoding="utf-8")
    assert divergentes(tmp_path) == []
    (tmp_path / "GEMINI.md").write_text("viejo\n", encoding="utf-8")
    assert divergentes(tmp_path) == ["GEMINI.md"]


@pytest.mark.unit
def test_titulo_ausente_falla() -> None:
    with pytest.raises(ValueError):
        espejo("sin título\n", "AGENTS.md")
