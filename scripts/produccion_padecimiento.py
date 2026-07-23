"""Selector productivo genérico por padecimiento (EPIC 3 + gates Fase 1).

Aplica la regla canónica (``epiforecast.selection.select_engine``: sMAPE→MASE→RMSE + banda
5% + orden estable) sobre los motores ELEGIBLES del padecimiento, usando las métricas CV por
serie de cada ``{Motor}_{Padecimiento}_completo.csv``.

**Gate COMPLETO (lifecycle + ownership + slug) en ``resolve_destination``**, fail-closed:

- Un padecimiento NO ``published`` no puede recrear una selección canónica: aborta sin escribir,
  salvo ``--allow-preliminary``, que emite un CSV **PRELIMINAR** bajo ``_preliminar_NO_GO/`` con
  criterio ``insample_cv_PRELIMINAR_NO_GO`` (nunca la etiqueta de la política: este selector usa
  métricas CV *in-sample*, no un rolling-origin OOS real).
- Un padecimiento ``published`` es dominio de su selector DEDICADO (neuro: ``reselect_motor_2026``;
  Dengue: ``produccion_dengue``). El genérico NO reproduce ``legacy_neuro_2026``/``legacy_dengue_2026``
  (esquema distinto — ~16 vs 30 columnas, rompería ``build_web_knowledge``): rechaza toda escritura
  canónica salvo que exista un **adapter callable** registrado en ``_CANONICAL_ADAPTERS`` (hoy vacío;
  registrar exige una FUNCIÓN real que produzca el esquema, no una string), y el write canónico
  **delega** en ese adapter. Reserva además ``_DEDICATED_ARTIFACTS``.
- ``--allow-preliminary`` sobre un ``published`` es contradicción → rechazado en el resolver.
- El ``slug`` se valida (formato + containment) antes de construir rutas: ningún ``../`` escapa.

La escritura es **atómica**: tmp en el MISMO directorio → validación → ``os.replace``, con lock
(``fcntl``) y limpieza del tmp ante fallo.

Uso: .venv/bin/python -m scripts.produccion_padecimiento --disease Obesidad [--allow-preliminary]
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import re

import pandas as pd

from epiforecast import registry
from epiforecast.selection import Candidate, select_engine
from epiforecast.utils.config import logger

ROOT = Path(__file__).resolve().parent.parent
# Etiqueta de DISPLAY para ``motor_productivo`` (convención del proyecto: DeepAR/NBGLM).
# NO sirve para construir nombres de archivo — ver ``_engine_file_prefix``.
_ENGINE_CAP = {
    "prophet": "Prophet",
    "deepar": "DeepAR",
    "ensemble": "Ensemble",
    "stacking": "Stacking",
    "nbglm": "NBGLM",
}
_SEXO_MAP = {
    "incrementos_hombres": "hombres",
    "incrementos_mujeres": "mujeres",
    "incrementos_total": "general",
}


def _engine_file_prefix(engine: str) -> str:
    """Prefijo REAL en disco del CSV de métricas (case-sensitive en Linux/CI).

    Los archivos son ``Prophet_``/``Deepar_``/``Ensemble_``/``Stacking_``/``Nbglm_`` (title-case),
    NO el display ``_ENGINE_CAP`` (``DeepAR``/``NBGLM``): usar ese mapa para el nombre de archivo
    encuentra el CSV en macOS (FS case-insensitive) y FALLA en Linux.
    """
    return engine.capitalize()


# ── Lifecycle gate (contrato Fase 1) ──
_PRELIMINAR_DIRNAME = "_preliminar_NO_GO"
_PRELIMINAR_CRITERIO = "insample_cv_PRELIMINAR_NO_GO"

# ── Ownership / policy gate (contrato Fase 1, P0) ──
# Adapter = callable que produce el DataFrame canónico con el ESQUEMA EXACTO de esa política.
# ``policy -> adapter``. VACÍO: no hay adapter validado (legacy_neuro_2026, legacy_dengue_2026,
# rolling_cv_v1 OOS real). Registrar exige una FUNCIÓN real, no una string: así, añadir una cadena
# NO rehabilita el writer genérico (que produce otro esquema). El write canónico DELEGA en el adapter.
CanonicalAdapter = Callable[["registry.Disease", Path], pd.DataFrame]
_CANONICAL_ADAPTERS: dict[str, CanonicalAdapter] = {}

# Artefactos canónicos con dueño DEDICADO — el genérico nunca los escribe, ni con adapter.
_DEDICATED_ARTIFACTS: frozenset[str] = frozenset({"produccion_dengue.csv"})

# Slug seguro: minúsculas/dígitos/guion-bajo, sin puntos ni separadores (impide traversal ../).
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")


class SlugError(ValueError):
    """slug con formato inseguro o que escaparía del directorio destino."""


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.fullmatch(slug):
        raise SlugError(f"slug inseguro: {slug!r} (esperado ^[a-z0-9][a-z0-9_]*$)")


def _safe_child(parent: Path, filename: str) -> Path:
    """``parent/filename`` garantizando CONTAINMENT (el hijo queda dentro de parent).

    Valida sobre las rutas resueltas pero devuelve la ruta SIN resolver (preserva el estilo
    del caller para comparaciones/logs). Backstop de ``_validate_slug`` ante cualquier ``../``.
    """
    child = parent / filename
    child_r, parent_r = child.resolve(), parent.resolve()
    if parent_r != child_r.parent and parent_r not in child_r.parents:
        raise SlugError(f"ruta '{child}' escaparía de '{parent_r}'")
    return child


@contextmanager
def _file_lock(lock_path: Path) -> Iterator[None]:
    """Lock exclusivo (``fcntl.flock``) sobre un archivo; se libera y limpia al salir."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        with suppress(FileNotFoundError):
            lock_path.unlink()


def _atomic_write_csv(df: pd.DataFrame, dest: Path) -> None:
    """Escritura atómica: tmp en el MISMO dir → validación → ``os.replace``.

    Serializa con lock; limpia el tmp ante fallo (el destino nunca queda a medias). ``os.replace``
    es atómico en el mismo filesystem, así que un abort deja el destino previo intacto byte-a-byte.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    lock = dest.parent / f".{dest.name}.lock"
    tmp = dest.parent / f".{dest.name}.tmp.{os.getpid()}"
    with _file_lock(lock):
        try:
            df.to_csv(tmp, index=False, encoding="utf-8")
            check = pd.read_csv(tmp)
            if list(check.columns) != list(df.columns) or len(check) != len(df):
                raise OSError(f"validación post-escritura falló para {dest.name}")
            tmp.replace(dest)  # atómico (os.replace) en el mismo filesystem
        finally:
            with suppress(FileNotFoundError):
                tmp.unlink()


@dataclass(frozen=True)
class Destination:
    """Destino resuelto del CSV de selección + etiqueta de criterio honesta."""

    path: Path
    criterio: str
    canonical: bool


def resolve_destination(
    d: registry.Disease, root: Path, *, allow_preliminary: bool
) -> Destination | None:
    """Gate COMPLETO (lifecycle + ownership + slug), fail-closed. ``None`` = no escribir.

    Valida el slug (formato + containment) SIEMPRE, antes de construir rutas, de modo que un
    caller que salte ``main`` no pueda evadir ningún control.

    - ``published`` + ``allow_preliminary``: ``None`` (contradicción; un published no admite preliminar).
    - ``published`` con adapter en ``_CANONICAL_ADAPTERS`` y artefacto NO reservado: ruta CANÓNICA,
      criterio = ``selection_policy`` (el write DELEGA en el adapter).
    - ``published`` sin adapter, o artefacto en ``_DEDICATED_ARTIFACTS``: ``None``.
    - no ``published`` sin ``allow_preliminary``: ``None``.
    - no ``published`` con ``allow_preliminary``: ruta PRELIMINAR en ``_preliminar_NO_GO/``,
      criterio ``insample_cv_PRELIMINAR_NO_GO``.
    """
    _validate_slug(d.slug)
    proddetails = root / "reports" / "ProdDetails"

    if d.lifecycle == "published":
        if allow_preliminary:
            return None  # contradicción: un published no admite preliminar
        if d.selection_policy not in _CANONICAL_ADAPTERS:
            return None
        canonical = _safe_child(proddetails, f"produccion_{d.slug}.csv")
        if canonical.name in _DEDICATED_ARTIFACTS:
            return None
        return Destination(canonical, d.selection_policy, True)

    if not allow_preliminary:
        return None
    prelim = _safe_child(proddetails / _PRELIMINAR_DIRNAME, f"produccion_{d.slug}_PRELIMINAR.csv")
    return Destination(prelim, _PRELIMINAR_CRITERIO, False)


def _load_engine_metrics(artifact_key: str, engine: str) -> pd.DataFrame | None:
    prefix = _engine_file_prefix(engine)
    path = ROOT / "models" / engine / artifact_key / f"{prefix}_{artifact_key}_completo.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["entidad"] = df["Entidad"].fillna("Nacional").astype(str) if "Entidad" in df else "Nacional"
    df["sexo"] = df["sexo"].map(lambda s: _SEXO_MAP.get(str(s), str(s)))
    out = df[["entidad", "sexo", "smape", "mase", "rmse"]].copy()
    out["motor"] = engine
    return out


def _build_preliminary_selection(d: registry.Disease, criterio: str) -> pd.DataFrame | None:
    """Selección PRELIMINAR in-sample (sMAPE→MASE→RMSE) por serie. ``None`` si nada entrenado."""
    metricas: dict[str, pd.DataFrame] = {}
    for engine in d.eligible_engines:
        m = _load_engine_metrics(d.artifact_key, engine)
        if m is not None:
            metricas[engine] = m
    if not metricas:
        return None
    faltantes = [e for e in d.eligible_engines if e not in metricas]
    if faltantes:
        logger.warning("Motores elegibles SIN entrenar (omitidos): {}", faltantes)

    todas = pd.concat(metricas.values(), ignore_index=True)
    series = todas[["entidad", "sexo"]].drop_duplicates().itertuples(index=False)
    rows: list[dict[str, object]] = []
    for entidad, sexo in series:
        cands: list[Candidate] = []
        detalle: dict[str, float | None] = {}
        for engine, mdf in metricas.items():
            sel = mdf[(mdf.entidad == entidad) & (mdf.sexo == sexo)]
            if sel.empty:
                continue
            r = sel.iloc[0]
            cands.append(
                Candidate(engine, smape=_num(r.smape), mase=_num(r.mase), rmse=_num(r.rmse))
            )
            detalle[f"smape_{engine}"] = _num(r.smape)
            detalle[f"mase_{engine}"] = _num(r.mase)
        ganador = select_engine(cands)
        rows.append(
            {
                "padecimiento": d.data_name,
                "entidad": entidad,
                "sexo": sexo,
                "motor_productivo": _ENGINE_CAP.get(ganador, ganador) if ganador else None,
                "criterio_seleccion": criterio,
                "motores_evaluados": ",".join(sorted(metricas)),
                **detalle,
            }
        )
    return pd.DataFrame(rows).sort_values(["entidad", "sexo"]).reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disease", required=True)
    ap.add_argument(
        "--allow-preliminary",
        action="store_true",
        help=(
            "Permite emitir un CSV PRELIMINAR (bajo _preliminar_NO_GO/) para un padecimiento no "
            "publicado. Sin este flag, un padecimiento configured/trained aborta sin escribir."
        ),
    )
    args = ap.parse_args(argv)

    d = registry.require(args.disease)
    logger.info(
        "Selector {} | lifecycle={} | política={} | motores elegibles={}",
        d.data_name,
        d.lifecycle,
        d.selection_policy,
        list(d.eligible_engines),
    )

    if args.allow_preliminary and d.lifecycle == "published":
        logger.error(
            "--allow-preliminary no aplica a un padecimiento published ('{}'): su selección "
            "canónica es dominio del selector dedicado, no un preliminar.",
            d.data_name,
        )
        return 2

    try:
        dest = resolve_destination(d, ROOT, allow_preliminary=args.allow_preliminary)
    except SlugError as e:
        logger.error("GATE slug: {}", e)
        return 2

    if dest is None:
        if d.lifecycle == "published":
            logger.error(
                "GATE ownership: '{}' (published, política '{}') es dominio del selector DEDICADO "
                "(reselect_motor_2026.py / produccion_dengue.py). El genérico no reproduce esa "
                "política ni escribe su artefacto canónico produccion_{}.csv.",
                d.data_name,
                d.selection_policy,
                d.slug,
            )
        else:
            logger.error(
                "GATE lifecycle: '{}' está en lifecycle={} (no 'published'). Usa --allow-preliminary "
                "para emitir un CSV PRELIMINAR en reports/ProdDetails/{}/.",
                d.data_name,
                d.lifecycle,
                _PRELIMINAR_DIRNAME,
            )
        return 2

    if dest.canonical:
        # Write canónico: DELEGA en el adapter registrado (esquema exacto de la política).
        prod = _CANONICAL_ADAPTERS[d.selection_policy](d, ROOT)
    else:
        seleccion = _build_preliminary_selection(d, dest.criterio)
        if seleccion is None:
            logger.error("Ningún motor entrenado para {} — corre entrena primero.", d.data_name)
            return 1
        prod = seleccion

    _atomic_write_csv(prod, dest.path)
    dist = prod["motor_productivo"].value_counts().to_dict()
    logger.success(
        "Producción {} ({}): {} series | distribución motor {} -> {}",
        d.data_name,
        "CANÓNICA" if dest.canonical else "PRELIMINAR/NO-GO",
        len(prod),
        dist,
        dest.path,
    )
    return 0


def _num(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
