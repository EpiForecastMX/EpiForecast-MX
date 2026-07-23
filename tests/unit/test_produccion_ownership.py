"""Fase 1 P0 — ownership/policy + slug + escritura TOCTOU-safe + E2E del selector genérico.

Contrato: el genérico solo escribe un CANÓNICO vía ADAPTER CALLABLE (selección validada
contextualmente ANTES de publicar) y un PRELIMINAR honesto para no publicados. Escritura anclada
a ROOT con openat/O_NOFOLLOW (segura ante swaps por symlink), tmp exclusivo, fsync, modo 0644
preservado, lock estable con cierre garantizado.
"""

from __future__ import annotations

import contextlib
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
    "entidad_vacia": lambda: _adapter_bad({"entidad": [""]}),
    "sexo_whitespace": lambda: _adapter_bad({"sexo": ["   "]}),
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


# ── Componentes relativos y destinos fuera de ROOT ──
def test_atomic_write_rechaza_dotdot_no_escapa(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    dest = root / "sub" / ".." / ".." / "escape.csv"  # textual: relative_to(root) NO normaliza
    with pytest.raises(mod.SlugError):
        mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest, root=root)
    assert not (tmp_path / "escape.csv").exists()  # nada fuera de ROOT


def test_atomic_write_rechaza_destino_fuera_de_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(mod.SlugError):
        mod._atomic_write_csv(pd.DataFrame({"a": [1]}), tmp_path / "fuera.csv", root=root)
    assert not (tmp_path / "fuera.csv").exists()


# ── Round-trip por VALORES (no solo forma) ──
def test_roundtrip_detecta_string_vacio_que_muta_a_nan(tmp_path):
    """entidad="" se relee como NaN: el round-trip por valores lo detecta y NO publica."""
    dest = tmp_path / "out.csv"
    dest.write_text("SENTINEL\n", encoding="utf-8")
    df = pd.DataFrame(
        {
            "padecimiento": ["X"],
            "entidad": [""],  # sobrevive isna() pero muta a NaN en CSV
            "sexo": ["general"],
            "motor_productivo": ["Prophet"],
            "criterio_seleccion": ["c"],
        }
    )
    with pytest.raises(OSError):
        mod._atomic_write_csv(df, dest, root=tmp_path)
    assert dest.read_text(encoding="utf-8") == "SENTINEL\n"  # preservado
    assert _tmp_residuos(tmp_path) == []


# ── Invariante post-commit: un éxito jamás se reporta como fallo ──
def test_close_falla_post_commit_no_convierte_publicacion_en_error(tmp_path, monkeypatch):
    """os.close que falla (pero cierra) en el teardown: la publicación NO se reporta como error."""
    real_close = mod.os.close

    def close_then_raise(fd):
        real_close(fd)  # cierra de verdad (no filtra fds)
        raise OSError("close boom")

    monkeypatch.setattr(mod.os, "close", close_then_raise)
    dest = tmp_path / "out.csv"
    mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest, root=tmp_path)  # NO levanta
    monkeypatch.setattr(mod.os, "close", real_close)
    assert pd.read_csv(dest)["a"].tolist() == [1]


def test_unlock_falla_post_commit_no_convierte_publicacion_en_error(tmp_path, monkeypatch):
    real_flock = mod.fcntl.flock

    def flock_unlock_boom(fd, op):
        if op == mod.fcntl.LOCK_UN:
            raise OSError("unlock boom")
        return real_flock(fd, op)

    monkeypatch.setattr(mod.fcntl, "flock", flock_unlock_boom)
    dest = tmp_path / "out.csv"
    mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest, root=tmp_path)  # NO levanta
    assert dest.exists()


def test_main_rc0_aunque_teardown_falle(tmp_path, monkeypatch):
    """main jamás dice 'no publicado' (rc=4) cuando el replace SÍ ocurrió."""
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_completo(tmp_path, "Prophet", "Obesidad", "prophet")
    real_close = mod.os.close

    def close_then_raise(fd):
        real_close(fd)
        raise OSError("close boom")

    monkeypatch.setattr(mod.os, "close", close_then_raise)
    rc = mod.main(["--disease", "Obesidad", "--allow-preliminary"])
    monkeypatch.setattr(mod.os, "close", real_close)
    assert rc == 0
    preliminar = (
        tmp_path
        / "reports"
        / "ProdDetails"
        / "_preliminar_NO_GO"
        / "produccion_obesidad_PRELIMINAR.csv"
    )
    assert preliminar.exists()  # publicado y reportado como éxito


def test_signal_post_commit_no_propaga(tmp_path, monkeypatch):
    """KeyboardInterrupt durante el fsync(dir) POST-commit: no propaga; el commit queda."""
    real_fsync, calls = mod.os.fsync, {"n": 0}

    def fake(fd):
        calls["n"] += 1
        if calls["n"] == 2:  # fsync(dir), después del replace
            raise KeyboardInterrupt
        return real_fsync(fd)

    monkeypatch.setattr(mod.os, "fsync", fake)
    dest = tmp_path / "out.csv"
    mod._atomic_write_csv(pd.DataFrame({"a": [1]}), dest, root=tmp_path)  # NO propaga la señal
    assert dest.exists()  # commit consumado


def test_main_rc0_aunque_teardown_reciba_senal(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_completo(tmp_path, "Prophet", "Obesidad", "prophet")
    real_fsync, calls = mod.os.fsync, {"n": 0}

    def fake(fd):
        calls["n"] += 1
        if calls["n"] == 2:
            raise KeyboardInterrupt
        return real_fsync(fd)

    monkeypatch.setattr(mod.os, "fsync", fake)
    assert mod.main(["--disease", "Obesidad", "--allow-preliminary"]) == 0
    preliminar = (
        tmp_path
        / "reports"
        / "ProdDetails"
        / "_preliminar_NO_GO"
        / "produccion_obesidad_PRELIMINAR.csv"
    )
    assert preliminar.exists()


# ── Round-trip: coerción de tipos en columnas requeridas ──
@pytest.mark.parametrize("val", ["True", "False", "1", "1.5", "inf", "nan"])
def test_roundtrip_rechaza_coercion_de_columna_requerida(tmp_path, val):
    """entidad='True'/'1'/'inf' pasa la validación (string no vacío) pero un consumidor por
    defecto la relee como bool/int/float: el round-trip lo detecta y NO publica."""
    dest = tmp_path / "out.csv"
    dest.write_text("SENTINEL\n", encoding="utf-8")
    df = pd.DataFrame(
        {
            "padecimiento": ["X"],
            "entidad": [val],
            "sexo": ["general"],
            "motor_productivo": ["Prophet"],
            "criterio_seleccion": ["c"],
        }
    )
    with pytest.raises(OSError):
        mod._atomic_write_csv(df, dest, root=tmp_path)
    assert dest.read_text(encoding="utf-8") == "SENTINEL\n"  # NO publicó basura coercible
    assert _tmp_residuos(tmp_path) == []


def test_roundtrip_acepta_nombres_reales_de_geografia(tmp_path):
    """Los valores reales del pipeline (nombres de estado + floats) NO se coercionan: publica bien."""
    dest = tmp_path / "out.csv"
    df = pd.DataFrame(
        {
            "padecimiento": ["Obesidad", "Obesidad"],
            "entidad": ["Nuevo León", "Nacional"],
            "sexo": ["general", "hombres"],
            "motor_productivo": ["Prophet", "Ensemble"],
            "criterio_seleccion": ["insample_cv_PRELIMINAR_NO_GO", "insample_cv_PRELIMINAR_NO_GO"],
            "motores_evaluados": ["deepar,prophet", "deepar,prophet"],
            "smape_prophet": [10.0, 9.9],
            "mase_prophet": [0.5, None],  # NaN legítimo en no-requerida
        }
    )
    mod._atomic_write_csv(df, dest, root=tmp_path)  # publica sin falso positivo del round-trip
    assert pd.read_csv(dest)["entidad"].tolist() == ["Nuevo León", "Nacional"]


@pytest.mark.parametrize("val", ["007", "1e5", "inf", "True"])
def test_roundtrip_rechaza_coercion_en_columna_no_requerida(tmp_path, val):
    """Un string de forma numérica/bool en una columna NO requerida (motores_evaluados) también
    se coerciona para un consumidor por defecto: se detecta y NO publica."""
    dest = tmp_path / "out.csv"
    dest.write_text("SENTINEL\n", encoding="utf-8")
    df = pd.DataFrame(
        {
            "padecimiento": ["X"],
            "entidad": ["Nacional"],
            "sexo": ["general"],
            "motor_productivo": ["Prophet"],
            "criterio_seleccion": ["c"],
            "motores_evaluados": [val],
        }
    )
    with pytest.raises(OSError):
        mod._atomic_write_csv(df, dest, root=tmp_path)
    assert dest.read_text(encoding="utf-8") == "SENTINEL\n"
    assert _tmp_residuos(tmp_path) == []


# ── TOCTOU post-lock + filenames reservados ──
def test_assert_fd_contained_detecta_dir_movido_fuera(tmp_path):
    """El dir ABIERTO se renombra fuera de ROOT (sin symlink): la re-validación por inodo aborta."""
    root = tmp_path / "repo"
    prel = root / "reports" / "ProdDetails" / "_preliminar_NO_GO"
    prel.mkdir(parents=True)
    parts = ("reports", "ProdDetails", "_preliminar_NO_GO")
    fds = mod._open_dir_chain(root, parts)
    try:
        (tmp_path / "outside").mkdir()
        prel.rename(tmp_path / "outside" / "gone")  # mueve el inodo abierto fuera de ROOT
        with pytest.raises(mod.SlugError):
            mod._assert_fd_still_contained(root, parts, fds[-1])
    finally:
        for fd in reversed(fds):
            with contextlib.suppress(OSError):
                mod.os.close(fd)


def test_assert_fd_contained_ok_dir_intacto(tmp_path):
    root = tmp_path / "repo"
    (root / "reports" / "ProdDetails").mkdir(parents=True)
    parts = ("reports", "ProdDetails")
    fds = mod._open_dir_chain(root, parts)
    try:
        mod._assert_fd_still_contained(root, parts, fds[-1])  # mismo inodo → no levanta
    finally:
        for fd in reversed(fds):
            with contextlib.suppress(OSError):
                mod.os.close(fd)


@pytest.mark.parametrize("bad", ["x.lock", ".hidden", "x.tmp", "produccion_x.csv.lock"])
def test_atomic_write_rechaza_filename_reservado(tmp_path, bad):
    with pytest.raises(mod.SlugError):
        mod._atomic_write_csv(pd.DataFrame({"a": [1]}), tmp_path / bad, root=tmp_path)


def test_escape_post_replace_detectado_limpiado_y_fallado(tmp_path, monkeypatch):
    """El dir se mueve fuera de ROOT en la ventana justo-antes-del-replace: el post-check detecta
    el escape, LIMPIA el archivo escapado y FALLA (no lo reporta como éxito)."""
    root, external = tmp_path / "repo", tmp_path / "external"
    external.mkdir()
    prel = root / "reports" / "ProdDetails" / "_preliminar_NO_GO"
    prel.mkdir(parents=True)
    dest = prel / "produccion_x_PRELIMINAR.csv"
    real_replace = mod.os.replace

    def replace_after_move(src, dst, *, src_dir_fd, dst_dir_fd):
        prel.rename(external / "moved")  # atacante: mueve el dir ABIERTO fuera de ROOT
        return real_replace(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)

    monkeypatch.setattr(mod.os, "replace", replace_after_move)
    df = pd.DataFrame(
        {
            "padecimiento": ["X"],
            "entidad": ["Nacional"],
            "sexo": ["g"],
            "motor_productivo": ["Prophet"],
            "criterio_seleccion": ["c"],
        }
    )
    with pytest.raises(mod.SlugError):
        mod._atomic_write_csv(df, dest, root=root)
    # El archivo escapó momentáneamente pero fue LIMPIADO por la detección post-replace.
    assert not (external / "moved" / "produccion_x_PRELIMINAR.csv").exists()


def test_deferred_signals_enmascara_y_restaura():
    import signal as _sig

    before = _sig.pthread_sigmask(_sig.SIG_BLOCK, set())
    with mod._deferred_signals():
        masked = _sig.pthread_sigmask(_sig.SIG_BLOCK, set())
        assert _sig.SIGINT in masked and _sig.SIGTERM in masked
    assert _sig.pthread_sigmask(_sig.SIG_BLOCK, set()) == before  # restaurado


# ── Lock REAL del writer: exclusión mutua + carrera de mkdir, multi-proceso ──
def _locked_counter_worker(root_str: str, iters: int) -> None:
    """Ejercita _locked_lockfile — la ÚNICA implementación de lock, la que usa el writer."""
    import os as _os

    import scripts.produccion_padecimiento as m

    root = Path(root_str)
    parent_fd = _os.open(str(root), _os.O_RDONLY | _os.O_DIRECTORY)
    try:
        counter = root / "counter.txt"
        for _ in range(iters):
            with m._locked_lockfile(parent_fd, ".concur.lock"):
                v = int(counter.read_text())
                time.sleep(0.002)
                counter.write_text(str(v + 1))
    finally:
        _os.close(parent_fd)


def _concurrent_writer(root_str: str, idx: int) -> None:
    """Writer completo (_atomic_write_csv) al MISMO destino en un dir anidado NUEVO:
    ejercita a la vez la carrera de mkdir y el lock real de producción."""
    import pandas as _pd
    import scripts.produccion_padecimiento as m

    root = Path(root_str)
    dest = root / "reports" / "ProdDetails" / "carrera_nueva" / "out.csv"
    m._atomic_write_csv(_pd.DataFrame({"a": [idx]}), dest, root=root)


def _join_or_kill(procs) -> None:
    """join con timeout; termina (y si hace falta mata) procesos vivos — nunca quedan colgados."""
    try:
        for p in procs:
            p.join(timeout=60)
    finally:
        for p in procs:
            if p.is_alive():
                p.terminate()
                p.join(timeout=10)
            if p.is_alive():
                p.kill()
                p.join(timeout=10)


def test_locked_lockfile_tres_procesos_sin_split_brain(tmp_path):
    (tmp_path / "counter.txt").write_text("0", encoding="utf-8")
    ctx = mp.get_context("spawn")  # spawn: seguro con hilos (fork advierte/deadlock) y portable
    iters = 10
    procs = [
        ctx.Process(target=_locked_counter_worker, args=(str(tmp_path), iters)) for _ in range(3)
    ]
    for p in procs:
        p.start()
    _join_or_kill(procs)
    assert all(p.exitcode == 0 for p in procs)
    assert int((tmp_path / "counter.txt").read_text()) == 3 * iters  # sin lost updates


def test_doce_writers_concurrentes_mkdir_y_lock_reales(tmp_path):
    """12 procesos por _atomic_write_csv al MISMO destino en un dir anidado inexistente:
    la carrera de mkdir se tolera (EEXIST idempotente) y todos publican sin error."""
    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=_concurrent_writer, args=(str(tmp_path), i)) for i in range(12)]
    for p in procs:
        p.start()
    _join_or_kill(procs)
    assert [p.exitcode for p in procs] == [0] * 12  # ni un FileExistsError
    dest = tmp_path / "reports" / "ProdDetails" / "carrera_nueva" / "out.csv"
    df = pd.read_csv(dest)
    assert list(df.columns) == ["a"] and len(df) == 1 and 0 <= int(df["a"].iloc[0]) < 12
    assert _tmp_residuos(dest.parent) == []


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
