"""F1/C1 — geografía y exposición para EpiDatasetV2 (join estricto 1:1, digests).

- Catálogo geográfico TRACKEADO (``config/geografia/entidades_mx.csv``): CVE_ENT 01–32, nombre
  canónico, nombre INEGI y aliases. Resolución de nombres **exacta o por alias** (NFKD-fold), nunca
  fuzzy ni por orden.
- Snapshot de exposición ``inegi_cpv2020_static`` (``data/utils/inegi.csv``): join por nombre INEGI
  → CVE_ENT, verificación ``Hombres + Mujeres = Total`` en 32/32, digest SHA-256 reproducible.

Sin lógica de reconciliación. Puro loader + validación; ``EpiDatasetV2`` lo EXIGE.
"""

from __future__ import annotations

from datetime import date
import hashlib
from pathlib import Path
from typing import Any, cast
import unicodedata

from omegaconf import OmegaConf
import pandas as pd

from epiforecast.data.epi_dataset_spec import ExposureSnapshot, GeoEntity

_ROOT = Path(__file__).resolve().parents[3]


class GeoExposureError(ValueError):
    """Catálogo geográfico o snapshot de exposición inválidos (duplicados, join incompleto…)."""


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().strip().lower()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exposicion_config_path() -> Path:
    return _ROOT / "config" / "exposicion.yaml"


class GeoCatalog:
    """Catálogo geográfico con resolución estricta de nombres a CVE_ENT."""

    def __init__(self, entities: list[GeoEntity]) -> None:
        self.entities = entities
        self._by_cve: dict[str, GeoEntity] = {}
        self._by_folded: dict[str, str] = {}  # nombre/alias folded -> cve_ent
        for e in entities:
            if e.cve_ent in self._by_cve:
                raise GeoExposureError(f"CVE_ENT duplicado: {e.cve_ent}")
            self._by_cve[e.cve_ent] = e
            for token in (e.nombre_canonico, e.nombre_inegi, *e.aliases):
                f = _fold(token)
                if not f:
                    continue
                if f in self._by_folded and self._by_folded[f] != e.cve_ent:
                    raise GeoExposureError(
                        f"alias '{token}' colisiona: {e.cve_ent} vs {self._by_folded[f]}"
                    )
                self._by_folded[f] = e.cve_ent
        if len(self._by_cve) != 32:
            raise GeoExposureError(
                f"el catálogo debe tener 32 entidades, tiene {len(self._by_cve)}"
            )

    def resolve(self, name: str) -> str:
        """Nombre (canónico/INEGI/alias) → CVE_ENT. Estricto: desconocido levanta."""
        cve = self._by_folded.get(_fold(name))
        if cve is None:
            raise GeoExposureError(f"entidad no reconocida en el catálogo: {name!r}")
        return cve

    def entity(self, cve_ent: str) -> GeoEntity:
        e = self._by_cve.get(cve_ent)
        if e is None:
            raise GeoExposureError(f"CVE_ENT desconocido: {cve_ent}")
        return e

    def cve_ents(self) -> list[str]:
        return sorted(self._by_cve)


def _load_yaml(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", OmegaConf.to_container(OmegaConf.load(path), resolve=True))


def load_geo_catalog(path: str | Path | None = None) -> GeoCatalog:
    """Carga el catálogo geográfico trackeado."""
    if path is None:
        path = _ROOT / str(_load_yaml(_exposicion_config_path())["catalogo_geografico"])
    df = pd.read_csv(path, dtype=str).fillna("")
    entities = [
        GeoEntity(
            cve_ent=str(r["cve_ent"]).zfill(2),
            nombre_canonico=str(r["nombre_canonico"]).strip(),
            nombre_inegi=str(r["nombre_inegi"]).strip(),
            aliases=tuple(a.strip() for a in str(r["aliases"]).split("|") if a.strip()),
        )
        for _, r in df.iterrows()
    ]
    return GeoCatalog(entities)


def load_exposure_snapshot(
    source_id: str, catalog: GeoCatalog, config_path: str | Path | None = None
) -> ExposureSnapshot:
    """Carga ``source_id`` (p.ej. ``inegi_cpv2020_static``), join estricto por nombre INEGI.

    Verifica: 32/32 entidades mapeadas 1:1, ``Hombres+Mujeres=Total`` por fila, exposiciones
    positivas, y (si se declara) el digest esperado del archivo.
    """
    fuentes = _load_yaml(Path(config_path or _exposicion_config_path()))["fuentes"]
    if source_id not in fuentes:
        raise GeoExposureError(f"fuente de exposición desconocida: {source_id}")
    spec = fuentes[source_id]
    path = _ROOT / str(spec["path"])
    digest = _sha256(path)
    expected = spec.get("sha256")
    if expected and digest != expected:
        raise GeoExposureError(
            f"digest de {source_id} no coincide: {digest} != {expected} (esperado)"
        )

    ent_col = str(spec["entidad_column"])
    cols = [str(c) for c in spec["columns"]]
    df = pd.read_csv(path)
    by_cve: dict[str, dict[str, int]] = {}
    for _, r in df.iterrows():
        cve = catalog.resolve(str(r[ent_col]))
        if cve in by_cve:
            raise GeoExposureError(f"exposición duplicada para CVE_ENT {cve}")
        vals = {c: int(r[c]) for c in cols}
        if not all(v > 0 for v in vals.values()):
            raise GeoExposureError(f"exposición no positiva en {cve}: {vals}")
        if {"Hombres", "Mujeres", "Total"} <= vals.keys() and (
            vals["Hombres"] + vals["Mujeres"] != vals["Total"]
        ):
            raise GeoExposureError(f"Hombres+Mujeres != Total en {cve}: {vals}")
        by_cve[cve] = vals
    if len(by_cve) != 32:
        raise GeoExposureError(f"la exposición debe cubrir 32 entidades, cubre {len(by_cve)}")

    return ExposureSnapshot(
        source_id=source_id,
        reference=str(spec["reference"]),
        cutoff=date.fromisoformat(str(spec["cutoff"])),
        columns=tuple(cols),
        digest=digest,
        by_cve_ent=by_cve,
    )
