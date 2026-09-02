"""P0.10: la cadena de caché del EpiBot, comprobada contra el HEAD del dashboard.

Cada archivo del EpiBot que cambia tiene que llevar un `?v=` nuevo en TODOS los que lo
referencian: `knowledge.json` y `zoom_series.json` se piden con `?v=DATA_VERSION` desde
`epibot/js/kb.js`; cada módulo de `epibot/js/` se importa con su propio `?v=` desde los
módulos que lo usan (`app.js` importa `kb.js`, pero `kb.js` importa `entities.js`, y
`timelapse.js` importa `mexico-map.js`: el consumidor no es sólo `app.js`); y `app.js` y el
CSS se cargan desde `epibot/index.html` con otro `?v=`. Subir sólo la versión de `app.js` no
invalida ni `kb.js` ni la URL versionada de los datos. Y hay una cuarta boca que **no** es
un `?v=`: la raíz `index.html` pide `epibot/knowledge.json` con `cache: 'no-store'`; es
correcta y se exige tal cual, para que nadie «arregle» lo que no está roto.

La regla es local a cada eslabón: si un archivo cambió respecto al HEAD que se sella, el
`?v=` con el que lo referencia cada consumidor tiene que ser distinto del que tenía en ese
HEAD. Se compara contra `git show`, no contra la semilla: lo que importa es lo publicado.
Falla cerrado: sin repositorio, sin commit, o con un candidato que lleva EpiBot cuando el
HEAD no (destino mal ruteado), es error, no «no aplica».
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Any

from epiforecast.publication.errores import StagingError

KB_JS = "epibot/js/kb.js"
APP_JS = "epibot/js/app.js"
DIR_MODULOS = "epibot/js/"
EPIBOT_INDEX = "epibot/index.html"
RAIZ_INDEX = "index.html"
DATOS_VERSIONADOS = ("epibot/knowledge.json", "epibot/zoom_series.json")
_PASADAS_MAX = 12  # la cadena de imports es un DAG corto; más pasadas es un ciclo

_RE_DATA_VERSION = re.compile(r"DATA_VERSION\s*=\s*['\"]([^'\"]+)['\"]")
_RE_IMPORT = re.compile(r"from\s+['\"]\./([A-Za-z0-9_.\-]+\.js)\?v=([^'\"]+)['\"]")
_RE_RECURSO = re.compile(r"(?:src|href)=[\"']([^\"'?]+\.(?:js|css))\?v=([^\"']+)[\"']")
_RE_NO_STORE = re.compile(
    r"fetch\(\s*['\"]epibot/knowledge\.json['\"]\s*,\s*\{\s*cache\s*:\s*['\"]no-store['\"]"
)


@dataclass(frozen=True)
class ResultadoCadena:
    aplica: bool
    cambiados: tuple[str, ...]
    problemas: tuple[str, ...]


def _arbol(repo: Path, head: str) -> frozenset[str]:
    """Las rutas rastreadas en `head`. Falla cerrado: sin repositorio o sin commit no hay cadena."""
    if repo.is_symlink() or not repo.is_dir():
        raise StagingError(f"el repositorio del dashboard no existe (o es un enlace): {repo}")
    existe = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{head}^{{commit}}"], capture_output=True
    )
    if existe.returncode != 0:
        raise StagingError(
            f"el HEAD del dashboard {head[:12]} no existe en {repo}: "
            f"{existe.stderr.decode(errors='replace').strip()}"
        )
    listado = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "core.quotepath=false",
            "ls-tree",
            "-r",
            "--name-only",
            head,
        ],
        capture_output=True,
    )
    if listado.returncode != 0:
        raise StagingError(
            f"no se pudo listar el árbol de {head[:12]} en {repo}: "
            f"{listado.stderr.decode(errors='replace').strip()}"
        )
    return frozenset(listado.stdout.decode("utf-8").splitlines())


def _blob(repo: Path, head: str, rel: str, arbol: frozenset[str]) -> bytes | None:
    """Bytes de `rel` en `head`, o None SÓLO si el árbol no lo rastrea."""
    if rel not in arbol:
        return None
    salida = subprocess.run(["git", "-C", str(repo), "show", f"{head}:{rel}"], capture_output=True)
    if salida.returncode != 0:
        raise StagingError(
            f"git show {head[:12]}:{rel} falló: {salida.stderr.decode(errors='replace').strip()}"
        )
    return salida.stdout


def _lee(outputs: Path, rel: str) -> bytes | None:
    ruta = outputs / rel
    if ruta.is_symlink() or not ruta.is_file():
        return None
    return ruta.read_bytes()


def _texto(crudo: bytes | None) -> str:
    return crudo.decode("utf-8", errors="replace") if crudo is not None else ""


def _modulos(outputs: Path, arbol: frozenset[str]) -> list[str]:
    """Todos los módulos JS del EpiBot, en el candidato o en el HEAD: cada uno puede importar."""
    carpeta = outputs / DIR_MODULOS
    presentes = (
        {f"{DIR_MODULOS}{p.name}" for p in carpeta.iterdir() if p.is_file() and p.suffix == ".js"}
        if carpeta.is_dir() and not carpeta.is_symlink()
        else set()
    )
    rastreados = {rel for rel in arbol if rel.startswith(DIR_MODULOS) and rel.endswith(".js")}
    return sorted(presentes | rastreados)


class _Contexto:
    """HEAD, candidato y —al subir— una capa en memoria con lo que se escribiría.

    `sube_cadena_cache` planifica sobre la capa y sólo al final vuelca al disco: si algo
    aborta a mitad (una versión no numérica que sólo aparece en el tercer eslabón), el
    candidato queda intacto en vez de medio subido.
    """

    def __init__(self, repo: Path, head: str, outputs: Path) -> None:
        self.repo, self.head, self.outputs = repo, head, outputs
        self.arbol = _arbol(repo, head)
        self.capa: dict[str, bytes] = {}

    def blob(self, rel: str) -> bytes | None:
        return _blob(self.repo, self.head, rel, self.arbol)

    def ahora(self, rel: str) -> bytes | None:
        if rel in self.capa:
            return self.capa[rel]
        return _lee(self.outputs, rel)

    def escribe(self, rel: str, texto: str) -> None:
        ruta = self.outputs / rel
        if ruta.is_symlink() or not ruta.is_file():
            raise StagingError(f"{rel} del candidato no es un archivo regular")
        self.capa[rel] = texto.encode("utf-8")

    def vuelca(self) -> None:
        for rel, crudo in self.capa.items():
            (self.outputs / rel).write_bytes(crudo)

    def cambio(self, rel: str) -> bool:
        ahora = self.ahora(rel)
        return ahora is not None and ahora != self.blob(rel)

    def aplica(self) -> bool:
        """El HEAD lleva EpiBot. Un candidato con EpiBot y un HEAD sin él es otro repositorio."""
        if KB_JS in self.arbol:
            return True
        if self.ahora(KB_JS) is not None:
            raise StagingError(
                f"el candidato lleva {KB_JS} y el HEAD del dashboard {self.head[:12]} no lo "
                "rastrea; el destino del dashboard no es el repositorio del candidato"
            )
        return False


def revisa_cadena_cache(
    repo_dashboard: Path, head_dashboard: str, outputs_dashboard: Path, semilla: Any = None
) -> ResultadoCadena:
    """Exige que cada archivo cambiado del EpiBot lleve un `?v=` nuevo en cada consumidor.

    `semilla` se acepta por simetría con el sello, pero la referencia es el HEAD.
    """
    del semilla
    ctx = _Contexto(repo_dashboard, head_dashboard, outputs_dashboard)
    if not ctx.aplica():
        return ResultadoCadena(aplica=False, cambiados=(), problemas=())

    problemas: list[str] = []
    cambiados: set[str] = set()

    # 1 · datos -> DATA_VERSION de kb.js
    datos_cambiados = [rel for rel in DATOS_VERSIONADOS if ctx.cambio(rel)]
    cambiados.update(datos_cambiados)
    kb_antes = _RE_DATA_VERSION.search(_texto(ctx.blob(KB_JS)))
    kb_ahora = _RE_DATA_VERSION.search(_texto(ctx.ahora(KB_JS)))
    if kb_ahora is None:
        problemas.append(f"{KB_JS} del candidato no declara DATA_VERSION")
    elif datos_cambiados and kb_antes is not None and kb_ahora.group(1) == kb_antes.group(1):
        problemas.append(
            f"{', '.join(datos_cambiados)} cambiaron y DATA_VERSION sigue en "
            f"'{kb_ahora.group(1)}' en {KB_JS}: el navegador serviría los datos viejos"
        )

    # 2 · módulos -> ?v= en CADA módulo que los importa (app.js, kb.js, timelapse.js, ...)
    if KB_JS.rsplit("/", 1)[-1] not in dict(_RE_IMPORT.findall(_texto(ctx.ahora(APP_JS)))):
        problemas.append(f"{APP_JS} del candidato no importa kb.js con ?v=")
    for importador in _modulos(outputs_dashboard, ctx.arbol):
        if ctx.ahora(importador) is None:
            continue
        imports_antes = dict(_RE_IMPORT.findall(_texto(ctx.blob(importador))))
        for modulo, version in _RE_IMPORT.findall(_texto(ctx.ahora(importador))):
            rel = f"{DIR_MODULOS}{modulo}"
            if ctx.cambio(rel):
                cambiados.add(rel)
                if imports_antes.get(modulo) == version:
                    problemas.append(
                        f"{rel} cambió y {importador} lo sigue importando con ?v={version}"
                    )

    # 3 · app.js y css -> ?v= en epibot/index.html
    recursos_antes = dict(_RE_RECURSO.findall(_texto(ctx.blob(EPIBOT_INDEX))))
    recursos_ahora = dict(_RE_RECURSO.findall(_texto(ctx.ahora(EPIBOT_INDEX))))
    if "js/app.js" not in recursos_ahora:
        problemas.append(f"{EPIBOT_INDEX} del candidato no carga js/app.js con ?v=")
    for recurso, version in recursos_ahora.items():
        rel = f"epibot/{recurso}"
        if ctx.cambio(rel):
            cambiados.add(rel)
            if recursos_antes.get(recurso) == version:
                problemas.append(
                    f"{rel} cambió y {EPIBOT_INDEX} lo sigue cargando con ?v={version}"
                )

    # 4 · la cuarta boca: la raíz pide knowledge.json sin caché, y así tiene que seguir
    raiz_antes = _texto(ctx.blob(RAIZ_INDEX))
    raiz_ahora = _texto(ctx.ahora(RAIZ_INDEX))
    if _RE_NO_STORE.search(raiz_antes) and not _RE_NO_STORE.search(raiz_ahora):
        problemas.append(
            f"{RAIZ_INDEX} dejó de pedir epibot/knowledge.json con cache: 'no-store'; esa "
            "boca no lleva ?v= y no se «arregla»"
        )

    if problemas:
        raise StagingError("cadena de caché rota:\n  - " + "\n  - ".join(problemas))
    return ResultadoCadena(aplica=True, cambiados=tuple(sorted(cambiados)), problemas=())


# ── subir la cadena: el paso que el orquestador no tenía ─────────────────────


@dataclass(frozen=True)
class ResultadoSubida:
    cambios: tuple[str, ...]
    cadena: ResultadoCadena


def _incrementa(version: str, que: str) -> str:
    if not version.isdigit():
        raise StagingError(
            f"la versión de caché de {que} no es numérica ({version!r}); súbela a mano"
        )
    return str(int(version) + 1)


def _sube_imports(ctx: _Contexto, importador: str) -> list[str]:
    """Sube en `importador` el `?v=` de cada módulo cambiado que aún lleve la versión del HEAD."""
    texto = _texto(ctx.ahora(importador))
    imports_antes = dict(_RE_IMPORT.findall(_texto(ctx.blob(importador))))
    cambios: list[str] = []
    for modulo, version in _RE_IMPORT.findall(texto):
        rel = f"{DIR_MODULOS}{modulo}"
        if ctx.cambio(rel) and imports_antes.get(modulo) == version:
            nueva = _incrementa(version, rel)
            patron = re.compile(
                rf"(from\s+['\"]\./{re.escape(modulo)}\?v=){re.escape(version)}(['\"])"
            )
            texto, n = patron.subn(rf"\g<1>{nueva}\g<2>", texto, count=1)
            if n != 1:
                raise StagingError(f"no se pudo subir el import de {modulo} en {importador}")
            cambios.append(f"{importador}: {modulo}?v={version} -> {nueva}")
    if cambios:
        ctx.escribe(importador, texto)
    return cambios


def sube_cadena_cache(
    repo_dashboard: Path,
    head_dashboard: str,
    outputs_dashboard: Path,
    *,
    data_version: str | None = None,
) -> ResultadoSubida:
    """Sube cada `?v=` (y DATA_VERSION) que la cadena exija, SÓLO en el candidato.

    Eslabón a eslabón y hasta el punto fijo, porque subir un import cambia al importador y
    ese cambio obliga a subirlo en quien lo importe a él: datos cambiados -> DATA_VERSION en
    `kb.js`; módulos cambiados -> su `?v=` en cada módulo que los importe; `app.js`/CSS
    cambiados -> su `?v=` en `epibot/index.html`. Sólo se toca lo que sigue con la versión
    del HEAD; lo que ya subió quien generó no se vuelve a subir. Al final se exige la cadena
    entera. Versiones no numéricas no se inventan: el plan se calcula en memoria y aborta
    sin escribir nada.
    """
    ctx = _Contexto(repo_dashboard, head_dashboard, outputs_dashboard)
    if not ctx.aplica():
        return ResultadoSubida((), ResultadoCadena(aplica=False, cambiados=(), problemas=()))
    cambios: list[str] = []

    # 1 · datos -> DATA_VERSION
    if any(ctx.cambio(rel) for rel in DATOS_VERSIONADOS):
        kb_texto = _texto(ctx.ahora(KB_JS))
        ahora = _RE_DATA_VERSION.search(kb_texto)
        antes = _RE_DATA_VERSION.search(_texto(ctx.blob(KB_JS)))
        if ahora is None:
            raise StagingError(f"{KB_JS} del candidato no declara DATA_VERSION")
        if antes is not None and ahora.group(1) == antes.group(1):
            nueva = data_version or _incrementa(ahora.group(1), "DATA_VERSION")
            if nueva == ahora.group(1):
                raise StagingError(f"la DATA_VERSION nueva es la misma que la del HEAD: {nueva!r}")
            inicio, fin = ahora.span(1)
            ctx.escribe(KB_JS, kb_texto[:inicio] + nueva + kb_texto[fin:])
            cambios.append(f"{KB_JS}: DATA_VERSION {ahora.group(1)} -> {nueva}")

    # 2 · módulos -> imports, hasta el punto fijo
    for _ in range(_PASADAS_MAX):
        nuevos: list[str] = []
        for importador in _modulos(outputs_dashboard, ctx.arbol):
            if ctx.ahora(importador) is not None:
                nuevos.extend(_sube_imports(ctx, importador))
        cambios.extend(nuevos)
        if not nuevos:
            break
    else:
        raise StagingError("la cadena de imports del EpiBot no converge; ¿un ciclo de imports?")

    # 3 · app.js y css -> epibot/index.html
    index_texto = _texto(ctx.ahora(EPIBOT_INDEX))
    recursos_antes = dict(_RE_RECURSO.findall(_texto(ctx.blob(EPIBOT_INDEX))))
    for recurso, version in _RE_RECURSO.findall(index_texto):
        rel = f"epibot/{recurso}"
        if ctx.cambio(rel) and recursos_antes.get(recurso) == version:
            nueva = _incrementa(version, rel)
            patron = re.compile(
                rf"((?:src|href)=[\"']{re.escape(recurso)}\?v=){re.escape(version)}([\"'])"
            )
            index_texto, n = patron.subn(rf"\g<1>{nueva}\g<2>", index_texto, count=1)
            if n != 1:
                raise StagingError(f"no se pudo subir {recurso} en {EPIBOT_INDEX}")
            cambios.append(f"{EPIBOT_INDEX}: {recurso}?v={version} -> {nueva}")
    if any(c.startswith(EPIBOT_INDEX) for c in cambios):
        ctx.escribe(EPIBOT_INDEX, index_texto)

    # Nada se ha escrito todavía: si llegamos aquí, el plan entero es válido.
    ctx.vuelca()
    cadena = revisa_cadena_cache(repo_dashboard, head_dashboard, outputs_dashboard)
    return ResultadoSubida(tuple(cambios), cadena)
