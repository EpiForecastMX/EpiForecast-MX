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
        (lambda d: d.pop("profundidad_minima_semanas"), "malformada"),
        (lambda d: d.pop("directorios_scratch"), "malformada"),
        (lambda d: d.update(directorios_scratch=["data/raw", "data/raw"]), "sin repetidos"),
        (lambda d: d.update(directorios_scratch=["../fuera"]), "directorio scratch"),
        (lambda d: d.update(profundidad_minima_semanas=0), "entero >= 1"),
        (lambda d: d.update(profundidad_minima_semanas=True), "entero >= 1"),
        (
            lambda d: d["entradas"].append(
                {"ruta": "reports/*.xlsx", "rol": "tabla_produccion", "obligatoria": True}
            ),
            "un patrón no puede tener el rol",
        ),
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
    # Los directorios scratch existen vacíos: los generadores escriben ahí sus intermedios.
    assert (backend / "data" / "raw").is_dir() and not any((backend / "data" / "raw").iterdir())
    assert (backend / "web_dashboard").is_dir()
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


def test_una_entrada_rastreada_se_toma_del_head_y_no_se_copia_a_ciegas(tmp_path: Path) -> None:
    """Las tablas de producción están en git: el sandbox ya las trae; el worktree tiene que
    coincidir, y si no coincide es un cambio de datos sin confirmar."""
    lista = fab.lista_entradas_cruda(
        [
            (fab.RUTA_CONSOLIDADO, "consolidado", True),
            ("reports/ProdDetails/tabla.csv", "tabla", True),
        ]
    )
    repo_b, head_b, _, trabajo = _montaje(tmp_path, lista=lista)

    resultado = hidrata(
        trabajo, repo_b, head_b, padecimientos_autorizados=fab.PADECIMIENTOS, contrato=fab.CONTRATO
    )

    tabla = resultado.sandbox / "EpiForecast-MX" / "reports" / "ProdDetails" / "tabla.csv"
    assert tabla.read_text() == "viejo\n"
    assert (
        resultado.registro.entradas["reports/ProdDetails/tabla.csv"]["sha256"]
        == hashlib.sha256(b"viejo\n").hexdigest()
    )

    # Ahora el worktree difiere del HEAD: no se hidrata con ninguno de los dos.
    repo_b2, head_b2, _, trabajo2 = _montaje(tmp_path / "otro", lista=lista)
    (repo_b2 / "reports" / "ProdDetails" / "tabla.csv").write_text("editado sin confirmar\n")
    with pytest.raises(StagingError, match="difiere del HEAD en el árbol de trabajo"):
        hidrata(
            trabajo2,
            repo_b2,
            head_b2,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=fab.CONTRATO,
        )
    assert not (tmp_path / "otro" / "trabajo.sandbox").exists()


# ── patrones, materialización y profundidad ──────────────────────────────────


def test_un_patron_hidrata_cada_coincidencia_con_su_rol(tmp_path: Path) -> None:
    lista = fab.lista_entradas_cruda(
        [
            (fab.RUTA_CONSOLIDADO, "consolidado", True),
            ("models/*/*/*_completo.csv", "metricas", True),
            ("models/*/*/*.pkl", "metricas", False),
        ]
    )
    repo_b, head_b, _, trabajo = _montaje(
        tmp_path,
        lista=lista,
        extra_sin_rastrear={
            "models/prophet/Dengue/Prophet_Dengue_completo.csv": "a\n",
            "models/deepar/Dengue/Deepar_Dengue_completo.csv": "b\n",
            "models/deepar/Dengue/otro.txt": "no casa\n",
        },
    )

    resultado = hidrata(
        trabajo, repo_b, head_b, padecimientos_autorizados=fab.PADECIMIENTOS, contrato=fab.CONTRATO
    )

    assert {r for r, m in resultado.registro.entradas.items() if m["rol"] == "metricas"} == {
        "models/deepar/Dengue/Deepar_Dengue_completo.csv",
        "models/prophet/Dengue/Prophet_Dengue_completo.csv",
    }
    assert not (
        resultado.sandbox / "EpiForecast-MX" / "models" / "deepar" / "Dengue" / "otro.txt"
    ).exists()


def test_un_patron_obligatorio_sin_coincidencias_aborta(tmp_path: Path) -> None:
    lista = fab.lista_entradas_cruda(
        [
            (fab.RUTA_CONSOLIDADO, "consolidado", True),
            ("models/*/*/*_completo.csv", "metricas", True),
        ]
    )
    repo_b, head_b, _, trabajo = _montaje(tmp_path, lista=lista)

    with pytest.raises(
        StagingError, match="patrón obligatorio models/\\*/\\*/\\*_completo.csv no casa"
    ):
        hidrata(
            trabajo,
            repo_b,
            head_b,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=fab.CONTRATO,
        )
    assert not (tmp_path / "trabajo.sandbox").exists()


def test_hidratar_exige_el_head_de_la_materializacion(tmp_path: Path) -> None:
    repo_b, head_b, _, trabajo = _montaje(tmp_path)
    (repo_b / "marca.txt").write_text("otro commit", encoding="utf-8")
    import subprocess

    subprocess.run(["git", "-C", str(repo_b), "add", "marca.txt"], check=True)
    subprocess.run(["git", "-C", str(repo_b), "commit", "-qm", "avanza"], check=True)
    head_nuevo = subprocess.run(
        ["git", "-C", str(repo_b), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert head_nuevo != head_b

    with pytest.raises(StagingError, match=f"materializó desde el backend {head_b[:12]}"):
        hidrata(
            trabajo,
            repo_b,
            head_nuevo,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=fab.CONTRATO,
        )
    (trabajo / "materializacion.json").unlink()
    with pytest.raises(StagingError, match="no hay materialización registrada"):
        hidrata(
            trabajo,
            repo_b,
            head_b,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=fab.CONTRATO,
        )


def test_la_profundidad_de_la_lista_y_la_del_contrato_tienen_que_coincidir(tmp_path: Path) -> None:
    from dataclasses import replace

    repo_b, head_b, _, trabajo = _montaje(tmp_path)
    with pytest.raises(
        StagingError, match="profundidad mínima de la lista \\(2\\) no es la del contrato \\(52\\)"
    ):
        hidrata(
            trabajo,
            repo_b,
            head_b,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=replace(fab.CONTRATO, profundidad_minima=52),
        )


def test_el_digest_declarado_es_el_del_origen_antes_de_copiar(tmp_path: Path, monkeypatch) -> None:
    """Un origen que cambia durante la copia no pasa por copia fiel."""
    from epiforecast.publication import hidratacion

    origen = tmp_path / "origen.csv"
    origen.write_text("antes\n", encoding="utf-8")
    copia_real = hidratacion.shutil.copyfileobj

    def copia_que_cambia_el_origen(f, g, *a):  # noqa: ANN001, ANN202
        copia_real(f, g, *a)
        origen.write_text("despues\n", encoding="utf-8")

    monkeypatch.setattr(hidratacion.shutil, "copyfileobj", copia_que_cambia_el_origen)
    with pytest.raises(StagingError, match="no coincide con el original"):
        hidratacion._copia_regular(origen, tmp_path / "copia.csv")


def test_un_patron_no_casa_a_traves_de_enlaces_de_directorio(tmp_path: Path) -> None:
    """`*` sigue enlaces de directorio: `models/prophet -> /fuera` declararía como intra-repo
    lo que vive en otro sitio."""
    lista = fab.lista_entradas_cruda(
        [
            (fab.RUTA_CONSOLIDADO, "consolidado", True),
            ("models/*/*/*_completo.csv", "metricas", True),
        ]
    )
    repo_b, head_b, _, trabajo = _montaje(tmp_path, lista=lista)
    fuera = tmp_path / "fuera" / "Dengue"
    fuera.mkdir(parents=True)
    (fuera / "X_completo.csv").write_text("a\n", encoding="utf-8")
    (repo_b / "models").mkdir()
    (repo_b / "models" / "prophet").symlink_to(tmp_path / "fuera", target_is_directory=True)

    with pytest.raises(StagingError, match="casó a través de un enlace simbólico"):
        hidrata(
            trabajo,
            repo_b,
            head_b,
            padecimientos_autorizados=fab.PADECIMIENTOS,
            contrato=fab.CONTRATO,
        )
    assert not (tmp_path / "trabajo.sandbox").exists()


def test_un_origen_que_cambia_conservando_el_tamano_tampoco_pasa(
    tmp_path: Path, monkeypatch
) -> None:
    from epiforecast.publication import hidratacion

    origen = tmp_path / "origen.csv"
    origen.write_text("antes\n", encoding="utf-8")
    copia_real = hidratacion.shutil.copyfileobj

    def copia_y_cambia_mismo_tamano(f, g, *a):  # noqa: ANN001, ANN202
        copia_real(f, g, *a)
        origen.write_text("aXtes\n", encoding="utf-8")

    monkeypatch.setattr(hidratacion.shutil, "copyfileobj", copia_y_cambia_mismo_tamano)
    with pytest.raises(StagingError, match="no coincide con el original"):
        hidratacion._copia_regular(origen, tmp_path / "copia.csv")


def test_autorizar_un_solo_padecimiento_no_reduce_el_contrato_en_la_hidratacion(
    tmp_path: Path,
) -> None:
    """Dengue en W30 y neuro en W31: aunque sólo se autorice Dengue, la paridad es entre todos."""
    repo_b, head_b, _, trabajo = _montaje(
        tmp_path, consolidado=fab.consolidado_csv(cortes={fab.PAD_CONTEO: (2026, 30)})
    )

    with pytest.raises(StagingError, match="corte dispar"):
        hidrata(
            trabajo,
            repo_b,
            head_b,
            padecimientos_autorizados=(fab.PAD_CONTEO,),
            contrato=fab.CONTRATO,
        )
    with pytest.raises(StagingError, match="fuera del contrato"):
        hidrata(
            trabajo, repo_b, head_b, padecimientos_autorizados=("Obesidad",), contrato=fab.CONTRATO
        )


def test_la_copia_conserva_el_mtime_del_origen(tmp_path: Path) -> None:
    """`build_web_knowledge.py` deriva «último entrenamiento» del mtime del forecast: una
    copia fresca publicaba la fecha de la hidratación como si se hubiera entrenado."""
    import os

    from epiforecast.publication import hidratacion

    origen = tmp_path / "forecast.csv"
    origen.write_text("ds,yhat\n", encoding="utf-8")
    antiguo = 1_700_000_000
    os.utime(origen, (antiguo, antiguo))

    hidratacion._copia_regular(origen, tmp_path / "copia.csv")

    assert int((tmp_path / "copia.csv").stat().st_mtime) == antiguo
