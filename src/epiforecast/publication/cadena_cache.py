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


def _blob(repo: Path, head: str, rel: str) -> bytes | None:
    salida = subprocess.run(["git", "-C", str(repo), "show", f"{head}:{rel}"], capture_output=True)
    return salida.stdout if salida.returncode == 0 else None


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
    if _blob(repo_dashboard, head_dashboard, KB_JS) is None:
        return ResultadoCadena(aplica=False, cambiados=(), problemas=())

    def cambio(rel: str) -> bool:
        antes = _blob(repo_dashboard, head_dashboard, rel)
        ahora = _lee(outputs_dashboard, rel)
        return ahora is not None and ahora != antes

    problemas: list[str] = []
    cambiados: list[str] = []

    # 1 · datos -> DATA_VERSION de kb.js
    datos_cambiados = [rel for rel in DATOS_VERSIONADOS if cambio(rel)]
    cambiados.extend(datos_cambiados)
    kb_antes = _RE_DATA_VERSION.search(_texto(_blob(repo_dashboard, head_dashboard, KB_JS)))
    kb_ahora = _RE_DATA_VERSION.search(_texto(_lee(outputs_dashboard, KB_JS)))
    if kb_ahora is None:
        problemas.append(f"{KB_JS} del candidato no declara DATA_VERSION")
    elif datos_cambiados and kb_antes is not None and kb_ahora.group(1) == kb_antes.group(1):
        problemas.append(
            f"{', '.join(datos_cambiados)} cambiaron y DATA_VERSION sigue en "
            f"'{kb_ahora.group(1)}' en {KB_JS}: el navegador serviría los datos viejos"
        )

    # 2 · módulos -> ?v= de sus imports en app.js
    imports_antes = dict(_RE_IMPORT.findall(_texto(_blob(repo_dashboard, head_dashboard, APP_JS))))
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
    recursos_antes = dict(
        _RE_RECURSO.findall(_texto(_blob(repo_dashboard, head_dashboard, EPIBOT_INDEX)))
    )
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
    raiz_antes = _texto(_blob(repo_dashboard, head_dashboard, RAIZ_INDEX))
    raiz_ahora = _texto(_lee(outputs_dashboard, RAIZ_INDEX))
    if _RE_NO_STORE.search(raiz_antes) and not _RE_NO_STORE.search(raiz_ahora):
        problemas.append(
            f"{RAIZ_INDEX} dejó de pedir epibot/knowledge.json con cache: 'no-store'; esa "
            "boca no lleva ?v= y no se «arregla»"
        )

    if problemas:
        raise StagingError("cadena de caché rota:\n  - " + "\n  - ".join(problemas))
    return ResultadoCadena(aplica=True, cambiados=tuple(sorted(set(cambiados))), problemas=())
