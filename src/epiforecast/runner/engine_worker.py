"""F2/C2 — worker de subprocess LIMPIO: ejecuta UN motor para UN comando bajo runs/<run_id>/.

El orquestador lanza ``python -m epiforecast.runner.engine_worker`` por motor (intérprete fresco,
sin estado compartido). El worker resuelve el adapter y:
- sin adapter → escribe result.json (NoAdapter) y termina **rc=2** (nunca aparenta éxito);
- con adapter → lo ejecuta, escribe artefactos + result.json (succeeded) y termina rc=0;
- excepción → result.json (error) y termina rc=1.

El result.json (``runs/<run_id>/jobs/<engine>.result.json``) es la ÚNICA señal de terminación que
el orquestador consume: un .pkl existente NO equivale a job terminado.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import traceback

from epiforecast.runner.adapters import get_adapter
import epiforecast.runner.engines as _engines  # noqa: F401 — registra los adapters al importar

RC_OK = 0
RC_ERROR = 1
RC_NO_ADAPTER = 2
RC_UNSUPPORTED = 3  # el motor existe pero no implementa el comando


def _write_result(jobs_dir: Path, engine: str, attempt: str, payload: dict[str, object]) -> None:
    jobs_dir.mkdir(parents=True, exist_ok=True)
    (jobs_dir / f"{engine}.result.json").write_text(
        json.dumps(
            {"engine": engine, "attempt": attempt, **payload}, indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="engine_worker")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--engine", required=True)
    ap.add_argument("--command", required=True)
    ap.add_argument("--attempt", required=True, help="token del intento (anti-stale)")
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    jobs_dir = run_dir / "jobs"
    engine: str = args.engine
    attempt: str = args.attempt

    try:
        adapter = get_adapter(engine)
        if adapter is None:
            _write_result(
                jobs_dir,
                engine,
                attempt,
                {
                    "status": "failed",
                    "exit_code": RC_NO_ADAPTER,
                    "error_type": "NoAdapter",
                    "error_message": f"sin adapter registrado para el motor {engine!r}",
                    "artifacts": [],
                },
            )
            print(
                f"[disease_run] motor {engine!r}: sin adapter (rc={RC_NO_ADAPTER})",
                file=sys.stderr,
            )
            return RC_NO_ADAPTER

        if not adapter.supports(args.command):
            _write_result(
                jobs_dir,
                engine,
                attempt,
                {
                    "status": "failed",
                    "exit_code": RC_UNSUPPORTED,
                    "error_type": "UnsupportedCommand",
                    "error_message": (
                        f"el motor {engine!r} no implementa el comando {args.command!r}"
                    ),
                    "artifacts": [],
                },
            )
            print(
                f"[disease_run] motor {engine!r}: comando {args.command!r} no soportado "
                f"(rc={RC_UNSUPPORTED})",
                file=sys.stderr,
            )
            return RC_UNSUPPORTED

        artifacts = adapter.run(args.command, str(run_dir))
        _write_result(
            jobs_dir,
            engine,
            attempt,
            {
                "status": "succeeded",
                "exit_code": RC_OK,
                "error_type": None,
                "error_message": None,
                "artifacts": [asdict(a) for a in artifacts],
            },
        )
        return RC_OK
    except Exception as exc:  # noqa: BLE001 — el worker convierte cualquier fallo en rc=1 honesto
        _write_result(
            jobs_dir,
            engine,
            attempt,
            {
                "status": "failed",
                "exit_code": RC_ERROR,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "artifacts": [],
            },
        )
        traceback.print_exc()
        return RC_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
