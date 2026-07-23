"""Selector productivo genérico por padecimiento (EPIC 3 + gates Fase 1).

Aplica la regla canónica (``epiforecast.selection.select_engine``: sMAPE→MASE→RMSE + banda
5% + orden estable) sobre los motores ELEGIBLES del padecimiento, usando las métricas CV por
serie de cada ``{Motor}_{Padecimiento}_completo.csv``.

**Gate COMPLETO (lifecycle + ownership + slug) en ``resolve_destination``**, fail-closed:

- Un padecimiento NO ``published`` no puede recrear una selección canónica: aborta sin escribir,
  salvo ``--allow-preliminary``, que emite un CSV **PRELIMINAR** bajo ``_preliminar_NO_GO/`` con
  criterio ``insample_cv_PRELIMINAR_NO_GO`` (nunca la etiqueta de la política).
- Un padecimiento ``published`` es dominio de su selector DEDICADO. El genérico rechaza toda
  escritura canónica salvo que exista un **adapter callable** registrado en ``_CANONICAL_ADAPTERS``
  (hoy vacío) y el write **delega** en él. Reserva además ``_DEDICATED_ARTIFACTS``.
- El ``slug`` se valida (formato + longitud + containment anclado a ROOT).

**Publicación robusta:** la selección se valida CONTEXTUALMENTE (DataFrame, escalares, enfermedad,
política, motores permitidos, no-null, claves únicas) y ``dist`` se calcula ANTES del ``replace`` —
nada susceptible de fallar corre después de publicar. La escritura es **TOCTOU-safe**: se camina
desde ROOT con ``openat``+``O_NOFOLLOW`` (un swap de directorio por symlink aborta), el tmp es
exclusivo (``O_CREAT|O_EXCL|O_NOFOLLOW``) en el MISMO dir con el modo del destino preservado (0644),
y el flujo es fsync(tmp) → ``os.replace`` relativo (dirfd) → fsync(dir) best-effort, con lock
``fcntl`` estable cuyo cierre está garantizado aunque ``LOCK_UN`` falle.

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
import stat

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
# ``policy -> adapter``. VACÍO: no hay adapter validado. Registrar exige una FUNCIÓN real
# (verificada con ``callable``), no una string: así, añadir una cadena NO rehabilita el writer.
CanonicalAdapter = Callable[["registry.Disease", Path], pd.DataFrame]
_CANONICAL_ADAPTERS: dict[str, CanonicalAdapter] = {}

# Artefactos canónicos con dueño DEDICADO — el genérico nunca los escribe, ni con adapter.
_DEDICATED_ARTIFACTS: frozenset[str] = frozenset({"produccion_dengue.csv"})

# Columnas mínimas que DEBE tener cualquier selección antes de publicarse.
_REQUIRED_COLUMNS = ("padecimiento", "entidad", "sexo", "motor_productivo", "criterio_seleccion")
_DEFAULT_MODE = 0o644

# Slug seguro: minúsculas/dígitos/guion-bajo, sin puntos ni separadores (impide traversal ../).
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")
_SLUG_MAX_LEN = 64  # límite portable de longitud (el filename queda muy por debajo de 255).


class SlugError(ValueError):
    """slug con formato/longitud inseguros o ruta que escaparía de ROOT."""


class SelectionSchemaError(ValueError):
    """La selección a escribir no cumple el contrato contextual (esquema/valores/claves)."""


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.fullmatch(slug) or len(slug) > _SLUG_MAX_LEN:
        raise SlugError(f"slug inseguro: {slug!r} (^[a-z0-9][a-z0-9_]*$, ≤{_SLUG_MAX_LEN})")


def _safe_child(parent: Path, filename: str, *, anchor: Path) -> Path:
    """``parent/filename`` ANCLADO a ``anchor`` (ROOT): la ruta RESUELTA debe quedar dentro de
    ``anchor`` resuelto. Pre-check estático (el writer re-verifica en runtime vía openat/O_NOFOLLOW,
    lo que además cubre swaps TOCTOU). Devuelve la ruta SIN resolver.
    """
    child = parent / filename
    child_r, anchor_r = child.resolve(), anchor.resolve()
    if child_r != anchor_r and anchor_r not in child_r.parents:
        raise SlugError(f"ruta '{child}' escaparía de ROOT '{anchor_r}'")
    return child


def _validate_selection(prod: object, disease: registry.Disease, criterio: str) -> None:
    """Contrato CONTEXTUAL antes de publicar. Corre entero ANTES del ``replace``."""
    if not isinstance(prod, pd.DataFrame):
        raise SelectionSchemaError(f"la selección no es un DataFrame: {type(prod).__name__}")
    missing = [c for c in _REQUIRED_COLUMNS if c not in prod.columns]
    if missing:
        raise SelectionSchemaError(f"faltan columnas requeridas: {missing}")
    if len(prod) == 0:
        raise SelectionSchemaError("selección vacía (0 filas)")
    # Valores ESCALARES en columnas requeridas (rechaza list/dict/set/tuple) — antes de astype.
    for c in _REQUIRED_COLUMNS:
        if prod[c].map(lambda v: isinstance(v, (list, dict, set, tuple))).any():
            raise SelectionSchemaError(f"columna '{c}' con valores no escalares")
    if prod[list(_REQUIRED_COLUMNS)].isna().to_numpy().any():
        raise SelectionSchemaError("nulls en columnas requeridas")
    pads = set(prod["padecimiento"].astype(str).unique())
    if pads != {disease.data_name}:
        raise SelectionSchemaError(f"padecimiento {pads} != {disease.data_name!r}")
    crits = set(prod["criterio_seleccion"].astype(str).unique())
    if crits != {criterio}:
        raise SelectionSchemaError(f"criterio {crits} != {criterio!r}")
    permitidos = {_ENGINE_CAP.get(e, e) for e in disease.eligible_engines}
    motores = set(prod["motor_productivo"].astype(str).unique())
    if not motores <= permitidos:
        raise SelectionSchemaError(f"motores no permitidos: {sorted(motores - permitidos)}")
    if prod.duplicated(subset=["entidad", "sexo"]).any():
        raise SelectionSchemaError("claves (entidad, sexo) duplicadas")


@contextmanager
def _file_lock(lock_path: Path) -> Iterator[None]:
    """Lock exclusivo (``fcntl.flock``) sobre un lockfile ESTABLE.

    El lockfile NO se borra (unlink tras liberar causa split-brain). El descriptor se CIERRA
    siempre, aunque ``LOCK_UN`` falle (el close libera el lock igual y no filtra el fd).
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        with suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _open_dir_chain(root: Path, dir_parts: tuple[str, ...]) -> list[int]:
    """Abre ROOT (resuelto, confiable) y camina ``dir_parts`` con ``O_NOFOLLOW``, creando faltantes.

    Un componente que sea symlink aborta (ELOOP) — defensa TOCTOU: un swap por symlink DESPUÉS del
    pre-check estático no permite escribir fuera de ROOT. Devuelve [root_fd, …, parent_fd].
    """
    fds = [os.open(str(root.resolve()), os.O_RDONLY | os.O_DIRECTORY)]
    try:
        for name in dir_parts:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            try:
                fds.append(os.open(name, flags, dir_fd=fds[-1]))
            except FileNotFoundError:
                os.mkdir(name, 0o755, dir_fd=fds[-1])
                fds.append(os.open(name, flags, dir_fd=fds[-1]))
    except BaseException:
        for fd in reversed(fds):
            with suppress(OSError):
                os.close(fd)
        raise
    return fds


def _create_tmp_excl(parent_fd: int, base: str) -> tuple[int, str]:
    """Crea un tmp EXCLUSIVO (``O_CREAT|O_EXCL|O_NOFOLLOW``) relativo a ``parent_fd``. Sin symlinks."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW
    for i in range(10000):
        name = f".{base}.tmp.{os.getpid()}.{i}"
        try:
            return os.open(name, flags, _DEFAULT_MODE, dir_fd=parent_fd), name
        except FileExistsError:
            continue
    raise OSError(f"no se pudo crear tmp exclusivo para {base}")


def _roundtrip_check(parent_fd: int, tmp_name: str, df: pd.DataFrame) -> None:
    rfd = os.open(tmp_name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    with os.fdopen(rfd, encoding="utf-8") as fh:
        check = pd.read_csv(fh)
    if list(check.columns) != list(df.columns) or len(check) != len(df):
        raise OSError(f"validación round-trip falló para {tmp_name}")


def _write_and_replace(df: pd.DataFrame, parent_fd: int, filename: str) -> None:
    tmp_fd, tmp_name = _create_tmp_excl(parent_fd, filename)
    try:
        # Preservar el modo del destino solo si es un archivo REGULAR (P1: no bajar 0644→0600;
        # nunca heredar el modo de un symlink). Nuevo o no-regular → 0644.
        mode = _DEFAULT_MODE
        with suppress(FileNotFoundError):
            st = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
            if stat.S_ISREG(st.st_mode):
                mode = stat.S_IMODE(st.st_mode)
        os.fchmod(tmp_fd, mode)
        with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="") as fh:
            tmp_fd = -1  # fh es dueño del fd ahora (lo cierra al salir del with)
            df.to_csv(fh, index=False)
            fh.flush()
            os.fsync(fh.fileno())
        _roundtrip_check(parent_fd, tmp_name, df)
        os.replace(tmp_name, filename, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    except BaseException:
        if tmp_fd != -1:
            with suppress(OSError):
                os.close(tmp_fd)
        with suppress(OSError):
            os.unlink(tmp_name, dir_fd=parent_fd)
        raise
    # Publicado. Durabilidad del directorio: best-effort (no revierte ni falla la publicación).
    with suppress(OSError):
        os.fsync(parent_fd)


def _atomic_write_csv(df: pd.DataFrame, dest: Path, *, root: Path) -> None:
    """Escritura atómica TOCTOU-safe anclada a ``root`` (dirfd/openat + O_NOFOLLOW, replace relativo).

    Serializa con un lock ``fcntl`` anclado al dir destino. El tmp se limpia ante cualquier fallo;
    tras el ``replace`` solo corre un fsync(dir) best-effort.
    """
    *dir_parts, filename = dest.relative_to(root).parts
    fds = _open_dir_chain(root, tuple(dir_parts))
    parent_fd = fds[-1]
    try:
        lock_fd = os.open(
            f".{filename}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o644, dir_fd=parent_fd
        )
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            _write_and_replace(df, parent_fd, filename)
        finally:
            with suppress(OSError):
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)  # SIEMPRE (aunque LOCK_UN falle) → no filtra fd
    finally:
        for fd in reversed(fds):
            with suppress(OSError):
                os.close(fd)


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

    - ``published`` + ``allow_preliminary``: ``None`` (contradicción).
    - ``published`` con adapter CALLABLE registrado y artefacto NO reservado: ruta CANÓNICA.
    - ``published`` sin adapter callable, o artefacto en ``_DEDICATED_ARTIFACTS``: ``None``.
    - no ``published`` sin ``allow_preliminary``: ``None``.
    - no ``published`` con ``allow_preliminary``: ruta PRELIMINAR en ``_preliminar_NO_GO/``.
    """
    _validate_slug(d.slug)
    proddetails = root / "reports" / "ProdDetails"

    if d.lifecycle == "published":
        if allow_preliminary:
            return None  # contradicción: un published no admite preliminar
        if not callable(_CANONICAL_ADAPTERS.get(d.selection_policy)):
            return None
        canonical = _safe_child(proddetails, f"produccion_{d.slug}.csv", anchor=root)
        if canonical.name in _DEDICATED_ARTIFACTS:
            return None
        return Destination(canonical, d.selection_policy, True)

    if not allow_preliminary:
        return None
    prelim = _safe_child(
        proddetails / _PRELIMINAR_DIRNAME, f"produccion_{d.slug}_PRELIMINAR.csv", anchor=root
    )
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

    # Validación contextual + dist ANTES de publicar: nada susceptible de fallar tras el replace.
    try:
        _validate_selection(prod, d, dest.criterio)
    except SelectionSchemaError as e:
        logger.error("Selección inválida para {} (NO se publica): {}", d.data_name, e)
        return 3
    dist = prod["motor_productivo"].value_counts().to_dict()

    try:
        _atomic_write_csv(prod, dest.path, root=ROOT)
    except OSError as e:
        logger.error("Escritura atómica falló para {} (no publicado): {}", d.data_name, e)
        return 4

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
