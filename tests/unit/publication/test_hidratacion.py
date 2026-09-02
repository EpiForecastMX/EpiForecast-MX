"""P0.1/P0.2: hidratación por allowlist con contrato exacto, y copias inmutables de entradas."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from epiforecast.publication.hidratacion import ListaEntradas, hidrata
from epiforecast.publication.materializa import materializa_candidato
from epiforecast.publication.weekly_staging import (
    Boletin,
    RegistroHidratacion,
    StagingError,
    inventaria,
)
from tests.unit.publication import fabrica_p0 as fab


def _montaje(tmp_path: Path, **kwargs):  # noqa: ANN003, ANN202
    politica = fab.politica_cruda(fab.superficies_de(fab.SITIO_EPIBOT))
    repo_b, head_b = fab.repo_backend(tmp_path / "repo_backend", politica=politica, **kwargs)
    repo_d, head_d = fab.repo_dashboard(tmp_path / "repo_dashboard")
    trabajo = tmp_path / "trabajo"
    materializa_candidato(
        trabajo, {"backend": repo_b, "dashboard": repo_d}, {"backend": head_b, "dashboard": head_d}
    )
    return repo_b, head_b, repo_d, trabajo


# ── la allowlist ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("mutador", "mensaje"),
    [
        (lambda d: d.update(version="entradas/0"), "otra versión"),
        (
            lambda d: d["entradas"].append(
                {"ruta": "../x.csv", "rol": "tabla", "obligatoria": True}
            ),
            "'\\.\\.'",
        ),
        (
            lambda d: d["entradas"].append(
                {"ruta": "/abs.csv", "rol": "tabla", "obligatoria": True}
            ),
            "relativa POSIX",
        ),
        (
            lambda d: d["entradas"].append(
                {"ruta": "x.csv", "rol": "secreto", "obligatoria": True}
            ),
            "rol de entrada desconocido",
        ),
        (
            lambda d: d["entradas"].append({"ruta": "x.csv", "rol": "tabla", "obligatoria": "sí"}),
            "booleano",
        ),
        (
            lambda d: d["entradas"].append(
                {"ruta": fab.RUTA_FORECAST, "rol": "forecast", "obligatoria": True}
            ),
            "repite rutas",
        ),
        (
            lambda d: d["entradas"].append(
                {"ruta": "otro.csv", "rol": "consolidado", "obligatoria": True}
            ),
            "exactamente un consolidado",
        ),
        (
            lambda d: d["entradas"][0].update(obligatoria=False),
            "exactamente un consolidado obligatorio",
        ),
        (lambda d: d.update(extra=1), "malformada"),
    ],
)
def test_el_parser_de_la_allowlist_falla_cerrado(mutador, mensaje: str) -> None:
    cruda = fab.lista_entradas_cruda()
    mutador(cruda)
    with pytest.raises(StagingError, match=mensaje):
        ListaEntradas.desde_bytes(json.dumps(cruda).encode())


def test_la_allowlist_se_lee_del_head_y_no_del_disco(tmp_path: Path) -> None:
    repo_b, head_b, _, _ = _montaje(tmp_path)
    ruta = repo_b / "config" / "publication" / "entradas_semanales.json"
    ruta.write_text(
        json.dumps(fab.lista_entradas_cruda([(fab.RUTA_CONSOLIDADO, "consolidado", True)]))
    )

    with pytest.raises(StagingError, match="difiere de la versión"):
        ListaEntradas.del_head(repo_b, head_b)


# ── hidratar: sandbox, copias, inventario y contrato ────────────────────────


def test_hidrata_construye_el_sandbox_con_solo_lo_declarado(tmp_path: Path) -> None:
    repo_b, head_b, _, trabajo = _montaje(
        tmp_path, extra_sin_rastrear={"data/processed/secreto.csv": "no declarado"}
    )
    antes = inventaria(trabajo / "outputs")

    resultado = hidrata(
        trabajo, repo_b, head_b, padecimientos_autorizados=fab.PADECIMIENTOS, contrato=fab.CONTRATO
    )

    backend = resultado.sandbox / "EpiForecast-MX"
    assert (backend / "src" / "codigo.py").read_text() == "print('sandbox')\n", "código del HEAD"
    assert (backend / fab.RUTA_CONSOLIDADO).read_text() == fab.consolidado_csv()
    assert (backend / fab.RUTA_FORECAST).is_file()
    assert not (backend / "data" / "processed" / "secreto.csv").exists(), "sólo la allowlist"
    assert not (backend / ".git").exists()
    enlace = resultado.sandbox / "EpiForecast-IMSS-Dashboard"
    assert (
        enlace.is_symlink() and enlace.resolve() == (trabajo / "outputs" / "dashboard").resolve()
    )
    # Copias inmutables e inventario con digests.
    base = trabajo / "inputs" / "consolidado_base.csv"
    assert base.read_text() == fab.consolidado_csv()
    registro = RegistroHidratacion.lee(trabajo)
    assert registro.head_backend == head_b
    assert set(registro.entradas) == {fab.RUTA_CONSOLIDADO, fab.RUTA_FORECAST}
    assert (
        registro.entradas[fab.RUTA_CONSOLIDADO]["sha256"]
        == hashlib.sha256(base.read_bytes()).hexdigest()
    )
    assert registro.cobertura["consolidado"]["cortes"] == {
        fab.slug(p): [2026, 31] for p in fab.PADECIMIENTOS
    }
    assert [c.fuente for c in resultado.coberturas] == ["consolidado", "forecasts"]
    # El candidato no se contamina.
    assert inventaria(trabajo / "outputs") == antes


def test_una_entrada_obligatoria_ausente_aborta_sin_dejar_medias(tmp_path: Path) -> None:
    repo_b, head_b, _, trabajo = _montaje(tmp_path)
    (repo_b / fab.RUTA_FORECAST).unlink()

    with pytest.raises(StagingError, match="falta la entrada obligatoria"):
        hidrata(
            trabajo,
            repo_b,
            head_b,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=fab.CONTRATO,
        )
    assert not (tmp_path / "trabajo.sandbox").exists()
    assert not (trabajo / "inputs").exists() and not (trabajo / "entradas.json").exists()


def test_una_entrada_opcional_ausente_se_omite(tmp_path: Path) -> None:
    lista = fab.lista_entradas_cruda(
        [
            (fab.RUTA_CONSOLIDADO, "consolidado", True),
            ("data/interim/opcional.csv", "contexto", False),
        ]
    )
    repo_b, head_b, _, trabajo = _montaje(tmp_path, lista=lista)

    resultado = hidrata(
        trabajo, repo_b, head_b, padecimientos_autorizados=fab.PADECIMIENTOS, contrato=fab.CONTRATO
    )

    assert set(resultado.registro.entradas) == {fab.RUTA_CONSOLIDADO}


def test_una_hidratacion_corta_revienta_antes_de_generar(tmp_path: Path) -> None:
    """Consolidado con una entidad de menos: plausible para un generador, FAIL aquí."""
    repo_b, head_b, _, trabajo = _montaje(
        tmp_path, consolidado=fab.consolidado_csv(quitar={(fab.PAD_NEURO, "México")})
    )

    with pytest.raises(
        StagingError, match="(?s)no cubre el contrato.*faltan entidades \\['mexico'\\]"
    ):
        hidrata(
            trabajo,
            repo_b,
            head_b,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=fab.CONTRATO,
        )
    assert not (tmp_path / "trabajo.sandbox").exists()


def test_un_corte_dispar_de_dengue_revienta_en_la_hidratacion(tmp_path: Path) -> None:
    repo_b, head_b, _, trabajo = _montaje(
        tmp_path, consolidado=fab.consolidado_csv(cortes={fab.PAD_CONTEO: (2026, 30)})
    )

    with pytest.raises(StagingError, match="corte dispar"):
        hidrata(
            trabajo,
            repo_b,
            head_b,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=fab.CONTRATO,
        )


def test_una_entrada_que_es_enlace_no_se_hidrata(tmp_path: Path) -> None:
    repo_b, head_b, _, trabajo = _montaje(tmp_path)
    real = repo_b / "data" / "processed" / "real.csv"
    (repo_b / fab.RUTA_CONSOLIDADO).rename(real)
    (repo_b / fab.RUTA_CONSOLIDADO).symlink_to(real)

    with pytest.raises(StagingError, match="enlace simbólico"):
        hidrata(
            trabajo,
            repo_b,
            head_b,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=fab.CONTRATO,
        )


def test_un_boletin_declarado_se_copia_verificado(tmp_path: Path) -> None:
    pdf = b"%PDF-1.4 boletin semana 31"
    repo_b, head_b, _, trabajo = _montaje(
        tmp_path, extra_sin_rastrear={"data/raw_PDFs/2026_sem31.pdf": pdf}
    )
    boletin = Boletin(
        "2026_sem31.pdf", "https://ejemplo/sem31.pdf", len(pdf), hashlib.sha256(pdf).hexdigest()
    )

    resultado = hidrata(
        trabajo,
        repo_b,
        head_b,
        padecimientos_autorizados=fab.PADECIMIENTOS,
        boletines=(boletin,),
        contrato=fab.CONTRATO,
    )

    assert (trabajo / "inputs" / "boletines" / "2026_sem31.pdf").read_bytes() == pdf
    assert (
        resultado.sandbox / "EpiForecast-MX" / "data" / "raw_PDFs" / "2026_sem31.pdf"
    ).read_bytes() == pdf
    assert resultado.registro.boletines == (boletin,)
    assert resultado.registro.entradas["data/raw_PDFs/2026_sem31.pdf"]["rol"] == "pdf"


@pytest.mark.parametrize("campo", ["bytes", "sha256", "nombre"])
def test_un_boletin_que_no_coincide_con_lo_declarado_aborta(tmp_path: Path, campo: str) -> None:
    pdf = b"%PDF-1.4 boletin"
    repo_b, head_b, _, trabajo = _montaje(
        tmp_path, extra_sin_rastrear={"data/raw_PDFs/2026_sem31.pdf": pdf}
    )
    declarado = {
        "nombre": "2026_sem31.pdf",
        "url": "u",
        "bytes": len(pdf),
        "sha256": hashlib.sha256(pdf).hexdigest(),
    }
    declarado[campo] = {"bytes": 1, "sha256": "e" * 64, "nombre": "2026_sem99.pdf"}[campo]

    with pytest.raises(StagingError, match="no existe la entrada|no coincide con lo declarado"):
        hidrata(
            trabajo,
            repo_b,
            head_b,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            boletines=(Boletin(**declarado),),
            contrato=fab.CONTRATO,
        )
    assert not (trabajo / "inputs").exists()


def test_no_se_hidrata_dos_veces_ni_sobre_un_sandbox_existente(tmp_path: Path) -> None:
    repo_b, head_b, _, trabajo = _montaje(tmp_path)
    hidrata(
        trabajo, repo_b, head_b, padecimientos_autorizados=fab.PADECIMIENTOS, contrato=fab.CONTRATO
    )

    with pytest.raises(StagingError, match="no se hidrata dos veces"):
        hidrata(
            trabajo,
            repo_b,
            head_b,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=fab.CONTRATO,
        )


def test_hidratar_exige_un_trabajo_materializado(tmp_path: Path) -> None:
    repo_b, head_b, _, _ = _montaje(tmp_path)
    with pytest.raises(StagingError, match="no está materializado"):
        hidrata(
            tmp_path / "vacio",
            repo_b,
            head_b,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=fab.CONTRATO,
        )


# ── el registro de hidratación es fail-closed ────────────────────────────────


def test_el_registro_se_relee_con_sidecar_y_forma_exacta(tmp_path: Path) -> None:
    repo_b, head_b, _, trabajo = _montaje(tmp_path)
    hidrata(
        trabajo, repo_b, head_b, padecimientos_autorizados=fab.PADECIMIENTOS, contrato=fab.CONTRATO
    )
    ruta = trabajo / "entradas.json"
    crudo = json.loads(ruta.read_text(encoding="utf-8"))
    crudo["entradas"][fab.RUTA_CONSOLIDADO]["sha256"] = "f" * 64
    ruta.write_text(json.dumps(crudo, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(StagingError, match="entradas.sha256"):
        RegistroHidratacion.lee(trabajo)


def test_el_cli_hidrata_y_reporta_la_cobertura(tmp_path: Path, capsys) -> None:
    from scripts.refresh_staging import main

    repo_b, head_b, _, trabajo = _montaje(tmp_path)

    rc = main(
        [
            "hydrate",
            "--trabajo",
            str(trabajo),
            "--repo-backend",
            str(repo_b),
            "--head-backend",
            head_b,
            "--padecimientos",
            ",".join(fab.PADECIMIENTOS),
        ]
    )

    assert rc == 0
    salida = capsys.readouterr().out
    assert "cobertura consolidado" in salida and "cobertura forecasts" in salida
    assert (trabajo / "entradas.json").is_file()
