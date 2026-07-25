"""CLI DELGADO del runner genérico de padecimientos (F2/C3). Lógica en ``epiforecast.runner``.

Subcomandos:
  validate-data <pad>                          construye dataset + 111 productos (FUNCIONAL)
  benchmark <pad> --stage smoke|full [--engines a,b]   subprocess limpio por motor (rc=2 sin adapter)
  tune <pad> --stage smoke|full [--engines a,b]        congela hiperparámetros (centinelas+rejilla)
  select <pad> --benchmark-run <run_id>                congela la selección por SeriesKey
  benchmark <pad> --stage test --selection <run_id>    abre 2025 UNA vez (gate de aceptación)
  refit <pad> [--engines a,b]
  forecast <pad> --horizon 52 [--engines a,b]

``--engines`` es OVERRIDE opcional; por defecto se usan los candidatos de la POLÍTICA de evaluación
(``config/evaluation/rolling_cv_v1.yaml``), NO los training_engines legacy del registry.

validate-data → runs/<dataset_id>/ (DatasetManifest). benchmark/refit/forecast → runs/<run_id>/
(dir distinto que referencia el dataset_id). NO entrena de verdad, NO publica, NO push/DVC.
El exit code refleja el estado del run (0 ok, 2 sin adapter, 1 error).

    python -m scripts.disease_run validate-data Obesidad
    python -m scripts.disease_run benchmark Obesidad --stage smoke
    python -m scripts.disease_run tune Obesidad --stage smoke --engines prophet_count_log1p
    python -m scripts.disease_run forecast Obesidad --horizon 52
"""

from __future__ import annotations

import argparse

from epiforecast.runner import orchestrator as orch
from epiforecast.runner.manifest import (
    CMD_BENCHMARK,
    CMD_FORECAST,
    CMD_REFIT,
    CMD_SELECT,
    CMD_TUNE,
    CMD_VALIDATE_DATA,
    STAGE_FULL,
    STAGE_SMOKE,
    STAGE_TEST,
)


def _engines(raw: str) -> list[str]:
    engines = [e.strip() for e in raw.split(",") if e.strip()]
    if not engines:
        raise argparse.ArgumentTypeError("se requiere al menos un motor")
    return engines


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="disease_run", description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    val = sub.add_parser(CMD_VALIDATE_DATA, help="construye y valida el dataset + productos")
    val.add_argument("disease")

    bench = sub.add_parser(CMD_BENCHMARK, help="backtest OOS por motor (subprocess limpio)")
    bench.add_argument("disease")
    bench.add_argument(
        "--stage", choices=[STAGE_SMOKE, STAGE_FULL, STAGE_TEST], default=STAGE_FULL
    )
    bench.add_argument(
        "--engines", type=_engines, help="override; default = candidatos de la política"
    )
    bench.add_argument(
        "--selection", help="run_id de la selección congelada (OBLIGATORIO con --stage test)"
    )
    bench.add_argument("--no-resume", action="store_true")
    bench.add_argument("--allow-dirty", action="store_true", help="permite árbol trackeado sucio")

    tune = sub.add_parser(
        CMD_TUNE, help="congela hiperparámetros por motor (centinelas + rejilla)"
    )
    tune.add_argument("disease")
    tune.add_argument("--stage", choices=[STAGE_SMOKE, STAGE_FULL], default=STAGE_SMOKE)
    tune.add_argument(
        "--engines", type=_engines, help="override; default = candidatos de la política"
    )
    tune.add_argument("--no-resume", action="store_true")
    tune.add_argument("--allow-dirty", action="store_true")

    select = sub.add_parser(CMD_SELECT, help="congela la selección por SeriesKey (no entrena)")
    select.add_argument("disease")
    select.add_argument("--benchmark-run", required=True, help="run_id del benchmark ya ejecutado")
    select.add_argument("--allow-dirty", action="store_true")

    refit = sub.add_parser(CMD_REFIT, help="refit por motor (subprocess limpio)")
    refit.add_argument("disease")
    refit.add_argument("--engines", type=_engines)
    refit.add_argument("--no-resume", action="store_true")
    refit.add_argument("--allow-dirty", action="store_true")

    fc = sub.add_parser(CMD_FORECAST, help="forecast por motor (subprocess limpio)")
    fc.add_argument("disease")
    fc.add_argument("--horizon", type=int, default=52)
    fc.add_argument("--engines", type=_engines)
    fc.add_argument("--no-resume", action="store_true")
    fc.add_argument("--allow-dirty", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == CMD_VALIDATE_DATA:
        dm = orch.validate_data(args.disease)
        print(
            f"dataset_id={dm.dataset_id} status=validated → runs/{dm.dataset_id}/dataset_manifest.json"
        )
        return 0

    if args.command == CMD_SELECT:
        sm = orch.run_selection(
            args.disease,
            args.benchmark_run,
            runs_root=None,
            require_clean=not args.allow_dirty,
        )
        print(f"run_id={sm.run_id} status={sm.status} → runs/{sm.run_id}/selection_manifest.json")
        return sm.exit_code or 0

    rm = orch.run_command(
        args.disease,
        args.command,
        stage=getattr(args, "stage", STAGE_FULL),
        engines=args.engines,
        horizon=getattr(args, "horizon", None),
        resume=not args.no_resume,
        require_clean=not args.allow_dirty,  # runs por CLI son oficiales: exigen árbol limpio
        selection_run_id=getattr(args, "selection", None),
    )
    print(f"run_id={rm.run_id} status={rm.status} → runs/{rm.run_id}/run_manifest.json")
    return rm.exit_code or 0


if __name__ == "__main__":
    raise SystemExit(main())
