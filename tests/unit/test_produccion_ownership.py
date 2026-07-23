"""Fase 1 P0 — ownership/policy + slug + escritura TOCTOU-safe + E2E del selector genérico.

Contrato: el genérico solo escribe un CANÓNICO vía ADAPTER CALLABLE (selección validada
contextualmente ANTES de publicar) y un PRELIMINAR honesto para no publicados. Escritura anclada
a ROOT con openat/O_NOFOLLOW (segura ante swaps por symlink), tmp exclusivo, fsync, modo 0644
preservado, lock estable con cierre garantizado.
"""

from __future__ import annotations

import hashlib
import multiprocessing as mp
from pathlib import Path
import stat
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


def _mode(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


_YAML_DENGUE_SLUG = """
version: 1
perfiles:
  conteos: {cohorte_id: conteos, motor_rate: {prophet: false, deepar: true}}
padecimientos:
  - {id: dengue_fake, data_name: DengueFake, artifact_key: DengueFake, slug: dengue,
     cie_codes: [Z9], profile: conteos, lifecycle: published,
     selection_policy: legacy_dengue_2026, eligible_engines: [prophet], training_engines: [prophet]}
"""

_YAML_PUB_NEURO = """
version: 1
perfiles:
  neuro: {cohorte_id: neuro, motor_rate: {prophet: true}}
padecimientos:
  - {id: pubneuro, data_name: PubNeuro, artifact_key: PubNeuro, slug: pubneuro,
     cie_codes: [N1], profile: neuro, lifecycle: published,
     selection_policy: legacy_neuro_2026, eligible_engines: [prophet], training_engines: [prophet]}
"""

_YAML_CONFIGURED = """
version: 1
perfiles:
  cronica: {cohorte_id: cronica, motor_rate: {prophet: true}}
padecimientos:
  - {id: cfg, data_name: Cfg, artifact_key: Cfg, slug: cfg, cie_codes: [C9],
     profile: cronica, lifecycle: configured, selection_policy: rolling_cv_v1,
     eligible_engines: [prophet], training_engines: [prophet]}
"""

_YAML_BAD_SLUG = """
version: 1
perfiles:
  cronica: {cohorte_id: cronica, motor_rate: {prophet: true}}
padecimientos:
  - {id: evil, data_name: Evil, artifact_key: Evil, slug: "../escape", cie_codes: [E1],
     profile: cronica, lifecycle: configured, selection_policy: rolling_cv_v1,
     eligible_engines: [prophet], training_engines: [prophet]}
"""


def _valid_adapter(d, root):
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


# ── Ownership + adapter callable ──
def test_slug_dengue_reservado_incluso_con_adapter(tmp_path, monkeypatch):
    reg = load_registry_from_text(tmp_path, _YAML_DENGUE_SLUG)
    monkeypatch.setattr(mod, "_CANONICAL_ADAPTERS", {"legacy_dengue_2026": _valid_adapter})
    assert (
        mod.resolve_destination(reg.get("DengueFake"), tmp_path, allow_preliminary=False) is None
    )


def test_string_en_adapters_no_habilita_canonico(tmp_path, monkeypatch):
    reg = load_registry_from_text(tmp_path, _YAML_PUB_NEURO)
    monkeypatch.setattr(mod, "_CANONICAL_ADAPTERS", {"legacy_neuro_2026": "not-callable"})
    assert mod.resolve_destination(reg.get("PubNeuro"), tmp_path, allow_preliminary=False) is None


def test_canonical_delega_en_adapter_valido(tmp_path, monkeypatch):
    reg = load_registry_from_text(tmp_path, _YAML_PUB_NEURO)
    pub = reg.get("PubNeuro")
    monkeypatch.setattr(mod, "_CANONICAL_ADAPTERS", {"legacy_neuro_2026": _valid_adapter})
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod.registry, "require", lambda name: pub)
    assert mod.main(["--disease", "PubNeuro"]) == 0
    df = pd.read_csv(tmp_path / "reports" / "ProdDetails" / "produccion_pubneuro.csv")
    assert "col_adapter" in df.columns  # esquema del adapter, no del genérico


# ── Validación contextual ANTES de publicar (nunca publica basura) ──
def _adapter_bad(fields: dict):
    base = {
        "padecimiento": ["PubNeuro"],
        "entidad": ["Nacional"],
        "sexo": ["general"],
        "motor_productivo": ["Prophet"],
        "criterio_seleccion": ["legacy_neuro_2026"],
    }
    base.update(fields)

    def adapter(d, root):
        return pd.DataFrame(base)

    return adapter


_BAD_ADAPTERS = {
    "faltan_columnas": lambda: (lambda d, root: pd.DataFrame({"wrong": [1]})),
    "no_dataframe": lambda: (lambda d, root: {"padecimiento": "x"}),
    "no_escalar": lambda: _adapter_bad({"motor_productivo": [["Prophet"]]}),
    "null": lambda: _adapter_bad({"motor_productivo": [None]}),
    "enfermedad_incorrecta": lambda: _adapter_bad({"padecimiento": ["Otra"]}),
    "criterio_incorrecto": lambda: _adapter_bad({"criterio_seleccion": ["mentira"]}),
    "motor_no_permitido": lambda: _adapter_bad({"motor_productivo": ["XGBoost"]}),
    "claves_duplicadas": lambda: (
        lambda d, root: pd.DataFrame(
            {
                "padecimiento": ["PubNeuro", "PubNeuro"],
                "entidad": ["Nacional", "Nacional"],
                "sexo": ["general", "general"],
                "motor_productivo": ["Prophet", "Prophet"],
                "criterio_seleccion": ["legacy_neuro_2026", "legacy_neuro_2026"],
            }
        )
    ),
}


@pytest.mark.parametrize("caso", sorted(_BAD_ADAPTERS))
def test_adapter_invalido_no_publica_sentinel(tmp_path, monkeypatch, caso):
    reg = load_registry_from_text(tmp_path, _YAML_PUB_NEURO)
    pub = reg.get("PubNeuro")
    monkeypatch.setattr(mod, "_CANONICAL_ADAPTERS", {"legacy_neuro_2026": _BAD_ADAPTERS[caso]()})
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod.registry, "require", lambda name: pub)
    dest = tmp_path / "reports" / "ProdDetails" / "produccion_pubneuro.csv"
    dest.parent.mkdir(parents=True)
    dest.write_text("SENTINEL\n", encoding="utf-8")
    before = _sha256(dest)

    assert mod.main(["--disease", "PubNeuro"]) == 3
    assert _sha256(dest) == before  # NO publicó; sentinel intacto byte-a-byte


# ── Engine filename case (regresión Linux/CI) ──
@pytest.mark.parametrize(
    "engine,expected",
    [("prophet", "Prophet"), ("deepar", "Deepar"), ("nbglm", "Nbglm"), ("stacking", "Stacking")],
)
def test_engine_file_prefix_case_real(engine, expected):
    assert mod._engine_file_prefix(engine) == expected


def test_engine_file_prefix_difiere_del_display_en_deepar_nbglm():
    assert mod._engine_file_prefix("deepar") != mod._ENGINE_CAP["deepar"]
    assert mod._engine_file_prefix("nbglm") != mod._ENGINE_CAP["nbglm"]


# ── Slug fail-closed + longitud + containment estático ──
@pytest.mark.parametrize("bad", ["../evil", "a/b", "a.b", "A", "", "a b", "cafe/../x", "/abs"])
def test_validate_slug_rechaza_inseguros(bad):
    with pytest.raises(mod.SlugError):
        mod._validate_slug(bad)


def test_validate_slug_rechaza_muy_largo():
    with pytest.raises(mod.SlugError):
        mod._validate_slug("a" * 65)


@pytest.mark.parametrize("good", ["obesidad", "dengue", "a1_b2", "x"])
def test_validate_slug_acepta_seguros(good):
    mod._validate_slug(good)


def test_resolve_destination_slug_traversal_raises(tmp_path):
    reg = load_registry_from_text(tmp_path, _YAML_BAD_SLUG)
    with pytest.raises(mod.SlugError):
        mod.resolve_destination(reg.get("Evil"), tmp_path, allow_preliminary=True)


def test_containment_symlink_estatico_rechazado(tmp_path):
    root, external = tmp_path / "repo", tmp_path / "external"
    external.mkdir()
    (root / "reports" / "ProdDetails").mkdir(parents=True)
    (root / "reports" / "ProdDetails" / "_preliminar_NO_GO").symlink_to(
        external, target_is_directory=True
    )
    reg = load_registry_from_text(tmp_path, _YAML_CONFIGURED)
    with pytest.raises(mod.SlugError):
        mod.resolve_destination(reg.get("Cfg"), root, allow_preliminary=True)


# ── Escritura TOCTOU-safe ──
def _raise_os(*_a, **_k):
    raise OSError("boom")


def test_atomic_write_ok_sin_tmp_residuo(tmp_path):
    dest = tmp_path / "sub" / "out.csv"
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    mod._atomic_write_csv(df, dest, root=tmp_path)
    assert list(pd.read_csv(dest).columns) == ["a", "b"]
    assert _tmp_residuos(dest.parent) == []


def test_atomic_write_fallo_preserva_dest_y_limpia_tmp(tmp_path, monkeypatch):
    dest = tmp_path / "out.csv"
    dest.write_text("SENTINEL\n", encoding="utf-8")
    monkeypatch.setattr(mod.os, "replace", _raise_os)
    with pytest.raises(OSError):
        mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest, root=tmp_path)
    assert dest.read_text(encoding="utf-8") == "SENTINEL\n"
    assert _tmp_residuos(tmp_path) == []


def test_atomic_write_toctou_swap_dir_no_escribe_fuera(tmp_path):
    """Swap TOCTOU: el dir aprobado se reemplaza por un symlink externo antes de escribir."""
    root, external = tmp_path / "repo", tmp_path / "external"
    external.mkdir()
    prel = root / "reports" / "ProdDetails" / "_preliminar_NO_GO"
    prel.mkdir(parents=True)
    dest = prel / "produccion_x_PRELIMINAR.csv"
    prel.rmdir()
    prel.symlink_to(external, target_is_directory=True)  # swap post pre-check
    with pytest.raises(OSError):
        mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest, root=root)
    assert list(external.iterdir()) == []  # nada escrito fuera de ROOT


def test_atomic_write_reemplaza_symlink_dest_sin_tocar_victima(tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("NO_TOCAR\n", encoding="utf-8")
    dest = tmp_path / "out.csv"
    dest.symlink_to(victim)
    mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest, root=tmp_path)
    assert not dest.is_symlink()
    assert victim.read_text(encoding="utf-8") == "NO_TOCAR\n"


def test_atomic_write_modo_nuevo_0644(tmp_path):
    dest = tmp_path / "out.csv"
    mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest, root=tmp_path)
    assert _mode(dest) == 0o644  # nuevo: 0644, no el 0600 de mkstemp


def test_atomic_write_preserva_modo_existente(tmp_path):
    dest = tmp_path / "out.csv"
    dest.write_text("old\n", encoding="utf-8")
    dest.chmod(0o644)
    mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest, root=tmp_path)
    assert _mode(dest) == 0o644


def test_atomic_write_fsync_temp_falla_no_publica(tmp_path, monkeypatch):
    dest = tmp_path / "out.csv"
    dest.write_text("SENTINEL\n", encoding="utf-8")
    real_fsync, calls = mod.os.fsync, {"n": 0}

    def fake(fd):
        calls["n"] += 1
        if calls["n"] == 1:  # fsync del temp (antes del replace)
            raise OSError("fsync temp boom")
        return real_fsync(fd)

    monkeypatch.setattr(mod.os, "fsync", fake)
    with pytest.raises(OSError):
        mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest, root=tmp_path)
    assert dest.read_text(encoding="utf-8") == "SENTINEL\n"  # NO publicó
    assert _tmp_residuos(tmp_path) == []


def test_atomic_write_fsync_dir_falla_es_best_effort(tmp_path, monkeypatch):
    dest = tmp_path / "out.csv"
    real_fsync, calls = mod.os.fsync, {"n": 0}

    def fake(fd):
        calls["n"] += 1
        if calls["n"] == 2:  # fsync del dir (después del replace)
            raise OSError("fsync dir boom")
        return real_fsync(fd)

    monkeypatch.setattr(mod.os, "fsync", fake)
    mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest, root=tmp_path)  # NO levanta
    assert dest.exists()  # publicado pese al fallo de fsync(dir)
    assert calls["n"] == 2  # orden: fsync(temp)=1 antes de replace, fsync(dir)=2 después


# ── Lock: 3 procesos, sin split-brain, con terminación en timeout ──
def _locked_incr_worker(root_str: str, iters: int) -> None:
    import scripts.produccion_padecimiento as m

    root = Path(root_str)
    lock, counter = root / "concur.lock", root / "counter.txt"
    for _ in range(iters):
        with m._file_lock(lock):
            v = int(counter.read_text())
            time.sleep(0.002)
            counter.write_text(str(v + 1))


def test_file_lock_tres_procesos_sin_split_brain(tmp_path):
    (tmp_path / "counter.txt").write_text("0", encoding="utf-8")
    ctx = mp.get_context("spawn")  # spawn: seguro con hilos (fork advierte/deadlock) y portable
    iters = 10
    procs = [
        ctx.Process(target=_locked_incr_worker, args=(str(tmp_path), iters)) for _ in range(3)
    ]
    try:
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=60)
        assert all(p.exitcode == 0 for p in procs)
        assert int((tmp_path / "counter.txt").read_text()) == 3 * iters
    finally:
        for p in procs:  # no dejar procesos vivos si algo venció el timeout
            if p.is_alive():
                p.terminate()
                p.join(timeout=10)


# ── E2E ──
def test_e2e_preliminar_escribe_schema_honesto(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_completo(tmp_path, "Prophet", "Obesidad", "prophet")
    _write_completo(tmp_path, "Deepar", "Obesidad", "deepar")  # case real: Deepar_, no DeepAR_

    assert mod.main(["--disease", "Obesidad", "--allow-preliminary"]) == 0

    canonical = tmp_path / "reports" / "ProdDetails" / "produccion_obesidad.csv"
    preliminar = (
        tmp_path
        / "reports"
        / "ProdDetails"
        / "_preliminar_NO_GO"
        / "produccion_obesidad_PRELIMINAR.csv"
    )
    assert not canonical.exists()
    assert preliminar.exists()
    df = pd.read_csv(preliminar)
    assert set(df["criterio_seleccion"]) == {"insample_cv_PRELIMINAR_NO_GO"}
    assert "smape_deepar" in df.columns  # fixture Deepar_ cargado (case fix)
    assert _tmp_residuos(preliminar.parent) == []


_DENGUE_SENTINEL = (
    "padecimiento,entidad,sexo,motor_productivo,criterio_seleccion,smape_ganador\n"
    "Dengue,Nacional,general,DeepAR,legacy_dengue_2026,12.3\n"
)


def _seed_dengue_sentinel(root: Path) -> Path:
    p = root / "reports" / "ProdDetails" / "produccion_dengue.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_DENGUE_SENTINEL, encoding="utf-8")
    return p


@pytest.mark.parametrize(
    "argv", [["--disease", "Dengue"], ["--disease", "Dengue", "--allow-preliminary"]]
)
def test_e2e_dengue_gated_preserva_sentinel(tmp_path, monkeypatch, argv):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    sentinel = _seed_dengue_sentinel(tmp_path)
    before_sha, before_bytes = _sha256(sentinel), sentinel.read_bytes()
    _write_completo(tmp_path, "Prophet", "Dengue", "prophet")

    assert mod.main(argv) == 2
    assert _sha256(sentinel) == before_sha
    assert sentinel.read_bytes() == before_bytes
