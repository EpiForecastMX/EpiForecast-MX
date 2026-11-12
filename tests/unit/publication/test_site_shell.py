"""Helper de cabecera/pie comunes para generadores del backend (fragmentos del frontend)."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from epiforecast.publication.site_shell import (
    ESQUEMA,
    FRAGMENTOS,
    ShellError,
    cargar_fragmentos,
    estampa,
    marcadores,
)

pytestmark = pytest.mark.unit

# Copia literal de archivos del frontend (ver tests/fixtures/site_shell/README.md): sin repo hermano.
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "site_shell"


def _dashboard(tmp_path: Path, familias: dict | None = None) -> Path:
    fam = familias or {
        "editorial": {
            "variant": "default",
            "header": '<header id="nav">H</header>',
            "footer": "<footer>F</footer>",
        },
        "epibot": {"variant": "app", "header": '<header class="site-header--app">A</header>'},
    }
    ruta = tmp_path / FRAGMENTOS
    ruta.parent.mkdir(parents=True)
    ruta.write_text(json.dumps({"schema": ESQUEMA, "families": fam}), encoding="utf-8")
    return tmp_path


def _plantilla(variante: str = "default") -> str:
    m = marcadores(variante)
    pie = m.get("footer", "")
    return f"<body>\n{m['header']}\n<main>Contenido</main>\n{pie}\n</body>"


def test_estampa_cabecera_y_pie_y_es_idempotente(tmp_path: Path) -> None:
    frag = cargar_fragmentos(_dashboard(tmp_path))
    una = estampa(_plantilla(), "editorial", frag)
    assert '<header id="nav">H</header>' in una and "<footer>F</footer>" in una
    assert "<main>Contenido</main>" in una
    assert estampa(una, "editorial", frag) == una


def test_variante_app_sin_pie(tmp_path: Path) -> None:
    frag = cargar_fragmentos(_dashboard(tmp_path))
    assert "site-header--app" in estampa(_plantilla("app"), "epibot", frag)
    with pytest.raises(ShellError, match="no lleva pie"):
        estampa(_plantilla(), "epibot", frag)


def test_falla_cerrado_sin_marcadores_familia_o_fragmentos(tmp_path: Path) -> None:
    frag = cargar_fragmentos(_dashboard(tmp_path))
    with pytest.raises(ShellError, match="0/0"):
        estampa("<body>sin marcadores</body>", "editorial", frag)
    with pytest.raises(ShellError, match="familia desconocida"):
        estampa(_plantilla(), "otra", frag)
    with pytest.raises(ShellError, match="2/2"):
        estampa(_plantilla() + _plantilla(), "editorial", frag)
    with pytest.raises(ShellError, match="site_shell.mjs"):
        cargar_fragmentos(tmp_path / "vacio")
    roto = _dashboard(tmp_path / "roto", {"editorial": {"variant": "default", "header": "H"}})
    with pytest.raises(ShellError, match="sin bloque footer"):
        cargar_fragmentos(roto)


def _vacia(html: str) -> str:
    return re.sub(
        r"<!-- site:(header|footer):start -->.*?<!-- site:\1:end -->",
        lambda m: f"<!-- site:{m.group(1)}:start -->\n<!-- site:{m.group(1)}:end -->",
        html,
        flags=re.S,
    )


@pytest.mark.parametrize(
    ("pagina", "familia"),
    [("asma_j45.html", "ficha-release"), ("reporte_resultados.html", "editorial")],
)
def test_con_los_fragmentos_reales_reproduce_la_pagina_byte_a_byte(
    pagina: str, familia: str
) -> None:
    """Una sola fuente: el helper y `site_shell.mjs` dan los mismos bytes (fixture del frontend)."""
    frag = cargar_fragmentos(FIXTURE)
    real = (FIXTURE / pagina).read_text(encoding="utf-8")
    vacia = _vacia(real)
    assert vacia != real
    assert estampa(vacia, familia, frag) == real


def test_la_pagina_actual_de_cada_familia_es_la_que_declara_la_configuracion() -> None:
    """aria-current por familia: page/true según currentKind; ninguno en `editorial`."""
    frag = cargar_fragmentos(FIXTURE)
    cfg = json.loads((FIXTURE / "assets/site/shell.config.json").read_text(encoding="utf-8"))
    hrefs = {p["id"]: p.get("href") for p in cfg["primary"]}
    assert set(frag["families"]) == set(cfg["families"])
    for nombre, fam in cfg["families"].items():
        header = frag["families"][nombre]["header"]
        assert frag["families"][nombre]["variant"] == fam["variant"]
        marcas = re.findall(r'aria-current="(page|true)"', header)
        assert len(set(marcas)) <= 1, nombre
        if fam["current"] in (None, "inicio"):
            assert 'aria-current="' not in header.split("</a>", 1)[1], nombre
            continue
        valor = "page" if fam["currentKind"] == "page" else "true"
        if hrefs.get(fam["current"]):
            assert f'<a href="{hrefs[fam["current"]]}" aria-current="{valor}">' in header, nombre
        else:  # grupo (Congresos): el botón del grupo lleva la marca
            assert "data-current" in header, nombre
        assert "../" not in header, nombre  # fragmentos para la raíz del sitio


def test_bump_cache_no_ve_los_recursos_compartidos_de_epibot() -> None:
    """La cadena de caché del EpiBot sólo versiona recursos de epibot/: los de assets/site van sin
    ?v= (must-revalidate) para que el carril semanal no exija subidas espurias de «../»."""
    from epiforecast.publication.cadena_cache import _RE_RECURSO

    index = (FIXTURE / "epibot_index.html").read_text(encoding="utf-8")
    assert "../assets/site/site.css" in index
    recursos = [r for r, _v in _RE_RECURSO.findall(index)]
    assert recursos and all(not r.startswith("../") for r in recursos)
    assert _RE_RECURSO.findall('<link href="../assets/site/site.css?v=3">') == [
        ("../assets/site/site.css", "3")
    ]
