"""Materialización 41/41 y ensayo integral del cableado (P0.12 en sintético).

`materialize` extrae el árbol administrado completo de los HEAD sellados; el ensayo
recorre el flujo entero por el CLI —materialize → generación candidata → run-gates →
seal → prepare-worktrees → apply → check-completeness— y comprueba la invariante fuerte:
el árbol administrado del par aplicado, recompuesto desde disco, tiene el mismo digest
que la composición que midieron los gates.

Todo en repositorios Git de usar y tirar. Ningún repositorio real, ningún dato real.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import pytest

from epiforecast.publication.materializa import materializa_candidato
from epiforecast.publication.release_worktrees import ESTADO_APLICADO, RegistroDestinos
from epiforecast.publication.weekly_staging import (
    VERSION_POLITICA,
    Manifiesto,
    StagingError,
    calcula_composicion,
    inventaria,
)
from tests.unit.publication import fabrica_p0 as fab

PYTHON = sys.executable
TRUE = shutil.which("true") or "/usr/bin/true"


# ── montaje ──────────────────────────────────────────────────────────────────


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def _repo(raiz: Path, archivos: dict[str, str]) -> tuple[Path, str]:
    raiz.mkdir(parents=True)
    for rel, contenido in archivos.items():
        (raiz / rel).parent.mkdir(parents=True, exist_ok=True)
        (raiz / rel).write_text(contenido, encoding="utf-8")
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "prueba@ejemplo")
    _git(raiz, "config", "user.name", "Prueba")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-qm", "inicial")
    return raiz.resolve(), _git(raiz, "rev-parse", "HEAD").strip()


SITIO = {
    "index.html": "<h1>semana 31</h1>",
    "EpiDashboard.html": "<p>datos reales hasta la semana 31</p>",
    "calass.html": "<p>ponencia: semana 31</p>",
    "Reports/index.html": "<h1>galeria</h1>",
    "Reports/zoom_data_neuro.json": '{"max_semana": 31}',
    "epibot/index.html": "<script src=app.js?v=138></script>",
    "epibot/knowledge.json": fab.knowledge_json(max_semana=31),
    "epibot/scripts/verify.mjs": "// gate\n",
    "epibot/scripts/lib/corpus.mjs": "// lib\n",
    ".gitignore": "node_modules/\n",
    "netlify.toml": "[build]\n",
}
SUPERFICIES = sorted(
    f"dashboard/{rel}" for rel in SITIO if rel.lower().endswith((".html", ".json"))
)


def _politica_cruda(gates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "version": VERSION_POLITICA,
        "prefijos_administrados": ["backend/reports/ProdDetails/", "dashboard/"],
        "patron_superficie": {
            "prefijo": "dashboard/",
            "sufijos": [".html", ".json"],
            "directorios_excluidos": ["node_modules"],
        },
        "superficies_verificables": SUPERFICIES,
        "retirables": [],
        "gates": gates
        or [
            {
                # Gate de CONTEO, como el censo real: todas las superficies presentes.
                "id": "cifras",
                "argv": [
                    PYTHON,
                    "-c",
                    "import os, sys; n = sum(1 for _, _, fs in os.walk('.') for f in fs "
                    "if f.endswith(('.html', '.json'))); print('superficies', n); "
                    f"sys.exit(0 if n == {len(SUPERFICIES)} else 1)",
                ],
                "cwd": "dashboard/",
                "timeout_s": 30,
                "entorno": {"heredar": [], "fijar": {}},
            },
            {
                # Gate de CONTENIDO, como el contrato de cifras real: el candidato tiene que
                # declarar la semana nueva en el conocimiento del EpiBot.
                "id": "rag",
                "argv": [
                    PYTHON,
                    "-c",
                    "import json, sys; d = json.load(open('knowledge.json')); "
                    "print('max_semana', d['max_semana']); "
                    "sys.exit(0 if d['max_semana'] >= 32 else 1)",
                ],
                "cwd": "dashboard/epibot/",
                "timeout_s": 30,
                "entorno": {"heredar": [], "fijar": {}},
            },
        ],
    }


def _repos(tmp_path: Path, politica: dict[str, Any] | None = None) -> dict[str, Any]:
    repo_b, head_b = fab.repo_backend(
        tmp_path / "repo_backend",
        politica=politica or _politica_cruda(),
        extra_rastreados={
            "reports/ProdDetails/produccion.csv": "motor,smape\nprophet,10\n",
            "reports/ProdDetails/validacion_semanal.html": "<p>semana 31</p>",
            "reports/otros/no_administrado.txt": "fuera del prefijo",
        },
    )
    repo_d, head_d = _repo(tmp_path / "repo_dashboard", SITIO)
    return {"repo_b": repo_b, "head_b": head_b, "repo_d": repo_d, "head_d": head_d}


def _hidrata(trabajo: Path, r: dict[str, Any]) -> None:
    from scripts.refresh_staging import main

    assert (
        main(
            [
                "hydrate",
                "--trabajo",
                str(trabajo),
                "--repo-backend",
                str(r["repo_b"]),
                "--head-backend",
                r["head_b"],
                "--padecimientos",
                ",".join(fab.PADECIMIENTOS),
            ]
        )
        == 0
    )


def _argv_materialize(trabajo: Path, r: dict[str, Any]) -> list[str]:
    return [
        "materialize",
        "--trabajo",
        str(trabajo),
        "--repo-backend",
        str(r["repo_b"]),
        "--head-backend",
        r["head_b"],
        "--repo-dashboard",
        str(r["repo_d"]),
        "--head-dashboard",
        r["head_d"],
    ]


def _argv_run_gates(trabajo: Path, r: dict[str, Any]) -> list[str]:
    return [
        "run-gates",
        "--trabajo",
        str(trabajo),
        "--head-backend",
        r["head_b"],
        "--destino-backend",
        str(r["repo_b"]),
        "--destino-dashboard",
        str(r["repo_d"]),
    ]


def _argv_seal(trabajo: Path, r: dict[str, Any]) -> list[str]:
    return [
        "seal",
        "--trabajo",
        str(trabajo),
        "--semilla",
        str(trabajo / "semilla.json"),
        "--head-backend",
        r["head_b"],
        "--head-dashboard",
        r["head_d"],
        "--semana-anterior",
        "2026,31",
        "--semana-nueva",
        "2026,32",
        "--padecimientos",
        "Dengue",
        "--destino-backend",
        str(r["repo_b"]),
        "--destino-dashboard",
        str(r["repo_d"]),
    ]


# ── 1 · materialize: todo lo rastreado bajo los prefijos, y nada más ────────


def test_materialize_extrae_el_arbol_administrado_completo(tmp_path: Path) -> None:
    r = _repos(tmp_path)
    trabajo = tmp_path / "trabajo"

    resultado = materializa_candidato(
        trabajo,
        {"backend": r["repo_b"], "dashboard": r["repo_d"]},
        {"backend": r["head_b"], "dashboard": r["head_d"]},
    )

    rastreados_d = _git(r["repo_d"], "ls-files").split()
    presentes = inventaria(trabajo / "outputs")
    assert {rel for rel in presentes if rel.startswith("dashboard/")} == {
        f"dashboard/{rel}" for rel in rastreados_d
    }, "el dashboard se materializa ENTERO: 41/41 en el sitio real"
    assert {rel for rel in presentes if rel.startswith("backend/")} == {
        "backend/reports/ProdDetails/produccion.csv",
        "backend/reports/ProdDetails/validacion_semanal.html",
        "backend/reports/ProdDetails/tabla.csv",
    }, "del backend sólo el prefijo administrado"
    assert resultado.archivos == len(presentes)
    semilla = json.loads((trabajo / "semilla.json").read_text(encoding="utf-8"))
    assert semilla == presentes
    assert not (trabajo / "outputs" / "dashboard" / ".git").exists()
    meta = json.loads((trabajo / "materializacion.json").read_text(encoding="utf-8"))
    assert meta["heads"] == {"backend": r["head_b"], "dashboard": r["head_d"]}
    # La política gobierna qué se materializa: coincide con la del HEAD.
    assert meta["politica"]["sha256"] == resultado.politica.sha256


def test_materialize_no_pisa_un_trabajo_existente(tmp_path: Path) -> None:
    r = _repos(tmp_path)
    trabajo = tmp_path / "trabajo"
    trabajo.mkdir()
    (trabajo / "del_usuario.txt").write_text("no me borres")

    with pytest.raises(StagingError, match="no se pisa"):
        materializa_candidato(
            trabajo,
            {"backend": r["repo_b"], "dashboard": r["repo_d"]},
            {"backend": r["head_b"], "dashboard": r["head_d"]},
        )
    assert (trabajo / "del_usuario.txt").read_text() == "no me borres"


def test_materialize_exige_heads_existentes_y_no_deja_medias(tmp_path: Path) -> None:
    r = _repos(tmp_path)
    trabajo = tmp_path / "trabajo"

    with pytest.raises(StagingError, match="git archive falló"):
        materializa_candidato(
            trabajo,
            {"backend": r["repo_b"], "dashboard": r["repo_d"]},
            {"backend": r["head_b"], "dashboard": "f" * 40},
        )
    assert not trabajo.exists(), "un candidato a medias se retira entero"


def test_materialize_rechaza_un_enlace_rastreado(tmp_path: Path) -> None:
    """Un HEAD que rastrea un enlace simbólico no se materializa: se rechaza al extraer."""
    r = _repos(tmp_path)
    (r["repo_d"] / "alias.html").symlink_to("index.html")
    _git(r["repo_d"], "add", "alias.html")
    _git(r["repo_d"], "commit", "-qm", "enlace")
    head_con_enlace = _git(r["repo_d"], "rev-parse", "HEAD").strip()

    with pytest.raises(StagingError, match="no es un archivo regular"):
        materializa_candidato(
            tmp_path / "trabajo",
            {"backend": r["repo_b"], "dashboard": r["repo_d"]},
            {"backend": r["head_b"], "dashboard": head_con_enlace},
        )
    assert not (tmp_path / "trabajo").exists()


def test_la_politica_del_head_decide_los_prefijos(tmp_path: Path) -> None:
    """Si la política del HEAD administra sólo `dashboard/`, del backend no sale nada."""
    politica = _politica_cruda()
    politica["prefijos_administrados"] = ["dashboard/"]
    r = _repos(tmp_path, politica)

    resultado = materializa_candidato(
        tmp_path / "trabajo",
        {"backend": r["repo_b"], "dashboard": r["repo_d"]},
        {"backend": r["head_b"], "dashboard": r["head_d"]},
    )

    assert not (tmp_path / "trabajo" / "outputs" / "backend").exists()
    assert resultado.politica.prefijos_administrados == ("dashboard/",)


# ── 2 · ensayo integral por el CLI (P0.12, sintético) ────────────────────────


def _composicion_de(raiz: Path, subruta: str, espacio: str) -> dict[str, str]:
    base = raiz / subruta if subruta else raiz
    arbol: dict[str, str] = {}
    for dirpath, _, filenames in os.walk(base):
        for nombre in filenames:
            ruta = Path(dirpath) / nombre
            rel = ruta.relative_to(raiz)
            if rel.parts[0] == ".git":
                continue
            import hashlib

            arbol[f"{espacio}/{rel.as_posix()}"] = hashlib.sha256(ruta.read_bytes()).hexdigest()
    return arbol


def test_ensayo_integral_materialize_gates_seal_apply_completitud(tmp_path: Path, capsys) -> None:
    """El cableado completo, y la invariante: composición aplicada == composición sellada."""
    from scripts.refresh_staging import main

    r = _repos(tmp_path)
    trabajo = tmp_path / "runs" / "_refresh" / "_trabajo"
    trabajo.parent.mkdir(parents=True)

    assert main(_argv_materialize(trabajo, r)) == 0
    assert "materializados" in capsys.readouterr().out
    _hidrata(trabajo, r)
    # Generación candidata: dos superficies cambian, una tabla del backend cambia.
    outputs = trabajo / "outputs"
    (outputs / "dashboard" / "index.html").write_text("<h1>semana 32</h1>", encoding="utf-8")
    (outputs / "dashboard" / "epibot" / "knowledge.json").write_text(
        fab.knowledge_json(max_semana=32)
    )
    (outputs / "backend" / "reports" / "ProdDetails" / "produccion.csv").write_text(
        "motor,smape\nprophet,9\n"
    )
    composicion_candidata, _ = calcula_composicion({}, inventaria(outputs), ())

    assert main(_argv_run_gates(trabajo, r)) == 0
    salida = capsys.readouterr().out
    assert "gate cifras       PASS" in salida and "gate rag          PASS" in salida
    assert main(_argv_seal(trabajo, r)) == 0
    (sellado,) = [d for d in trabajo.parent.iterdir() if (d / "manifest.json").is_file()]
    manifiesto = Manifiesto.lee(sellado / "manifest.json")
    assert manifiesto.composicion == composicion_candidata
    assert set(manifiesto.inventario) == {
        "dashboard/index.html",
        "dashboard/epibot/knowledge.json",
        "backend/reports/ProdDetails/produccion.csv",
    }
    assert manifiesto.modo == "aplicable"
    assert manifiesto.operaciones_dvc == ()
    assert set(manifiesto.inputs) == {
        "inputs/consolidado_base.csv",
        "inputs/consolidado_candidato.csv",
    }
    assert (sellado / "inputs" / "consolidado_base.csv").read_text() == fab.consolidado_csv()

    destinos = tmp_path / "runs" / "_release" / "par"
    argv_base = ["--manifiesto", str(sellado / "manifest.json"), "--destinos", str(destinos)]
    assert (
        main(
            [
                "prepare-worktrees",
                *argv_base,
                "--repo-backend",
                str(r["repo_b"]),
                "--repo-dashboard",
                str(r["repo_d"]),
            ]
        )
        == 0
    )
    assert main(["apply", *argv_base]) == 0
    assert main(["check-completeness", *argv_base]) == 0
    salida = capsys.readouterr().out
    assert "exactamente lo que el sello declara" in salida
    assert f"aplicada {manifiesto.composicion[:16]}" in salida

    registro = RegistroDestinos.lee(destinos)
    assert registro.estado == ESTADO_APLICADO
    wt_d = Path(registro.destinos["dashboard"].ruta)
    wt_b = Path(registro.destinos["backend"].ruta)
    # Bytes: el par contiene el sitio ENTERO en su versión nueva…
    assert (wt_d / "index.html").read_text() == "<h1>semana 32</h1>"
    assert (wt_d / "calass.html").read_text() == SITIO["calass.html"]
    assert (
        wt_b / "reports" / "ProdDetails" / "produccion.csv"
    ).read_text() == "motor,smape\nprophet,9\n"
    # …y su digest de composición es el sellado, recompuesto desde disco por la prueba.
    arbol = _composicion_de(wt_d, "", "dashboard") | _composicion_de(
        wt_b, "reports/ProdDetails", "backend"
    )
    assert calcula_composicion({}, arbol, ())[0] == manifiesto.composicion
    # Los repositorios canónicos siguen intactos.
    assert (r["repo_d"] / "index.html").read_text() == "<h1>semana 31</h1>"
    assert _git(r["repo_d"], "status", "--porcelain").strip() == ""
    assert _git(r["repo_b"], "status", "--porcelain").strip() == ""

    # Un byte tocado en el par con el MISMO tamaño: la completitud lo ve por digest.
    (wt_d / "Reports" / "index.html").write_text("<h1>galerix</h1>", encoding="utf-8")
    assert main(["check-completeness", *argv_base]) == 1
    salida = capsys.readouterr()
    assert "SOBRANTE: Reports/index.html" in salida.out
    assert "composición aplicada" in salida.err


def test_un_gate_de_contenido_que_falla_no_sella(tmp_path: Path, capsys) -> None:
    """El candidato cambia el índice pero no el conocimiento: el gate `rag` lo caza."""
    from scripts.refresh_staging import main

    r = _repos(tmp_path)
    trabajo = tmp_path / "trabajo"
    assert main(_argv_materialize(trabajo, r)) == 0
    (trabajo / "outputs" / "dashboard" / "index.html").write_text("<h1>semana 32</h1>")

    assert main(_argv_run_gates(trabajo, r)) == 1
    salida = capsys.readouterr().out
    assert "gate cifras       PASS" in salida
    assert "gate rag          FAIL (exit_code: terminó con código 1)" in salida
    assert main(_argv_seal(trabajo, r)) == 1
    assert "el gate rag declara FAIL" in capsys.readouterr().err
    assert not [d for d in tmp_path.iterdir() if (d / "manifest.json").is_file()]


def test_una_superficie_retirada_sin_permiso_no_sella(tmp_path: Path, capsys) -> None:
    """El generador retiró `calass.html`: el gate de conteo falla y, aunque no fallara,
    la política no permite esa retirada. Dos barreras; `seal` muestra la suya primero."""
    from scripts.refresh_staging import main

    r = _repos(tmp_path)
    trabajo = tmp_path / "trabajo"
    assert main(_argv_materialize(trabajo, r)) == 0
    (trabajo / "outputs" / "dashboard" / "calass.html").unlink()

    assert main(_argv_run_gates(trabajo, r)) == 1
    assert "gate cifras       FAIL (exit_code" in capsys.readouterr().out
    assert main(_argv_seal(trabajo, r)) == 1
    assert "no permite borrar: ['dashboard/calass.html']" in capsys.readouterr().err


def test_una_materializacion_parcial_no_cubre_el_censo(tmp_path: Path, capsys) -> None:
    """La siembra parcial de antes, reproducida: el censo la rechaza al sellar."""
    from scripts.refresh_staging import main

    r = _repos(tmp_path)
    trabajo = tmp_path / "trabajo"
    outputs = trabajo / "outputs"
    (outputs / "dashboard" / "epibot").mkdir(parents=True)
    for rel in ("index.html", "epibot/knowledge.json"):  # 2 de 8 superficies
        shutil.copyfile(r["repo_d"] / rel, outputs / "dashboard" / rel)
    assert (
        main(["snapshot", "--raiz", str(outputs), "--salida", str(trabajo / "semilla.json")]) == 0
    )
    (outputs / "dashboard" / "index.html").write_text("cambiado")
    politica_solo_rag = _politica_cruda()
    # El gate de cifras fallaría por conteo; se deja sólo `rag` para aislar el censo.
    politica_solo_rag["gates"] = [g for g in politica_solo_rag["gates"] if g["id"] == "rag"]
    (r["repo_b"] / "config" / "publication" / "politica_censo.json").write_text(
        json.dumps(politica_solo_rag, indent=2) + "\n"
    )
    _git(r["repo_b"], "commit", "-qam", "solo rag")
    r["head_b"] = _git(r["repo_b"], "rev-parse", "HEAD").strip()

    assert main(_argv_run_gates(trabajo, r)) == 1, "sin knowledge nuevo, rag falla; da igual"
    assert main(_argv_seal(trabajo, r)) == 1
    faltan = len(SUPERFICIES) - 2
    assert f"no cubre {faltan} superficie(s) del censo" in capsys.readouterr().err


def test_seal_no_admite_operaciones_dvc(tmp_path: Path) -> None:
    """P0.11, opción C: el manifiesto no autoriza DVC y no hay flag para declararlo."""
    from scripts.refresh_staging import main

    r = _repos(tmp_path)
    trabajo = tmp_path / "trabajo"
    assert main(_argv_materialize(trabajo, r)) == 0
    with pytest.raises(SystemExit) as salida:
        main([*_argv_seal(trabajo, r), "--operacion-dvc", "data/x.dvc"])
    assert salida.value.code == 2
