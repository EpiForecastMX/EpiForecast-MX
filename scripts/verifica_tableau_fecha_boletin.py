"""Gate del XLSX de Tableau tras introducir `fecha_boletin`.

Se escribe ANTES de regenerar el archivo: un gate redactado despues de ver el resultado
solo comprueba que el resultado es el que se vio.

Contrato (auditoria 20-ago-2026):
  · `fecha_boletin` vive SOLO en scaffold, nunca en real ni en forecast;
  · vale exactamente `ds + 7 dias` en el 100% de las filas, sin nulos;
  · las cuatro llaves originales de scaffold quedan intactas y sin duplicados;
  · las demas hojas no cambian de forma;
  · la ultima observacion real, al relacionarla con scaffold, cae en 2026-07-27 (W31);
  · nada de Obesidad en lo que se publica.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

XLSX = Path("data/processed/tableau_model.xlsx")
LLAVES = ["ds", "entidad", "padecimiento", "meta_modo"]
FORMA = {
    "scaffold": (227106, 5),
    "real": (72705, 6),
    "forecast": (227106, 5),
    "metricas": (333, 10),
    "entidades": (37, 12),
}


def main() -> int:
    hojas = {n: pd.read_excel(XLSX, sheet_name=n) for n in FORMA}
    fallos: list[str] = []

    def revisa(ok: bool, mensaje: str) -> None:
        print(f"  {'ok    ' if ok else 'FALLA '} {mensaje}")
        if not ok:
            fallos.append(mensaje)

    print("── Forma de las hojas ──")
    for n, (filas, cols) in FORMA.items():
        real = hojas[n].shape
        revisa(
            real == (filas, cols), f"{n}: {real[0]:,} x {real[1]} (esperado {filas:,} x {cols})"
        )

    print("\n── fecha_boletin ──")
    s = hojas["scaffold"]
    revisa("fecha_boletin" in s.columns, "scaffold tiene la columna")
    if "fecha_boletin" in s.columns:
        fb, ds = pd.to_datetime(s.fecha_boletin), pd.to_datetime(s.ds)
        revisa(
            bool((fb == ds + pd.Timedelta(weeks=1)).all()),
            "vale ds + 7 dias en el 100% de las filas",
        )
        revisa(int(fb.isna().sum()) == 0, "sin nulos")
        revisa(str(fb.dtype).startswith("datetime"), f"tipo fecha valido ({fb.dtype})")
    for otra in ("real", "forecast"):
        revisa(
            "fecha_boletin" not in hojas[otra].columns,
            f"{otra} NO la repite (evita columnas temporales ambiguas)",
        )

    print("\n── Llaves relacionales ──")
    revisa(
        list(s.columns[:4]) == LLAVES,
        f"scaffold conserva y ordena las 4 llaves: {list(s.columns[:4])}",
    )
    revisa(int(s.duplicated(LLAVES).sum()) == 0, "sin duplicados en las 4 llaves")
    for otra in ("real", "forecast"):
        faltan = set(LLAVES if otra == "forecast" else LLAVES[:3]) - set(hojas[otra].columns)
        revisa(not faltan, f"{otra} conserva sus llaves de union")

    print("\n── Corte semanal visible ──")
    r = hojas["real"].copy()
    r["ds"] = pd.to_datetime(r.ds)
    ultima = r.ds.max()
    esperado = pd.Timestamp("2026-07-27")
    fb_ultima = ultima + pd.Timedelta(weeks=1)
    revisa(
        fb_ultima == esperado,
        f"ultima real ds={ultima.date()} -> fecha_boletin={fb_ultima.date()} "
        f"(esperado {esperado.date()})",
    )
    revisa(
        int(fb_ultima.isocalendar().week) == 31,
        f"esa fecha cae en la semana {fb_ultima.isocalendar().week} (esperado 31)",
    )

    print("\n── Cohorte publicada ──")
    pads = set()
    for n in ("scaffold", "real", "forecast"):
        if "padecimiento" in hojas[n]:
            pads |= set(hojas[n].padecimiento.dropna().unique())
    revisa(not ({"Obesidad", "Anorexia"} & pads), f"padecimientos publicados: {sorted(pads)}")

    total = sum((len(d) + 1) * d.shape[1] for d in hojas.values())
    print(f"\n  celdas totales con encabezados: {total:,}")
    print(
        "\n"
        + (
            "✔ El XLSX cumple el contrato."
            if not fallos
            else f"✖ {len(fallos)} incumplimiento(s)."
        )
    )
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
