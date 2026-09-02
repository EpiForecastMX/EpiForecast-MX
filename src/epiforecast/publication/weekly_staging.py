"""Sellado y aplicación del refresh semanal.

El refresh preparaba los artefactos escribiéndolos directamente en los repositorios
publicables y después decidía si publicarlos. Eso tenía dos consecuencias: el propio
modo en seco ensuciaba el árbol, de modo que la publicación posterior abortaba por su
culpa; y lo que se publicaba no era necesariamente lo que se había revisado, porque
entre una cosa y otra el pipeline volvía a ejecutarse.

Aquí la preparación produce un **staging sellado**: un directorio aparte con los
artefactos y un manifiesto que fija quién los generó, sobre qué entradas y con qué
digest cada uno. La aplicación no regenera nada; verifica el sello y copia exactamente
esos bytes. Si algo cambió entre el sellado y la aplicación —el HEAD de un repositorio,
un artefacto, un archivo que no estaba inventariado— se detiene.

No existe un escape general: no hay `--allow-dirty` que permita publicar algo distinto
de lo sellado. Un escape general convierte todas las comprobaciones anteriores en
decoración.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
from typing import Any

from epiforecast.publication.errores import StagingError

# v2 = el sello empieza a gobernar de verdad: rutas con gramática cerrada, sidecar de
# integridad y escrituras que no siguen enlaces. Las nueve corridas `weekly_staging/1` de
# `runs/_refresh/` quedan históricas y NO aplicables: no traen sidecar, y anunciarlo por
# la versión es justo lo que evita que un v1 se rechace por un motivo que no declara.
# v3 (P0.2): la entrada deja de ser un digest declarado. El sello lleva el inventario de
# las entradas hidratadas por allowlist, el consolidado base y candidato como copias
# inmutables bajo `inputs/` con sus digests, y los boletines con bytes verificados.
VERSION_GENERADOR = "weekly_staging/3"
ARCHIVO_ENTRADAS = "entradas.json"
DIR_INPUTS = "inputs"
ESQUEMA_HIDRATACION = "hidratacion/1"
RUTA_LISTA_ENTRADAS = "config/publication/entradas_semanales.json"

# Único espacio de nombres sellable. Toda ruta del inventario cuelga de uno de estos dos
# prefijos, que `aplica` traduce a la raíz del repositorio correspondiente.
PREFIJOS_SELLABLES: tuple[str, ...] = ("backend", "dashboard")

# Objetivos DVC que el refresh semanal puede versionar. El versionado global arrastraba
# artefactos de modelos de carriles sin autorizar; esta lista es la frontera.
TARGETS_DVC_PERMITIDOS: tuple[str, ...] = (
    "data/processed/dataset_boletin_epidemiologico.csv.dvc",
)


__all__ = ["StagingError"]


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def valida_ruta_sellable(rel: str) -> tuple[str, ...]:
    """Gramática cerrada de rutas del inventario. Devuelve sus componentes.

    Un manifiesto es un archivo de texto editable: sus claves gobiernan dónde escribe
    `aplica`, así que son entrada no confiable y se validan como tal. Sin esta gramática,
    `raiz.joinpath(*partes)` acepta lo que le den.

    Hoy una clave con `..` ya no prospera, pero por un motivo accidental: `verifica` exige
    igualdad exacta entre el inventario y los archivos presentes, y una clave así nunca
    aparece entre los presentes. Esa barrera es un efecto lateral del chequeo de
    completitud, no una defensa; si algún día se relaja, la puerta queda abierta. Los dos
    vectores que sí estaban abiertos —un padre del destino sustituido por enlace y un
    enlace dentro del propio staging— se comprobaron escribiendo fuera de la raíz.
    """
    if not rel:
        raise StagingError("ruta sellable vacía")
    if "\\" in rel:
        raise StagingError(f"ruta sellable con barra invertida ambigua: {rel!r}")
    if rel.startswith("/"):
        raise StagingError(f"ruta sellable absoluta: {rel!r}")
    partes = tuple(rel.split("/"))
    if any(parte in ("", ".", "..") for parte in partes):
        raise StagingError(f"ruta sellable con componente vacío, '.' o '..': {rel!r}")
    if any("\x00" in parte for parte in partes):
        raise StagingError(f"ruta sellable con byte nulo: {rel!r}")
    if ".git" in partes:
        # `aplica` escribe en worktrees: una clave bajo `.git` reescribiría el repositorio
        # (HEAD, index, hooks) con bytes «sellados». Nada administrado vive ahí.
        raise StagingError(f"ruta sellable dentro de .git: {rel!r}")
    if partes[0] not in PREFIJOS_SELLABLES:
        raise StagingError(f"ruta sellable fuera de los prefijos {PREFIJOS_SELLABLES}: {rel!r}")
    if len(partes) < 2:
        raise StagingError(f"ruta sellable sin archivo bajo '{partes[0]}': {rel!r}")
    return partes


def _destino_seguro(raiz: Path, partes: tuple[str, ...]) -> Path:
    """Traduce una ruta sellada a su destino real, sin salirse de la raíz.

    La gramática ya prohíbe `..`, pero un **enlace en el destino** escapa sin necesitarlo:
    si `dashboard/sub` es un enlace a otro directorio, escribir en `dashboard/sub/x` cae
    fuera del repositorio. Por eso se comprueba componente a componente, y también el
    último: sobrescribir un enlace escribiría a través de él.
    """
    raiz_real = raiz.resolve()
    destino = raiz_real.joinpath(*partes)
    try:
        destino.relative_to(raiz_real)
    except ValueError as exc:  # pragma: no cover - la gramática ya lo impide
        raise StagingError(f"la ruta escaparía de {raiz_real}: {'/'.join(partes)}") from exc

    actual = raiz_real
    for parte in partes:
        actual = actual / parte
        if actual.is_symlink():
            raise StagingError(f"un componente del destino es un enlace simbólico: {actual}")
    return destino


def _escribe_exclusivo(ruta: Path, crudo: bytes) -> None:
    """Crea `ruta` y escribe `crudo`, sin seguir enlaces y sin reutilizar lo que haya.

    `write_bytes` sigue un enlace preexistente: un `manifest.json.part` preplantado como
    enlace hacía que el manifiesto se escribiera **dentro del archivo apuntado** y que
    `manifest.json` acabara siendo un enlace. Comprobado. Aquí un residuo regular se
    retira y cualquier otra cosa aborta; la creación es exclusiva y `O_NOFOLLOW` cierra
    la carrera entre comprobar y abrir.
    """
    _vuelca_exclusivo(ruta, [crudo], hashlib.sha256(crudo).hexdigest())


def _vuelca_exclusivo(ruta: Path, bloques: Iterable[bytes], digest: str) -> None:
    """Crea `ruta` en exclusiva, vuelca los bloques enteros y comprueba el resultado.

    `os.write` puede escribir **menos** bytes de los pedidos y devolver cuántos sin que
    nadie proteste: una sola llamada publicaba un archivo truncado. Aquí se escribe en
    bucle hasta agotar cada bloque, se fuerza a disco y se relee el digest antes de que
    nadie renombre nada. Un archivo corto no llega a ser candidato a publicarse.
    """
    banderas = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(ruta, banderas, 0o644)
    except FileExistsError as exc:
        # Antes esto retiraba un archivo regular preexistente «porque era un residuo».
        # Exclusiva quiere decir exclusiva: si la ruta existe, alguien la puso ahí y esta
        # función no decide por él. Un residuo real lo limpia quien creó el staging.
        raise StagingError(f"la ruta de escritura ya existe: {ruta}") from exc
    try:
        for bloque in bloques:
            memoria = memoryview(bloque)
            while memoria:
                escritos = os.write(descriptor, memoria)
                if escritos <= 0:
                    raise StagingError(f"escritura incompleta en {ruta}")
                memoria = memoria[escritos:]
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        ruta.unlink(missing_ok=True)
        raise
    else:
        os.close(descriptor)

    if sha256_de(ruta) != digest:
        ruta.unlink(missing_ok=True)
        raise StagingError(f"lo escrito en {ruta} no coincide con su digest; quedó truncado")


def _escribe_atomico(destino: Path, crudo: bytes, sufijo: str) -> None:
    """Publica `destino` a través de un temporal creado en exclusiva."""
    if destino.is_symlink():
        raise StagingError(f"la ruta de destino es un enlace simbólico: {destino}")
    temporal = destino.with_name(destino.name + sufijo)
    _escribe_exclusivo(temporal, crudo)
    try:
        temporal.replace(destino)
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise


@dataclass
class _Transicion:
    """Qué le pasó realmente a una ruta durante la instalación.

    `apartado` y `publicado` son independientes: entre apartar el original y publicar el
    nuevo hay un instante en que ninguna de las dos cosas es cierta, y el rollback tiene
    que distinguirlo de las otras tres combinaciones.
    """

    destino: Path
    previo: Path | None
    apartado: bool = False
    publicado: bool = False


def _exige_libre(ruta: Path) -> None:
    """Ninguna ruta auxiliar de la transacción puede existir de antemano."""
    if ruta.is_symlink() or ruta.exists():
        raise StagingError(f"la ruta auxiliar de la transacción ya existe: {ruta}")


def _copia_exclusiva(origen: Path, temporal: Path, digest: str) -> None:
    """Copia `origen` a un `temporal` recién creado, sin seguir enlaces.

    `shutil.copy2` abre el destino con las banderas de siempre: un `.part` preplantado
    como enlace hacía que la copia se escribiera en el archivo apuntado y que el destino
    acabara publicado como enlace. Comprobado.
    """

    def bloques() -> Iterable[bytes]:
        with origen.open("rb") as f:
            yield from iter(lambda: f.read(1 << 20), b"")

    _vuelca_exclusivo(temporal, bloques(), digest)
    shutil.copystat(origen, temporal)


def _exige_directorio_real(raiz: Path, que: str) -> None:
    """`raiz` tiene que ser un directorio de verdad, no un enlace a uno.

    `is_dir()` sigue enlaces, así que un `outputs/` enlazado se recorría entero y sellaba
    artefactos de fuera del staging como si fueran suyos. Comprobado.
    """
    if raiz.is_symlink():
        raise StagingError(f"{que} es un enlace simbólico: {raiz}")
    if not raiz.is_dir():
        raise StagingError(f"no existe {que}: {raiz}")


def _relativos(raiz: Path) -> list[Path]:
    """Archivos regulares bajo `raiz`, sin seguir enlaces y fallando cerrado.

    `is_file()` sigue los enlaces: un enlace a un archivo de fuera se inventariaba como si
    fuera del staging y se copiaba su contenido al destino. Aquí se clasifica con `lstat`
    y cualquier enlace o tipo especial aborta, en vez de saltarse en silencio.
    """
    _exige_directorio_real(raiz, "el directorio de artefactos")
    encontrados: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(raiz, followlinks=False):
        base = Path(dirpath)
        for nombre in sorted(dirnames):
            if (base / nombre).is_symlink():
                raise StagingError(
                    f"enlace simbólico en el staging: {(base / nombre).relative_to(raiz)}"
                )
        for nombre in sorted(filenames):
            ruta = base / nombre
            modo = ruta.lstat().st_mode
            if stat.S_ISLNK(modo):
                raise StagingError(f"enlace simbólico en el staging: {ruta.relative_to(raiz)}")
            if not stat.S_ISREG(modo):
                raise StagingError(f"archivo no regular en el staging: {ruta.relative_to(raiz)}")
            encontrados.append(ruta.relative_to(raiz))
    return sorted(encontrados)


@dataclass(frozen=True)
class Boletin:
    """Un PDF de origen, con su procedencia verificable."""

    nombre: str
    url: str
    bytes: int
    sha256: str

    def como_dict(self) -> dict[str, Any]:
        return {"nombre": self.nombre, "url": self.url, "bytes": self.bytes, "sha256": self.sha256}


@dataclass
class SelloEntrada:
    """Lo que había ANTES de generar: si esto cambia, el sello deja de valer.

    Lo que declara quien sella: HEADs, semanas y padecimientos. Lo demás —digests del
    consolidado base y candidato, boletines e inventario de entradas— lo **deriva**
    `sella` de la hidratación registrada en el staging; no se recibe por parámetro.
    """

    head_backend: str
    head_dashboard: str
    semana_anterior: str
    semana_nueva: str
    padecimientos_autorizados: tuple[str, ...]
    digest_consolidado_antes: str = ""
    digest_consolidado_candidato: str = ""
    boletines: tuple[Boletin, ...] = ()
    entradas: dict[str, dict[str, Any]] = field(default_factory=dict)

    def como_dict(self) -> dict[str, Any]:
        return {
            "head_backend": self.head_backend,
            "head_dashboard": self.head_dashboard,
            "digest_consolidado_antes": self.digest_consolidado_antes,
            "digest_consolidado_candidato": self.digest_consolidado_candidato,
            "semana_anterior": self.semana_anterior,
            "semana_nueva": self.semana_nueva,
            "padecimientos_autorizados": list(self.padecimientos_autorizados),
            "boletines": [b.como_dict() for b in self.boletines],
            "entradas": {ruta: dict(meta) for ruta, meta in sorted(self.entradas.items())},
        }


@dataclass(frozen=True)
class RegistroHidratacion:
    """Lo que `hydrate` dejó en el staging: qué entradas, con qué digests, y dónde está
    el sandbox. Lo lee `sella` de su ruta fija; no hay parámetro para inyectarlo."""

    head_backend: str
    lista: dict[str, str]
    sandbox: str
    consolidado: str
    entradas: dict[str, dict[str, Any]]
    boletines: tuple[Boletin, ...]
    cobertura: dict[str, Any]

    CLAVES = (
        "esquema",
        "head_backend",
        "lista",
        "sandbox",
        "consolidado",
        "entradas",
        "boletines",
        "cobertura",
    )

    def como_dict(self) -> dict[str, Any]:
        return {
            "esquema": ESQUEMA_HIDRATACION,
            "head_backend": self.head_backend,
            "lista": dict(self.lista),
            "sandbox": self.sandbox,
            "consolidado": self.consolidado,
            "entradas": {ruta: dict(meta) for ruta, meta in sorted(self.entradas.items())},
            "boletines": [b.como_dict() for b in self.boletines],
            "cobertura": dict(self.cobertura),
        }

    def escribe(self, trabajo: Path) -> None:
        crudo = json.dumps(self.como_dict(), indent=2, ensure_ascii=False, sort_keys=True).encode()
        crudo += b"\n"
        destino = trabajo / ARCHIVO_ENTRADAS
        _escribe_exclusivo(destino, crudo)
        _escribe_exclusivo(
            destino.with_name(destino.stem + ".sha256"),
            hashlib.sha256(crudo).hexdigest().encode() + b"\n",
        )

    @staticmethod
    def lee(trabajo: Path) -> RegistroHidratacion:
        ruta = trabajo / ARCHIVO_ENTRADAS
        if ruta.is_symlink() or not ruta.is_file():
            raise StagingError(
                f"no hay hidratación registrada en {trabajo}: corre `hydrate` antes de sellar"
            )
        verifica_sidecar(ruta)
        try:
            crudo = json.loads(ruta.read_bytes(), object_pairs_hook=_sin_duplicados)
        except json.JSONDecodeError as exc:
            raise StagingError(f"registro de hidratación ilegible: {exc}") from exc
        if not isinstance(crudo, dict) or set(crudo) != set(RegistroHidratacion.CLAVES):
            raise StagingError("registro de hidratación malformado")
        if crudo["esquema"] != ESQUEMA_HIDRATACION:
            raise StagingError(f"registro de hidratación de otro esquema: {crudo['esquema']!r}")
        if not isinstance(crudo["head_backend"], str) or not re.fullmatch(
            r"[0-9a-f]{40}", crudo["head_backend"]
        ):
            raise StagingError("head_backend de la hidratación no es un SHA1")
        lista = crudo["lista"]
        if (
            not isinstance(lista, dict)
            or set(lista) != {"version", "sha256"}
            or not isinstance(lista["sha256"], str)
            or not _RE_SHA256.fullmatch(lista["sha256"])
        ):
            raise StagingError("la hidratación no identifica la lista de entradas")
        if not isinstance(crudo["sandbox"], str) or not crudo["sandbox"].startswith("/"):
            raise StagingError("el sandbox de la hidratación tiene que ser una ruta absoluta")
        entradas = crudo["entradas"]
        if not isinstance(entradas, dict) or not entradas:
            raise StagingError("la hidratación no registra ninguna entrada")
        for ruta_e, meta in entradas.items():
            valida_ruta_entrada(ruta_e)
            if (
                not isinstance(meta, dict)
                or set(meta) != {"rol", "bytes", "sha256"}
                or not isinstance(meta["rol"], str)
                or isinstance(meta["bytes"], bool)
                or not isinstance(meta["bytes"], int)
                or meta["bytes"] < 0
                or not isinstance(meta["sha256"], str)
                or not _RE_SHA256.fullmatch(meta["sha256"])
            ):
                raise StagingError(f"entrada hidratada malformada: {ruta_e} -> {meta!r}")
        consolidado = crudo["consolidado"]
        if consolidado not in entradas or entradas[consolidado]["rol"] != "consolidado":
            raise StagingError("la hidratación no señala un consolidado entre sus entradas")
        if not isinstance(crudo["boletines"], list) or not isinstance(crudo["cobertura"], dict):
            raise StagingError("boletines/cobertura de la hidratación malformados")
        boletines = tuple(_lee_boletin(b) for b in crudo["boletines"])
        return RegistroHidratacion(
            head_backend=crudo["head_backend"],
            lista=dict(lista),
            sandbox=crudo["sandbox"],
            consolidado=consolidado,
            entradas={r: dict(m) for r, m in entradas.items()},
            boletines=boletines,
            cobertura=dict(crudo["cobertura"]),
        )


def _lee_boletin(crudo: Any) -> Boletin:
    if not isinstance(crudo, dict) or set(crudo) != {"nombre", "url", "bytes", "sha256"}:
        raise StagingError(f"boletín malformado: {crudo!r}")
    if (
        not isinstance(crudo["nombre"], str)
        or not crudo["nombre"]
        or not isinstance(crudo["url"], str)
        or isinstance(crudo["bytes"], bool)
        or not isinstance(crudo["bytes"], int)
        or not isinstance(crudo["sha256"], str)
        or not _RE_SHA256.fullmatch(crudo["sha256"])
    ):
        raise StagingError(f"boletín con campos inválidos: {crudo!r}")
    return Boletin(
        nombre=crudo["nombre"], url=crudo["url"], bytes=crudo["bytes"], sha256=crudo["sha256"]
    )


def valida_ruta_entrada(rel: Any) -> None:
    """Ruta relativa POSIX al backend, sin `..`; distinta de la gramática sellable."""
    if not isinstance(rel, str) or not rel or rel != rel.strip():
        raise StagingError(f"ruta de entrada inválida: {rel!r}")
    if rel.startswith("/") or "\\" in rel or "\x00" in rel:
        raise StagingError(f"ruta de entrada tiene que ser relativa POSIX: {rel!r}")
    if any(p in ("", ".", "..") for p in rel.split("/")):
        raise StagingError(f"ruta de entrada con componente vacío, '.' o '..': {rel!r}")


@dataclass
class Manifiesto:
    """El sello completo. `run_id` deriva de las entradas y del inventario producido."""

    run_id: str
    creado: str
    modo: str
    version_generador: str
    entrada: SelloEntrada
    inventario: dict[str, str] = field(default_factory=dict)
    # Estado del DESTINO en el momento de sellar, para cada ruta administrada. Sin esto
    # una lápida borra lo que encuentre —incluido trabajo del usuario que nunca estuvo en
    # la semilla— y una instalación pisa una edición local hecha después del sello.
    baseline: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Las lápidas viven en su PROPIO campo, disjunto del inventario. Meterlas dentro
    # obligaría a relajar la igualdad «inventariado == presente», que hoy es lo único que
    # detiene una clave con `..`; separarlas conserva esa igualdad intacta.
    tombstones: tuple[str, ...] = ()
    # Digest del árbol completo sobre el que se corrieron los gates. Ata el PASS a una
    # composición concreta y no a un overlay temporal que ya no existe.
    composicion: str = ""
    # Versión y digest de la política contra la que se aprobó la corrida. Sin esto, un
    # conjunto de gates que cambia deja los PASS históricos sin referente.
    politica: dict[str, str] = field(default_factory=dict)
    motivo_draft: str = ""
    # Operaciones DVC EXACTAS que esta corrida autoriza. Vacío por defecto: una lista
    # blanca serializada como si fuera intención no describe ninguna acción real.
    operaciones_dvc: tuple[str, ...] = ()
    resultados_pruebas: dict[str, Any] = field(default_factory=dict)
    # Copias inmutables bajo `<run>/inputs/`: consolidado base y candidato, y cada PDF.
    inputs: dict[str, str] = field(default_factory=dict)

    def como_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "creado": self.creado,
            "modo": self.modo,
            "version_generador": self.version_generador,
            "entrada": self.entrada.como_dict(),
            "inventario": dict(sorted(self.inventario.items())),
            "baseline": dict(sorted(self.baseline.items())),
            "tombstones": sorted(self.tombstones),
            "composicion": self.composicion,
            "politica": dict(sorted(self.politica.items())),
            "motivo_draft": self.motivo_draft,
            "operaciones_dvc": list(self.operaciones_dvc),
            "resultados_pruebas": self.resultados_pruebas,
            "inputs": dict(sorted(self.inputs.items())),
        }

    def payload_canonico(self) -> dict[str, Any]:
        """Todo lo que gobierna una acción entra en el identificador.

        Quedan fuera sólo `creado` y el registro observacional de los gates (tiempos,
        ejecutable resuelto): son informativos, y dos corridas equivalentes deben compartir
        identificador aunque difieran en ellos. Por eso el sidecar cubre el JSON entero, esos
        campos incluidos, y `verifica` exige que la evidencia observacional en disco coincida
        con su digest.
        """
        cuerpo = self.como_dict()
        cuerpo.pop("run_id")
        cuerpo.pop("creado")
        if isinstance(cuerpo["resultados_pruebas"], dict):
            resultados = dict(cuerpo["resultados_pruebas"])
            resultados.pop("observacional", None)
            cuerpo["resultados_pruebas"] = resultados
        return cuerpo

    def escribe(self, destino: Path) -> None:
        """Escribe el manifiesto y su sidecar `manifest.sha256`.

        `run_id` deja fuera `creado` a propósito, para que dos corridas idénticas compartan
        identificador. El sidecar cubre el JSON **completo**, ese campo incluido, así que
        una edición del manifiesto se detecta aunque no toque nada que entre en el ID.
        No es una firma: quien edite el JSON puede recalcularlo. Detecta corrupción y
        edición no revisada, que es lo que ocurre en la práctica.
        """
        destino.parent.mkdir(parents=True, exist_ok=True)
        cuerpo = json.dumps(self.como_dict(), indent=2, ensure_ascii=False, sort_keys=False)
        crudo = cuerpo.encode("utf-8")
        _escribe_atomico(destino, crudo, ".part")
        sidecar = destino.with_name(destino.stem + ".sha256")
        _escribe_atomico(sidecar, hashlib.sha256(crudo).hexdigest().encode() + b"\n", ".part")

    @staticmethod
    def lee(ruta: Path) -> Manifiesto:
        if not ruta.is_file():
            raise StagingError(f"no existe el manifiesto: {ruta}")

        try:
            crudo = json.loads(ruta.read_text(encoding="utf-8"), object_pairs_hook=_sin_duplicados)
        except json.JSONDecodeError as exc:
            raise StagingError(f"manifiesto ilegible: {exc}") from exc

        version = crudo.get("version_generador")
        if version != VERSION_GENERADOR:
            raise StagingError(
                f"el staging lo generó {version} y este es {VERSION_GENERADOR}; "
                "regenéralo en vez de aplicarlo"
            )

        esperadas = {
            "run_id",
            "creado",
            "modo",
            "version_generador",
            "entrada",
            "inventario",
            "baseline",
            "tombstones",
            "composicion",
            "politica",
            "motivo_draft",
            "operaciones_dvc",
            "resultados_pruebas",
            "inputs",
        }
        if faltantes := esperadas - set(crudo):
            raise StagingError(f"manifiesto incompleto, faltan claves: {sorted(faltantes)}")
        if sobrantes := set(crudo) - esperadas:
            raise StagingError(f"manifiesto con claves desconocidas: {sorted(sobrantes)}")

        if not isinstance(crudo["resultados_pruebas"], dict):
            raise StagingError("resultados_pruebas tiene que ser un objeto")
        e = crudo["entrada"]
        claves_entrada = {
            "head_backend",
            "head_dashboard",
            "digest_consolidado_antes",
            "digest_consolidado_candidato",
            "semana_anterior",
            "semana_nueva",
            "padecimientos_autorizados",
            "boletines",
            "entradas",
        }
        if not isinstance(e, dict) or set(e) != claves_entrada:
            raise StagingError("la entrada del manifiesto no tiene la forma de weekly_staging/3")
        if not isinstance(e["boletines"], list) or not isinstance(e["entradas"], dict):
            raise StagingError("boletines/entradas de la entrada malformados")
        if not isinstance(crudo["inputs"], dict):
            raise StagingError("inputs tiene que ser un objeto")
        entrada = SelloEntrada(
            head_backend=e["head_backend"],
            head_dashboard=e["head_dashboard"],
            semana_anterior=e["semana_anterior"],
            semana_nueva=e["semana_nueva"],
            padecimientos_autorizados=tuple(e["padecimientos_autorizados"]),
            digest_consolidado_antes=e["digest_consolidado_antes"],
            digest_consolidado_candidato=e["digest_consolidado_candidato"],
            boletines=tuple(_lee_boletin(b) for b in e["boletines"]),
            entradas={r: dict(m) for r, m in e["entradas"].items()},
        )
        manifiesto = Manifiesto(
            run_id=crudo["run_id"],
            creado=crudo["creado"],
            modo=crudo["modo"],
            version_generador=crudo["version_generador"],
            entrada=entrada,
            inventario=dict(crudo["inventario"]),
            baseline=dict(crudo["baseline"]),
            tombstones=tuple(crudo["tombstones"]),
            composicion=crudo["composicion"],
            politica=dict(crudo["politica"]),
            motivo_draft=crudo["motivo_draft"],
            operaciones_dvc=tuple(crudo["operaciones_dvc"]),
            resultados_pruebas=dict(crudo["resultados_pruebas"]),
            inputs=dict(crudo["inputs"]),
        )
        valida_contrato(manifiesto)
        if manifiesto.run_id != calcula_run_id_de(manifiesto):
            raise StagingError(
                "el run_id no deriva del contenido del manifiesto; fue editado o corrompido"
            )
        return manifiesto


@dataclass(frozen=True)
class AutoridadLapidas:
    """De dónde sale el permiso para retirar un archivo del sitio.

    Tres cosas distintas, y ninguna sustituye a las otras:

    - `eliminados_reales`: rutas de la semilla que ya no estaban en el candidato **antes de
      podar**. Es la única señal de que un generador retiró algo. La ausencia posterior a
      la poda no sirve: la poda quita lo que no cambió, así que un artefacto intacto
      quedaba indistinguible de uno borrado — y por tanto autorizable como lápida.
    - `allowlist`: rutas que la política declara retirables. Estar en la semilla dice que
      el archivo existe, no que este flujo pueda borrarlo.

    Las lápidas no se declaran a mano: se **derivan** de `eliminados_reales`, y la política
    decide si esa eliminación está permitida. Declararlas manualmente admitía dos errores
    simétricos —inventar una retirada y olvidar otra— y sólo el primero se detectaba.

    Limitación declarada: el manifiesto guarda las lápidas resultantes, no esta evidencia.
    Un lector no puede recomprobar la autorización; se comprueba al sellar. Lo que sí queda
    ligado al sello es la política —versión y digest— contra la que se autorizó.
    """

    eliminados_reales: frozenset[str]
    allowlist: frozenset[str]

    @staticmethod
    def sin_lapidas() -> AutoridadLapidas:
        """Para sellos que no retiran nada. No autoriza ninguna retirada."""
        return AutoridadLapidas(eliminados_reales=frozenset(), allowlist=frozenset())


# ── gates: definición en la política y evidencia de su ejecución ────────────
#
# La política ya no dice `"gates": ["cifras", "rag"]`. Un nombre no es un gate: un gate es un
# `argv` exacto, un cwd cerrado, un plazo y un entorno permitido, y su resultado se deriva
# de ejecutarlo. Sin esto, «PASS» era una palabra que cualquiera podía escribir en un JSON.

VERSION_POLITICA = "censo/2"
ESQUEMA_EVIDENCIA = "gates_evidencia/1"
ESQUEMA_OBSERVACIONAL = "gates_observacional/1"
DIR_EVIDENCIA = "gates"
ARCHIVO_INDICE = "indice.json"
ARCHIVO_OBSERVACIONAL = "observacional.json"
TIMEOUT_MAX_S = 24 * 60 * 60
VEREDICTO_FAIL = "FAIL"
# Un argv cuyo ejecutable es un intérprete de órdenes equivale a `shell=True`: la política
# volvería a ser una cadena de shell con otro envoltorio.
INTERPRETES_DE_ORDENES = frozenset(
    {
        "sh",
        "bash",
        "zsh",
        "dash",
        "ksh",
        "csh",
        "tcsh",
        "fish",
        "cmd",
        "cmd.exe",
        "powershell",
        "pwsh",
    }
)
# Por qué un gate NO pasó. `""` es la única causa de un PASS.
CAUSAS_FAIL = (
    "exit_code",
    "timeout",
    "senal",
    "ejecutable_ausente",
    "cwd_invalido",
    "excepcion",
    "mutacion",
    "no_ejecutado",
)
_RE_ID_GATE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
_RE_VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_RE_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class GateSpec:
    """Un gate es un `argv` exacto, no una orden de shell.

    Cuatro cosas cerradas: el comando como lista (nunca una cadena, nunca un intérprete),
    el cwd como prefijo administrado de la composición, el plazo y las variables de entorno
    que se heredan por nombre o se fijan con valor. No hay ninguna otra clave: `shell`,
    `cmd` o cualquier alias es un error de parseo, no una opción.
    """

    id: str
    argv: tuple[str, ...]
    cwd: str
    timeout_s: int
    heredar: tuple[str, ...]
    fijar: tuple[tuple[str, str], ...]

    CLAVES = ("id", "argv", "cwd", "timeout_s", "entorno")

    @staticmethod
    def desde_dict(crudo: Any, prefijos_administrados: tuple[str, ...] | None = None) -> GateSpec:
        if not isinstance(crudo, dict):
            raise StagingError(
                "un gate se declara como objeto {id, argv, cwd, timeout_s, entorno}, no como "
                f"{type(crudo).__name__} {crudo!r}; no existe forma de dar una orden de shell"
            )
        if faltan := set(GateSpec.CLAVES) - set(crudo):
            raise StagingError(f"gate incompleto, faltan: {sorted(faltan)}")
        if sobran := set(crudo) - set(GateSpec.CLAVES):
            raise StagingError(
                f"gate con claves desconocidas {sorted(sobran)}: no hay modo shell ni opciones "
                "fuera del contrato"
            )
        ident = crudo["id"]
        if not isinstance(ident, str) or not _RE_ID_GATE.fullmatch(ident):
            raise StagingError(f"id de gate inválido: {ident!r}")

        argv = crudo["argv"]
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            raise StagingError(
                f"el argv del gate {ident} tiene que ser una lista no vacía de cadenas, no "
                f"{argv!r}: una cadena de shell no es un argv"
            )
        if any(not a or "\x00" in a for a in argv):
            raise StagingError(
                f"el argv del gate {ident} tiene un argumento vacío o con byte nulo"
            )
        ejecutable = argv[0]
        if ejecutable.rsplit("/", 1)[-1].lower() in INTERPRETES_DE_ORDENES:
            raise StagingError(
                f"el gate {ident} invoca un intérprete de órdenes ({ejecutable!r}): equivale a "
                "shell=True y no se admite"
            )
        if "/" in ejecutable and not ejecutable.startswith("/"):
            raise StagingError(
                f"el ejecutable del gate {ident} es una ruta relativa: {ejecutable!r}; o es un "
                "nombre que se busca en el PATH permitido o es una ruta absoluta"
            )

        cwd = crudo["cwd"]
        if not isinstance(cwd, str):
            raise StagingError(f"el cwd del gate {ident} tiene que ser una cadena: {cwd!r}")
        _valida_prefijo(cwd, f"cwd del gate {ident}")
        if not cwd.startswith(PREFIJOS_SELLABLES_CON_BARRA):
            raise StagingError(
                f"el cwd del gate {ident} ({cwd!r}) no cuelga de una raíz de la composición "
                f"{PREFIJOS_SELLABLES_CON_BARRA}"
            )
        if prefijos_administrados is not None and not cwd.startswith(prefijos_administrados):
            raise StagingError(
                f"el cwd del gate {ident} ({cwd!r}) no cae bajo ningún prefijo administrado "
                f"{prefijos_administrados}"
            )

        timeout = crudo["timeout_s"]
        if isinstance(timeout, bool) or not isinstance(timeout, int):
            raise StagingError(f"timeout_s del gate {ident} tiene que ser un entero: {timeout!r}")
        if not 1 <= timeout <= TIMEOUT_MAX_S:
            raise StagingError(
                f"timeout_s del gate {ident} fuera de rango [1, {TIMEOUT_MAX_S}]: {timeout!r}"
            )

        entorno = crudo["entorno"]
        if not isinstance(entorno, dict) or set(entorno) != {"heredar", "fijar"}:
            raise StagingError(
                f"el entorno del gate {ident} tiene que ser {{heredar: [...], fijar: {{...}}}}: "
                f"{entorno!r}"
            )
        heredar, fijar = entorno["heredar"], entorno["fijar"]
        if not isinstance(heredar, list) or not all(isinstance(v, str) for v in heredar):
            raise StagingError(
                f"entorno.heredar del gate {ident} tiene que ser una lista de nombres"
            )
        if not isinstance(fijar, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in fijar.items()
        ):
            raise StagingError(
                f"entorno.fijar del gate {ident} tiene que ser un objeto nombre -> valor de texto"
            )
        for variable in [*heredar, *fijar]:
            if not _RE_VARIABLE.fullmatch(variable):
                raise StagingError(
                    f"variable de entorno inválida en el gate {ident}: {variable!r}"
                )
        if len(set(heredar)) != len(heredar):
            raise StagingError(f"entorno.heredar del gate {ident} tiene nombres duplicados")
        if repetidas := sorted(set(heredar) & set(fijar)):
            raise StagingError(f"el gate {ident} hereda y fija a la vez: {repetidas}")

        return GateSpec(
            id=ident,
            argv=tuple(argv),
            cwd=cwd,
            timeout_s=timeout,
            heredar=tuple(heredar),
            fijar=tuple(sorted(fijar.items())),
        )

    def como_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "argv": list(self.argv),
            "cwd": self.cwd,
            "timeout_s": self.timeout_s,
            "entorno": {"heredar": list(self.heredar), "fijar": dict(self.fijar)},
        }


PREFIJOS_SELLABLES_CON_BARRA = tuple(f"{p}/" for p in PREFIJOS_SELLABLES)


@dataclass(frozen=True)
class PoliticaCenso:
    """Qué administra este flujo, qué puede retirar y qué gates exige.

    Dos universos distintos, y confundirlos es un error de tipo:

    - **Archivos administrados**: todo el árbol compuesto —miles de artefactos— tiene que
      caer bajo un prefijo declarado. Enumerarlos sería absurdo; gobernarlos por prefijo
      no. Sirve para rechazar lo que se coló, no para censarlo.
    - **Superficies verificables**: las páginas y JSON que el sitio publica y de las que se
      afirman cosas. Ésas sí se censan **exactamente**: falta una y la semilla era parcial;
      sobra una y alguien publicó algo que nadie revisó. Se derivan del árbol con el mismo
      patrón que usa el gate de cifras y se comparan con la lista declarada.

    Es un documento versionado y **rastreado por Git**: se lee del HEAD que se está
    sellando, no del disco. Una política temporal, sin versionar o de fuera del repositorio
    permitiría fabricar el permiso al mismo tiempo que se usa.
    """

    version: str
    sha256: str
    prefijos_administrados: tuple[str, ...]
    prefijo_publicado: str
    sufijos_superficie: tuple[str, ...]
    directorios_excluidos: frozenset[str]
    superficies_verificables: frozenset[str]
    retirables: frozenset[str]
    gates: tuple[GateSpec, ...]

    CLAVES = (
        "version",
        "prefijos_administrados",
        "patron_superficie",
        "superficies_verificables",
        "retirables",
        "gates",
    )

    @property
    def ids_gates(self) -> tuple[str, ...]:
        return tuple(gate.id for gate in self.gates)

    @staticmethod
    def del_head(repo: Path, head: str) -> PoliticaCenso:
        """Lee la política **desde el commit que se sella**, en su ruta fija.

        La ruta no es parametrizable a propósito. Cuando lo era, `Path.resolve()` seguía
        los enlaces antes de comprobar la pertenencia al repositorio, así que un alias
        interno —`alias.json` apuntando a la política real— pasaba el control. Un flag que
        elige qué documento manda la autoridad es, por definición, una forma de fabricarla.

        Traer el blob del HEAD y exigir igualdad byte a byte resuelve de una vez las tres
        preguntas: que exista en el repositorio, que no esté modificada y que pertenezca a
        ese commit.
        """
        ruta = repo / RUTA_POLITICA
        actual = repo
        for parte in RUTA_POLITICA.split("/"):
            actual = actual / parte
            if actual.is_symlink():
                raise StagingError(
                    f"un componente de la ruta de la política es un enlace: {actual}"
                )

        salida = subprocess.run(
            ["git", "-C", str(repo), "show", f"{head}:{RUTA_POLITICA}"],
            capture_output=True,
        )
        if salida.returncode != 0:
            raise StagingError(
                f"la política {RUTA_POLITICA} no está en {head[:12]}: "
                f"{salida.stderr.decode(errors='replace').strip()}"
            )
        if not ruta.is_file():
            raise StagingError(f"la política {ruta} no existe en el árbol de trabajo")
        if ruta.read_bytes() != salida.stdout:
            raise StagingError(
                f"la política {RUTA_POLITICA} difiere de la versión de {head[:12]}: "
                "confírmala antes de sellar con ella"
            )
        return PoliticaCenso.desde_bytes(salida.stdout)

    @staticmethod
    def desde_bytes(crudo_bytes: bytes) -> PoliticaCenso:
        """Parser fail-closed: la política es la autoridad, así que se lee con desconfianza."""
        try:
            crudo = json.loads(crudo_bytes, object_pairs_hook=_sin_duplicados)
        except json.JSONDecodeError as exc:
            raise StagingError(f"política de censo ilegible: {exc}") from exc
        if not isinstance(crudo, dict):
            raise StagingError("la política de censo no es un objeto")
        if faltan := set(PoliticaCenso.CLAVES) - set(crudo):
            raise StagingError(f"política de censo incompleta, faltan: {sorted(faltan)}")
        if sobran := set(crudo) - set(PoliticaCenso.CLAVES):
            raise StagingError(f"política de censo con claves desconocidas: {sorted(sobran)}")

        patron = crudo["patron_superficie"]
        if not isinstance(patron, dict) or set(patron) != {
            "prefijo",
            "sufijos",
            "directorios_excluidos",
        }:
            raise StagingError(f"patrón de superficie malformado: {patron!r}")
        if not isinstance(crudo["version"], str) or not crudo["version"].strip():
            raise StagingError("la política no declara una versión legible")
        if crudo["version"] != VERSION_POLITICA:
            raise StagingError(
                f"la política declara la versión {crudo['version']!r} y este sello sólo "
                f"interpreta {VERSION_POLITICA!r}; una política de otra versión no se lee a medias"
            )
        if not isinstance(patron["prefijo"], str) or not patron["prefijo"].endswith("/"):
            raise StagingError(
                f"el prefijo publicado tiene que terminar en '/': {patron['prefijo']!r}"
            )

        listas = {
            "prefijos_administrados": crudo["prefijos_administrados"],
            "superficies_verificables": crudo["superficies_verificables"],
            "retirables": crudo["retirables"],
            "patron_superficie.sufijos": patron["sufijos"],
            "patron_superficie.directorios_excluidos": patron["directorios_excluidos"],
        }
        for nombre, valor in listas.items():
            if not isinstance(valor, list) or not all(isinstance(x, str) for x in valor):
                raise StagingError(f"{nombre} tiene que ser una lista de cadenas")
            if len(set(valor)) != len(valor):
                raise StagingError(f"{nombre} tiene entradas duplicadas")
        if not crudo["prefijos_administrados"]:
            raise StagingError("la política no declara ningún prefijo administrado")
        for prefijo in crudo["prefijos_administrados"]:
            _valida_prefijo(prefijo, "prefijo administrado")
        prefijos = tuple(crudo["prefijos_administrados"])
        gates_crudos = crudo["gates"]
        if not isinstance(gates_crudos, list):
            raise StagingError(
                "gates tiene que ser una lista de definiciones {id, argv, cwd, timeout_s, "
                f"entorno}}, no {gates_crudos!r}"
            )
        if not gates_crudos:
            raise StagingError("la política no declara ningún gate; un sello sin gates no vale")
        gates = tuple(GateSpec.desde_dict(g, prefijos) for g in gates_crudos)
        if len({g.id for g in gates}) != len(gates):
            raise StagingError("gates con id duplicado")
        _valida_prefijo(patron["prefijo"], "prefijo publicado")
        for sufijo in patron["sufijos"]:
            if not sufijo.startswith(".") or "/" in sufijo or sufijo != sufijo.strip():
                raise StagingError(f"sufijo de superficie malformado: {sufijo!r}")
        for nombre in patron["directorios_excluidos"]:
            if not nombre or "/" in nombre or nombre != nombre.strip() or nombre in (".", ".."):
                raise StagingError(
                    f"exclusión malformada: {nombre!r}; tiene que ser el nombre de un "
                    "único directorio"
                )

        superficies = frozenset(crudo["superficies_verificables"])
        retirables = frozenset(crudo["retirables"])
        for rel in sorted(superficies | retirables):
            valida_ruta_sellable(rel)
        if fuera := sorted(retirables - superficies):
            raise StagingError(f"la política permite retirar rutas que no administra: {fuera[:5]}")

        politica = PoliticaCenso(
            version=str(crudo["version"]),
            sha256=hashlib.sha256(crudo_bytes).hexdigest(),
            prefijos_administrados=prefijos,
            prefijo_publicado=str(patron["prefijo"]),
            sufijos_superficie=tuple(patron["sufijos"]),
            directorios_excluidos=frozenset(patron["directorios_excluidos"]),
            superficies_verificables=superficies,
            retirables=retirables,
            gates=gates,
        )
        # Coherencia entre las piezas, no sólo forma de cada una. Una política puede estar
        # bien escrita y decir algo imposible: publicar bajo un prefijo que no administra,
        # o censar rutas que su propio patrón no reconocería como superficie.
        if not politica.prefijo_publicado.startswith(prefijos):
            raise StagingError(
                f"el prefijo publicado {politica.prefijo_publicado!r} no cae bajo ningún "
                f"prefijo administrado {prefijos}"
            )
        if ajenas := sorted(rel for rel in superficies if not politica.es_superficie(rel)):
            raise StagingError(
                f"el censo declara {len(ajenas)} ruta(s) que su propio patrón no reconoce "
                f"como superficie: {ajenas[:5]}"
            )
        return politica

    def es_superficie(self, rel: str) -> bool:
        """Sólo lo que el sitio publica. Las tablas del backend no son superficie."""
        if not rel.startswith(self.prefijo_publicado):
            return False
        partes = rel.split("/")
        # El gate real (`cifras_contrato.mjs`) salta CUALQUIER directorio oculto, no sólo
        # los enumerados. Replicar la lista y olvidar el `startsWith('.')` hacía que
        # `.claude/settings.local.json` contara como superficie aquí y no allí: dos censos
        # que se creen el mismo. Un control que no reproduce la regla del gate mide otra
        # cosa.
        if any(
            parte in self.directorios_excluidos or parte.startswith(".") for parte in partes[:-1]
        ):
            return False
        return partes[-1].lower().endswith(self.sufijos_superficie)

    def revisa_universos(self, arbol: dict[str, str], tombstones: tuple[str, ...]) -> None:
        """Los dos universos, cada uno con su regla. Faltantes y sobrantes, en ambos."""
        if colados := sorted(
            rel for rel in arbol if not rel.startswith(self.prefijos_administrados)
        ):
            raise StagingError(
                f"la composición incluye {len(colados)} archivo(s) que la política no "
                f"administra: {colados[:5]}"
            )
        observadas = {rel for rel in arbol if self.es_superficie(rel)}
        if faltan := sorted(self.superficies_verificables - observadas - set(tombstones)):
            raise StagingError(
                f"la composición no cubre {len(faltan)} superficie(s) del censo: "
                f"{faltan[:5]}. La semilla es parcial: sellar así certificaría un sitio que "
                "no es el que se publica"
            )
        if sobran := sorted(observadas - self.superficies_verificables):
            raise StagingError(
                f"la composición publica {len(sobran)} superficie(s) que el censo no "
                f"declara: {sobran[:5]}. Añádelas a la política tras revisarlas"
            )


def calcula_composicion(
    semilla: dict[str, str], cambiados: dict[str, str], tombstones: tuple[str, ...]
) -> tuple[str, dict[str, str]]:
    """Digest canónico del árbol administrado completo tras aplicar el candidato.

    `semilla completa + cambiados − lápidas`, con las rutas ordenadas. Es lo que `apply`
    va a reconstruir, así que es lo único contra lo que tiene sentido correr un gate: un
    PASS sobre un overlay temporal no certifica los bytes que se instalarán.
    """
    arbol = dict(semilla)
    arbol.update(cambiados)
    for rel in tombstones:
        arbol.pop(rel, None)
    cuerpo = json.dumps(dict(sorted(arbol.items())), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(cuerpo.encode()).hexdigest(), arbol


@dataclass(frozen=True)
class RegistroGate:
    """Lo que gobierna de la ejecución de un gate. Todo entra en el identificador.

    Los tiempos y la RUTA del ejecutable resuelto NO están aquí: son observacionales y viven
    en `observacional.json`. El DIGEST del ejecutable sí: la política gobierna el nombre
    (`argv[0]`) y el PATH permitido, pero dos máquinas con el mismo nombre pueden ejecutar
    binarios distintos, y un PASS de `node` que no dice qué `node` no certifica el mismo
    gate. Dos ejecuciones equivalentes comparten este registro byte a byte.
    """

    gate: str
    veredicto: str
    causa: str
    detalle: str
    politica_sha256: str
    composicion: str
    spec: GateSpec
    exit_code: int | None
    senal: int | None
    stdout_bytes: int
    stdout_sha256: str
    stderr_bytes: int
    stderr_sha256: str
    ejecutable_sha256: str = ""

    CLAVES = (
        "gate",
        "veredicto",
        "causa",
        "detalle",
        "politica_sha256",
        "composicion",
        "argv",
        "cwd",
        "timeout_s",
        "entorno",
        "exit_code",
        "senal",
        "stdout",
        "stderr",
        "ejecutable_sha256",
    )

    def como_dict(self) -> dict[str, Any]:
        spec = self.spec.como_dict()
        return {
            "gate": self.gate,
            "veredicto": self.veredicto,
            "causa": self.causa,
            "detalle": self.detalle,
            "politica_sha256": self.politica_sha256,
            "composicion": self.composicion,
            "argv": spec["argv"],
            "cwd": spec["cwd"],
            "timeout_s": spec["timeout_s"],
            "entorno": spec["entorno"],
            "exit_code": self.exit_code,
            "senal": self.senal,
            "stdout": {"bytes": self.stdout_bytes, "sha256": self.stdout_sha256},
            "stderr": {"bytes": self.stderr_bytes, "sha256": self.stderr_sha256},
            "ejecutable_sha256": self.ejecutable_sha256,
        }

    @staticmethod
    def desde_dict(nombre: str, crudo: Any) -> RegistroGate:
        """Parser fail-closed del registro de un gate; se usa al releer índice y manifiesto."""
        if not isinstance(crudo, dict):
            raise StagingError(f"el resultado del gate {nombre} no es un objeto")
        if set(crudo) != set(RegistroGate.CLAVES):
            faltan = sorted(set(RegistroGate.CLAVES) - set(crudo))
            sobran = sorted(set(crudo) - set(RegistroGate.CLAVES))
            raise StagingError(
                f"registro del gate {nombre} malformado (faltan {faltan}, sobran {sobran})"
            )
        if crudo["gate"] != nombre:
            raise StagingError(
                f"el registro bajo la clave {nombre!r} dice ser del gate {crudo['gate']!r}"
            )
        veredicto = crudo["veredicto"]
        causa = crudo["causa"]
        if veredicto not in (VEREDICTO_REQUERIDO, VEREDICTO_FAIL):
            raise StagingError(f"veredicto desconocido en el gate {nombre}: {veredicto!r}")
        if veredicto == VEREDICTO_REQUERIDO and causa != "":
            raise StagingError(f"el gate {nombre} declara PASS con causa de fallo {causa!r}")
        if veredicto == VEREDICTO_FAIL and causa not in CAUSAS_FAIL:
            raise StagingError(f"el gate {nombre} declara FAIL con causa desconocida {causa!r}")
        if not isinstance(crudo["detalle"], str):
            raise StagingError(f"el detalle del gate {nombre} no es texto")
        for clave in ("politica_sha256", "composicion"):
            if not isinstance(crudo[clave], str) or not _RE_SHA256.fullmatch(crudo[clave]):
                raise StagingError(f"{clave} del gate {nombre} no es un SHA256 de 64 hex")
        spec = GateSpec.desde_dict(
            {
                "id": nombre,
                "argv": crudo["argv"],
                "cwd": crudo["cwd"],
                "timeout_s": crudo["timeout_s"],
                "entorno": crudo["entorno"],
            }
        )
        exit_code, senal = crudo["exit_code"], crudo["senal"]
        for etiqueta, valor in (("exit_code", exit_code), ("senal", senal)):
            if valor is not None and (isinstance(valor, bool) or not isinstance(valor, int)):
                raise StagingError(f"{etiqueta} del gate {nombre} tiene que ser entero o null")
        if veredicto == VEREDICTO_REQUERIDO and (exit_code != 0 or senal is not None):
            raise StagingError(
                f"el gate {nombre} declara PASS sin código 0 (exit_code={exit_code!r}, "
                f"senal={senal!r}); PASS sólo se deriva de un código de salida 0"
            )
        if causa == "exit_code" and exit_code in (None, 0):
            raise StagingError(
                f"el gate {nombre} declara fallo por exit_code y trae {exit_code!r}"
            )
        if causa == "senal" and senal is None:
            raise StagingError(f"el gate {nombre} declara fallo por señal sin número de señal")
        flujos: dict[str, tuple[int, str]] = {}
        for flujo in ("stdout", "stderr"):
            valor = crudo[flujo]
            if (
                not isinstance(valor, dict)
                or set(valor) != {"bytes", "sha256"}
                or isinstance(valor["bytes"], bool)
                or not isinstance(valor["bytes"], int)
                or valor["bytes"] < 0
                or not isinstance(valor["sha256"], str)
                or not _RE_SHA256.fullmatch(valor["sha256"])
            ):
                raise StagingError(f"{flujo} del gate {nombre} malformado: {valor!r}")
            flujos[flujo] = (valor["bytes"], valor["sha256"])
        ejecutable = crudo["ejecutable_sha256"]
        if not isinstance(ejecutable, str) or (
            ejecutable != "" and not _RE_SHA256.fullmatch(ejecutable)
        ):
            raise StagingError(f"ejecutable_sha256 del gate {nombre} no es un SHA256 o vacío")
        # Un gate que llegó a lanzarse tiene ejecutable; uno que no (ausente, cwd inválido,
        # no ejecutado) no lo tiene. Un PASS sin digest de ejecutable no dice qué corrió.
        if veredicto == VEREDICTO_REQUERIDO and ejecutable == "":
            raise StagingError(f"el gate {nombre} declara PASS sin digest del ejecutable")
        return RegistroGate(
            gate=nombre,
            veredicto=veredicto,
            causa=causa,
            detalle=crudo["detalle"],
            politica_sha256=crudo["politica_sha256"],
            composicion=crudo["composicion"],
            spec=spec,
            exit_code=exit_code,
            senal=senal,
            stdout_bytes=flujos["stdout"][0],
            stdout_sha256=flujos["stdout"][1],
            stderr_bytes=flujos["stderr"][0],
            stderr_sha256=flujos["stderr"][1],
            ejecutable_sha256=ejecutable,
        )


def rutas_evidencia(ids_gates: Iterable[str]) -> tuple[frozenset[str], frozenset[str]]:
    """Qué archivos, y sólo cuáles, forman la evidencia de un conjunto de gates.

    Devuelve (gobernantes, observacionales), con rutas relativas al staging.
    """
    gobernantes = {
        f"{DIR_EVIDENCIA}/{ARCHIVO_INDICE}",
        f"{DIR_EVIDENCIA}/{Path(ARCHIVO_INDICE).stem}.sha256",
    }
    for ident in ids_gates:
        gobernantes.add(f"{DIR_EVIDENCIA}/{ident}/stdout.bin")
        gobernantes.add(f"{DIR_EVIDENCIA}/{ident}/stderr.bin")
    return frozenset(gobernantes), frozenset({f"{DIR_EVIDENCIA}/{ARCHIVO_OBSERVACIONAL}"})


@dataclass(frozen=True)
class EvidenciaGates:
    """La evidencia que dejó el runner, releída desde disco y verificada.

    Es la ÚNICA fuente de resultados de gates que `sella` acepta, y vive en la ruta fija
    `<staging>/gates/`. No hay parámetro ni flag para señalar otra: un resultado que se
    pueda suministrar es un resultado que se puede fabricar.
    """

    politica_version: str
    politica_sha256: str
    composicion: str
    veredicto: str
    gates: dict[str, RegistroGate]
    evidencia: dict[str, str]
    observacional: dict[str, str]

    @staticmethod
    def lee(raiz_staging: Path) -> EvidenciaGates:
        carpeta = raiz_staging / DIR_EVIDENCIA
        if carpeta.is_symlink():
            raise StagingError(f"la evidencia de gates es un enlace simbólico: {carpeta}")
        if not carpeta.is_dir():
            raise StagingError(
                f"no hay evidencia de gates en {carpeta}: corre `run-gates` sobre el árbol "
                "completo antes de sellar"
            )
        presentes = {str(rel) for rel in _relativos(carpeta)}

        indice = carpeta / ARCHIVO_INDICE
        if ARCHIVO_INDICE not in presentes:
            raise StagingError(f"la evidencia no tiene índice {ARCHIVO_INDICE}")
        verifica_sidecar(indice)
        crudo_indice = indice.read_bytes()
        try:
            crudo = json.loads(crudo_indice, object_pairs_hook=_sin_duplicados)
        except json.JSONDecodeError as exc:
            raise StagingError(f"índice de evidencia ilegible: {exc}") from exc
        if not isinstance(crudo, dict) or set(crudo) != {
            "esquema",
            "politica",
            "composicion",
            "veredicto",
            "gates",
        }:
            raise StagingError(f"índice de evidencia malformado: {crudo!r}"[:300])
        if crudo["esquema"] != ESQUEMA_EVIDENCIA:
            raise StagingError(
                f"la evidencia es del esquema {crudo['esquema']!r} y este sello lee "
                f"{ESQUEMA_EVIDENCIA!r}"
            )
        politica = crudo["politica"]
        if (
            not isinstance(politica, dict)
            or set(politica) != {"version", "sha256"}
            or not isinstance(politica["version"], str)
            or not isinstance(politica["sha256"], str)
            or not _RE_SHA256.fullmatch(politica["sha256"])
        ):
            raise StagingError(f"la evidencia no identifica la política: {politica!r}")
        composicion = crudo["composicion"]
        if not isinstance(composicion, str) or not _RE_SHA256.fullmatch(composicion):
            raise StagingError("la composición de la evidencia no es un SHA256 de 64 hex")
        if crudo["veredicto"] not in (VEREDICTO_REQUERIDO, VEREDICTO_FAIL):
            raise StagingError(f"veredicto global desconocido: {crudo['veredicto']!r}")
        if not isinstance(crudo["gates"], dict) or not crudo["gates"]:
            raise StagingError("la evidencia no registra ningún gate")
        registros = {
            nombre: RegistroGate.desde_dict(nombre, valor)
            for nombre, valor in crudo["gates"].items()
        }
        for nombre, registro in registros.items():
            if registro.composicion != composicion:
                raise StagingError(
                    f"el gate {nombre} apunta a otra composición que el índice de evidencia"
                )
            if registro.politica_sha256 != politica["sha256"]:
                raise StagingError(f"el gate {nombre} apunta a otra política que el índice")
        todos_pasan = all(r.veredicto == VEREDICTO_REQUERIDO for r in registros.values())
        if (crudo["veredicto"] == VEREDICTO_REQUERIDO) != todos_pasan:
            raise StagingError(
                f"el índice declara {crudo['veredicto']} y los gates no lo sostienen"
            )

        gobernantes, observacionales = rutas_evidencia(registros)
        esperados = {
            rel.removeprefix(f"{DIR_EVIDENCIA}/") for rel in gobernantes | observacionales
        }
        if faltan := sorted(esperados - presentes):
            raise StagingError(f"evidencia incompleta, faltan: {faltan[:5]}")
        if sobran := sorted(presentes - esperados):
            raise StagingError(f"evidencia con archivos que nadie produjo: {sobran[:5]}")

        digestos: dict[str, str] = {
            f"{DIR_EVIDENCIA}/{ARCHIVO_INDICE}": hashlib.sha256(crudo_indice).hexdigest(),
            f"{DIR_EVIDENCIA}/{Path(ARCHIVO_INDICE).stem}.sha256": sha256_de(
                indice.with_name(indice.stem + ".sha256")
            ),
        }
        for nombre, registro in registros.items():
            for flujo, tamano, digest in (
                ("stdout", registro.stdout_bytes, registro.stdout_sha256),
                ("stderr", registro.stderr_bytes, registro.stderr_sha256),
            ):
                ruta = carpeta / nombre / f"{flujo}.bin"
                if ruta.stat().st_size != tamano or sha256_de(ruta) != digest:
                    raise StagingError(
                        f"{flujo} del gate {nombre} no coincide con lo que registra el índice; "
                        "la evidencia fue editada o se corrompió"
                    )
                digestos[f"{DIR_EVIDENCIA}/{nombre}/{flujo}.bin"] = digest

        observacional = carpeta / ARCHIVO_OBSERVACIONAL
        try:
            obs = json.loads(observacional.read_bytes(), object_pairs_hook=_sin_duplicados)
        except json.JSONDecodeError as exc:
            raise StagingError(f"registro observacional ilegible: {exc}") from exc
        if (
            not isinstance(obs, dict)
            or set(obs) != {"esquema", "gates"}
            or obs["esquema"] != ESQUEMA_OBSERVACIONAL
            or not isinstance(obs["gates"], dict)
            or set(obs["gates"]) != set(registros)
        ):
            raise StagingError("registro observacional malformado o de otros gates")

        return EvidenciaGates(
            politica_version=politica["version"],
            politica_sha256=politica["sha256"],
            composicion=composicion,
            veredicto=crudo["veredicto"],
            gates=registros,
            evidencia=dict(sorted(digestos.items())),
            observacional={f"{DIR_EVIDENCIA}/{ARCHIVO_OBSERVACIONAL}": sha256_de(observacional)},
        )

    def como_manifiesto(self) -> dict[str, Any]:
        """Lo que el manifiesto guarda. `observacional` queda fuera del `run_id`."""
        return {
            "esquema": ESQUEMA_EVIDENCIA,
            "gates": {nombre: registro.como_dict() for nombre, registro in self.gates.items()},
            "evidencia": dict(sorted(self.evidencia.items())),
            "observacional": dict(sorted(self.observacional.items())),
        }


def valida_gates(evidencia: EvidenciaGates, politica: PoliticaCenso, composicion: str) -> None:
    """La evidencia corresponde a ESTA política, ESTE conjunto de gates y ESTA composición.

    Si un byte cambia después de correr los gates, la composición recompuesta deja de
    coincidir con la que midieron y el sello aborta: recomponer obliga a repetirlos todos.
    """
    if evidencia.politica_sha256 != politica.sha256:
        raise StagingError(
            f"la evidencia se produjo contra la política {evidencia.politica_sha256[:12]}… y el "
            f"HEAD sellado trae {politica.sha256[:12]}…; no es la misma política"
        )
    esperados = set(politica.ids_gates)
    if faltan := sorted(esperados - set(evidencia.gates)):
        raise StagingError(f"faltan resultados de gates que la política exige: {faltan}")
    if sobran := sorted(set(evidencia.gates) - esperados):
        raise StagingError(f"hay resultados de gates que la política no declara: {sobran}")
    for spec in politica.gates:
        registro = evidencia.gates[spec.id]
        if registro.spec != spec:
            raise StagingError(
                f"la evidencia del gate {spec.id} ejecutó otro comando, cwd, plazo o entorno "
                "que el que declara la política"
            )
        if registro.veredicto != VEREDICTO_REQUERIDO:
            raise StagingError(
                f"el gate {spec.id} declara {registro.veredicto} ({registro.causa}: "
                f"{registro.detalle}) y se exige {VEREDICTO_REQUERIDO}"
            )
        if registro.composicion != composicion:
            raise StagingError(
                f"el gate {spec.id} se corrió sobre la composición "
                f"{registro.composicion[:12]}… y el candidato es {composicion[:12]}…: "
                "algo cambió después de los gates; recompón y vuelve a correrlos"
            )


def valida_resultados_pruebas(manifiesto: Manifiesto) -> None:
    """Forma exacta de `resultados_pruebas` en el manifiesto, y coherencia con el sello."""
    resultados = manifiesto.resultados_pruebas
    if not resultados:
        raise StagingError("un sello sin resultados de gates no autoriza nada")
    if set(resultados) != {"esquema", "gates", "evidencia", "observacional"}:
        raise StagingError(f"resultados_pruebas malformado: claves {sorted(resultados)}")
    if resultados["esquema"] != ESQUEMA_EVIDENCIA:
        raise StagingError(f"resultados_pruebas de otro esquema: {resultados['esquema']!r}")
    gates = resultados["gates"]
    if not isinstance(gates, dict) or not gates:
        raise StagingError("resultados_pruebas no registra ningún gate")
    registros = {nombre: RegistroGate.desde_dict(nombre, valor) for nombre, valor in gates.items()}
    for nombre, registro in registros.items():
        if registro.veredicto != VEREDICTO_REQUERIDO:
            raise StagingError(
                f"el gate {nombre} declara {registro.veredicto!r} y se exige {VEREDICTO_REQUERIDO}"
            )
        if registro.composicion != manifiesto.composicion:
            raise StagingError(
                f"el gate {nombre} no apunta a la composición del sello; se corrió sobre otro árbol"
            )
        if registro.politica_sha256 != manifiesto.politica.get("sha256"):
            raise StagingError(f"el gate {nombre} no apunta a la política del sello")

    gobernantes, observacionales = rutas_evidencia(registros)
    for clave, esperadas in (("evidencia", gobernantes), ("observacional", observacionales)):
        mapa = resultados[clave]
        if not isinstance(mapa, dict) or set(mapa) != esperadas:
            raise StagingError(
                f"{clave} de resultados_pruebas no inventaría exactamente los archivos "
                f"esperados: {sorted(mapa) if isinstance(mapa, dict) else mapa!r}"[:300]
            )
        for rel, digest in mapa.items():
            if not isinstance(digest, str) or not _RE_SHA256.fullmatch(digest):
                raise StagingError(f"digest inválido en {clave} para {rel}")
    for nombre, registro in registros.items():
        evidencia = resultados["evidencia"]
        if (
            evidencia[f"{DIR_EVIDENCIA}/{nombre}/stdout.bin"] != registro.stdout_sha256
            or evidencia[f"{DIR_EVIDENCIA}/{nombre}/stderr.bin"] != registro.stderr_sha256
        ):
            raise StagingError(
                f"los digests de stdout/stderr del gate {nombre} no coinciden con su evidencia"
            )


def verifica_evidencia_en_disco(raiz_staging: Path, manifiesto: Manifiesto) -> None:
    """Lo que hay bajo `<staging>/gates/` es exactamente lo que el manifiesto inventarió."""
    resultados = manifiesto.resultados_pruebas
    esperados: dict[str, str] = {**resultados["evidencia"], **resultados["observacional"]}
    carpeta = raiz_staging / DIR_EVIDENCIA
    _exige_directorio_real(carpeta, "la evidencia de gates")
    presentes = {f"{DIR_EVIDENCIA}/{rel}" for rel in _relativos(carpeta)}
    if faltan := sorted(set(esperados) - presentes):
        raise StagingError(f"falta evidencia de gates sellada: {faltan[:5]}")
    if sobran := sorted(presentes - set(esperados)):
        raise StagingError(f"hay evidencia de gates fuera del inventario: {sobran[:5]}")
    alterados = sorted(
        rel for rel, digest in esperados.items() if sha256_de(raiz_staging / rel) != digest
    )
    if alterados:
        raise StagingError(f"evidencia de gates alterada después del sellado: {alterados[:5]}")


@dataclass(frozen=True)
class Poda:
    """Resultado de podar el staging: lo que cambió y lo que de verdad desapareció."""

    cambiados: dict[str, str]
    eliminados_reales: frozenset[str]


def valida_autoridad_lapidas(
    tombstones: tuple[str, ...],
    autoridad: AutoridadLapidas,
    baseline: dict[str, dict[str, Any]],
    semilla: dict[str, str],
) -> None:
    """Comprueba que cada retirada esté autorizada. Sólo tiene sentido al sellar.

    Al releer un manifiesto ya no existe la semilla, así que esta comprobación no se puede
    repetir: allí sólo se conserva la gramática y la disjunción con el inventario.
    """
    for rel in sorted(tombstones):
        if rel not in semilla:
            raise StagingError(
                f"la lápida {rel} no está en la semilla del staging: este flujo no retira "
                "archivos que no clonó"
            )
        if rel not in autoridad.eliminados_reales:
            raise StagingError(
                f"la lápida {rel} no la retiró ningún generador: seguía presente antes de "
                "podar. La poda quita lo que no cambió, y eso no es un borrado"
            )
        if rel not in autoridad.allowlist:
            raise StagingError(
                f"la lápida {rel} no está en la allowlist de la política de rutas retirables; "
                "estar en la semilla dice que el archivo existe, no que se pueda borrar"
            )
        previo = baseline.get(rel, {})
        if not previo.get("presente"):
            raise StagingError(f"la lápida {rel} no existe en el destino")
        if previo.get("sha256") != semilla[rel]:
            raise StagingError(
                f"la lápida {rel} cambió en el destino desde la semilla; no se retira algo "
                "que ya no es lo que se revisó"
            )

    # La inversa, que es la fuga simétrica: si el candidato retiró algo y el sello no lo
    # declara, el sitio conserva lo obsoleto y nada protesta. La correspondencia es una
    # IGUALDAD, no una inclusión: ni lápidas inventadas ni eliminaciones omitidas.
    if omitidas := sorted(autoridad.eliminados_reales - set(tombstones)):
        raise StagingError(
            f"el candidato retiró {len(omitidas)} archivo(s) que el sello no declara: "
            f"{omitidas[:5]}. Una eliminación observada y no sellada deja vivo lo obsoleto"
        )


def valida_tombstones(
    tombstones: tuple[str, ...],
    inventario: dict[str, str],
) -> None:
    """Las lápidas usan la misma gramática, no se solapan con el inventario y tienen autoridad.

    Gramática y disjunción, nada más: una ruta que se instala y se retira a la vez no tiene
    significado. El permiso para retirarla lo comprueba `valida_autoridad_lapidas`.
    """
    for rel in tombstones:
        valida_ruta_sellable(rel)
    if repetidas := sorted(set(tombstones) & set(inventario)):
        raise StagingError(
            f"estas rutas están a la vez inventariadas y con lápida: {repetidas[:5]}"
        )
    if len(set(tombstones)) != len(tombstones):
        raise StagingError("hay lápidas duplicadas")


VEREDICTO_REQUERIDO = "PASS"
# Ruta FIJA de la política. No es parametrizable: un flag que elige qué documento manda la
# autoridad es una forma de fabricarla.
RUTA_POLITICA = "config/publication/politica_censo.json"


def _valida_prefijo(valor: str, que: str) -> None:
    """Un prefijo POSIX limpio: termina en `/`, es relativo y no esconde nada.

    `"../"` pasaba porque sólo se miraba el final; `" dashboard/"` porque nadie miraba los
    bordes. Un prefijo mal formado no es cosmético: gobierna qué archivos se consideran
    administrados.
    """
    if not valor or valor != valor.strip():
        raise StagingError(f"{que} vacío o con espacios en los bordes: {valor!r}")
    if not valor.endswith("/"):
        raise StagingError(f"{que} tiene que terminar en '/': {valor!r}")
    if valor.startswith("/") or "\\" in valor or "\x00" in valor or "//" in valor:
        raise StagingError(f"{que} malformado: {valor!r}")
    for parte in valor.rstrip("/").split("/"):
        if parte in ("", ".", "..") or parte != parte.strip():
            raise StagingError(f"{que} con componente inválido {parte!r}: {valor!r}")


def _sin_duplicados(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    """`json.loads` se queda con la última de dos claves iguales, sin decir nada."""
    vistas: set[str] = set()
    for clave, _ in pares:
        if clave in vistas:
            raise StagingError(f"clave duplicada en el JSON: {clave!r}")
        vistas.add(clave)
    return dict(pares)


# Un sello sólo es instalable cuando su composición y sus gates se calcularon, no cuando
# alguien los declaró. Eso ya ocurre (P0.9); lo que falta es el confinamiento de la
# instalación (P0.6), y mientras no exista `sella` produce borradores.
MODO_APLICABLE = "aplicable"
MODO_DRAFT = "draft"
# Motivo que llevan los borradores sellados ANTES de P0.6. Se conserva para leerlos y
# para construir borradores en pruebas; ningún sello nuevo lo escribe.
MOTIVO_P06 = (
    "P0.6 pendiente: apply todavía admite destinos arbitrarios y no exige worktrees "
    "desechables. Verificar el sello y poder instalarlo son dos cosas distintas."
)
# Encendida con P0.6 (1-sep-2026): `release_worktrees.aplica` sólo instala en el par de
# worktrees desechables registrado para el run_id, verificado con git y bajo lock, y
# cualquier fallo deja el par inválido. Es la única palanca que convierte un sello
# verificado en instalable, y está aquí para que se vea de un vistazo. Los borradores
# sellados antes siguen siendo borradores: el modo vive en el manifiesto, no aquí.
CONFINAMIENTO_LISTO = True


def valida_contrato(manifiesto: Manifiesto) -> None:
    """Contrato de `weekly_staging/2`: nada que autorice una acción puede faltar.

    Una versión distinta no se juzga aquí: la rechaza `verifica()` con su propio mensaje,
    que dice qué hacer. Los resultados de gates tienen forma exacta: el registro de cada
    gate, el inventario de su evidencia y el digest de lo observacional.
    """
    if manifiesto.version_generador != VERSION_GENERADOR:
        return

    for rel in manifiesto.inventario:
        valida_ruta_sellable(rel)
    valida_tombstones(manifiesto.tombstones, manifiesto.inventario)

    administradas = set(manifiesto.inventario) | set(manifiesto.tombstones)
    if set(manifiesto.baseline) != administradas:
        faltan = sorted(administradas - set(manifiesto.baseline))
        sobran = sorted(set(manifiesto.baseline) - administradas)
        raise StagingError(
            f"el baseline no cubre exactamente las rutas administradas "
            f"(faltan {faltan[:3]}, sobran {sobran[:3]})"
        )
    for rel, previo in manifiesto.baseline.items():
        if set(previo) != {"presente", "tipo", "modo", "bytes", "sha256"}:
            raise StagingError(f"baseline malformado para {rel}: {sorted(previo)}")
        if previo["presente"] and previo["tipo"] != "regular":
            raise StagingError(f"baseline de {rel} no describe un archivo regular")

    if not re.fullmatch(r"[0-9a-f]{64}", manifiesto.composicion):
        raise StagingError(
            "la composición no es un SHA256 de 64 hex; un PASS sin composición canónica "
            "certifica un árbol temporal, no los bytes que se instalarían"
        )
    if set(manifiesto.politica) != {"version", "sha256"}:
        raise StagingError(
            f"el sello no identifica la política contra la que se aprobó: {manifiesto.politica}"
        )
    if not re.fullmatch(r"[0-9a-f]{64}", manifiesto.politica.get("sha256", "")):
        raise StagingError("el digest de la política no es un SHA256 de 64 hex")
    if (manifiesto.modo == MODO_DRAFT) != bool(manifiesto.motivo_draft):
        raise StagingError(
            f"modo {manifiesto.modo!r} y motivo_draft {manifiesto.motivo_draft!r} no "
            "concuerdan; un borrador dice por qué lo es y un aplicable no tiene motivo"
        )
    for operacion in manifiesto.operaciones_dvc:
        if operacion not in TARGETS_DVC_PERMITIDOS:
            raise StagingError(f"objetivo DVC no permitido en el manifiesto: {operacion}")

    valida_resultados_pruebas(manifiesto)
    valida_inputs(manifiesto)


def rutas_inputs(manifiesto: Manifiesto) -> frozenset[str]:
    """Qué copias inmutables, y sólo cuáles, viven bajo `<run>/inputs/`."""
    return frozenset(
        {
            f"{DIR_INPUTS}/consolidado_base.csv",
            f"{DIR_INPUTS}/consolidado_candidato.csv",
            *(f"{DIR_INPUTS}/boletines/{b.nombre}" for b in manifiesto.entrada.boletines),
        }
    )


def valida_inputs(manifiesto: Manifiesto) -> None:
    """P0.2: los inputs son copias con digest, y cada digest cuadra con lo que lo cita."""
    entrada = manifiesto.entrada
    if not entrada.entradas:
        raise StagingError("un sello sin inventario de entradas no dice sobre qué se preparó")
    consolidados = [
        ruta for ruta, meta in entrada.entradas.items() if meta.get("rol") == "consolidado"
    ]
    if len(consolidados) != 1:
        raise StagingError(
            "el inventario de entradas tiene que señalar exactamente un consolidado"
        )
    for ruta, meta in entrada.entradas.items():
        valida_ruta_entrada(ruta)
        if (
            not isinstance(meta, dict)
            or set(meta) != {"rol", "bytes", "sha256"}
            or not isinstance(meta["sha256"], str)
            or not _RE_SHA256.fullmatch(meta["sha256"])
        ):
            raise StagingError(f"entrada malformada en el manifiesto: {ruta}")
    esperadas = rutas_inputs(manifiesto)
    if set(manifiesto.inputs) != esperadas:
        raise StagingError(
            f"inputs no inventaría exactamente las copias esperadas: {sorted(manifiesto.inputs)}"
        )
    for rel, digest in manifiesto.inputs.items():
        if not isinstance(digest, str) or not _RE_SHA256.fullmatch(digest):
            raise StagingError(f"digest inválido en inputs para {rel}")
    base = manifiesto.inputs[f"{DIR_INPUTS}/consolidado_base.csv"]
    if entrada.digest_consolidado_antes != base:
        raise StagingError("digest_consolidado_antes no es el de la copia base sellada")
    if entrada.entradas[consolidados[0]]["sha256"] != base:
        raise StagingError("la copia base del consolidado no es la entrada hidratada")
    if (
        entrada.digest_consolidado_candidato
        != manifiesto.inputs[f"{DIR_INPUTS}/consolidado_candidato.csv"]
    ):
        raise StagingError("digest_consolidado_candidato no es el de la copia candidata sellada")
    nombres = [b.nombre for b in entrada.boletines]
    if len(set(nombres)) != len(nombres):
        raise StagingError("boletines repetidos en el sello")
    for boletin in entrada.boletines:
        if (
            not boletin.sha256
            or manifiesto.inputs[f"{DIR_INPUTS}/boletines/{boletin.nombre}"] != boletin.sha256
        ):
            raise StagingError(f"el boletín {boletin.nombre} no coincide con su copia sellada")


def verifica_inputs_en_disco(raiz_staging: Path, manifiesto: Manifiesto) -> None:
    """Lo que hay bajo `<staging>/inputs/` es exactamente lo que el manifiesto inventarió."""
    carpeta = raiz_staging / DIR_INPUTS
    _exige_directorio_real(carpeta, "las copias de entradas")
    presentes = {f"{DIR_INPUTS}/{rel}" for rel in _relativos(carpeta)}
    if faltan := sorted(set(manifiesto.inputs) - presentes):
        raise StagingError(f"faltan copias de entradas selladas: {faltan[:5]}")
    if sobran := sorted(presentes - set(manifiesto.inputs)):
        raise StagingError(f"hay copias de entradas fuera del inventario: {sobran[:5]}")
    alterados = sorted(
        rel for rel, digest in manifiesto.inputs.items() if sha256_de(raiz_staging / rel) != digest
    )
    if alterados:
        raise StagingError(f"copias de entradas alteradas después del sellado: {alterados[:5]}")


def calcula_run_id_de(manifiesto: Manifiesto) -> str:
    """SHA256 completo del payload que gobierna. La fecha NO entra.

    Antes se truncaba a 16 hex y sólo cubría entradas e inventario: versión, modo,
    baseline, lápidas, gates y operaciones DVC quedaban fuera del identificador aunque
    todas autorizan algo.
    """
    cuerpo = json.dumps(manifiesto.payload_canonico(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(cuerpo.encode()).hexdigest()


def calcula_baseline(destinos: dict[str, Path], rutas: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Estado actual del DESTINO para cada ruta administrada.

    Una ausencia se registra explícitamente: es la diferencia entre «esto no estaba» y
    «esto no lo miré», y de ella depende que una lápida no borre trabajo ajeno.
    """
    previo: dict[str, dict[str, Any]] = {}
    for rel in sorted(rutas):
        partes = valida_ruta_sellable(rel)
        raiz = destinos.get(partes[0])
        if raiz is None:
            raise StagingError(f"no hay destino declarado para '{partes[0]}' (ruta {rel})")
        objetivo = _destino_seguro(raiz, partes[1:])
        if not objetivo.exists():
            previo[rel] = {
                "presente": False,
                "tipo": None,
                "modo": None,
                "bytes": None,
                "sha256": None,
            }
            continue
        estado = objetivo.lstat()
        if not stat.S_ISREG(estado.st_mode):
            raise StagingError(f"la ruta administrada {rel} no es un archivo regular en destino")
        previo[rel] = {
            "presente": True,
            "tipo": "regular",
            "modo": stat.S_IMODE(estado.st_mode),
            "bytes": estado.st_size,
            "sha256": sha256_de(objetivo),
        }
    return previo


def _comprueba_baseline(manifiesto: Manifiesto, destinos: dict[str, Path]) -> None:
    """El destino tiene que estar como estaba al sellar. Se comprueba ANTES de tocar nada."""
    actual = calcula_baseline(destinos, manifiesto.baseline)
    if divergentes := sorted(rel for rel in actual if actual[rel] != manifiesto.baseline[rel]):
        raise StagingError(
            f"el destino cambió desde el sellado en {len(divergentes)} ruta(s): "
            f"{divergentes[:5]}. Un HEAD igual no garantiza un árbol igual."
        )


def inventaria(raiz_outputs: Path) -> dict[str, str]:
    """Digest de cada archivo producido, con rutas relativas al staging."""
    if not raiz_outputs.is_dir():
        raise StagingError(f"no existe el directorio de artefactos: {raiz_outputs}")
    return {str(rel): sha256_de(raiz_outputs / rel) for rel in _relativos(raiz_outputs)}


def sella(
    raiz_staging: Path,
    entrada: SelloEntrada,
    *,
    semilla: dict[str, str],
    baseline: dict[str, dict[str, Any]],
    politica: PoliticaCenso,
    autoridad_lapidas: AutoridadLapidas,
    tombstones: tuple[str, ...] = (),
    operaciones_dvc: tuple[str, ...] = (),
    contrato: Any = None,
) -> Manifiesto:
    """Inventaria lo producido, **calcula** la composición y escribe el manifiesto.

    La composición ya no la declara quien llama: se deriva de la semilla, lo cambiado y
    las lápidas. Antes era una cadena cualquiera, y hashear una afirmación falsa la vuelve
    íntegra, no verdadera.

    Los resultados de los gates tampoco se reciben: se releen de `<staging>/gates/`, que
    sólo escribe el runner, y tienen que apuntar a esta política y a esta composición. No
    hay parámetro para inyectarlos porque cualquier parámetro sería un JSON diciendo PASS.
    """
    outputs = raiz_staging / "outputs"
    inventario = inventaria(outputs)
    if not inventario and not tombstones:
        raise StagingError("el staging no contiene ningun artefacto; nada que sellar")
    for rel in inventario:
        valida_ruta_sellable(rel)
    # Una lápida con archivo presente en el staging la rechaza ya `valida_tombstones`: el
    # inventario ES lo presente, y una ruta inventariada y con lápida no tiene significado.
    valida_tombstones(tombstones, inventario)
    valida_autoridad_lapidas(tombstones, autoridad_lapidas, baseline, semilla)

    composicion, arbol = calcula_composicion(semilla, inventario, tombstones)
    politica.revisa_universos(arbol, tombstones)
    if fuera := sorted(set(tombstones) - politica.retirables):
        raise StagingError(f"la política no permite retirar: {fuera[:5]}")
    evidencia = EvidenciaGates.lee(raiz_staging)
    valida_gates(evidencia, politica, composicion)
    entrada = _completa_entrada(raiz_staging, entrada, contrato)
    inputs = {
        f"{DIR_INPUTS}/{rel}": sha256_de(raiz_staging / DIR_INPUTS / rel)
        for rel in _relativos(raiz_staging / DIR_INPUTS)
    }

    manifiesto = Manifiesto(
        run_id="",
        creado=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # Composición, política y gates coinciden, pero el sello sigue siendo BORRADOR
        # mientras P0.6 no confine la instalación a worktrees desechables. Verificado no es
        # instalable: son dos preguntas distintas y hoy sólo una tiene respuesta.
        modo=MODO_APLICABLE if CONFINAMIENTO_LISTO else MODO_DRAFT,
        motivo_draft="" if CONFINAMIENTO_LISTO else MOTIVO_P06,
        version_generador=VERSION_GENERADOR,
        entrada=entrada,
        inventario=inventario,
        baseline=baseline,
        tombstones=tuple(sorted(tombstones)),
        composicion=composicion,
        politica={"version": politica.version, "sha256": politica.sha256},
        operaciones_dvc=tuple(operaciones_dvc),
        resultados_pruebas=evidencia.como_manifiesto(),
        inputs=inputs,
    )
    valida_contrato(manifiesto)
    manifiesto.run_id = calcula_run_id_de(manifiesto)
    manifiesto.escribe(raiz_staging / "manifest.json")
    return manifiesto


def _completa_entrada(raiz_staging: Path, entrada: SelloEntrada, contrato: Any) -> SelloEntrada:
    """P0.2 y P0.8: la entrada se deriva de la hidratación; el candidato cumple el contrato.

    Lee `entradas.json`, exige que la copia base bajo `inputs/` sea la entrada hidratada,
    copia el consolidado candidato del sandbox a `inputs/` (en exclusiva; si ya está, tiene
    que ser idéntico), exige paridad de corte y cobertura sobre el candidato, y devuelve la
    entrada con digests, boletines e inventario. Nada de eso lo declara quien llama.
    """
    # Importación local: contratos_datos depende de este módulo para la excepción, y el
    # sello depende del contrato para el candidato. Una dirección en tiempo de carga.
    from epiforecast.publication.contratos_datos import (
        ContratoCobertura,
        exige_todo,
        revisa_candidato,
        revisa_consolidado,
    )
    from epiforecast.publication.contratos_datos import slug as slug_pad

    hidratacion = RegistroHidratacion.lee(raiz_staging)
    if hidratacion.head_backend != entrada.head_backend:
        raise StagingError(
            f"la hidratación se hizo sobre {hidratacion.head_backend[:12]} y se sella "
            f"{entrada.head_backend[:12]}"
        )
    inputs = raiz_staging / DIR_INPUTS
    _exige_directorio_real(inputs, "las copias de entradas")
    base = inputs / "consolidado_base.csv"
    if base.is_symlink() or not base.is_file():
        raise StagingError("falta inputs/consolidado_base.csv; la hidratación está incompleta")
    digest_base = sha256_de(base)
    if digest_base != hidratacion.entradas[hidratacion.consolidado]["sha256"]:
        raise StagingError("la copia base del consolidado no coincide con la entrada hidratada")

    origen_candidato = Path(hidratacion.sandbox) / hidratacion.consolidado
    if origen_candidato.is_symlink() or not origen_candidato.is_file():
        raise StagingError(f"no existe el consolidado candidato en el sandbox: {origen_candidato}")
    digest_candidato = sha256_de(origen_candidato)
    candidato = inputs / "consolidado_candidato.csv"
    if candidato.is_symlink():
        raise StagingError("inputs/consolidado_candidato.csv es un enlace simbólico")
    if candidato.exists():
        if sha256_de(candidato) != digest_candidato:
            raise StagingError(
                "inputs/consolidado_candidato.csv ya existe y no es el consolidado del sandbox"
            )
    else:
        _copia_exclusiva(origen_candidato, candidato, digest_candidato)

    for boletin in hidratacion.boletines:
        copia = inputs / "boletines" / boletin.nombre
        if copia.is_symlink() or not copia.is_file() or sha256_de(copia) != boletin.sha256:
            raise StagingError(f"la copia del boletín {boletin.nombre} falta o no coincide")

    contrato_real = contrato if contrato is not None else ContratoCobertura.canonico()
    # La paridad de corte se exige entre TODOS los publicados del contrato (registry), no
    # entre los que declare quien sella: declarar sólo «Dengue» no desactiva la paridad.
    declarados = {slug_pad(p) for p in entrada.padecimientos_autorizados}
    if fuera := sorted(declarados - set(contrato_real.padecimientos)):
        raise StagingError(f"padecimientos autorizados fuera del contrato: {fuera}")
    revisa_consolidado(candidato, contrato_real, contrato_real.padecimientos).exige()
    exige_todo(revisa_candidato(raiz_staging / "outputs" / "dashboard", contrato_real))

    return SelloEntrada(
        head_backend=entrada.head_backend,
        head_dashboard=entrada.head_dashboard,
        semana_anterior=entrada.semana_anterior,
        semana_nueva=entrada.semana_nueva,
        padecimientos_autorizados=entrada.padecimientos_autorizados,
        digest_consolidado_antes=digest_base,
        digest_consolidado_candidato=digest_candidato,
        boletines=hidratacion.boletines,
        entradas={r: dict(m) for r, m in hidratacion.entradas.items()},
    )


def verifica_sidecar(ruta_manifiesto: Path) -> None:
    """El manifiesto en disco tiene que coincidir con su `manifest.sha256`."""
    sidecar = ruta_manifiesto.with_name(ruta_manifiesto.stem + ".sha256")
    for ruta, que in ((ruta_manifiesto, "el manifiesto"), (sidecar, "el sidecar")):
        if ruta.is_symlink():
            raise StagingError(f"{que} es un enlace simbólico: {ruta}")
    if not sidecar.is_file():
        raise StagingError(
            f"falta el sidecar de integridad {sidecar.name}; el sello no está completo"
        )
    esperado = sidecar.read_text(encoding="utf-8").strip()
    real = hashlib.sha256(ruta_manifiesto.read_bytes()).hexdigest()
    if esperado != real:
        raise StagingError(
            f"el manifiesto no coincide con {sidecar.name}: fue editado o se corrompió"
        )


def verifica(
    raiz_staging: Path,
    manifiesto: Manifiesto,
    *,
    head_backend: str,
    head_dashboard: str,
) -> None:
    """Comprueba que lo que hay en disco es exactamente lo que se selló.

    Se niega ante cualquiera de estas cuatro situaciones, y las cuatro han ocurrido en
    la práctica o pueden ocurrir: que el repositorio haya avanzado desde el sellado, que
    un artefacto haya cambiado, que falte, o que aparezca uno que nadie inventarió.
    """
    if manifiesto.version_generador != VERSION_GENERADOR:
        raise StagingError(
            f"el staging lo generó {manifiesto.version_generador} y este es "
            f"{VERSION_GENERADOR}; regenéralo en vez de aplicarlo"
        )

    canonico = raiz_staging / "manifest.json"
    verifica_sidecar(canonico)
    if Manifiesto.lee(canonico).como_dict() != manifiesto.como_dict():
        raise StagingError(
            "el manifiesto recibido no es el que está sellado en disco; el sidecar cubre "
            f"{canonico.name}, así que aplicar otro objeto publicaría algo no revisado"
        )

    if head_backend != manifiesto.entrada.head_backend:
        raise StagingError(
            f"el backend avanzó desde el sellado: {manifiesto.entrada.head_backend[:12]} "
            f"-> {head_backend[:12]}. Lo revisado ya no es lo que se publicaría."
        )
    if head_dashboard != manifiesto.entrada.head_dashboard:
        raise StagingError(
            f"el dashboard avanzó desde el sellado: {manifiesto.entrada.head_dashboard[:12]} "
            f"-> {head_dashboard[:12]}. Lo revisado ya no es lo que se publicaría."
        )

    valida_contrato(manifiesto)
    if manifiesto.run_id != calcula_run_id_de(manifiesto):
        raise StagingError("el run_id no deriva del contenido del manifiesto")

    for rel in manifiesto.inventario:
        valida_ruta_sellable(rel)
    valida_tombstones(manifiesto.tombstones, manifiesto.inventario)

    outputs = raiz_staging / "outputs"
    presentes = {str(rel) for rel in _relativos(outputs)}
    inventariados = set(manifiesto.inventario)

    if faltan := sorted(inventariados - presentes):
        raise StagingError(f"faltan artefactos sellados: {faltan[:5]}")
    if sobran := sorted(presentes - inventariados):
        raise StagingError(f"hay artefactos fuera del inventario: {sobran[:5]}")

    alterados = [
        rel for rel, digest in manifiesto.inventario.items() if sha256_de(outputs / rel) != digest
    ]
    if alterados:
        raise StagingError(f"artefactos alterados despues del sellado: {sorted(alterados)[:5]}")

    verifica_evidencia_en_disco(raiz_staging, manifiesto)
    verifica_inputs_en_disco(raiz_staging, manifiesto)


def _instala(
    raiz_staging: Path,
    manifiesto: Manifiesto,
    destinos: dict[str, Path],
    *,
    head_backend: str,
    head_dashboard: str,
) -> list[str]:
    """Núcleo transaccional de la instalación. No regenera nada y no elige el destino.

    Es privado a propósito: la entrada pública es `release_worktrees.aplica`, que sólo
    admite el par de worktrees desechables registrado para el `run_id`. Aquí `destinos`
    mapea el primer segmento de cada ruta inventariada a su raíz real, de modo que el
    staging pueda contener artefactos de más de un repositorio.

    La instalación es transaccional en tres tiempos:

    1. **Copiar** todo a temporales contiguos. Un fallo aquí borra los temporales y deja
       el destino sin tocar.
    2. **Publicar** renombrando uno a uno, apartando antes el archivo previo. Renombrar
       es rápido pero no instantáneo para una lista larga: si el segundo renombrado
       falla, el primero ya quedó instalado. Por eso cada publicación recuerda qué
       reemplazó, y un fallo deshace en orden inverso todo lo ya publicado.
    3. **Limpiar** los apartados cuando ya no hacen falta.

    Así el destino queda con la versión nueva completa o con la anterior completa, nunca
    con una mezcla de las dos. Las lápidas del manifiesto se retiran en esa misma
    transacción, apartándolas primero y borrándolas sólo al final.
    """
    verifica(raiz_staging, manifiesto, head_backend=head_backend, head_dashboard=head_dashboard)
    if manifiesto.modo != MODO_APLICABLE:
        raise StagingError(
            f"el sello está en modo {manifiesto.modo!r} y no es aplicable. "
            f"{manifiesto.motivo_draft or 'No declara motivo.'} Sólo un sello "
            f"{MODO_APLICABLE!r} puede instalarse."
        )
    _comprueba_baseline(manifiesto, destinos)

    outputs = raiz_staging / "outputs"
    # Sufijos propios de esta corrida: un `.part` o un `.prev` genéricos son nombres
    # predecibles que otro proceso —o alguien— puede preplantar.
    marca = manifiesto.run_id[:12]
    sufijo_part = f".{marca}.part"
    sufijo_prev = f".{marca}.prev"
    pendientes: list[tuple[Path, Path]] = []

    try:
        for rel in sorted(manifiesto.inventario):
            partes = valida_ruta_sellable(rel)
            raiz = destinos.get(partes[0])
            if raiz is None:
                raise StagingError(
                    f"no hay destino declarado para '{partes[0]}' (artefacto {rel})"
                )
            destino = _destino_seguro(raiz, partes[1:])
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_name(destino.name + sufijo_part)
            _copia_exclusiva(outputs / rel, temporal, manifiesto.inventario[rel])
            pendientes.append((temporal, destino))
    except Exception:
        for temporal, _ in pendientes:
            temporal.unlink(missing_ok=True)
        raise

    # ── publicar, recordando en qué punto quedó cada archivo ───────────────
    #
    # Dos estados INDEPENDIENTES por ruta. Con un solo registro, un fallo antes de apartar
    # el original hacía que el rollback lo borrase —creyendo que había publicado algo— y
    # no tuviera ningún `.prev` que restaurar. El original se perdía por completo.
    publicados: list[_Transicion] = []
    retirados: list[_Transicion] = []
    try:
        for temporal, destino in pendientes:
            previo: Path | None = None
            if destino.exists():
                previo = destino.with_name(destino.name + sufijo_prev)
                _exige_libre(previo)
            transicion = _Transicion(destino=destino, previo=previo)
            publicados.append(transicion)
            if previo is not None:
                destino.replace(previo)
                transicion.apartado = True
            temporal.replace(destino)
            transicion.publicado = True

        # Las retiradas entran en la MISMA transacción: se apartan, y sólo se borran de
        # verdad cuando todo lo demás ya salió bien. Un archivo ausente no es un error:
        # la lápida declara el estado final, no una operación obligatoria.
        for rel in sorted(manifiesto.tombstones):
            partes = valida_ruta_sellable(rel)
            raiz = destinos.get(partes[0])
            if raiz is None:
                raise StagingError(f"no hay destino declarado para '{partes[0]}' (lápida {rel})")
            objetivo = _destino_seguro(raiz, partes[1:])
            if not objetivo.exists():
                continue
            aparte = objetivo.with_name(objetivo.name + sufijo_prev)
            _exige_libre(aparte)
            transicion = _Transicion(destino=objetivo, previo=aparte)
            retirados.append(transicion)
            objetivo.replace(aparte)
            transicion.apartado = True
    except Exception:
        for transicion in reversed(retirados + publicados):
            # Sólo se borra lo que de verdad se publicó, y sólo se restaura lo que de
            # verdad se apartó. Cualquier otra combinación destruiría el original.
            if transicion.publicado:
                transicion.destino.unlink(missing_ok=True)
            if transicion.apartado and transicion.previo is not None:
                transicion.previo.replace(transicion.destino)
        for temporal, _ in pendientes:
            temporal.unlink(missing_ok=True)
        raise

    for transicion in publicados + retirados:
        if transicion.previo is not None:
            transicion.previo.unlink(missing_ok=True)

    return sorted(manifiesto.inventario)


def snapshot_digests(raiz: Path) -> dict[str, str]:
    """Digest de cada archivo bajo `raiz`, con rutas relativas.

    Se toma antes de generar, sobre la semilla clonada del destino, para poder distinguir
    después qué produjo el refresh de lo que ya estaba ahí.
    """
    if not raiz.is_dir():
        return {}
    return {str(rel): sha256_de(raiz / rel) for rel in _relativos(raiz)}


def poda_a_cambiados(raiz_outputs: Path, semilla: dict[str, str]) -> Poda:
    """Deja en el staging solo lo que el refresh cambió o creó.

    El staging se siembra clonando el destino, porque varios generadores leen lo que ya
    existe. Sellarlo entero significaría inventariar y reinstalar los casi dos mil
    archivos del sitio en cada refresh, y un inventario así no dice nada: lo que hay que
    poder revisar es qué cambió esta semana.

    Devuelve lo que queda **y** lo que de verdad desapareció, censado ANTES de podar. Sin
    esa distinción, un artefacto intacto —que la poda retira por idéntico— era
    indistinguible de uno que un generador borró. Los directorios vacíos se retiran.
    """
    if not raiz_outputs.is_dir():
        raise StagingError(f"no existe el directorio de artefactos: {raiz_outputs}")

    presentes = {str(rel) for rel in _relativos(raiz_outputs)}
    eliminados = frozenset(semilla) - presentes

    conservados: dict[str, str] = {}
    for rel in _relativos(raiz_outputs):
        clave = str(rel)
        actual = sha256_de(raiz_outputs / rel)
        if semilla.get(clave) == actual:
            (raiz_outputs / rel).unlink()
        else:
            conservados[clave] = actual

    for directorio in sorted(
        (p for p in raiz_outputs.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        if not any(directorio.iterdir()):
            directorio.rmdir()

    return Poda(cambiados=conservados, eliminados_reales=eliminados)
