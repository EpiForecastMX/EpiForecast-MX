"""Controles del runner real de gates.

La pregunta que responde cada prueba es la misma: ¿puede alguien conseguir un sello con
gates «PASS» sin haberlos ejecutado, o habiéndolos ejecutado sobre otro árbol? Cada
control negativo dice por qué exactamente falla; un rc≠0 por otro motivo no cuenta.

Nada de aquí toca el frontend productivo ni datos reales: los gates son comandos inocuos
(`true`, `python -c …`) dentro de repositorios Git de usar y tirar.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

import pytest

from epiforecast.publication import gate_runner
from epiforecast.publication.gate_runner import ejecuta_gates
from epiforecast.publication.release_worktrees import aplica
from epiforecast.publication.weekly_staging import (
    CONFINAMIENTO_LISTO,
    DIR_EVIDENCIA,
    MODO_APLICABLE,
    VERSION_POLITICA,
    EvidenciaGates,
    GateSpec,
    Manifiesto,
    PoliticaCenso,
    StagingError,
    calcula_run_id_de,
    inventaria,
    verifica,
)

PYTHON = sys.executable
TRUE = shutil.which("true") or "/usr/bin/true"


# ── montaje ──────────────────────────────────────────────────────────────────


def _gate(
    nombre: str,
    argv: list[str] | None = None,
    *,
    cwd: str = "dashboard/",
    timeout_s: int = 30,
    heredar: tuple[str, ...] = (),
    fijar: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "id": nombre,
        "argv": argv or [TRUE],
        "cwd": cwd,
        "timeout_s": timeout_s,
        "entorno": {"heredar": list(heredar), "fijar": dict(fijar or {})},
    }


def _python(nombre: str, codigo: str, **kwargs: Any) -> dict[str, Any]:
    """Un gate que ejecuta Python con `-c`: absoluto, sin shell, salida determinista."""
    return _gate(nombre, [PYTHON, "-c", codigo], **kwargs)


def _politica_cruda(
    gates: list[dict[str, Any]],
    superficies: tuple[str, ...] = ("dashboard/index.html",),
) -> dict[str, Any]:
    return {
        "version": VERSION_POLITICA,
        "prefijos_administrados": ["dashboard/"],
        "patron_superficie": {
            "prefijo": "dashboard/",
            "sufijos": [".html", ".json"],
            "directorios_excluidos": ["node_modules"],
        },
        "superficies_verificables": sorted(superficies),
        "retirables": [],
        "gates": gates,
    }


def _politica(gates: list[dict[str, Any]], **kwargs: Any) -> PoliticaCenso:
    return PoliticaCenso.desde_bytes(json.dumps(_politica_cruda(gates, **kwargs)).encode())


def _staging(raiz: Path, contenido: str = "uno") -> Path:
    (raiz / "outputs" / "dashboard").mkdir(parents=True)
    (raiz / "outputs" / "dashboard" / "index.html").write_text(contenido, encoding="utf-8")
    return raiz


def _corre(raiz: Path, gates: list[dict[str, Any]], **kwargs: Any) -> EvidenciaGates:
    return ejecuta_gates(raiz, _politica(gates, **kwargs), destinos_vivos=())


def _repo_con_politica(raiz: Path, politica: dict[str, Any]) -> tuple[Path, str]:
    """Repositorio Git desechable con la política confirmada en su HEAD."""
    ruta = raiz / "config" / "publication" / "politica_censo.json"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(json.dumps(politica, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    git = ["git", "-C", str(raiz)]
    subprocess.run([*git, "init", "-q"], check=True, capture_output=True)
    subprocess.run([*git, "config", "user.email", "prueba@ejemplo"], check=True)
    subprocess.run([*git, "config", "user.name", "Prueba"], check=True)
    subprocess.run([*git, "add", "config/publication/politica_censo.json"], check=True)
    subprocess.run([*git, "commit", "-qm", "politica"], check=True, capture_output=True)
    head = subprocess.run(
        [*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    return raiz, head


def _argv_run_gates(trabajo: Path, repo: Path, head: str) -> list[str]:
    return [
        "run-gates",
        "--trabajo",
        str(trabajo),
        "--head-backend",
        head,
        "--destino-backend",
        str(repo),
        "--destino-dashboard",
        str(repo),
    ]


def _argv_seal(trabajo: Path, repo: Path, head: str, semilla: Path) -> list[str]:
    return [
        "seal",
        "--trabajo",
        str(trabajo),
        "--semilla",
        str(semilla),
        "--head-backend",
        head,
        "--head-dashboard",
        "b" * 40,
        "--digest-consolidado",
        "c" * 64,
        "--semana-anterior",
        "2026,30",
        "--semana-nueva",
        "2026,31",
        "--padecimientos",
        "Dengue",
        "--destino-backend",
        str(repo),
        "--destino-dashboard",
        str(repo),
    ]


def _reescribe_indice(raiz: Path, mutador) -> None:  # noqa: ANN001
    """Edita el índice y recalcula su sidecar: lo que haría quien quisiera «arreglarlo»."""
    ruta = raiz / DIR_EVIDENCIA / "indice.json"
    crudo = json.loads(ruta.read_text(encoding="utf-8"))
    mutador(crudo)
    cuerpo = json.dumps(crudo, indent=2, ensure_ascii=False, sort_keys=True).encode() + b"\n"
    ruta.write_bytes(cuerpo)
    (raiz / DIR_EVIDENCIA / "indice.sha256").write_text(
        hashlib.sha256(cuerpo).hexdigest() + "\n", encoding="utf-8"
    )


# ── 1 · control positivo: E2E sintético por el CLI ───────────────────────────


def test_e2e_gates_sinteticos_sellan_un_borrador_verificable(tmp_path: Path) -> None:
    """`snapshot` → `run-gates` → `seal`: evidencia real, copiada al sello y verificable.

    Los gates `cifras` y `rag` son comandos inocuos dentro de un repo temporal. Nada de
    esto toca el frontend ni datos reales.
    """
    from scripts.refresh_staging import main

    gates = [
        _python(
            "cifras",
            "import os, sys; print('superficies', sorted(os.listdir('.'))); sys.exit(0)",
        ),
        _python("rag", "print('rag: indice coherente')", cwd="dashboard/epibot/"),
    ]
    repo, head = _repo_con_politica(
        tmp_path / "repo",
        _politica_cruda(gates, superficies=("dashboard/index.html", "dashboard/epibot/kb.json")),
    )
    trabajo = _staging(tmp_path / "trabajo", "sembrado")
    (trabajo / "outputs" / "dashboard" / "epibot").mkdir()
    (trabajo / "outputs" / "dashboard" / "epibot" / "kb.json").write_text("{}", encoding="utf-8")
    semilla = tmp_path / "semilla.json"
    assert main(["snapshot", "--raiz", str(trabajo / "outputs"), "--salida", str(semilla)]) == 0
    # El refresh cambia una superficie y deja la otra intacta.
    (trabajo / "outputs" / "dashboard" / "index.html").write_text("semana 31", encoding="utf-8")
    inventario_antes = inventaria(trabajo / "outputs")

    assert main(_argv_run_gates(trabajo, repo, head)) == 0
    assert inventaria(trabajo / "outputs") == inventario_antes, "la evidencia no contamina outputs"
    evidencia = EvidenciaGates.lee(trabajo)
    assert evidencia.veredicto == "PASS"
    assert (
        (trabajo / DIR_EVIDENCIA / "cifras" / "stdout.bin")
        .read_bytes()
        .startswith(b"superficies ['epibot', 'index.html']")
    )

    assert main(_argv_seal(trabajo, repo, head, semilla)) == 0
    (sellado,) = [d for d in tmp_path.iterdir() if (d / "manifest.json").is_file()]
    manifiesto = Manifiesto.lee(sellado / "manifest.json")

    # Aplicable y sin motivo: P0.6 confina la instalación al par registrado.
    assert CONFINAMIENTO_LISTO is True
    assert manifiesto.modo == MODO_APLICABLE
    assert manifiesto.motivo_draft == ""
    # Sólo lo cambiado se inventaría; la composición es la del árbol completo.
    assert set(manifiesto.inventario) == {"dashboard/index.html"}
    assert manifiesto.composicion == evidencia.composicion
    resultados = manifiesto.resultados_pruebas
    assert set(resultados["gates"]) == {"cifras", "rag"}
    assert all(
        g["veredicto"] == "PASS" and g["exit_code"] == 0 for g in resultados["gates"].values()
    )
    assert resultados["gates"]["cifras"]["argv"] == gates[0]["argv"]
    assert set(resultados["evidencia"]) == {
        "gates/indice.json",
        "gates/indice.sha256",
        "gates/cifras/stdout.bin",
        "gates/cifras/stderr.bin",
        "gates/rag/stdout.bin",
        "gates/rag/stderr.bin",
    }
    assert set(resultados["observacional"]) == {"gates/observacional.json"}
    # La evidencia viaja dentro de la corrida sellada y entra en el identificador.
    assert (sellado / DIR_EVIDENCIA / "indice.json").is_file()
    assert manifiesto.run_id == calcula_run_id_de(manifiesto)
    assert "evidencia" in manifiesto.payload_canonico()["resultados_pruebas"]
    assert "observacional" not in manifiesto.payload_canonico()["resultados_pruebas"]
    verifica(sellado, manifiesto, head_backend=head, head_dashboard="b" * 40)
    # Y aun así no hay destino arbitrario: sin par registrado no se instala en ningún sitio.
    with pytest.raises(StagingError, match="no existe la raíz de destinos"):
        aplica(sellado, manifiesto, tmp_path / "sin_registro")
    assert not (tmp_path / "d").exists() and not (tmp_path / "b").exists()


def test_dos_ejecuciones_equivalentes_comparten_identidad_aunque_cambien_los_tiempos(
    tmp_path: Path, monkeypatch
) -> None:
    """Los tiempos son observacionales: no entran en el índice ni en el `run_id`."""
    relojes = iter(["2026-09-01T10:00:00.000000+00:00", "2026-09-01T10:00:01.000000+00:00"] * 4)
    monkeypatch.setattr(gate_runner, "_ahora", lambda: next(relojes))
    gates = [_python("cifras", "print('ok')"), _gate("rag")]

    uno = _corre(_staging(tmp_path / "uno"), gates)
    relojes = iter(["2027-01-01T00:00:00.000000+00:00", "2027-01-01T00:00:09.000000+00:00"] * 4)
    dos = _corre(_staging(tmp_path / "dos"), gates)

    assert (tmp_path / "uno" / DIR_EVIDENCIA / "indice.json").read_bytes() == (
        tmp_path / "dos" / DIR_EVIDENCIA / "indice.json"
    ).read_bytes()
    assert (tmp_path / "uno" / DIR_EVIDENCIA / "observacional.json").read_bytes() != (
        tmp_path / "dos" / DIR_EVIDENCIA / "observacional.json"
    ).read_bytes()
    assert uno.evidencia == dos.evidencia
    assert uno.observacional != dos.observacional
    assert uno.como_manifiesto()["gates"] == dos.como_manifiesto()["gates"]


# ── 2 · la interfaz para suministrar resultados ya no existe ────────────────


def test_no_existe_forma_de_suministrar_un_pass(tmp_path: Path) -> None:
    from scripts.refresh_staging import main

    repo, head = _repo_con_politica(tmp_path / "repo", _politica_cruda([_gate("cifras")]))
    trabajo = _staging(tmp_path / "trabajo")
    semilla = tmp_path / "semilla.json"
    semilla.write_text("{}", encoding="utf-8")
    fabricado = tmp_path / "pass.json"
    fabricado.write_text('{"cifras": {"veredicto": "PASS"}}', encoding="utf-8")

    with pytest.raises(SystemExit) as salida:
        main([*_argv_seal(trabajo, repo, head, semilla), "--resultados-pruebas", str(fabricado)])
    assert salida.value.code == 2  # argparse: argumento desconocido


def test_sellar_sin_haber_corrido_los_gates_aborta_antes_de_podar(tmp_path: Path, capsys) -> None:
    from scripts.refresh_staging import main

    repo, head = _repo_con_politica(tmp_path / "repo", _politica_cruda([_gate("cifras")]))
    trabajo = _staging(tmp_path / "trabajo")
    # La semilla ya contiene index.html intacto: si `seal` llegara a podar, lo borraría.
    semilla = tmp_path / "semilla.json"
    assert main(["snapshot", "--raiz", str(trabajo / "outputs"), "--salida", str(semilla)]) == 0

    assert main(_argv_seal(trabajo, repo, head, semilla)) == 1

    assert "no hay evidencia de gates" in capsys.readouterr().err
    # No podó: el árbol candidato sigue entero para poder correr los gates después.
    assert (trabajo / "outputs" / "dashboard" / "index.html").read_text() == "uno"


def test_seal_no_consume_evidencia_escrita_a_mano(tmp_path: Path) -> None:
    """Un `gates/` con sólo un índice que dice PASS no es evidencia."""
    raiz = _staging(tmp_path / "staging")
    (raiz / DIR_EVIDENCIA).mkdir()
    (raiz / DIR_EVIDENCIA / "indice.json").write_text(
        json.dumps({"esquema": "gates_evidencia/1", "veredicto": "PASS"}), encoding="utf-8"
    )

    with pytest.raises(StagingError, match="falta el sidecar"):
        EvidenciaGates.lee(raiz)


# ── 3 · el parser de la política rechaza todo lo que no sea un argv cerrado ──


@pytest.mark.parametrize(
    ("mutador", "mensaje"),
    [
        (lambda g: g.update(argv="true"), "una cadena de shell no es un argv"),
        (lambda g: g.update(argv=["sh", "-c", "true"]), "intérprete de órdenes"),
        (lambda g: g.update(argv=["/bin/bash", "-c", "true"]), "intérprete de órdenes"),
        (lambda g: g.update(argv=["PowerShell"]), "intérprete de órdenes"),
        (lambda g: g.update(shell=True), "claves desconocidas.*shell"),
        (lambda g: g.update(argv=[]), "lista no vacía"),
        (lambda g: g.update(argv=[""]), "vacío o con byte nulo"),
        (lambda g: g.update(argv=[TRUE, "a\x00b"]), "vacío o con byte nulo"),
        (lambda g: g.update(argv=[1]), "lista no vacía de cadenas"),
        (lambda g: g.update(argv=["./scripts/x.mjs"]), "ruta relativa"),
        (lambda g: g.update(cwd="dashboard"), "terminar en '/'"),
        (lambda g: g.update(cwd="../"), "componente inválido"),
        (lambda g: g.update(cwd="/tmp/"), "malformado"),
        (lambda g: g.update(cwd="otro/"), "no cuelga de una raíz"),
        (lambda g: g.update(cwd="backend/"), "no cae bajo ningún prefijo administrado"),
        (lambda g: g.update(cwd="dashboard/../x/"), "componente inválido"),
        (lambda g: g.update(timeout_s=0), "fuera de rango"),
        (lambda g: g.update(timeout_s="5"), "tiene que ser un entero"),
        (lambda g: g.update(timeout_s=True), "tiene que ser un entero"),
        (lambda g: g.update(timeout_s=10**9), "fuera de rango"),
        (lambda g: g.update(entorno=["PATH"]), "heredar"),
        (lambda g: g.update(entorno={"heredar": []}), "fijar"),
        (lambda g: g["entorno"].update(heredar=["1BAD"]), "variable de entorno inválida"),
        (lambda g: g["entorno"].update(fijar={"X": 1}), "nombre -> valor de texto"),
        (lambda g: g["entorno"].update(heredar=["X"], fijar={"X": "1"}), "hereda y fija"),
        (lambda g: g["entorno"].update(heredar=["X", "X"]), "duplicados"),
        (lambda g: g.update(id="Cifras"), "id de gate inválido"),
        (lambda g: g.pop("timeout_s"), "incompleto"),
    ],
)
def test_el_parser_rechaza_gates_que_no_son_un_argv_cerrado(mutador, mensaje: str) -> None:
    gate = _gate("cifras")
    mutador(gate)

    with pytest.raises(StagingError, match=mensaje):
        _politica([gate])


def test_la_forma_censo_1_de_gates_ya_no_se_lee() -> None:
    """`"gates": ["cifras", "rag"]` era un nombre sin comando: la v1 se rechaza entera."""
    cruda = _politica_cruda([_gate("cifras")])
    cruda["gates"] = ["cifras", "rag"]
    with pytest.raises(StagingError, match="no como str"):
        PoliticaCenso.desde_bytes(json.dumps(cruda).encode())

    cruda = _politica_cruda([_gate("cifras")])
    cruda["version"] = "censo/1"
    with pytest.raises(StagingError, match="otra versión"):
        PoliticaCenso.desde_bytes(json.dumps(cruda).encode())


def test_un_gate_legitimo_se_parsea_tal_cual() -> None:
    spec = GateSpec.desde_dict(
        _gate(
            "cifras", ["node", "scripts/x.mjs", "--silent"], heredar=("PATH",), fijar={"CI": "1"}
        ),
        ("dashboard/",),
    )

    assert spec.argv == ("node", "scripts/x.mjs", "--silent")
    assert spec.heredar == ("PATH",)
    assert spec.fijar == (("CI", "1"),)


# ── 4 · el veredicto se deriva; cada forma de no pasar tiene su causa ────────


def test_pass_solo_con_codigo_cero(tmp_path: Path) -> None:
    evidencia = _corre(
        _staging(tmp_path / "s"),
        [_python("cifras", "import sys; sys.exit(0)"), _python("rag", "import sys; sys.exit(1)")],
    )

    assert evidencia.veredicto == "FAIL"
    assert evidencia.gates["cifras"].veredicto == "PASS"
    assert evidencia.gates["cifras"].causa == ""
    assert evidencia.gates["rag"].veredicto == "FAIL"
    assert evidencia.gates["rag"].causa == "exit_code"
    assert evidencia.gates["rag"].exit_code == 1


def test_un_gate_que_devuelve_1_no_sella(tmp_path: Path, capsys) -> None:
    from scripts.refresh_staging import main

    repo, head = _repo_con_politica(
        tmp_path / "repo",
        _politica_cruda([_python("cifras", "import sys; print('mal'); sys.exit(3)")]),
    )
    trabajo = _staging(tmp_path / "trabajo")
    semilla = tmp_path / "semilla.json"
    semilla.write_text("{}", encoding="utf-8")

    assert main(_argv_run_gates(trabajo, repo, head)) == 1
    assert "al menos un gate no pasó" in capsys.readouterr().err
    assert main(_argv_seal(trabajo, repo, head, semilla)) == 1
    assert "cifras declara FAIL (exit_code: terminó con código 3)" in capsys.readouterr().err
    assert not [d for d in tmp_path.iterdir() if (d / "manifest.json").is_file()]


def test_un_gate_que_muere_por_senal_es_fail(tmp_path: Path) -> None:
    evidencia = _corre(
        _staging(tmp_path / "s"),
        [_python("cifras", "import os, signal; os.kill(os.getpid(), signal.SIGKILL)")],
    )
    registro = evidencia.gates["cifras"]

    assert registro.veredicto == "FAIL"
    assert registro.causa == "senal"
    assert registro.senal == 9
    assert registro.exit_code is None
    assert "SIGKILL" in registro.detalle


def test_un_gate_que_vence_el_plazo_es_fail_y_se_mata(tmp_path: Path) -> None:
    inicio = time.monotonic()
    evidencia = _corre(
        _staging(tmp_path / "s"),
        [
            _python(
                "cifras", "import time; print('empiezo', flush=True); time.sleep(60)", timeout_s=1
            )
        ],
    )
    registro = evidencia.gates["cifras"]

    assert time.monotonic() - inicio < 15, "el runner no espera al proceso más allá del plazo"
    assert registro.veredicto == "FAIL"
    assert registro.causa == "timeout"
    assert registro.exit_code is None
    assert (tmp_path / "s" / DIR_EVIDENCIA / "cifras" / "stdout.bin").read_bytes() == b"empiezo\n"


@pytest.mark.parametrize(
    "argv",
    [["no-existe-en-ningun-path-xyz"], ["/no/existe/tampoco"], [TRUE.rsplit("/", 1)[-1]]],
    ids=("nombre_sin_path", "absoluto_ausente", "nombre_con_path_vacio"),
)
def test_un_ejecutable_ausente_es_fail(tmp_path: Path, argv: list[str]) -> None:
    """Sin `PATH` en el entorno permitido, un nombre desnudo no se resuelve: falla cerrado."""
    evidencia = _corre(_staging(tmp_path / "s"), [_gate("cifras", argv)])

    assert evidencia.gates["cifras"].veredicto == "FAIL"
    assert evidencia.gates["cifras"].causa == "ejecutable_ausente"


def test_un_nombre_se_resuelve_solo_con_el_path_permitido(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", str(Path(TRUE).parent))
    evidencia = _corre(
        _staging(tmp_path / "s"), [_gate("cifras", [Path(TRUE).name], heredar=("PATH",))]
    )

    assert evidencia.gates["cifras"].veredicto == "PASS"


def test_una_excepcion_al_lanzar_es_fail(tmp_path: Path, monkeypatch) -> None:
    def popen_roto(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("fallo inyectado al lanzar")

    monkeypatch.setattr(gate_runner.subprocess, "Popen", popen_roto)
    evidencia = _corre(_staging(tmp_path / "s"), [_gate("cifras")])

    assert evidencia.gates["cifras"].veredicto == "FAIL"
    assert evidencia.gates["cifras"].causa == "excepcion"
    assert "fallo inyectado" in evidencia.gates["cifras"].detalle


def test_un_cwd_que_no_existe_en_el_candidato_es_fail(tmp_path: Path) -> None:
    evidencia = _corre(_staging(tmp_path / "s"), [_gate("cifras", cwd="dashboard/epibot/")])

    assert evidencia.gates["cifras"].causa == "cwd_invalido"
    assert "no existe en la composición candidata" in evidencia.gates["cifras"].detalle


def test_el_entorno_es_exactamente_el_permitido(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CANARIO_DEL_OPERADOR", "no debería llegar")
    evidencia = _corre(
        _staging(tmp_path / "s"),
        [
            _python(
                "cifras",
                "import os; print(sorted(k for k in os.environ if k in "
                "('CANARIO_DEL_OPERADOR', 'HOME', 'X_GATE')))",
                fijar={"X_GATE": "1"},
            )
        ],
    )

    assert (
        tmp_path / "s" / DIR_EVIDENCIA / "cifras" / "stdout.bin"
    ).read_bytes() == b"['X_GATE']\n"


# ── 5 · la composición: se mide entera, y un byte movido invalida ────────────


def test_un_gate_que_muta_la_composicion_es_fail_y_los_siguientes_no_corren(
    tmp_path: Path,
) -> None:
    raiz = _staging(tmp_path / "s")
    evidencia = _corre(
        raiz,
        [
            _python("cifras", "open('index.html', 'w').write('mutado por el gate')"),
            _python("rag", "print('nunca')"),
        ],
    )

    assert evidencia.gates["cifras"].veredicto == "FAIL"
    assert evidencia.gates["cifras"].causa == "mutacion"
    assert evidencia.gates["cifras"].exit_code == 0, "el gate terminó bien y aun así no pasa"
    assert "dashboard/index.html" in evidencia.gates["cifras"].detalle
    assert evidencia.gates["rag"].causa == "no_ejecutado"
    assert (raiz / DIR_EVIDENCIA / "rag" / "stdout.bin").read_bytes() == b""


def test_un_gate_que_anade_un_archivo_tambien_muta(tmp_path: Path) -> None:
    evidencia = _corre(
        _staging(tmp_path / "s"), [_python("cifras", "open('colado.html', 'w').write('x')")]
    )

    assert evidencia.gates["cifras"].causa == "mutacion"
    assert "1 añadido(s) ['dashboard/colado.html']" in evidencia.gates["cifras"].detalle


def test_la_evidencia_de_otra_composicion_no_sirve(tmp_path: Path) -> None:
    """Se corren los gates en A y se traslada su `gates/` a B, que tiene otros bytes."""
    a = _staging(tmp_path / "a", "uno")
    b = _staging(tmp_path / "b", "dos")
    politica = _politica([_gate("cifras")])
    ejecuta_gates(a, politica, destinos_vivos=())
    shutil.copytree(a / DIR_EVIDENCIA, b / DIR_EVIDENCIA)
    evidencia = EvidenciaGates.lee(b)  # íntegra en sí misma…

    from epiforecast.publication.weekly_staging import calcula_composicion, valida_gates

    composicion_b, _ = calcula_composicion({}, inventaria(b / "outputs"), ())
    with pytest.raises(StagingError, match="algo cambió después de los gates"):
        valida_gates(evidencia, politica, composicion_b)  # …pero no es de este árbol


def test_la_evidencia_se_corre_sobre_el_arbol_completo_antes_de_podar(tmp_path: Path) -> None:
    """La composición de la evidencia es la del árbol entero: semilla intacta incluida."""
    raiz = _staging(tmp_path / "s", "intacto")
    (raiz / "outputs" / "dashboard" / "nuevo.html").write_text("nuevo", encoding="utf-8")
    evidencia = _corre(raiz, [_gate("cifras")])

    from epiforecast.publication.weekly_staging import calcula_composicion

    completa, _ = calcula_composicion({}, inventaria(raiz / "outputs"), ())
    solo_nuevo, _ = calcula_composicion(
        {}, {"dashboard/nuevo.html": inventaria(raiz / "outputs")["dashboard/nuevo.html"]}, ()
    )
    assert evidencia.composicion == completa
    assert evidencia.composicion != solo_nuevo


# ── 6 · la evidencia es exacta: ni editada, ni incompleta, ni con extras ─────


def test_editar_stdout_tras_ejecutar_rompe_la_evidencia(tmp_path: Path) -> None:
    raiz = _staging(tmp_path / "s")
    _corre(raiz, [_python("cifras", "print('41 superficies')")])
    (raiz / DIR_EVIDENCIA / "cifras" / "stdout.bin").write_bytes(b"42 superficies\n")

    with pytest.raises(StagingError, match="stdout del gate cifras no coincide"):
        EvidenciaGates.lee(raiz)


def test_editar_el_indice_sin_recalcular_el_sidecar_rompe(tmp_path: Path) -> None:
    raiz = _staging(tmp_path / "s")
    _corre(raiz, [_python("cifras", "import sys; sys.exit(1)")])
    ruta = raiz / DIR_EVIDENCIA / "indice.json"
    ruta.write_text(ruta.read_text(encoding="utf-8").replace('"FAIL"', '"PASS"'), encoding="utf-8")

    with pytest.raises(StagingError, match="indice.sha256"):
        EvidenciaGates.lee(raiz)


def test_un_pass_editado_con_sidecar_recalculado_sigue_sin_cuadrar(tmp_path: Path) -> None:
    """Quien recalcula el sidecar no es el problema; el registro sigue diciendo exit 1."""
    raiz = _staging(tmp_path / "s")
    _corre(raiz, [_python("cifras", "import sys; sys.exit(1)")])

    def blanquea(d: dict) -> None:
        d["veredicto"] = "PASS"
        d["gates"]["cifras"].update(veredicto="PASS", causa="")

    _reescribe_indice(raiz, blanquea)

    with pytest.raises(StagingError, match="declara PASS sin código 0"):
        EvidenciaGates.lee(raiz)


@pytest.mark.parametrize(
    ("mutacion", "mensaje"),
    [
        ("enlace", "enlace simbólico"),
        ("extra", "que nadie produjo"),
        ("falta", "faltan"),
    ],
)
def test_evidencia_con_enlace_extra_o_faltante_se_rechaza(
    tmp_path: Path, mutacion: str, mensaje: str
) -> None:
    raiz = _staging(tmp_path / "s")
    _corre(raiz, [_gate("cifras")])
    carpeta = raiz / DIR_EVIDENCIA
    if mutacion == "enlace":
        (carpeta / "cifras" / "stdout.bin").unlink()
        (carpeta / "cifras" / "stdout.bin").symlink_to(carpeta / "cifras" / "stderr.bin")
    elif mutacion == "extra":
        (carpeta / "cifras" / "notas.txt").write_text("añadido a mano", encoding="utf-8")
    else:
        (carpeta / "cifras" / "stderr.bin").unlink()

    with pytest.raises(StagingError, match=mensaje):
        EvidenciaGates.lee(raiz)


def test_una_corrida_de_gates_no_se_sobrescribe(tmp_path: Path) -> None:
    raiz = _staging(tmp_path / "s")
    _corre(raiz, [_gate("cifras")])

    with pytest.raises(StagingError, match="ya existe evidencia"):
        _corre(raiz, [_gate("cifras")])


def test_un_gates_preplantado_como_enlace_no_se_usa(tmp_path: Path) -> None:
    raiz = _staging(tmp_path / "s")
    ajeno = tmp_path / "ajeno"
    ajeno.mkdir()
    (raiz / DIR_EVIDENCIA).symlink_to(ajeno, target_is_directory=True)

    with pytest.raises(StagingError, match="ya existe evidencia"):
        _corre(raiz, [_gate("cifras")])
    assert list(ajeno.iterdir()) == []


# ── 7 · el cwd no escapa ni cae en un destino vivo ───────────────────────────


def test_el_staging_no_puede_solaparse_con_un_destino_vivo(tmp_path: Path) -> None:
    vivo = tmp_path / "sitio_real"
    raiz = _staging(vivo / "staging_dentro")

    with pytest.raises(StagingError, match="se solapan"):
        ejecuta_gates(raiz, _politica([_gate("cifras")]), destinos_vivos=(vivo,))
    assert not (raiz / DIR_EVIDENCIA).exists()


def test_un_cwd_enlazado_no_se_ejecuta(tmp_path: Path) -> None:
    """Un `dashboard/` que es enlace a otro sitio: el inventario lo rechaza antes de correr."""
    raiz = tmp_path / "s"
    (raiz / "outputs").mkdir(parents=True)
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    (fuera / "index.html").write_text("ajeno", encoding="utf-8")
    (raiz / "outputs" / "dashboard").symlink_to(fuera, target_is_directory=True)

    with pytest.raises(StagingError, match="enlace simbólico"):
        _corre(raiz, [_gate("cifras")])
    assert not (raiz / DIR_EVIDENCIA).exists()


# ── 8 · después del sello: alterar la evidencia rompe la verificación ────────


def _sella_por_cli(tmp_path: Path, gates: list[dict[str, Any]]) -> tuple[Path, Manifiesto, str]:
    from scripts.refresh_staging import main

    repo, head = _repo_con_politica(tmp_path / "repo", _politica_cruda(gates))
    trabajo = _staging(tmp_path / "trabajo")
    semilla = tmp_path / "semilla.json"
    semilla.write_text("{}", encoding="utf-8")
    assert main(_argv_run_gates(trabajo, repo, head)) == 0
    assert main(_argv_seal(trabajo, repo, head, semilla)) == 0
    (sellado,) = [d for d in tmp_path.iterdir() if (d / "manifest.json").is_file()]
    return sellado, Manifiesto.lee(sellado / "manifest.json"), head


@pytest.mark.parametrize("archivo", ["cifras/stdout.bin", "observacional.json", "indice.json"])
def test_alterar_la_evidencia_sellada_rompe_la_verificacion(tmp_path: Path, archivo: str) -> None:
    sellado, manifiesto, head = _sella_por_cli(tmp_path, [_python("cifras", "print('ok')")])
    ruta = sellado / DIR_EVIDENCIA / archivo
    ruta.write_bytes(ruta.read_bytes() + b" ")

    with pytest.raises(StagingError, match="evidencia de gates alterada"):
        verifica(sellado, manifiesto, head_backend=head, head_dashboard="b" * 40)


def test_retirar_o_anadir_evidencia_sellada_rompe_la_verificacion(tmp_path: Path) -> None:
    sellado, manifiesto, head = _sella_por_cli(tmp_path, [_gate("cifras")])
    (sellado / DIR_EVIDENCIA / "cifras" / "stderr.bin").unlink()
    with pytest.raises(StagingError, match="falta evidencia"):
        verifica(sellado, manifiesto, head_backend=head, head_dashboard="b" * 40)

    (sellado / DIR_EVIDENCIA / "cifras" / "stderr.bin").write_bytes(b"")
    (sellado / DIR_EVIDENCIA / "extra.log").write_text("x", encoding="utf-8")
    with pytest.raises(StagingError, match="fuera del inventario"):
        verifica(sellado, manifiesto, head_backend=head, head_dashboard="b" * 40)


def test_editar_el_registro_de_un_gate_en_el_manifiesto_rompe_el_run_id(tmp_path: Path) -> None:
    sellado, _, head = _sella_por_cli(tmp_path, [_gate("cifras")])
    ruta = sellado / "manifest.json"
    crudo = json.loads(ruta.read_text(encoding="utf-8"))
    crudo["resultados_pruebas"]["gates"]["cifras"]["argv"] = ["node", "otro.mjs"]
    cuerpo = json.dumps(crudo, indent=2, ensure_ascii=False).encode()
    ruta.write_bytes(cuerpo)
    (sellado / "manifest.sha256").write_text(
        hashlib.sha256(cuerpo).hexdigest() + "\n", encoding="utf-8"
    )

    with pytest.raises(StagingError, match="run_id no deriva"):
        Manifiesto.lee(ruta)


def test_sellar_dos_veces_reutiliza_aunque_los_tiempos_difieran(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """Mismo árbol, misma política, gates corridos dos veces con relojes distintos.

    El sello se reutiliza y no se reescribe: lo observacional no gobierna la identidad.
    """
    from scripts.refresh_staging import main

    relojes = iter(f"2026-09-01T10:00:{i:02d}.000000+00:00" for i in range(60))
    monkeypatch.setattr(gate_runner, "_ahora", lambda: next(relojes))
    repo, head = _repo_con_politica(tmp_path / "repo", _politica_cruda([_gate("cifras")]))
    semilla = tmp_path / "semilla.json"
    semilla.write_text("{}", encoding="utf-8")
    a = _staging(tmp_path / "a")
    assert main(_argv_run_gates(a, repo, head)) == 0
    assert main(_argv_seal(a, repo, head, semilla)) == 0
    (sellado,) = [d for d in tmp_path.iterdir() if (d / "manifest.json").is_file()]
    antes = (sellado / "manifest.json").read_bytes()

    b = _staging(tmp_path / "b")
    assert main(_argv_run_gates(b, repo, head)) == 0
    # Relojes distintos por construcción; la corrida sellada conserva los de `a`.
    assert (sellado / DIR_EVIDENCIA / "observacional.json").read_bytes() != (
        b / DIR_EVIDENCIA / "observacional.json"
    ).read_bytes()
    assert (sellado / DIR_EVIDENCIA / "indice.json").read_bytes() == (
        b / DIR_EVIDENCIA / "indice.json"
    ).read_bytes()
    assert main([*_argv_seal(b, repo, head, semilla), "--destino-final", str(sellado)]) == 0

    assert "se reutiliza" in capsys.readouterr().out
    assert (sellado / "manifest.json").read_bytes() == antes


# ── 9 · la política sale del HEAD sellado, no del disco ─────────────────────


def test_run_gates_lee_la_politica_del_head(tmp_path: Path, capsys) -> None:
    from scripts.refresh_staging import main

    repo, head = _repo_con_politica(tmp_path / "repo", _politica_cruda([_gate("cifras")]))
    # Se cambia el comando en el árbol de trabajo, sin confirmarlo.
    ruta = repo / "config" / "publication" / "politica_censo.json"
    ruta.write_text(
        json.dumps(_politica_cruda([_python("cifras", "print('otro comando')")])),
        encoding="utf-8",
    )
    trabajo = _staging(tmp_path / "trabajo")

    assert main(_argv_run_gates(trabajo, repo, head)) == 1
    assert "difiere de la versión" in capsys.readouterr().err
    assert not (trabajo / DIR_EVIDENCIA).exists()


def test_la_evidencia_no_escribe_dentro_de_outputs(tmp_path: Path) -> None:
    raiz = _staging(tmp_path / "s")
    antes = inventaria(raiz / "outputs")
    _corre(raiz, [_gate("cifras"), _gate("rag")])

    assert inventaria(raiz / "outputs") == antes
    assert sorted(p.name for p in (raiz / DIR_EVIDENCIA).iterdir()) == [
        "cifras",
        "indice.json",
        "indice.sha256",
        "observacional.json",
        "rag",
    ]
    assert not os.path.lexists(raiz / "outputs" / DIR_EVIDENCIA)
