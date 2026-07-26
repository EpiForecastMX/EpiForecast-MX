"""Copia AISLADA de los runs sellados de Obesidad + utilidades de mutación (C7.1/Acción 3).

Ninguna prueba escribe jamás bajo ``runs/`` real: el refit, el forecast y el dataset canónicos son
la única evidencia viva de C5 y una interrupción a media prueba los dañaría (P0.1). Todo se copia
a ``tmp_path`` y las mutaciones ocurren solo sobre esa copia.

``resellar`` recalcula TODOS los digests declarados por los índices y manifiestos de la copia. Sin
él, cualquier mutación fallaría por el sello y jamás se ejercitarían las comprobaciones de
identidad; con él, la prueba llega hasta la comprobación semántica que quiere verificar.
"""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from epiforecast import registry

DISEASE = "obesidad"


def runs_root() -> Path:
    from epiforecast.registry_doctor import _runs_root

    return _runs_root()


def source() -> registry.ArtifactSource:
    return registry.require(DISEASE).artifact_source


def sealed_chain() -> dict[str, str]:
    """Cadena SELLADA del padecimiento, declarada por el release que el registry apunta (C7.2-B).

    Desde el flip a ``runner_release`` el registry ya no lleva los IDs de los runs: los lleva el
    propio bundle, en su ``chain``. Parece circular —hay que leer un release para reconstruirlo—
    pero no lo es: el release ya existe y está versionado; estas pruebas sólo lo re-derivan desde
    los runs para comprobar que sale idéntico. Y evita lo que sí sería un error: escribir los IDs
    de los runs a mano en los tests.
    """
    from epiforecast.runner.release_store import default_releases_root, release_path

    manifest = (
        release_path(default_releases_root(), DISEASE, str(source().release_id))
        / "release_manifest.json"
    )
    return {str(k): str(v) for k, v in leer(manifest)["chain"].items()}


def hay_runs() -> bool:
    """¿Están en local el release declarado Y los runs canónicos que lo originan?

    Ni `runs/` (gitignored) ni el bundle (DVC) viajan en el repo, así que sin ellos se salta. Se
    exigen los DOS a propósito: si sólo se comprobaran los runs, el flip a ``runner_release``
    habría dejado 159 pruebas en `skipped` —verdes de mentira— en vez de en rojo.
    """
    src = source()
    if not src.release_id:
        return False
    from epiforecast.runner.release_store import default_releases_root, release_path

    sede = release_path(default_releases_root(), DISEASE, str(src.release_id))
    if not (sede / "release_manifest.json").exists():
        return False
    cadena, root = sealed_chain(), runs_root()
    return (root / cadena["refit_run_id"] / "refit_summary.json").exists() and (
        root / cadena["forecast_run_id"] / "lineage.json"
    ).exists()


def refit_dir(root: Path) -> Path:
    return root / sealed_chain()["refit_run_id"]


def forecast_dir(root: Path) -> Path:
    return root / sealed_chain()["forecast_run_id"]


def dataset_dir(root: Path) -> Path:
    return root / str(leer(refit_dir(root) / "run_manifest.json")["dataset_id"])


def acceptance_dir(root: Path) -> Path:
    """El run de aceptación NO viaja en `ArtifactSource`: se deriva del resumen sellado."""
    resumen = leer(refit_dir(root) / "refit_summary.json")
    return root / str(resumen["provenance"]["acceptance_run_id"])


def copiar_runs_sellados(destino: Path) -> Path:
    """Dataset + aceptación + refit + forecast copiados tal cual (nunca hard links)."""
    origen = runs_root()
    cadena = sealed_chain()
    refit_id = cadena["refit_run_id"]
    resumen = leer(origen / refit_id / "refit_summary.json")
    ids = [
        refit_id,
        cadena["forecast_run_id"],
        str(leer(origen / refit_id / "run_manifest.json")["dataset_id"]),
        str(resumen["provenance"]["acceptance_run_id"]),
    ]
    for run_id in ids:
        shutil.copytree(origen / run_id, destino / run_id)
    return destino


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def leer(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def escribir(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def editar(path: Path, cambios: dict[str, Any]) -> None:
    """Aplica cambios de primer nivel a un JSON de la copia."""
    data = leer(path)
    data.update(cambios)
    escribir(path, data)


def _mapa(raw: Any) -> dict[str, Any]:
    """Vista tolerante: el fixture nunca debe reventar por un JSON que la prueba rompió a propósito."""
    return raw if isinstance(raw, dict) else {}


def _lista(raw: Any) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _ruta_opcional(resolver: Callable[[Path], Path], root: Path) -> Path:
    """Ruta derivada de un JSON que la prueba pudo haber roto: nunca revienta el fixture."""
    try:
        return resolver(root)
    except (OSError, ValueError, KeyError, TypeError):
        return root / "__no_resuelto__"


def _derivados(root: Path) -> dict[str, str]:
    """Digests que la cadena repite en varios sitios y que el re-sellado debe propagar."""
    salida: dict[str, str] = {}
    acta = _ruta_opcional(lambda r: acceptance_dir(r) / "acceptance.json", root)
    if acta.exists():
        salida["acceptance_digest"] = sha256(acta)
    dataset = _ruta_opcional(lambda r: dataset_dir(r) / "epi_dataset_v2.csv", root)
    if dataset.exists():
        salida["dataset_digest"] = sha256(dataset)
    return salida


def _propagar(root: Path, derivados: dict[str, str]) -> None:
    """Reescribe `acceptance_digest` y `dataset_digest` allí donde la cadena los repite."""
    acc, ds = derivados.get("acceptance_digest"), derivados.get("dataset_digest")
    resumen_path = refit_dir(root) / "refit_summary.json"
    if acc and resumen_path.exists():
        try:
            resumen = leer(resumen_path)
        except ValueError:
            resumen = {}
        if resumen:
            _mapa(resumen.get("provenance"))["acceptance_digest"] = acc
            escribir(resumen_path, resumen)
    for man_path in sorted(root.glob("*/run_manifest.json")):
        try:
            man = leer(man_path)
        except ValueError:
            continue
        digests = man.get("input_digests")
        if not isinstance(digests, dict):
            continue
        if acc and "acceptance_digest" in digests:
            digests["acceptance_digest"] = acc
        if ds and "dataset" in digests:
            digests["dataset"] = ds
        escribir(man_path, man)
    if ds:
        ds_man = _ruta_opcional(lambda r: dataset_dir(r) / "dataset_manifest.json", root)
        if ds_man.exists():
            try:
                man = leer(ds_man)
            except ValueError:
                man = {}
            if man:
                _mapa(man.get("digests"))["dataset"] = ds
                escribir(ds_man, man)
    for path in [
        *root.glob("*/models/*/model_index.json"),
        *root.glob("*/models/*/*.envelope.json"),
    ]:
        try:
            data = leer(path)
        except ValueError:
            continue
        procedencia = data.get("provenance")
        if not isinstance(procedencia, dict):
            continue
        if acc and "acceptance_digest" in procedencia:
            procedencia["acceptance_digest"] = acc
        if ds and "dataset_digest" in procedencia:
            procedencia["dataset_digest"] = ds
        escribir(path, data)
    _propagar_refit_digest(root, resumen_path)


def _propagar_refit_digest(root: Path, resumen_path: Path) -> None:
    """El digest del resumen del refit se deriva de su contenido YA propagado, y viaja al forecast.

    Sin esto, tocar el veredicto de aceptación rompería la cadena en `refit_digest` y ninguna
    mutación semántica del veredicto llegaría nunca a probarse.
    """
    if not resumen_path.exists():
        return
    digest = sha256(resumen_path)
    for path in sorted(root.glob("*/run_manifest.json")):
        try:
            man = leer(path)
        except ValueError:
            continue
        digests = man.get("input_digests")
        if isinstance(digests, dict) and "refit_digest" in digests:
            digests["refit_digest"] = digest
            escribir(path, man)
    for path in sorted(root.glob("*/lineage.json")):
        try:
            lineage = leer(path)
        except ValueError:
            continue
        if isinstance(lineage, dict) and "refit_digest" in lineage:
            lineage["refit_digest"] = digest
            escribir(path, lineage)


def resellar(root: Path) -> None:
    """Recalcula índices y manifiestos para que la prueba mida identidad, no el sello.

    Propaga primero los digests derivados (aceptación y dataset), que la cadena repite en
    manifiestos, resumen, índices y envelopes; sin eso, cualquier mutación semántica del veredicto
    o del dataset moriría en la comprobación de digest y nunca se probaría el contrato real.

    Tolera artefactos ilegibles: un JSON truncado se re-sella igual (su digest se recalcula) para
    que el fallo lo produzca el validador —la frontera de error que se quiere probar— y no el
    propio fixture.
    """
    _propagar(root, _derivados(root))
    for index_path in sorted(root.glob("*/models/*/model_index.json")):
        try:
            index = leer(index_path)
        except ValueError:
            continue  # índice ilegible: lo re-sella la pasada de manifiestos
        for entry in _lista(index.get("models")):
            env_path = index_path.parent / _mapa(entry).get("envelope_path", "__sin_envelope__")
            if not env_path.exists():
                continue
            try:
                envelope = leer(env_path)
            except ValueError:
                entry["envelope_digest"] = sha256(env_path)
                continue
            estado = index_path.parent / _mapa(envelope).get("state_path", "__sin_estado__")
            if estado.exists():
                envelope["state_digest"] = entry["state_digest"] = sha256(estado)
            escribir(env_path, envelope)
            entry["envelope_digest"] = sha256(env_path)
        escribir(index_path, index)
    manifiestos = [*root.glob("*/run_manifest.json"), *root.glob("*/dataset_manifest.json")]
    for man_path in sorted(manifiestos):
        try:
            man = leer(man_path)
        except ValueError:
            continue
        jobs = _mapa(man.get("jobs"))
        grupos = [
            _lista(man.get("artifacts")),
            *(_lista(_mapa(j).get("artifacts")) for j in jobs.values()),
        ]
        for registros in grupos:
            for record in (r for r in registros if isinstance(r, dict) and "path" in r):
                archivo = man_path.parent / record["path"]
                if archivo.exists():
                    record["digest"] = sha256(archivo)
        escribir(man_path, man)


def un_envelope(root: Path, engine: str) -> Path:
    """Ruta del primer envelope (orden estable) del motor indicado dentro de la copia."""
    return sorted((refit_dir(root) / "models" / engine).glob("*.envelope.json"))[0]
