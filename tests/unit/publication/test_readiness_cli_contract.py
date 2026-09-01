"""Contratos del CLI de readiness contra Git, su fuente y su manual."""

import ast
from pathlib import Path
import re
import subprocess

import pytest
from scripts.publication_readiness import build_parser, check_evidence_root

from epiforecast.runner.artifact_identity import ArtifactValidationError

pytestmark = pytest.mark.contract

REPO = Path(__file__).resolve().parents[3]
FUENTE = REPO / "scripts" / "publication_readiness.py"
ESCRITURAS_PROHIBIDAS = {
    "apply",
    "apply_recovery",
    "recover",
    "promote",
    "rollback",
    "delete",
    "write_table",
    "rename_table",
    "drop_table",
    "del_worksheet",
    "update_title",
    "installShard",
}


def _repo_root() -> Path:
    assert (REPO / "pyproject.toml").is_file(), "la raíz calculada no es la del repo"
    return REPO


def test_el_orquestador_no_llama_a_ninguna_operacion_de_escritura():
    """AST, no grep: importa qué se llama, no qué aparece en un comentario."""
    arbol = ast.parse(FUENTE.read_text("utf-8"))
    llamadas = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call):
            funcion = nodo.func
            llamadas.add(
                funcion.attr if isinstance(funcion, ast.Attribute) else getattr(funcion, "id", "")
            )
    prohibidas = llamadas & ESCRITURAS_PROHIBIDAS
    assert not prohibidas, f"el orquestador llama a {prohibidas}"


def test_no_existe_bandera_ni_subcomando_equivalente_a_aplicar():
    fuente = FUENTE.read_text("utf-8")
    for prohibido in ('"--apply"', "'--apply'", '"apply"', '"recover"'):
        assert prohibido not in fuente, f"{prohibido} declarado en el CLI"

    ayuda = build_parser().format_help()
    assert "--apply" not in ayuda
    for accion in build_parser()._actions:  # noqa: SLF001 — inspección deliberada del parser
        assert getattr(accion, "dest", "") != "apply"


def test_el_orquestador_no_conoce_ningun_padecimiento_ni_conteo():
    """Genericidad: sin enfermedades, motores ni conteos del release actual."""
    arbol = ast.parse(FUENTE.read_text("utf-8"))
    literales = [
        nodo.value
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (str, int))
    ]
    docstrings = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(nodo)
            if doc:
                docstrings.add(doc)
    textos = [valor for valor in literales if isinstance(valor, str) and valor not in docstrings]

    for prohibido in (
        "obesidad",
        "e66",
        "anorexia",
        "dengue",
        "prophet",
        "deepar",
        "ridge",
        "ets",
    ):
        patron = re.compile(rf"\b{prohibido}\b", re.IGNORECASE)
        culpables = [texto for texto in textos if patron.search(texto)]
        assert not culpables, f"{prohibido} escrito en el orquestador: {culpables[:2]}"
    for conteo in (64, 111, 5772, 52, 47):
        assert conteo not in literales, f"el conteo {conteo} está hardcodeado"


def test_el_comando_documentado_en_el_manual_es_el_que_existe():
    """Anti-deriva: el comando se extrae del manual, no se transcribe aquí."""
    manual = (REPO / "docs" / "MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md").read_text("utf-8")
    bloques = re.findall(r"```zsh\n(.*?)```", manual, re.S)
    externos = [
        bloque for bloque in bloques if "publication_readiness external-readonly" in bloque
    ]
    assert externos, "el manual ya no documenta el comando externo"

    crudo = " ".join(externos[0].replace("\\\n", " ").split())
    argv = crudo.split()[crudo.split().index("external-readonly") :]
    assert argv[0] == "external-readonly"
    assert "--shard-root" not in argv, "el manual no puede depender de compatibilidad"
    assert "--apply" not in crudo
    args = build_parser().parse_args(["external-readonly", "--local-evidence", "x.json"])
    assert args.comando == "external-readonly"


def test_la_evidencia_no_puede_caer_dentro_del_repositorio(tmp_path):
    repo = _repo_root()
    for prohibida in ("reports/tmp/ev", "reports/runs/ev", "src/ev"):
        with pytest.raises(ArtifactValidationError, match="no se versiona"):
            check_evidence_root(repo / prohibida, repo)
    assert check_evidence_root(repo / "runs" / "_ev", repo)
    assert check_evidence_root(tmp_path / "ev", repo)


def test_runs_ignorado_se_acepta_antes_de_existir_en_un_clon_limpio(tmp_path):
    repo = tmp_path / "clean_clone"
    repo.mkdir()
    (repo / ".gitignore").write_text("runs/\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    destino = repo / "runs" / "readiness" / "evidence"
    assert not (repo / "runs").exists(), "la precondición reproduce el clon limpio"

    assert check_evidence_root(destino, repo) == destino.resolve()
    assert not (repo / "runs").exists(), "validar no crea el destino"
