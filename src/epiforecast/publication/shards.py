"""C7.3a — los cuatro puentes en modo candidate: Reports, Tableau, Web y EpiBot/RAG.

Cada puente escribe un shard PROPIO bajo el staging inyectado. Ninguno toca los artefactos vigentes
de los cuatro padecimientos publicados: no se añade nada a ``all_forecast_*.csv``, ni a
``tabla_333_modelos_produccion.xlsx``, ni se recrea ``produccion_<x>.csv`` con el selector legacy.

Todo sale del registry y del release: ni un ``if disease == ...``, ni una lista de padecimientos, ni
identidad recuperada de un nombre de archivo. Los canales que se emiten son los que el registry
DECLARA y para los que existe puente; los declarados sin puente se registran explícitamente en el
manifiesto del shard, para que no desaparezcan en silencio.

Determinista por construcción: JSON canónico, CSV con orden fijo y cero timestamps.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from epiforecast.data.epi_dataset_spec import (
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_SEX,
)
from epiforecast.runner.artifact_identity import require
from epiforecast.runner.release_contract import canonical_json, sha256_bytes

from .compiler import MODE_CANDIDATE, UNCERTAINTY_LABEL, Compilation, check_staging_root

CHANNEL_REPORTS = "reports"
CHANNEL_TABLEAU = "tableau"
CHANNEL_WEB = "web"
CHANNEL_EPIBOT = "epibot"
SHARD_MANIFEST = "shard_manifest.json"
SHARD_SCHEMA = "publication_shard.v1"


@dataclass(frozen=True, slots=True)
class EmittedShards:
    """Qué se escribió, dónde y con qué digest; más los canales declarados sin puente."""

    root: Path
    files: dict[str, str]
    channels: tuple[str, ...]
    channels_without_bridge: tuple[str, ...]


def _write(root: Path, relativo: str, datos: bytes, registro: dict[str, str]) -> None:
    destino = root / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(datos)
    registro[relativo] = sha256_bytes(datos)


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    """CSV en memoria, con orden y columnas ya fijados por el compilador."""
    texto: str = frame.to_csv(index=False)
    return texto.encode("utf-8")


def _facts(c: Compilation) -> dict[str, Any]:
    """Los hechos del release que TODO puente repite igual (nunca recalculados a mano)."""
    conteos = c.verified.counts
    return {
        "release_id": c.release_id,
        "disease_id": c.disease_id,
        "display_name": c.disease.display_name,
        "cie_codes": list(c.disease.cie_codes),
        "lifecycle": c.disease.lifecycle,
        "origin": list(c.verified.origin),
        "horizon_weeks": c.verified.horizon,
        "models": conteos["models"],
        "base_series": conteos["base"],
        "derived_products": conteos["derived"],
        "products": conteos["products"],
        "rows": int(len(c.rows)),
        "engines": dict(sorted(c.verified.engines.items())),
        "interval_method": c.verified.interval_method,
        "uncertainty_available": c.verified.uncertainty_available,
        "uncertainty_label": UNCERTAINTY_LABEL,
    }


def _reports(c: Compilation, root: Path, reg: dict[str, str]) -> None:
    """Shard separado de Reports: los 111 productos, con lineage visible y point-only."""
    hechos = _facts(c)
    _write(root, f"{CHANNEL_REPORTS}/forecast_products.csv", _csv_bytes(c.rows), reg)
    lineas = [
        f"# Pronóstico — {hechos['display_name']} ({', '.join(hechos['cie_codes'])})",
        "",
        f"- Release: `{hechos['release_id']}`",
        f"- Lineage: forecast `{c.verified.chain['forecast_run_id']}` · refit "
        f"`{c.verified.chain['refit_run_id']}` · dataset `{c.verified.chain['dataset_id']}`",
        f"- Origen {hechos['origin'][0]}-W{hechos['origin'][1]:02d} → horizonte "
        f"{hechos['horizon_weeks']} semanas",
        f"- {hechos['models']} modelos finales sobre {hechos['base_series']} series base; "
        f"{hechos['derived_products']} productos derivados por suma → {hechos['products']} "
        f"productos, {hechos['rows']} filas",
        "",
        "## Motores del portafolio",
        "",
        "| motor | series base |",
        "| --- | ---: |",
        *[f"| `{m}` | {n} |" for m, n in hechos["engines"].items()],
        "",
        "## Incertidumbre",
        "",
        f"- **{UNCERTAINTY_LABEL}.** `interval_method={hechos['interval_method']}`; los límites "
        "viajan nulos y no deben dibujarse como cero.",
        f"- Los {hechos['derived_products']} productos derivados se atribuyen al portafolio, no a "
        "un motor concreto: son la suma de las series base.",
        "",
        f"**Lifecycle `{hechos['lifecycle']}`**: shard de compilación, no publicación.",
    ]
    _write(root, f"{CHANNEL_REPORTS}/report.md", ("\n".join(lineas) + "\n").encode("utf-8"), reg)


def _tableau(c: Compilation, root: Path, reg: dict[str, str]) -> None:
    """Shard de Tableau con su schema DOCUMENTADO. No toca el workbook canónico."""
    _write(root, f"{CHANNEL_TABLEAU}/forecast_shard.csv", _csv_bytes(c.rows), reg)
    schema = {
        "schema": SHARD_SCHEMA,
        "channel": CHANNEL_TABLEAU,
        **_facts(c),
        "columns": [
            {"name": columna, "dtype": str(c.rows[columna].dtype)} for columna in c.rows.columns
        ],
        "keys": [COL_GEO_LEVEL, COL_GEO_ID, COL_SEX, COL_EPI_YEAR, COL_EPI_WEEK],
        "notes": [
            "`derived=false` son las series base modeladas; `derived=true` son sumas del portafolio.",
            "`yhat_lower`/`yhat_upper` viajan nulos a propósito: el release es point-only.",
        ],
    }
    _write(root, f"{CHANNEL_TABLEAU}/schema.json", canonical_json(schema), reg)


def _web(c: Compilation, root: Path, reg: dict[str, str]) -> None:
    """Manifest generado: filtros y series salen de los DATOS y la metadata del registry."""
    from epiforecast.runner.release_reproduce import horizon_periods

    filas = c.rows
    periodos = horizon_periods(c.verified.origin, c.verified.horizon)
    manifest = {
        "schema": SHARD_SCHEMA,
        "channel": CHANNEL_WEB,
        **_facts(c),
        "slug": c.disease.slug,
        "web": {str(k): v for k, v in sorted(dict(c.disease.web).items())},
        "gallery_enabled": bool(c.disease.gallery_enabled),
        "filters": {
            "geography_levels": sorted(set(filas[COL_GEO_LEVEL])),
            "geography_ids": sorted(set(filas[COL_GEO_ID])),
            "sexes": sorted(set(filas[COL_SEX])),
            "engines": sorted(set(filas.loc[~filas["derived"], "engine"])),
            # Del calendario MMWR del release, no de la posición de una fila: con el orden
            # geográfico coincidía por casualidad, y dejaría de coincidir en cuanto dos series
            # tuvieran horizontes distintos.
            "periods": [list(periodos[0]), list(periodos[-1])],
        },
    }
    _write(root, f"{CHANNEL_WEB}/manifest.json", canonical_json(manifest), reg)
    _write(root, f"{CHANNEL_WEB}/series.csv", _csv_bytes(filas), reg)


def _epibot(c: Compilation, root: Path, reg: dict[str, str]) -> None:
    """Sección de knowledge + corpus RAG, generados desde el release.

    El corpus dice explícitamente que NO hay intervalos y distingue los modelos finales de los
    productos derivados: confundirlos es el error que un RAG repetiría para siempre.
    """
    hechos = _facts(c)
    _write(root, f"{CHANNEL_EPIBOT}/knowledge.json", canonical_json({"release": hechos}), reg)
    motores = ", ".join(f"{m} ({n} series)" for m, n in hechos["engines"].items())
    corpus = [
        f"# {hechos['display_name']} — release {hechos['release_id']}",
        "",
        f"{hechos['display_name']} ({', '.join(hechos['cie_codes'])}) tiene "
        f"{hechos['models']} modelos finales, uno por serie base (estado × sexo). "
        f"De esas {hechos['base_series']} series base se derivan por suma "
        f"{hechos['derived_products']} productos agregados, hasta un total de "
        f"{hechos['products']} productos. Los modelos y los productos NO son lo mismo: "
        f"hay {hechos['models']} modelos y {hechos['products']} productos.",
        "",
        f"El pronóstico cubre {hechos['horizon_weeks']} semanas desde "
        f"{hechos['origin'][0]}-W{hechos['origin'][1]:02d}.",
        "",
        f"Motores del portafolio: {motores}. Los productos derivados se atribuyen al portafolio, "
        "no a un motor concreto.",
        "",
        f"IMPORTANTE — incertidumbre: {UNCERTAINTY_LABEL}. "
        f"interval_method={hechos['interval_method']} y uncertainty_available="
        f"{str(hechos['uncertainty_available']).lower()}: este release NO tiene intervalos de "
        "confianza ni bandas de incertidumbre. No deben describirse como si existieran.",
        "",
        f"Estado de publicación: lifecycle={hechos['lifecycle']}.",
    ]
    _write(
        root,
        f"{CHANNEL_EPIBOT}/corpus/{c.disease_id}.md",
        ("\n".join(corpus) + "\n").encode("utf-8"),
        reg,
    )


_BRIDGES: Mapping[str, Any] = {
    CHANNEL_REPORTS: _reports,
    CHANNEL_TABLEAU: _tableau,
    CHANNEL_WEB: _web,
    CHANNEL_EPIBOT: _epibot,
}


def emit_shards(
    c: Compilation, output_root: Path, *, repo_root_path: Path | None = None
) -> EmittedShards:
    """Escribe los shards de los canales DECLARADOS con puente, bajo ``<root>/<disease>/<release>``.

    El destino se valida AQUÍ. Tener el guard en el compilador y confiar en que el llamador lo
    invoque era una comprobación que no comprobaba: ``emit_shards`` aceptaba cualquier ruta, incluida
    una pública. En modo ``candidate`` el destino no puede caer bajo una ruta pública del repo.
    """
    if c.mode == MODE_CANDIDATE:
        check_staging_root(output_root, repo_root_path)
    declarados = tuple(sorted(set(c.disease.channels)))
    con_puente = tuple(canal for canal in declarados if canal in _BRIDGES)
    require(con_puente, f"{c.disease_id}: ningún canal declarado tiene puente de compilación")

    root = output_root / c.disease_id / c.release_id
    registro: dict[str, str] = {}
    for canal in con_puente:
        _BRIDGES[canal](c, root, registro)

    manifest = {
        "schema": SHARD_SCHEMA,
        "mode": c.mode,
        **_facts(c),
        "channels_emitted": list(con_puente),
        # Se declaran EXPLÍCITAMENTE: un canal sin puente no puede desaparecer sin dejar rastro.
        "channels_without_bridge": [ca for ca in declarados if ca not in _BRIDGES],
        "files": dict(sorted(registro.items())),
    }
    (root / SHARD_MANIFEST).write_bytes(canonical_json(manifest))
    return EmittedShards(
        root=root,
        files=dict(sorted(registro.items())),
        channels=con_puente,
        channels_without_bridge=tuple(ca for ca in declarados if ca not in _BRIDGES),
    )
