"""CLI: diagnostica qué falta para completar un padecimiento en el registry.

Uso:
  .venv/bin/python -m scripts.doctor_padecimiento --config-only            # todos (CI)
  .venv/bin/python -m scripts.doctor_padecimiento Obesidad --config-only   # uno
  .venv/bin/python -m scripts.doctor_padecimiento --artifacts              # + modelos en disco

Sale != 0 si hay problemas 'error'.
"""

from __future__ import annotations

import argparse
import sys

from epiforecast.registry_doctor import diagnose


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("padecimiento", nargs="?", default=None)
    ap.add_argument("--config-only", action="store_true", help="solo config (no artefactos)")
    ap.add_argument("--artifacts", action="store_true", help="también valida modelos en disco")
    args = ap.parse_args()

    check_artifacts = args.artifacts and not args.config_only
    problems = diagnose(args.padecimiento, check_artifacts=check_artifacts)

    scope = args.padecimiento or "TODOS los padecimientos"
    errors = [p for p in problems if p.severity == "error"]
    if not problems:
        print(f"✅ {scope}: completo ({'config+artefactos' if check_artifacts else 'config'}).")
        return 0
    print(f"Diagnóstico de {scope}:")
    for p in problems:
        mark = "❌" if p.severity == "error" else "⚠️ "
        print(f"  {mark} [{p.disease}] {p.message}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
