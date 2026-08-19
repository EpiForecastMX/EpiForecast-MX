"""Contratos del staging sellado del refresh semanal.

Las seis situaciones que este sello existe para impedir: que se publique algo distinto
de lo revisado, que un artefacto cambie entre el sellado y la publicación, que el
repositorio avance por debajo, que se cuele un archivo que nadie inventarió, que la
instalación no sea fiel byte a byte, y que un fallo a media instalación deje el destino
publicado a medias.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from epiforecast.publication.weekly_staging import (
    Boletin,
    Manifiesto,
    SelloEntrada,
    StagingError,
    aplica,
    calcula_run_id,
    sella,
    verifica,
)

HEAD_BACKEND = "a" * 40
HEAD_DASHBOARD = "b" * 40


def _entrada() -> SelloEntrada:
    return SelloEntrada(
        head_backend=HEAD_BACKEND,
        head_dashboard=HEAD_DASHBOARD,
        digest_consolidado="c" * 64,
        semana_anterior="2026,30",
        semana_nueva="2026,31",
        padecimientos_autorizados=("Depresión", "Parkinson", "Alzheimer", "Dengue"),
        boletines=(
            Boletin(
                nombre="2026_sem31.pdf", url="https://ejemplo/sem31.pdf", bytes=10, sha256="d" * 64
            ),
        ),
    )


def _staging_con_artefactos(raiz: Path) -> Path:
    outputs = raiz / "outputs"
    (outputs / "dashboard" / "Reports").mkdir(parents=True)
    (outputs / "dashboard" / "epibot").mkdir(parents=True)
    (outputs / "dashboard" / "Reports" / "index.html").write_text(
        "<h1>galeria</h1>", encoding="utf-8"
    )
    (outputs / "dashboard" / "epibot" / "knowledge.json").write_text(
        '{"semana": 31}', encoding="utf-8"
    )
    (outputs / "backend").mkdir(parents=True)
    (outputs / "backend" / "validacion.html").write_text("<p>validacion</p>", encoding="utf-8")
    return raiz


def _sella(tmp_path: Path) -> tuple[Path, Manifiesto]:
    raiz = _staging_con_artefactos(tmp_path / "staging")
    return raiz, sella(raiz, _entrada())


def _destinos(tmp_path: Path) -> dict[str, Path]:
    return {
        "dashboard": tmp_path / "destino_dashboard",
        "backend": tmp_path / "destino_backend",
    }


# ── 1 · reproducibilidad ────────────────────────────────────────────────────


def test_el_mismo_contenido_sella_el_mismo_identificador(tmp_path: Path) -> None:
    """Dos preparaciones idénticas en directorios distintos deben coincidir."""
    uno = sella(_staging_con_artefactos(tmp_path / "uno"), _entrada())
    dos = sella(_staging_con_artefactos(tmp_path / "dos"), _entrada())

    assert uno.run_id == dos.run_id
    assert uno.inventario == dos.inventario


def test_el_identificador_no_depende_de_la_fecha(tmp_path: Path) -> None:
    """Si la fecha entrase en el cálculo, dos corridas iguales parecerían distintas."""
    raiz, manifiesto = _sella(tmp_path)
    recalculado = calcula_run_id(manifiesto.entrada, manifiesto.inventario)

    assert recalculado == manifiesto.run_id


def test_un_artefacto_distinto_cambia_el_identificador(tmp_path: Path) -> None:
    uno = sella(_staging_con_artefactos(tmp_path / "uno"), _entrada())
    otra = _staging_con_artefactos(tmp_path / "dos")
    (otra / "outputs" / "backend" / "validacion.html").write_text("otra cosa", encoding="utf-8")
    dos = sella(otra, _entrada())

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
    raiz, manifiesto = _sella(tmp_path)
    manifiesto.targets_dvc = ("models.dvc",)

    with pytest.raises(StagingError, match="no permitido"):
        verifica(raiz, manifiesto, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)


# ── 5 · la instalación es fiel byte a byte ──────────────────────────────────


def test_instala_exactamente_los_bytes_sellados(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    destinos = _destinos(tmp_path)

    instalados = aplica(
        raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
    )

    assert len(instalados) == 3
    assert (destinos["dashboard"] / "epibot" / "knowledge.json").read_text() == '{"semana": 31}'
    assert (destinos["dashboard"] / "Reports" / "index.html").read_text() == "<h1>galeria</h1>"
    assert (destinos["backend"] / "validacion.html").read_text() == "<p>validacion</p>"
    assert list(destinos["dashboard"].rglob("*.part")) == []


def test_la_instalacion_no_regenera_nada(tmp_path: Path) -> None:
    """Lo instalado sale del staging, no de volver a calcular: se comprueba el digest."""
    raiz, manifiesto = _sella(tmp_path)
    destinos = _destinos(tmp_path)
    aplica(raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)

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
        aplica(
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
        aplica(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )

    assert not destinos["dashboard"].exists()
    assert not destinos["backend"].exists()


# ── manifiesto: persistencia y forma ────────────────────────────────────────


def test_el_manifiesto_se_relee_identico(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    releido = Manifiesto.lee(raiz / "manifest.json")

    assert releido.como_dict() == manifiesto.como_dict()


def test_un_manifiesto_incompleto_se_rechaza(tmp_path: Path) -> None:
    ruta = tmp_path / "manifest.json"
    ruta.write_text('{"run_id": "abc"}', encoding="utf-8")

    with pytest.raises(StagingError, match="incompleto"):
        Manifiesto.lee(ruta)


def test_un_staging_vacio_no_se_sella(tmp_path: Path) -> None:
    (tmp_path / "staging" / "outputs").mkdir(parents=True)

    with pytest.raises(StagingError, match="nada que sellar"):
        sella(tmp_path / "staging", _entrada())


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
    raiz, manifiesto = _sella(tmp_path)
    destinos = _destinos(tmp_path)

    # El destino ya tiene una version anterior de cada artefacto.
    previos = {}
    for rel in manifiesto.inventario:
        partes = Path(rel).parts
        anterior = destinos[partes[0]].joinpath(*partes[1:])
        anterior.parent.mkdir(parents=True, exist_ok=True)
        contenido = f"version anterior de {rel}"
        anterior.write_text(contenido, encoding="utf-8")
        previos[anterior] = contenido

    # Falla a mitad de los renombrados: son 3 artefactos y cada uno aparta y publica.
    monkeypatch.setattr(Path, "replace", _replace_que_falla_en(4))

    with pytest.raises(OSError, match="fallo simulado"):
        aplica(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )

    monkeypatch.undo()

    # Todo vuelve a su version anterior: ni una mezcla de las dos.
    for ruta, contenido in previos.items():
        assert ruta.read_text(encoding="utf-8") == contenido, f"{ruta} quedo publicado a medias"


def test_un_fallo_durante_la_publicacion_no_deja_residuos(tmp_path: Path, monkeypatch) -> None:
    raiz, manifiesto = _sella(tmp_path)
    destinos = _destinos(tmp_path)
    for rel in manifiesto.inventario:
        partes = Path(rel).parts
        anterior = destinos[partes[0]].joinpath(*partes[1:])
        anterior.parent.mkdir(parents=True, exist_ok=True)
        anterior.write_text("anterior", encoding="utf-8")

    monkeypatch.setattr(Path, "replace", _replace_que_falla_en(4))
    with pytest.raises(OSError):
        aplica(
            raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD
        )
    monkeypatch.undo()

    for raiz_destino in destinos.values():
        assert list(raiz_destino.rglob("*.part")) == []
        assert list(raiz_destino.rglob("*.prev")) == []


def test_una_publicacion_correcta_no_deja_apartados(tmp_path: Path) -> None:
    raiz, manifiesto = _sella(tmp_path)
    destinos = _destinos(tmp_path)
    for rel in manifiesto.inventario:
        partes = Path(rel).parts
        anterior = destinos[partes[0]].joinpath(*partes[1:])
        anterior.parent.mkdir(parents=True, exist_ok=True)
        anterior.write_text("anterior", encoding="utf-8")

    aplica(raiz, manifiesto, destinos, head_backend=HEAD_BACKEND, head_dashboard=HEAD_DASHBOARD)

    for raiz_destino in destinos.values():
        assert list(raiz_destino.rglob("*.prev")) == []
        assert list(raiz_destino.rglob("*.part")) == []
    assert (destinos["dashboard"] / "epibot" / "knowledge.json").read_text() == '{"semana": 31}'
