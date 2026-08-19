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

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

VERSION_GENERADOR = "weekly_staging/1"

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


def _relativos(raiz: Path) -> list[Path]:
    return sorted(p.relative_to(raiz) for p in raiz.rglob("*") if p.is_file())


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
    targets_dvc: tuple[str, ...] = TARGETS_DVC_PERMITIDOS
    resultados_pruebas: dict[str, Any] = field(default_factory=dict)

    def como_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "creado": self.creado,
            "modo": self.modo,
            "version_generador": self.version_generador,
            "entrada": self.entrada.como_dict(),
            "inventario": dict(sorted(self.inventario.items())),
            "targets_dvc": list(self.targets_dvc),
            "resultados_pruebas": self.resultados_pruebas,
        }

    def escribe(self, destino: Path) -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(destino.name + ".part")
        try:
            temporal.write_text(
                json.dumps(self.como_dict(), indent=2, ensure_ascii=False, sort_keys=False),
                encoding="utf-8",
            )
            temporal.replace(destino)
        finally:
            temporal.unlink(missing_ok=True)

    @staticmethod
    def lee(ruta: Path) -> Manifiesto:
        if not ruta.is_file():
            raise StagingError(f"no existe el manifiesto: {ruta}")
        try:
            crudo = json.loads(ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StagingError(f"manifiesto ilegible: {exc}") from exc

        faltantes = {
            "run_id",
            "creado",
            "modo",
            "version_generador",
            "entrada",
            "inventario",
            "targets_dvc",
        } - set(crudo)
        if faltantes:
            raise StagingError(f"manifiesto incompleto, faltan claves: {sorted(faltantes)}")

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
        return Manifiesto(
            run_id=crudo["run_id"],
            creado=crudo["creado"],
            modo=crudo["modo"],
            version_generador=crudo["version_generador"],
            entrada=entrada,
            inventario=dict(crudo["inventario"]),
            targets_dvc=tuple(crudo["targets_dvc"]),
            resultados_pruebas=crudo.get("resultados_pruebas", {}),
        )


def calcula_run_id(entrada: SelloEntrada, inventario: dict[str, str]) -> str:
    """Deriva el identificador de las entradas y de lo producido.

    Dos preparaciones con las mismas entradas y las mismas salidas comparten
    identificador, lo que hace comprobable la reproducibilidad. La fecha NO entra: si
    entrase, dos corridas idénticas parecerían distintas.
    """
    cuerpo = json.dumps(
        {"entrada": entrada.como_dict(), "inventario": dict(sorted(inventario.items()))},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(cuerpo.encode()).hexdigest()[:16]


def inventaria(raiz_outputs: Path) -> dict[str, str]:
    """Digest de cada archivo producido, con rutas relativas al staging."""
    if not raiz_outputs.is_dir():
        raise StagingError(f"no existe el directorio de artefactos: {raiz_outputs}")
    return {str(rel): sha256_de(raiz_outputs / rel) for rel in _relativos(raiz_outputs)}


def sella(
    raiz_staging: Path,
    entrada: SelloEntrada,
    *,
    resultados_pruebas: dict[str, Any] | None = None,
) -> Manifiesto:
    """Inventaria lo producido y escribe el manifiesto dentro del propio staging."""
    outputs = raiz_staging / "outputs"
    inventario = inventaria(outputs)
    if not inventario:
        raise StagingError("el staging no contiene ningun artefacto; nada que sellar")

    manifiesto = Manifiesto(
        run_id=calcula_run_id(entrada, inventario),
        creado=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        modo="staged",
        version_generador=VERSION_GENERADOR,
        entrada=entrada,
        inventario=inventario,
        resultados_pruebas=resultados_pruebas or {},
    )
    manifiesto.escribe(raiz_staging / "manifest.json")
    return manifiesto


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

    for target in manifiesto.targets_dvc:
        if target not in TARGETS_DVC_PERMITIDOS:
            raise StagingError(f"objetivo DVC no permitido en el manifiesto: {target}")

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

    La instalación es transaccional en dos tiempos: primero se copian TODOS los artefactos
    a temporales contiguos, y solo cuando todos están en su sitio se renombran. Copiar y
    renombrar de uno en uno dejaría el destino a medio publicar si algo falla a mitad de
    la lista, que es precisamente el estado que nadie sabe cómo deshacer.
    """
    verifica(raiz_staging, manifiesto, head_backend=head_backend, head_dashboard=head_dashboard)

    outputs = raiz_staging / "outputs"
    pendientes: list[tuple[Path, Path]] = []

    try:
        for rel in sorted(manifiesto.inventario):
            partes = Path(rel).parts
            raiz = destinos.get(partes[0])
            if raiz is None:
                raise StagingError(
                    f"no hay destino declarado para '{partes[0]}' (artefacto {rel})"
                )
            destino = raiz.joinpath(*partes[1:])
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_name(destino.name + ".part")
            shutil.copy2(outputs / rel, temporal)
            pendientes.append((temporal, destino))
    except Exception:
        for temporal, _ in pendientes:
            temporal.unlink(missing_ok=True)
        raise

    for temporal, destino in pendientes:
        temporal.replace(destino)
    return sorted(manifiesto.inventario)
