"""Paso semanal único del runner: lista desde el registry, filas de la semana y consolidado fail-closed."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import paso_semanal as ps

from epiforecast import registry

pytestmark = pytest.mark.unit

_CAB_SEXO = (
    "Anio,Semana,Entidad,Padecimiento,Casos_semana,Acumulado_hombres,Acumulado_mujeres,"
    "Acumulado_anio_anterior\n"
)
_CAB_TOTAL = (
    "Anio,Semana,Entidad,Padecimiento,Casos_semana,Acumulado_total,Acumulado_anio_anterior\n"
)


def test_la_lista_sale_del_registry_y_no_de_una_lista_escrita():
    assert ps.publicados() == [d.id for d in registry.release_published()]
    assert "obesidad" in ps.publicados() and "depresion" not in ps.publicados()


def test_filas_de_semana_respeta_comas_y_proyecta_el_raw_sin_sexo(tmp_path: Path):
    con = tmp_path / "con.csv"
    con.write_text(
        _CAB_SEXO
        + '2026,42,Jalisco,"Tumor maligno de tráquea, bronquios y pulmón",3,10,12,20\n'
        + '2026,41,Jalisco,"Tumor maligno de tráquea, bronquios y pulmón",2,9,10,19\n',
        encoding="utf-8",
    )
    assert ps.filas_de_semana(con, 2026, 42) == [
        '2026,42,Jalisco,"Tumor maligno de tráquea, bronquios y pulmón",3,10,12,20'
    ]
    sin = tmp_path / "sin.csv"
    sin.write_text(
        _CAB_TOTAL + "2026,42,Sonora,Tumor maligno del ovario,1,40,38\n", encoding="utf-8"
    )
    assert ps.filas_de_semana(sin, 2026, 42) == ["2026,42,Sonora,Tumor maligno del ovario,1,,,38"]


def _escenario(tmp_path: Path, monkeypatch, filas: int) -> dict[str, Path]:
    root = tmp_path / "be"
    raw = root / "artifacts" / "observations" / "x_c00" / "obs1" / "inputs" / "data_raw_X.csv"
    raw.parent.mkdir(parents=True)
    raw.write_text(
        _CAB_TOTAL + "".join(f"2026,43,E{i},X,1,5,4\n" for i in range(filas)), encoding="utf-8"
    )
    monkeypatch.setattr(ps, "publicados", lambda: ["x_c00"])
    monkeypatch.setattr(ps, "observacion_actual", lambda d, r=None: "obs1")
    vistos: dict[str, Path] = {}

    def revisa(out, c, pads):
        vistos["out"] = out
        return SimpleNamespace(pasa=True, problemas=(), cifras={"cortes": {"x": (2026, 43)}})

    import epiforecast.publication.contratos_datos as cd

    monkeypatch.setattr(cd, "revisa_consolidado", revisa)
    monkeypatch.setattr(
        cd.ContratoCobertura,
        "canonico",
        classmethod(lambda cls: SimpleNamespace(padecimientos=())),
    )
    base = tmp_path / "base.csv"
    base.write_text(_CAB_SEXO + "2026,42,A,Depresión,1,1,1,1\n", encoding="utf-8")
    leg_base = tmp_path / "leg_base.csv"
    leg_base.write_text(_CAB_SEXO + "2026,42,A,Depresión,1,1,1,1\n", encoding="utf-8")
    leg_cand = tmp_path / "leg_cand.csv"
    leg_cand.write_text(
        leg_base.read_text(encoding="utf-8") + "2026,43,A,Depresión,2,2,2,2\n", encoding="utf-8"
    )
    return {
        "root": root,
        "base": base,
        "leg_base": leg_base,
        "leg_cand": leg_cand,
        "out": tmp_path / "out.csv",
    }


def test_consolida_solo_anade_y_conserva_la_base(tmp_path: Path, monkeypatch):
    e = _escenario(tmp_path, monkeypatch, 32)
    rc = ps.consolida(43, 2026, e["base"], e["leg_base"], e["leg_cand"], e["out"], e["root"])
    assert rc == 0
    texto = e["out"].read_text(encoding="utf-8")
    assert texto.startswith(e["base"].read_text(encoding="utf-8"))
    assert "2026,43,A,Depresión,2,2,2,2\n" in texto
    assert texto.count(",X,1,,,4\n") == 32


def test_consolida_falla_cerrado_sin_las_32_entidades(tmp_path: Path, monkeypatch):
    e = _escenario(tmp_path, monkeypatch, 31)
    assert (
        ps.consolida(43, 2026, e["base"], e["leg_base"], e["leg_cand"], e["out"], e["root"]) == 2
    )


def test_consolida_falla_si_el_legacy_reescribe_su_base(tmp_path: Path, monkeypatch):
    e = _escenario(tmp_path, monkeypatch, 32)
    e["leg_cand"].write_text(_CAB_SEXO + "2026,42,A,Depresión,9,9,9,9\n", encoding="utf-8")
    assert (
        ps.consolida(43, 2026, e["base"], e["leg_base"], e["leg_cand"], e["out"], e["root"]) == 2
    )


def test_el_reporte_se_lee_aunque_el_estado_imprima_texto_antes():
    texto = (
        "✔ x: Validación prospectiva en curso (1/4 semanas)\n  estado:     ruta\n"
        '{"disease_id":"x","verdict":"INCOMPLETE","weeks_available":1,"weeks_required":4}'
    )
    rep = ps.reporte_de(texto)
    assert rep is not None and rep["verdict"] == "INCOMPLETE" and rep["weeks_available"] == 1
    assert ps.reporte_de("sin json") is None


def _corre_observa(tmp_path, monkeypatch, rcs: dict[str, int]) -> tuple[int, list[str]]:
    corridos: list[str] = []
    monkeypatch.setattr(ps, "publicados", lambda: list(rcs))

    def run(cmd, **kw):
        d = cmd[cmd.index("--disease") + 1]
        corridos.append(d)
        out = (
            f'texto\n{{"verdict":"{"FAIL" if rcs[d] == 3 else "INCOMPLETE"}","weeks_available":1}}'
        )
        return SimpleNamespace(returncode=rcs[d], stdout=out, stderr="")

    monkeypatch.setattr(ps.subprocess, "run", run)
    rc = ps.observa(
        Path("b.pdf"), write=True, first_available=None, runs_root=None, salida=tmp_path / "s"
    )
    return rc, corridos


def test_un_fail_no_deja_observaciones_pendientes(tmp_path: Path, monkeypatch):
    rc, corridos = _corre_observa(tmp_path, monkeypatch, {"a": 0, "b": 3, "c": 0})
    assert corridos == ["a", "b", "c"] and rc == ps.RC_FAIL


def test_un_error_que_no_es_fail_si_detiene_el_registro(tmp_path: Path, monkeypatch):
    rc, corridos = _corre_observa(tmp_path, monkeypatch, {"a": 0, "b": 2, "c": 0})
    assert corridos == ["a", "b"] and rc == 2
