"""Materialización del candidato: el árbol administrado COMPLETO desde los HEAD sellados.

La siembra del staging clonaba a mano un puñado de rutas del sitio real —18 de las 41
superficies— y por eso el sello, con razón, no podía cubrir el censo. Aquí la semilla es
otra cosa: cada prefijo administrado por la política se extrae con `git archive` del
HEAD que después se sella, en un directorio de trabajo nuevo. Ni `cp -Rc` del árbol de
trabajo (arrastra WIP, caches y enlaces) ni `git clone` (no trae lo que DVC materializa):
el contenido rastreado, exacto, y nada más. Lo que los generadores necesiten fuera de
eso —hoy nada para los gates del sitio— se hidrata aparte, fuera del árbol censado.

`git archive` no emite rutas absolutas ni `..`, pero un HEAD puede rastrear enlaces
simbólicos u otros tipos: se rechazan al extraer, en vez de reproducirlos en un árbol
que después `inventaria` rechazaría de todos modos con un mensaje peor.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

from epiforecast.publication.weekly_staging import (
    PREFIJOS_SELLABLES,
    PoliticaCenso,
    StagingError,
    _escribe_exclusivo,
    snapshot_digests,
)

ARCHIVO_MATERIALIZACION = "materializacion.json"
_RE_SHA1 = re.compile(r"[0-9a-f]{40}")
_RE_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class RegistroMaterializacion:
    """Lo que `materialize` dejó escrito: de qué HEAD y con qué política se extrajo el árbol.

    Es el ancla del resto del flujo: `hydrate`, `run-gates` y `seal` reciben HEAD y política
    por argumentos, y sin esto nada impedía materializar desde un commit, hidratar desde
    otro y sellar contra un tercero.
    """

    heads: dict[str, str]
    politica: dict[str, str]
    prefijos: tuple[str, ...]
    archivos: int

    @staticmethod
    def lee(trabajo: Path) -> RegistroMaterializacion:
        ruta = trabajo / ARCHIVO_MATERIALIZACION
        if ruta.is_symlink() or not ruta.is_file():
            raise StagingError(
                f"no hay materialización registrada en {trabajo}; el trabajo tiene que salir de "
                "`materialize`"
            )
        try:
            crudo = json.loads(ruta.read_bytes())
        except json.JSONDecodeError as exc:
            raise StagingError(f"registro de materialización ilegible: {exc}") from exc
        if not isinstance(crudo, dict) or set(crudo) != {
            "heads",
            "politica",
            "prefijos",
            "archivos",
        }:
            raise StagingError("registro de materialización malformado")
        heads = crudo["heads"]
        if (
            not isinstance(heads, dict)
            or set(heads) != set(PREFIJOS_SELLABLES)
            or not all(isinstance(h, str) and _RE_SHA1.fullmatch(h) for h in heads.values())
        ):
            raise StagingError("la materialización no identifica un HEAD SHA1 por repositorio")
        politica = crudo["politica"]
        if (
            not isinstance(politica, dict)
            or set(politica) != {"version", "sha256"}
            or not isinstance(politica["sha256"], str)
            or not _RE_SHA256.fullmatch(politica["sha256"])
        ):
            raise StagingError("la materialización no identifica la política por SHA256")
        if not isinstance(crudo["prefijos"], list) or isinstance(crudo["archivos"], bool):
            raise StagingError("prefijos/archivos de la materialización malformados")
        return RegistroMaterializacion(
            heads=dict(heads),
            politica=dict(politica),
            prefijos=tuple(crudo["prefijos"]),
            archivos=int(crudo["archivos"]),
        )


def exige_materializacion(
    trabajo: Path,
    *,
    head_backend: str,
    head_dashboard: str | None = None,
    politica_sha256: str | None = None,
) -> RegistroMaterializacion:
    """Los HEAD y la política de este paso tienen que ser los de la materialización."""
    registro = RegistroMaterializacion.lee(trabajo)
    if registro.heads["backend"] != head_backend:
        raise StagingError(
            f"el candidato se materializó desde el backend {registro.heads['backend'][:12]} y "
            f"este paso declara {head_backend[:12]}; no es el mismo árbol"
        )
    if head_dashboard is not None and registro.heads["dashboard"] != head_dashboard:
        raise StagingError(
            f"el candidato se materializó desde el dashboard {registro.heads['dashboard'][:12]} "
            f"y este paso declara {head_dashboard[:12]}; no es el mismo árbol"
        )
    if politica_sha256 is not None and registro.politica["sha256"] != politica_sha256:
        raise StagingError(
            "la política de este paso no es la que gobernó la materialización "
            f"({registro.politica['sha256'][:12]}… frente a {politica_sha256[:12]}…)"
        )
    return registro


@dataclass(frozen=True)
class Materializacion:
    trabajo: Path
    outputs: Path
    semilla: Path
    archivos: int
    politica: PoliticaCenso
    heads: dict[str, str]


def _archiva(repo: Path, head: str, subruta: str | None) -> bytes:
    argv = ["git", "-C", str(repo), "archive", "--format=tar", head]
    if subruta:
        argv += ["--", subruta]
    salida = subprocess.run(argv, capture_output=True)
    if salida.returncode != 0:
        raise StagingError(
            f"git archive falló en {repo} para {head[:12]}"
            f"{' ' + subruta if subruta else ''}: {salida.stderr.decode(errors='replace').strip()}"
        )
    return salida.stdout


def _extrae(crudo: bytes, destino: Path) -> int:
    """Extrae sólo archivos regulares, con gramática cerrada, creando cada uno en exclusiva."""
    extraidos = 0
    with tarfile.open(fileobj=io.BytesIO(crudo), mode="r:") as tar:
        for miembro in tar:
            if miembro.isdir():
                continue
            if not miembro.isreg():
                raise StagingError(
                    f"el HEAD rastrea una entrada que no es un archivo regular: "
                    f"{miembro.name!r} (tipo {miembro.type!r}); un enlace o tipo especial no "
                    "se materializa"
                )
            partes = miembro.name.split("/")
            if miembro.name.startswith("/") or any(p in ("", ".", "..") for p in partes):
                raise StagingError(f"ruta inválida en el archivo git: {miembro.name!r}")
            if ".git" in partes:
                raise StagingError(f"ruta bajo .git en el archivo git: {miembro.name!r}")
            ruta = destino.joinpath(*partes)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            flujo = tar.extractfile(miembro)
            if flujo is None:  # pragma: no cover - isreg() ya lo garantiza
                raise StagingError(f"no se pudo leer {miembro.name!r} del archivo git")
            _escribe_exclusivo(ruta, flujo.read())
            extraidos += 1
    return extraidos


def _prefijos_sin_solape(prefijos: tuple[str, ...]) -> list[str]:
    """`dashboard/` ya contiene `dashboard/epibot/`: extraer los dos duplicaría archivos."""
    return [p for p in prefijos if not any(otro != p and p.startswith(otro) for otro in prefijos)]


def materializa_candidato(
    trabajo: Path, repos: dict[str, Path], heads: dict[str, str]
) -> Materializacion:
    """Crea `<trabajo>/outputs` con el árbol administrado completo y su semilla.

    La política se lee del HEAD del backend que se va a sellar, y son SUS prefijos los que
    deciden qué se materializa: no hay lista de rutas en el orquestador. El directorio de
    trabajo tiene que ser nuevo; si algo falla a medias se retira entero, porque un
    candidato parcial es exactamente lo que este paso existe para impedir.
    """
    if set(repos) != set(PREFIJOS_SELLABLES) or set(heads) != set(PREFIJOS_SELLABLES):
        raise StagingError(f"hacen falta repos y HEAD para exactamente {PREFIJOS_SELLABLES}")
    if trabajo.is_symlink() or trabajo.exists():
        raise StagingError(
            f"ya existe el directorio de trabajo {trabajo}; un candidato no se pisa"
        )
    padre = trabajo.parent
    if padre.is_symlink() or not padre.is_dir():
        raise StagingError(f"no existe el directorio padre del trabajo (o es un enlace): {padre}")

    politica = PoliticaCenso.del_head(repos["backend"], heads["backend"])
    trabajo.mkdir()
    try:
        outputs = trabajo / "outputs"
        outputs.mkdir()
        total = 0
        for prefijo in _prefijos_sin_solape(politica.prefijos_administrados):
            espacio, _, subruta = prefijo.rstrip("/").partition("/")
            crudo = _archiva(repos[espacio], heads[espacio], subruta or None)
            total += _extrae(crudo, outputs / espacio)
        semilla = snapshot_digests(outputs)
        ruta_semilla = trabajo / "semilla.json"
        _escribe_exclusivo(
            ruta_semilla, json.dumps(semilla, indent=2, sort_keys=True).encode() + b"\n"
        )
        _escribe_exclusivo(
            trabajo / ARCHIVO_MATERIALIZACION,
            json.dumps(
                {
                    "heads": dict(sorted(heads.items())),
                    "politica": {"version": politica.version, "sha256": politica.sha256},
                    "prefijos": list(politica.prefijos_administrados),
                    "archivos": total,
                },
                indent=2,
                sort_keys=True,
            ).encode()
            + b"\n",
        )
    except BaseException:
        shutil.rmtree(trabajo, ignore_errors=True)
        raise
    return Materializacion(
        trabajo=trabajo,
        outputs=outputs,
        semilla=ruta_semilla,
        archivos=total,
        politica=politica,
        heads=dict(heads),
    )
