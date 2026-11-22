"""Evidencia de MLOps para el artículo de COMIA 2027, extraída del repositorio (sólo lectura).

Uso: python -m scripts.paper_comia_evidencia [--sin-red]

Escribe en docs/paper_comia2027/evidencia/:
- padecimientos.csv: un renglón por padecimiento publicado (legacy y del runner) con su perfil,
  política, desenlace de aceptación, motores del release y fecha de alta en git.
- cronologia.csv: publicados acumulados por fecha (de 4 legacy a todos los del runner).
- resumen.json: conteos del sistema (releases, productos, pronósticos, políticas, commits, PR, CI).

Sin red (``--sin-red``) se omiten los conteos de GitHub (PR fusionadas y corridas de CI).
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

import pandas as pd

from epiforecast import registry

_ROOT = Path(__file__).resolve().parents[1]
OUT = _ROOT / "docs" / "paper_comia2027" / "evidencia"
FRONTEND = "EpiForecastMX/EpiForecast-IMSS-Dashboard"
# Criterio uniforme para los cuatro legacy (mesa de expertos): son la línea base t0, en producción
# cuando se creó el registry central de padecimientos (commit verificable con ``git show``).
REGISTRY_ORIGEN = "960379db"
DEFINICIONES = {
    "fecha_alta": "runner: primer commit de main (first-parent) que agrega el puntero de release "
    "público; legacy: creación del registry (línea base t0)",
    "fecha_registry": "primer commit en que el id aparece en config/padecimientos.yaml",
    "releases_totales": "carpetas de release en disco, incluidas las reemplazadas",
    "commits": "historia de main; reescrita con filter-repo en junio de 2026 (conserva fechas "
    "de autor, cambia hashes anteriores)",
    "corridas_ci": "corridas del workflow CI del backend en GitHub, por conclusión y evento",
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _alta_git(disease: str) -> str | None:
    ruta = f"config/publication/{disease}/public_release_pointer.json"
    fechas = _git(
        "log",
        "main",
        "--first-parent",
        "-m",
        "--diff-filter=A",
        "--format=%ad",
        "--date=short",
        "--",
        ruta,
    )
    return fechas.splitlines()[-1] if fechas else None


def fechas_registry() -> dict[str, str]:
    """Primera fecha en que cada id aparece en el registry (recorre su historia una vez)."""
    import yaml

    primeras: dict[str, str] = {}
    for linea in _git(
        "log", "--reverse", "--format=%h %ad", "--date=short", "--", "config/padecimientos.yaml"
    ).splitlines():
        sha, fecha = linea.split()
        try:
            data = yaml.safe_load(_git("show", f"{sha}:config/padecimientos.yaml"))
        except subprocess.CalledProcessError:
            continue
        for d in (data or {}).get("padecimientos") or []:
            if isinstance(d, dict) and d.get("id"):
                primeras.setdefault(str(d["id"]), fecha)
    return primeras


def _desenlace(d: registry.Disease) -> str:
    if d.acceptance_fallback_run:
        return "control_tras_rechazo"
    if d.selection_policy == "rolling_cv_historia_corta_2024_v1":
        return "control_por_construccion"
    return "portafolio_aceptado"


def _manifiesto(d: registry.Disease) -> dict[str, object]:
    rel = d.artifact_source.release_id
    ruta = _ROOT / "artifacts" / "releases" / d.id / str(rel) / "release_manifest.json"
    data: dict[str, object] = json.loads(ruta.read_text(encoding="utf-8"))
    return data


def padecimientos() -> pd.DataFrame:
    filas = []
    t0 = _git("show", "-s", "--format=%ad", "--date=short", REGISTRY_ORIGEN)
    reg = fechas_registry()
    for d in registry.legacy_published():
        filas.append(
            {
                "disease_id": d.id,
                "nombre": d.display_name,
                "cie": " ".join(d.cie_codes),
                "carril": "legacy",
                "perfil": d.profile_name,
                "politica": "",
                "desenlace": "legacy",
                "sexo": d.sex_breakdown,
                "motores_release": "",
                "productos": None,
                "fecha_alta": t0,
                "fecha_registry": t0,
                "fuente_fecha": f"línea base: registry creado en {REGISTRY_ORIGEN}",
            }
        )
    for d in registry.release_published():
        m = _manifiesto(d)
        conteos = m["counts"] if isinstance(m["counts"], dict) else {}
        motores = m["engines"] if isinstance(m["engines"], dict) else {}
        filas.append(
            {
                "disease_id": d.id,
                "nombre": d.display_name,
                "cie": " ".join(d.cie_codes),
                "carril": "runner",
                "perfil": d.profile_name,
                "politica": d.selection_policy,
                "desenlace": _desenlace(d),
                "sexo": d.sex_breakdown,
                "motores_release": json.dumps(motores, sort_keys=True),
                "productos": conteos.get("products"),
                "fecha_alta": _alta_git(d.id),
                "fecha_registry": reg.get(d.id),
                "fuente_fecha": "puntero de release público en main (first-parent)",
            }
        )
    df = pd.DataFrame(filas).sort_values(["fecha_alta", "disease_id"]).reset_index(drop=True)
    df["dias_registry_a_publicacion"] = (
        pd.to_datetime(df["fecha_alta"]) - pd.to_datetime(df["fecha_registry"])
    ).dt.days
    return df


def cronologia(p: pd.DataFrame) -> pd.DataFrame:
    c = p.groupby("fecha_alta").size().rename("nuevos").reset_index()
    c["acumulados"] = c["nuevos"].cumsum()
    return c


def _gh(args: list[str]) -> list[dict[str, object]] | None:
    try:
        out = subprocess.run(
            ["gh", *args], cwd=_ROOT, capture_output=True, text=True, check=True, timeout=180
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    datos: list[dict[str, object]] = json.loads(out)
    return datos


def _corridas(repo: str | None, workflow: str | None) -> dict[str, object] | None:
    args = ["run", "list", "--limit", "5000", "--json", "conclusion,event,workflowName"]
    args += ["--repo", repo] if repo else []
    args += ["--workflow", workflow] if workflow else []
    runs = _gh(args)
    if runs is None:
        return None
    df = pd.DataFrame(runs)
    if df.empty:
        return {"total": 0}
    return {
        "total": len(df),
        "por_conclusion": df["conclusion"].replace("", "en_curso").value_counts().to_dict(),
        "por_evento": df["event"].value_counts().to_dict(),
        "por_workflow": df["workflowName"].value_counts().to_dict(),
    }


def resumen(p: pd.DataFrame, con_red: bool) -> dict[str, object]:
    runner = p[p["carril"] == "runner"]
    motores: Counter[str] = Counter()
    for m in runner["motores_release"]:
        motores.update(json.loads(m))
    res: dict[str, object] = {
        "publicados_total": len(p),
        "legacy": int((p["carril"] == "legacy").sum()),
        "runner": len(runner),
        "desenlaces": runner["desenlace"].value_counts().to_dict(),
        "politicas": runner["politica"].value_counts().to_dict(),
        "perfiles": runner["perfil"].value_counts().to_dict(),
        "sin_desglose_por_sexo": int((~runner["sexo"].astype(bool)).sum()),
        "productos_runner": int(runner["productos"].sum()),
        "series_base_por_motor_en_releases": dict(motores.most_common()),
        "releases_totales": sum(1 for _ in (_ROOT / "artifacts" / "releases").glob("*/*/")),
        "dias_registry_a_publicacion_runner": runner["dias_registry_a_publicacion"]
        .describe()
        .round(1)
        .to_dict(),
        "politicas_declaradas": sorted(
            f.stem for f in (_ROOT / "config" / "evaluation").glob("*.yaml")
        ),
        "commits": int(_git("rev-list", "--count", "HEAD")),
        "merges": int(_git("rev-list", "--count", "--merges", "HEAD")),
        "primer_commit": _git("log", "--reverse", "--format=%ad", "--date=short").splitlines()[0],
        "head": _git("rev-parse", "HEAD"),
        "archivos_de_prueba": sum(1 for _ in (_ROOT / "tests").rglob("test_*.py")),
        "definiciones": DEFINICIONES,
    }
    if con_red:
        pr_be = _gh(["pr", "list", "--state", "merged", "--limit", "2000", "--json", "number"])
        pr_fe = _gh(
            [
                "pr",
                "list",
                "--repo",
                FRONTEND,
                "--state",
                "merged",
                "--limit",
                "2000",
                "--json",
                "number",
            ]
        )
        res["pr_fusionadas"] = {
            "backend": len(pr_be) if pr_be is not None else None,
            "frontend": len(pr_fe) if pr_fe is not None else None,
        }
        res["corridas_ci"] = {
            "backend_ci": _corridas(None, "ci.yml"),
            "backend_todas": _corridas(None, None),
            "frontend_todas": _corridas(FRONTEND, None),
        }
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sin-red", action="store_true")
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    p = padecimientos()
    p.to_csv(OUT / "padecimientos.csv", index=False)
    cronologia(p).to_csv(OUT / "cronologia.csv", index=False)
    res = resumen(p, not args.sin_red)
    (OUT / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
