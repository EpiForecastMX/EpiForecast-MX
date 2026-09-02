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

# v2 = el sello empieza a gobernar de verdad: rutas con gramática cerrada, sidecar de
# integridad y escrituras que no siguen enlaces. Las nueve corridas `weekly_staging/1` de
# `runs/_refresh/` quedan históricas y NO aplicables: no traen sidecar, y anunciarlo por
# la versión es justo lo que evita que un v1 se rechace por un motivo que no declara.
VERSION_GENERADOR = "weekly_staging/2"

# Único espacio de nombres sellable. Toda ruta del inventario cuelga de uno de estos dos
# prefijos, que `aplica` traduce a la raíz del repositorio correspondiente.
PREFIJOS_SELLABLES: tuple[str, ...] = ("backend", "dashboard")

# Objetivos DVC que el refresh semanal puede versionar. El versionado global arrastraba
# artefactos de modelos de carriles sin autorizar; esta lista es la frontera.
TARGETS_DVC_PERMITIDOS: tuple[str, ...] = (
    "data/processed/dataset_boletin_epidemiologico.csv.dvc",
)


class StagingError(RuntimeError):
    """El staging no puede sellarse o aplicarse tal como está."""


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
    """Lo que había ANTES de generar: si esto cambia, el sello deja de valer."""

    head_backend: str
    head_dashboard: str
    digest_consolidado: str
    semana_anterior: str
    semana_nueva: str
    padecimientos_autorizados: tuple[str, ...]
    boletines: tuple[Boletin, ...] = ()

    def como_dict(self) -> dict[str, Any]:
        return {
            "head_backend": self.head_backend,
            "head_dashboard": self.head_dashboard,
            "digest_consolidado": self.digest_consolidado,
            "semana_anterior": self.semana_anterior,
            "semana_nueva": self.semana_nueva,
            "padecimientos_autorizados": list(self.padecimientos_autorizados),
            "boletines": [b.como_dict() for b in self.boletines],
        }


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
        }

    def payload_canonico(self) -> dict[str, Any]:
        """Todo lo que gobierna una acción entra en el identificador.

        Queda fuera sólo `creado`, que es informativo — y por eso el sidecar cubre el JSON
        entero, ese campo incluido.
        """
        cuerpo = self.como_dict()
        cuerpo.pop("run_id")
        cuerpo.pop("creado")
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
        }
        if faltantes := esperadas - set(crudo):
            raise StagingError(f"manifiesto incompleto, faltan claves: {sorted(faltantes)}")
        if sobrantes := set(crudo) - esperadas:
            raise StagingError(f"manifiesto con claves desconocidas: {sorted(sobrantes)}")

        e = crudo["entrada"]
        entrada = SelloEntrada(
            head_backend=e["head_backend"],
            head_dashboard=e["head_dashboard"],
            digest_consolidado=e["digest_consolidado"],
            semana_anterior=e["semana_anterior"],
            semana_nueva=e["semana_nueva"],
            padecimientos_autorizados=tuple(e["padecimientos_autorizados"]),
            boletines=tuple(Boletin(**b) for b in e.get("boletines", [])),
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
    Un lector no puede recomprobar la autorización; se comprueba al sellar. Ligar el digest
    de la política al sello es trabajo del censo (P0.9).
    """

    eliminados_reales: frozenset[str]
    allowlist: frozenset[str]

    @staticmethod
    def sin_lapidas() -> AutoridadLapidas:
        """Para sellos que no retiran nada. No autoriza ninguna retirada."""
        return AutoridadLapidas(eliminados_reales=frozenset(), allowlist=frozenset())


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
    gates: tuple[str, ...]

    CLAVES = (
        "version",
        "prefijos_administrados",
        "patron_superficie",
        "superficies_verificables",
        "retirables",
        "gates",
    )

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
        if not isinstance(patron["prefijo"], str) or not patron["prefijo"].endswith("/"):
            raise StagingError(
                f"el prefijo publicado tiene que terminar en '/': {patron['prefijo']!r}"
            )

        listas = {
            "prefijos_administrados": crudo["prefijos_administrados"],
            "superficies_verificables": crudo["superficies_verificables"],
            "retirables": crudo["retirables"],
            "gates": crudo["gates"],
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
        if not crudo["gates"]:
            raise StagingError("la política no declara ningún gate; un sello sin gates no vale")
        if any(not nombre.strip() for nombre in crudo["gates"]):
            raise StagingError("hay un gate sin nombre")
        for prefijo in crudo["prefijos_administrados"]:
            _valida_prefijo(prefijo, "prefijo administrado")
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
        prefijos = tuple(crudo["prefijos_administrados"])
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
            gates=tuple(crudo["gates"]),
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


def valida_gates(resultados: dict[str, Any], politica: PoliticaCenso, composicion: str) -> None:
    """El conjunto de gates es exacto, y cada resultado apunta a ESTA composición.

    Si un byte cambia después de correr los gates, la composición recalculada deja de
    coincidir con la que declararon y el sello aborta: recomponer obliga a repetirlos.
    """
    esperados = set(politica.gates)
    if faltan := sorted(esperados - set(resultados)):
        raise StagingError(f"faltan resultados de gates que la política exige: {faltan}")
    if sobran := sorted(set(resultados) - esperados):
        raise StagingError(f"hay resultados de gates que la política no declara: {sobran}")
    for nombre in sorted(esperados):
        resultado = resultados[nombre]
        if not isinstance(resultado, dict):
            raise StagingError(f"el resultado del gate {nombre} no es un objeto")
        if resultado.get("veredicto") != VEREDICTO_REQUERIDO:
            raise StagingError(
                f"el gate {nombre} declara {resultado.get('veredicto')!r} y se exige "
                f"{VEREDICTO_REQUERIDO}"
            )
        if resultado.get("composicion") != composicion:
            raise StagingError(
                f"el gate {nombre} se corrió sobre la composición "
                f"{str(resultado.get('composicion'))[:12]}… y el candidato es {composicion[:12]}…: "
                "algo cambió después de los gates; recompón y vuelve a correrlos"
            )


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
# alguien los declaró. Mientras P0.9 no exista, `sella` produce borradores.
MODO_APLICABLE = "aplicable"
MODO_DRAFT = "draft"
MOTIVO_P06 = (
    "P0.6 pendiente: apply todavía admite destinos arbitrarios y no exige worktrees "
    "desechables. Verificar el sello y poder instalarlo son dos cosas distintas."
)
# Se enciende junto con el confinamiento de P0.6, no antes. Es la única palanca que
# convierte un sello verificado en instalable, y está aquí para que se vea de un vistazo.
CONFINAMIENTO_LISTO = False


def valida_contrato(manifiesto: Manifiesto) -> None:
    """Contrato de `weekly_staging/2`: nada que autorice una acción puede faltar.

    Una versión distinta no se juzga aquí: la rechaza `verifica()` con su propio mensaje,
    que dice qué hacer.
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

    if not manifiesto.resultados_pruebas:
        raise StagingError("un sello sin resultados de gates no autoriza nada")
    for nombre, resultado in sorted(manifiesto.resultados_pruebas.items()):
        if not isinstance(resultado, dict):
            raise StagingError(f"el resultado del gate {nombre} no es un objeto")
        if resultado.get("veredicto") != VEREDICTO_REQUERIDO:
            raise StagingError(
                f"el gate {nombre} declara {resultado.get('veredicto')!r} y se exige "
                f"{VEREDICTO_REQUERIDO}"
            )
        if resultado.get("composicion") != manifiesto.composicion:
            raise StagingError(
                f"el gate {nombre} no apunta a la composición del sello; se corrió sobre otro árbol"
            )
    for boletin in manifiesto.entrada.boletines:
        if not boletin.sha256:
            raise StagingError(f"el boletín {boletin.nombre} no trae digest")


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
    resultados_pruebas: dict[str, Any],
    politica: PoliticaCenso,
    autoridad_lapidas: AutoridadLapidas,
    tombstones: tuple[str, ...] = (),
    operaciones_dvc: tuple[str, ...] = (),
) -> Manifiesto:
    """Inventaria lo producido, **calcula** la composición y escribe el manifiesto.

    La composición ya no la declara quien llama: se deriva de la semilla, lo cambiado y
    las lápidas. Antes era una cadena cualquiera, y hashear una afirmación falsa la vuelve
    íntegra, no verdadera.
    """
    outputs = raiz_staging / "outputs"
    inventario = inventaria(outputs)
    if not inventario and not tombstones:
        raise StagingError("el staging no contiene ningun artefacto; nada que sellar")
    for rel in inventario:
        valida_ruta_sellable(rel)
    valida_tombstones(tombstones, inventario)
    valida_autoridad_lapidas(tombstones, autoridad_lapidas, baseline, semilla)
    for rel in tombstones:
        if (outputs / rel).exists():
            raise StagingError(
                f"la lápida {rel} tiene un archivo presente en el staging; una lápida es "
                "una ausencia declarada, no un artefacto"
            )

    composicion, arbol = calcula_composicion(semilla, inventario, tombstones)
    politica.revisa_universos(arbol, tombstones)
    if fuera := sorted(set(tombstones) - politica.retirables):
        raise StagingError(f"la política no permite retirar: {fuera[:5]}")
    valida_gates(resultados_pruebas, politica, composicion)

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
        resultados_pruebas=resultados_pruebas,
    )
    valida_contrato(manifiesto)
    manifiesto.run_id = calcula_run_id_de(manifiesto)
    manifiesto.escribe(raiz_staging / "manifest.json")
    return manifiesto


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


def aplica(
    raiz_staging: Path,
    manifiesto: Manifiesto,
    destinos: dict[str, Path],
    *,
    head_backend: str,
    head_dashboard: str,
) -> list[str]:
    """Instala los bytes sellados. No regenera nada.

    `destinos` mapea el primer segmento de cada ruta inventariada a su raíz real, de modo
    que el staging pueda contener artefactos de más de un repositorio.

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
            f"el sello está en modo {manifiesto.modo!r} y no es aplicable: su composición y "
            "sus gates los declara quien sella, nadie los ha recomputado. Sólo un sello "
            f"{MODO_APLICABLE!r}, producido con la composición verificada, puede instalarse."
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
