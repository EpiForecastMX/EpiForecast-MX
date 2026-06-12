#!/usr/bin/env python3
"""EpiForecast-MX — Cookiecutter Data Science v2 Compliance Checker.

Strict audit against:
- Cookiecutter DS v2 directory structure
- SOLID principles
- MLOps best practices
- Clean Code standards

Usage:
    python scripts/compliance_check.py
    python scripts/compliance_check.py --strict   # fail on warnings too
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

# ── Config ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "epiforecast"
VENV_BIN = ROOT / ".venv" / "bin"

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"
SKIP = "⏭️"

results: list[tuple[str, str, str]] = []  # (status, category, message)


def check(condition: bool, category: str, msg: str, warn_only: bool = False) -> bool:
    """Register a check result."""
    if condition:
        results.append((PASS, category, msg))
    elif warn_only:
        results.append((WARN, category, msg))
    else:
        results.append((FAIL, category, msg))
    return condition


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: COOKIECUTTER DS v2 DIRECTORY STRUCTURE
# ══════════════════════════════════════════════════════════════════════════════


def check_directory_structure():
    """Validate Cookiecutter Data Science v2 required directories."""
    cat = "Structure"

    # Required top-level directories
    required_dirs = {
        "data": "Data directory (raw, interim, processed)",
        "data/raw": "Raw immutable data",
        "data/interim": "Intermediate transformed data",
        "data/processed": "Final canonical datasets",
        "src/epiforecast": "Source package",
        "tests": "Test suite",
        "tests/unit": "Unit tests",
        "notebooks": "Jupyter notebooks (exploration only)",
        "scripts": "Pipeline scripts",
        "config": "Configuration files",
        "docs": "Documentation",
        "reports": "Generated outputs (reports, forecasts)",
        "reports/figures": "Generated graphics and figures",
        "reports/forecasts": "Generated forecast data and model summaries",
        "models": "Trained model artifacts",
    }

    for d, desc in required_dirs.items():
        check((ROOT / d).is_dir(), cat, f"Directory exists: {d}/ — {desc}")

    # Required top-level files
    required_files = {
        "pyproject.toml": "Project metadata & tooling config",
        "Makefile": "Automation targets",
        "README.md": "Project documentation",
        ".gitignore": "Git ignore rules",
        ".pre-commit-config.yaml": "Pre-commit hooks",
        "LICENSE": "License file",
    }

    for f, desc in required_files.items():
        check((ROOT / f).exists(), cat, f"File exists: {f} — {desc}")

    # Additional required Cookiecutter v2 directories
    required_extra_dirs = {
        "reports": "Reports and figures (Cookiecutter v2)",
        "reports/figures": "Report figures",
    }
    for d, desc in required_extra_dirs.items():
        check((ROOT / d).is_dir(), cat, f"Directory exists: {d}/ — {desc}")

    # Optional Cookiecutter v2 directories
    optional_dirs = {
        "data/external": "External data sources (Cookiecutter v2)",
        "references": "Reference papers and data dictionaries",
    }
    for d, desc in optional_dirs.items():
        check((ROOT / d).is_dir(), cat, f"Directory exists: {d}/ — {desc}", warn_only=True)

    # Optional files
    optional_files = {
        "requirements.txt": "Legacy requirements file (pyproject.toml preferred)",
        ".dvcignore": "DVC ignore rules",
    }
    for f, desc in optional_files.items():
        check((ROOT / f).exists(), cat, f"File exists: {f} — {desc}", warn_only=True)

    # Cookiecutter v2: src layout (NOT flat)
    check(
        (ROOT / "src" / "epiforecast" / "__init__.py").exists(),
        cat,
        "src-layout: src/epiforecast/__init__.py exists",
    )

    # No legacy directories
    legacy_dirs = [
        "src/configuraciones",
        "src/datos",
        "src/extraccion",
        "src/modelado",
        "src/utils",
    ]
    for d in legacy_dirs:
        check(not (ROOT / d).exists(), cat, f"Legacy removed: {d}/ does not exist")

    # Data should NOT be in git (check .gitignore or .dvc)
    dvc_files = list(ROOT.glob("*.dvc")) + list(ROOT.glob("data/*.dvc"))
    check(len(dvc_files) > 0, cat, f"Data versioned with DVC: {len(dvc_files)} .dvc files found")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: PACKAGE STRUCTURE & SOLID PRINCIPLES
# ══════════════════════════════════════════════════════════════════════════════


def check_solid_principles():
    """Validate SOLID design patterns in the codebase."""
    cat = "SOLID"

    # S — Single Responsibility: no file > 300 lines.
    # Excepciones documentadas en CLAUDE.md (codigo intrinsecamente extenso o de
    # layout de figuras, periferico a la logica de modelado). Se reportan como
    # warning informativo en vez de fallo para no enmascarar deuda nueva.
    srp_exceptions = {
        "src/epiforecast/models/deepar/model.py",
        "src/epiforecast/visualization/avance5_tables.py",
        "src/epiforecast/visualization/avance5_charts.py",
        "src/epiforecast/visualization/comparison_bars.py",
    }
    for py in SRC.rglob("*.py"):
        if py.name.startswith("__"):
            continue
        rel = str(py.relative_to(ROOT))
        lines = len(py.read_text().splitlines())
        is_exception = rel in srp_exceptions
        check(
            lines <= 300,
            cat,
            f"SRP: {rel} has {lines} lines (max 300)"
            + (" [excepcion documentada]" if is_exception else ""),
            warn_only=lines <= 400 or is_exception,
        )

    # O — Open/Closed: model factory exists
    check(
        (SRC / "models" / "factory.py").exists(),
        cat,
        "OCP: ModelFactory exists for extensible model creation",
    )

    # L — Liskov: base classes with abstract methods
    base_files = list(SRC.rglob("base.py"))
    check(
        len(base_files) >= 2,
        cat,
        f"LSP: {len(base_files)} base.py files with abstract interfaces",
    )

    # Check ABC usage in base files
    for bf in base_files:
        content = bf.read_text()
        has_abc = "ABC" in content or "abstractmethod" in content
        check(
            has_abc,
            cat,
            f"LSP: {bf.relative_to(ROOT)} uses ABC/abstractmethod",
            warn_only=True,
        )

    # D — Dependency Inversion: no direct Prophet imports in scripts
    for script in (ROOT / "scripts").glob("*.py"):
        if script.name == "compliance_check.py":
            continue  # meta-script contains the search string as a literal
        content = script.read_text()
        has_direct_prophet = "from prophet import" in content
        check(
            not has_direct_prophet,
            cat,
            f"DIP: {script.name} does not import Prophet directly",
        )

    # I — Interface Segregation: models/ has separate modules
    prophet_dir = SRC / "models" / "prophet"
    expected_modules = ["model.py", "tuner.py", "cross_validator.py"]
    for mod in expected_modules:
        check(
            (prophet_dir / mod).exists(),
            cat,
            f"ISP: Prophet split into {mod}",
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: CLEAN CODE STANDARDS
# ══════════════════════════════════════════════════════════════════════════════


def check_clean_code():
    """Validate clean code practices."""
    cat = "CleanCode"

    # py.typed marker for mypy
    check(
        (SRC / "py.typed").exists(),
        cat,
        "py.typed marker exists for mypy type checking",
    )

    # __init__.py with version
    init = SRC / "__init__.py"
    if init.exists():
        content = init.read_text()
        check("__version__" in content, cat, "__version__ defined in __init__.py")
    else:
        check(False, cat, "__init__.py exists in package root")

    # No wildcard imports in src/epiforecast/
    wildcard_count = 0
    for py in SRC.rglob("*.py"):
        content = py.read_text()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("from ") and "import *" in stripped:
                wildcard_count += 1
    check(
        wildcard_count == 0,
        cat,
        f"No wildcard imports in package: found {wildcard_count}",
        warn_only=wildcard_count <= 3,
    )

    # No print() in src/epiforecast/ (should use logger)
    print_count = 0
    for py in SRC.rglob("*.py"):
        if py.name == "__init__.py":
            continue
        try:
            tree = ast.parse(py.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "print":
                        print_count += 1
        except SyntaxError:
            pass
    check(
        print_count == 0,
        cat,
        f"No print() in package (use logger): found {print_count}",
        warn_only=print_count <= 5,
    )

    # Docstrings on all modules
    missing_docstrings = []
    for py in SRC.rglob("*.py"):
        if py.name.startswith("__"):
            continue
        try:
            tree = ast.parse(py.read_text())
            if not ast.get_docstring(tree):
                missing_docstrings.append(str(py.relative_to(ROOT)))
        except SyntaxError:
            pass
    check(
        len(missing_docstrings) == 0,
        cat,
        f"All modules have docstrings: {len(missing_docstrings)} missing",
        warn_only=len(missing_docstrings) <= 3,
    )
    for m in missing_docstrings[:5]:
        results.append((WARN, cat, f"  Missing docstring: {m}"))

    # No TODO/FIXME/HACK in production code
    debt_count = 0
    debt_files = []
    for py in SRC.rglob("*.py"):
        content = py.read_text()
        for marker in ["TODO", "FIXME", "HACK", "XXX"]:
            count = content.count(marker)
            if count > 0:
                debt_count += count
                debt_files.append(f"{py.relative_to(ROOT)}: {marker}×{count}")
    check(
        debt_count == 0,
        cat,
        f"No tech debt markers (TODO/FIXME/HACK): found {debt_count}",
        warn_only=True,
    )
    for d in debt_files[:5]:
        results.append((WARN, cat, f"  Debt: {d}"))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: MLOps PRACTICES
# ══════════════════════════════════════════════════════════════════════════════


def check_mlops():
    """Validate MLOps best practices."""
    cat = "MLOps"

    # Config management: YAML-based, no hardcoded values
    config_dir = ROOT / "config"
    yaml_files = list(config_dir.rglob("*.yaml"))
    check(
        len(yaml_files) >= 5,
        cat,
        f"Config externalized: {len(yaml_files)} YAML files in config/",
    )

    # Config subdirectories
    config_subdirs = ["data", "models", "features", "visualization", "infrastructure"]
    for d in config_subdirs:
        check(
            (config_dir / d).is_dir(),
            cat,
            f"Config organized: config/{d}/ exists",
        )

    # DVC for data versioning
    check(
        (ROOT / ".dvc").is_dir(),
        cat,
        "DVC initialized: .dvc/ directory exists",
    )

    # CI/CD pipeline
    check(
        (ROOT / ".github" / "workflows" / "ci.yml").exists(),
        cat,
        "CI/CD: .github/workflows/ci.yml exists",
    )

    # Pre-commit hooks
    check(
        (ROOT / ".pre-commit-config.yaml").exists(),
        cat,
        "Pre-commit hooks configured",
    )

    # Makefile automation targets
    if (ROOT / "Makefile").exists():
        makefile = (ROOT / "Makefile").read_text()
        required_targets = ["quality", "lint", "test", "train", "preprocess"]
        for target in required_targets:
            check(
                f"{target}:" in makefile or f"{target} :" in makefile,
                cat,
                f"Makefile target: {target}",
            )

    # Reproducibility: requirements pinned
    pyproject = (ROOT / "pyproject.toml").read_text()
    check(
        "==" in pyproject or ">=" in pyproject,
        cat,
        "Dependencies declared in pyproject.toml with version constraints",
    )

    # Model serialization: .pkl files tracked
    model_files = list((ROOT / "models").rglob("*.pkl")) if (ROOT / "models").is_dir() else []
    check(
        len(model_files) > 0 or (ROOT / "models.dvc").exists(),
        cat,
        f"Models tracked: {len(model_files)} .pkl files or models.dvc",
        warn_only=True,
    )

    # Logging: loguru or logging configured
    has_logging = False
    for py in SRC.rglob("*.py"):
        if "loguru" in py.read_text() or "import logging" in py.read_text():
            has_logging = True
            break
    check(has_logging, cat, "Structured logging configured (loguru)")

    # Environment management
    check(
        (ROOT / ".env.example").exists(),
        cat,
        "Environment template: .env.example exists",
    )

    # Python version pinned
    check(
        (ROOT / ".python-version").exists(),
        cat,
        "Python version pinned: .python-version exists",
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: TESTING STANDARDS
# ══════════════════════════════════════════════════════════════════════════════


def check_testing():
    """Validate testing standards."""
    cat = "Testing"

    # Test directory structure
    test_dirs = ["tests/unit", "tests/integration", "tests/fixtures"]
    for d in test_dirs:
        check(
            (ROOT / d).is_dir(),
            cat,
            f"Test directory: {d}/",
        )

    # Test files exist
    test_files = list((ROOT / "tests").rglob("test_*.py"))
    check(
        len(test_files) >= 10,
        cat,
        f"Test files: {len(test_files)} test_*.py files (min 10)",
    )

    # conftest.py exists
    check(
        (ROOT / "tests" / "conftest.py").exists(),
        cat,
        "conftest.py with shared fixtures exists",
    )

    # Coverage configured in pyproject.toml
    pyproject = (ROOT / "pyproject.toml").read_text()
    check(
        "pytest-cov" in pyproject or "--cov" in pyproject,
        cat,
        "Coverage configured in pyproject.toml",
    )

    # Run tests and check count
    try:
        pytest_bin = str(VENV_BIN / "pytest") if VENV_BIN.exists() else "pytest"
        result = subprocess.run(
            [pytest_bin, "tests/unit/", "--tb=no", "-q"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=300,
        )
        output = result.stdout.strip().split("\n")[-1]
        if "passed" in output:
            import re

            match = re.search(r"(\d+) passed", output)
            if match:
                count = int(match.group(1))
                check(count >= 100, cat, f"Tests passing: {count} (min 100)")
                check(count >= 300, cat, f"Tests target: {count} (target 300+)", warn_only=True)
        else:
            check(False, cat, f"Tests: {output}")
    except Exception as e:
        check(False, cat, f"Could not run tests: {e}")

    # Coverage check
    try:
        pytest_bin = str(VENV_BIN / "pytest") if VENV_BIN.exists() else "pytest"
        result = subprocess.run(
            [
                pytest_bin,
                "tests/unit/",
                "--cov=src/epiforecast",
                "--cov-report=term",
                "--tb=no",
                "-q",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=300,
        )
        for line in result.stdout.split("\n"):
            if "TOTAL" in line:
                parts = line.split()
                for p in parts:
                    if p.endswith("%"):
                        cov = int(p.replace("%", ""))
                        check(cov >= 30, cat, f"Coverage: {cov}% (min 30%)")
                        check(
                            cov >= 50, cat, f"Coverage target: {cov}% (target 50%)", warn_only=True
                        )
                        check(
                            cov >= 80, cat, f"Coverage ideal: {cov}% (ideal 80%)", warn_only=True
                        )
                        break
    except Exception as e:
        results.append((WARN, cat, f"Could not measure coverage: {e}"))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: CODE QUALITY TOOLING
# ══════════════════════════════════════════════════════════════════════════════


def check_tooling():
    """Validate code quality tooling is configured and passing."""
    cat = "Tooling"

    pyproject = (ROOT / "pyproject.toml").read_text()

    # Ruff configured
    check("[tool.ruff]" in pyproject, cat, "Ruff linter configured in pyproject.toml")

    # Mypy configured
    check("[tool.mypy]" in pyproject, cat, "Mypy type checker configured in pyproject.toml")

    # Pytest configured
    check("[tool.pytest" in pyproject, cat, "Pytest configured in pyproject.toml")

    # Run ruff check
    try:
        ruff_bin = str(VENV_BIN / "ruff") if VENV_BIN.exists() else "ruff"
        result = subprocess.run(
            [ruff_bin, "check", "src/epiforecast/", "tests/"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=30,
        )
        check(
            result.returncode == 0,
            cat,
            f"Ruff check: {'PASS' if result.returncode == 0 else result.stdout.strip().split(chr(10))[-1]}",
        )
    except Exception as e:
        check(False, cat, f"Could not run ruff: {e}")

    # Run ruff format check
    try:
        result = subprocess.run(
            [ruff_bin, "format", "--check", "src/epiforecast/", "tests/"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=30,
        )
        check(
            result.returncode == 0,
            cat,
            f"Ruff format: {'PASS' if result.returncode == 0 else 'files need formatting'}",
        )
    except Exception as e:
        check(False, cat, f"Could not run ruff format: {e}")

    # Run mypy
    try:
        mypy_bin = str(VENV_BIN / "mypy") if VENV_BIN.exists() else "mypy"
        result = subprocess.run(
            [mypy_bin, "src/epiforecast/"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60,
        )
        check(
            result.returncode == 0,
            cat,
            f"Mypy: {'PASS' if result.returncode == 0 else result.stdout.strip().split(chr(10))[-1]}",
        )
    except Exception as e:
        check(False, cat, f"Could not run mypy: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7: IMPORT HYGIENE
# ══════════════════════════════════════════════════════════════════════════════


def check_imports():
    """Validate import conventions."""
    cat = "Imports"

    # No legacy src.* imports
    legacy_imports = 0
    legacy_files = []
    search_dirs = [SRC, ROOT / "scripts", ROOT / "tests"]
    for d in search_dirs:
        if not d.exists():
            continue
        for py in d.rglob("*.py"):
            if py.name == "compliance_check.py":
                continue  # meta-script contains the search string as a literal
            content = py.read_text()
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith(("#", '"', "'")):
                    continue
                if "from src.epiforecast" in stripped or "import src.epiforecast" in stripped:
                    legacy_imports += 1
                    legacy_files.append(str(py.relative_to(ROOT)))
                    break

    check(
        legacy_imports == 0,
        cat,
        f"No legacy 'src.epiforecast' imports: found in {legacy_imports} files",
    )
    for f in legacy_files[:5]:
        results.append((FAIL, cat, f"  Legacy import in: {f}"))

    # Canonical import style: from epiforecast.X
    canonical_count = 0
    for py in (ROOT / "scripts").rglob("*.py"):
        content = py.read_text()
        if "from epiforecast." in content:
            canonical_count += 1
    check(
        canonical_count > 0,
        cat,
        f"Canonical imports 'from epiforecast.*': {canonical_count} scripts",
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8: DOCUMENTATION STANDARDS
# (adapted from MLOps_Team24 validate_cookiecutter.py)
# ══════════════════════════════════════════════════════════════════════════════


def check_documentation():
    """Validate documentation standards: README content and notebook naming."""
    cat = "Documentation"

    # README.md must contain key sections
    readme = ROOT / "README.md"
    if readme.exists():
        content = readme.read_text().lower()
        readme_sections = {
            "project": "project description",
            "install": "installation instructions",
            "usage": "usage instructions",
            "structure": "project structure",
        }
        for keyword, desc in readme_sections.items():
            check(
                keyword in content,
                cat,
                f"README.md contains '{keyword}' section ({desc})",
                warn_only=True,
            )
    else:
        check(False, cat, "README.md exists for documentation")

    # Notebook naming convention: #.#-initials-description.ipynb
    import re

    nb_dir = ROOT / "notebooks"
    notebooks = list(nb_dir.glob("*.ipynb")) if nb_dir.exists() else []
    if notebooks:
        pattern = re.compile(r"^\d+\.\d+-[a-z]+-[\w-]+\.ipynb$")
        correct = [nb for nb in notebooks if pattern.match(nb.name)]
        check(
            len(correct) == len(notebooks),
            cat,
            f"Notebook naming convention: {len(correct)}/{len(notebooks)} follow #.#-initials-description.ipynb",
            warn_only=True,
        )

    # CLAUDE.md: project instructions for AI-assisted development
    check(
        (ROOT / "CLAUDE.md").exists(),
        cat,
        "CLAUDE.md — project instructions for AI-assisted development",
        warn_only=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# REPORT
# ══════════════════════════════════════════════════════════════════════════════


def print_report(strict: bool = False):
    """Print compliance report."""
    print("\n" + "═" * 70)
    print("  EpiForecast-MX — Cookiecutter DS v2 Compliance Report")
    print("═" * 70)

    categories = {}
    for status, cat, msg in results:
        categories.setdefault(cat, []).append((status, msg))

    total_pass = sum(1 for s, _, _ in results if s == PASS)
    total_fail = sum(1 for s, _, _ in results if s == FAIL)
    total_warn = sum(1 for s, _, _ in results if s == WARN)
    total = len(results)

    for cat, checks in categories.items():
        cat_pass = sum(1 for s, _ in checks if s == PASS)
        cat_total = sum(1 for s, _ in checks if s != WARN)
        print(f"\n{'─' * 70}")
        print(f"  {cat} ({cat_pass}/{cat_total})")
        print(f"{'─' * 70}")
        for status, msg in checks:
            print(f"  {status} {msg}")

    # Summary
    print(f"\n{'═' * 70}")
    score = (total_pass / total * 100) if total > 0 else 0
    grade = (
        "A+"
        if score >= 95
        else "A"
        if score >= 90
        else "B+"
        if score >= 85
        else "B"
        if score >= 80
        else "C"
        if score >= 70
        else "D"
        if score >= 60
        else "F"
    )
    print(f"  SCORE: {total_pass}/{total} ({score:.0f}%) — Grade: {grade}")
    print(
        f"  {PASS} {total_pass} passed  {FAIL} {total_fail} failed  {WARN} {total_warn} warnings"
    )
    print(f"{'═' * 70}\n")

    # Exit code
    if strict:
        sys.exit(1 if (total_fail + total_warn) > 0 else 0)
    else:
        sys.exit(1 if total_fail > 0 else 0)


if __name__ == "__main__":
    strict = "--strict" in sys.argv

    check_directory_structure()
    check_solid_principles()
    check_clean_code()
    check_mlops()
    check_testing()
    check_tooling()
    check_imports()
    check_documentation()

    print_report(strict)
