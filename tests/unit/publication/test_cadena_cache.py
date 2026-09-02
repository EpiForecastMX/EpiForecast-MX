"""P0.10: cada eslabón de la cadena de caché del EpiBot se comprueba contra el HEAD."""

from __future__ import annotations

from pathlib import Path

import pytest

from epiforecast.publication.cadena_cache import revisa_cadena_cache
from epiforecast.publication.weekly_staging import StagingError
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
