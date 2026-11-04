"""C7.7 — Activa la publicación de un release del runner y compila sus shards PÚBLICOS.

Es el paso que el plan C7 dejó descrito y sin herramienta. Hace tres cosas, en este orden y
fallando cerrado en cualquiera:

1. exige que el registry ya declare ``lifecycle=published`` para el padecimiento (el flip es un
   commit aparte y revisable; este comando no lo hace por nadie);
2. escribe o comprueba el puntero ACTIVO en ``config/publication/<id>/public_release_pointer.json``,
   derivado del registry y validado contra el release declarado;
3. compila el release en modo ``public`` dos veces bajo raíces distintas, exige que los dos árboles
   sean idénticos byte a byte y deja el shard listo para instalarse en el sitio.

No usa red, no toca DVC ni el frontend. La instalación en el sitio la hace
``epibot/scripts/install_publication.mjs`` del dashboard, que vuelve a verificar el shard.

    python -m scripts.publication_activate obesidad --out runs/publication --write-pointer
    python -m scripts.publication_activate obesidad --out runs/publication --check
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from epiforecast import registry
from epiforecast.publication.compiler import MODE_PUBLIC, compile_release
from epiforecast.publication.pointer import (
    LIFECYCLE_PUBLISHED,
    check_activation,
    declared_pointer_path,
    pointer_for,
    read_pointer,
    write_active_pointer,
)
from epiforecast.publication.shards import emit_shards
from epiforecast.publication.status import load_declared_status
from epiforecast.runner.artifact_identity import ArtifactValidationError, equal, require
from epiforecast.runner.release_store import diff_trees

ACTIVATION_SCHEMA = "publication_activation.v1"
_REPO = Path(__file__).resolve().parents[1]
RELEASES_ROOT = _REPO / "artifacts" / "releases"


def _check_output(out: Path) -> Path:
    """El shard público se compila en un directorio ignorado por git (runs/), nunca suelto."""
    destino = out.resolve()
    runs = (_REPO / "runs").resolve()
    require(
        destino == runs or runs in destino.parents,
        f"activación: --out tiene que vivir bajo runs/ (gitignored), no en {out}",
    )
    return destino


def activate(
    disease_id: str, *, out: Path, write_pointer: bool, releases_root: Path = RELEASES_ROOT
) -> dict[str, Any]:
    disease = registry.require(disease_id)
    equal(f"{disease.id}: lifecycle", disease.lifecycle, LIFECYCLE_PUBLISHED)
    estado = load_declared_status(disease.id)
    require(estado.publishable, f"{disease.id}: veredicto {estado.verdict}; no se publica")

    esperado = pointer_for(disease, active=True)
    ruta_puntero = declared_pointer_path(disease.id)
    if write_pointer:
        write_active_pointer(esperado, disease)
    require(ruta_puntero.is_file(), f"{disease.id}: falta el puntero activo {ruta_puntero}")
    puntero = read_pointer(ruta_puntero)
    equal(f"{disease.id}: puntero declarado", puntero, esperado)
    check_activation(puntero, disease)

    destino = _check_output(out)
    arboles: list[Path] = []
    for nombre in ("compile_a", "compile_b"):
        raiz = destino / nombre
        if raiz.exists():
            shutil.rmtree(raiz)
        compilacion = compile_release(
            disease_id=disease.id,
            mode=MODE_PUBLIC,
            releases_root=releases_root,
            pointer_release_id=puntero.release_id,
            status=estado,
        )
        arboles.append(emit_shards(compilacion, raiz).root)
    diferencias = diff_trees(arboles[0], arboles[1])
    require(not diferencias, f"activación: dos compilaciones difieren en {diferencias[:5]}")

    manifiesto = json.loads((arboles[0] / "shard_manifest.json").read_text("utf-8"))
    equal(f"{disease.id}: modo del shard", manifiesto.get("mode"), MODE_PUBLIC)
    return {
        "schema": ACTIVATION_SCHEMA,
        "disease_id": disease.id,
        "release_id": puntero.release_id,
        "channels": list(puntero.channels),
        "pointer_path": ruta_puntero.relative_to(_REPO).as_posix(),
        "pointer_digest": puntero.digest(),
        "verdict": estado.verdict,
        "label": compilacion.label,
        "observation_dataset_id": estado.status.observation_dataset_id,
        "shard_root": str(arboles[0]),
        "channels_emitted": manifiesto.get("channels_emitted"),
        "files": manifiesto.get("files"),
        "reproducible": {"compilations": len(arboles), "tree_differences": 0},
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    ap.add_argument("disease_id")
    ap.add_argument("--out", type=Path, required=True, help="raíz bajo runs/ para los shards")
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--write-pointer", action="store_true", help="escribe el puntero activo")
    modo.add_argument("--check", action="store_true", help="sólo comprueba el puntero existente")
    args = ap.parse_args(argv)
    try:
        resumen = activate(args.disease_id, out=args.out, write_pointer=args.write_pointer)
    except (ArtifactValidationError, KeyError, ValueError) as exc:
        print(f"ERROR: activación de {args.disease_id}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(resumen, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
