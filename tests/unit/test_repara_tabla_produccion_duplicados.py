"""La reparación de la tabla de producción: mínima, ligada a la autoridad y reproducible."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import zipfile

import pandas as pd
import pytest
from scripts import repara_tabla_produccion_duplicados as rep


def _tabla(ruta: Path, *, duplicar_deepar: bool = True, detalle: bool = True) -> None:
    filas = [
        (1, "Alzheimer", "Aguascalientes", "general", "Prophet", 10.0),
        (2, "Dengue", "Nacional", "general", "Prophet", 35.2),
        (3, "Dengue", "Nacional", "hombres", "Prophet", 38.4),
        (4, "Dengue", "Aguascalientes", "general", "DeepAR", 50.0),
    ]
    if duplicar_deepar:
        filas += [
            (5, "Dengue", "Nacional", "general", "DeepAR", 109.6),
            (6, "Dengue", "Nacional", "hombres", "DeepAR", 79.5),
        ]
    filas.append((len(filas) + 1, "Parkinson", "Aguascalientes", "general", "Ensemble", 12.0))
    prod = pd.DataFrame(
        filas,
        columns=["numero", "padecimiento", "entidad", "sexo", "modelo_produccion", "smape_prod"],
    )
    hojas = {"Produccion": prod}
    if detalle:
        hojas["Detalle Semanal"] = prod[
            ["numero", "padecimiento", "entidad", "sexo", "modelo_produccion"]
        ].assign(pron_sem_1=range(len(prod)))
    hojas["Análisis Visual"] = pd.DataFrame({"nota": ["sin gráficos"]})
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        for nombre, hoja in hojas.items():
            hoja.to_excel(w, sheet_name=nombre, index=False)


def _autoridad(ruta: Path, motor_nacional: str = "Prophet") -> None:
    pd.DataFrame(
        {
            "padecimiento": ["Dengue"] * 3,
            "entidad": ["Nacional", "Nacional", "Aguascalientes"],
            "sexo": ["general", "hombres", "general"],
            "motor_productivo": [motor_nacional, motor_nacional, "DeepAR"],
        }
    ).to_csv(ruta, index=False)


def test_conserva_la_fila_de_la_autoridad_en_todas_las_hojas_y_renumera(tmp_path: Path) -> None:
    tabla, autoridad, salida = tmp_path / "t.xlsx", tmp_path / "a.csv", tmp_path / "out.xlsx"
    _tabla(tabla)
    _autoridad(autoridad)

    assert (
        rep.main(["--tabla", str(tabla), "--autoridad", str(autoridad), "--out", str(salida)]) == 0
    )

    prod = pd.read_excel(salida, sheet_name="Produccion")
    assert len(prod) == 5
    assert list(prod["numero"]) == [1, 2, 3, 4, 5], "numero == posición"
    nacionales = prod[(prod.entidad == "Nacional")]
    assert list(nacionales["modelo_produccion"]) == ["Prophet", "Prophet"]
    assert list(nacionales["smape_prod"]) == [35.2, 38.4], (
        "las métricas de la fila conservada, intactas"
    )
    assert not prod.duplicated(["padecimiento", "entidad", "sexo"]).any()
    detalle = pd.read_excel(salida, sheet_name="Detalle Semanal")
    assert len(detalle) == 5 and list(detalle["numero"]) == [1, 2, 3, 4, 5]
    assert list(detalle["pron_sem_1"]) == [0, 1, 2, 3, 6], (
        "se retiran las mismas filas en el detalle"
    )
    assert pd.read_excel(salida, sheet_name="Análisis Visual").iloc[0, 0] == "sin gráficos"


def test_dos_corridas_dan_el_mismo_sha256(tmp_path: Path) -> None:
    tabla, autoridad = tmp_path / "t.xlsx", tmp_path / "a.csv"
    _tabla(tabla)
    _autoridad(autoridad)
    uno, dos = tmp_path / "uno.xlsx", tmp_path / "dos.xlsx"
    assert rep.main(["--tabla", str(tabla), "--autoridad", str(autoridad), "--out", str(uno)]) == 0
    assert rep.main(["--tabla", str(tabla), "--autoridad", str(autoridad), "--out", str(dos)]) == 0
    assert (
        hashlib.sha256(uno.read_bytes()).hexdigest()
        == hashlib.sha256(dos.read_bytes()).hexdigest()
    )
    # Lo que openpyxl estampa con el reloj queda fijado: hora de guardado y fechas del ZIP.
    with zipfile.ZipFile(uno) as z:
        nucleo = z.read("docProps/core.xml").decode("utf-8")
        assert nucleo.count("2026-09-02T00:00:00Z") == 2, "created y modified fijadas"
        assert {i.date_time for i in z.infolist()} == {(1980, 1, 1, 0, 0, 0)}


@pytest.mark.parametrize(
    ("motor_autoridad", "mensaje"),
    [
        ("DeepAR", "conserva fila 5"),  # la autoridad manda: si dijera DeepAR, se conserva DeepAR
        ("NBGLM", "0 fila\\(s\\) que casan"),  # ninguna fila casa: no se inventa
    ],
)
def test_la_autoridad_decide_y_sin_ella_no_se_toca_nada(
    tmp_path: Path, motor_autoridad: str, mensaje: str, capsys
) -> None:
    tabla, autoridad, salida = tmp_path / "t.xlsx", tmp_path / "a.csv", tmp_path / "out.xlsx"
    _tabla(tabla)
    _autoridad(autoridad, motor_nacional=motor_autoridad)

    rc = rep.main(["--tabla", str(tabla), "--autoridad", str(autoridad), "--out", str(salida)])

    if motor_autoridad == "DeepAR":
        assert rc == 0 and mensaje in capsys.readouterr().out
        prod = pd.read_excel(salida, sheet_name="Produccion")
        assert list(prod[prod.entidad == "Nacional"]["modelo_produccion"]) == ["DeepAR", "DeepAR"]
    else:
        assert rc == 1
        assert not salida.exists()
        assert re.search(mensaje, capsys.readouterr().err)


def test_sin_duplicados_no_hay_nada_que_reparar(tmp_path: Path, capsys) -> None:
    tabla, autoridad, salida = tmp_path / "t.xlsx", tmp_path / "a.csv", tmp_path / "out.xlsx"
    _tabla(tabla, duplicar_deepar=False)
    _autoridad(autoridad)
    assert (
        rep.main(["--tabla", str(tabla), "--autoridad", str(autoridad), "--out", str(salida)]) == 1
    )
    assert "nada que reparar" in capsys.readouterr().err
    assert not salida.exists()


def test_una_clave_repetida_fuera_de_la_autoridad_aborta(tmp_path: Path, capsys) -> None:
    tabla, autoridad, salida = tmp_path / "t.xlsx", tmp_path / "a.csv", tmp_path / "out.xlsx"
    _tabla(tabla)
    pd.DataFrame(
        {
            "padecimiento": ["Dengue"],
            "entidad": ["Nacional"],
            "sexo": ["general"],
            "motor_productivo": ["Prophet"],
        }
    ).to_csv(autoridad, index=False)
    assert (
        rep.main(["--tabla", str(tabla), "--autoridad", str(autoridad), "--out", str(salida)]) == 1
    )
    assert "no está en la autoridad" in capsys.readouterr().err
    assert not salida.exists()
