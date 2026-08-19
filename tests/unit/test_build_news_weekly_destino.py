"""El generador de novedades debe escribir donde se le dice, y solo ahí.

`bump_static_html` ignoraba la ruta recibida y usaba la constante global del repositorio.
El efecto era doble y silencioso: en el refresh semanal `news.json` iba al staging pero
`index.html` y `novedades.html` acababan en el sitio real, de modo que el sello quedaba
incompleto —esos dos archivos nunca entraban al inventario— y el sitio se modificaba
aunque la corrida no publicara nada. Aplicar ese sello sobre un clon limpio habría dejado
la portada y Novedades en la semana vieja con el resto en la nueva.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.build_news_weekly import DASHBOARD, bump_static_html

PORTADA = """<html><body>
<div class="dateline">Edición de la semana 27, 2026</div>
<div class="news-lead-title">Ya contamos con la semana epidemiológica 27 de 2026</div>
<span class="news-date">21 de julio de 2026</span>
<div class="news-lead-sub">texto anterior</div>
</body></html>
"""

NOVEDADES = """<html><body>
<div class="dateline">Edición de la semana 27, 2026</div>
</body></html>
"""


@pytest.fixture
def destino(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(PORTADA, encoding="utf-8")
    (tmp_path / "novedades.html").write_text(NOVEDADES, encoding="utf-8")
    return tmp_path


def _datos() -> tuple[dict, dict]:
    data = {"week": 31, "year": 2026}
    item = {
        "title": "Ya contamos con la semana epidemiológica 31 de 2026",
        "iso": "2026-08-18",
        "date": "18 de agosto de 2026",
        "body": ["…"],
    }
    return data, item


def test_escribe_en_el_destino_recibido(destino: Path) -> None:
    data, item = _datos()
    bump_static_html(data, item, destino)

    for nombre in ("index.html", "novedades.html"):
        html = (destino / nombre).read_text(encoding="utf-8")
        assert "Edición de la semana 31, 2026" in html
        assert "Edición de la semana 27, 2026" not in html


def test_actualiza_tambien_el_lead_de_la_portada(destino: Path) -> None:
    data, item = _datos()
    bump_static_html(data, item, destino)

    portada = (destino / "index.html").read_text(encoding="utf-8")
    assert "semana epidemiológica 31 de 2026" in portada
    assert "semana epidemiológica 27 de 2026" not in portada


def test_no_toca_el_dashboard_canonico(destino: Path) -> None:
    """La prueba que faltaba: el sitio real no puede moverse por una corrida dirigida."""
    canonicos = {
        p: p.read_bytes()
        for nombre in ("index.html", "novedades.html")
        if (p := DASHBOARD / nombre).is_file()
    }
    if not canonicos:
        pytest.skip("el dashboard canónico no está presente en este entorno")

    data, item = _datos()
    bump_static_html(data, item, destino)

    intactos = {p: p.read_bytes() == contenido for p, contenido in canonicos.items()}
    assert all(intactos.values()), (
        f"se modificó el sitio real: {[str(p) for p, ok in intactos.items() if not ok]}"
    )


def test_un_destino_sin_esos_archivos_no_falla(tmp_path: Path) -> None:
    """El generador salta lo que no existe en vez de romper la corrida."""
    data, item = _datos()
    bump_static_html(data, item, tmp_path)

    assert not list(tmp_path.iterdir())
