"""C7.2-A/R15.5 — el release REPRODUCE el forecast publicable sin `runs/`.

Éste es el criterio de cierre de C7.2-A: no basta con que el bundle verifique. Hay que cargar los
64 modelos finales desde el bundle, resolver exposición y geografía desde ``runtime_inputs/``,
pronosticar las 52 semanas, materializar los 111 productos y obtener EXACTAMENTE los frames que el
propio bundle transporta.

Para que "sin `runs/`" sea una afirmación verificada y no una promesa, la carga y la reproducción
corren con un guardia que revienta si algo intenta abrir un archivo bajo cualquiera de los dos
árboles de runs (el canónico del repo y la copia desde la que se construyó).
"""

from __future__ import annotations

import builtins
from collections.abc import Iterator
from contextlib import contextmanager
import io
import os
from pathlib import Path

import pytest

from epiforecast.runner.release_loader import bootstrap_engines, verify_bundle
from epiforecast.runner.release_reproduce import check_reproduction, reproduce_forecast
from tests.unit.runner import artifact_fixtures as af
from tests.unit.runner import release_fixtures as rf

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not af.hay_runs(),
        reason="los runs sellados de C5 no están en este entorno (runs/ gitignored)",
    ),
]


@contextmanager
def sin_leer(prohibidos: tuple[Path, ...]) -> Iterator[list[str]]:
    """Revienta si se abre cualquier archivo bajo ``prohibidos`` (incluye el parser C de pandas)."""
    abiertos: list[str] = []
    # `pathlib.Path.open` llama a `io.open`, NO a `builtins.open`: parchear sólo uno deja el
    # agujero por el que entra la mitad del código. `os.open` cubre lo de bajo nivel.
    real_open, real_io_open, real_os_open = builtins.open, io.open, os.open

    def vigilar(nombre: object) -> None:
        if not isinstance(nombre, (str, bytes, os.PathLike)):
            return
        try:
            path = Path(os.fsdecode(nombre)).resolve()
        except (TypeError, ValueError):  # pragma: no cover — descriptores y rutas raras
            return
        for raiz in prohibidos:
            if path == raiz or raiz in path.parents:
                abiertos.append(str(path))
                raise AssertionError(f"el release leyó {path}, que está bajo {raiz}")

    def abrir(file, *args, **kwargs):  # type: ignore[no-untyped-def]
        vigilar(file)
        return real_open(file, *args, **kwargs)

    def abrir_os(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        vigilar(path)
        return real_os_open(path, *args, **kwargs)

    builtins.open, io.open, os.open = abrir, abrir, abrir_os
    try:
        yield abiertos
    finally:
        builtins.open, io.open, os.open = real_open, real_io_open, real_os_open


@pytest.fixture(scope="module")
def construido(tmp_path_factory):
    """Bundle construido una vez; después, los runs de origen quedan prohibidos."""
    raiz = tmp_path_factory.mktemp("release")
    prep = rf.preparar(raiz)
    bundle = rf.construir_en(prep, raiz / "out")
    bootstrap_engines()  # el registry de adapters se puebla ANTES de cerrar la puerta a runs/
    return bundle, (prep.runs_root.resolve(), af.runs_root().resolve())


@pytest.mark.parametrize("via", ["pathlib", "builtins", "pandas"])
def test_el_guardia_de_lecturas_realmente_muerde(construido, via):
    """Guardia del guardia: si no detectara las lecturas, todo lo de abajo sería un falso verde."""
    import pandas as pd

    _bundle, prohibidos = construido
    objetivo = next(p for p in prohibidos[1].rglob("*.json") if p.is_file())
    with sin_leer(prohibidos), pytest.raises(AssertionError, match="que está bajo"):
        if via == "pathlib":
            objetivo.read_text(encoding="utf-8")
        elif via == "builtins":
            # noqa PTH123 a propósito: la vía que se prueba ES `builtins.open`, no `Path.open`.
            with builtins.open(objetivo, encoding="utf-8") as fh:  # noqa: PTH123
                fh.read()
        else:
            pd.read_json(objetivo)


def test_el_bundle_reproduce_el_forecast_exactamente_y_sin_runs(construido):
    bundle, prohibidos = construido
    with sin_leer(prohibidos):
        verificado = verify_bundle(bundle.path)
        reproduccion = check_reproduction(verificado, tol=0.0)

    conteos = verificado.counts
    assert len(reproduccion.base) == conteos["base_forecast"]
    assert len(reproduccion.products) == conteos["products_forecast"]
    assert reproduccion.max_delta_base == 0.0
    assert reproduccion.max_delta_products == 0.0


def test_la_reproducción_cubre_las_series_base_y_los_productos_declarados(construido):
    bundle, prohibidos = construido
    with sin_leer(prohibidos):
        verificado = verify_bundle(bundle.path)
        base, productos = reproduce_forecast(verificado)

    series = {(g, s) for g, s in zip(base["geography_id"], base["sex"], strict=True)}
    assert series == set(verificado.selection)
    assert len(series) == verificado.counts["base"]
    productos_unicos = {
        (n, g, s)
        for n, g, s in zip(
            productos["geography_level"], productos["geography_id"], productos["sex"], strict=True
        )
    }
    assert len(productos_unicos) == verificado.counts["products"]


def test_los_modelos_se_cargan_desde_el_bundle_y_no_desde_el_refit_original(construido):
    """Si el loader mirara `runs/`, el guardia lo delataría aunque el resultado coincidiera."""
    bundle, prohibidos = construido
    with sin_leer(prohibidos) as abiertos:
        verificado = verify_bundle(bundle.path)
    assert not abiertos
    assert sum(verificado.engines.values()) == verificado.counts["models"]


def test_alterar_un_insumo_de_ejecución_rompe_la_reproducción(construido, tmp_path):
    """Retirar o alterar una dependencia produce error TIPADO, no un forecast distinto en silencio."""
    from epiforecast.runner.artifact_identity import ArtifactValidationError
    from epiforecast.runner.release_runtime import RUNTIME_DIR

    bundle, _ = construido
    copia = rf.copia(bundle.path, tmp_path / "bundle")
    exposicion = sorted((copia / RUNTIME_DIR).glob("exposure_*.csv"))[0]
    exposicion.write_bytes(exposicion.read_bytes() + b"\n")
    rf.resellar(copia)
    with pytest.raises(ArtifactValidationError, match="digest"):
        verify_bundle(copia)


def test_sin_los_insumos_de_ejecución_el_bundle_no_carga(construido, tmp_path):
    from epiforecast.runner.artifact_identity import ArtifactValidationError
    from epiforecast.runner.release_runtime import RUNTIME_DIR

    bundle, _ = construido
    copia = rf.copia(bundle.path, tmp_path / "bundle")
    sorted((copia / RUNTIME_DIR).glob("exposure_*.csv"))[0].unlink()
    with pytest.raises(ArtifactValidationError, match="faltan"):
        verify_bundle(copia)
