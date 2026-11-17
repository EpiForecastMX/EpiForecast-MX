"""Pruebas unitarias sintéticas de O1 y O2 en ``a51_history_io_guards``."""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import pytest
from scripts import paso_semanal
from scripts.piloto_carbon_alta1 import a51_history_io_guards as io_guards
from scripts.piloto_carbon_alta1 import add_a51_history_base as ahb
from scripts.piloto_carbon_alta1.a51_history_projection import BaseHistoryBuildError

from epiforecast import registry
from epiforecast.data.epi_calendar import shift as semana_siguiente
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.publication.contratos_datos import ContratoCobertura

pytestmark = pytest.mark.unit


def _old_85_names() -> list[str]:
    names = [
        d.data_name
        for d in registry.get_registry().diseases
        if d.lifecycle == "published" and d.id != "sifilis_adquirida_a51"
    ]
    assert len(names) == 85
    return names


def _csv_bytes(rows: list[list[object]], *, include_header: bool = True) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    if include_header:
        writer.writerow(paso_semanal.CONSOLIDADO_COLS.split(","))
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _install_fsync_link_spies(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    events: list[str] = []
    real_fsync = os.fsync
    real_link = os.link

    def _spy_fsync(fd: int) -> None:
        events.append("fsync")
        real_fsync(fd)

    def _spy_link(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        events.append("link")
        real_link(src, dst)

    monkeypatch.setattr(os, "fsync", _spy_fsync)
    monkeypatch.setattr(os, "link", _spy_link)
    return events


def _build_small_candidate_fixture(tmp_path: Path) -> tuple[bytes, dict[str, Any]]:
    contrato_86 = dataclasses.replace(
        ContratoCobertura.canonico(),
        entidades=("aguascalientes", "zacatecas"),
        alias={},
        profundidad_minima=2,
    )
    ents = ("Aguascalientes", "Zacatecas")
    periods = ((2026, 42), (2026, 43))
    base_rows: list[list[object]] = [
        [anio, sem, ent, pad_name, "1", "2", "3", "4"]
        for pad_name in _old_85_names()
        for anio, sem in periods
        for ent in ents
    ]
    base_bytes = _csv_bytes(base_rows)
    base_csv = tmp_path / "base_85_small.csv"
    base_csv.write_bytes(base_bytes)

    raw_rows: list[list[object]] = [
        [anio, sem, ent, "Sífilis adquirida", "3", "12", "10", "18"]
        for anio, sem in (*periods, (2026, 44))
        for ent in ents
    ]
    raw_csv = tmp_path / "raw_a51_small.csv"
    raw_csv.write_bytes(_csv_bytes(raw_rows))

    a51_included = [r for r in raw_rows if (int(str(r[0])), int(str(r[1]))) <= (2026, 43)]
    expected_out = base_bytes + _csv_bytes(a51_included, include_header=False)
    kwargs: dict[str, Any] = {
        "expected_out_bytes": expected_out,
        "expected_out_sha": io_guards.sha256_bytes(expected_out),
        "base_csv": base_csv,
        "base_bytes": base_bytes,
        "exp_base_sha": io_guards.sha256_bytes(base_bytes),
        "raw_a51_csv": raw_csv,
        "contrato_86": contrato_86,
        "cutoff": (2026, 43),
    }
    return expected_out, kwargs


def test_o1_cli_mismo_report_created_pasa_en_noop_sin_modificar_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = Path(registry.__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root)
    catalog = load_geo_catalog()
    entidades = [catalog.entity(cve).nombre_canonico for cve in sorted(catalog.cve_ents())]

    periods_52: list[tuple[int, int]] = [(2025, 45)]
    while periods_52[-1] != (2026, 43):
        periods_52.append(semana_siguiente(periods_52[-1][0], periods_52[-1][1], 1))
    assert len(periods_52) == 52

    base_bytes = _csv_bytes(
        [
            [anio, sem, ent, pad_name, "1", "2", "3", "4"]
            for pad_name in _old_85_names()
            for anio, sem in periods_52
            for ent in entidades
        ]
    )
    base_csv = tmp_path / "base_85.csv"
    base_csv.write_bytes(base_bytes)

    raw_bytes = _csv_bytes(
        [
            [anio, f"{sem:02d}", ent, "Sífilis adquirida", "2", "8.0", "6.0", "9"]
            for anio, sem in (*periods_52, (2026, 44))
            for ent in entidades
        ]
    )
    raw_csv = tmp_path / "raw_a51.csv"
    raw_csv.write_bytes(raw_bytes)

    out_csv = tmp_path / "out" / "base_86.csv"
    rep_json = tmp_path / "out" / "report.json"
    cli_args = [
        f"--base-csv={base_csv}",
        f"--expected-base-sha256={io_guards.sha256_bytes(base_bytes)}",
        f"--raw-a51-csv={raw_csv}",
        f"--expected-raw-sha256={io_guards.sha256_bytes(raw_bytes)}",
        "--cutoff-year=2026",
        "--cutoff-week=43",
        f"--out-csv={out_csv}",
        f"--report-json={rep_json}",
    ]

    assert ahb.main(cli_args) == 0
    orig_rep_bytes = rep_json.read_bytes()
    orig_rep_ino = rep_json.stat().st_ino
    assert json.loads(orig_rep_bytes)["status"] == "CREATED_VERIFIED"

    assert ahb.main(cli_args) == 0
    assert rep_json.read_bytes() == orig_rep_bytes
    assert rep_json.stat().st_ino == orig_rep_ino


def test_o1_noop_rechaza_reporte_otro_sha_rancio_malformado_duplicado_o_symlink(
    tmp_path: Path,
) -> None:
    rep_ok = tmp_path / "rep_created.json"
    common: dict[str, Any] = {
        "data_name": "Sífilis adquirida",
        "base_csv": tmp_path / "base.csv",
        "exp_base_sha": "a" * 64,
        "base_bytes_len": 100,
        "raw_a51_csv": tmp_path / "raw.csv",
        "exp_raw_sha": "b" * 64,
        "out_csv": tmp_path / "out.csv",
        "expected_out_sha": "c" * 64,
        "out_bytes_len": 150,
        "old85_info": {"old_published_verified": 85},
        "new86_info": {"new_published_verified": 86},
        "exclusions_info": {"lag_applied_in_consolidado": False},
        "a51_summary": {"rows_added": 64},
    }
    io_guards.emit_history_report(noop=False, report_json=rep_ok, **common)
    created_bytes = rep_ok.read_bytes()

    res_noop = io_guards.emit_history_report(noop=True, report_json=rep_ok, **common)
    assert res_noop["status"] == "NOOP_IDENTICAL" and res_noop["noop_identical"] is True
    assert rep_ok.read_bytes() == created_bytes

    base_obj = json.loads(created_bytes.decode("utf-8"))
    bad_payloads = [
        json.dumps({**base_obj, "out_sha256": "d" * 64}).encode("utf-8"),
        json.dumps({**base_obj, "base_sha256": "e" * 64}).encode("utf-8"),
        json.dumps({**base_obj, "a51_history": {"rows_added": 32}}).encode("utf-8"),
        json.dumps({**base_obj, "status": "FAILED"}).encode("utf-8"),
        json.dumps({**base_obj, "noop_identical": "false"}).encode("utf-8"),
        json.dumps({**base_obj, "prefix_byte_identical": 1}).encode("utf-8"),
        json.dumps({**base_obj, "extra": 1}).encode("utf-8"),
        b'{"schema": "x", "schema": "y"}',
        b"{malformed_json",
    ]
    for idx, bad_bytes in enumerate(bad_payloads):
        bad_path = tmp_path / f"bad_{idx}.json"
        bad_path.write_bytes(bad_bytes)
        with pytest.raises(BaseHistoryBuildError):
            io_guards.emit_history_report(noop=True, report_json=bad_path, **common)
        assert bad_path.read_bytes() == bad_bytes

    sym_path = tmp_path / "rep_symlink.json"
    sym_path.symlink_to(rep_ok)
    with pytest.raises(BaseHistoryBuildError, match="symlink"):
        io_guards.emit_history_report(noop=True, report_json=sym_path, **common)
    assert sym_path.is_symlink() and rep_ok.read_bytes() == created_bytes


def test_o2_write_exclusive_or_noop_preserva_temporal_preplantado_fsync_y_noclobber(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = tmp_path / "sub" / "report.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    foreign_tmp = dest.with_name(f".{dest.name}.tmp.{os.getpid()}")
    foreign_bytes = b"foreign_temp_must_survive\n"
    foreign_tmp.write_bytes(foreign_bytes)

    events = _install_fsync_link_spies(monkeypatch)
    assert io_guards.write_exclusive_or_noop(dest, b"ok_payload\n", "report_json") is False
    assert dest.read_bytes() == b"ok_payload\n"
    assert foreign_tmp.read_bytes() == foreign_bytes
    assert events == ["fsync", "link"]

    with pytest.raises(BaseHistoryBuildError, match="contenido distinto"):
        io_guards.write_exclusive_or_noop(dest, b"different_payload\n", "report_json")
    assert dest.read_bytes() == b"ok_payload\n" and foreign_tmp.read_bytes() == foreign_bytes

    dest_race = tmp_path / "sub" / "race.json"
    foreign_race = dest_race.with_name(f".{dest_race.name}.tmp.{os.getpid()}")
    foreign_race.write_bytes(foreign_bytes)
    real_link = os.link

    def _racing_link(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        Path(dst).write_bytes(b"winner_bytes\n")
        real_link(src, dst)

    monkeypatch.setattr(os, "link", _racing_link)
    with pytest.raises(BaseHistoryBuildError, match="apareció concurrentemente"):
        io_guards.write_exclusive_or_noop(dest_race, b"loser_bytes\n", "report_json")
    assert dest_race.read_bytes() == b"winner_bytes\n"
    assert foreign_race.read_bytes() == foreign_bytes
    leftover = [p.name for p in dest_race.parent.iterdir() if p.name.startswith(".race.json.tmp.")]
    assert leftover == [foreign_race.name]

    def _fail_mkstemp(**_kw: Any) -> tuple[int, str]:
        raise FileExistsError("exhausted")

    monkeypatch.setattr(tempfile, "mkstemp", _fail_mkstemp)
    with pytest.raises(BaseHistoryBuildError, match="temporal exclusivo"):
        io_guards.write_exclusive_or_noop(tmp_path / "sub" / "mkfail.json", b"x\n", "report_json")
    assert foreign_race.read_bytes() == foreign_bytes


def test_o2_materialize_or_verify_out_csv_preserva_temporal_preplantado_fsync_y_noclobber(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_out, common_mat = _build_small_candidate_fixture(tmp_path)
    out_csv = tmp_path / "out_dir" / "base_86_small.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    foreign_tmp = out_csv.with_name(f".{out_csv.name}.tmp.{os.getpid()}")
    foreign_bytes = b"foreign_csv_temp_must_survive\n"
    foreign_tmp.write_bytes(foreign_bytes)

    events = _install_fsync_link_spies(monkeypatch)
    noop, info = io_guards.materialize_or_verify_out_csv(out_csv=out_csv, **common_mat)
    assert noop is False and info["new_published_verified"] == 86
    assert out_csv.read_bytes() == expected_out
    assert foreign_tmp.read_bytes() == foreign_bytes
    assert events == ["fsync", "link"]

    race_csv = tmp_path / "out_dir" / "race_86.csv"
    foreign_race = race_csv.with_name(f".{race_csv.name}.tmp.{os.getpid()}")
    foreign_race.write_bytes(foreign_bytes)
    real_link = os.link

    def _racing_csv_link(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        Path(dst).write_bytes(b"unique_do_not_touch\n")
        real_link(src, dst)

    monkeypatch.setattr(os, "link", _racing_csv_link)
    with pytest.raises(BaseHistoryBuildError, match="apareció concurrentemente"):
        io_guards.materialize_or_verify_out_csv(out_csv=race_csv, **common_mat)
    assert race_csv.read_bytes() == b"unique_do_not_touch\n"
    assert foreign_race.read_bytes() == foreign_bytes
