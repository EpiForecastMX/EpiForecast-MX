"""Paquete reproducible del artículo de COMIA 2027: tablas, figuras y manifiesto con hashes.

Uso: python -m scripts.paper_comia_paquete

Lee los resultados ya calculados (no recalcula ni publica nada):
- runs/banco_ampliado/v1/ (banco de motores y sus pruebas estadísticas),
- runs/banco_optuna/v2/ (búsqueda anidada),
- runs/banco_sensibilidad/v1/ (sensibilidad sin 2020–2021),
- docs/paper_comia2027/evidencia/ (MLOps, de ``paper_comia_evidencia``),
y escribe en docs/paper_comia2027/ las tablas resumidas (resultados/), las figuras (figuras/) y
MANIFEST.json con el SHA-256 de cada archivo y de cada insumo, más el commit de origen.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
DOC = _ROOT / "docs" / "paper_comia2027"
BANCO = _ROOT / "runs" / "banco_ampliado" / "v1"
OPT = _ROOT / "runs" / "banco_optuna" / "v2"
SEN = _ROOT / "runs" / "banco_sensibilidad" / "v1"
EST = BANCO / "estadistica"
COPIAS = {
    BANCO / "metricas.csv": "banco/metricas.csv",
    BANCO / "motor_fijo.csv": "banco/motor_fijo.csv",
    BANCO / "resumen.json": "banco/resumen.json",
    BANCO / "smape_nacional_por_padecimiento.csv": "banco/smape_nacional_por_padecimiento.csv",
    EST / "titular_interseccion.csv": "banco/titular_interseccion.csv",
    EST / "contra_naive_lag52.csv": "banco/contra_naive_lag52.csv",
    EST / "contra_naive_lag52_bases.csv": "banco/contra_naive_lag52_bases.csv",
    EST / "contra_naive_lag52_wape_bases.csv": "banco/contra_naive_lag52_wape_bases.csv",
    EST / "contra_media_52s.csv": "banco/contra_media_52s.csv",
    EST / "por_pliegue.csv": "banco/por_pliegue.csv",
    EST / "por_estrato.csv": "banco/por_estrato.csv",
    EST / "friedman.json": "banco/friedman.json",
    EST / "victorias_mae.csv": "banco/victorias_mae.csv",
    OPT / "resumen.json": "optuna/resumen.json",
    OPT / "resumen_configuraciones.csv": "optuna/resumen_configuraciones.csv",
    OPT / "pruebas_holm.csv": "optuna/pruebas_holm.csv",
    OPT / "externo_por_padecimiento.csv": "optuna/externo_por_padecimiento.csv",
    SEN / "resumen.csv": "sensibilidad/resumen.csv",
    SEN / "pruebas_holm.csv": "sensibilidad/pruebas_holm.csv",
    SEN / "por_anio.csv": "sensibilidad/por_anio.csv",
    SEN / "procedencia.json": "sensibilidad/procedencia.json",
}
SCRIPTS = [
    "scripts/banco_ampliado.py",
    "scripts/banco_estadistica.py",
    "scripts/banco_optuna.py",
    "scripts/banco_optuna_evalua.py",
    "scripts/banco_sensibilidad.py",
    "scripts/paper_comia_evidencia.py",
    "scripts/paper_comia_paquete.py",
    "src/epiforecast/banco/ajuste.py",
    "src/epiforecast/banco/ajuste_flujo.py",
    "src/epiforecast/banco/estadistica.py",
    "src/epiforecast/banco/estadistica_banco.py",
    "src/epiforecast/banco/sensibilidad.py",
    "config/banco/banco_ampliado_v1.yaml",
]
TINTA, ACENTO, GRIS = "#1E293B", "#4F46E5", "#94A3B8"


def _copiar_texto(src: Path, dst: Path) -> None:
    """Copia con salto de línea final (el hook end-of-file-fixer no alterará el hash)."""
    datos = src.read_bytes()
    dst.write_bytes(datos if datos.endswith(b"\n") else datos + b"\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copiar() -> list[str]:
    hechos = []
    for src, rel in COPIAS.items():
        if not src.exists():
            raise FileNotFoundError(f"falta el insumo {src.relative_to(_ROOT)}")
        dst = DOC / "resultados" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        _copiar_texto(src, dst)
        hechos.append(rel)
    for g in sorted((OPT / "global").glob("*.json")):
        dst = DOC / "resultados" / "optuna" / "global" / g.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        _copiar_texto(g, dst)
    return hechos


def fig_cronologia(dest: Path) -> None:
    c = pd.read_csv(DOC / "evidencia" / "cronologia.csv", parse_dates=["fecha_alta"])
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.step(c["fecha_alta"], c["acumulados"], where="post", color=ACENTO, lw=2)
    ax.scatter(c["fecha_alta"], c["acumulados"], color=ACENTO, s=12, zorder=3)
    for _, r in c[c["nuevos"] >= 20].iterrows():
        ax.annotate(
            f"+{r['nuevos']}",
            (r["fecha_alta"], r["acumulados"]),
            textcoords="offset points",
            xytext=(-22, 4),
            fontsize=8,
            color=TINTA,
        )
    ax.set_ylabel("Padecimientos publicados")
    ax.set_title("De 4 padecimientos a 152 con pronóstico semanal", fontsize=10, color=TINTA)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(dest, dpi=200)
    plt.close(fig)


def fig_diferencia_critica(dest: Path, top: int = 14) -> None:
    fr = json.loads((EST / "friedman.json").read_text())
    rangos = list(fr["rangos_medios"].items())[:top]
    cd = fr["diferencia_critica"]
    fig, ax = plt.subplots(figsize=(7, 0.32 * top + 1))
    nombres = [n for n, _ in rangos][::-1]
    valores = [v for _, v in rangos][::-1]
    ax.barh(nombres, valores, color=[ACENTO if v - valores[-1] <= cd else GRIS for v in valores])
    ax.axvline(valores[-1] + cd, color=TINTA, ls="--", lw=1)
    ax.set_xlabel(f"Rango medio de Friedman (menor es mejor); línea = mejor + DC {cd:.2f}")
    ax.set_title(
        f"Friedman p = {fr['p_chi2']:.1e}; {fr['padecimientos']} padecimientos, "
        f"{fr['motores']} motores",
        fontsize=9,
        color=TINTA,
    )
    fig.tight_layout()
    fig.savefig(dest, dpi=200)
    plt.close(fig)


def fig_mejora(dest: Path) -> None:
    t = pd.read_csv(BANCO / "smape_nacional_por_padecimiento.csv", index_col=0)
    motores = [
        "nivel_x_perfil_5y",
        "topdown_ets_nacional",
        "combo_media_top3",
        "media_52s",
        "ets_amortiguado_log1p",
        "media_5y",
        "prophet_log1p",
        "lgbm_global_directo",
    ]
    datos = [((t[m] / t["naive_lag52"] - 1) * 100).dropna().to_numpy() for m in motores]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.boxplot(
        datos,
        orientation="horizontal",
        tick_labels=motores,
        showfliers=False,
        medianprops={"color": ACENTO, "lw": 2},
    )
    ax.axvline(0, color=TINTA, lw=1)
    ax.set_xlabel("sMAPE nacional frente al naive estacional (%), desarrollo")
    fig.tight_layout()
    fig.savefig(dest, dpi=200)
    plt.close(fig)


def fig_optuna(dest: Path) -> None:
    r = pd.read_csv(OPT / "resumen_configuraciones.csv")
    r = r[r["grupo"] == "externo"]
    motores = sorted({c.split("__")[0] for c in r["config"] if "__" in c})
    fig, ax = plt.subplots(figsize=(7, 3.4))
    x = np.arange(len(motores))
    for i, (alcance, color) in enumerate(
        [("default", GRIS), ("global", ACENTO), ("padecimiento", TINTA)]
    ):
        sub: dict[str, dict[str, float]] = {
            str(k): {str(c): float(v) for c, v in d.items()}
            for k, d in r.set_index("config")[["mejora_mediana_pct", "ic_bajo", "ic_alto"]]
            .to_dict("index")
            .items()
        }
        med: list[float] = []
        lo: list[float] = []
        hi: list[float] = []
        for m in motores:
            k = f"{m}__{alcance}"
            if k not in sub:
                med.append(float("nan"))
                lo.append(0.0)
                hi.append(0.0)
                continue
            c = sub[k]["mejora_mediana_pct"]
            med.append(c)
            lo.append(c - sub[k]["ic_bajo"])
            hi.append(sub[k]["ic_alto"] - c)
        ax.bar(
            x + (i - 1) * 0.27,
            med,
            0.27,
            color=color,
            label=alcance,
            yerr=[lo, hi],
            capsize=2,
            error_kw={"lw": 0.8},
        )
    ax.axhline(0, color=TINTA, lw=1)
    ax.set_xticks(x, motores, rotation=15, fontsize=8)
    ax.set_ylabel("Mediana vs naive (%), pliegues externos")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(dest, dpi=200)
    plt.close(fig)


def _sucio() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--", *SCRIPTS, "src", "config"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--permitir-sucio", action="store_true", help="sólo para desarrollo")
    args = ap.parse_args(argv)
    sucio = _sucio()
    if sucio and not args.permitir_sucio:
        raise SystemExit(
            f"árbol con cambios sin commit; el manifiesto no sería verificable:\n{sucio}"
        )
    copiadas = copiar()
    figs = DOC / "figuras"
    figs.mkdir(parents=True, exist_ok=True)
    fig_cronologia(figs / "cronologia.png")
    fig_diferencia_critica(figs / "diferencia_critica.png")
    fig_mejora(figs / "mejora_vs_naive.png")
    fig_optuna(figs / "optuna_externo.png")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    archivos = {
        str(p.relative_to(DOC)): _sha(p)
        for p in sorted(DOC.rglob("*"))
        if p.is_file() and p.name != "MANIFEST.json"
    }
    insumos = {str(s.relative_to(_ROOT)): _sha(s) for s in COPIAS}
    manifiesto = {
        "commit_origen": head,
        "arbol_limpio": not sucio,
        "codigo": {s_: _sha(_ROOT / s_) for s_ in SCRIPTS},
        "archivos": archivos,
        "insumos_runs": insumos,
        "copiados": copiadas,
    }
    (DOC / "MANIFEST.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(archivos)} archivos; commit {head[:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
