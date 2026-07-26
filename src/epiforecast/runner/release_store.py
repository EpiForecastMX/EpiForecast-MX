"""C7.2-B/R19.5 — sede final de los release bundles y promoción ATÓMICA desde un temporal.

```text
<releases_root>/<disease_id>/<release_id>/
```

``releases_root`` se INYECTA siempre. Nada aquí mira el cwd, ``runs/``, el home ni una ruta absoluta
del equipo: la sede es un parámetro, y por eso el mismo código sirve para la ruta real del repo y
para un temporal de prueba sin una sola excepción.

Promover es mover un bundle **ya verificado** a su sede con un rename atómico: o está entero o no
está. Nunca se escribe directamente en el destino final, porque un fallo a media copia dejaría un
release incompleto con aspecto de release. Y es idempotente: promover dos veces el mismo contenido
lo acepta; promover contenido distinto bajo el mismo ``release_id`` se rechaza, porque un release es
inmutable por definición.
"""

from __future__ import annotations

from dataclasses import dataclass
import filecmp
from pathlib import Path
import shutil
import tempfile

from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    require,
    text_of,
)

ARTIFACTS_DIRNAME = "artifacts"
RELEASES_DIRNAME = "releases"


def default_releases_root() -> Path:
    """Sede por defecto del repo. Sólo la usa el CLI/doctor cuando nadie inyecta una.

    ``parents[3]`` es la raíz del repo desde ``src/epiforecast/runner/``: este módulo está un nivel
    más hondo que ``registry_doctor``, que usa ``parents[2]``.
    """
    return Path(__file__).resolve().parents[3] / ARTIFACTS_DIRNAME / RELEASES_DIRNAME


def _segment(raw: object, label: str) -> str:
    """Un segmento de ruta que viene de identidad: sin separadores, sin ``..``, sin sorpresas."""
    valor = text_of(raw, label)
    require(
        "/" not in valor and "\\" not in valor and valor not in (".", ".."),
        f"{label}: {valor!r} no es un nombre de directorio válido",
    )
    return valor


def release_path(releases_root: Path, disease_id: str, release_id: str) -> Path:
    """``<releases_root>/<disease_id>/<release_id>``, derivada y nunca escrita a mano."""
    return (
        releases_root
        / _segment(disease_id, "sede: disease_id")
        / _segment(release_id, "sede: release_id")
    )


def diff_trees(izq: Path, der: Path) -> list[str]:
    """Rutas que sobran, faltan o difieren BYTE a byte entre dos árboles."""
    izquierda = {p.relative_to(izq).as_posix() for p in izq.rglob("*") if p.is_file()}
    derecha = {p.relative_to(der).as_posix() for p in der.rglob("*") if p.is_file()}
    distintos = [
        ruta
        for ruta in sorted(izquierda & derecha)
        if not filecmp.cmp(izq / ruta, der / ruta, shallow=False)
    ]
    return sorted(izquierda ^ derecha) + distintos


@dataclass(frozen=True, slots=True)
class PromotedRelease:
    """Dónde quedó el release y si ya estaba ahí con el mismo contenido."""

    disease_id: str
    release_id: str
    path: Path
    reused: bool


def promote_release(bundle_dir: Path, *, releases_root: Path, disease_id: str) -> PromotedRelease:
    """Verifica el bundle y lo promueve a su sede. Devuelve dónde quedó.

    El ``release_id`` NO se recibe: sale de verificar el bundle, para que la sede no pueda quedar
    nombrada por algo distinto de lo que el propio artefacto declara.
    """
    from epiforecast.runner.release_loader import verify_bundle

    verificado = verify_bundle(bundle_dir)
    equal("promoción: disease_id", verificado.disease_id, disease_id)
    destino = release_path(releases_root, disease_id, verificado.release_id)

    if destino.exists():
        diferencias = diff_trees(bundle_dir, destino)
        require(
            not diferencias,
            f"release {verificado.release_id}: ya existe en la sede con contenido distinto "
            f"({len(diferencias)} rutas, p.ej. {diferencias[:3]})",
        )
        verify_bundle(destino)  # lo que ya estaba tiene que seguir siendo válido
        return PromotedRelease(disease_id, verificado.release_id, destino, reused=True)

    destino.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=destino.parent, prefix=".promoting-"))
    try:
        # copytree a un hermano del destino: el rename final es dentro del MISMO sistema de
        # archivos, así que es atómico. Copiar directo al destino dejaría releases a medias.
        shutil.rmtree(staging)
        shutil.copytree(bundle_dir, staging)
        verify_bundle(staging)
        staging.replace(destino)
    except IO_ERRORS as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise ArtifactValidationError(
            f"release {verificado.release_id}: promoción fallida ({exc})"
        ) from exc
    verify_bundle(destino)
    return PromotedRelease(disease_id, verificado.release_id, destino, reused=False)
