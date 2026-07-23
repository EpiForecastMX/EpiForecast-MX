"""Fase 1 P0 — ownership/policy + slug + atomicidad segura + E2E del selector genérico.

Contrato: el genérico NO reproduce las políticas legacy ni pisa artefactos dedicados; solo
escribe un CANÓNICO vía ADAPTER CALLABLE (esquema validado ANTES de publicar) y un PRELIMINAR
honesto para no publicados. Gate completo en el resolver (slug + containment anclado a ROOT);
escritura atómica y segura ante symlinks (mkstemp O_EXCL, fsync, lock estable sin split-brain).
"""

from __future__ import annotations

import hashlib
import multiprocessing as mp
from pathlib import Path
import time

import pandas as pd
import pytest
import scripts.produccion_padecimiento as mod

from epiforecast.registry import load_registry


def load_registry_from_text(tmp_path: Path, text: str):
    p = tmp_path / "padecimientos.yaml"
    p.write_text(text, encoding="utf-8")
    return load_registry(p)


def _write_completo(root: Path, engine_prefix: str, artifact_key: str, engine_dir: str) -> None:
    """Escribe un ``<Prefix>_<key>_completo.csv`` mínimo (schema que lee _load_engine_metrics)."""
    d = root / "models" / engine_dir / artifact_key
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{engine_prefix}_{artifact_key}_completo.csv").write_text(
        "Entidad,sexo,smape,mase,rmse\n"
        "Nacional,incrementos_total,10.0,0.5,1.0\n"
        "Aguascalientes,incrementos_hombres,20.0,0.8,2.0\n",
        encoding="utf-8",
    )


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _tmp_residuos(directory: Path) -> list[str]:
    return [p.name for p in directory.iterdir() if ".tmp" in p.name]


_YAML_DENGUE_SLUG = """
version: 1
perfiles:
  conteos: {cohorte_id: conteos, motor_rate: {prophet: false, deepar: true}}
padecimientos:
  - id: dengue_fake
    data_name: DengueFake
    artifact_key: DengueFake
    slug: dengue
    cie_codes: [Z9]
    profile: conteos
    lifecycle: published
    selection_policy: legacy_dengue_2026
    eligible_engines: [prophet]
    training_engines: [prophet]
"""

_YAML_PUB_NEURO = """
version: 1
perfiles:
  neuro: {cohorte_id: neuro, motor_rate: {prophet: true}}
padecimientos:
  - id: pubneuro
    data_name: PubNeuro
    artifact_key: PubNeuro
    slug: pubneuro
    cie_codes: [N1]
    profile: neuro
    lifecycle: published
    selection_policy: legacy_neuro_2026
    eligible_engines: [prophet]
    training_engines: [prophet]
"""

_YAML_CONFIGURED = """
version: 1
perfiles:
  cronica: {cohorte_id: cronica, motor_rate: {prophet: true}}
padecimientos:
  - id: cfg
    data_name: Cfg
    artifact_key: Cfg
    slug: cfg
    cie_codes: [C9]
    profile: cronica
    lifecycle: configured
    selection_policy: rolling_cv_v1
    eligible_engines: [prophet]
    training_engines: [prophet]
"""

_YAML_BAD_SLUG = """
version: 1
perfiles:
  cronica: {cohorte_id: cronica, motor_rate: {prophet: true}}
padecimientos:
  - id: evil
    data_name: Evil
    artifact_key: Evil
    slug: "../escape"
    cie_codes: [E1]
    profile: cronica
    lifecycle: configured
    selection_policy: rolling_cv_v1
    eligible_engines: [prophet]
    training_engines: [prophet]
"""


def _valid_adapter(d, root):
    """Adapter con el esquema mínimo requerido + una columna propia (esquema del adapter)."""
    return pd.DataFrame(
        {
            "padecimiento": [d.data_name],
            "entidad": ["Nacional"],
            "sexo": ["general"],
            "motor_productivo": ["Prophet"],
            "criterio_seleccion": [d.selection_policy],
            "col_adapter": [1],
        }
    )


# ── Ownership: artefacto dedicado reservado (aun con adapter callable) ──
def test_slug_dengue_reservado_incluso_con_adapter(tmp_path, monkeypatch):
    reg = load_registry_from_text(tmp_path, _YAML_DENGUE_SLUG)
    monkeypatch.setattr(mod, "_CANONICAL_ADAPTERS", {"legacy_dengue_2026": _valid_adapter})
    d = reg.get("DengueFake")
    assert mod.resolve_destination(d, tmp_path, allow_preliminary=False) is None


# ── Adapter callable (una string NO habilita el canónico) ──
def test_string_en_adapters_no_habilita_canonico(tmp_path, monkeypatch):
    reg = load_registry_from_text(tmp_path, _YAML_PUB_NEURO)
    pub = reg.get("PubNeuro")
    monkeypatch.setattr(mod, "_CANONICAL_ADAPTERS", {"legacy_neuro_2026": "not-callable"})
    assert mod.resolve_destination(pub, tmp_path, allow_preliminary=False) is None


def test_canonical_delega_en_adapter_valido(tmp_path, monkeypatch):
    reg = load_registry_from_text(tmp_path, _YAML_PUB_NEURO)
    pub = reg.get("PubNeuro")
    monkeypatch.setattr(mod, "_CANONICAL_ADAPTERS", {"legacy_neuro_2026": _valid_adapter})
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod.registry, "require", lambda name: pub)
    rc = mod.main(["--disease", "PubNeuro"])
    assert rc == 0
    out = tmp_path / "reports" / "ProdDetails" / "produccion_pubneuro.csv"
    df = pd.read_csv(out)
    # El canónico tiene el ESQUEMA del adapter, no las columnas del selector genérico.
    assert "col_adapter" in df.columns


def test_adapter_esquema_invalido_no_publica_sentinel(tmp_path, monkeypatch):
    """Un adapter con esquema roto NO publica: se valida ANTES del replace; sentinel intacto."""
    reg = load_registry_from_text(tmp_path, _YAML_PUB_NEURO)
    pub = reg.get("PubNeuro")
    monkeypatch.setattr(
        mod,
        "_CANONICAL_ADAPTERS",
        {"legacy_neuro_2026": lambda d, root: pd.DataFrame({"wrong": [1]})},
    )
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod.registry, "require", lambda name: pub)
    dest = tmp_path / "reports" / "ProdDetails" / "produccion_pubneuro.csv"
    dest.parent.mkdir(parents=True)
    dest.write_text("SENTINEL\n", encoding="utf-8")
    before = _sha256(dest)

    rc = mod.main(["--disease", "PubNeuro"])
    assert rc == 3
    assert _sha256(dest) == before  # NO publicó basura


# ── Engine filename case (regresión Linux/CI) ──
@pytest.mark.parametrize(
    "engine,expected",
    [
        ("prophet", "Prophet"),
        ("deepar", "Deepar"),
        ("ensemble", "Ensemble"),
        ("stacking", "Stacking"),
        ("nbglm", "Nbglm"),
    ],
)
def test_engine_file_prefix_case_real(engine, expected):
    assert mod._engine_file_prefix(engine) == expected


def test_engine_file_prefix_difiere_del_display_en_deepar_nbglm():
    assert mod._engine_file_prefix("deepar") != mod._ENGINE_CAP["deepar"]
    assert mod._engine_file_prefix("nbglm") != mod._ENGINE_CAP["nbglm"]


# ── Slug fail-closed + containment anclado a ROOT ──
@pytest.mark.parametrize("bad", ["../evil", "a/b", "a.b", "A", "", "a b", "cafe/../x", "/abs"])
def test_validate_slug_rechaza_inseguros(bad):
    with pytest.raises(mod.SlugError):
        mod._validate_slug(bad)


def test_validate_slug_rechaza_muy_largo():
    with pytest.raises(mod.SlugError):
        mod._validate_slug("a" * 65)


@pytest.mark.parametrize("good", ["obesidad", "dengue", "a1_b2", "x"])
def test_validate_slug_acepta_seguros(good):
    mod._validate_slug(good)  # no raise


def test_resolve_destination_slug_traversal_raises(tmp_path):
    reg = load_registry_from_text(tmp_path, _YAML_BAD_SLUG)
    d = reg.get("Evil")
    with pytest.raises(mod.SlugError):
        mod.resolve_destination(d, tmp_path, allow_preliminary=True)


def _symlinked_preliminar(tmp_path: Path):
    """ROOT=repo con _preliminar_NO_GO -> external (fuera de ROOT); devuelve (root, external, d)."""
    root, external = tmp_path / "repo", tmp_path / "external"
    external.mkdir()
    (root / "reports" / "ProdDetails").mkdir(parents=True)
    (root / "reports" / "ProdDetails" / "_preliminar_NO_GO").symlink_to(
        external, target_is_directory=True
    )
    reg = load_registry_from_text(tmp_path, _YAML_CONFIGURED)
    return root, external, reg.get("Cfg")


def test_containment_symlink_fuera_de_root_rechazado(tmp_path):
    root, _external, d = _symlinked_preliminar(tmp_path)
    with pytest.raises(mod.SlugError):
        mod.resolve_destination(d, root, allow_preliminary=True)


def test_main_containment_symlink_no_escribe_fuera(tmp_path, monkeypatch):
    root, external, d = _symlinked_preliminar(tmp_path)
    monkeypatch.setattr(mod.registry, "require", lambda name: d)
    monkeypatch.setattr(mod, "ROOT", root)
    rc = mod.main(["--disease", "Cfg", "--allow-preliminary"])
    assert rc == 2
    assert list(external.iterdir()) == []  # nada escrito fuera de ROOT


# ── Escritura atómica segura ──
def _raise_os(*_a, **_k):
    raise OSError("boom")


def test_atomic_write_ok_sin_tmp_residuo(tmp_path):
    dest = tmp_path / "sub" / "out.csv"
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    mod._atomic_write_csv(df, dest)
    assert dest.exists()
    back = pd.read_csv(dest)
    assert list(back.columns) == ["a", "b"] and len(back) == 2
    assert _tmp_residuos(dest.parent) == []  # ningún .tmp (el .lock estable puede persistir)


def test_atomic_write_fallo_preserva_dest_y_limpia_tmp(tmp_path, monkeypatch):
    dest = tmp_path / "out.csv"
    dest.write_text("SENTINEL\n", encoding="utf-8")
    monkeypatch.setattr(mod.os, "replace", _raise_os)
    with pytest.raises(OSError):
        mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest)
    assert dest.read_text(encoding="utf-8") == "SENTINEL\n"  # intacto byte-a-byte
    assert _tmp_residuos(tmp_path) == []  # tmp limpiado


def test_atomic_write_no_sigue_symlink_del_tmp(tmp_path):
    """mkstemp (O_EXCL) no reutiliza un nombre pre-plantado; el destino queda archivo regular."""
    dest = tmp_path / "out.csv"
    external = tmp_path / "victim.txt"
    external.write_text("NO_TOCAR\n", encoding="utf-8")
    mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest)
    assert not dest.is_symlink()
    assert external.read_text(encoding="utf-8") == "NO_TOCAR\n"


# ── Lock: 3 procesos, sin split-brain ──
def _locked_incr_worker(root_str: str, iters: int) -> None:
    import scripts.produccion_padecimiento as m

    root = Path(root_str)
    lock, counter = root / "concur.lock", root / "counter.txt"
    for _ in range(iters):
        with m._file_lock(lock):
            v = int(counter.read_text())
            time.sleep(0.002)  # ensancha la ventana de carrera
            counter.write_text(str(v + 1))


def test_file_lock_tres_procesos_sin_split_brain(tmp_path):
    (tmp_path / "counter.txt").write_text("0", encoding="utf-8")
    ctx = mp.get_context("spawn")  # spawn: seguro con hilos (fork advierte/deadlock) y portable
    iters = 10
    procs = [
        ctx.Process(target=_locked_incr_worker, args=(str(tmp_path), iters)) for _ in range(3)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
    assert all(p.exitcode == 0 for p in procs)
    assert int((tmp_path / "counter.txt").read_text()) == 3 * iters  # sin lost updates


# ── E2E: preliminar (no publicado) ──
def test_e2e_preliminar_escribe_schema_honesto(tmp_path, monkeypatch):
    """Obesidad (configured) + --allow-preliminary escribe a _preliminar_NO_GO con criterio
    honesto y sin recrear el canónico. Incluye un fixture Deepar_ (case real)."""
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_completo(tmp_path, "Prophet", "Obesidad", "prophet")
    _write_completo(tmp_path, "Deepar", "Obesidad", "deepar")  # case real: Deepar_, no DeepAR_

    rc = mod.main(["--disease", "Obesidad", "--allow-preliminary"])
    assert rc == 0

    canonical = tmp_path / "reports" / "ProdDetails" / "produccion_obesidad.csv"
    preliminar = (
        tmp_path
        / "reports"
        / "ProdDetails"
        / "_preliminar_NO_GO"
        / "produccion_obesidad_PRELIMINAR.csv"
    )
    assert not canonical.exists()  # invariante: no toca el canónico
    assert preliminar.exists()

    df = pd.read_csv(preliminar)
    assert set(df["criterio_seleccion"]) == {"insample_cv_PRELIMINAR_NO_GO"}
    assert "rolling_cv_v1" not in set(df["criterio_seleccion"].astype(str))
    assert "smape_deepar" in df.columns  # el fixture Deepar_ SE cargó (case fix)
    assert "deepar" in set(df["motores_evaluados"].iloc[0].split(","))
    assert list(df.columns[:3]) == ["padecimiento", "entidad", "sexo"]
    assert _tmp_residuos(preliminar.parent) == []  # sin residuos de escritura atómica


# ── E2E: published dedicado → gated, sentinel byte-idéntico tras AMBOS aborts ──
_DENGUE_SENTINEL = (
    "padecimiento,entidad,sexo,motor_productivo,criterio_seleccion,smape_ganador\n"
    "Dengue,Nacional,general,DeepAR,legacy_dengue_2026,12.3\n"
)


def _seed_dengue_sentinel(root: Path) -> Path:
    p = root / "reports" / "ProdDetails" / "produccion_dengue.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_DENGUE_SENTINEL, encoding="utf-8")
    return p


def test_e2e_dengue_gated_preserva_sentinel(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    sentinel = _seed_dengue_sentinel(tmp_path)
    before_sha, before_bytes = _sha256(sentinel), sentinel.read_bytes()
    before = pd.read_csv(sentinel)
    _write_completo(tmp_path, "Prophet", "Dengue", "prophet")  # aunque haya métricas

    rc = mod.main(["--disease", "Dengue"])
    assert rc == 2

    assert _sha256(sentinel) == before_sha
    assert sentinel.read_bytes() == before_bytes
    after = pd.read_csv(sentinel)
    assert list(after.columns) == list(before.columns)
    assert len(after) == len(before)


def test_e2e_allow_preliminary_en_published_preserva_sentinel(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    sentinel = _seed_dengue_sentinel(tmp_path)
    before_sha, before_bytes = _sha256(sentinel), sentinel.read_bytes()

    rc = mod.main(["--disease", "Dengue", "--allow-preliminary"])
    assert rc == 2

    assert _sha256(sentinel) == before_sha
    assert sentinel.read_bytes() == before_bytes
