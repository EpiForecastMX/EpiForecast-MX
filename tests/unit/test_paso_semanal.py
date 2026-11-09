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


def _con_historia(e: dict[str, Path], base_x: str) -> None:
    """El raw vigente de X trae W42 y W43; la base trae W42 de X como se indique."""
    raw = next((e["root"] / "artifacts").rglob("data_raw_X.csv"))
    raw.write_text(
        raw.read_text(encoding="utf-8") + "".join(f"2026,42,E{i},X,2,5,4\n" for i in range(32)),
        encoding="utf-8",
    )
    e["base"].write_text(e["base"].read_text(encoding="utf-8") + base_x, encoding="utf-8")


def test_consolida_acepta_la_base_vigente_aunque_cambie_el_formato(tmp_path: Path, monkeypatch):
    e = _escenario(tmp_path, monkeypatch, 32)
    _con_historia(e, "".join(f"2026,42,E{i},X,2.0,,,4.0\n" for i in range(32)))
    assert (
        ps.consolida(43, 2026, e["base"], e["leg_base"], e["leg_cand"], e["out"], e["root"]) == 0
    )


def test_consolida_rechaza_una_base_sustituida(tmp_path: Path, monkeypatch, capsys):
    """Auditoría 9-nov-2026, R1: una base anterior a una corrección no se hereda en silencio."""
    e = _escenario(tmp_path, monkeypatch, 32)
    vieja = "".join(f"2026,42,E{i},X,{1 if i == 7 else 2},,,4\n" for i in range(32))
    _con_historia(e, vieja)
    assert (
        ps.consolida(43, 2026, e["base"], e["leg_base"], e["leg_cand"], e["out"], e["root"]) == 2
    )
    assert "2026-W42" in capsys.readouterr().err and not e["out"].exists()


def test_consolida_rechaza_una_base_a_la_que_le_falta_historia(tmp_path: Path, monkeypatch):
    e = _escenario(tmp_path, monkeypatch, 32)
    _con_historia(e, "".join(f"2026,42,E{i},X,2,,,4\n" for i in range(31)))
    assert (
        ps.consolida(43, 2026, e["base"], e["leg_base"], e["leg_cand"], e["out"], e["root"]) == 2
    )


def test_tras_un_fail_en_seco_se_registra_a_todos_y_se_consolida_sin_el_retirado(
    tmp_path: Path, monkeypatch
):
    """Auditoría 9-nov-2026, R2: la ruta literal seco (FAIL) → registro → retiro → consolidado."""
    rcs = {"a": 0, "b": 3, "c": 0}
    llamadas: list[tuple[str, bool]] = []
    monkeypatch.setattr(ps, "publicados", lambda: list(rcs))

    def run(cmd, **kw):
        d = cmd[cmd.index("--disease") + 1]
        llamadas.append((d, "--write" in cmd))
        veredicto = "FAIL" if rcs[d] == 3 else "PASS"
        return SimpleNamespace(returncode=rcs[d], stdout=f'{{"verdict":"{veredicto}"}}', stderr="")

    monkeypatch.setattr(ps.subprocess, "run", run)
    kw = {"first_available": None, "runs_root": None}
    assert ps.observa(Path("b.pdf"), write=False, salida=tmp_path / "seco", **kw) == ps.RC_FAIL
    # La guía: con un FAIL en seco se registra igual a todos; el FAIL queda como evidencia.
    assert ps.observa(Path("b.pdf"), write=True, salida=tmp_path / "reg", **kw) == ps.RC_FAIL
    assert [d for d, w in llamadas if w] == ["a", "b", "c"]

    # El autor retira b: a y c ya tienen su observación de la semana y el consolidado cierra.
    root = tmp_path / "be"
    for d in ("a", "c"):
        raw = root / "artifacts" / "observations" / d / "obs" / "inputs" / f"data_raw_{d}.csv"
        raw.parent.mkdir(parents=True)
        raw.write_text(
            _CAB_SEXO + "".join(f"2026,43,E{i},{d.upper()},1,1,1,1\n" for i in range(32)),
            encoding="utf-8",
        )
    monkeypatch.setattr(ps, "publicados", lambda: ["a", "c"])
    monkeypatch.setattr(ps, "observacion_actual", lambda d, r=None: "obs")
    import epiforecast.publication.contratos_datos as cd

    monkeypatch.setattr(
        cd,
        "revisa_consolidado",
        lambda out, c, p: SimpleNamespace(pasa=True, problemas=(), cifras={"cortes": {}}),
    )
    monkeypatch.setattr(
        cd.ContratoCobertura,
        "canonico",
        classmethod(lambda cls: SimpleNamespace(padecimientos=())),
    )
    base = tmp_path / "base.csv"
    base.write_text(_CAB_SEXO, encoding="utf-8")
    out = tmp_path / "out.csv"
    assert ps.consolida(43, 2026, base, base, base, out, root) == 0
    assert out.read_text(encoding="utf-8").count("2026,43,") == 64


def test_consolida_rechaza_una_base_con_un_duplicado_falso(tmp_path: Path, monkeypatch, capsys):
    """Tercera auditoría, A1: una fila falsa antes de la correcta no se oculta al indexar."""
    e = _escenario(tmp_path, monkeypatch, 32)
    _con_historia(
        e, "2026,42,E7,X,999999,,,4\n" + "".join(f"2026,42,E{i},X,2,,,4\n" for i in range(32))
    )
    assert (
        ps.consolida(43, 2026, e["base"], e["leg_base"], e["leg_cand"], e["out"], e["root"]) == 2
    )
    assert "repite filas" in capsys.readouterr().err and not e["out"].exists()


def test_consolida_rechaza_sexo_inventado_en_una_serie_sin_desglose(tmp_path: Path, monkeypatch):
    """Tercera auditoría, A2."""
    e = _escenario(tmp_path, monkeypatch, 32)
    filas = "".join(
        f"2026,42,E{i},X,2,{'12345' if i == 0 else ''},{'67890' if i == 0 else ''},4\n"
        for i in range(32)
    )
    _con_historia(e, filas)
    assert (
        ps.consolida(43, 2026, e["base"], e["leg_base"], e["leg_cand"], e["out"], e["root"]) == 2
    )


def test_consolida_rechaza_una_semana_fraccionaria_en_la_base(tmp_path: Path, monkeypatch, capsys):
    """Cuarta auditoría, B2."""
    e = _escenario(tmp_path, monkeypatch, 32)
    filas = "".join(f"2026,{'42.5' if i == 3 else '42'},E{i},X,2,,,4\n" for i in range(32))
    _con_historia(e, filas)
    assert (
        ps.consolida(43, 2026, e["base"], e["leg_base"], e["leg_cand"], e["out"], e["root"]) == 2
    )
    assert "no entero" in capsys.readouterr().err and not e["out"].exists()
