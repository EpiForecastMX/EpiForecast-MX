"""La lista ``DATA`` de la galería sale de lo generado (ronda W37, 444 → 432)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.inyecta_galeria_items import RE_DATA, inyecta


def _item(p: str, f: str) -> dict[str, str]:
    return {"p": p, "n": "X", "c": "Estatal", "s": "General", "f": f}


def _reports(tmp_path: Path, previos: list[dict[str, str]], dengue: list[dict[str, str]]) -> Path:
    rep = tmp_path / "Reports"
    (rep / "dengue").mkdir(parents=True)
    linea = "const DATA = " + json.dumps(previos, ensure_ascii=False) + ";"
    (rep / "index.html").write_text(f"<script>\n{linea}\nconst x = 1;\n</script>\n", "utf-8")
    (rep / "dengue" / "_gallery_items.json").write_text(json.dumps(dengue), "utf-8")
    for it in previos + dengue:
        if "Region_" not in it["f"]:  # los PNG regionales de Dengue ya se retiraron
            (rep / it["f"]).parent.mkdir(parents=True, exist_ok=True)
            (rep / it["f"]).write_bytes(b"png")
    return rep


def _data(rep: Path) -> list[dict[str, str]]:
    m = RE_DATA.search((rep / "index.html").read_text("utf-8"))
    assert m is not None
    return json.loads(m.group(1))


def test_dengue_sale_del_inventario_y_las_regiones_desaparecen(tmp_path: Path) -> None:
    neuro = [_item("Depresión", f"Depresión/E{i}/a.png") for i in range(3)]
    estados = [_item("Dengue", f"dengue/E{i}/Dengue_E{i}_general.png") for i in range(2)]
    region = _item("Dengue", "dengue/Region_Sur/Dengue_Region_Sur_general.png")
    rep = _reports(tmp_path, neuro + estados + [region], estados)

    conteo = inyecta(rep)

    assert conteo == {"Depresión": 3, "Dengue": 2}
    assert _data(rep) == neuro + estados  # orden estable; la región ya no existe
    assert "const x = 1;" in (rep / "index.html").read_text("utf-8")  # el resto, intacto


def test_un_grafico_neuro_sin_png_aborta(tmp_path: Path) -> None:
    neuro = [_item("Parkinson", "Parkinson/E/a.png")]
    estados = [_item("Dengue", "dengue/E/b.png")]
    rep = _reports(tmp_path, neuro, estados)
    (rep / "Parkinson/E/a.png").unlink()
    antes = (rep / "index.html").read_bytes()

    with pytest.raises(FileNotFoundError, match="tarjeta rota"):
        inyecta(rep)
    assert (rep / "index.html").read_bytes() == antes  # no escribe nada a medias


def test_inventario_de_dengue_con_otro_padecimiento_aborta(tmp_path: Path) -> None:
    rep = _reports(tmp_path, [], [_item("Alzheimer", "Alzheimer/E/a.png")])
    with pytest.raises(ValueError, match="no son de Dengue"):
        inyecta(rep)


def test_sin_linea_data_aborta(tmp_path: Path) -> None:
    rep = _reports(tmp_path, [], [_item("Dengue", "dengue/E/b.png")])
    (rep / "index.html").write_text("<html></html>", "utf-8")
    with pytest.raises(ValueError, match="UNA línea"):
        inyecta(rep)
