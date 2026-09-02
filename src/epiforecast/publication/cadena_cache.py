"""P0.10: la cadena de caché del EpiBot, comprobada contra el HEAD del dashboard.

Tres niveles, y cada uno invalida sólo el siguiente: `knowledge.json` y `zoom_series.json`
se piden con `?v=DATA_VERSION` desde `epibot/js/kb.js`; `kb.js` (y los demás módulos) se
importan desde `epibot/js/app.js` con su propio `?v=`; y `app.js` (y el CSS) se cargan desde
`epibot/index.html` con otro `?v=`. Subir sólo la versión de `app.js` no invalida ni `kb.js`
ni la URL versionada de los datos. Y hay una cuarta boca que **no** es un `?v=`: la raíz
`index.html` pide `epibot/knowledge.json` con `cache: 'no-store'`; es correcta y se exige
tal cual, para que nadie «arregle» lo que no está roto.

La regla es local a cada eslabón: si un archivo cambió respecto al HEAD que se sella, el
`?v=` con el que lo referencia su consumidor tiene que ser distinto del que tenía en ese
HEAD. Se compara contra `git show`, no contra la semilla: lo que importa es lo publicado.
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
EPIBOT_INDEX = "epibot/index.html"
RAIZ_INDEX = "index.html"
DATOS_VERSIONADOS = ("epibot/knowledge.json", "epibot/zoom_series.json")

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
    """Las rutas rastreadas en `head`. Falla cerrado: sin repositorio o sin commit no hay cadena.

    Antes, `git show` fallido se leía como «archivo ausente», y un HEAD inexistente o una
    ruta que no es repositorio hacían que la cadena «no aplicara»: un PASS por error.
    """
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


def revisa_cadena_cache(
    repo_dashboard: Path, head_dashboard: str, outputs_dashboard: Path, semilla: Any = None
) -> ResultadoCadena:
    """Exige que cada archivo cambiado del EpiBot lleve un `?v=` nuevo en su consumidor.

    Si el HEAD no tiene `epibot/js/kb.js`, el sitio no lleva EpiBot y la cadena no aplica.
    `semilla` se acepta por simetría con el sello, pero la referencia es el HEAD.
    """
    del semilla
    arbol = _arbol(repo_dashboard, head_dashboard)
    if KB_JS not in arbol:
        return ResultadoCadena(aplica=False, cambiados=(), problemas=())

    def blob(rel: str) -> bytes | None:
        return _blob(repo_dashboard, head_dashboard, rel, arbol)

    def cambio(rel: str) -> bool:
        antes = blob(rel)
        ahora = _lee(outputs_dashboard, rel)
        return ahora is not None and ahora != antes

    problemas: list[str] = []
    cambiados: list[str] = []

    # 1 · datos -> DATA_VERSION de kb.js
    datos_cambiados = [rel for rel in DATOS_VERSIONADOS if cambio(rel)]
    cambiados.extend(datos_cambiados)
    kb_antes = _RE_DATA_VERSION.search(_texto(blob(KB_JS)))
    kb_ahora = _RE_DATA_VERSION.search(_texto(_lee(outputs_dashboard, KB_JS)))
    if kb_ahora is None:
        problemas.append(f"{KB_JS} del candidato no declara DATA_VERSION")
    elif datos_cambiados and kb_antes is not None and kb_ahora.group(1) == kb_antes.group(1):
        problemas.append(
            f"{', '.join(datos_cambiados)} cambiaron y DATA_VERSION sigue en "
            f"'{kb_ahora.group(1)}' en {KB_JS}: el navegador serviría los datos viejos"
        )

    # 2 · módulos -> ?v= de sus imports en app.js
    imports_antes = dict(_RE_IMPORT.findall(_texto(blob(APP_JS))))
    imports_ahora = dict(_RE_IMPORT.findall(_texto(_lee(outputs_dashboard, APP_JS))))
    if KB_JS.rsplit("/", 1)[-1] not in imports_ahora:
        problemas.append(f"{APP_JS} del candidato no importa kb.js con ?v=")
    for modulo, version in imports_ahora.items():
        rel = f"epibot/js/{modulo}"
        if cambio(rel):
            cambiados.append(rel)
            if imports_antes.get(modulo) == version:
                problemas.append(f"{rel} cambió y {APP_JS} lo sigue importando con ?v={version}")

    # 3 · app.js y css -> ?v= en epibot/index.html
    recursos_antes = dict(_RE_RECURSO.findall(_texto(blob(EPIBOT_INDEX))))
    recursos_ahora = dict(_RE_RECURSO.findall(_texto(_lee(outputs_dashboard, EPIBOT_INDEX))))
    if "js/app.js" not in recursos_ahora:
        problemas.append(f"{EPIBOT_INDEX} del candidato no carga js/app.js con ?v=")
    for recurso, version in recursos_ahora.items():
        rel = f"epibot/{recurso}"
        if cambio(rel):
            cambiados.append(rel)
            if recursos_antes.get(recurso) == version:
                problemas.append(
                    f"{rel} cambió y {EPIBOT_INDEX} lo sigue cargando con ?v={version}"
                )

    # 4 · la cuarta boca: la raíz pide knowledge.json sin caché, y así tiene que seguir
    raiz_antes = _texto(blob(RAIZ_INDEX))
    raiz_ahora = _texto(_lee(outputs_dashboard, RAIZ_INDEX))
    if _RE_NO_STORE.search(raiz_antes) and not _RE_NO_STORE.search(raiz_ahora):
        problemas.append(
            f"{RAIZ_INDEX} dejó de pedir epibot/knowledge.json con cache: 'no-store'; esa "
            "boca no lleva ?v= y no se «arregla»"
        )

    if problemas:
        raise StagingError("cadena de caché rota:\n  - " + "\n  - ".join(problemas))
    return ResultadoCadena(aplica=True, cambiados=tuple(sorted(set(cambiados))), problemas=())


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


def _escribe_texto(outputs: Path, rel: str, texto: str) -> None:
    ruta = outputs / rel
    if ruta.is_symlink() or not ruta.is_file():
        raise StagingError(f"{rel} del candidato no es un archivo regular")
    ruta.write_text(texto, encoding="utf-8")


def sube_cadena_cache(
    repo_dashboard: Path,
    head_dashboard: str,
    outputs_dashboard: Path,
    *,
    data_version: str | None = None,
) -> ResultadoSubida:
    """Sube cada `?v=` (y DATA_VERSION) que la cadena exija, SÓLO en el candidato.

    Eslabón a eslabón y en orden, porque subir uno cambia el archivo que el siguiente
    referencia: datos cambiados -> DATA_VERSION en `kb.js`; módulos cambiados (kb.js
    incluido) -> su `?v=` en `app.js`; `app.js`/CSS cambiados -> su `?v=` en
    `epibot/index.html`. Sólo se toca lo que sigue con la versión del HEAD; lo que ya subió
    quien generó no se vuelve a subir. Al final se exige la cadena entera. Versiones no
    numéricas no se inventan: se abortan.
    """
    arbol = _arbol(repo_dashboard, head_dashboard)
    if KB_JS not in arbol:
        return ResultadoSubida((), ResultadoCadena(aplica=False, cambiados=(), problemas=()))

    def blob(rel: str) -> bytes | None:
        return _blob(repo_dashboard, head_dashboard, rel, arbol)

    def cambio(rel: str) -> bool:
        ahora = _lee(outputs_dashboard, rel)
        return ahora is not None and ahora != blob(rel)

    cambios: list[str] = []

    # 1 · datos -> DATA_VERSION
    if any(cambio(rel) for rel in DATOS_VERSIONADOS):
        kb_texto = _texto(_lee(outputs_dashboard, KB_JS))
        ahora = _RE_DATA_VERSION.search(kb_texto)
        antes = _RE_DATA_VERSION.search(_texto(blob(KB_JS)))
        if ahora is None:
            raise StagingError(f"{KB_JS} del candidato no declara DATA_VERSION")
        if antes is not None and ahora.group(1) == antes.group(1):
            nueva = data_version or _incrementa(ahora.group(1), "DATA_VERSION")
            if nueva == ahora.group(1):
                raise StagingError(f"la DATA_VERSION nueva es la misma que la del HEAD: {nueva!r}")
            inicio, fin = ahora.span(1)
            _escribe_texto(outputs_dashboard, KB_JS, kb_texto[:inicio] + nueva + kb_texto[fin:])
            cambios.append(f"{KB_JS}: DATA_VERSION {ahora.group(1)} -> {nueva}")

    # 2 · módulos -> imports de app.js
    app_texto = _texto(_lee(outputs_dashboard, APP_JS))
    imports_antes = dict(_RE_IMPORT.findall(_texto(blob(APP_JS))))
    for modulo, version in _RE_IMPORT.findall(app_texto):
        rel = f"epibot/js/{modulo}"
        if cambio(rel) and imports_antes.get(modulo) == version:
            nueva = _incrementa(version, rel)
            patron = re.compile(
                rf"(from\s+['\"]\./{re.escape(modulo)}\?v=){re.escape(version)}(['\"])"
            )
            app_texto, n = patron.subn(rf"\g<1>{nueva}\g<2>", app_texto, count=1)
            if n != 1:
                raise StagingError(f"no se pudo subir el import de {modulo} en {APP_JS}")
            cambios.append(f"{APP_JS}: {modulo}?v={version} -> {nueva}")
    if any(c.startswith(APP_JS) for c in cambios):
        _escribe_texto(outputs_dashboard, APP_JS, app_texto)

    # 3 · app.js y css -> epibot/index.html
    index_texto = _texto(_lee(outputs_dashboard, EPIBOT_INDEX))
    recursos_antes = dict(_RE_RECURSO.findall(_texto(blob(EPIBOT_INDEX))))
    for recurso, version in _RE_RECURSO.findall(index_texto):
        rel = f"epibot/{recurso}"
        if cambio(rel) and recursos_antes.get(recurso) == version:
            nueva = _incrementa(version, rel)
            patron = re.compile(
                rf"((?:src|href)=[\"']{re.escape(recurso)}\?v=){re.escape(version)}([\"'])"
            )
            index_texto, n = patron.subn(rf"\g<1>{nueva}\g<2>", index_texto, count=1)
            if n != 1:
                raise StagingError(f"no se pudo subir {recurso} en {EPIBOT_INDEX}")
            cambios.append(f"{EPIBOT_INDEX}: {recurso}?v={version} -> {nueva}")
    if any(c.startswith(EPIBOT_INDEX) for c in cambios):
        _escribe_texto(outputs_dashboard, EPIBOT_INDEX, index_texto)

    cadena = revisa_cadena_cache(repo_dashboard, head_dashboard, outputs_dashboard)
    return ResultadoSubida(tuple(cambios), cadena)
