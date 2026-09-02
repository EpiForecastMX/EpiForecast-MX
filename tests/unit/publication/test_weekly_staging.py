"""Contratos del staging sellado del refresh semanal.

Las seis situaciones que este sello existe para impedir: que se publique algo distinto
de lo revisado, que un artefacto cambie entre el sellado y la publicación, que el
repositorio avance por debajo, que se cuele un archivo que nadie inventarió, que la
instalación no sea fiel byte a byte, y que un fallo a media instalación deje el destino
publicado a medias.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

import pytest

from epiforecast.publication.gate_runner import ejecuta_gates
from epiforecast.publication.weekly_staging import (
    CONFINAMIENTO_LISTO,
    DIR_EVIDENCIA,
    MODO_APLICABLE,
    MODO_DRAFT,
    MOTIVO_P06,
    VERSION_POLITICA,
    AutoridadLapidas,
    Boletin,
    Manifiesto,
    PoliticaCenso,
    SelloEntrada,
    StagingError,
    _instala,
    calcula_baseline,
    calcula_composicion,
    calcula_run_id_de,
    inventaria,
    poda_a_cambiados,
    sella,
    sha256_de,
    valida_ruta_sellable,
    verifica,
)
from tests.unit.publication import fabrica_p0 as fab

# Un gate inocuo y determinista: termina en 0 y no escribe nada. Ruta absoluta para que
# el entorno vacío que la política permite no tenga que traer PATH.
EJECUTABLE_INOCUO = shutil.which("true") or "/usr/bin/true"

HEAD_BACKEND = "a" * 40
HEAD_DASHBOARD = "b" * 40


def _entrada() -> SelloEntrada:
    """Sólo lo que declara quien sella; digests, boletines e inventario los deriva `sella`."""
    return SelloEntrada(
        head_backend=HEAD_BACKEND,
        head_dashboard=HEAD_DASHBOARD,
        # Base y candidato de la fábrica cortan en 2026-W31: las semanas del sello se atan a
        # esos cortes (y al EpiBot del candidato), así que un sello sin semana nueva las repite.
        semana_anterior="2026,31",
        semana_nueva="2026,31",
        padecimientos_autorizados=fab.PADECIMIENTOS,
    )


KNOWLEDGE = fab.knowledge_json()


def _staging_con_artefactos(raiz: Path) -> Path:
    outputs = raiz / "outputs"
    (outputs / "dashboard" / "Reports").mkdir(parents=True)
    (outputs / "dashboard" / "epibot").mkdir(parents=True)
    (outputs / "dashboard" / "Reports" / "index.html").write_text(
        "<h1>galeria</h1>", encoding="utf-8"
    )
    (outputs / "dashboard" / "epibot" / "knowledge.json").write_text(KNOWLEDGE, encoding="utf-8")
    (outputs / "backend").mkdir(parents=True)
    (outputs / "backend" / "validacion.html").write_text("<p>validacion</p>", encoding="utf-8")
    return raiz


def _gate(
    nombre: str,
    argv: list[str] | None = None,
    *,
    cwd: str = "dashboard/",
    timeout_s: int = 60,
) -> dict[str, Any]:
    """Definición estructurada de un gate: argv exacto, cwd cerrado, plazo y entorno vacío."""
    return {
        "id": nombre,
        "argv": argv or [EJECUTABLE_INOCUO],
        "cwd": cwd,
        "timeout_s": timeout_s,
        "entorno": {"heredar": [], "fijar": {}},
    }


def _semilla_de(destinos: dict[str, Path], rutas: tuple[str, ...]) -> dict[str, str]:
    """Digest en el destino de cada ruta, saltando las que ni son direccionables.

    Las pruebas de gramática pasan rutas inválidas a propósito; se ignoran para que salte
    el error de la gramática y no un KeyError del montaje.
    """
    semilla = {}
    for rel in rutas:
        partes = Path(rel).parts
        if len(partes) < 2 or partes[0] not in destinos:
            continue
        objetivo = destinos[partes[0]].joinpath(*partes[1:])
        if objetivo.exists():
            semilla[rel] = hashlib.sha256(objetivo.read_bytes()).hexdigest()
    return semilla


def _autoridad_de(
    raiz: Path, destinos: dict[str, Path], tombstones: tuple[str, ...]
) -> AutoridadLapidas:
    """Autoridad plausible para las pruebas: el generador retiró justo esas rutas.

    Modela el caso legítimo —estaban en la semilla, desaparecieron del candidato antes de
    podar y la política las permite— para que las pruebas de la maquinaria no repitan el
    montaje. Los casos ilegítimos construyen su autoridad a mano.
    """
    return AutoridadLapidas(
        eliminados_reales=frozenset(tombstones),
        allowlist=frozenset(tombstones),
    )


SUPERFICIES_DEL_STAGING = ("dashboard/Reports/index.html", "dashboard/epibot/knowledge.json")


def _politica_cruda(
    *,
    superficies: tuple[str, ...] = SUPERFICIES_DEL_STAGING,
    retirables: tuple[str, ...] = (),
    gates: tuple[str | dict[str, Any], ...] = ("cifras", "rag"),
    prefijos: tuple[str, ...] = ("backend/", "dashboard/"),
) -> dict[str, Any]:
    return {
        "version": VERSION_POLITICA,
        "prefijos_administrados": sorted(prefijos),
        "patron_superficie": {
            "prefijo": "dashboard/",
            "sufijos": [".html", ".json"],
            "directorios_excluidos": ["node_modules"],
        },
        "superficies_verificables": sorted(set(superficies) | set(retirables)),
        "retirables": sorted(retirables),
        # Un nombre solo se traduce a un gate inocuo; un dict se toma tal cual.
        "gates": [g if isinstance(g, dict) else _gate(g) for g in gates],
    }


def _politica(
    tmp_path: Path,
    *,
    superficies: tuple[str, ...] = SUPERFICIES_DEL_STAGING,
    retirables: tuple[str, ...] = (),
    gates: tuple[str | dict[str, Any], ...] = ("cifras", "rag"),
    nombre: str = "politica.json",
) -> PoliticaCenso:
    del tmp_path, nombre
    return PoliticaCenso.desde_bytes(
        json.dumps(
            _politica_cruda(superficies=superficies, retirables=retirables, gates=gates)
        ).encode("utf-8")
    )


def _sella_en(
    raiz: Path,
    tmp_path: Path,
    *,
    destinos: dict[str, Path] | None = None,
    tombstones: tuple[str, ...] = (),
    semilla: dict[str, str] | None = None,
    politica: PoliticaCenso | None = None,
    corre_gates: bool = True,
    politica_para_gates: PoliticaCenso | None = None,
) -> Manifiesto:
    """Sella con el contrato v2 completo, reproduciendo el orden real del flujo.

    Primero se CORREN los gates de la política sobre el árbol completo —el runner real,
    con comandos inocuos—, y sólo entonces se sella: no existe forma de pasarle a `sella`
    un resultado, así que la única manera de tener uno es haberlo ejecutado.
    """
    destinos = destinos or _destinos(tmp_path)
    semilla = {} if semilla is None else semilla
    inventario = (
        inventaria(raiz / "outputs")
        if (raiz / "outputs").is_dir() and not (raiz / "outputs").is_symlink()
        else {}
    )
    if politica is None:
        # El censo por defecto declara lo que este árbol publica de verdad: semilla,
        # candidato y lápidas. Fijar una lista a mano haría que media docena de pruebas
        # fallaran por el montaje y no por lo que miden.
        censo = tuple(
            sorted(
                {
                    rel
                    for rel in set(semilla) | set(inventario) | set(tombstones)
                    if rel.startswith("dashboard/") and rel.endswith((".html", ".json"))
                }
            )
        )
        politica = _politica(tmp_path, superficies=censo, retirables=tombstones)
    if corre_gates:
        ejecuta_gates(raiz, politica_para_gates or politica, destinos_vivos=destinos)
    if not fab.esta_hidratado(raiz):
        fab.hidrata_minimo(raiz, head_backend=HEAD_BACKEND)
    return sella(
        raiz,
        _entrada(),
        semilla=semilla,
        baseline=calcula_baseline(destinos, set(inventario) | set(tombstones)),
        politica=politica,
        tombstones=tombstones,
        autoridad_lapidas=_autoridad_de(raiz, destinos, tombstones),
        contrato=fab.CONTRATO,
    )


def _relativos_de(raiz: Path) -> list[str]:
    salida = raiz / "outputs"
    return [str(p.relative_to(salida)) for p in salida.rglob("*") if p.is_file()]


def _puebla_destino(raiz: Path, destinos: dict[str, Path], contenido) -> dict[Path, str]:
    """Deja una versión anterior de cada artefacto en el destino, ANTES de sellar.

    El baseline se toma del destino en el momento del sello, así que poblarlo después
    haría que `aplica` abortara por divergencia — que es justamente lo que debe hacer.
    """
    previos: dict[Path, str] = {}
    for rel in _relativos_de(raiz):
        partes = Path(rel).parts
        anterior = destinos[partes[0]].joinpath(*partes[1:])
        anterior.parent.mkdir(parents=True, exist_ok=True)
        texto = contenido(rel) if callable(contenido) else contenido
        anterior.write_text(texto, encoding="utf-8")
        previos[anterior] = texto
    return previos


def _hazlo_aplicable(raiz: Path, manifiesto: Manifiesto) -> Manifiesto:
    """Fija el sello en `aplicable` para probar la maquinaria de instalación.

    Desde P0.6 `sella` ya lo emite así; esto lo deja explícito y reescribe el manifiesto
    para que las pruebas de la transacción no dependan de la palanca global.
    """
    manifiesto.modo = MODO_APLICABLE
    manifiesto.motivo_draft = ""
    manifiesto.run_id = calcula_run_id_de(manifiesto)
    manifiesto.escribe(raiz / "manifest.json")
    return manifiesto


def _sella_aplicable(
    raiz: Path, tmp_path: Path, *, destinos: dict[str, Path] | None = None, **kwargs
) -> Manifiesto:
    return _hazlo_aplicable(raiz, _sella_en(raiz, tmp_path, destinos=destinos, **kwargs))


def _sella(tmp_path: Path) -> tuple[Path, Manifiesto]:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    return raiz, _sella_aplicable(raiz, tmp_path)


def _destinos(tmp_path: Path) -> dict[str, Path]:
    return {
        "dashboard": tmp_path / "destino_dashboard",
        "backend": tmp_path / "destino_backend",
    }


# ── 1 · reproducibilidad ────────────────────────────────────────────────────


def test_el_mismo_contenido_sella_el_mismo_identificador(tmp_path: Path) -> None:
    """Dos preparaciones idénticas en directorios distintos deben coincidir."""
    uno = _sella_en(_staging_con_artefactos(tmp_path / "uno"), tmp_path)
    dos = _sella_en(_staging_con_artefactos(tmp_path / "dos"), tmp_path)

    assert uno.run_id == dos.run_id
    assert uno.inventario == dos.inventario


def test_el_identificador_no_depende_de_la_fecha(tmp_path: Path) -> None:
    """Si la fecha entrase en el cálculo, dos corridas iguales parecerían distintas."""
    _, manifiesto = _sella(tmp_path)

    assert calcula_run_id_de(manifiesto) == manifiesto.run_id
    assert "creado" not in manifiesto.payload_canonico()


def test_un_artefacto_distinto_cambia_el_identificador(tmp_path: Path) -> None:
    uno = _sella_en(_staging_con_artefactos(tmp_path / "uno"), tmp_path)
    otra = _staging_con_artefactos(tmp_path / "dos")
    (otra / "outputs" / "backend" / "validacion.html").write_text("otra cosa", encoding="utf-8")
    dos = _sella_en(otra, tmp_path)

    assert uno.run_id != dos.run_id


# ── 2 · alterar un artefacto después del sellado ────────────────────────────


def test_alterar_un_artefacto_aborta(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    (raiz / "outputs" / "dashboard" / "epibot" / "knowledge.json").write_text(
        '{"semana": 27}', encoding="utf-8"
    )

    with pytest.raises(StagingError, match="alterados"):
        verifica(raiz, manifiesto, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)


def test_borrar_un_artefacto_aborta(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    (raiz / "outputs" / "backend" / "validacion.html").unlink()

    with pytest.raises(StagingError, match="faltan"):
        verifica(raiz, manifiesto, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)


# ── 3 · el repositorio avanzó por debajo ────────────────────────────────────


@pytest.mark.parametrize(
    "backend, dashboard",
    [("f" * 40, HEAD_DASHBOARD), (HEAD_BACKEND, "f" * 40)],
    ids=("backend", "dashboard"),
)
def test_cambiar_un_head_aborta(tmp_path: Path, backend: str, dashboard: str) -> None:
    raiz, manifiesto = _sella(tmp_path)

    with pytest.raises(StagingError, match="avanzó desde el sellado"):
        verifica(raiz, manifiesto, head_backend=backend, head_dashboard=dashboard)


# ── 4 · archivo fuera del inventario ────────────────────────────────────────


def test_un_archivo_no_inventariado_aborta(tmp_path: Path) -> None:
    """Aunque sea inofensivo: si nadie lo selló, nadie lo revisó."""
    raiz, manifiesto = _sella(tmp_path)
    (raiz / "outputs" / "dashboard" / "colado.txt").write_text("sorpresa", encoding="utf-8")

    with pytest.raises(StagingError, match="fuera del inventario"):
        verifica(raiz, manifiesto, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)


def test_un_objetivo_dvc_no_permitido_aborta(tmp_path: Path) -> None:
    """Se manipula EN DISCO, que es como llegaría: el objeto en memoria ya no manda."""
    raiz, _ = _sella(tmp_path)
    _reescribe_manifiesto(raiz, lambda crudo: crudo.update(operaciones_dvc=["models.dvc"]))

    with pytest.raises(StagingError, match="no permitido"):
        verifica(
            raiz,
            Manifiesto.lee(raiz / "manifest.json"),
            head_backend=HEAD_BACKEND,
            head_dashboard=HEAD_DASHBOARD,
        )


# ── 5 · la instalación es fiel byte a byte ──────────────────────────────────


def test_instala_exactamente_los_bytes_sellados(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    destinos = _destinos(tmp_path)

    instalados = _instala(
        raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
    )

    assert len(instalados) == 3
    assert (destinos["dashboard"] / "epibot" / "knowledge.json").read_text() == KNOWLEDGE
    assert (destinos["dashboard"] / "Reports" / "index.html").read_text() == "<h1>galeria</h1>"
    assert (destinos["backend"] / "validacion.html").read_text() == "<p>validacion</p>"
    assert list(destinos["dashboard"].rglob("*.part")) == []


def test_un_destino_que_cambio_desde_el_sello_no_se_instala(tmp_path: Path) -> None:
    """Control de M32: el baseline se comprueba ANTES de tocar nada.

    El sello registró que `Reports/index.html` no existía en el destino; alguien lo escribe
    después. Instalar encima pisaría trabajo que nadie revisó.
    """
    raiz, manifiesto = _sella(tmp_path)
    destinos = _destinos(tmp_path)
    ajeno = destinos["dashboard"] / "Reports" / "index.html"
    ajeno.parent.mkdir(parents=True)
    ajeno.write_text("editado después del sello", encoding="utf-8")

    with pytest.raises(StagingError, match="el destino cambió desde el sellado"):
        _instala(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )
    assert ajeno.read_text(encoding="utf-8") == "editado después del sello"
    assert not (destinos["dashboard"] / "epibot" / "knowledge.json").exists()
    assert list(destinos["dashboard"].rglob("*.prev")) == []


def test_la_instalacion_no_regenera_nada(tmp_path: Path) -> None:
    """Lo instalado sale del staging, no de volver a calcular: se comprueba el digest."""
    raiz, manifiesto = _sella(tmp_path)
    destinos = _destinos(tmp_path)
    _instala(raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)

    from epiforecast.publication.weekly_staging import sha256_de

    for rel, digest in manifiesto.inventario.items():
        partes = Path(rel).parts
        assert sha256_de(destinos[partes[0]].joinpath(*partes[1:])) == digest


# ── 6 · un fallo intermedio no publica nada ─────────────────────────────────


def test_un_destino_sin_declarar_no_publica_nada(tmp_path: Path) -> None:
    """El fallo ocurre a mitad de la lista; el destino debe quedar como estaba."""
    raiz, manifiesto = _sella(tmp_path)
    destinos = {"dashboard": tmp_path / "destino_dashboard"}  # falta 'backend'

    with pytest.raises(StagingError, match="no hay destino declarado"):
        _instala(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )

    assert not list((tmp_path / "destino_dashboard").rglob("*")) or not any(
        p.is_file() for p in (tmp_path / "destino_dashboard").rglob("*")
    )


def test_la_verificacion_falla_antes_de_tocar_el_destino(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    destinos = _destinos(tmp_path)
    (raiz / "outputs" / "dashboard" / "epibot" / "knowledge.json").write_text(
        "roto", encoding="utf-8"
    )

    with pytest.raises(StagingError):
        _instala(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )

    assert not destinos["dashboard"].exists()
    assert not destinos["backend"].exists()


# ── manifiesto: persistencia y forma ────────────────────────────────────────


def test_el_manifiesto_se_relee_identico(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    releido = Manifiesto.lee(raiz / "manifest.json")

    assert releido.como_dict() == manifiesto.como_dict()


def test_un_manifiesto_sin_version_se_rechaza_por_version(tmp_path: Path) -> None:
    ruta = tmp_path / "manifest.json"
    ruta.write_text('{"run_id": "abc"}', encoding="utf-8")

    with pytest.raises(StagingError, match="regenéralo"):
        Manifiesto.lee(ruta)


def test_un_manifiesto_v1_real_se_rechaza_por_version_no_por_forma(tmp_path: Path) -> None:
    """El camino real del CLI: un manifiesto histórico en disco, no un objeto mutado.

    Exigir primero la forma v2 daba «faltan claves: baseline, composicion, …», que hace
    pensar en un manifiesto corrupto cuando lo que ocurre es que es de otra versión.
    """
    ruta = tmp_path / "manifest.json"
    ruta.write_text(
        json.dumps(
            {
                "run_id": "6e22d412cb54fdc0",
                "creado": "2026-08-19T04:11:11Z",
                "modo": "staged",
                "version_generador": "weekly_staging/1",
                "entrada": {"head_backend": "a" * 40},
                "inventario": {"dashboard/index.html": "d" * 64},
                "targets_dvc": ["data/processed/dataset_boletin_epidemiologico.csv.dvc"],
                "resultados_pruebas": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(StagingError, match="weekly_staging/1"):
        Manifiesto.lee(ruta)


def test_un_manifiesto_v2_incompleto_se_rechaza_por_forma(tmp_path: Path) -> None:
    ruta = tmp_path / "manifest.json"
    ruta.write_text(
        json.dumps({"run_id": "abc", "version_generador": "weekly_staging/3"}),
        encoding="utf-8",
    )

    with pytest.raises(StagingError, match="incompleto"):
        Manifiesto.lee(ruta)


def test_un_staging_vacio_no_se_sella(tmp_path: Path) -> None:
    (tmp_path / "staging" / "outputs").mkdir(parents=True)

    with pytest.raises(StagingError, match="nada que sellar"):
        _sella_en(tmp_path / "staging", tmp_path)


def test_una_version_distinta_del_generador_se_rechaza(tmp_path: Path) -> None:
    """Un staging viejo no se aplica con un generador nuevo: se regenera."""
    raiz, manifiesto = _sella(tmp_path)
    manifiesto.version_generador = "weekly_staging/0"

    with pytest.raises(StagingError, match="regenéralo"):
        verifica(raiz, manifiesto, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)


# ── 7 · fallo DURANTE la publicación: recuperación ──────────────────────────


def _replace_que_falla_en(n: int):
    """Devuelve un reemplazo de Path.replace que falla en la n-ésima llamada.

    Copiar es la parte lenta y ya estaba cubierta. Lo que faltaba probar es el tramo
    corto pero real en el que unos archivos ya se publicaron y otros no. Tiene que ser
    una función, no un objeto invocable: asignado a la clase, solo una función recibe
    el `self` de la instancia.
    """
    original = Path.replace
    estado = {"llamadas": 0}

    def _reemplazo(self: Path, destino):  # noqa: ANN001
        estado["llamadas"] += 1
        if estado["llamadas"] == n:
            raise OSError("fallo simulado del sistema de archivos")
        return original(self, destino)

    return _reemplazo


def test_un_fallo_durante_la_publicacion_restaura_el_estado_previo(
    tmp_path: Path, monkeypatch
) -> None:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    destinos = _destinos(tmp_path)
    # El destino ya tiene una version anterior de cada artefacto.
    previos = _puebla_destino(raiz, destinos, lambda rel: f"version anterior de {rel}")
    manifiesto = _sella_aplicable(raiz, tmp_path, destinos=destinos)

    # Falla a mitad de los renombrados: son 3 artefactos y cada uno aparta y publica.
    monkeypatch.setattr(Path, "replace", _replace_que_falla_en(4))

    with pytest.raises(OSError, match="fallo simulado"):
        _instala(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )

    monkeypatch.undo()

    # Todo vuelve a su version anterior: ni una mezcla de las dos.
    for ruta, contenido in previos.items():
        assert ruta.read_text(encoding="utf-8") == contenido, f"{ruta} quedo publicado a medias"


def test_un_fallo_durante_la_publicacion_no_deja_residuos(tmp_path: Path, monkeypatch) -> None:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    destinos = _destinos(tmp_path)
    _puebla_destino(raiz, destinos, "anterior")
    manifiesto = _sella_aplicable(raiz, tmp_path, destinos=destinos)

    monkeypatch.setattr(Path, "replace", _replace_que_falla_en(4))
    with pytest.raises(OSError):
        _instala(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )
    monkeypatch.undo()

    for raiz_destino in destinos.values():
        assert list(raiz_destino.rglob("*.part")) == []
        assert list(raiz_destino.rglob("*.prev")) == []


def test_una_publicacion_correcta_no_deja_apartados(tmp_path: Path) -> None:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    destinos = _destinos(tmp_path)
    _puebla_destino(raiz, destinos, "anterior")
    manifiesto = _sella_aplicable(raiz, tmp_path, destinos=destinos)

    _instala(raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)

    for raiz_destino in destinos.values():
        assert list(raiz_destino.rglob("*.prev")) == []
        assert list(raiz_destino.rglob("*.part")) == []
    assert (destinos["dashboard"] / "epibot" / "knowledge.json").read_text() == KNOWLEDGE


# ── 8 · el espacio de nombres del manifiesto es cerrado ─────────────────────
#
# Las claves del inventario gobiernan dónde escribe `aplica`, y el manifiesto es un
# archivo de texto editable: son entrada no confiable. Los tres vectores se probaron
# contra el módulo antes de cerrarlos, y no se comportaban igual: la clave con `..` ya
# rebotaba —por un efecto lateral del chequeo de completitud, no por validación—, y los
# dos de enlace simbólico escribían fuera de la raíz o metían bytes ajenos.


def _reescribe_manifiesto(raiz: Path, mutador) -> None:
    """Reescribe manifest.json **y su sidecar**, como haría quien lo editara a mano.

    Recalcular el sidecar es justo lo que puede hacer un editor: por eso el sidecar
    detecta corrupción y edición no revisada, y no es una firma. Sin recalcularlo, estas
    pruebas medirían el sidecar en vez de la gramática de rutas.
    """
    ruta = raiz / "manifest.json"
    crudo = json.loads(ruta.read_text(encoding="utf-8"))
    mutador(crudo)
    cuerpo = json.dumps(crudo, indent=2, ensure_ascii=False).encode("utf-8")
    ruta.write_bytes(cuerpo)
    (raiz / "manifest.sha256").write_text(
        hashlib.sha256(cuerpo).hexdigest() + "\n", encoding="utf-8"
    )


@pytest.mark.parametrize(
    "ruta",
    [
        "dashboard/../../fuera.html",
        "/etc/passwd",
        "dashboard\\Reports\\index.html",
        "dashboard//index.html",
        "dashboard/./index.html",
        "otro/index.html",
        "dashboard",
        "",
    ],
)
def test_la_gramatica_de_rutas_rechaza(ruta: str) -> None:
    with pytest.raises(StagingError):
        valida_ruta_sellable(ruta)


def test_la_gramatica_admite_una_ruta_legitima() -> None:
    assert valida_ruta_sellable("dashboard/Reports/index.html") == (
        "dashboard",
        "Reports",
        "index.html",
    )


def test_una_clave_que_escapa_no_llega_a_tocar_el_destino(tmp_path: Path) -> None:
    """El vector `../`: antes rebotaba por accidente, ahora por gramática."""
    raiz, _ = _sella(tmp_path)
    fuera = tmp_path / "FUERA.html"

    def mete_escape(crudo: dict) -> None:
        digest = crudo["inventario"].pop("dashboard/Reports/index.html")
        crudo["inventario"]["dashboard/../../FUERA.html"] = digest

    _reescribe_manifiesto(raiz, mete_escape)

    with pytest.raises(StagingError, match="ruta sellable"):
        _instala(
            raiz,
            Manifiesto.lee(raiz / "manifest.json"),
            _destinos(tmp_path),
            head_backend=HEAD_BACKEND,
            head_dashboard=HEAD_DASHBOARD,
        )
    assert not fuera.exists()


def test_un_padre_del_destino_que_es_enlace_aborta(tmp_path: Path) -> None:
    """El vector que SÍ estaba abierto: escribía fuera del repositorio."""
    raiz, manifiesto = _sella(tmp_path)
    destinos = _destinos(tmp_path)
    ajeno = tmp_path / "ajeno"
    ajeno.mkdir()
    destinos["dashboard"].mkdir(parents=True)
    (destinos["dashboard"] / "Reports").symlink_to(ajeno, target_is_directory=True)

    with pytest.raises(StagingError, match="enlace simbólico"):
        _instala(
            raiz,
            manifiesto,
            destinos,
            head_backend=HEAD_BACKEND,
            head_dashboard=HEAD_DASHBOARD,
        )
    assert list(ajeno.iterdir()) == []


def test_un_enlace_dentro_del_staging_no_se_sella(tmp_path: Path) -> None:
    """El otro vector abierto: se inventariaba siguiendo el enlace y se copiaba."""
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("contenido ajeno", encoding="utf-8")
    raiz = _staging_con_artefactos(tmp_path / "staging")
    (raiz / "outputs" / "dashboard" / "colado.html").symlink_to(secreto)

    with pytest.raises(StagingError, match="enlace simbólico"):
        _sella_en(raiz, tmp_path)


def test_un_archivo_no_regular_en_el_staging_no_se_sella(tmp_path: Path) -> None:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    os.mkfifo(raiz / "outputs" / "dashboard" / "tuberia")

    with pytest.raises(StagingError, match="no regular"):
        _sella_en(raiz, tmp_path)


# ── 9 · el manifiesto lleva sidecar de integridad ───────────────────────────


def test_editar_el_manifiesto_sin_recalcular_el_sidecar_aborta(tmp_path: Path) -> None:
    """`creado` queda fuera del run_id a propósito; el sidecar sí lo cubre."""
    raiz, _ = _sella(tmp_path)
    ruta = raiz / "manifest.json"
    crudo = json.loads(ruta.read_text(encoding="utf-8"))
    crudo["creado"] = "1999-01-01T00:00:00Z"
    ruta.write_text(json.dumps(crudo, indent=2, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(StagingError, match="manifest.sha256"):
        verifica(
            raiz,
            Manifiesto.lee(ruta),
            head_backend=HEAD_BACKEND,
            head_dashboard=HEAD_DASHBOARD,
        )


def test_sin_sidecar_no_se_verifica(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    (raiz / "manifest.sha256").unlink()

    with pytest.raises(StagingError, match="falta el sidecar"):
        verifica(raiz, manifiesto, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)


# ── 10 · una corrida sellada es inmutable ───────────────────────────────────
#
# `seal` hacía `if destino.exists(): shutil.rmtree(destino)`. Repetir una corrida con el
# mismo contenido —o una colisión de identificador— destruía la evidencia ya revisada y
# colocaba otra bajo el mismo nombre, sin dejar rastro de la sustitución.


def _trabajo_para_sellar(raiz: Path, contenido: str) -> Path:
    trabajo = raiz
    (trabajo / "outputs" / "dashboard").mkdir(parents=True)
    (trabajo / "outputs" / "dashboard" / "index.html").write_text(contenido, encoding="utf-8")
    (trabajo / "semilla.json").write_text("{}", encoding="utf-8")
    return trabajo


def _repo_con_politica(
    raiz: Path, politica: dict[str, Any], marca: str | None = None
) -> tuple[Path, str]:
    """Repositorio Git de usar y tirar con la política **confirmada** en su HEAD.

    `seal` lee la política del commit que sella, así que una prueba honesta necesita un
    commit de verdad: sin él sólo se probaría el camino que el bloqueante describía, el de
    fabricar la política en el momento de usarla.
    """
    raiz.mkdir(parents=True, exist_ok=True)
    ruta = raiz / "config" / "publication" / "politica_censo.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(politica, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Lo que `hydrate` y el contrato leen del HEAD: allowlist y catálogo; datos sin rastrear.
    (raiz / "config" / "publication" / "entradas_semanales.json").write_text(
        json.dumps(fab.lista_entradas_cruda(), indent=2) + "\n", encoding="utf-8"
    )
    (raiz / "config" / "geografia").mkdir(parents=True, exist_ok=True)
    (raiz / "config" / "geografia" / "entidades_mx.csv").write_text(
        fab.CATALOGO_CSV, encoding="utf-8"
    )
    (raiz / "config" / "padecimientos.yaml").write_text(fab.REGISTRY_YAML, encoding="utf-8")
    for rel, texto in (
        (fab.RUTA_CONSOLIDADO, fab.consolidado_csv()),
        (fab.RUTA_FORECAST, fab.forecast_csv()),
    ):
        (raiz / rel).parent.mkdir(parents=True, exist_ok=True)
        (raiz / rel).write_text(texto, encoding="utf-8")
    corre = lambda *args: subprocess.run(  # noqa: E731
        ["git", "-C", str(raiz), *args], check=True, capture_output=True
    )
    corre("init", "-q")
    corre("config", "user.email", "prueba@ejemplo")
    corre("config", "user.name", "Prueba")
    if marca is not None:
        # Cambia el árbol sin tocar la política: así el HEAD difiere por construcción y no
        # por el azar del segundo en que se confirma.
        (raiz / "marca.txt").write_text(marca, encoding="utf-8")
        corre("add", "marca.txt")
    corre("add", "config")
    corre("commit", "-qm", "politica de censo")
    head = subprocess.run(
        ["git", "-C", str(raiz), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    return raiz, head


def _argv_seal(
    trabajo: Path,
    destino_final: Path | None = None,
    allowlist: set[str] | None = None,
    repo: tuple[Path, str] | None = None,
    *,
    corre_gates: bool = True,
) -> list[str]:
    """Argumentos de `seal` para un staging dado.

    `repo` permite COMPARTIR repositorio y HEAD entre dos invocaciones. Sin eso cada
    llamada creaba el suyo, y dos commits idénticos sólo coinciden en hash si caen en el
    mismo segundo: la prueba de reutilización pasaba por azar del reloj.
    """
    # La política declara lo que este staging publica: semilla y candidato juntos. Un
    # censo que no case con el árbol es justamente lo que el sello rechaza.
    semilla_previa = json.loads((trabajo / "semilla.json").read_text(encoding="utf-8"))
    presentes_previos = inventaria(trabajo / "outputs") if (trabajo / "outputs").is_dir() else {}
    censo = tuple(
        sorted(
            {
                rel
                for rel in set(semilla_previa) | set(presentes_previos)
                if rel.startswith("dashboard/") and rel.endswith((".html", ".json"))
            }
            | set(allowlist or ())
        )
    )
    destino, head = repo or _repo_con_politica(
        trabajo.parent / f"dest_{trabajo.name}",
        _politica_cruda(superficies=censo, retirables=tuple(allowlist or ()), gates=("cifras",)),
    )
    # El staging montado a mano lleva el registro que dejaría `materialize`: HEAD y política.
    if not (trabajo / "materializacion.json").exists():
        fab.materializa_a_mano(
            trabajo,
            head_backend=head,
            head_dashboard=head,
            politica_sha256=fab.sha_politica_del_head(destino, head),
        )

    # La evidencia la produce el runner sobre el árbol COMPLETO, antes de que `seal` pode.
    # Ya no hay un JSON de resultados que escribir: la única forma de tenerlos es correrlos.
    if corre_gates:
        from scripts.refresh_staging import main

        rc_hidrata = main(
            [
                "hydrate",
                "--trabajo",
                str(trabajo),
                "--repo-backend",
                str(destino),
                "--head-backend",
                head,
                "--padecimientos",
                ",".join(fab.PADECIMIENTOS),
            ]
        )
        assert rc_hidrata == 0, "la hidratación del montaje tiene que pasar"
        rc_gates = main(
            [
                "run-gates",
                "--trabajo",
                str(trabajo),
                "--head-backend",
                head,
                "--destino-backend",
                str(destino),
                "--destino-dashboard",
                str(destino),
            ]
        )
        assert rc_gates == 0, "los gates inocuos del montaje tienen que pasar"
    argv = [
        "seal",
        "--trabajo",
        str(trabajo),
        "--semilla",
        str(trabajo / "semilla.json"),
        "--head-backend",
        head,
        # El mismo repositorio hace de dashboard: el HEAD existe (la cadena de caché falla
        # cerrado ante un HEAD inexistente) y sin kb.js la cadena no aplica.
        "--head-dashboard",
        head,
        "--semana-anterior",
        "2026,31",
        "--semana-nueva",
        "2026,31",
        "--padecimientos",
        "Dengue",
        "--destino-dashboard",
        str(destino),
        "--destino-backend",
        str(destino),
    ]
    if destino_final is not None:
        argv += ["--destino-final", str(destino_final)]
    return argv


def test_sellar_dos_veces_el_mismo_contenido_reutiliza_sin_reescribir(tmp_path: Path) -> None:
    from scripts.refresh_staging import main

    argv = _argv_seal(_trabajo_para_sellar(tmp_path / "a", "uno"))
    repo = (
        Path(argv[argv.index("--destino-backend") + 1]),
        argv[argv.index("--head-backend") + 1],
    )

    assert main(argv) == 0
    (sellado,) = [d for d in (tmp_path / "a").parent.iterdir() if (d / "manifest.json").is_file()]
    antes = (sellado / "manifest.json").read_bytes()

    # MISMO repositorio y MISMO head: es la única forma de que la entrada sea idéntica.
    assert main(_argv_seal(_trabajo_para_sellar(tmp_path / "b", "uno"), sellado, repo=repo)) == 0
    assert (sellado / "manifest.json").read_bytes() == antes


def test_el_mismo_contenido_con_otro_head_no_se_reutiliza(tmp_path: Path, capsys) -> None:
    """El HEAD gobierna: cambiarlo cambia la entrada aunque las salidas sean idénticas.

    Es lo que hacía no determinista a la prueba de arriba: cada invocación creaba su propio
    repositorio, y dos commits iguales sólo comparten hash si caen en el mismo segundo.

    Se afirma la CAUSA, no sólo el código de salida: un rc=1 por «la política no está en el
    HEAD» o por un censo que no casa también preservaría el manifiesto, y la prueba pasaría
    por el motivo equivocado.
    """
    from scripts.refresh_staging import main

    argv = _argv_seal(_trabajo_para_sellar(tmp_path / "a", "uno"))
    argv_previo_head = argv[argv.index("--head-backend") + 1]
    assert main(argv) == 0
    (sellado,) = [d for d in (tmp_path / "a").parent.iterdir() if (d / "manifest.json").is_file()]
    antes = (sellado / "manifest.json").read_bytes()

    # MISMA política —para que el censo no sea el motivo del rechazo— y otro HEAD.
    politica = json.loads(
        (tmp_path / "dest_a" / "config" / "publication" / "politica_censo.json").read_text(
            encoding="utf-8"
        )
    )
    otro = _repo_con_politica(tmp_path / "otro_repo", politica, marca="otro árbol")
    assert otro[1] != argv_previo_head

    rc = main(_argv_seal(_trabajo_para_sellar(tmp_path / "b", "uno"), sellado, repo=otro))

    assert rc == 1
    # Difiere EXACTAMENTE `entrada` —el HEAD vive ahí— y ningún otro campo: las salidas,
    # la política y la composición son idénticas por construcción.
    assert (
        f"ABORTA: {sellado.name} ya existe con otro contenido; difieren: entrada\n"
        in capsys.readouterr().err
    )
    assert (sellado / "manifest.json").read_bytes() == antes


def test_un_destino_ya_ocupado_por_otra_corrida_no_se_pisa(tmp_path: Path) -> None:
    """No es una colisión de hash —imposible de fabricar—: es el mismo destino forzado.

    Se llamaba «colisión de run_id» y no lo era: `--destino-final` obliga a compartir
    directorio aunque los identificadores calculados difieran. El nombre importa porque
    una prueba mal nombrada promete una garantía que no da.
    """
    from scripts.refresh_staging import main

    assert main(_argv_seal(_trabajo_para_sellar(tmp_path / "a", "uno"))) == 0
    (sellado,) = [d for d in (tmp_path / "a").parent.iterdir() if (d / "manifest.json").is_file()]
    antes = (sellado / "manifest.json").read_bytes()

    rc = main(_argv_seal(_trabajo_para_sellar(tmp_path / "b", "DOS"), sellado))

    assert rc == 1
    assert (sellado / "manifest.json").read_bytes() == antes
    assert (sellado / "outputs" / "dashboard" / "index.html").read_text() == "uno"


def test_un_directorio_ocupado_sin_manifiesto_no_se_borra(tmp_path: Path) -> None:
    from scripts.refresh_staging import main

    ocupado = tmp_path / "ocupado"
    ocupado.mkdir()
    (ocupado / "algo_del_usuario.txt").write_text("no me borres", encoding="utf-8")

    rc = main(_argv_seal(_trabajo_para_sellar(tmp_path / "a", "uno"), ocupado))

    assert rc == 1
    assert (ocupado / "algo_del_usuario.txt").read_text() == "no me borres"


# ── 11 · el sello gobierna el objeto que se aplica, no uno parecido ─────────


def test_un_manifiesto_mutado_en_memoria_no_se_aplica(tmp_path: Path) -> None:
    """El sidecar cubría el JSON en disco mientras `aplica` publicaba otro objeto.

    Reproducido: bastaba cambiar el artefacto y su digest en el objeto en memoria para
    publicar bytes que nadie revisó, con el sidecar original intacto y válido.
    """
    raiz, manifiesto = _sella(tmp_path)
    artefacto = raiz / "outputs" / "dashboard" / "Reports" / "index.html"
    artefacto.write_text("ALTERADO DESPUES", encoding="utf-8")
    manifiesto.inventario["dashboard/Reports/index.html"] = sha256_de(artefacto)
    destinos = _destinos(tmp_path)

    with pytest.raises(StagingError, match="no es el que está sellado en disco"):
        _instala(
            raiz,
            manifiesto,
            destinos,
            head_backend=HEAD_BACKEND,
            head_dashboard=HEAD_DASHBOARD,
        )
    assert not (destinos["dashboard"] / "Reports" / "index.html").exists()


# ── 12 · ni la raíz ni los temporales siguen enlaces ────────────────────────


def test_una_raiz_outputs_enlazada_no_se_sella(tmp_path: Path) -> None:
    ajeno = tmp_path / "ajeno"
    (ajeno / "dashboard").mkdir(parents=True)
    (ajeno / "dashboard" / "index.html").write_text("desde fuera", encoding="utf-8")
    raiz = tmp_path / "staging"
    raiz.mkdir()
    (raiz / "outputs").symlink_to(ajeno, target_is_directory=True)

    with pytest.raises(StagingError, match="enlace simbólico"):
        _sella_en(raiz, tmp_path)


def test_un_temporal_preplantado_como_enlace_no_escribe_fuera(tmp_path: Path) -> None:
    """`write_bytes` seguía el enlace: el manifiesto acababa dentro del archivo apuntado."""
    victima = tmp_path / "victima.txt"
    victima.write_text("archivo externo", encoding="utf-8")
    raiz = _staging_con_artefactos(tmp_path / "staging")
    (raiz / "manifest.json.part").symlink_to(victima)

    with pytest.raises(StagingError, match="ya existe"):
        _sella_en(raiz, tmp_path)
    assert victima.read_text(encoding="utf-8") == "archivo externo"


def test_un_temporal_regular_preexistente_tampoco_se_pisa(tmp_path: Path) -> None:
    """Exclusiva es exclusiva: antes se retiraba «el residuo» y se escribía encima."""
    raiz = _staging_con_artefactos(tmp_path / "staging")
    (raiz / "manifest.json.part").write_text("algo que alguien puso", encoding="utf-8")

    with pytest.raises(StagingError, match="ya existe"):
        _sella_en(raiz, tmp_path)
    assert (raiz / "manifest.json.part").read_text() == "algo que alguien puso"


def test_un_part_del_destino_preplantado_no_se_sigue(tmp_path: Path) -> None:
    """El mismo agujero, pero en `aplica`: copiaba a través del enlace y publicaba enlace."""
    raiz, manifiesto = _sella(tmp_path)
    victima = tmp_path / "victima.txt"
    victima.write_text("archivo externo", encoding="utf-8")
    destinos = _destinos(tmp_path)
    (destinos["dashboard"] / "Reports").mkdir(parents=True)
    marca = manifiesto.run_id[:12]
    (destinos["dashboard"] / "Reports" / f"index.html.{marca}.part").symlink_to(victima)

    with pytest.raises(StagingError, match="ya existe"):
        _instala(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )
    assert victima.read_text(encoding="utf-8") == "archivo externo"
    assert not (destinos["dashboard"] / "Reports" / "index.html").exists()


def test_un_sidecar_enlazado_no_se_acepta(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    señuelo = tmp_path / "señuelo.sha256"
    señuelo.write_text(
        hashlib.sha256((raiz / "manifest.json").read_bytes()).hexdigest() + "\n",
        encoding="utf-8",
    )
    (raiz / "manifest.sha256").unlink()
    (raiz / "manifest.sha256").symlink_to(señuelo)

    with pytest.raises(StagingError, match="enlace simbólico"):
        verifica(raiz, manifiesto, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)


# ── 13 · reutilizar exige que coincidan también las ENTRADAS ────────────────


def test_mismas_salidas_con_entradas_distintas_no_se_reutiliza(tmp_path: Path) -> None:
    """Mismo output y otra semana declarada: antes daba rc=0 las dos veces."""
    from scripts.refresh_staging import main

    argv = _argv_seal(_trabajo_para_sellar(tmp_path / "a", "uno"))
    assert main(argv) == 0
    (sellado,) = [d for d in (tmp_path / "a").parent.iterdir() if (d / "manifest.json").is_file()]

    otro = _argv_seal(_trabajo_para_sellar(tmp_path / "b", "uno"), sellado)
    otro[otro.index("--semana-nueva") + 1] = "2026,32"

    assert main(otro) == 1
    assert (
        json.loads((sellado / "manifest.json").read_text())["entrada"]["semana_nueva"] == "2026,31"
    )


# ── 14 · publicar la corrida es lo último ───────────────────────────────────


def test_un_fallo_al_sellar_no_deja_corrida_publicada(tmp_path: Path, monkeypatch) -> None:
    """Antes se renombraba a nombre final y SE SELLABA después."""
    from scripts import refresh_staging

    # Se ataca el punto exacto: `sella` lanza. Con el orden viejo el directorio final ya
    # existía cuando eso ocurría; con el nuevo no puede existir, porque su nombre se
    # deriva de un manifiesto que todavía no hay.
    trabajo = _trabajo_para_sellar(tmp_path / "a", "uno")

    def sella_que_falla(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise StagingError("fallo inyectado durante el sellado")

    monkeypatch.setattr(refresh_staging, "sella", sella_que_falla)

    assert refresh_staging.main(_argv_seal(trabajo)) == 1
    assert trabajo.is_dir(), "el trabajo sigue donde estaba"
    assert (trabajo / "outputs" / "dashboard" / "index.html").read_text() == "uno"
    assert [d for d in tmp_path.iterdir() if (d / "manifest.json").is_file()] == []


# ── 15 · lápidas: campo separado, misma gramática, misma transacción ────────


def _sella_con_lapida(tmp_path: Path, lapidas: tuple[str, ...]) -> tuple[Path, Manifiesto]:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    destinos = _destinos(tmp_path)
    return raiz, _sella_aplicable(
        raiz,
        tmp_path,
        tombstones=lapidas,
        semilla=_semilla_de(destinos, lapidas),
        politica=_politica(tmp_path, retirables=lapidas),
    )


def test_una_lapida_retira_el_archivo_del_destino(tmp_path: Path) -> None:
    destinos = _destinos(tmp_path)
    destinos["dashboard"].mkdir(parents=True)
    (destinos["dashboard"] / "viejo.html").write_text("obsoleto", encoding="utf-8")
    raiz, manifiesto = _sella_con_lapida(tmp_path, ("dashboard/viejo.html",))

    _instala(raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)

    assert not (destinos["dashboard"] / "viejo.html").exists()
    assert not (destinos["dashboard"] / "viejo.html.prev").exists()
    assert (destinos["dashboard"] / "Reports" / "index.html").read_text() == "<h1>galeria</h1>"


def test_una_lapida_de_algo_que_no_esta_en_el_destino_no_se_sella(tmp_path: Path) -> None:
    """Antes se admitía y no hacía nada; ahora no se puede ni declarar.

    Una lápida sobre una ruta ausente del destino no describe ninguna retirada: o el
    archivo nunca estuvo, o alguien ya lo quitó. En ninguno de los dos casos le toca a este
    sello autorizar un borrado futuro.
    """
    with pytest.raises(StagingError, match="no está en la semilla|no existe en el destino"):
        _sella_con_lapida(tmp_path, ("dashboard/nunca_existio.html",))


def test_un_fallo_en_la_segunda_lapida_restaura_la_primera(tmp_path: Path, monkeypatch) -> None:
    """Dos lápidas: la primera se aparta y la segunda falla.

    Con una sola, el fallo ocurría ANTES de apartar nada: no había nada que deshacer y la
    prueba pasaba sin ejercitar la restauración.
    """
    destinos = _destinos(tmp_path)
    destinos["dashboard"].mkdir(parents=True)
    (destinos["dashboard"] / "a_retirar.html").write_text("primera", encoding="utf-8")
    (destinos["dashboard"] / "b_retirar.html").write_text("segunda", encoding="utf-8")
    raiz, manifiesto = _sella_con_lapida(
        tmp_path, ("dashboard/a_retirar.html", "dashboard/b_retirar.html")
    )

    original = Path.replace

    def replace_que_falla(self, target):  # type: ignore[no-untyped-def]
        if self.name == "b_retirar.html":
            raise OSError("fallo inyectado al retirar la segunda")
        return original(self, target)

    monkeypatch.setattr(Path, "replace", replace_que_falla)
    with pytest.raises(OSError):
        _instala(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )
    monkeypatch.undo()

    assert (destinos["dashboard"] / "a_retirar.html").read_text() == "primera"
    assert (destinos["dashboard"] / "b_retirar.html").read_text() == "segunda"
    assert not list(destinos["dashboard"].rglob("*.prev"))
    assert not (destinos["dashboard"] / "Reports" / "index.html").exists()


@pytest.mark.parametrize(
    "lapida",
    ["dashboard/../../fuera.html", "/etc/passwd", "otro/x.html", "dashboard/./x.html", ""],
)
def test_una_lapida_con_ruta_invalida_no_se_sella(tmp_path: Path, lapida: str) -> None:
    with pytest.raises(StagingError):
        _sella_con_lapida(tmp_path, (lapida,))


def test_una_lapida_no_puede_estar_tambien_inventariada(tmp_path: Path) -> None:
    with pytest.raises(StagingError, match="a la vez inventariadas"):
        _sella_con_lapida(tmp_path, ("dashboard/Reports/index.html",))


def test_una_lapida_con_archivo_presente_en_el_staging_no_se_sella(tmp_path: Path) -> None:
    """Lo presente ES el inventario: una lápida presente es una ruta inventariada con lápida."""
    raiz = _staging_con_artefactos(tmp_path / "staging")
    (raiz / "outputs" / "dashboard" / "ambiguo.html").write_text("presente", encoding="utf-8")

    with pytest.raises(StagingError, match="a la vez inventariadas y con lápida"):
        _sella_en(raiz, tmp_path, tombstones=("dashboard/ambiguo.html",))


@pytest.mark.parametrize(
    "lapida",
    ["dashboard/../../fuera.html", "/etc/passwd", "otro/x.html", "dashboard/./x.html", ""],
)
def test_la_gramatica_de_lapidas_se_exige_directamente(lapida: str) -> None:
    """Control de M11: la gramática la aplica `valida_tombstones`, no sólo el parser de la
    política que en `_sella_con_lapida` salta antes."""
    from epiforecast.publication.weekly_staging import valida_tombstones

    with pytest.raises(StagingError, match="ruta sellable"):
        valida_tombstones((lapida,), {})


def test_una_lapida_invalida_metida_en_el_manifiesto_no_se_relee(tmp_path: Path) -> None:
    """El vector real de M11: editar el manifiesto sellado para colar una lápida con `..`."""
    raiz, _ = _sella(tmp_path)

    def cuela(crudo: dict) -> None:
        crudo["tombstones"] = ["dashboard/../../fuera.html"]
        crudo["baseline"]["dashboard/../../fuera.html"] = {
            "presente": False,
            "tipo": None,
            "modo": None,
            "bytes": None,
            "sha256": None,
        }

    _reescribe_manifiesto(raiz, cuela)

    with pytest.raises(StagingError, match="componente vacío, '.' o '..'"):
        Manifiesto.lee(raiz / "manifest.json")


@pytest.mark.parametrize("rel", ["dashboard/.git/HEAD", "backend/.git/hooks/pre-commit"])
def test_una_ruta_bajo_git_no_es_sellable(rel: str) -> None:
    from epiforecast.publication.weekly_staging import valida_ruta_sellable

    with pytest.raises(StagingError, match="dentro de .git"):
        valida_ruta_sellable(rel)


def test_una_lapida_con_padre_enlazado_no_se_aplica(tmp_path: Path) -> None:
    """El escape por enlace se reejecuta contra el campo nuevo, no sólo el inventario."""
    destinos = _destinos(tmp_path)
    (destinos["dashboard"] / "sub").mkdir(parents=True)
    (destinos["dashboard"] / "sub" / "viejo.html").write_text("obsoleto", encoding="utf-8")
    raiz, manifiesto = _sella_con_lapida(tmp_path, ("dashboard/sub/viejo.html",))

    # El enlace se planta DESPUÉS del sello: es el caso real, alguien cambia el árbol
    # entre revisar y aplicar.
    ajeno = tmp_path / "ajeno"
    ajeno.mkdir()
    (ajeno / "viejo.html").write_text("archivo externo", encoding="utf-8")
    (destinos["dashboard"] / "sub" / "viejo.html").unlink()
    (destinos["dashboard"] / "sub").rmdir()
    (destinos["dashboard"] / "sub").symlink_to(ajeno, target_is_directory=True)

    with pytest.raises(StagingError, match="enlace simbólico"):
        _instala(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )
    assert (ajeno / "viejo.html").read_text() == "archivo externo"


def test_las_lapidas_entran_en_el_identificador(tmp_path: Path) -> None:  # noqa: D103
    destinos = _destinos(tmp_path)
    destinos["dashboard"].mkdir(parents=True)
    (destinos["dashboard"] / "retirado.html").write_text("se fue", encoding="utf-8")
    raiz_a = _staging_con_artefactos(tmp_path / "a")
    raiz_b = _staging_con_artefactos(tmp_path / "b")
    lapida = ("dashboard/retirado.html",)
    semilla = _semilla_de(destinos, lapida)
    # En `a` el archivo sigue tal cual en el candidato (heredado); en `b` lo retiró el
    # generador. Misma semilla, dos árboles: dos identificadores.
    (raiz_a / "outputs" / "dashboard" / "retirado.html").write_text("se fue", encoding="utf-8")
    sin = _sella_en(raiz_a, tmp_path, destinos=destinos, semilla=semilla)
    con = _sella_en(
        raiz_b,
        tmp_path,
        destinos=destinos,
        tombstones=lapida,
        semilla=semilla,
        politica=_politica(tmp_path, retirables=lapida),
    )

    assert sin.run_id != con.run_id
    assert sin.run_id == calcula_run_id_de(sin)


# ── 16 · la transición de cada archivo tiene DOS estados independientes ─────
#
# Registrar «esta ruta entra en la transacción» no dice si el original llegó a apartarse
# ni si el nuevo llegó a publicarse. Con un solo registro, un fallo ANTES de apartar hacía
# que el rollback borrase el original y no tuviera nada que restaurar.


def _falla_en(nombre: str, cuando: str):
    """Reemplazo de `Path.replace` que falla en una transición concreta y determinista."""
    original = Path.replace

    def _reemplazo(self, target):  # type: ignore[no-untyped-def]
        apartando = str(target).endswith(".prev")
        publicando = str(self).endswith(".part")
        if self.name.startswith(nombre) or target.name.startswith(nombre):
            if cuando == "al_apartar" and apartando:
                raise OSError("fallo inyectado al apartar el original")
            if cuando == "al_publicar" and publicando:
                raise OSError("fallo inyectado al publicar el nuevo")
        return original(self, target)

    return _reemplazo


@pytest.mark.parametrize("cuando", ["al_apartar", "al_publicar"])
def test_un_fallo_en_cualquier_transicion_conserva_el_original(
    tmp_path: Path, monkeypatch, cuando: str
) -> None:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    destinos = _destinos(tmp_path)
    _puebla_destino(raiz, destinos, "version anterior")
    manifiesto = _sella_aplicable(raiz, tmp_path, destinos=destinos)

    monkeypatch.setattr(Path, "replace", _falla_en("index.html", cuando))
    with pytest.raises(OSError):
        _instala(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )
    monkeypatch.undo()

    anterior = destinos["dashboard"] / "Reports" / "index.html"
    assert anterior.exists(), f"el original desapareció tras el rollback ({cuando})"
    assert anterior.read_text(encoding="utf-8") == "version anterior"
    for raiz_destino in destinos.values():
        assert list(raiz_destino.rglob("*.prev")) == []
        assert list(raiz_destino.rglob("*.part")) == []


# ── 17 · una escritura corta no puede publicarse ───────────────────────────


def test_una_escritura_corta_se_completa_en_vez_de_truncar(tmp_path: Path, monkeypatch) -> None:
    """`os.write` puede escribir menos bytes de los pedidos sin decirlo al llamador.

    Una sola llamada publicaba el archivo truncado. Con el bucle, una escritura corta deja
    de ser un defecto: se completa.
    """
    import os as _os

    original = _os.write
    monkeypatch.setattr(_os, "write", lambda fd, datos: original(fd, datos[:2]))
    raiz = _staging_con_artefactos(tmp_path / "staging")
    manifiesto = _sella_en(raiz, tmp_path)
    monkeypatch.undo()

    crudo = (raiz / "manifest.json").read_bytes()
    assert json.loads(crudo)["run_id"] == manifiesto.run_id
    assert (raiz / "manifest.sha256").read_text().strip() == hashlib.sha256(crudo).hexdigest()


def test_una_escritura_que_miente_sobre_lo_escrito_no_se_publica(
    tmp_path: Path, monkeypatch
) -> None:
    """Si la escritura declara más bytes de los que puso, lo caza el digest del temporal."""
    raiz, manifiesto = _sella(tmp_path)
    destinos = _destinos(tmp_path)
    import os as _os

    original = _os.write

    def write_mentiroso(fd, datos):  # type: ignore[no-untyped-def]
        original(fd, datos[:2])
        return len(datos)

    monkeypatch.setattr(_os, "write", write_mentiroso)
    with pytest.raises(StagingError, match="truncad"):
        _instala(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )
    monkeypatch.undo()

    assert not (destinos["dashboard"] / "Reports" / "index.html").exists()
    for raiz_destino in destinos.values():
        assert list(raiz_destino.rglob("*.part")) == []


# ── 18 · una lápida necesita AUTORIDAD, no sólo una foto del destino ────────


def test_una_lapida_fuera_de_la_semilla_no_se_sella(tmp_path: Path) -> None:
    """El negativo exacto: archivo presente antes del sello y ausente de la semilla.

    El baseline sólo fotografía lo que se le ordenó borrar. Si eso bastara, cualquier
    `--tombstone` adquiriría autoridad por el mero hecho de existir en el destino.
    """
    destinos = _destinos(tmp_path)
    destinos["dashboard"].mkdir(parents=True)
    (destinos["dashboard"] / "del_usuario.html").write_text("trabajo ajeno", encoding="utf-8")
    raiz = _staging_con_artefactos(tmp_path / "staging")

    politica = _politica(tmp_path, retirables=("dashboard/del_usuario.html",))
    ejecuta_gates(raiz, politica, destinos_vivos=destinos)
    fab.hidrata_minimo(raiz, head_backend=HEAD_BACKEND)
    with pytest.raises(StagingError, match="no está en la semilla"):
        sella(
            raiz,
            _entrada(),
            baseline=calcula_baseline(
                destinos, set(_relativos_de(raiz)) | {"dashboard/del_usuario.html"}
            ),
            semilla={},
            politica=politica,
            tombstones=("dashboard/del_usuario.html",),
            contrato=fab.CONTRATO,
            autoridad_lapidas=AutoridadLapidas(
                eliminados_reales=frozenset(), allowlist=frozenset()
            ),
        )
    assert (destinos["dashboard"] / "del_usuario.html").exists()


def test_una_lapida_cuyo_digest_cambio_no_se_sella(tmp_path: Path) -> None:
    """Estaba en la semilla, pero el destino ya no es el que la semilla vio."""
    destinos = _destinos(tmp_path)
    destinos["dashboard"].mkdir(parents=True)
    objetivo = destinos["dashboard"] / "viejo.html"
    objetivo.write_text("editado por el usuario", encoding="utf-8")
    raiz = _staging_con_artefactos(tmp_path / "staging")

    politica = _politica(tmp_path, retirables=("dashboard/viejo.html",))
    ejecuta_gates(raiz, politica, destinos_vivos=destinos)
    fab.hidrata_minimo(raiz, head_backend=HEAD_BACKEND)
    with pytest.raises(StagingError, match="cambió en el destino"):
        sella(
            raiz,
            _entrada(),
            baseline=calcula_baseline(
                destinos, set(_relativos_de(raiz)) | {"dashboard/viejo.html"}
            ),
            semilla={"dashboard/viejo.html": "0" * 64},
            politica=politica,
            tombstones=("dashboard/viejo.html",),
            contrato=fab.CONTRATO,
            autoridad_lapidas=AutoridadLapidas(
                eliminados_reales=frozenset({"dashboard/viejo.html"}),
                allowlist=frozenset({"dashboard/viejo.html"}),
            ),
        )


# ── 19 · un sello sin composición verificada no se aplica ───────────────────


def test_un_sello_borrador_no_se_aplica(tmp_path: Path) -> None:
    """Un borrador anterior a P0.6 sigue sin poder instalarse.

    El modo vive en el manifiesto: encender `CONFINAMIENTO_LISTO` no promueve lo que ya
    estaba sellado como borrador. Se construye uno como los que dejaron las rondas previas.
    """
    raiz = _staging_con_artefactos(tmp_path / "staging")
    manifiesto = _sella_en(raiz, tmp_path)
    manifiesto.modo = MODO_DRAFT
    manifiesto.motivo_draft = MOTIVO_P06
    manifiesto.run_id = calcula_run_id_de(manifiesto)
    manifiesto.escribe(raiz / "manifest.json")

    assert Manifiesto.lee(raiz / "manifest.json").modo == MODO_DRAFT
    with pytest.raises(StagingError, match="draft|no aplicable"):
        _instala(
            raiz,
            manifiesto,
            _destinos(tmp_path),
            head_backend=HEAD_BACKEND,
            head_dashboard=HEAD_DASHBOARD,
        )


# ── 20 · la autoridad de una lápida no la da la ausencia ───────────────────
#
# Dos fugas distintas, cerradas juntas porque comparten causa: la ausencia de un archivo
# en el candidato no prueba que un generador lo retirase.


def _autoridad(
    eliminados: tuple[str, ...] = (), allowlist: tuple[str, ...] = ()
) -> AutoridadLapidas:
    return AutoridadLapidas(
        eliminados_reales=frozenset(eliminados), allowlist=frozenset(allowlist)
    )


def _sella_con_autoridad(
    raiz: Path,
    destinos: dict[str, Path],
    tombstones: tuple[str, ...],
    autoridad,
    semilla: dict[str, str],
    tmp_path: Path,
) -> Manifiesto:
    politica = _politica(tmp_path, retirables=tombstones)
    ejecuta_gates(raiz, politica, destinos_vivos=destinos)
    fab.hidrata_minimo(raiz, head_backend=HEAD_BACKEND)
    return sella(
        raiz,
        _entrada(),
        semilla=semilla,
        baseline=calcula_baseline(destinos, set(_relativos_de(raiz)) | set(tombstones)),
        politica=politica,
        tombstones=tombstones,
        contrato=fab.CONTRATO,
        autoridad_lapidas=autoridad,
    )


def test_un_archivo_sembrado_e_intacto_no_puede_volverse_lapida(tmp_path: Path) -> None:
    """La poda retira del staging lo idéntico a la semilla; eso NO es una eliminación.

    Sin distinguir las dos ausencias, cualquier artefacto que no cambió esta semana quedaba
    autorizado para borrarse del sitio.
    """
    destinos = _destinos(tmp_path)
    destinos["dashboard"].mkdir(parents=True)
    intacto = destinos["dashboard"] / "intacto.html"
    intacto.write_text("no cambió esta semana", encoding="utf-8")
    raiz = _staging_con_artefactos(tmp_path / "staging")
    digest = hashlib.sha256(intacto.read_bytes()).hexdigest()

    with pytest.raises(StagingError, match="no la retiró ningún generador"):
        _sella_con_autoridad(
            raiz,
            destinos,
            ("dashboard/intacto.html",),
            # La semilla lo tenía y la poda lo quitó, pero NO está entre los eliminados
            # reales, porque seguía presente antes de podar.
            _autoridad(eliminados=(), allowlist=("dashboard/intacto.html",)),
            {"dashboard/intacto.html": digest},
            tmp_path,
        )
    assert intacto.exists()


def test_una_lapida_sin_semilla_aborta(tmp_path: Path) -> None:
    """`semilla=None` desactivaba la autoridad entera y el sello se creaba igual."""
    destinos = _destinos(tmp_path)
    destinos["dashboard"].mkdir(parents=True)
    (destinos["dashboard"] / "ajeno.html").write_text("archivo ajeno", encoding="utf-8")
    raiz = _staging_con_artefactos(tmp_path / "staging")

    with pytest.raises(StagingError, match="semilla"):
        _sella_con_autoridad(
            raiz,
            destinos,
            ("dashboard/ajeno.html",),
            _autoridad((), ("dashboard/ajeno.html",)),
            {},
            tmp_path,
        )
    assert (destinos["dashboard"] / "ajeno.html").exists()


def test_una_eliminacion_real_y_permitida_se_acepta(tmp_path: Path) -> None:
    destinos = _destinos(tmp_path)
    destinos["dashboard"].mkdir(parents=True)
    retirado = destinos["dashboard"] / "obsoleto.html"
    retirado.write_text("lo retiró el generador", encoding="utf-8")
    raiz = _staging_con_artefactos(tmp_path / "staging")
    digest = hashlib.sha256(retirado.read_bytes()).hexdigest()

    manifiesto = _sella_con_autoridad(
        raiz,
        destinos,
        ("dashboard/obsoleto.html",),
        _autoridad(
            eliminados=("dashboard/obsoleto.html",),
            allowlist=("dashboard/obsoleto.html",),
        ),
        {"dashboard/obsoleto.html": digest},
        tmp_path,
    )

    assert manifiesto.tombstones == ("dashboard/obsoleto.html",)


def test_una_eliminacion_real_fuera_de_la_allowlist_aborta(tmp_path: Path) -> None:
    """Pertenecer a la semilla no prueba que la ruta sea administrable."""
    destinos = _destinos(tmp_path)
    destinos["dashboard"].mkdir(parents=True)
    retirado = destinos["dashboard"] / "obsoleto.html"
    retirado.write_text("lo retiró el generador", encoding="utf-8")
    raiz = _staging_con_artefactos(tmp_path / "staging")
    digest = hashlib.sha256(retirado.read_bytes()).hexdigest()

    with pytest.raises(StagingError, match="allowlist|política"):
        _sella_con_autoridad(
            raiz,
            destinos,
            ("dashboard/obsoleto.html",),
            _autoridad(eliminados=("dashboard/obsoleto.html",), allowlist=()),
            {"dashboard/obsoleto.html": digest},
            tmp_path,
        )
    assert retirado.exists()


def test_la_poda_distingue_lo_retirado_de_lo_intacto(tmp_path: Path) -> None:
    """`poda_a_cambiados` tiene que declarar las dos ausencias por separado."""
    outputs = tmp_path / "outputs"
    (outputs / "dashboard").mkdir(parents=True)
    (outputs / "dashboard" / "cambiado.html").write_text("nuevo", encoding="utf-8")
    (outputs / "dashboard" / "intacto.html").write_text("igual", encoding="utf-8")
    semilla = {
        "dashboard/intacto.html": hashlib.sha256(b"igual").hexdigest(),
        "dashboard/cambiado.html": hashlib.sha256(b"viejo").hexdigest(),
        "dashboard/borrado.html": hashlib.sha256(b"se fue").hexdigest(),
    }

    poda = poda_a_cambiados(outputs, semilla)

    assert set(poda.cambiados) == {"dashboard/cambiado.html"}
    assert poda.eliminados_reales == frozenset({"dashboard/borrado.html"})
    assert not (outputs / "dashboard" / "intacto.html").exists()


def test_una_corrida_que_solo_retira_tambien_se_sella(tmp_path: Path) -> None:
    """Si sólo hay lápidas y ningún artefacto nuevo, sigue siendo una corrida.

    El atajo «no cambió nada, no hay nada que sellar» se tragaba las lápidas en silencio y
    el sitio conservaba lo obsoleto.
    """
    destinos = _destinos(tmp_path)
    destinos["dashboard"].mkdir(parents=True)
    (destinos["dashboard"] / "obsoleto.html").write_text("se va", encoding="utf-8")
    raiz = tmp_path / "staging"
    (raiz / "outputs" / "dashboard").mkdir(parents=True)

    semilla = _semilla_de(destinos, ("dashboard/obsoleto.html",))
    politica = _politica(
        tmp_path,
        superficies=("dashboard/obsoleto.html",),
        retirables=("dashboard/obsoleto.html",),
    )
    ejecuta_gates(raiz, politica, destinos_vivos=destinos)
    fab.hidrata_minimo(raiz, head_backend=HEAD_BACKEND)
    manifiesto = sella(
        raiz,
        _entrada(),
        semilla=semilla,
        baseline=calcula_baseline(destinos, {"dashboard/obsoleto.html"}),
        politica=politica,
        tombstones=("dashboard/obsoleto.html",),
        contrato=fab.CONTRATO,
        autoridad_lapidas=_autoridad_de(raiz, destinos, ("dashboard/obsoleto.html",)),
    )

    assert manifiesto.inventario == {}
    assert manifiesto.tombstones == ("dashboard/obsoleto.html",)


# ── 21 · las lápidas se derivan; no se declaran ni se olvidan ──────────────
#
# La correspondencia entre lo que el candidato retiró y lo que el sello declara es una
# IGUALDAD. Validar sólo `lápidas ⊆ eliminadas` dejaba pasar el error simétrico: una
# eliminación real que nadie declaraba se ignoraba en silencio y el sitio conservaba lo
# obsoleto. Derivarlas del censo elimina las dos formas de equivocarse a la vez.


def _trabajo_con_borrado(raiz: Path, *, cambia_algo: bool) -> Path:
    """Staging cuyo generador retiró `dashboard/obsoleto.html` de la semilla."""
    from epiforecast.publication.weekly_staging import snapshot_digests

    salida = raiz / "outputs" / "dashboard"
    salida.mkdir(parents=True)
    # El destino que usará `_argv_seal` ya tiene el archivo: la lápida exige que exista
    # allí con el digest que la semilla vio.
    destino = raiz.parent / f"dest_{raiz.name}"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "obsoleto.html").write_text("estaba en el sitio", encoding="utf-8")
    (salida / "obsoleto.html").write_text("estaba en el sitio", encoding="utf-8")
    (salida / "otro.html").write_text("viejo", encoding="utf-8")
    (raiz / "semilla.json").write_text(
        json.dumps(snapshot_digests(raiz / "outputs")), encoding="utf-8"
    )
    (salida / "obsoleto.html").unlink()
    if cambia_algo:
        (salida / "otro.html").write_text("nuevo", encoding="utf-8")
    return raiz


def _sellado_en(directorio: Path) -> Manifiesto | None:
    for candidato in directorio.iterdir():
        if candidato.is_dir() and (candidato / "manifest.json").is_file():
            return Manifiesto.lee(candidato / "manifest.json")
    return None


def test_una_eliminacion_real_sin_politica_aborta(tmp_path: Path) -> None:
    """Antes: rc=0 y sello sin lápidas. El obsoleto sobrevivía en el sitio."""
    from scripts.refresh_staging import main

    trabajo = _trabajo_con_borrado(tmp_path / "a", cambia_algo=True)

    assert main(_argv_seal(trabajo)) == 1
    assert _sellado_en(tmp_path) is None


def test_una_eliminacion_real_se_sella_sin_que_nadie_la_declare(tmp_path: Path) -> None:
    from scripts.refresh_staging import main

    trabajo = _trabajo_con_borrado(tmp_path / "a", cambia_algo=True)

    assert main(_argv_seal(trabajo, allowlist={"dashboard/obsoleto.html"})) == 0

    sellado = _sellado_en(tmp_path)
    assert sellado is not None
    assert sellado.tombstones == ("dashboard/obsoleto.html",)
    assert set(sellado.inventario) == {"dashboard/otro.html"}


def test_una_eliminacion_sin_ningun_cambio_tambien_se_sella(tmp_path: Path) -> None:
    """Antes: rc=0 y ni siquiera se creaba el sello."""
    from scripts.refresh_staging import main

    trabajo = _trabajo_con_borrado(tmp_path / "a", cambia_algo=False)

    assert main(_argv_seal(trabajo, allowlist={"dashboard/obsoleto.html"})) == 0

    sellado = _sellado_en(tmp_path)
    assert sellado is not None
    assert sellado.tombstones == ("dashboard/obsoleto.html",)
    assert sellado.inventario == {}


# ── 22 · P0.9 · la composición se calcula, no se declara ───────────────────


def test_la_composicion_es_semilla_mas_cambiados_menos_lapidas() -> None:
    """Algoritmo canónico, con las rutas ordenadas y digest de 64 hex."""
    semilla = {"dashboard/a.html": "1" * 64, "dashboard/b.html": "2" * 64}
    cambiados = {"dashboard/b.html": "3" * 64, "dashboard/c.html": "4" * 64}

    digest, arbol = calcula_composicion(semilla, cambiados, ("dashboard/a.html",))

    assert arbol == {"dashboard/b.html": "3" * 64, "dashboard/c.html": "4" * 64}
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    # El orden de inserción no puede cambiar el resultado.
    assert (
        digest
        == calcula_composicion(dict(reversed(semilla.items())), cambiados, ("dashboard/a.html",))[
            0
        ]
    )


def test_la_composicion_del_sello_la_calcula_el_sello(tmp_path: Path) -> None:
    """El flujo real: gates sobre el árbol completo, poda, y el sello recompone lo mismo.

    Un archivo heredado de la semilla e intacto se poda del staging, pero sigue formando
    parte de la composición: la que midieron los gates y la que `apply` reconstruiría.
    """
    raiz = _staging_con_artefactos(tmp_path / "staging")
    heredado = raiz / "outputs" / "dashboard" / "heredado.html"
    heredado.write_text("heredado e intacto", encoding="utf-8")
    semilla = {"dashboard/heredado.html": sha256_de(heredado)}
    politica = _politica(
        tmp_path, superficies=(*SUPERFICIES_DEL_STAGING, "dashboard/heredado.html")
    )
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    completa, _ = calcula_composicion({}, inventaria(raiz / "outputs"), ())
    poda = poda_a_cambiados(raiz / "outputs", semilla)
    assert not heredado.exists() and "dashboard/heredado.html" not in poda.cambiados

    manifiesto = _sella_en(raiz, tmp_path, semilla=semilla, politica=politica, corre_gates=False)

    assert manifiesto.composicion == completa
    assert "dashboard/heredado.html" not in manifiesto.inventario
    assert re.fullmatch(r"[0-9a-f]{64}", manifiesto.composicion)


def test_una_semilla_que_promete_un_archivo_que_los_gates_no_vieron_no_sella(
    tmp_path: Path,
) -> None:
    """Semilla con un archivo que ni está en el candidato ni tiene lápida.

    Antes, con gates fabricados a la medida de cualquier composición declarada, esto
    sellaba. Ahora la composición que midieron los gates no incluye ese archivo, y la que
    el sello recompone sí: no son el mismo árbol.
    """
    raiz = _staging_con_artefactos(tmp_path / "staging")

    with pytest.raises(StagingError, match="algo cambió después de los gates"):
        _sella_en(raiz, tmp_path, semilla={"dashboard/fantasma.html": "9" * 64})


def test_una_semilla_parcial_no_puede_sellar(tmp_path: Path) -> None:
    """Condición 2: la composición cubre el árbol administrado, no un trozo.

    El orquestador siembra hoy 18 de las 41 superficies publicadas. Sellar con esa semilla
    certificaría un sitio que no es el que se publica.
    """
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(
        tmp_path, superficies=(*SUPERFICIES_DEL_STAGING, "dashboard/no_sembrada.html")
    )

    with pytest.raises(StagingError, match="no cubre 1 superficie"):
        _sella_en(raiz, tmp_path, politica=politica)


def test_la_politica_queda_identificada_en_el_sello(tmp_path: Path) -> None:
    """Condición 4: versión y digest, para saber contra qué se aprobó la corrida."""
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)

    manifiesto = _sella_en(raiz, tmp_path, politica=politica)

    assert manifiesto.politica == {"version": VERSION_POLITICA, "sha256": politica.sha256}
    assert "politica" in manifiesto.payload_canonico()


def test_cambiar_la_politica_cambia_el_identificador(tmp_path: Path) -> None:
    raiz_a = _staging_con_artefactos(tmp_path / "a")
    raiz_b = _staging_con_artefactos(tmp_path / "b")

    uno = _sella_en(raiz_a, tmp_path, politica=_politica(tmp_path))
    otro = _sella_en(raiz_b, tmp_path, politica=_politica(tmp_path, gates=("cifras",)))

    assert uno.run_id != otro.run_id


def _reescribe_indice(raiz: Path, mutador) -> None:
    """Edita `gates/indice.json` **y recalcula su sidecar**, como haría quien lo tocara.

    Igual que con el manifiesto: el sidecar detecta edición no revisada y corrupción, no es
    una firma. Estas pruebas miden las comprobaciones estructurales que vienen DESPUÉS.
    """
    ruta = raiz / DIR_EVIDENCIA / "indice.json"
    crudo = json.loads(ruta.read_text(encoding="utf-8"))
    mutador(crudo)
    cuerpo = json.dumps(crudo, indent=2, ensure_ascii=False, sort_keys=True).encode() + b"\n"
    ruta.write_bytes(cuerpo)
    (raiz / DIR_EVIDENCIA / "indice.sha256").write_text(
        hashlib.sha256(cuerpo).hexdigest() + "\n", encoding="utf-8"
    )


def test_evidencia_de_otra_politica_no_sella(tmp_path: Path) -> None:
    """Condición 5, primera capa: la política de la evidencia es la del HEAD, o nada."""
    raiz = _staging_con_artefactos(tmp_path / "staging")

    with pytest.raises(StagingError, match="no es la misma política"):
        _sella_en(
            raiz,
            tmp_path,
            politica=_politica(tmp_path, gates=("cifras", "rag")),
            politica_para_gates=_politica(tmp_path, gates=("cifras",)),
        )


def test_un_gate_de_menos_en_la_evidencia_se_rechaza(tmp_path: Path) -> None:
    """Condición 5, segunda capa: misma política, evidencia a la que le falta un gate.

    Se edita la evidencia dejándola internamente coherente —índice, sidecar y archivos—
    para que lo que falle sea la comparación con la política, no la integridad.
    """
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    shutil.rmtree(raiz / DIR_EVIDENCIA / "rag")
    _reescribe_indice(raiz, lambda d: d["gates"].pop("rag"))
    _reescribe_observacional(raiz, lambda d: d["gates"].pop("rag"))

    with pytest.raises(StagingError, match="faltan resultados de gates"):
        _sella_en(raiz, tmp_path, politica=politica, corre_gates=False)


def test_un_gate_de_mas_en_la_evidencia_se_rechaza(tmp_path: Path) -> None:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    shutil.copytree(raiz / DIR_EVIDENCIA / "rag", raiz / DIR_EVIDENCIA / "inventado")

    def mete_gate(d: dict) -> None:
        d["gates"]["inventado"] = dict(d["gates"]["rag"], gate="inventado")

    _reescribe_indice(raiz, mete_gate)
    _reescribe_observacional(raiz, lambda d: d["gates"].update(inventado=d["gates"]["rag"]))

    with pytest.raises(StagingError, match="que la política no declara"):
        _sella_en(raiz, tmp_path, politica=politica, corre_gates=False)


def test_un_argv_editado_en_la_evidencia_no_cuadra_con_la_politica(tmp_path: Path) -> None:
    """Misma política, mismo conjunto de gates, pero la evidencia dice que corrió OTRO argv.

    Es el caso «resultado de otro gate»: la identidad del gate coincide y el comando no.
    La evidencia se deja coherente consigo misma para que falle la comparación con la
    política y no la integridad.
    """
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    _reescribe_indice(raiz, lambda d: d["gates"]["cifras"].update(argv=["/usr/bin/env", "true"]))

    with pytest.raises(StagingError, match="ejecutó otro comando"):
        _sella_en(raiz, tmp_path, politica=politica, corre_gates=False)


def _reescribe_observacional(raiz: Path, mutador) -> None:
    ruta = raiz / DIR_EVIDENCIA / "observacional.json"
    crudo = json.loads(ruta.read_text(encoding="utf-8"))
    mutador(crudo)
    ruta.write_text(json.dumps(crudo, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_un_gate_corrido_sobre_otra_composicion_aborta(tmp_path: Path) -> None:
    """Condiciones 6 y 7: si un byte cambia tras los gates, hay que repetirlos.

    El caso real: los gates corren, y después alguien toca un artefacto. La composición
    recompuesta por `sella` deja de coincidir con la que midieron.
    """
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    (raiz / "outputs" / "dashboard" / "Reports" / "index.html").write_text(
        "regenerado despues de los gates", encoding="utf-8"
    )

    with pytest.raises(StagingError, match="algo cambió después de los gates"):
        _sella_en(raiz, tmp_path, politica=politica, corre_gates=False)


def test_un_sello_verificado_sale_aplicable_tras_p06(tmp_path: Path) -> None:
    """Condición 8 cerrada: composición, política y gates cuadran, y la instalación está
    confinada a worktrees desechables, así que el sello nuevo es aplicable y sin motivo.
    """
    raiz = _staging_con_artefactos(tmp_path / "staging")

    manifiesto = _sella_en(raiz, tmp_path)

    assert CONFINAMIENTO_LISTO is True
    assert manifiesto.modo == MODO_APLICABLE
    assert manifiesto.motivo_draft == ""
    assert Manifiesto.lee(raiz / "manifest.json").modo == MODO_APLICABLE


# ── 23 · los dos universos y la política canónica ──────────────────────────


def test_un_archivo_no_administrado_no_se_sella(tmp_path: Path) -> None:
    """La cobertura se validaba en un solo sentido: faltantes sí, extras no.

    Un archivo que nadie administra colado en el árbol compuesto se sellaba sin protestar.
    """
    raiz = _staging_con_artefactos(tmp_path / "staging")
    (raiz / "outputs" / "ajeno").mkdir()
    (raiz / "outputs" / "ajeno" / "colado.txt").write_text("no soy de aquí", encoding="utf-8")

    with pytest.raises(StagingError, match="ruta sellable fuera de los prefijos"):
        _sella_en(raiz, tmp_path)


def test_un_prefijo_no_administrado_por_la_politica_no_se_sella(tmp_path: Path) -> None:
    """La gramática admite `backend/`; la política puede no administrarlo."""
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica_cruda(superficies=SUPERFICIES_DEL_STAGING, prefijos=("dashboard/",))

    with pytest.raises(StagingError, match="que la política no administra"):
        _sella_en(
            raiz, tmp_path, politica=PoliticaCenso.desde_bytes(json.dumps(politica).encode())
        )


def test_una_superficie_no_censada_no_se_sella(tmp_path: Path) -> None:
    """El otro sentido del censo: una página nueva que nadie revisó."""
    raiz = _staging_con_artefactos(tmp_path / "staging")
    (raiz / "outputs" / "dashboard" / "pagina_nueva.html").write_text("nueva", encoding="utf-8")

    with pytest.raises(StagingError, match="que el censo no declara"):
        _sella_en(raiz, tmp_path, politica=_politica(tmp_path))


def test_las_tablas_del_backend_no_son_superficie(tmp_path: Path) -> None:
    """`backend/validacion.html` está administrado pero no se publica."""
    politica = _politica(tmp_path)

    assert politica.es_superficie("dashboard/Reports/index.html")
    assert not politica.es_superficie("backend/validacion.html")
    assert not politica.es_superficie("dashboard/epibot/node_modules/paquete/package.json")


def test_una_politica_fuera_del_repositorio_no_vale(tmp_path: Path) -> None:
    repo, head = _repo_con_politica(tmp_path / "repo", _politica_cruda())
    fuera = tmp_path / "politica_suelta.json"
    fuera.write_text(json.dumps(_politica_cruda()), encoding="utf-8")

    with pytest.raises(StagingError, match="no está en"):
        PoliticaCenso.del_head(fuera.parent, head)


def test_una_politica_sin_confirmar_no_vale(tmp_path: Path) -> None:
    """Modificada en el árbol de trabajo: difiere del commit que se está sellando."""
    repo, head = _repo_con_politica(tmp_path / "repo", _politica_cruda())
    ruta = repo / "config" / "publication" / "politica_censo.json"
    ruta.write_text(json.dumps(_politica_cruda(gates=("otro",))), encoding="utf-8")

    with pytest.raises(StagingError, match="difiere de la versión"):
        PoliticaCenso.del_head(repo, head)


def test_una_politica_ausente_del_commit_no_vale(tmp_path: Path) -> None:
    repo, head = _repo_con_politica(tmp_path / "repo", _politica_cruda())
    (repo / "config" / "publication" / "politica_censo.json").unlink()

    with pytest.raises(StagingError, match="no existe en el árbol de trabajo"):
        PoliticaCenso.del_head(repo, head)


def test_la_politica_canonica_del_repositorio_es_valida() -> None:
    """La política real del repo tiene que parsear con el parser canónico."""
    from scripts.refresh_staging import POLITICA_CANONICA

    politica = PoliticaCenso.desde_bytes(POLITICA_CANONICA.read_bytes())

    assert politica.version == VERSION_POLITICA
    assert politica.superficies_verificables
    assert politica.ids_gates == ("cifras", "rag")
    assert politica.prefijo_publicado == "dashboard/"
    # Los gates reales corren `node` directamente, no `npm run` (que pasa por `sh -c`).
    assert all(gate.argv[0] == "node" for gate in politica.gates)
    assert all(gate.cwd == "dashboard/epibot/" for gate in politica.gates)


# ── 24 · el censo replica la regla del gate real, y la política no se elige ─


def test_los_directorios_ocultos_se_excluyen_como_en_el_gate(tmp_path: Path) -> None:
    """`cifras_contrato.mjs` salta cualquier directorio oculto, no sólo los enumerados.

    Copiar la lista y olvidar el `startsWith('.')` daba dos censos que se creen el mismo:
    `.claude/settings.local.json` era superficie aquí y no allí.
    """
    politica = _politica(tmp_path)

    assert not politica.es_superficie("dashboard/.claude/settings.local.json")
    assert not politica.es_superficie("dashboard/.github/workflows/algo.json")
    assert not politica.es_superficie("dashboard/epibot/node_modules/x/package.json")
    assert politica.es_superficie("dashboard/Reports/index.html")


def test_la_politica_canonica_no_declara_superficies_bajo_ocultos() -> None:
    from scripts.refresh_staging import POLITICA_CANONICA

    politica = PoliticaCenso.desde_bytes(POLITICA_CANONICA.read_bytes())

    assert all(politica.es_superficie(rel) for rel in politica.superficies_verificables)


def test_un_alias_interno_a_la_politica_no_vale(tmp_path: Path) -> None:
    """`resolve()` seguía el enlace antes de comprobar la pertenencia al repositorio.

    Con la ruta fija el vector desaparece por construcción; el `lstat` cubre el caso de que
    sea la propia ruta canónica la que se sustituya por un alias.
    """
    repo, head = _repo_con_politica(tmp_path / "repo", _politica_cruda())
    canonica = repo / "config" / "publication" / "politica_censo.json"
    real = repo / "config" / "publication" / "real.json"
    canonica.rename(real)
    canonica.symlink_to(real)

    with pytest.raises(StagingError, match="es un enlace"):
        PoliticaCenso.del_head(repo, head)


@pytest.mark.parametrize(
    ("mutador", "mensaje"),
    [
        (lambda d: d.update(gates=[_gate("cifras"), _gate("cifras")]), "id duplicado"),
        (lambda d: d.update(gates=[_gate("  ")]), "id de gate inválido"),
        (lambda d: d.update(gates=["cifras", "rag"]), "no como str"),
        (lambda d: d.update(version="censo/1"), "otra versión"),
        (lambda d: d.update(prefijos_administrados=["dashboard"]), "terminar en"),
        (lambda d: d.update(version=""), "versión legible"),
        (lambda d: d.update(superficies_verificables=[1]), "lista de cadenas"),
        (lambda d: d["patron_superficie"].update(prefijo="dashboard"), "terminar en"),
        (lambda d: d["patron_superficie"].update(sufijos=["html"]), "sufijo de superficie"),
        (lambda d: d.update(retirables=["dashboard/no_censada.html"]), "no administra"),
        # Coherencia entre piezas: bien escritas por separado, imposibles juntas.
        (lambda d: d["patron_superficie"].update(prefijo="../"), "componente inválido"),
        (lambda d: d.update(prefijos_administrados=[" dashboard/"]), "espacios en los bordes"),
        (
            lambda d: d["superficies_verificables"].append("backend/tabla.html"),
            "su propio patrón no reconoce",
        ),
        (
            lambda d: d["patron_superficie"].update(prefijo="publicado/"),
            "no cae bajo ningún prefijo administrado",
        ),
        (
            lambda d: d["patron_superficie"].update(directorios_excluidos=["a/b"]),
            "exclusión malformada",
        ),
        (lambda d: d.update(prefijos_administrados=["dashboard/../"]), "componente inválido"),
    ],
)
def test_el_parser_de_la_politica_falla_cerrado(mutador, mensaje: str) -> None:
    crudo = _politica_cruda()
    mutador(crudo)

    with pytest.raises(StagingError, match=mensaje):
        PoliticaCenso.desde_bytes(json.dumps(crudo).encode("utf-8"))


def test_una_clave_duplicada_en_la_politica_no_pasa() -> None:
    """`json.loads` se queda con la última y no dice nada."""
    crudo = json.dumps(_politica_cruda())
    con_duplicado = crudo.replace('"version"', '"version": "censo/falso", "version"', 1)

    with pytest.raises(StagingError, match="clave duplicada"):
        PoliticaCenso.desde_bytes(con_duplicado.encode("utf-8"))


# ── 25 · P0.2/P0.8 · la entrada se deriva de la hidratación y el candidato cumple ──


def test_sin_hidratacion_no_hay_sello(tmp_path: Path) -> None:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))

    with pytest.raises(StagingError, match="no hay hidratación registrada"):
        sella(
            raiz,
            _entrada(),
            semilla={},
            baseline=calcula_baseline(_destinos(tmp_path), set(_relativos_de(raiz))),
            politica=politica,
            autoridad_lapidas=AutoridadLapidas.sin_lapidas(),
            contrato=fab.CONTRATO,
        )


def test_el_sello_deriva_los_digests_del_consolidado_y_los_boletines(tmp_path: Path) -> None:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    # El candidato sólo AÑADE: filas de un padecimiento no publicado (como Obesidad en el
    # consolidado real), que el contrato ignora y el invariante aditivo admite.
    candidato = fab.consolidado_csv() + "2026,31,Aguascalientes,Obesidad,1,1,1\n"
    boletin = Boletin("2026_sem31.pdf", "https://ejemplo/sem31.pdf", 0, "")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    registro = fab.hidrata_minimo(
        raiz, head_backend=HEAD_BACKEND, candidato=candidato, boletines=(boletin,)
    )

    manifiesto = _sella_en(raiz, tmp_path, politica=politica, corre_gates=False)

    entrada = manifiesto.entrada
    assert entrada.digest_consolidado_antes == registro.entradas[fab.RUTA_CONSOLIDADO]["sha256"]
    assert entrada.digest_consolidado_candidato == hashlib.sha256(candidato.encode()).hexdigest()
    assert entrada.digest_consolidado_antes != entrada.digest_consolidado_candidato
    assert [b.nombre for b in entrada.boletines] == ["2026_sem31.pdf"]
    assert entrada.boletines[0].sha256 == manifiesto.inputs["inputs/boletines/2026_sem31.pdf"]
    assert (raiz / "inputs" / "consolidado_candidato.csv").read_text() == candidato
    assert set(manifiesto.inputs) == {
        "inputs/consolidado_base.csv",
        "inputs/consolidado_candidato.csv",
        "inputs/boletines/2026_sem31.pdf",
    }
    assert "inputs" in manifiesto.payload_canonico()


def test_un_candidato_que_cambia_una_fila_ya_publicada_no_sella(tmp_path: Path) -> None:
    """Invariante aditivo: base ⊆ candidato con los mismos valores. Una corrección de lo ya
    publicado no se cuela en un refresh semanal."""
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    fab.hidrata_minimo(
        raiz,
        head_backend=HEAD_BACKEND,
        candidato=fab.consolidado_csv().replace("3,10,12", "4,10,12"),
    )

    with pytest.raises(StagingError, match="cambió 16 fila\\(s\\) ya publicadas"):
        _sella_en(raiz, tmp_path, politica=politica, corre_gates=False)


def test_un_candidato_que_pierde_una_semana_publicada_no_sella(tmp_path: Path) -> None:
    """La base traía W29-W31; el candidato, W30-W31: cubre el contrato (profundidad 2,
    contiguas) y aun así perdió lo publicado. Sólo el ancla aditiva lo ve."""
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    fab.hidrata_minimo(
        raiz,
        head_backend=HEAD_BACKEND,
        consolidado=fab.consolidado_csv(semanas=((2026, 29), (2026, 30), (2026, 31))),
        candidato=fab.consolidado_csv(),
    )

    with pytest.raises(StagingError, match="perdió 8 fila\\(s\\) de la base"):
        _sella_en(raiz, tmp_path, politica=politica, corre_gates=False)


def test_las_semanas_del_sello_se_atan_a_los_cortes(tmp_path: Path) -> None:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    fab.hidrata_minimo(raiz, head_backend=HEAD_BACKEND)
    entrada = _entrada()

    entrada.semana_nueva = "2026,32"
    with pytest.raises(
        StagingError, match="no es el corte del consolidado candidato \\(2026, 31\\)"
    ):
        sella(
            raiz,
            entrada,
            semilla={},
            baseline=calcula_baseline(_destinos(tmp_path), inventaria(raiz / "outputs")),
            politica=politica,
            autoridad_lapidas=_autoridad_de(raiz, _destinos(tmp_path), ()),
            contrato=fab.CONTRATO,
        )
    entrada.semana_nueva = "2026,31"
    entrada.semana_anterior = "2026,30"
    with pytest.raises(StagingError, match="no es el corte del consolidado base \\(2026, 31\\)"):
        sella(
            raiz,
            entrada,
            semilla={},
            baseline=calcula_baseline(_destinos(tmp_path), inventaria(raiz / "outputs")),
            politica=politica,
            autoridad_lapidas=_autoridad_de(raiz, _destinos(tmp_path), ()),
            contrato=fab.CONTRATO,
        )
    entrada.semana_anterior = "semana 31"
    with pytest.raises(StagingError, match="forma AAAA,SS"):
        sella(
            raiz,
            entrada,
            semilla={},
            baseline=calcula_baseline(_destinos(tmp_path), inventaria(raiz / "outputs")),
            politica=politica,
            autoridad_lapidas=_autoridad_de(raiz, _destinos(tmp_path), ()),
            contrato=fab.CONTRATO,
        )


def test_la_semana_nueva_es_la_que_publica_el_epibot_del_candidato(tmp_path: Path) -> None:
    """knowledge.json dice W32 y el consolidado candidato corta en W31: no cuadra."""
    raiz = _staging_con_artefactos(tmp_path / "staging")
    (raiz / "outputs" / "dashboard" / "epibot" / "knowledge.json").write_text(
        fab.knowledge_json(max_semana=32), encoding="utf-8"
    )
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    fab.hidrata_minimo(raiz, head_backend=HEAD_BACKEND)

    with pytest.raises(
        StagingError, match="publica la semana \\(2026, 32\\) y el sello declara \\(2026, 31\\)"
    ):
        _sella_en(raiz, tmp_path, politica=politica, corre_gates=False)


def test_una_entrada_inmutable_reescrita_en_el_sandbox_no_sella(tmp_path: Path) -> None:
    """Un generador que escribe sobre un PDF (o un forecast) produjo un candidato que no salió
    de las entradas selladas."""
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    boletin = Boletin("2026_sem31.pdf", "https://ejemplo/sem31.pdf", 0, "")
    fab.hidrata_minimo(raiz, head_backend=HEAD_BACKEND, boletines=(boletin,))
    sandbox = tmp_path / "staging.sandbox" / "EpiForecast-MX"
    (sandbox / "data" / "raw_PDFs" / "2026_sem31.pdf").write_bytes(b"%PDF-otro")

    with pytest.raises(
        StagingError, match="entrada inmutable data/raw_PDFs/2026_sem31.pdf \\(pdf\\) cambió"
    ):
        _sella_en(raiz, tmp_path, politica=politica, corre_gates=False)


def test_el_sello_lleva_la_lista_de_entradas_y_la_exige(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    assert manifiesto.entrada.lista == {"version": "entradas/2", "sha256": "1" * 64}
    assert "lista" in manifiesto.payload_canonico()["entrada"]

    _reescribe_manifiesto(raiz, lambda d: d["entrada"].update(lista={}))
    with pytest.raises(StagingError, match="no identifica la lista de entradas"):
        Manifiesto.lee(raiz / "manifest.json")


def test_un_candidato_con_dengue_rezagado_no_sella(tmp_path: Path) -> None:
    """P0.8: el consolidado candidato corta Dengue una semana antes que neuro."""
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    fab.hidrata_minimo(
        raiz,
        head_backend=HEAD_BACKEND,
        candidato=fab.consolidado_csv(cortes={fab.PAD_CONTEO: (2026, 30)}),
    )

    with pytest.raises(StagingError, match="corte dispar"):
        _sella_en(raiz, tmp_path, politica=politica, corre_gates=False)
    assert not (raiz / "manifest.json").exists()


def test_una_copia_de_entrada_alterada_tras_sellar_rompe_la_verificacion(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    copia = raiz / "inputs" / "consolidado_base.csv"
    copia.write_text(copia.read_text(encoding="utf-8") + "2026,31,Jalisco,Dengue,1,0,0\n")

    with pytest.raises(StagingError, match="copias de entradas alteradas"):
        verifica(raiz, manifiesto, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)


def test_un_digest_de_entrada_editado_en_el_manifiesto_no_cuadra(tmp_path: Path) -> None:
    raiz, _ = _sella(tmp_path)
    _reescribe_manifiesto(raiz, lambda d: d["entrada"].update(digest_consolidado_antes="e" * 64))

    with pytest.raises(StagingError, match="digest_consolidado_antes no es el de la copia base"):
        Manifiesto.lee(raiz / "manifest.json")


def test_la_hidratacion_tiene_que_ser_del_head_que_se_sella(tmp_path: Path) -> None:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    fab.hidrata_minimo(raiz, head_backend="f" * 40)

    with pytest.raises(StagingError, match="la hidratación se hizo sobre ffffffffffff"):
        _sella_en(raiz, tmp_path, politica=politica, corre_gates=False)


def test_declarar_menos_padecimientos_no_desactiva_la_paridad(tmp_path: Path) -> None:
    """Interfaz alternativa cerrada: la paridad es entre los publicados del registry."""
    raiz = _staging_con_artefactos(tmp_path / "staging")
    politica = _politica(tmp_path)
    ejecuta_gates(raiz, politica, destinos_vivos=_destinos(tmp_path))
    fab.hidrata_minimo(
        raiz,
        head_backend=HEAD_BACKEND,
        candidato=fab.consolidado_csv(cortes={fab.PAD_NEURO: (2026, 30)}),
    )
    solo_dengue = SelloEntrada(
        head_backend=HEAD_BACKEND,
        head_dashboard=HEAD_DASHBOARD,
        semana_anterior="2026,30",
        semana_nueva="2026,31",
        padecimientos_autorizados=(fab.PAD_CONTEO,),
    )

    with pytest.raises(StagingError, match="corte dispar"):
        sella(
            raiz,
            solo_dengue,
            semilla={},
            baseline=calcula_baseline(_destinos(tmp_path), set(_relativos_de(raiz))),
            politica=politica,
            autoridad_lapidas=AutoridadLapidas.sin_lapidas(),
            contrato=fab.CONTRATO,
        )


@pytest.mark.parametrize("rel", ["dashboard/.GIT/HEAD", "backend/.Git/config"])
def test_git_en_mayusculas_tampoco_es_sellable(rel: str) -> None:
    """El disco de macOS no distingue mayúsculas; la gramática tampoco."""
    from epiforecast.publication.weekly_staging import valida_ruta_sellable

    with pytest.raises(StagingError, match="dentro de .git"):
        valida_ruta_sellable(rel)
