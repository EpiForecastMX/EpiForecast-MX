#!/usr/bin/env python3
"""Sella el paquete historico del paper MICAI 2026 (paso 1 de la secuencia autorizada).

Materializa, desde la cache local de DVC y desde git, los artefactos exactos con los que
se escribio el paper, y escribe un MANIFEST inmutable con commit, hash DVC y SHA-256 de
cada pieza. Nada de rutas vivas: quien quiera un numero del paper lo saca de aqui.

Composicion del paquete y por que:
  - pronosticos y metricas CV -> c13e7163 (los modelos quedaron congelados ahi; el
    horizonte del pronostico llega a 2027-01-25, asi que la fecha del commit no limita
    la ventana evaluable)
  - observaciones             -> b43ebdf2 (panel del boletin ya con W18, que es la
    ventana que evalua la Tabla 2; el dataset de c13e7163 solo llega a W8)

Uso:  ../../.venv/bin/python sella_bundle.py
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

RAIZ = Path(__file__).resolve().parents[2]
CACHE = RAIZ / ".dvc/cache/files/md5"
DESTINO = Path(os.environ.get("EPIFORECAST_BUNDLE", RAIZ / "Congresos/MICAI/bundle_historico"))

COMMIT_MODELOS = "c13e7163"
COMMIT_OBSERVACIONES = "b43ebdf2"

# (nombre en el bundle, commit, ruta del .dvc o del blob, tipo)
PIEZAS = [
    ("tableau.csv", COMMIT_MODELOS, "data/processed/tableau.csv.dvc", "dvc"),
    (
        "dataset_boletin_epidemiologico.csv",
        COMMIT_OBSERVACIONES,
        "data/processed/dataset_boletin_epidemiologico.csv.dvc",
        "dvc",
    ),
    (
        "tabla_333_modelos_produccion.xlsx",
        COMMIT_MODELOS,
        "reports/ProdDetails/tabla_333_modelos_produccion.xlsx",
        "git",
    ),
]
FORECASTS = ["deepar", "prophet", "ensemble", "stacking"]


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(RAIZ), *args], check=True, capture_output=True).stdout


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def desde_cache(md5: str) -> Path:
    p = CACHE / md5[:2] / md5[2:]
    if not p.exists():
        raise SystemExit(f"FALTA en la cache de DVC: {md5}\n  esperado en {p}")
    return p


def md5_del_dvc(commit: str, ruta_dvc: str) -> str:
    texto = git("show", f"{commit}:{ruta_dvc}").decode()
    for linea in texto.splitlines():
        if "md5:" in linea:
            return linea.split("md5:")[1].strip()
    raise SystemExit(f"sin md5 en {commit}:{ruta_dvc}")


def enlaza(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() or destino.is_symlink():
        destino.unlink()
    destino.symlink_to(origen.resolve())


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    entradas = []

    for nombre, commit, ruta, tipo in PIEZAS:
        destino = DESTINO / nombre
        if tipo == "dvc":
            md5 = md5_del_dvc(commit, ruta)
            enlaza(desde_cache(md5), destino)
            origen = f"dvc:{md5}"
        else:
            destino.write_bytes(git("show", f"{commit}:{ruta}"))
            md5 = hashlib.md5(destino.read_bytes()).hexdigest()  # noqa: S324
            origen = f"git:{commit}:{ruta}"
        entradas.append(
            dict(
                nombre=nombre,
                commit=commit,
                origen=origen,
                md5=md5,
                sha256=sha256(destino),
                bytes=destino.stat().st_size,
            )
        )
        print(f"  sellado  {nombre}")

    # los cuatro all_forecast salen del arbol DVC de reports/forecasts
    md5_dir = md5_del_dvc(COMMIT_MODELOS, "reports/forecasts.dvc")
    arbol = json.loads(desde_cache(md5_dir).read_text())
    por_ruta = {e["relpath"]: e["md5"] for e in arbol}
    for motor in FORECASTS:
        rel = f"{motor}/all_forecast_{motor}.csv"
        if rel not in por_ruta:
            raise SystemExit(f"{rel} no esta en el arbol {md5_dir}")
        destino = DESTINO / "forecasts" / rel
        enlaza(desde_cache(por_ruta[rel]), destino)
        entradas.append(
            dict(
                nombre=f"forecasts/{rel}",
                commit=COMMIT_MODELOS,
                origen=f"dvc:{md5_dir}#{rel}",
                md5=por_ruta[rel],
                sha256=sha256(destino),
                bytes=destino.stat().st_size,
            )
        )
        print(f"  sellado  forecasts/{rel}")

    manifiesto = dict(
        proyecto="EpiForecast-MX / MICAI 2026 paper #12",
        proposito="Paquete historico congelado: unica fuente autorizada de cifras del paper.",
        sellado_utc=datetime.now(UTC).isoformat(timespec="seconds"),
        commit_modelos=COMMIT_MODELOS,
        commit_observaciones=COMMIT_OBSERVACIONES,
        arbol_forecasts=md5_dir,
        piezas=entradas,
    )
    (DESTINO / "MANIFEST.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n"
    )

    lineas = [
        "# MANIFEST — paquete historico MICAI 2026",
        "",
        f"Sellado: {manifiesto['sellado_utc']}",
        "",
        f"- Modelos, pronosticos y metricas CV: `{COMMIT_MODELOS}`",
        f"- Observaciones del boletin (hasta W18): `{COMMIT_OBSERVACIONES}`",
        f"- Arbol DVC de forecasts: `{md5_dir}`",
        "",
        "| pieza | md5 | sha256 | bytes |",
        "|---|---|---|---|",
    ]
    for e in entradas:
        lineas.append(
            f"| `{e['nombre']}` | `{e['md5'][:16]}` | `{e['sha256'][:16]}` | {e['bytes']:,} |"
        )
    (DESTINO / "MANIFEST.md").write_text("\n".join(lineas) + "\n")

    print(f"\n  MANIFEST -> {DESTINO / 'MANIFEST.json'}")
    print(f"  {len(entradas)} piezas selladas")


if __name__ == "__main__":
    main()
