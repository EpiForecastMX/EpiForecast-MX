"""P0.10: cada eslabón de la cadena de caché del EpiBot se comprueba contra el HEAD."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from epiforecast.publication.cadena_cache import revisa_cadena_cache, sube_cadena_cache
from epiforecast.publication.weekly_staging import DIR_EVIDENCIA, Manifiesto, StagingError
from tests.unit.publication import fabrica_p0 as fab


def _candidato(tmp_path: Path, cambios: dict[str, str]) -> tuple[Path, str, Path]:
    """Repo del dashboard en HEAD y un candidato igual salvo `cambios`."""
    repo, head = fab.repo_dashboard(tmp_path / "repo")
    outputs = tmp_path / "outputs" / "dashboard"
    for rel, texto in {**fab.SITIO_EPIBOT, **cambios}.items():
        (outputs / rel).parent.mkdir(parents=True, exist_ok=True)
        (outputs / rel).write_text(texto, encoding="utf-8")
    return repo, head, outputs


def test_sin_cambios_no_hay_nada_que_invalidar(tmp_path: Path) -> None:
    repo, head, outputs = _candidato(tmp_path, {})
    resultado = revisa_cadena_cache(repo, head, outputs)
    assert resultado.aplica and resultado.cambiados == ()


def test_datos_nuevos_exigen_data_version_nueva(tmp_path: Path) -> None:
    repo, head, outputs = _candidato(
        tmp_path, {"epibot/knowledge.json": fab.knowledge_json(max_semana=32)}
    )

    with pytest.raises(StagingError, match="DATA_VERSION sigue en '1'"):
        revisa_cadena_cache(repo, head, outputs)


def test_subir_data_version_obliga_a_subir_el_import_de_kb(tmp_path: Path) -> None:
    """kb.js cambió (por DATA_VERSION); app.js lo sigue importando con ?v=1."""
    repo, head, outputs = _candidato(
        tmp_path,
        {
            "epibot/knowledge.json": fab.knowledge_json(max_semana=32),
            "epibot/js/kb.js": "const DATA_VERSION = '2';\nexport function loadKnowledge() {}\n",
        },
    )

    with pytest.raises(
        StagingError, match="kb.js cambió y epibot/js/app.js lo sigue importando con \\?v=1"
    ):
        revisa_cadena_cache(repo, head, outputs)


def test_subir_el_import_obliga_a_subir_app_en_el_html(tmp_path: Path) -> None:
    repo, head, outputs = _candidato(
        tmp_path,
        {
            "epibot/knowledge.json": fab.knowledge_json(max_semana=32),
            "epibot/js/kb.js": "const DATA_VERSION = '2';\nexport function loadKnowledge() {}\n",
            "epibot/js/app.js": "import { loadKnowledge } from './kb.js?v=2';\nimport { norm } from './entities.js?v=1';\n",
        },
    )

    with pytest.raises(
        StagingError, match="app.js cambió y epibot/index.html lo sigue cargando con \\?v=1"
    ):
        revisa_cadena_cache(repo, head, outputs)


def test_la_cadena_completa_pasa(tmp_path: Path) -> None:
    repo, head, outputs = _candidato(
        tmp_path,
        {
            "epibot/knowledge.json": fab.knowledge_json(max_semana=32),
            "epibot/js/kb.js": "const DATA_VERSION = '2';\nexport function loadKnowledge() {}\n",
            "epibot/js/app.js": "import { loadKnowledge } from './kb.js?v=2';\nimport { norm } from './entities.js?v=1';\n",
            "epibot/index.html": '<link rel="stylesheet" href="css/style.css?v=1">\n<script type="module" src="js/app.js?v=2"></script>\n',
        },
    )

    resultado = revisa_cadena_cache(repo, head, outputs)

    assert resultado.aplica
    assert resultado.cambiados == ("epibot/js/app.js", "epibot/js/kb.js", "epibot/knowledge.json")


def test_subir_solo_app_no_invalida_los_datos(tmp_path: Path) -> None:
    """La confusión de la v2 del plan: subir `app.js?v=` no toca DATA_VERSION."""
    repo, head, outputs = _candidato(
        tmp_path,
        {
            "epibot/zoom_series.json": fab.zoom_json(faltan={"dengue|nacional|hombres"}),
            "epibot/index.html": '<link rel="stylesheet" href="css/style.css?v=1">\n<script type="module" src="js/app.js?v=2"></script>\n',
        },
    )

    with pytest.raises(StagingError, match="zoom_series.json cambiaron y DATA_VERSION sigue"):
        revisa_cadena_cache(repo, head, outputs)


def test_un_modulo_secundario_y_el_css_tambien_cuentan(tmp_path: Path) -> None:
    repo, head, outputs = _candidato(
        tmp_path,
        {
            "epibot/js/entities.js": "export function norm(s) { return s.trim(); }\n",
            "epibot/css/style.css": "body { margin: 1px; }\n",
        },
    )

    with pytest.raises(StagingError) as error:
        revisa_cadena_cache(repo, head, outputs)
    assert "entities.js cambió" in str(error.value)
    assert "style.css cambió" in str(error.value)


def test_la_cuarta_boca_no_se_arregla(tmp_path: Path) -> None:
    repo, head, outputs = _candidato(
        tmp_path,
        {
            "index.html": "<h1>semana 31</h1>\n<script>fetch('epibot/knowledge.json?v=2')</script>\n"
        },
    )

    with pytest.raises(StagingError, match="no-store"):
        revisa_cadena_cache(repo, head, outputs)


def test_un_sitio_sin_epibot_no_tiene_cadena(tmp_path: Path) -> None:
    repo, head = fab.repo_dashboard(tmp_path / "repo", {"index.html": "<h1>sin epibot</h1>"})
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "index.html").write_text("<h1>cambiado</h1>", encoding="utf-8")

    assert not revisa_cadena_cache(repo, head, outputs).aplica


# ── fail-closed: sin repositorio o sin commit no hay «no aplica» ─────────────


def test_un_head_inexistente_no_hace_que_la_cadena_no_aplique(tmp_path: Path) -> None:
    repo, _head, outputs = _candidato(tmp_path, {})

    with pytest.raises(StagingError, match="no existe en"):
        revisa_cadena_cache(repo, "b" * 40, outputs)


def test_una_ruta_que_no_es_repositorio_aborta(tmp_path: Path) -> None:
    _repo, head, outputs = _candidato(tmp_path, {})
    (tmp_path / "no_repo").mkdir()

    with pytest.raises(StagingError, match="no se pudo listar|no existe"):
        revisa_cadena_cache(tmp_path / "no_repo", head, outputs)
    with pytest.raises(StagingError, match="no existe"):
        revisa_cadena_cache(tmp_path / "ausente", head, outputs)


# ── subir la cadena ──────────────────────────────────────────────────────────


def test_subir_la_cadena_deja_cada_eslabon_al_dia(tmp_path: Path) -> None:
    """Datos nuevos: DATA_VERSION sube, con ella kb.js cambia, con él app.js, con él index."""
    repo, head, outputs = _candidato(
        tmp_path, {"epibot/knowledge.json": fab.knowledge_json(max_semana=32)}
    )

    resultado = sube_cadena_cache(repo, head, outputs)

    assert resultado.cambios == (
        "epibot/js/kb.js: DATA_VERSION 1 -> 2",
        "epibot/js/app.js: kb.js?v=1 -> 2",
        "epibot/index.html: js/app.js?v=1 -> 2",
    )
    assert resultado.cadena.aplica
    assert "DATA_VERSION = '2'" in (outputs / "epibot" / "js" / "kb.js").read_text()
    assert "./kb.js?v=2" in (outputs / "epibot" / "js" / "app.js").read_text()
    assert "./entities.js?v=1" in (outputs / "epibot" / "js" / "app.js").read_text()
    assert "js/app.js?v=2" in (outputs / "epibot" / "index.html").read_text()
    assert "css/style.css?v=1" in (outputs / "epibot" / "index.html").read_text()
    assert (outputs / "index.html").read_text() == fab.SITIO_EPIBOT["index.html"]
    # Idempotente: volver a subir no toca nada.
    assert sube_cadena_cache(repo, head, outputs).cambios == ()
    # Y el repositorio no cambió: sólo se escribe en el candidato.
    assert "DATA_VERSION = '1'" in (repo / "epibot" / "js" / "kb.js").read_text()


def test_subir_respeta_lo_que_el_generador_ya_subio(tmp_path: Path) -> None:
    repo, head, outputs = _candidato(
        tmp_path,
        {
            "epibot/knowledge.json": fab.knowledge_json(max_semana=32),
            "epibot/js/kb.js": "const DATA_VERSION = '20260901';\nexport function loadKnowledge() {}\n",
        },
    )

    resultado = sube_cadena_cache(repo, head, outputs, data_version="ignorado")

    assert resultado.cambios == (
        "epibot/js/app.js: kb.js?v=1 -> 2",
        "epibot/index.html: js/app.js?v=1 -> 2",
    )


def test_una_data_version_explicita_se_usa_tal_cual(tmp_path: Path) -> None:
    repo, head, outputs = _candidato(
        tmp_path, {"epibot/knowledge.json": fab.knowledge_json(max_semana=32)}
    )
    resultado = sube_cadena_cache(repo, head, outputs, data_version="20260902")
    assert resultado.cambios[0] == "epibot/js/kb.js: DATA_VERSION 1 -> 20260902"

    with pytest.raises(StagingError, match="la misma que la del HEAD"):
        sube_cadena_cache(
            *_candidato(
                tmp_path / "otro", {"epibot/knowledge.json": fab.knowledge_json(max_semana=33)}
            ),
            data_version="1",
        )


def test_una_version_no_numerica_no_se_inventa(tmp_path: Path) -> None:
    repo, head = fab.repo_dashboard(
        tmp_path / "repo",
        {
            **fab.SITIO_EPIBOT,
            "epibot/index.html": '<script type="module" src="js/app.js?v=beta"></script>\n',
        },
    )
    outputs = tmp_path / "outputs" / "dashboard"
    for rel, texto in {
        **fab.SITIO_EPIBOT,
        "epibot/index.html": '<script type="module" src="js/app.js?v=beta"></script>\n',
        "epibot/js/app.js": "import { loadKnowledge } from './kb.js?v=1'; // cambiado\n",
    }.items():
        (outputs / rel).parent.mkdir(parents=True, exist_ok=True)
        (outputs / rel).write_text(texto, encoding="utf-8")

    with pytest.raises(StagingError, match="no es numérica"):
        sube_cadena_cache(repo, head, outputs)


# ── M31: la cadena está cableada en `seal`, por el CLI y con un EpiBot real ─


def _staging_con_epibot(tmp_path: Path) -> dict[str, Any]:
    """Backend y dashboard sintéticos; el candidato trae knowledge.json nuevo sin subir nada."""
    from scripts.refresh_staging import main

    politica = fab.politica_cruda(fab.superficies_de(fab.SITIO_EPIBOT), gates=[fab.gate("cifras")])
    repo_b, head_b = fab.repo_backend(tmp_path / "backend", politica=politica)
    repo_d, head_d = fab.repo_dashboard(tmp_path / "dashboard")
    trabajo = tmp_path / "trabajo"
    outputs = trabajo / "outputs" / "dashboard"
    for rel, texto in fab.SITIO_EPIBOT.items():
        (outputs / rel).parent.mkdir(parents=True, exist_ok=True)
        (outputs / rel).write_text(texto, encoding="utf-8")
    semilla = trabajo / "semilla.json"
    assert main(["snapshot", "--raiz", str(trabajo / "outputs"), "--salida", str(semilla)]) == 0
    (outputs / "epibot" / "knowledge.json").write_text(
        fab.knowledge_json(max_semana=32), encoding="utf-8"
    )
    assert (
        main(
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
        == 0
    )
    return {
        "trabajo": trabajo,
        "semilla": semilla,
        "repo_b": repo_b,
        "head_b": head_b,
        "repo_d": repo_d,
        "head_d": head_d,
        "run_gates": [
            "run-gates",
            "--trabajo",
            str(trabajo),
            "--head-backend",
            head_b,
            "--destino-backend",
            str(repo_b),
            "--destino-dashboard",
            str(repo_d),
        ],
        "seal": [
            "seal",
            "--trabajo",
            str(trabajo),
            "--semilla",
            str(semilla),
            "--head-backend",
            head_b,
            "--head-dashboard",
            head_d,
            "--semana-anterior",
            "2026,31",
            "--semana-nueva",
            "2026,31",
            "--padecimientos",
            ",".join(fab.PADECIMIENTOS),
            "--destino-backend",
            str(repo_b),
            "--destino-dashboard",
            str(repo_d),
        ],
        "bump": [
            "bump-cache",
            "--trabajo",
            str(trabajo),
            "--destino-dashboard",
            str(repo_d),
            "--head-dashboard",
            head_d,
        ],
    }


def test_seal_por_cli_exige_la_cadena_de_cache_y_bump_cache_la_repara(
    tmp_path: Path, capsys
) -> None:
    """Control de M31: sin `revisa_cadena_cache` en `seal`, este sello saldría."""
    from scripts.refresh_staging import main

    r = _staging_con_epibot(tmp_path)
    assert main(r["run_gates"]) == 0

    assert main(r["seal"]) == 1
    assert "cadena de caché rota" in capsys.readouterr().err
    # No podó: el candidato sigue entero para poder subir la cadena y repetir los gates.
    assert (r["trabajo"] / "outputs" / "dashboard" / "epibot" / "js" / "entities.js").is_file()

    assert main(r["bump"]) == 0
    salida = capsys.readouterr().out
    assert "DATA_VERSION 1 -> 2" in salida and "js/app.js?v=1 -> 2" in salida
    # La composición cambió: la evidencia anterior se aparta sola y los gates se repiten.
    assert main(r["run_gates"]) == 0
    assert (r["trabajo"] / f"{DIR_EVIDENCIA}.otra-composicion-1").is_dir()
    assert main(r["seal"]) == 0
    (sellado,) = [d for d in tmp_path.iterdir() if (d / "manifest.json").is_file()]
    manifiesto = Manifiesto.lee(sellado / "manifest.json")
    assert set(manifiesto.inventario) == {
        "dashboard/epibot/index.html",
        "dashboard/epibot/js/app.js",
        "dashboard/epibot/js/kb.js",
        "dashboard/epibot/knowledge.json",
    }
