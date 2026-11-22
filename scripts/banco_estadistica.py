"""Pruebas estadísticas sobre el banco ampliado (sólo pliegues de desarrollo; no publica nada).

Uso: python -m scripts.banco_estadistica [--banco runs/banco_ampliado/v1]

Escribe en <banco>/estadistica/ (versión 2, tras la mesa de expertos del 22-nov-2026):
- titular_interseccion.csv: motores con cobertura >= 90 % sobre los mismos padecimientos y pliegues.
- contra_<ref>[_bases].csv: Wilcoxon emparejado por pliegue, Holm por familia (confirmatoria =
  ronda 1; exploratoria = ronda 2), signo, IC bootstrap, cuantiles, MAE relativo geométrico.
- por_pliegue.csv y por_estrato.csv (perfil y tercil de incidencia): consistencia del efecto.
- friedman.json: Friedman con corrección por empates sin clones; padecimientos excluidos listados.
- victorias_mae.csv: proporción descriptiva de pliegues con menor MAE (sustituye a Diebold-Mariano).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from epiforecast import registry
from epiforecast.banco import estadistica
from epiforecast.banco import estadistica_banco as eb

_ROOT = Path(__file__).resolve().parents[1]
REFERENCIAS = ("naive_lag52", "media_52s")
COBERTURA = 0.9
DESTACADOS = [
    "nivel_x_perfil_5y",
    "topdown_ets_nacional",
    "combo_media_top3",
    "media_26s",
    "media_52s",
    "ets_amortiguado_log1p",
    "tsb",
    "media_5y",
    "prophet_log1p",
    "ridge_fourier_log1p",
    "lgbm_global_directo",
]


def estratos(banco: Path) -> dict[str, pd.Series]:
    perfil = pd.Series({d.id: d.profile_name for d in registry.release_published()})
    nivel = {}
    for f in sorted((banco / "tareas").glob("*__naive_lag52.parquet")):
        df = pd.read_parquet(f)
        nivel[f.name.split("__")[0]] = df["y_true"].sum() / df["fold"].nunique()
    tercil = pd.qcut(pd.Series(nivel), 3, labels=["baja", "media", "alta"]).astype(str)
    return {"perfil": perfil, "tercil_incidencia": tercil}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--banco", type=Path, default=_ROOT / "runs" / "banco_ampliado" / "v1")
    args = ap.parse_args(argv)
    out = args.banco / "estadistica"
    out.mkdir(parents=True, exist_ok=True)
    met = pd.read_csv(args.banco / "metricas.csv")
    m = eb.completos(met)
    motores = sorted(met["engine"].unique())
    todos = set(met["disease_id"])
    cov = m.reset_index().groupby("engine")["disease_id"].nunique() / len(todos)
    amplios = [str(e) for e in cov[cov >= COBERTURA].index if e not in eb.CLONES]
    inter = eb.interseccion(m, amplios)
    titular = pd.DataFrame(
        {
            "mediana": inter.median(),
            "media": inter.mean(),
            "gana_al_naive": inter.lt(inter["naive_lag52"], axis=0).sum(),
            "cobertura_total": cov.reindex(inter.columns),
        }
    ).sort_values("mediana")
    titular.to_csv(out / "titular_interseccion.csv")
    for ref in REFERENCIAS:
        eb.contra(m, ref, motores, "smape_nacional").to_csv(out / f"contra_{ref}.csv", index=False)
    eb.contra(m, "naive_lag52", motores, "smape_bases").to_csv(
        out / "contra_naive_lag52_bases.csv", index=False
    )
    # WAPE de bases (reusa el mismo emparejamiento: la columna se llama smape_nacional ahí).
    wb = eb.completos(eb.wape_bases(args.banco / "tareas", ["naive_lag52", *DESTACADOS]))
    eb.contra(wb, "naive_lag52", DESTACADOS, "smape_nacional").to_csv(
        out / "contra_naive_lag52_wape_bases.csv", index=False
    )
    eb.por_pliegue(m, "naive_lag52", DESTACADOS).to_csv(out / "por_pliegue.csv", index=False)
    est = [
        eb.por_estrato(m, "naive_lag52", DESTACADOS, s).assign(tipo=nombre)
        for nombre, s in estratos(args.banco).items()
    ]
    pd.concat(est).to_csv(out / "por_estrato.csv", index=False)
    fr = estadistica.friedman_nemenyi(inter)
    fr |= {
        "clones_excluidos": eb.CLONES,
        "motores_excluidos_por_cobertura": {
            str(e): round(float(c), 3) for e, c in cov.items() if c < COBERTURA
        },
        "padecimientos_excluidos": sorted(todos - set(inter.index)),
        "nota": "DC de Nemenyi descriptiva; la inferencia contra el control usa Wilcoxon + Holm.",
    }
    (out / "friedman.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1))
    eb.victorias_descriptivas(m, "naive_lag52", DESTACADOS).to_csv(
        out / "victorias_mae.csv", index=False
    )
    for viejo in ("diebold_mariano.csv", "diebold_mariano_resumen.csv", "friedman_amplio.json"):
        (out / viejo).unlink(missing_ok=True)
    print(f"intersección: {len(inter)} padecimientos × {inter.shape[1]} motores")
    print(titular.round(2).head(12).to_string())
    c = pd.read_csv(out / "contra_naive_lag52.csv")
    cols = ["engine", "familia", "wilcoxon_n", "no_aplica", "mediana_pct", "ic_bajo", "ic_alto"]
    cols += ["q10_pct", "q90_pct", "peor_mas_10pct", "mae_rel_geo", "p_holm", "veredicto"]
    print(c[cols].round(3).to_string(index=False))
    print({k: fr[k] for k in ("padecimientos", "motores", "chi2", "p_chi2", "diferencia_critica")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
