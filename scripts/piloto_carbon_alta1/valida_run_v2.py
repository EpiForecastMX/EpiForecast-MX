"""Validador reproducible RUN_v2 (SHA40) y comparador de doble corrida — piloto Carbon alta1.

Recomputa todos los hashes desde disco y git sin confiar en autodeclaraciones previas:
- Commit exacto de 40 hex en el worktree y árbol git limpio (sin modificaciones ni archivos no
  rastreados en config/, src/, scripts/).
- Fijación del propio validador contra el blob ``HEAD:scripts/piloto_carbon_alta1/valida_run_v2.py``
  (y opcionalmente ``--expected-validator-sha256``).
- Hashes SHA-256 de configuración y fuentes del extractor idénticos en inicio, fin, árbol actual y
  blob de ``HEAD``.
- Inventario del corpus PDF variable por archivo JSON sellado (ej. ``ROOT_PDF_INVENTORY.json`` de
  670 PDFs), verificando presencia exacta, tamaño y SHA-256 de cada PDF en ``--pdf-dir``.
- Frescura (``mtime >= t0_epoch``), ausencia previa de ``data/interim/<slug>_*`` antes de extraer,
  e igualdad byte a byte entre el original en ``data/interim/`` y la copia archivada en ``out_dir``.
- El manifiesto por PDF es el gate: sin duplicados, cobertura exacta del inventario, sólo estados
  ``ok`` / ``excluded``, ``32`` entidades en cada ``ok``, exclusiones iguales a ``cuadros.yaml`` y
  conteo exacto de filas en ``<id>_boletin.csv``.
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any

import yaml

VERSION = "piloto_carbon_alta1.valida_run_v2.v1"
SCHEMA_RUN_V2 = "piloto_carbon_alta1.run_v2"
SCHEMA_CANON = "piloto_carbon_alta1.canon_raw.v1"
ESTADOS_VALIDOS = frozenset({"ok", "excluded"})
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
VALIDATOR_REL_PATH = "scripts/piloto_carbon_alta1/valida_run_v2.py"

TRACKED_EXTRACTION_INPUTS: tuple[str, ...] = (
    "config/data/cuadros.yaml",
    "config/padecimientos.yaml",
    "src/epiforecast/data/extraction/cuadro_extractor.py",
    "src/epiforecast/data/extraction/cuadro_reparaciones.py",
    "src/epiforecast/data/extraction/pdf_extractor.py",
    "src/epiforecast/data/extraction/dengue_extractor.py",
    "scripts/extrae_cuadro.py",
)

SINGLE_THREAD_VARS: tuple[str, ...] = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)


def sha256_file(path: Path) -> str | None:
    """Calcula el SHA-256 de un archivo regular, o None si no existe."""
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def compute_tracked_hashes(worktree: Path) -> dict[str, str | None]:
    """Calcula el mapa de hashes SHA-256 de las entradas rastreadas del extractor."""
    return {rel: sha256_file(worktree / rel) for rel in TRACKED_EXTRACTION_INPUTS}


def git_head_40(worktree: Path) -> str | None:
    """Devuelve el SHA de 40 hex de HEAD en worktree, o None si falla."""
    res = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return None
    sha = res.stdout.strip()
    return sha if HEX40_RE.fullmatch(sha) else None


def git_dirty_entries(worktree: Path) -> list[str]:
    """Entradas sucias en archivos rastreados o no rastreados bajo config/, src/, scripts/, tests/."""
    res = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return ["git_status_error"]
    dirty: list[str] = []
    protected_prefixes = ("config/", "src/", "scripts/", "tests/")
    for line in res.stdout.splitlines():
        if not line:
            continue
        status_code = line[:2]
        rel = line[3:].strip()
        if status_code != "??" or rel.startswith(protected_prefixes):
            dirty.append(line)
    return dirty


def git_blob_sha256(worktree: Path, commit40: str, rel_path: str) -> str | None:
    """Devuelve el SHA-256 del blob ``<commit40>:<rel_path>`` en git."""
    res = subprocess.run(
        ["git", "-C", str(worktree), "show", f"{commit40}:{rel_path}"],
        capture_output=True,
        check=False,
    )
    if res.returncode != 0:
        return None
    return hashlib.sha256(res.stdout).hexdigest()


def slug_for_disease(padecimientos_cfg: dict[str, Any], disease_id: str) -> str:
    """Resuelve el slug del padecimiento desde ``config/padecimientos.yaml``."""
    for entry in padecimientos_cfg.get("padecimientos", []):
        if entry.get("id") == disease_id:
            return str(entry.get("slug") or disease_id)
    raise KeyError(f"padecimiento no encontrado en config/padecimientos.yaml: {disease_id}")


def declarados_cuadros(
    cuadros_cfg: dict[str, Any], disease_id: str
) -> tuple[list[str], list[str], int]:
    """Devuelve (excluidos_todos, excluidos_keep_period, n_states_expected) para ``disease_id``."""
    groups = cuadros_cfg.get("cuadro_groups", {})
    group = next(
        (
            spec
            for spec in groups.values()
            if any(d.get("id") == disease_id for d in spec.get("diseases", []))
        ),
        None,
    )
    if group is None:
        raise KeyError(f"grupo de cuadro no encontrado para: {disease_id}")
    exclusions = [
        exc
        for exc in (group.get("source_exclusions") or [])
        if disease_id in exc.get("diseases", [])
    ]
    all_excl = sorted(str(exc["file"]) for exc in exclusions)
    keep_excl = sorted(str(exc["file"]) for exc in exclusions if exc.get("keep_period", False))
    n_states = int(group.get("n_states_expected", 32))
    return all_excl, keep_excl, n_states


def verify_pdf_inventory(
    pdf_dir: Path,
    inventory_json: Path,
    *,
    expected_inventory_sha256: str | None = None,
    verify_pdf_hashes: bool = True,
) -> tuple[list[str], dict[str, Any]]:
    """Verifica el directorio PDF contra el JSON sellado del inventario."""
    fallas: list[str] = []
    inv_sha = sha256_file(inventory_json)
    if inv_sha is None:
        return ["inventory_json inexistente"], {"inventory_sha256": None, "count": 0, "files": []}
    if expected_inventory_sha256 and inv_sha != expected_inventory_sha256:
        fallas.append(f"inventory_json sha256 {inv_sha} != esperado {expected_inventory_sha256}")
    data = json.loads(inventory_json.read_text(encoding="utf-8"))
    entries = data.get("files")
    if not isinstance(entries, list) or not entries:
        return [*fallas, "inventory_json sin lista files válida"], {
            "inventory_sha256": inv_sha,
            "count": 0,
            "files": [],
        }
    declared_count = int(data.get("count", len(entries)))
    if declared_count != len(entries):
        fallas.append(f"inventory_json count={declared_count} != len(files)={len(entries)}")

    expected_map: dict[str, dict[str, Any]] = {}
    for item in entries:
        fname = str(item["file"])
        if fname in expected_map:
            fallas.append(f"PDF duplicado en inventory_json: {fname}")
        expected_map[fname] = item

    if not pdf_dir.is_dir():
        return [*fallas, f"pdf_dir inexistente: {pdf_dir}"], {
            "inventory_sha256": inv_sha,
            "count": len(expected_map),
            "files": sorted(expected_map),
        }

    actual_pdfs = sorted(p.name for p in pdf_dir.iterdir() if p.suffix.lower() == ".pdf")
    expected_pdfs = sorted(expected_map)
    if actual_pdfs != expected_pdfs:
        faltan = sorted(set(expected_pdfs) - set(actual_pdfs))
        sobran = sorted(set(actual_pdfs) - set(expected_pdfs))
        fallas.append(
            f"pdf_dir no coincide con inventory_json: faltan={faltan[:5]} ({len(faltan)}), "
            f"sobran={sobran[:5]} ({len(sobran)})"
        )

    hash_mismatches: list[str] = []
    size_mismatches: list[str] = []
    if verify_pdf_hashes:
        for fname in sorted(set(expected_pdfs) & set(actual_pdfs)):
            p = pdf_dir / fname
            spec_item = expected_map[fname]
            if "bytes" in spec_item and p.stat().st_size != int(spec_item["bytes"]):
                size_mismatches.append(fname)
            if "sha256" in spec_item and sha256_file(p) != str(spec_item["sha256"]):
                hash_mismatches.append(fname)
    if size_mismatches:
        fallas.append(
            f"tamaño PDF distinto del inventario: {size_mismatches[:5]} ({len(size_mismatches)})"
        )
    if hash_mismatches:
        fallas.append(
            f"sha256 PDF distinto del inventario: {hash_mismatches[:5]} ({len(hash_mismatches)})"
        )

    return fallas, {
        "inventory_json": str(inventory_json.resolve()),
        "inventory_sha256": inv_sha,
        "pdf_dir": str(pdf_dir.resolve()),
        "count": len(expected_pdfs),
        "files": expected_pdfs,
    }


def validate_single_run(
    *,
    run_raw_path: Path,
    worktree: Path,
    out_dir: Path,
    pdf_dir: Path,
    inventory_json: Path,
    expected_commit: str | None = None,
    expected_inventory_sha256: str | None = None,
    expected_validator_sha256: str | None = None,
    validator_file: Path | None = None,
    verify_pdf_hashes: bool = True,
) -> tuple[int, dict[str, Any]]:
    """Recomputa hashes y valida una corrida individual, escribiendo ``<id>_RUN_v2.json``."""
    fallas: list[str] = []
    wt = worktree.resolve()
    out = out_dir.resolve()
    val_path = (validator_file or Path(__file__)).resolve()
    val_disk_sha = sha256_file(val_path)

    if not run_raw_path.is_file():
        raise FileNotFoundError(f"run_raw_path inexistente: {run_raw_path}")
    run_raw = json.loads(run_raw_path.read_text(encoding="utf-8"))
    disease_id = str(run_raw["id"])
    pasada = str(run_raw["pasada"])

    head40 = git_head_40(wt)
    if head40 is None:
        fallas.append("HEAD del worktree no es un SHA de 40 hex")
    else:
        if run_raw.get("snapshot_sha") != head40:
            fallas.append(
                f"snapshot_sha registrado ({run_raw.get('snapshot_sha')}) != HEAD ({head40})"
            )
        if expected_commit and head40 != expected_commit:
            fallas.append(f"HEAD ({head40}) != expected_commit ({expected_commit})")

    dirty = git_dirty_entries(wt)
    if dirty:
        fallas.append(f"worktree sucio (dirty): {dirty[:5]}")

    val_git_sha = git_blob_sha256(wt, head40, VALIDATOR_REL_PATH) if head40 else None
    if val_disk_sha is None or val_git_sha is None or val_disk_sha != val_git_sha:
        fallas.append(
            f"validador en disco ({val_disk_sha}) != blob fijado en HEAD ({val_git_sha})"
        )
    if expected_validator_sha256 and val_disk_sha != expected_validator_sha256:
        fallas.append(
            f"validador en disco ({val_disk_sha}) != expected_validator_sha256 "
            f"({expected_validator_sha256})"
        )

    if int(run_raw.get("rc", -1)) != 0:
        fallas.append(f"rc={run_raw.get('rc')}")
    if run_raw.get("pre_interim_absent") is not True:
        fallas.append("pre_interim_absent no es True (data/interim no estaba limpio al iniciar)")
    if str(run_raw.get("cwd", "")) != str(wt):
        fallas.append(f"cwd registrado ({run_raw.get('cwd')}) != worktree ({wt})")

    expected_reg = str((wt / "src" / "epiforecast" / "registry.py").resolve())
    expected_ext = str((wt / "scripts" / "extrae_cuadro.py").resolve())
    if str(run_raw.get("registry_file", "")) != expected_reg:
        fallas.append(
            f"registry.__file__ ({run_raw.get('registry_file')}) != worktree ({expected_reg})"
        )
    if str(run_raw.get("extrae_cuadro_file", "")) != expected_ext:
        fallas.append(
            f"extrae_cuadro.__file__ ({run_raw.get('extrae_cuadro_file')}) != worktree ({expected_ext})"
        )

    threads_env = run_raw.get("single_thread_env") or {}
    if any(str(threads_env.get(k)) != "1" for k in SINGLE_THREAD_VARS):
        fallas.append("variables de hilos numéricos distintas de '1'")

    actual_hashes = compute_tracked_hashes(wt)
    if any(v is None for v in actual_hashes.values()):
        fallas.append("faltan archivos rastreados de configuración o extractor en worktree")
    if run_raw.get("tracked_hashes_inicio") != actual_hashes:
        fallas.append("tracked_hashes_inicio != hashes actuales recomputados")
    if run_raw.get("tracked_hashes_fin") != actual_hashes:
        fallas.append("tracked_hashes_fin != hashes actuales recomputados")
    if head40:
        head_hashes = {rel: git_blob_sha256(wt, head40, rel) for rel in TRACKED_EXTRACTION_INPUTS}
        if head_hashes != actual_hashes:
            fallas.append("hashes en disco difieren de los blobs del commit40")

    inv_fallas, inv_meta = verify_pdf_inventory(
        pdf_dir,
        inventory_json,
        expected_inventory_sha256=expected_inventory_sha256,
        verify_pdf_hashes=verify_pdf_hashes,
    )
    fallas.extend(inv_fallas)
    if run_raw.get("inventory_sha256_inicio") != inv_meta["inventory_sha256"]:
        fallas.append("inventory_sha256_inicio != sha256 actual de inventory_json")
    if run_raw.get("inventory_sha256_fin") != inv_meta["inventory_sha256"]:
        fallas.append("inventory_sha256_fin != sha256 actual de inventory_json")

    pad_cfg = yaml.safe_load((wt / "config" / "padecimientos.yaml").read_text(encoding="utf-8"))
    cuadros_cfg = yaml.safe_load(
        (wt / "config" / "data" / "cuadros.yaml").read_text(encoding="utf-8")
    )
    slug = slug_for_disease(pad_cfg, disease_id)
    decl_all, decl_keep, n_states_expected = declarados_cuadros(cuadros_cfg, disease_id)

    interim_csv = wt / "data" / "interim" / f"{slug}_boletin.csv"
    interim_man = wt / "data" / "interim" / f"{slug}_extraccion_manifest.csv"
    copy_csv = out / f"{disease_id}_boletin.csv"
    copy_man = out / f"{disease_id}_extraccion_manifest.csv"

    t0_epoch = float(run_raw.get("t0_epoch", 0.0))
    for label, p in (
        ("interim_csv", interim_csv),
        ("interim_manifest", interim_man),
        ("copy_csv", copy_csv),
        ("copy_manifest", copy_man),
    ):
        if not p.is_file() or p.stat().st_size == 0:
            fallas.append(f"{label} inexistente o vacío: {p.name}")
        elif p.stat().st_mtime < t0_epoch:
            fallas.append(f"{label} no es fresco (mtime < t0_epoch): {p.name}")

    interim_csv_sha = sha256_file(interim_csv)
    interim_man_sha = sha256_file(interim_man)
    copy_csv_sha = sha256_file(copy_csv)
    copy_man_sha = sha256_file(copy_man)

    if copy_csv_sha is None or copy_csv_sha != run_raw.get("csv_sha256"):
        fallas.append("copy_csv sha256 != csv_sha256 registrado en run_raw")
    if copy_man_sha is None or copy_man_sha != run_raw.get("manifiesto_sha256"):
        fallas.append("copy_manifest sha256 != manifiesto_sha256 registrado en run_raw")
    if interim_csv_sha != copy_csv_sha:
        fallas.append("interim_csv sha256 != copy_csv sha256 (sobreescrito o copia corrupta)")
    if interim_man_sha != copy_man_sha:
        fallas.append("interim_manifest sha256 != copy_manifest sha256")

    estados: dict[str, int] = {}
    excluidos: list[str] = []
    manifest_rows: list[dict[str, str]] = []
    if copy_man.is_file():
        with copy_man.open(encoding="utf-8", newline="") as fh:
            manifest_rows = list(csv.DictReader(fh))
        seen_files = [r["file"] for r in manifest_rows]
        if len(seen_files) != len(set(seen_files)):
            fallas.append("manifiesto con PDFs duplicados")
        previstos = inv_meta["files"]
        if previstos and set(seen_files) != set(previstos):
            faltan = sorted(set(previstos) - set(seen_files))
            sobran = sorted(set(seen_files) - set(previstos))
            fallas.append(
                f"manifiesto no cubre el inventario: faltan={faltan[:5]} ({len(faltan)}), "
                f"sobran={sobran[:5]} ({len(sobran)})"
            )
        bad_states_rows: list[str] = []
        for r in manifest_rows:
            st = r["status"]
            estados[st] = estados.get(st, 0) + 1
            if st == "ok" and int(r.get("n_states") or 0) != n_states_expected:
                bad_states_rows.append(f"{r['file']}:{r.get('n_states')}")
        if set(estados) - ESTADOS_VALIDOS:
            fallas.append(
                f"estados no válidos en manifiesto: {sorted(set(estados) - ESTADOS_VALIDOS)}"
            )
        if bad_states_rows:
            fallas.append(f"boletines ok sin {n_states_expected} entidades: {bad_states_rows[:5]}")
        excluidos = sorted(r["file"] for r in manifest_rows if r["status"] == "excluded")
        if excluidos != decl_all:
            fallas.append(f"excluidos {excluidos} != declarados {decl_all}")

    csv_rows_count = 0
    if copy_csv.is_file():
        with copy_csv.open(encoding="utf-8", newline="") as fh:
            reader = list(csv.DictReader(fh))
        csv_rows_count = len(reader)
        expected_rows = (estados.get("ok", 0) + len(decl_keep)) * n_states_expected
        if manifest_rows and csv_rows_count != expected_rows:
            fallas.append(
                f"filas CSV ({csv_rows_count}) != esperadas ({expected_rows} = "
                f"({estados.get('ok', 0)} ok + {len(decl_keep)} keep_period) * {n_states_expected})"
            )
        keys = [(r["Anio"], r["Semana"], r["Entidad"], r["Padecimiento"]) for r in reader]
        if len(keys) != len(set(keys)):
            fallas.append("claves duplicadas (Anio, Semana, Entidad, Padecimiento) en boletin.csv")

    payload: dict[str, Any] = {
        "schema": SCHEMA_RUN_V2,
        "id": disease_id,
        "slug": slug,
        "pasada": pasada,
        "worktree": str(wt),
        "snapshot_sha": head40,
        "run_raw": {
            "path": str(run_raw_path.resolve()),
            "sha256": sha256_file(run_raw_path),
        },
        "tracked_hashes_recomputed": actual_hashes,
        "inventario": {
            "json_path": inv_meta.get("inventory_json"),
            "json_sha256": inv_meta.get("inventory_sha256"),
            "pdf_dir": inv_meta.get("pdf_dir"),
            "pdf_count": inv_meta.get("count"),
            "pdf_hashes_verified": verify_pdf_hashes,
        },
        "csv_sha256": copy_csv_sha,
        "manifiesto_sha256": copy_man_sha,
        "csv_rows": csv_rows_count,
        "estados": estados,
        "excluidos": excluidos,
        "declarados": decl_all,
        "declarados_keep_period": decl_keep,
        "validador": {
            "version": VERSION,
            "rel_path": VALIDATOR_REL_PATH,
            "sha256": val_disk_sha,
            "git_blob_sha256": val_git_sha,
        },
        "revalidado_utc": datetime.now(UTC).isoformat(),
        "valida": len(fallas) == 0,
        "fallas": fallas,
    }
    out.mkdir(parents=True, exist_ok=True)
    out_v2 = out / f"{disease_id}_RUN_v2.json"
    out_v2.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return (0 if not fallas else 1), payload


def _set_readonly(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def validate_pair(
    *,
    disease_id: str,
    dir_a: Path,
    worktree_a: Path,
    dir_b: Path,
    worktree_b: Path,
    canon_dir: Path,
    pdf_dir: Path,
    inventory_json: Path,
    expected_commit: str | None = None,
    expected_inventory_sha256: str | None = None,
    expected_validator_sha256: str | None = None,
    verify_pdf_hashes: bool = True,
) -> tuple[int, dict[str, Any]]:
    """Revalida ambas corridas independientes y sella el canónico si coinciden byte a byte."""
    fallas: list[str] = []
    if worktree_a.resolve() == worktree_b.resolve():
        fallas.append("worktree_a y worktree_b deben ser directorios distintos (F5)")
    if dir_a.resolve() == dir_b.resolve():
        fallas.append("dir_a y dir_b deben ser directorios distintos (F5)")

    rc_a, v2_a = validate_single_run(
        run_raw_path=dir_a / f"{disease_id}_RUN_raw.json",
        worktree=worktree_a,
        out_dir=dir_a,
        pdf_dir=pdf_dir,
        inventory_json=inventory_json,
        expected_commit=expected_commit,
        expected_inventory_sha256=expected_inventory_sha256,
        expected_validator_sha256=expected_validator_sha256,
        verify_pdf_hashes=verify_pdf_hashes,
    )
    rc_b, v2_b = validate_single_run(
        run_raw_path=dir_b / f"{disease_id}_RUN_raw.json",
        worktree=worktree_b,
        out_dir=dir_b,
        pdf_dir=pdf_dir,
        inventory_json=inventory_json,
        expected_commit=expected_commit,
        expected_inventory_sha256=expected_inventory_sha256,
        expected_validator_sha256=expected_validator_sha256,
        verify_pdf_hashes=verify_pdf_hashes,
    )
    if rc_a != 0 or not v2_a["valida"]:
        fallas.append(f"corrida A inválida: {v2_a['fallas']}")
    if rc_b != 0 or not v2_b["valida"]:
        fallas.append(f"corrida B inválida: {v2_b['fallas']}")
    if v2_a["snapshot_sha"] != v2_b["snapshot_sha"]:
        fallas.append(
            f"snapshot_sha distinto entre A ({v2_a['snapshot_sha']}) y B ({v2_b['snapshot_sha']})"
        )
    if v2_a["csv_sha256"] != v2_b["csv_sha256"]:
        fallas.append(
            f"boletin.csv distinto entre A ({v2_a['csv_sha256']}) y B ({v2_b['csv_sha256']})"
        )
    if v2_a["manifiesto_sha256"] != v2_b["manifiesto_sha256"]:
        fallas.append(
            f"manifiesto distinto entre A ({v2_a['manifiesto_sha256']}) y "
            f"B ({v2_b['manifiesto_sha256']})"
        )

    canon_dir.mkdir(parents=True, exist_ok=True)
    canon_csv = canon_dir / f"{disease_id}_boletin.csv"
    canon_man = canon_dir / f"{disease_id}_extraccion_manifest.csv"
    sums_path = canon_dir / "SHA256SUMS"
    canon_json = canon_dir / f"{disease_id}_CANON_RAW.json"

    if not fallas:
        for dst in (canon_csv, canon_man, sums_path):
            if dst.exists():
                dst.chmod(stat.S_IWUSR | stat.S_IRUSR)
        shutil.copy2(dir_a / f"{disease_id}_boletin.csv", canon_csv)
        shutil.copy2(dir_a / f"{disease_id}_extraccion_manifest.csv", canon_man)
        if sha256_file(canon_csv) != v2_a["csv_sha256"]:
            fallas.append("copia canónica boletin.csv no coincide con sha256 validado")
        if sha256_file(canon_man) != v2_a["manifiesto_sha256"]:
            fallas.append("copia canónica manifiesto no coincide con sha256 validado")
        sums_text = (
            f"{v2_a['csv_sha256']}  {canon_csv.name}\n"
            f"{v2_a['manifiesto_sha256']}  {canon_man.name}\n"
        )
        sums_path.write_text(sums_text, encoding="utf-8")
        _set_readonly(canon_csv)
        _set_readonly(canon_man)
        _set_readonly(sums_path)

    payload: dict[str, Any] = {
        "schema": SCHEMA_CANON,
        "id": disease_id,
        "snapshot_sha": v2_a["snapshot_sha"] if not fallas else None,
        "raw_sha256": v2_a["csv_sha256"] if not fallas else None,
        "manifiesto_sha256": v2_a["manifiesto_sha256"] if not fallas else None,
        "csv_rows": v2_a["csv_rows"] if not fallas else 0,
        "pasadas": {"a": v2_a, "b": v2_b},
        "sellado_utc": datetime.now(UTC).isoformat(),
        "valida": len(fallas) == 0,
        "fallas": fallas,
    }
    if canon_json.exists():
        canon_json.chmod(stat.S_IWUSR | stat.S_IRUSR)
    canon_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not fallas:
        _set_readonly(canon_json)
    return (0 if not fallas else 1), payload


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_single = sub.add_parser("single", help="revalida una corrida individual y escribe RUN_v2")
    p_single.add_argument("--run-raw", type=Path, required=True)
    p_single.add_argument("--worktree", type=Path, required=True)
    p_single.add_argument("--out-dir", type=Path, required=True)
    p_single.add_argument("--pdf-dir", type=Path, required=True)
    p_single.add_argument("--inventory-json", type=Path, required=True)
    p_single.add_argument("--expected-commit", default=None)
    p_single.add_argument("--expected-inventory-sha256", default=None)
    p_single.add_argument("--expected-validator-sha256", default=None)
    p_single.add_argument("--skip-pdf-hashes", action="store_true")

    p_pair = sub.add_parser("pair", help="revalida dos corridas aisladas y sella el canónico")
    p_pair.add_argument("--disease", required=True)
    p_pair.add_argument("--dir-a", type=Path, required=True)
    p_pair.add_argument("--worktree-a", type=Path, required=True)
    p_pair.add_argument("--dir-b", type=Path, required=True)
    p_pair.add_argument("--worktree-b", type=Path, required=True)
    p_pair.add_argument("--canon-dir", type=Path, required=True)
    p_pair.add_argument("--pdf-dir", type=Path, required=True)
    p_pair.add_argument("--inventory-json", type=Path, required=True)
    p_pair.add_argument("--expected-commit", default=None)
    p_pair.add_argument("--expected-inventory-sha256", default=None)
    p_pair.add_argument("--expected-validator-sha256", default=None)
    p_pair.add_argument("--skip-pdf-hashes", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "single":
        rc, res = validate_single_run(
            run_raw_path=args.run_raw,
            worktree=args.worktree,
            out_dir=args.out_dir,
            pdf_dir=args.pdf_dir,
            inventory_json=args.inventory_json,
            expected_commit=args.expected_commit,
            expected_inventory_sha256=args.expected_inventory_sha256,
            expected_validator_sha256=args.expected_validator_sha256,
            verify_pdf_hashes=not args.skip_pdf_hashes,
        )
        print(
            f"{res['id']} {res['pasada']} "
            f"{'VALIDA' if res['valida'] else 'FALLA'} csv={str(res['csv_sha256'])[:12]} "
            f"fallas={res['fallas']}"
        )
        return rc

    rc, res = validate_pair(
        disease_id=args.disease,
        dir_a=args.dir_a,
        worktree_a=args.worktree_a,
        dir_b=args.dir_b,
        worktree_b=args.worktree_b,
        canon_dir=args.canon_dir,
        pdf_dir=args.pdf_dir,
        inventory_json=args.inventory_json,
        expected_commit=args.expected_commit,
        expected_inventory_sha256=args.expected_inventory_sha256,
        expected_validator_sha256=args.expected_validator_sha256,
        verify_pdf_hashes=not args.skip_pdf_hashes,
    )
    print(
        f"{res['id']} PAIR {'VALIDA' if res['valida'] else 'FALLA'} "
        f"raw={str(res['raw_sha256'])[:12]} fallas={res['fallas']}"
    )
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
