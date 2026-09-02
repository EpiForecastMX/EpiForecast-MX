"""Destinos desechables para `apply`: worktrees registrados, verificados con git y bajo lock.

`apply` instalaba en cualquier par de directorios que se le diera. Con el sello ya
gobernando qué bytes se instalan, la pregunta pendiente era **dónde**: un HEAD igual no
garantiza un árbol igual, dos apply concurrentes colisionan, y una interrupción a mitad
deja una mezcla sin recuperación. La respuesta de P0.6 no es un journal: es que el destino
sea **desechable**. Se instala únicamente en un par de worktrees creados para ese `run_id`,
limpios y en el HEAD exacto; si algo se tuerce —excepción, interrupción, residuo, digest
final discordante— el par se marca inválido y se reconstruye desde cero. Nunca se
«continúa».

Cómo se cierra la puerta al destino arbitrario:

- el par lo crea esta misma herramienta (`prepara_worktrees`) con `git worktree add
  --detach` en el HEAD sellado, y deja un **registro** `run_id -> destinos` fuera de los
  worktrees, con sidecar, y un lock de inode estable;
- `aplica` no acepta rutas: acepta la raíz del registro, y contrasta cada destino con git
  —`--show-toplevel`, `--git-common-dir`, `worktree list --porcelain`, HEAD, `status`—, no
  con lo que diga el registro. El registro dice dónde mirar; git dice qué hay;
- el worktree principal del repositorio nunca es destino: su `--git-common-dir` cuelga de
  él mismo;
- el lock es `flock` sobre un archivo que se crea una vez y no se borra al liberar: un lock
  que se `unlink`a deja a un tercer proceso crear otro inode con el mismo nombre y entrar.

La atomicidad sigue siendo por archivo y por repositorio; entre los dos repositorios no la
hay, y no se promete. Lo que sí se promete: ningún par parcial se promueve.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any

from epiforecast.publication.weekly_staging import (
    MODO_APLICABLE,
    PREFIJOS_SELLABLES,
    Manifiesto,
    StagingError,
    _escribe_atomico,
    _escribe_exclusivo,
    _instala,
    _sin_duplicados,
    sha256_de,
    valida_ruta_sellable,
    verifica,
    verifica_sidecar,
)

ESQUEMA_REGISTRO = "destinos/1"
ARCHIVO_REGISTRO = "registro.json"
ARCHIVO_LOCK = "apply.lock"
ESTADO_LISTO = "listo"
ESTADO_EN_CURSO = "en_curso"
ESTADO_APLICADO = "aplicado"
ESTADO_INVALIDO = "invalido"
ESTADO_DESCARTADO = "descartado"
ESTADOS = (ESTADO_LISTO, ESTADO_EN_CURSO, ESTADO_APLICADO, ESTADO_INVALIDO, ESTADO_DESCARTADO)
_RE_SHA1 = re.compile(r"[0-9a-f]{40}")
_RE_SHA256 = re.compile(r"[0-9a-f]{64}")


def _git(cwd: Path, *args: str) -> str:
    salida = subprocess.run(
        ["git", "-C", str(cwd), "-c", "core.quotepath=false", *args],
        capture_output=True,
        text=True,
    )
    if salida.returncode != 0:
        raise StagingError(
            f"git {' '.join(args)} falló en {cwd}: {salida.stderr.strip() or salida.stdout.strip()}"
        )
    return salida.stdout


@dataclass(frozen=True)
class Destino:
    """Un worktree desechable: dónde está, de qué repositorio cuelga y en qué HEAD."""

    espacio: str
    ruta: str
    repo: str
    head: str

    def como_dict(self) -> dict[str, str]:
        return {"ruta": self.ruta, "repo": self.repo, "head": self.head}


@dataclass
class RegistroDestinos:
    """`run_id -> par de worktrees`, con estado. Vive fuera de los worktrees, con sidecar."""

    raiz: Path
    run_id: str
    manifiesto_sha256: str
    estado: str
    motivo: str
    creado: str
    destinos: dict[str, Destino]

    CLAVES = ("esquema", "run_id", "manifiesto_sha256", "estado", "motivo", "creado", "destinos")

    def como_dict(self) -> dict[str, Any]:
        return {
            "esquema": ESQUEMA_REGISTRO,
            "run_id": self.run_id,
            "manifiesto_sha256": self.manifiesto_sha256,
            "estado": self.estado,
            "motivo": self.motivo,
            "creado": self.creado,
            "destinos": {esp: d.como_dict() for esp, d in sorted(self.destinos.items())},
        }

    def escribe(self) -> None:
        crudo = json.dumps(self.como_dict(), indent=2, ensure_ascii=False, sort_keys=True).encode()
        destino = self.raiz / ARCHIVO_REGISTRO
        _escribe_atomico(destino, crudo + b"\n", ".part")
        _escribe_atomico(
            destino.with_name(destino.stem + ".sha256"),
            hashlib.sha256(crudo + b"\n").hexdigest().encode() + b"\n",
            ".part",
        )

    def marca(self, estado: str, motivo: str = "") -> None:
        if estado not in ESTADOS:
            raise StagingError(f"estado de registro desconocido: {estado!r}")
        self.estado = estado
        self.motivo = motivo
        self.escribe()

    @staticmethod
    def lee(raiz: Path) -> RegistroDestinos:
        if raiz.is_symlink() or not raiz.is_dir():
            raise StagingError(f"no existe la raíz de destinos (o es un enlace): {raiz}")
        ruta = raiz / ARCHIVO_REGISTRO
        if ruta.is_symlink() or not ruta.is_file():
            raise StagingError(
                f"no hay registro de destinos en {raiz}; crea el par con `prepare-worktrees`"
            )
        verifica_sidecar(ruta)
        try:
            crudo = json.loads(ruta.read_bytes(), object_pairs_hook=_sin_duplicados)
        except json.JSONDecodeError as exc:
            raise StagingError(f"registro de destinos ilegible: {exc}") from exc
        if not isinstance(crudo, dict) or set(crudo) != set(RegistroDestinos.CLAVES):
            raise StagingError("registro de destinos malformado")
        if crudo["esquema"] != ESQUEMA_REGISTRO:
            raise StagingError(f"registro de destinos de otro esquema: {crudo['esquema']!r}")
        if not isinstance(crudo["run_id"], str) or not _RE_SHA256.fullmatch(crudo["run_id"]):
            raise StagingError("el registro no identifica un run_id de 64 hex")
        if not isinstance(crudo["manifiesto_sha256"], str) or not _RE_SHA256.fullmatch(
            crudo["manifiesto_sha256"]
        ):
            raise StagingError("el registro no identifica el manifiesto por SHA256")
        if crudo["estado"] not in ESTADOS:
            raise StagingError(f"estado de registro desconocido: {crudo['estado']!r}")
        if not isinstance(crudo["motivo"], str) or not isinstance(crudo["creado"], str):
            raise StagingError("motivo/creado del registro tienen que ser texto")
        destinos_crudos = crudo["destinos"]
        if not isinstance(destinos_crudos, dict) or set(destinos_crudos) != set(
            PREFIJOS_SELLABLES
        ):
            raise StagingError(
                f"el registro tiene que declarar exactamente los destinos {PREFIJOS_SELLABLES}"
            )
        destinos: dict[str, Destino] = {}
        for espacio, valor in destinos_crudos.items():
            if not isinstance(valor, dict) or set(valor) != {"ruta", "repo", "head"}:
                raise StagingError(f"destino {espacio} malformado: {valor!r}")
            for clave in ("ruta", "repo"):
                if not isinstance(valor[clave], str) or not valor[clave].startswith("/"):
                    raise StagingError(f"{clave} del destino {espacio} tiene que ser absoluta")
            if not isinstance(valor["head"], str) or not _RE_SHA1.fullmatch(valor["head"]):
                raise StagingError(f"head del destino {espacio} no es un SHA1 de 40 hex")
            destinos[espacio] = Destino(
                espacio=espacio, ruta=valor["ruta"], repo=valor["repo"], head=valor["head"]
            )
        return RegistroDestinos(
            raiz=raiz,
            run_id=crudo["run_id"],
            manifiesto_sha256=crudo["manifiesto_sha256"],
            estado=crudo["estado"],
            motivo=crudo["motivo"],
            creado=crudo["creado"],
            destinos=destinos,
        )


@contextmanager
def lock_exclusivo(raiz: Path) -> Iterator[None]:
    """`flock` no bloqueante sobre `apply.lock`, que existe desde `prepare-worktrees`.

    El archivo nunca se borra: un lock que se `unlink`a al liberar deja que un tercer
    proceso cree otro inode con el mismo nombre y entre a la vez. Comprobado en el writer.
    """
    ruta = raiz / ARCHIVO_LOCK
    if ruta.is_symlink():
        raise StagingError(f"el lock es un enlace simbólico: {ruta}")
    if not ruta.is_file():
        raise StagingError(f"falta el lock {ruta}; el par no lo creó esta herramienta")
    descriptor = os.open(ruta, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise StagingError(f"el lock no es un archivo regular: {ruta}")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StagingError(f"otro apply tiene el bloqueo de {raiz}; no se compite") from exc
        yield
    finally:
        os.close(descriptor)


def _raiz_de_repo(repo: Path) -> Path:
    """La raíz del worktree PRINCIPAL de `repo`, comprobada con git y no con la ruta."""
    real = repo.resolve()
    toplevel = Path(_git(real, "rev-parse", "--show-toplevel").strip()).resolve()
    comun = Path(_git(real, "rev-parse", "--git-common-dir").strip())
    if not comun.is_absolute():
        comun = real / comun
    comun = comun.resolve()
    if toplevel != real:
        raise StagingError(f"{repo} no es la raíz de un repositorio, es {toplevel}")
    if comun.parent != real:
        raise StagingError(
            f"{repo} no es el worktree principal de su repositorio (git-common-dir {comun})"
        )
    return real


def _worktrees_registrados(repo: Path) -> dict[Path, dict[str, str]]:
    """`git worktree list --porcelain` como {ruta_real: {HEAD, detached}}."""
    bloques: dict[Path, dict[str, str]] = {}
    actual: dict[str, str] = {}
    for linea in _git(repo, "worktree", "list", "--porcelain").splitlines():
        if not linea.strip():
            if "worktree" in actual:
                bloques[Path(actual["worktree"]).resolve()] = actual
            actual = {}
            continue
        clave, _, valor = linea.partition(" ")
        actual[clave] = valor
    if "worktree" in actual:
        bloques[Path(actual["worktree"]).resolve()] = actual
    return bloques


def _verifica_destino(
    destino: Destino, head_esperado: str, run_dir: Path, *, limpio: bool
) -> Path:
    """Contrasta un destino con git. Devuelve su ruta real.

    El registro sólo dice dónde mirar: cada propiedad —que es un worktree, de qué repositorio,
    en qué HEAD, si está limpio— se le pregunta a git desde el propio destino y desde el
    repositorio principal, y las respuestas tienen que coincidir entre sí y con el registro.
    """
    ruta = Path(destino.ruta)
    if ruta.is_symlink():
        raise StagingError(f"el destino {destino.espacio} es un enlace simbólico: {ruta}")
    if not ruta.is_dir():
        raise StagingError(f"el destino {destino.espacio} no existe: {ruta}")
    real = ruta.resolve()
    if real != ruta:
        raise StagingError(
            f"el destino {destino.espacio} no está en su ruta real ({ruta} -> {real}); un "
            "componente es un enlace"
        )
    repo = Path(destino.repo)
    if real == repo or repo in real.parents and (repo / ".git") in real.parents:
        raise StagingError(
            f"el destino {destino.espacio} es el worktree canónico o vive dentro de su .git"
        )
    if real == run_dir or run_dir in real.parents or real in run_dir.parents:
        raise StagingError(f"el destino {destino.espacio} se solapa con la corrida sellada")

    toplevel = Path(_git(real, "rev-parse", "--show-toplevel").strip()).resolve()
    if toplevel != real:
        raise StagingError(
            f"el destino {destino.espacio} no es la raíz de un worktree: {toplevel}"
        )
    comun = Path(_git(real, "rev-parse", "--git-common-dir").strip())
    if not comun.is_absolute():
        comun = real / comun
    comun = comun.resolve()
    if comun.parent != repo or comun.parent == real:
        raise StagingError(
            f"el destino {destino.espacio} no cuelga del repositorio registrado {repo} "
            f"(git-common-dir {comun})"
        )
    registrados = _worktrees_registrados(repo)
    bloque = registrados.get(real)
    if bloque is None:
        raise StagingError(
            f"el destino {destino.espacio} no figura en `git worktree list` de {repo}"
        )
    if bloque.get("HEAD") != head_esperado or "detached" not in bloque:
        raise StagingError(
            f"el destino {destino.espacio} no está desprendido en el HEAD sellado "
            f"{head_esperado[:12]} (git dice {bloque.get('HEAD', '?')[:12]})"
        )
    if _git(real, "rev-parse", "HEAD").strip() != head_esperado or destino.head != head_esperado:
        raise StagingError(f"el destino {destino.espacio} no está en el HEAD sellado")
    if limpio:
        estado = _git(real, "status", "--porcelain", "--untracked-files=all")
        if estado.strip():
            primeras = [linea for linea in estado.splitlines()[:5]]
            raise StagingError(
                f"el destino {destino.espacio} no está limpio: {primeras}. Un par desechable "
                "sucio no se usa; se descarta y se reconstruye"
            )
    return real


def prepara_worktrees(
    ruta_manifiesto: Path, repos: dict[str, Path], raiz: Path
) -> RegistroDestinos:
    """Crea el par desechable para un manifiesto aplicable y lo registra.

    `raiz` se crea en exclusiva: si existe, es otra corrida o un residuo, y no se pisa. Los
    worktrees se crean desprendidos en el HEAD sellado con `git worktree add --detach`, y
    se comprueban recién creados con las mismas reglas que `aplica` usará después.
    """
    if ruta_manifiesto.is_symlink() or not ruta_manifiesto.is_file():
        raise StagingError(f"no existe el manifiesto: {ruta_manifiesto}")
    manifiesto = Manifiesto.lee(ruta_manifiesto)
    run_dir = ruta_manifiesto.parent.resolve()
    verifica(
        run_dir,
        manifiesto,
        head_backend=manifiesto.entrada.head_backend,
        head_dashboard=manifiesto.entrada.head_dashboard,
    )
    if manifiesto.modo != MODO_APLICABLE:
        raise StagingError(
            f"el sello está en modo {manifiesto.modo!r}: un borrador no necesita destinos. "
            f"{manifiesto.motivo_draft}"
        )
    if set(repos) != set(PREFIJOS_SELLABLES):
        raise StagingError(f"hacen falta exactamente los repositorios {PREFIJOS_SELLABLES}")
    heads = {
        "backend": manifiesto.entrada.head_backend,
        "dashboard": manifiesto.entrada.head_dashboard,
    }
    raices_repo = {espacio: _raiz_de_repo(repo) for espacio, repo in repos.items()}
    for espacio, repo in raices_repo.items():
        salida = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"{heads[espacio]}^{{commit}}"],
            capture_output=True,
        )
        if salida.returncode != 0:
            raise StagingError(
                f"el HEAD sellado {heads[espacio][:12]} no existe en el repositorio {espacio} "
                f"({repo})"
            )

    padre = raiz.parent
    if padre.is_symlink():
        raise StagingError(f"el directorio padre de los destinos es un enlace: {padre}")
    # `runs/_release/` puede no existir todavía: se crea. Lo que no se crea es la raíz del
    # par, que tiene que ser nueva.
    padre.mkdir(parents=True, exist_ok=True)
    if not padre.is_dir():
        raise StagingError(f"el directorio padre de los destinos no es un directorio: {padre}")
    raiz_real = padre.resolve() / raiz.name
    for espacio, repo in raices_repo.items():
        if (
            raiz_real == repo
            or raiz_real in (repo / ".git").parents
            or (repo / ".git") in raiz_real.parents
        ):
            raise StagingError(f"la raíz de destinos no puede caer dentro del .git de {espacio}")
    if raiz_real == run_dir or run_dir in raiz_real.parents or raiz_real in run_dir.parents:
        raise StagingError("la raíz de destinos no puede solaparse con la corrida sellada")
    try:
        raiz.mkdir()
    except FileExistsError as exc:
        raise StagingError(
            f"ya existe {raiz}; un par de destinos no se reutiliza ni se pisa: elige otra raíz"
        ) from exc

    destinos: dict[str, Destino] = {}
    for espacio in sorted(raices_repo):
        repo = raices_repo[espacio]
        ruta = raiz_real / espacio
        _git(repo, "worktree", "add", "--detach", str(ruta), heads[espacio])
        destinos[espacio] = Destino(
            espacio=espacio, ruta=str(ruta.resolve()), repo=str(repo), head=heads[espacio]
        )
        _verifica_destino(destinos[espacio], heads[espacio], run_dir, limpio=True)

    _escribe_exclusivo(raiz_real / ARCHIVO_LOCK, b"")
    registro = RegistroDestinos(
        raiz=raiz_real,
        run_id=manifiesto.run_id,
        manifiesto_sha256=sha256_de(ruta_manifiesto),
        estado=ESTADO_LISTO,
        motivo="",
        creado=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        destinos=destinos,
    )
    registro.escribe()
    return registro


def descarta_worktrees(raiz: Path) -> RegistroDestinos:
    """Retira el par con `git worktree remove --force` y lo marca descartado.

    Un par inválido o ya aplicado se descarta; nunca se «repara». El registro se conserva
    para dejar constancia de por qué.
    """
    registro = RegistroDestinos.lee(raiz)
    with lock_exclusivo(raiz):
        for destino in registro.destinos.values():
            ruta = Path(destino.ruta)
            repo = Path(destino.repo)
            if ruta.is_dir() and not ruta.is_symlink():
                _git(repo, "worktree", "remove", "--force", str(ruta))
            _git(repo, "worktree", "prune")
        registro.marca(ESTADO_DESCARTADO, registro.motivo)
    return registro


def _exige_instalado(manifiesto: Manifiesto, destinos: dict[str, Path]) -> None:
    """Después de instalar, cada destino contiene EXACTAMENTE los bytes sellados."""
    discordantes: list[str] = []
    for rel, digest in sorted(manifiesto.inventario.items()):
        partes = valida_ruta_sellable(rel)
        objetivo = destinos[partes[0]].joinpath(*partes[1:])
        if objetivo.is_symlink() or not objetivo.is_file() or sha256_de(objetivo) != digest:
            discordantes.append(rel)
    for rel in manifiesto.tombstones:
        partes = valida_ruta_sellable(rel)
        if os.path.lexists(destinos[partes[0]].joinpath(*partes[1:])):
            discordantes.append(rel)
    if discordantes:
        raise StagingError(
            f"digest final discordante en {len(discordantes)} ruta(s): {discordantes[:5]}; el "
            "par queda inválido"
        )


def aplica(raiz_staging: Path, manifiesto: Manifiesto, raiz_destinos: Path) -> list[str]:
    """Instala el sello ÚNICAMENTE en el par registrado para su `run_id`.

    No acepta rutas de destino. Bajo el lock: relee el registro, rechaza pares en curso
    (interrupción anterior), inválidos o descartados, contrasta cada worktree con git,
    instala con la transacción por archivo, y exige el digest final exacto. Cualquier
    fallo marca el par inválido; no hay segunda oportunidad sobre el mismo par.
    """
    if manifiesto.modo != MODO_APLICABLE:
        raise StagingError(
            f"el sello está en modo {manifiesto.modo!r} y no es aplicable. "
            f"{manifiesto.motivo_draft or 'No declara motivo.'}"
        )
    registro = RegistroDestinos.lee(raiz_destinos)
    if registro.run_id != manifiesto.run_id:
        raise StagingError(
            f"el par de destinos es de otra corrida ({registro.run_id[:12]}… frente a "
            f"{manifiesto.run_id[:12]}…)"
        )
    manifiesto_disco = raiz_staging / "manifest.json"
    if registro.manifiesto_sha256 != sha256_de(manifiesto_disco):
        raise StagingError("el par de destinos se preparó para otro manifiesto")

    with lock_exclusivo(raiz_destinos):
        registro = RegistroDestinos.lee(raiz_destinos)
        if registro.estado == ESTADO_EN_CURSO:
            registro.marca(
                ESTADO_INVALIDO,
                "un apply anterior quedó en curso: terminación abrupta; reconstruye el par",
            )
            raise StagingError(
                "un apply anterior sobre este par quedó interrumpido; el par queda inválido y "
                "hay que reconstruirlo desde cero"
            )
        if registro.estado in (ESTADO_INVALIDO, ESTADO_DESCARTADO):
            raise StagingError(
                f"el par de destinos está {registro.estado}: {registro.motivo or 'sin motivo'}"
            )
        heads = {
            "backend": manifiesto.entrada.head_backend,
            "dashboard": manifiesto.entrada.head_dashboard,
        }
        run_dir = raiz_staging.resolve()
        destinos = {espacio: Path(d.ruta) for espacio, d in registro.destinos.items()}
        if registro.estado == ESTADO_APLICADO:
            # Repetir un apply completado es un no-op VERIFICADO, no una reinstalación.
            for espacio, destino in registro.destinos.items():
                _verifica_destino(destino, heads[espacio], run_dir, limpio=False)
            _exige_instalado(manifiesto, destinos)
            return sorted(manifiesto.inventario)

        try:
            for espacio, destino in registro.destinos.items():
                _verifica_destino(destino, heads[espacio], run_dir, limpio=True)
            registro.marca(ESTADO_EN_CURSO)
            instalados = _instala(
                raiz_staging,
                manifiesto,
                destinos,
                head_backend=heads["backend"],
                head_dashboard=heads["dashboard"],
            )
            _exige_instalado(manifiesto, destinos)
        except BaseException as exc:
            registro.marca(ESTADO_INVALIDO, f"{type(exc).__name__}: {exc}"[:400])
            raise
        registro.marca(ESTADO_APLICADO)
    return instalados
