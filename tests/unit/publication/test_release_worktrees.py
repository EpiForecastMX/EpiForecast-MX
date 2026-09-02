"""Controles de P0.6: `apply` sólo instala en el par de worktrees desechables registrado.

Cada prueba responde a la misma pregunta: ¿puede `apply` tocar un directorio que no sea el
par creado para ese `run_id`, en el HEAD exacto, limpio, verificado con git y bajo lock? Y
cuando algo se tuerce, ¿queda el par inválido en vez de a medias?

Todo ocurre en repositorios Git de usar y tirar; los repositorios canónicos del proyecto
no se tocan.
"""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import pytest

from epiforecast.publication import release_worktrees
from epiforecast.publication.gate_runner import ejecuta_gates
from epiforecast.publication.release_worktrees import (
    ESTADO_APLICADO,
    ESTADO_DESCARTADO,
    ESTADO_EN_CURSO,
    ESTADO_INVALIDO,
    ESTADO_LISTO,
    RegistroDestinos,
    aplica,
    descarta_worktrees,
    prepara_worktrees,
)
from epiforecast.publication.weekly_staging import (
    MODO_APLICABLE,
    MODO_DRAFT,
    MOTIVO_P06,
    VERSION_POLITICA,
    AutoridadLapidas,
    Manifiesto,
    PoliticaCenso,
    SelloEntrada,
    StagingError,
    calcula_baseline,
    calcula_run_id_de,
    poda_a_cambiados,
    sella,
    snapshot_digests,
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


def _politica_cruda(*, con_lapida: bool = False) -> dict[str, Any]:
    superficies = ["dashboard/index.html", "dashboard/epibot/knowledge.json"]
    retirables: list[str] = []
    if con_lapida:
        superficies.append("dashboard/obsoleto.html")
        retirables.append("dashboard/obsoleto.html")
    return {
        "version": VERSION_POLITICA,
        "prefijos_administrados": ["backend/reports/ProdDetails/", "dashboard/"],
        "patron_superficie": {
            "prefijo": "dashboard/",
            "sufijos": [".html", ".json"],
            "directorios_excluidos": ["node_modules"],
        },
        "superficies_verificables": sorted(superficies),
        "retirables": retirables,
        "gates": [
            {
                "id": "cifras",
                "argv": [TRUE],
                "cwd": "dashboard/",
                "timeout_s": 30,
                "entorno": {"heredar": [], "fijar": {}},
            }
        ],
    }


@dataclass
class Corrida:
    repo_backend: Path
    head_backend: str
    repo_dashboard: Path
    head_dashboard: str
    staging: Path
    manifiesto: Manifiesto

    @property
    def repos(self) -> dict[str, Path]:
        return {"backend": self.repo_backend, "dashboard": self.repo_dashboard}

    @property
    def ruta_manifiesto(self) -> Path:
        return self.staging / "manifest.json"


def _fija_modo(corrida: Corrida, modo: str) -> None:
    """Fuerza el modo del sello en disco (borrador o aplicable) y recalcula su identidad."""
    manifiesto = corrida.manifiesto
    manifiesto.modo = modo
    manifiesto.motivo_draft = MOTIVO_P06 if modo == MODO_DRAFT else ""
    manifiesto.run_id = calcula_run_id_de(manifiesto)
    manifiesto.escribe(corrida.ruta_manifiesto)


def _corrida(
    tmp_path: Path,
    *,
    aplicable: bool = True,
    con_lapida: bool = False,
    canonico_sucio: bool = False,
) -> Corrida:
    """Repos canónicos + staging sellado por el flujo real: siembra, cambio, gates, poda, sello.

    `canonico_sucio` deja una edición SIN confirmar en el backend canónico antes de sellar:
    el baseline la registra, y el worktree desprendido en el HEAD no la tiene.
    """
    politica = _politica_cruda(con_lapida=con_lapida)
    repo_b, head_b = _repo(
        tmp_path / "repo_backend",
        {
            "config/publication/politica_censo.json": json.dumps(politica, indent=2) + "\n",
            "reports/ProdDetails/tabla.csv": "viejo\n",
        },
    )
    archivos_d = {"index.html": "semana 31", "epibot/knowledge.json": '{"semana": 31}'}
    if con_lapida:
        archivos_d["obsoleto.html"] = "ya no se publica"
    repo_d, head_d = _repo(tmp_path / "repo_dashboard", archivos_d)

    staging = tmp_path / "staging"
    outputs = staging / "outputs"
    for rel in archivos_d:
        destino = outputs / "dashboard" / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo_d / rel, destino)
    (outputs / "backend" / "reports" / "ProdDetails").mkdir(parents=True)
    shutil.copyfile(
        repo_b / "reports" / "ProdDetails" / "tabla.csv",
        outputs / "backend" / "reports" / "ProdDetails" / "tabla.csv",
    )
    semilla = snapshot_digests(outputs)
    # «Generación candidata»: cambia una superficie y una tabla; retira la obsoleta.
    (outputs / "dashboard" / "index.html").write_text("semana 32", encoding="utf-8")
    (outputs / "backend" / "reports" / "ProdDetails" / "tabla.csv").write_text("nuevo\n")
    if con_lapida:
        (outputs / "dashboard" / "obsoleto.html").unlink()

    if canonico_sucio:
        (repo_b / "reports" / "ProdDetails" / "tabla.csv").write_text("sucio\n", encoding="utf-8")
    politica_head = PoliticaCenso.del_head(repo_b, head_b)
    ejecuta_gates(staging, politica_head, destinos_vivos={"backend": repo_b, "dashboard": repo_d})
    fab.hidrata_minimo(staging, head_backend=head_b)
    poda = poda_a_cambiados(outputs, semilla)
    tombstones = tuple(sorted(poda.eliminados_reales))
    manifiesto = sella(
        staging,
        SelloEntrada(
            head_backend=head_b,
            head_dashboard=head_d,
            semana_anterior="2026,31",
            semana_nueva="2026,32",
            padecimientos_autorizados=("Dengue",),
        ),
        semilla=semilla,
        # El baseline se toma contra los repositorios canónicos, limpios en su HEAD: es
        # exactamente el estado que tendrá un worktree desprendido en ese HEAD.
        baseline=calcula_baseline(
            {"backend": repo_b, "dashboard": repo_d}, set(poda.cambiados) | set(tombstones)
        ),
        politica=politica_head,
        tombstones=tombstones,
        autoridad_lapidas=AutoridadLapidas(
            eliminados_reales=poda.eliminados_reales, allowlist=politica_head.retirables
        ),
        contrato=fab.CONTRATO,
    )
    corrida = Corrida(repo_b, head_b, repo_d, head_d, staging, manifiesto)
    _fija_modo(corrida, MODO_APLICABLE if aplicable else MODO_DRAFT)
    return corrida


def _reescribe_registro(raiz: Path, mutador) -> None:  # noqa: ANN001
    """Edita el registro y recalcula su digest embebido: lo que haría quien lo tocara."""
    ruta = raiz / "registro.json"
    crudo = json.loads(ruta.read_text(encoding="utf-8"))
    mutador(crudo)
    crudo["sha256"] = release_worktrees._digest_registro(crudo)
    cuerpo = json.dumps(crudo, indent=2, ensure_ascii=False, sort_keys=True).encode() + b"\n"
    ruta.write_bytes(cuerpo)


def _worktrees_de(repo: Path) -> list[str]:
    return [
        linea.split(" ", 1)[1]
        for linea in _git(repo, "worktree", "list", "--porcelain").splitlines()
        if linea.startswith("worktree ")
    ]


# ── 1 · control positivo ─────────────────────────────────────────────────────


def test_prepare_y_apply_instalan_solo_en_el_par_registrado(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"

    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)

    assert registro.estado == ESTADO_LISTO
    assert (raiz / "apply.lock").is_file()
    wt_d = Path(registro.destinos["dashboard"].ruta)
    wt_b = Path(registro.destinos["backend"].ruta)
    assert (wt_d / "index.html").read_text() == "semana 31"
    assert str(wt_d) in _worktrees_de(c.repo_dashboard)

    instalados = aplica(c.staging, c.manifiesto, raiz)

    assert set(instalados) == {"dashboard/index.html", "backend/reports/ProdDetails/tabla.csv"}
    assert (wt_d / "index.html").read_text() == "semana 32"
    assert (wt_b / "reports" / "ProdDetails" / "tabla.csv").read_text() == "nuevo\n"
    assert (wt_d / "epibot" / "knowledge.json").read_text() == '{"semana": 31}'
    assert RegistroDestinos.lee(raiz).estado == ESTADO_APLICADO
    # Los repositorios canónicos no cambian ni un byte.
    assert (c.repo_dashboard / "index.html").read_text() == "semana 31"
    assert (c.repo_backend / "reports" / "ProdDetails" / "tabla.csv").read_text() == "viejo\n"
    assert _git(c.repo_dashboard, "status", "--porcelain").strip() == ""
    assert _git(c.repo_backend, "status", "--porcelain").strip() == ""
    assert not list(wt_d.rglob("*.part")) and not list(wt_d.rglob("*.prev"))


def test_repetir_un_apply_completado_es_un_no_op_verificado(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    wt_d = Path(registro.destinos["dashboard"].ruta)
    primero = aplica(c.staging, c.manifiesto, raiz)
    mtime = (wt_d / "index.html").stat().st_mtime_ns

    assert aplica(c.staging, c.manifiesto, raiz) == primero
    assert (wt_d / "index.html").stat().st_mtime_ns == mtime, "no reinstala"
    assert RegistroDestinos.lee(raiz).estado == ESTADO_APLICADO

    # Pero si alguien tocó el par después, la repetición no lo tapa.
    (wt_d / "index.html").write_text("editado después", encoding="utf-8")
    with pytest.raises(StagingError, match="digest final discordante"):
        aplica(c.staging, c.manifiesto, raiz)


def test_las_lapidas_se_retiran_del_par(tmp_path: Path) -> None:
    c = _corrida(tmp_path, con_lapida=True)
    assert c.manifiesto.tombstones == ("dashboard/obsoleto.html",)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    wt_d = Path(registro.destinos["dashboard"].ruta)
    assert (wt_d / "obsoleto.html").exists()

    aplica(c.staging, c.manifiesto, raiz)

    assert not (wt_d / "obsoleto.html").exists()
    assert (c.repo_dashboard / "obsoleto.html").exists(), "el canónico conserva el archivo"


# ── 2 · no hay destino arbitrario ────────────────────────────────────────────


def test_apply_ya_no_acepta_rutas_de_destino(tmp_path: Path) -> None:
    from scripts.refresh_staging import main

    c = _corrida(tmp_path)
    with pytest.raises(SystemExit) as salida:
        main(
            [
                "apply",
                "--manifiesto",
                str(c.ruta_manifiesto),
                "--destino-backend",
                str(tmp_path / "libre_b"),
                "--destino-dashboard",
                str(tmp_path / "libre_d"),
            ]
        )
    assert salida.value.code == 2
    assert not (tmp_path / "libre_d").exists()


def test_un_manifiesto_borrador_no_tiene_destinos_ni_se_aplica(tmp_path: Path) -> None:
    """Un draft anterior a P0.6 sigue sin poder instalarse, aunque exista un par."""
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    _fija_modo(c, MODO_DRAFT)
    borrador = Manifiesto.lee(c.ruta_manifiesto)
    assert borrador.modo == MODO_DRAFT

    with pytest.raises(StagingError, match="no es aplicable"):
        aplica(c.staging, borrador, raiz)
    with pytest.raises(StagingError, match="borrador no necesita destinos"):
        prepara_worktrees(c.ruta_manifiesto, c.repos, tmp_path / "otros")
    assert RegistroDestinos.lee(raiz).estado == ESTADO_LISTO


def test_el_worktree_canonico_nunca_es_destino(tmp_path: Path) -> None:
    """Se falsifica el registro para que apunte al repositorio real: git lo desmiente."""
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    _reescribe_registro(
        raiz, lambda d: d["destinos"]["dashboard"].update(ruta=str(c.repo_dashboard))
    )

    with pytest.raises(StagingError, match="worktree canónico"):
        aplica(c.staging, c.manifiesto, raiz)
    assert (c.repo_dashboard / "index.html").read_text() == "semana 31"
    assert RegistroDestinos.lee(raiz).estado == ESTADO_INVALIDO


def test_un_directorio_que_no_es_worktree_del_repo_no_es_destino(tmp_path: Path) -> None:
    """Un clon suelto en el HEAD correcto tampoco vale: no cuelga del repositorio registrado."""
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    clon = tmp_path / "clon"
    _git(tmp_path, "clone", "-q", str(c.repo_dashboard), str(clon))
    _git(clon, "checkout", "-q", "--detach", c.head_dashboard)
    _reescribe_registro(
        raiz, lambda d: d["destinos"]["dashboard"].update(ruta=str(clon.resolve()))
    )

    with pytest.raises(StagingError, match="no cuelga del repositorio registrado"):
        aplica(c.staging, c.manifiesto, raiz)
    assert (clon / "index.html").read_text() == "semana 31"


# ── 3 · el par tiene que estar exactamente como se creó ─────────────────────


def test_un_destino_sustituido_por_enlace_invalida_el_par(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    wt_d = Path(registro.destinos["dashboard"].ruta)
    copia = tmp_path / "copia"
    shutil.copytree(wt_d, copia)
    shutil.rmtree(wt_d)
    wt_d.symlink_to(copia, target_is_directory=True)

    with pytest.raises(StagingError, match="enlace simbólico"):
        aplica(c.staging, c.manifiesto, raiz)
    assert (copia / "index.html").read_text() == "semana 31"
    assert RegistroDestinos.lee(raiz).estado == ESTADO_INVALIDO


def test_un_head_distinto_invalida_el_par(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    wt_d = Path(registro.destinos["dashboard"].ruta)
    (c.repo_dashboard / "nuevo.html").write_text("avanzó", encoding="utf-8")
    _git(c.repo_dashboard, "add", "nuevo.html")
    _git(c.repo_dashboard, "commit", "-qm", "avanza")
    otro = _git(c.repo_dashboard, "rev-parse", "HEAD").strip()
    _git(wt_d, "checkout", "-q", "--detach", otro)

    with pytest.raises(StagingError, match="HEAD sellado"):
        aplica(c.staging, c.manifiesto, raiz)
    assert (wt_d / "index.html").read_text() == "semana 31"
    assert RegistroDestinos.lee(raiz).estado == ESTADO_INVALIDO


@pytest.mark.parametrize(
    "residuo", ["extra.txt", "index.html.{marca}.part", "index.html.{marca}.prev"]
)
def test_un_par_sucio_o_con_temporales_preplantados_se_invalida(
    tmp_path: Path, residuo: str
) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    wt_d = Path(registro.destinos["dashboard"].ruta)
    (wt_d / residuo.format(marca=c.manifiesto.run_id[:12])).write_text("preplantado")

    with pytest.raises(StagingError, match="no está limpio"):
        aplica(c.staging, c.manifiesto, raiz)
    assert (wt_d / "index.html").read_text() == "semana 31"
    assert RegistroDestinos.lee(raiz).estado == ESTADO_INVALIDO


def test_un_baseline_tomado_sobre_un_canonico_sucio_invalida_el_par(tmp_path: Path) -> None:
    """Control de M32 por el camino real: el worktree está limpio en el HEAD, pero el sello
    registró como baseline una edición sin confirmar del canónico. No coinciden: no se
    instala, y el par queda inválido."""
    c = _corrida(tmp_path, canonico_sucio=True)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)

    with pytest.raises(StagingError, match="el destino cambió desde el sellado"):
        aplica(c.staging, c.manifiesto, raiz)

    assert RegistroDestinos.lee(raiz).estado == ESTADO_INVALIDO
    wt_b = Path(registro.destinos["backend"].ruta)
    assert (wt_b / "reports" / "ProdDetails" / "tabla.csv").read_text() == "viejo\n"
    assert _git(wt_b, "status", "--porcelain").strip() == ""


def test_un_par_invalido_no_se_reutiliza(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    (Path(registro.destinos["backend"].ruta) / "colado.txt").write_text("sucio")
    with pytest.raises(StagingError):
        aplica(c.staging, c.manifiesto, raiz)
    (Path(registro.destinos["backend"].ruta) / "colado.txt").unlink()  # «arreglado» a mano

    with pytest.raises(StagingError, match="está invalido"):
        aplica(c.staging, c.manifiesto, raiz)
    with pytest.raises(StagingError, match="ya existe"):
        prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)


# ── 4 · registro: identidad y sidecar ────────────────────────────────────────


def test_un_registro_de_otra_corrida_o_manifiesto_se_rechaza(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)

    _reescribe_registro(raiz, lambda d: d.update(run_id="f" * 64))
    with pytest.raises(StagingError, match="otra corrida"):
        aplica(c.staging, c.manifiesto, raiz)
    _reescribe_registro(
        raiz, lambda d: d.update(run_id=c.manifiesto.run_id, manifiesto_sha256="e" * 64)
    )
    with pytest.raises(StagingError, match="otro manifiesto"):
        aplica(c.staging, c.manifiesto, raiz)
    # Ninguna de las dos llegó al lock: el estado sigue intacto.
    assert RegistroDestinos.lee(raiz).estado == ESTADO_LISTO


def test_un_registro_editado_sin_recalcular_el_digest_se_rechaza(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    ruta = raiz / "registro.json"
    ruta.write_text(ruta.read_text(encoding="utf-8").replace('"listo"', '"aplicado"'))

    with pytest.raises(StagingError, match="digest embebido"):
        aplica(c.staging, c.manifiesto, raiz)
    assert not (raiz / "registro.sha256").exists(), "un solo archivo: no hay sidecar"
    assert not list(raiz.glob("*.part")), "la escritura es un replace atómico"


def test_el_registro_se_escribe_de_una_vez(tmp_path: Path, monkeypatch) -> None:
    """Control de la escritura atómica: un fallo en el replace no deja un registro a medias."""
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    antes = (raiz / "registro.json").read_bytes()
    registro = RegistroDestinos.lee(raiz)

    def replace_roto(*_a: Any, **_k: Any) -> None:
        raise OSError("disco lleno")

    monkeypatch.setattr(release_worktrees.Path, "replace", replace_roto)
    with pytest.raises(OSError, match="disco lleno"):
        registro.marca(ESTADO_INVALIDO, "prueba")
    monkeypatch.undo()

    assert (raiz / "registro.json").read_bytes() == antes
    assert RegistroDestinos.lee(raiz).estado == ESTADO_LISTO


# ── 5 · lock: exactamente un apply ───────────────────────────────────────────


def test_dos_apply_no_compiten_en_el_mismo_proceso(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    descriptor = os.open(raiz / "apply.lock", os.O_RDWR)
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    try:
        with pytest.raises(StagingError, match="otro apply tiene el bloqueo"):
            aplica(c.staging, c.manifiesto, raiz)
    finally:
        os.close(descriptor)
    assert RegistroDestinos.lee(raiz).estado == ESTADO_LISTO, "perder el lock no invalida"
    assert aplica(c.staging, c.manifiesto, raiz)


def test_dos_apply_no_compiten_entre_procesos(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    hijo = subprocess.Popen(
        [
            PYTHON,
            "-c",
            "import fcntl, os, sys, time\n"
            "fd = os.open(sys.argv[1], os.O_RDWR)\n"
            "fcntl.flock(fd, fcntl.LOCK_EX)\n"
            "print('locked', flush=True)\n"
            "time.sleep(30)\n",
            str(raiz / "apply.lock"),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert hijo.stdout is not None and hijo.stdout.readline().strip() == "locked"
        with pytest.raises(StagingError, match="otro apply tiene el bloqueo"):
            aplica(c.staging, c.manifiesto, raiz)
    finally:
        hijo.kill()
        hijo.wait()
    assert aplica(c.staging, c.manifiesto, raiz)


def test_el_lock_nunca_se_borra(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    inode = (raiz / "apply.lock").stat().st_ino
    aplica(c.staging, c.manifiesto, raiz)
    aplica(c.staging, c.manifiesto, raiz)

    assert (raiz / "apply.lock").stat().st_ino == inode


# ── 6 · interrupción, excepción, digest discordante: el par queda inválido ──


def test_una_interrupcion_anterior_invalida_el_par_y_se_reconstruye(tmp_path: Path) -> None:
    """Estado residual de un apply matado a mitad: registro «en curso» y temporal a medias."""
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    wt_d = Path(registro.destinos["dashboard"].ruta)
    marca = c.manifiesto.run_id[:12]
    (wt_d / f"index.html.{marca}.part").write_bytes(b"semana 3")  # escritura truncada
    registro.marca(ESTADO_EN_CURSO)

    with pytest.raises(StagingError, match="interrumpido"):
        aplica(c.staging, c.manifiesto, raiz)
    assert RegistroDestinos.lee(raiz).estado == ESTADO_INVALIDO
    with pytest.raises(StagingError, match="está invalido"):
        aplica(c.staging, c.manifiesto, raiz)

    # Reconstrucción: otro par desde los mismos HEAD sellados, y ahí sí se instala.
    otro = prepara_worktrees(c.ruta_manifiesto, c.repos, tmp_path / "destinos_2")
    assert aplica(c.staging, c.manifiesto, tmp_path / "destinos_2")
    assert (Path(otro.destinos["dashboard"].ruta) / "index.html").read_text() == "semana 32"
    assert (c.repo_dashboard / "index.html").read_text() == "semana 31"


def test_una_excepcion_durante_la_instalacion_invalida_el_par_sin_dejar_mezcla(
    tmp_path: Path, monkeypatch
) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    wt_d = Path(registro.destinos["dashboard"].ruta)
    wt_b = Path(registro.destinos["backend"].ruta)
    original = Path.replace

    def replace_que_falla(self: Path, target: Any) -> Any:
        if self.name.startswith("index.html") and str(self).endswith(".part"):
            raise OSError("fallo inyectado al publicar index.html")
        return original(self, target)

    monkeypatch.setattr(Path, "replace", replace_que_falla)
    with pytest.raises(OSError, match="fallo inyectado"):
        aplica(c.staging, c.manifiesto, raiz)
    monkeypatch.undo()

    # El worktree vuelve a su HEAD: ni mezcla ni residuos; y el par ya no sirve.
    assert (wt_d / "index.html").read_text() == "semana 31"
    assert (wt_b / "reports" / "ProdDetails" / "tabla.csv").read_text() == "viejo\n"
    assert _git(wt_d, "status", "--porcelain", "--untracked-files=all").strip() == ""
    assert _git(wt_b, "status", "--porcelain", "--untracked-files=all").strip() == ""
    registro_final = RegistroDestinos.lee(raiz)
    assert registro_final.estado == ESTADO_INVALIDO
    assert "fallo inyectado" in registro_final.motivo
    with pytest.raises(StagingError, match="está invalido"):
        aplica(c.staging, c.manifiesto, raiz)


def test_un_digest_final_discordante_invalida_el_par(tmp_path: Path, monkeypatch) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)

    def instala_mal(
        raiz_staging: Path, manifiesto: Manifiesto, destinos: dict[str, Path], **_: Any
    ) -> list[str]:
        for rel in manifiesto.inventario:
            partes = rel.split("/")
            objetivo = destinos[partes[0]].joinpath(*partes[1:])
            objetivo.write_text("bytes que nadie selló", encoding="utf-8")
        return sorted(manifiesto.inventario)

    monkeypatch.setattr(release_worktrees, "_instala", instala_mal)
    with pytest.raises(StagingError, match="digest final discordante"):
        aplica(c.staging, c.manifiesto, raiz)
    assert RegistroDestinos.lee(raiz).estado == ESTADO_INVALIDO


# ── 7 · prepare: raíz nueva, fuera de .git y de la corrida; HEAD existente ──


def test_prepare_rechaza_raices_que_no_son_nuevas_o_estan_donde_no_deben(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    ocupada = tmp_path / "ocupada"
    ocupada.mkdir()
    (ocupada / "algo").write_text("del usuario")
    with pytest.raises(StagingError, match="ya existe"):
        prepara_worktrees(c.ruta_manifiesto, c.repos, ocupada)
    assert (ocupada / "algo").read_text() == "del usuario"

    with pytest.raises(StagingError, match="\\.git"):
        prepara_worktrees(c.ruta_manifiesto, c.repos, c.repo_backend / ".git" / "par")
    with pytest.raises(StagingError, match="solaparse con la corrida"):
        prepara_worktrees(c.ruta_manifiesto, c.repos, c.staging / "par")
    assert not (c.staging / "par").exists()


def test_prepare_exige_que_el_head_sellado_exista_en_el_repositorio(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    ajeno, _ = _repo(tmp_path / "ajeno", {"index.html": "otro repo"})

    with pytest.raises(StagingError, match="no existe en el repositorio dashboard"):
        prepara_worktrees(
            c.ruta_manifiesto, {"backend": c.repo_backend, "dashboard": ajeno}, tmp_path / "d"
        )
    assert not (tmp_path / "d").exists()


def test_prepare_exige_la_politica_del_head_canonico(tmp_path: Path) -> None:
    """Un sello cuya política no es la del HEAD del repositorio canónico no obtiene par.

    Se edita el manifiesto (con run_id y sidecar recalculados, como haría quien lo
    tocara) para que declare otra política: el repositorio desmiente el sello.
    """
    c = _corrida(tmp_path)
    # Coherente consigo mismo: la política del sello y la de cada registro de gate dicen
    # lo mismo, así que el manifiesto pasa su propia validación y sólo git lo desmiente.
    c.manifiesto.politica = {"version": VERSION_POLITICA, "sha256": "e" * 64}
    for registro in c.manifiesto.resultados_pruebas["gates"].values():
        registro["politica_sha256"] = "e" * 64
    c.manifiesto.run_id = calcula_run_id_de(c.manifiesto)
    c.manifiesto.escribe(c.ruta_manifiesto)
    assert Manifiesto.lee(c.ruta_manifiesto).politica["sha256"] == "e" * 64

    with pytest.raises(StagingError, match="no es la que el repositorio canónico lleva"):
        prepara_worktrees(c.ruta_manifiesto, c.repos, tmp_path / "d")
    assert not (tmp_path / "d").exists()
    assert _worktrees_de(c.repo_dashboard) == [str(c.repo_dashboard)]


def test_prepare_verifica_el_sello_antes_de_crear_nada(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    (c.staging / "outputs" / "dashboard" / "index.html").write_text("alterado tras sellar")

    with pytest.raises(StagingError, match="alterados"):
        prepara_worktrees(c.ruta_manifiesto, c.repos, tmp_path / "d")
    assert not (tmp_path / "d").exists()
    assert _worktrees_de(c.repo_dashboard) == [str(c.repo_dashboard)]


# ── 8 · descartar ────────────────────────────────────────────────────────────


def test_discard_retira_el_par_y_lo_deja_inservible(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    aplica(c.staging, c.manifiesto, raiz)

    descarta_worktrees(raiz, c.ruta_manifiesto)

    assert _worktrees_de(c.repo_dashboard) == [str(c.repo_dashboard)]
    assert not Path(registro.destinos["dashboard"].ruta).exists()
    assert RegistroDestinos.lee(raiz).estado == ESTADO_DESCARTADO
    with pytest.raises(StagingError, match="descartado"):
        aplica(c.staging, c.manifiesto, raiz)
    with pytest.raises(StagingError, match="ya está descartado"):
        descarta_worktrees(raiz, c.ruta_manifiesto)
    assert (c.repo_dashboard / "index.html").read_text() == "semana 31"


def test_discard_exige_el_manifiesto_del_par(tmp_path: Path) -> None:
    """Sin ligar `discard` al manifiesto, cualquier raíz con un registro plausible se retira."""
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    otra = _corrida(tmp_path / "otra", con_lapida=True)  # otro contenido, otro run_id

    with pytest.raises(StagingError, match="otra corrida"):
        descarta_worktrees(raiz, otra.ruta_manifiesto)
    # Mismo run_id, manifiesto reescrito (otro digest en disco): tampoco.
    c.manifiesto.escribe(c.ruta_manifiesto.with_name("copia.json"))
    (c.ruta_manifiesto.with_name("copia.json")).write_text(
        c.ruta_manifiesto.read_text(encoding="utf-8").replace("\n", "\n ", 1), encoding="utf-8"
    )
    with pytest.raises(StagingError, match="otro manifiesto|no coincide|ilegible|sidecar"):
        descarta_worktrees(raiz, c.ruta_manifiesto.with_name("copia.json"))
    assert Path(registro.destinos["dashboard"].ruta).is_dir()
    assert RegistroDestinos.lee(raiz).estado == ESTADO_LISTO


def test_discard_no_retira_lo_que_git_no_reconoce_como_su_worktree(tmp_path: Path) -> None:
    """El registro dice dónde mirar, git dice qué hay: un directorio ajeno en el sitio del
    worktree no se borra con --force."""
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    wt_d = Path(registro.destinos["dashboard"].ruta)
    _git(c.repo_dashboard, "worktree", "remove", "--force", str(wt_d))
    wt_d.mkdir()
    (wt_d / "del_usuario.txt").write_text("no es un worktree", encoding="utf-8")

    with pytest.raises(StagingError, match="no figura en `git worktree list`"):
        descarta_worktrees(raiz, c.ruta_manifiesto)

    assert (wt_d / "del_usuario.txt").read_text() == "no es un worktree"
    assert RegistroDestinos.lee(raiz).estado == ESTADO_LISTO
    # Y el worktree del backend, que sí es legítimo, tampoco se tocó: se comprueba todo antes.
    assert Path(registro.destinos["backend"].ruta).is_dir()


def test_discard_no_retira_un_destino_fuera_de_la_raiz_del_registro(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    ajeno = tmp_path / "ajeno_worktree"
    _git(c.repo_dashboard, "worktree", "add", "--detach", str(ajeno), c.head_dashboard)

    _reescribe_registro(raiz, lambda d: d["destinos"]["dashboard"].update(ruta=str(ajeno)))
    with pytest.raises(StagingError, match="no está bajo la raíz del registro"):
        descarta_worktrees(raiz, c.ruta_manifiesto)

    assert ajeno.is_dir() and (ajeno / "index.html").is_file()
    _git(c.repo_dashboard, "worktree", "remove", "--force", str(ajeno))


def test_discard_no_compite_con_un_apply_en_marcha(tmp_path: Path) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    registro = prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    descriptor = os.open(raiz / "apply.lock", os.O_RDWR)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(StagingError, match="otro apply tiene el bloqueo"):
            descarta_worktrees(raiz, c.ruta_manifiesto)
    finally:
        os.close(descriptor)
    assert Path(registro.destinos["dashboard"].ruta).is_dir()


def test_discard_por_cli_exige_el_manifiesto(tmp_path: Path, capsys) -> None:
    from scripts.refresh_staging import main

    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)

    with pytest.raises(SystemExit):
        main(["discard-worktrees", "--destinos", str(raiz)])
    assert "--manifiesto" in capsys.readouterr().err
    assert (
        main(
            [
                "discard-worktrees",
                "--manifiesto",
                str(c.ruta_manifiesto),
                "--destinos",
                str(raiz),
            ]
        )
        == 0
    )
    assert RegistroDestinos.lee(raiz).estado == ESTADO_DESCARTADO


# ── 10 · prepare: rollback y revalidación de gates ──────────────────────────


def test_un_fallo_a_mitad_de_prepare_no_deja_un_par_a_medias(tmp_path: Path, monkeypatch) -> None:
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    verifica_real = release_worktrees._verifica_destino

    def verifica_que_falla_en_el_dashboard(destino: Any, *args: Any, **kwargs: Any) -> Path:
        if destino.espacio == "dashboard":
            raise StagingError("el dashboard no pasó la verificación (simulado)")
        return verifica_real(destino, *args, **kwargs)

    monkeypatch.setattr(release_worktrees, "_verifica_destino", verifica_que_falla_en_el_dashboard)
    with pytest.raises(StagingError, match="simulado"):
        prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)

    assert not raiz.exists(), "la raíz del par se retira entera"
    assert _worktrees_de(c.repo_backend) == [str(c.repo_backend)], "el backend ya creado se retiró"
    assert _worktrees_de(c.repo_dashboard) == [str(c.repo_dashboard)]
    # Y se puede volver a intentar sobre la misma raíz.
    monkeypatch.undo()
    assert prepara_worktrees(c.ruta_manifiesto, c.repos, raiz).estado == ESTADO_LISTO


def test_prepare_revalida_los_gates_contra_la_politica_del_head(tmp_path: Path) -> None:
    """Un sello fabricado, coherente consigo mismo, cuya evidencia no cubre el conjunto de
    gates que la política del HEAD exige. `verifica` lo acepta (digests cuadran); sólo
    `valida_gates` contra el blob canónico lo desmiente."""
    from epiforecast.publication.weekly_staging import DIR_EVIDENCIA, EvidenciaGates

    c = _corrida(tmp_path)
    # La política real del HEAD pasa a exigir DOS gates; el sello sólo trae `cifras`.
    politica = _politica_cruda()
    politica["gates"].append({**politica["gates"][0], "id": "rag"})
    ruta_politica = c.repo_backend / "config" / "publication" / "politica_censo.json"
    ruta_politica.write_text(json.dumps(politica, indent=2) + "\n", encoding="utf-8")
    _git(c.repo_backend, "commit", "-qam", "dos gates")
    head_nuevo = _git(c.repo_backend, "rev-parse", "HEAD").strip()
    digest_politica = hashlib.sha256(ruta_politica.read_bytes()).hexdigest()

    # Sello fabricado: apunta al HEAD nuevo y a su política, con evidencia de un solo gate.
    m = c.manifiesto
    m.entrada.head_backend = head_nuevo
    m.politica = {"version": VERSION_POLITICA, "sha256": digest_politica}
    for registro in m.resultados_pruebas["gates"].values():
        registro["politica_sha256"] = digest_politica
    indice = c.staging / DIR_EVIDENCIA / "indice.json"
    crudo = json.loads(indice.read_text(encoding="utf-8"))
    crudo["politica"]["sha256"] = digest_politica
    for registro in crudo["gates"].values():
        registro["politica_sha256"] = digest_politica
    cuerpo = json.dumps(crudo, indent=2, ensure_ascii=False, sort_keys=True).encode() + b"\n"
    indice.write_bytes(cuerpo)
    (c.staging / DIR_EVIDENCIA / "indice.sha256").write_text(
        hashlib.sha256(cuerpo).hexdigest() + "\n", encoding="utf-8"
    )
    m.resultados_pruebas = EvidenciaGates.lee(c.staging).como_manifiesto()
    m.run_id = calcula_run_id_de(m)
    m.escribe(c.ruta_manifiesto)
    # Coherente consigo mismo: la verificación del sello pasa.
    from epiforecast.publication.weekly_staging import verifica

    verifica(
        c.staging,
        Manifiesto.lee(c.ruta_manifiesto),
        head_backend=head_nuevo,
        head_dashboard=c.head_dashboard,
    )

    with pytest.raises(StagingError, match="faltan resultados de gates que la política exige"):
        prepara_worktrees(c.ruta_manifiesto, c.repos, tmp_path / "d")
    assert not (tmp_path / "d").exists()
    assert _worktrees_de(c.repo_backend) == [str(c.repo_backend)]


def test_apply_no_declara_aplicado_un_par_cuya_composicion_no_es_la_sellada(
    tmp_path: Path, monkeypatch
) -> None:
    """Todo lo declarado está, pero el árbol administrado del par no es el que midieron los
    gates: un archivo administrado más, colado en la instalación."""
    c = _corrida(tmp_path)
    raiz = tmp_path / "destinos"
    prepara_worktrees(c.ruta_manifiesto, c.repos, raiz)
    instala_real = release_worktrees._instala

    def instala_y_cuela(
        raiz_staging: Path, manifiesto: Manifiesto, destinos: dict[str, Path], **kw: Any
    ) -> list[str]:
        resultado = instala_real(raiz_staging, manifiesto, destinos, **kw)
        (destinos["dashboard"] / "colado.html").write_text("nadie lo selló", encoding="utf-8")
        return resultado

    monkeypatch.setattr(release_worktrees, "_instala", instala_y_cuela)
    with pytest.raises(StagingError, match="composición aplicada"):
        aplica(c.staging, c.manifiesto, raiz)
    assert RegistroDestinos.lee(raiz).estado == ESTADO_INVALIDO


# ── 9 · CLI: prepare → apply → check-completeness ───────────────────────────


def test_cli_prepare_apply_y_completitud(tmp_path: Path, capsys) -> None:
    from scripts.refresh_staging import main

    c = _corrida(tmp_path, con_lapida=True)
    raiz = tmp_path / "destinos"
    argv_base = ["--manifiesto", str(c.ruta_manifiesto), "--destinos", str(raiz)]

    assert main(["check-completeness", *argv_base]) == 1
    assert "no existe la raíz de destinos" in capsys.readouterr().err
    assert (
        main(
            [
                "prepare-worktrees",
                *argv_base,
                "--repo-backend",
                str(c.repo_backend),
                "--repo-dashboard",
                str(c.repo_dashboard),
            ]
        )
        == 0
    )
    assert main(["check-completeness", *argv_base]) == 1
    assert "par aplicado" in capsys.readouterr().err
    assert main(["apply", *argv_base]) == 0
    assert main(["check-completeness", *argv_base]) == 0
    salida = capsys.readouterr().out
    assert "exactamente lo que el sello declara" in salida
    assert "lápidas 1" in salida

    wt_d = Path(RegistroDestinos.lee(raiz).destinos["dashboard"].ruta)
    (wt_d / "index.html").write_text("tocado después", encoding="utf-8")
    assert main(["check-completeness", *argv_base]) == 1
    assert "ALTERADO: index.html" in capsys.readouterr().out

    (wt_d / "index.html").write_text("semana 32", encoding="utf-8")
    (wt_d / "colado.html").write_text("nadie lo selló", encoding="utf-8")
    assert main(["check-completeness", *argv_base]) == 1
    assert "SOBRANTE: colado.html" in capsys.readouterr().out

    (wt_d / "colado.html").unlink()
    (wt_d / "index.html").unlink()
    assert main(["check-completeness", *argv_base]) == 1
    assert "FALTANTE: index.html" in capsys.readouterr().out

    (wt_d / "index.html").write_text("semana 32", encoding="utf-8")
    (wt_d / "obsoleto.html").write_text("resucitado", encoding="utf-8")
    assert main(["check-completeness", *argv_base]) == 1
    assert "LÁPIDA MAL: obsoleto.html" in capsys.readouterr().out

    (wt_d / "obsoleto.html").unlink()
    assert main(["check-completeness", *argv_base]) == 0
    assert main(["discard-worktrees", *argv_base]) == 0
