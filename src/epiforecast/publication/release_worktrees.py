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
import shutil
import stat
import subprocess
from typing import Any

from epiforecast.publication.weekly_staging import (
    MODO_APLICABLE,
    PREFIJOS_SELLABLES,
    RUTA_POLITICA,
    EvidenciaGates,
    Manifiesto,
    PoliticaCenso,
    StagingError,
    _escribe_atomico,
    _escribe_exclusivo,
    _instala,
    _relativos,
    _sin_duplicados,
    calcula_composicion,
    sha256_de,
    valida_gates,
    valida_ruta_sellable,
    verifica,
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


def _digest_registro(cuerpo: dict[str, Any]) -> str:
    """Digest del registro SIN su propio campo `sha256`, en forma canónica."""
    sin_digest = {k: v for k, v in cuerpo.items() if k != "sha256"}
    return hashlib.sha256(
        json.dumps(sin_digest, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


@dataclass
class RegistroDestinos:
    """`run_id -> par de worktrees`, con estado. Vive fuera de los worktrees.

    Un solo archivo con el digest embebido, escrito con un único `replace` atómico. Con
    registro y sidecar aparte había dos escrituras: una interrupción entre ambas dejaba un
    par que ni `apply` ni `discard` podían releer, es decir, un residuo sin salida.
    """

    raiz: Path
    run_id: str
    manifiesto_sha256: str
    estado: str
    motivo: str
    creado: str
    destinos: dict[str, Destino]

    CLAVES = (
        "esquema",
        "run_id",
        "manifiesto_sha256",
        "estado",
        "motivo",
        "creado",
        "destinos",
        "sha256",
    )

    def como_dict(self) -> dict[str, Any]:
        cuerpo: dict[str, Any] = {
            "esquema": ESQUEMA_REGISTRO,
            "run_id": self.run_id,
            "manifiesto_sha256": self.manifiesto_sha256,
            "estado": self.estado,
            "motivo": self.motivo,
            "creado": self.creado,
            "destinos": {esp: d.como_dict() for esp, d in sorted(self.destinos.items())},
        }
        cuerpo["sha256"] = _digest_registro(cuerpo)
        return cuerpo

    def escribe(self) -> None:
        crudo = json.dumps(self.como_dict(), indent=2, ensure_ascii=False, sort_keys=True).encode()
        # Temporal con el pid: un `.part` rancio de una corrida muerta no bloquea `marca()`
        # (que además corre dentro del `except` de `aplica` y enmascararía el error real).
        _escribe_atomico(self.raiz / ARCHIVO_REGISTRO, crudo + b"\n", f".{os.getpid()}.part")

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
        try:
            crudo = json.loads(ruta.read_bytes(), object_pairs_hook=_sin_duplicados)
        except json.JSONDecodeError as exc:
            raise StagingError(f"registro de destinos ilegible: {exc}") from exc
        if not isinstance(crudo, dict) or set(crudo) != set(RegistroDestinos.CLAVES):
            raise StagingError("registro de destinos malformado")
        if crudo["esquema"] != ESQUEMA_REGISTRO:
            raise StagingError(f"registro de destinos de otro esquema: {crudo['esquema']!r}")
        if crudo["sha256"] != _digest_registro(crudo):
            raise StagingError(
                f"el registro de destinos no coincide con su digest embebido ({ARCHIVO_REGISTRO}): "
                "fue editado o se corrompió"
            )
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
    # La política que aprobó el sello tiene que ser la que ESTE repositorio canónico lleva
    # en ese HEAD. Un sello producido contra otro repositorio con el mismo commit es
    # imposible salvo colisión; contra otra política, no: se comprueba el digest.
    blob = subprocess.run(
        ["git", "-C", str(raices_repo["backend"]), "show", f"{heads['backend']}:{RUTA_POLITICA}"],
        capture_output=True,
    )
    if blob.returncode != 0:
        raise StagingError(
            f"el HEAD sellado {heads['backend'][:12]} no contiene la política {RUTA_POLITICA}"
        )
    if hashlib.sha256(blob.stdout).hexdigest() != manifiesto.politica.get("sha256"):
        raise StagingError(
            "la política del sello no es la que el repositorio canónico lleva en el HEAD "
            "sellado; este par no se crea"
        )
    # Y la evidencia de gates que viaja en la corrida tiene que aprobar, contra ESA
    # política parseada de ESE blob, la composición sellada: el conjunto de gates, sus
    # argv, el PASS y la composición. Sin esto, prepare sólo comprobaba digests de archivo.
    valida_gates(
        EvidenciaGates.lee(run_dir), PoliticaCenso.desde_bytes(blob.stdout), manifiesto.composicion
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
    creados: list[tuple[Path, Path]] = []
    try:
        for espacio in sorted(raices_repo):
            repo = raices_repo[espacio]
            ruta = raiz_real / espacio
            _git(repo, "worktree", "add", "--detach", str(ruta), heads[espacio])
            creados.append((repo, ruta))
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
    except BaseException:
        # Rollback: un par a medias —un worktree creado y el otro no, o sin registro— es
        # un residuo que ni `apply` ni `discard` podrían releer. Se retira todo lo creado.
        for repo, ruta in reversed(creados):
            _retira_worktree(repo, ruta)
        shutil.rmtree(raiz_real, ignore_errors=True)
        raise
    return registro


def _retira_worktree(repo: Path, ruta: Path) -> None:
    """`git worktree remove --force` si existe, y `prune` siempre. Sin excepción hacia arriba."""
    if ruta.is_dir() and not ruta.is_symlink():
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "remove", "--force", str(ruta)],
            capture_output=True,
        )
    subprocess.run(["git", "-C", str(repo), "worktree", "prune"], capture_output=True)


def _exige_worktree_del_repo(destino: Destino, raiz_real: Path) -> Path | None:
    """Un destino sólo se retira si es EXACTAMENTE el worktree que este registro creó.

    Devuelve la ruta real a retirar, o None si ya no existe (sólo queda `prune`). Se
    niega a pasar `--force` sobre cualquier otra cosa: un directorio que no cuelga del
    repositorio registrado, que no está donde el registro dice o que es un enlace.
    """
    ruta = Path(destino.ruta)
    if ruta != raiz_real / destino.espacio:
        raise StagingError(
            f"el destino {destino.espacio} no está bajo la raíz del registro "
            f"({ruta} frente a {raiz_real / destino.espacio}); no se retira"
        )
    if ruta.is_symlink():
        raise StagingError(f"el destino {destino.espacio} es un enlace simbólico; no se retira")
    repo = _raiz_de_repo(Path(destino.repo))
    if not ruta.exists():
        return None
    real = ruta.resolve()
    if real != ruta:
        raise StagingError(f"el destino {destino.espacio} no está en su ruta real; no se retira")
    if real == repo or (repo / ".git") in real.parents:
        raise StagingError(
            f"el destino {destino.espacio} es el worktree canónico o vive en su .git; no se retira"
        )
    bloque = _worktrees_registrados(repo).get(real)
    if bloque is None:
        raise StagingError(
            f"el destino {destino.espacio} no figura en `git worktree list` de {repo}; "
            "no se retira con --force lo que git no reconoce como suyo"
        )
    comun = Path(_git(real, "rev-parse", "--git-common-dir").strip())
    if not comun.is_absolute():
        comun = real / comun
    if comun.resolve().parent != repo:
        raise StagingError(
            f"el destino {destino.espacio} no cuelga del repositorio registrado {repo}"
        )
    return real


def descarta_worktrees(raiz: Path, ruta_manifiesto: Path) -> RegistroDestinos:
    """Retira el par y lo marca descartado. Sólo el par de ESE manifiesto, y sólo sus worktrees.

    Ligaduras, todas exigidas: el manifiesto es el que el registro cita (`run_id` y digest);
    el registro está íntegro; nadie tiene el lock (un apply en marcha no se descarta por
    debajo); y cada destino es exactamente el worktree que `prepare` creó bajo la raíz,
    reconocido por git como worktree del repositorio registrado. Un par ya descartado no
    se descarta dos veces. El registro se conserva para dejar constancia de por qué.
    """
    if ruta_manifiesto.is_symlink() or not ruta_manifiesto.is_file():
        raise StagingError(f"no existe el manifiesto: {ruta_manifiesto}")
    manifiesto = Manifiesto.lee(ruta_manifiesto)
    registro = RegistroDestinos.lee(raiz)
    if registro.run_id != manifiesto.run_id:
        raise StagingError(
            f"el par de destinos es de otra corrida ({registro.run_id[:12]}… frente a "
            f"{manifiesto.run_id[:12]}…); no se descarta"
        )
    if registro.manifiesto_sha256 != sha256_de(ruta_manifiesto):
        raise StagingError("el par de destinos se preparó para otro manifiesto; no se descarta")
    with lock_exclusivo(raiz):
        registro = RegistroDestinos.lee(raiz)
        if registro.run_id != manifiesto.run_id or registro.manifiesto_sha256 != sha256_de(
            ruta_manifiesto
        ):
            raise StagingError(
                "el registro cambió de corrida o de manifiesto bajo el lock; no se descarta"
            )
        if registro.estado == ESTADO_DESCARTADO:
            raise StagingError(f"el par {registro.run_id[:12]}… ya está descartado")
        raiz_real = raiz.resolve()
        # Primero se comprueba TODO; después se retira. Un fallo a mitad no deja un par
        # medio retirado con el registro diciendo otra cosa.
        a_retirar = {
            espacio: _exige_worktree_del_repo(destino, raiz_real)
            for espacio, destino in sorted(registro.destinos.items())
        }
        motivo_previo = registro.motivo
        for espacio, real in a_retirar.items():
            repo = Path(registro.destinos[espacio].repo)
            if real is not None:
                _git(repo, "worktree", "remove", "--force", str(real))
            _git(repo, "worktree", "prune")
        registro.marca(ESTADO_DESCARTADO, motivo_previo)
    return registro


def composicion_del_par(destinos: dict[str, Path], politica: PoliticaCenso) -> str:
    """Digest canónico del árbol administrado tal como quedó en un par de worktrees."""
    arbol: dict[str, str] = {}
    prefijos = [
        p
        for p in politica.prefijos_administrados
        if not any(o != p and p.startswith(o) for o in politica.prefijos_administrados)
    ]
    for prefijo in prefijos:
        espacio, _, subruta = prefijo.rstrip("/").partition("/")
        raiz = destinos[espacio]
        base = raiz / subruta if subruta else raiz
        if not base.is_dir():
            continue
        for rel in _relativos(base):
            partes = rel.parts
            # El worktree lleva un archivo `.git` en su raíz; no es del árbol administrado.
            if partes[0] == ".git":
                continue
            logico = "/".join([espacio, *([subruta] if subruta else []), *partes])
            arbol[logico] = sha256_de(base / rel)
    digest, _ = calcula_composicion({}, arbol, ())
    return digest


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


def _exige_composicion(
    manifiesto: Manifiesto, destinos: dict[str, Path], head_backend: str
) -> None:
    politica = PoliticaCenso.del_head(destinos["backend"], head_backend)
    aplicada = composicion_del_par(destinos, politica)
    if aplicada != manifiesto.composicion:
        raise StagingError(
            f"composición aplicada {aplicada[:12]}… ≠ sellada "
            f"{manifiesto.composicion[:12]}…; el par no es el árbol que aprobaron los gates"
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
        # Se re-liga tras releer: lo comprobado antes del lock pudo cambiar en medio.
        if registro.run_id != manifiesto.run_id or registro.manifiesto_sha256 != sha256_de(
            manifiesto_disco
        ):
            raise StagingError("el registro cambió de corrida o de manifiesto bajo el lock")
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
            # Repetir un apply completado es un no-op VERIFICADO, no una reinstalación: cada
            # destino sigue siendo el worktree, lo declarado está, y el árbol administrado
            # entero sigue siendo la composición sellada (un archivo colado la cambia).
            try:
                for espacio, destino in registro.destinos.items():
                    _verifica_destino(destino, heads[espacio], run_dir, limpio=False)
                _exige_instalado(manifiesto, destinos)
                _exige_composicion(manifiesto, destinos, heads["backend"])
            except BaseException as exc:
                registro.marca(ESTADO_INVALIDO, f"{type(exc).__name__}: {exc}"[:400])
                raise
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
            # La prueba fuerte, ANTES de declarar el par aplicado: el árbol administrado del
            # par, recompuesto desde disco con la política del HEAD sellado (leída del
            # worktree del backend, que la lleva tal cual), es la composición que los gates
            # midieron. «Todo lo declarado está» no dice que el par sea el árbol probado.
            _exige_composicion(manifiesto, destinos, heads["backend"])
        except BaseException as exc:
            registro.marca(ESTADO_INVALIDO, f"{type(exc).__name__}: {exc}"[:400])
            raise
        registro.marca(ESTADO_APLICADO)
    return instalados
