"""CLI DELGADO del runner genérico de padecimientos (F2/C2). Lógica en ``epiforecast.runner``.

Subcomandos:
  validate-data <padecimiento>                     construye dataset + 111 productos (FUNCIONAL)
  benchmark|refit|forecast <pad> --engines a,b     un subprocess limpio por motor (rc=2 sin adapter)

Todo queda bajo ``runs/<run_id>/``. NO entrena de verdad, NO publica, NO hace push/DVC.
El exit code refleja el estado del run (0 ok, 2 sin adapter, 1 error).

    python -m scripts.disease_run validate-data Obesidad
    python -m scripts.disease_run benchmark Obesidad --engines prophet,deepar
"""

from __future__ import annotations

import argparse

from epiforecast.runner import orchestrator as orch
from epiforecast.runner.manifest import (
    CMD_BENCHMARK,
    CMD_FORECAST,
    CMD_REFIT,
    CMD_VALIDATE_DATA,
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

    for cmd in (CMD_BENCHMARK, CMD_REFIT, CMD_FORECAST):
        p = sub.add_parser(cmd, help=f"{cmd}: un subprocess limpio por motor")
        p.add_argument("disease")
        p.add_argument(
            "--engines", required=True, type=_engines, help="motores separados por coma"
        )
        p.add_argument("--no-resume", action="store_true", help="ignora jobs previos completos")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == CMD_VALIDATE_DATA:
        man = orch.validate_data(args.disease)
    else:
        man = orch.run_command(args.disease, args.command, args.engines, resume=not args.no_resume)
    print(f"run_id={man.run_id} status={man.status} → runs/{man.run_id}/run_manifest.json")
    return man.exit_code or 0


if __name__ == "__main__":
    raise SystemExit(main())
