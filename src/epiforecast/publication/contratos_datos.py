"""Contratos exactos de cobertura de datos: conjuntos, unicidad y paridad de corte.

Una hidratación corta no hace fallar a los generadores: los hace producir un candidato
más pequeño y plausible. Y una sustitución que conserve el conteo pasa cualquier control
que cuente. Por eso el contrato no son las cifras 333/99/432/444 —esas se informan— sino
los **conjuntos exactos**: qué padecimientos, qué entidades, qué sexos, y por tanto qué
claves tienen que existir, ni una más ni una menos, sin duplicados y con el mismo corte
semanal en todos los padecimientos publicados.

La identidad de una entidad no es su ortografía: `México`, `Estado de México` y `mexico`
son la misma, y el catálogo geográfico rastreado (`config/geografia/entidades_mx.csv`) es
quien lo dice. Los padecimientos publicados salen del registry; las regiones, de
`constants.INEGI_REGIONS`. No hay lista escrita a mano aquí.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any
import unicodedata

import pandas as pd

from epiforecast import registry
from epiforecast.constants import INEGI_REGIONS
from epiforecast.data.epi_calendar import shift as semana_siguiente
from epiforecast.publication.errores import StagingError

SEXOS: tuple[str, ...] = ("general", "hombres", "mujeres")
NACIONAL = "nacional"
_REPO = Path(__file__).resolve().parents[3]
CATALOGO_ENTIDADES = _REPO / "config" / "geografia" / "entidades_mx.csv"
RUTA_CATALOGO = "config/geografia/entidades_mx.csv"
RUTA_REGISTRY = "config/padecimientos.yaml"
RUTA_LISTA = "config/publication/entradas_semanales.json"
MOTORES_LEGACY: tuple[str, ...] = ("prophet", "deepar", "ensemble", "stacking")
PROFUNDIDAD_MINIMA_POR_DEFECTO = 52
# Columnas del consolidado cuyos valores, una vez publicados, no pueden cambiar en silencio.
COLUMNAS_VALOR = (
    "Casos_semana",
    "Acumulado_hombres",
    "Acumulado_mujeres",
    "Acumulado_anio_anterior",
)

# Rutas de los datos que gobierna el contrato, relativas a la raíz del backend.
RUTA_CONSOLIDADO = "data/processed/dataset_boletin_epidemiologico.csv"
RUTA_TABLA_PRODUCCION = "reports/ProdDetails/tabla_333_modelos_produccion.xlsx"
RUTA_PRODUCCION_DENGUE = "reports/ProdDetails/produccion_dengue.csv"
DIR_FORECASTS = "reports/forecasts"

Clave = tuple[str, str, str]


def slug(texto: Any) -> str:
    """Minúsculas, sin acentos ni puntuación: `Depresión` -> `depresion`."""
    plano = unicodedata.normalize("NFKD", str(texto))
    plano = "".join(c for c in plano if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", plano).strip()


@dataclass(frozen=True)
class ContratoCobertura:
    """Los conjuntos que un candidato completo tiene que cubrir exactamente."""

    neuro: tuple[str, ...]
    conteo: tuple[str, ...]
    entidades: tuple[str, ...]
    alias: Mapping[str, str]
    regiones: tuple[str, ...]
    # Semanas que el consolidado tiene que traer por padecimiento, contiguas al corte. No
    # es una ventana «relativa» que se conforma con lo que haya: es un mínimo absoluto.
    profundidad_minima: int = PROFUNDIDAD_MINIMA_POR_DEFECTO

    @property
    def padecimientos(self) -> tuple[str, ...]:
        return self.neuro + self.conteo

    def entidad_canonica(self, nombre: Any) -> str | None:
        """Slug canónico de una entidad, región o del agregado nacional; None si no es nada."""
        s = slug(nombre)
        if s in self.entidades:
            return s
        if s in self.alias:
            return self.alias[s]
        if s == NACIONAL:
            return NACIONAL
        if s.startswith("region "):
            region = s.removeprefix("region ").strip()
            if region in self.regiones:
                return f"region {region}"
        return None

    def productos(self, padecimiento: str) -> frozenset[Clave]:
        """Claves (padecimiento, entidad, sexo) esperadas para un padecimiento."""
        pad = slug(padecimiento)
        if pad in self.neuro:
            entidades = (*self.entidades, NACIONAL, *(f"region {r}" for r in self.regiones))
        elif pad in self.conteo:
            entidades = (*self.entidades, NACIONAL)
        else:
            raise StagingError(f"padecimiento fuera del contrato: {padecimiento!r}")
        return frozenset((pad, e, sexo) for e in entidades for sexo in SEXOS)

    def claves_esperadas(self) -> frozenset[Clave]:
        """Todas las series productivas: 3×111 neuro + 99 Dengue = 432 en el contrato real."""
        return frozenset().union(*(self.productos(p) for p in self.padecimientos))

    def zoom_esperado(self) -> frozenset[Clave]:
        """La galería/zoom deriva regiones también para los de conteo: 4×111 = 444."""
        entidades = (*self.entidades, NACIONAL, *(f"region {r}" for r in self.regiones))
        return frozenset(
            (pad, e, sexo) for pad in self.padecimientos for e in entidades for sexo in SEXOS
        )

    @staticmethod
    def canonico(catalogo: Path = CATALOGO_ENTIDADES) -> ContratoCobertura:
        """Del registry (publicados), el catálogo geográfico rastreado y las regiones INEGI."""
        return ContratoCobertura.desde_catalogo(catalogo.read_text(encoding="utf-8"))

    @staticmethod
    def del_head(repo: Path, head: str) -> ContratoCobertura:
        """Catálogo geográfico, registry y profundidad mínima, leídos del HEAD que se sella.

        Igual que la política: nada de lo que gobierna el contrato viene de un archivo
        suelto ni del proceso. Los padecimientos publicados salen del `padecimientos.yaml`
        de ESE commit (no del registry cacheado del intérprete, que es el del worktree), y
        la profundidad mínima, de la allowlist de entradas del mismo commit. Cada archivo
        tiene que coincidir byte a byte con el árbol de trabajo.
        """
        catalogo = _blob_del_head(repo, head, RUTA_CATALOGO, "el catálogo geográfico")
        yaml_registry = _blob_del_head(repo, head, RUTA_REGISTRY, "el registry de padecimientos")
        lista = _blob_del_head(repo, head, RUTA_LISTA, "la lista de entradas")
        with tempfile.NamedTemporaryFile("wb", suffix=".yaml", delete=False) as tmp:
            tmp.write(yaml_registry)
            ruta_tmp = Path(tmp.name)
        try:
            registro = registry.load_registry(ruta_tmp)
        except Exception as exc:  # RegistryError, YAML, ...: un registry ilegible no gobierna
            raise StagingError(f"el registry de {head[:12]} no se puede cargar: {exc}") from exc
        finally:
            ruta_tmp.unlink(missing_ok=True)
        return ContratoCobertura.desde_catalogo(
            catalogo.decode("utf-8"),
            registro=registro,
            profundidad_minima=_profundidad_de_la_lista(lista),
        )

    @staticmethod
    def desde_catalogo(
        texto: str,
        *,
        registro: Any = None,
        profundidad_minima: int = PROFUNDIDAD_MINIMA_POR_DEFECTO,
    ) -> ContratoCobertura:
        entidades: list[str] = []
        alias: dict[str, str] = {}
        for fila in csv.DictReader(texto.splitlines()):
            canonico = slug(fila["nombre_canonico"])
            entidades.append(canonico)
            for nombre in (fila.get("nombre_inegi", ""), *fila.get("aliases", "").split("|")):
                s = slug(nombre)
                if not s or s == canonico:
                    continue
                if s in alias and alias[s] != canonico:
                    raise StagingError(
                        f"catálogo geográfico ambiguo: el alias {nombre!r} apunta a "
                        f"{alias[s]!r} y a {canonico!r}"
                    )
                alias[s] = canonico
        if len(set(entidades)) != len(entidades) or not entidades:
            raise StagingError("catálogo geográfico con entidades duplicadas o vacío")
        if colision := sorted(set(alias) & set(entidades)):
            raise StagingError(
                f"catálogo geográfico ambiguo: alias que son también entidades: {colision[:3]}"
            )
        if registro is None:
            registro = registry.get_registry()
        publicados = [d for d in registro.diseases if d.lifecycle == "published"]
        return ContratoCobertura(
            neuro=tuple(slug(d.data_name) for d in publicados if d.batch == "General"),
            conteo=tuple(slug(d.data_name) for d in publicados if d.batch != "General"),
            entidades=tuple(entidades),
            alias=alias,
            regiones=tuple(slug(r) for r in INEGI_REGIONS),
            profundidad_minima=profundidad_minima,
        )


def _blob_del_head(repo: Path, head: str, rel: str, que: str) -> bytes:
    """Bytes de `rel` en `head`, exigiendo que el árbol de trabajo lleve exactamente lo mismo."""
    salida = subprocess.run(["git", "-C", str(repo), "show", f"{head}:{rel}"], capture_output=True)
    if salida.returncode != 0:
        raise StagingError(
            f"{que} {rel} no está en {head[:12]}: {salida.stderr.decode(errors='replace').strip()}"
        )
    ruta = repo / rel
    if ruta.is_symlink() or not ruta.is_file() or ruta.read_bytes() != salida.stdout:
        raise StagingError(f"{que} {rel} difiere de la versión de {head[:12]}")
    return salida.stdout


def _profundidad_de_la_lista(crudo: bytes) -> int:
    """`profundidad_minima_semanas` de la allowlist; la forma completa la valida `hidratacion`."""
    try:
        lista = json.loads(crudo)
    except json.JSONDecodeError as exc:
        raise StagingError(f"lista de entradas ilegible: {exc}") from exc
    valor = lista.get("profundidad_minima_semanas") if isinstance(lista, dict) else None
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise StagingError(
            "la lista de entradas tiene que declarar profundidad_minima_semanas (entero >= 1)"
        )
    return valor


@dataclass(frozen=True)
class Cobertura:
    """Resultado de un control: cifras informativas y problemas. Sin problemas es PASS."""

    fuente: str
    cifras: Mapping[str, Any]
    problemas: tuple[str, ...]

    @property
    def pasa(self) -> bool:
        return not self.problemas

    def exige(self) -> Cobertura:
        if self.problemas:
            raise StagingError(
                f"cobertura de {self.fuente} fuera de contrato:\n  - "
                + "\n  - ".join(self.problemas)
            )
        return self


def _compara_conjuntos(
    fuente: str, observadas: Iterable[Clave], esperadas: frozenset[Clave]
) -> tuple[list[str], dict[str, Any]]:
    """Faltantes, sobrantes y duplicados, con los primeros ejemplos de cada uno."""
    conteo = Counter(observadas)
    problemas: list[str] = []
    if faltan := sorted(esperadas - set(conteo)):
        problemas.append(f"{fuente}: faltan {len(faltan)} clave(s) del contrato: {faltan[:5]}")
    if sobran := sorted(set(conteo) - esperadas):
        problemas.append(f"{fuente}: {len(sobran)} clave(s) fuera del contrato: {sobran[:5]}")
    if duplicadas := sorted(k for k, n in conteo.items() if n > 1):
        problemas.append(f"{fuente}: {len(duplicadas)} clave(s) duplicadas: {duplicadas[:5]}")
    return problemas, {"claves": len(conteo), "esperadas": len(esperadas)}


def _clave(contrato: ContratoCobertura, pad: Any, entidad: Any, sexo: Any) -> Clave:
    canon = contrato.entidad_canonica(entidad)
    return (slug(pad), canon if canon is not None else f"?{slug(entidad)}", slug(sexo))


def revisa_consolidado(
    ruta: Path,
    contrato: ContratoCobertura,
    padecimientos_autorizados: Iterable[str],
    *,
    ventana_semanas: int = 52,
) -> Cobertura:
    """Paridad de corte entre los publicados, 32 entidades exactas por semana y unicidad.

    Se revisan las últimas `ventana_semanas` semanas de cada padecimiento autorizado: es la
    ventana que consumen los generadores del sitio. Un padecimiento autorizado ausente del
    consolidado es un problema, no un cero.
    """
    autorizados = {slug(p) for p in padecimientos_autorizados}
    if fuera := sorted(autorizados - set(contrato.padecimientos)):
        raise StagingError(f"padecimientos autorizados fuera del contrato: {fuera}")
    df = pd.read_csv(ruta, usecols=["Anio", "Semana", "Entidad", "Padecimiento"], low_memory=False)
    df["pad"] = df["Padecimiento"].map(slug)
    df = df[df["pad"].isin(autorizados)]
    problemas: list[str] = []
    if ausentes := sorted(autorizados - set(df["pad"])):
        problemas.append(f"consolidado: sin filas para {ausentes}")

    cortes: dict[str, tuple[int, int]] = {}
    profundidad: dict[str, int] = {}
    huecos_historicos: dict[str, int] = {}
    esperadas = frozenset(contrato.entidades)
    minimo = contrato.profundidad_minima
    for pad, grupo in df.groupby("pad"):
        semanas = sorted(
            {(int(a), int(s)) for a, s in zip(grupo["Anio"], grupo["Semana"], strict=True)}
        )
        cortes[str(pad)] = semanas[-1]
        profundidad[str(pad)] = len(semanas)
        # Profundidad absoluta y continuidad MMWR de las últimas `minimo` semanas: un
        # consolidado truncado, o con una semana saltada junto al corte, no es «corto», es
        # otro dato. Los huecos anteriores (boletines históricos ilegibles) se informan.
        if len(semanas) < minimo:
            problemas.append(
                f"consolidado {pad}: {len(semanas)} semana(s), y el contrato exige al menos "
                f"{minimo} contiguas hasta el corte"
            )
        recientes = semanas[-minimo:]
        if saltos := [
            (a, b) for a, b in zip(recientes, recientes[1:], strict=False) if _siguiente(a) != b
        ]:
            problemas.append(
                f"consolidado {pad}: hueco(s) en las últimas {minimo} semanas: {saltos[:3]}"
            )
        anteriores = semanas[: len(semanas) - minimo + 1]
        huecos_historicos[str(pad)] = sum(
            1 for a, b in zip(anteriores, anteriores[1:], strict=False) if _siguiente(a) != b
        )
        for anio, semana in semanas[-ventana_semanas:]:
            fila = grupo[(grupo["Anio"] == anio) & (grupo["Semana"] == semana)]
            canonicas = [contrato.entidad_canonica(e) for e in fila["Entidad"]]
            if desconocidas := sorted(
                {str(e) for e, c in zip(fila["Entidad"], canonicas, strict=True) if c is None}
            ):
                problemas.append(
                    f"consolidado {pad} {anio}-W{semana}: entidades fuera del catálogo {desconocidas[:5]}"
                )
            conteo = Counter(c for c in canonicas if c is not None)
            if duplicadas := sorted(e for e, n in conteo.items() if n > 1):
                problemas.append(
                    f"consolidado {pad} {anio}-W{semana}: entidades duplicadas {duplicadas[:5]}"
                )
            if faltan := sorted(esperadas - set(conteo)):
                problemas.append(
                    f"consolidado {pad} {anio}-W{semana}: faltan entidades {faltan[:5]}"
                )
            if sobran := sorted(set(conteo) - esperadas):
                problemas.append(
                    f"consolidado {pad} {anio}-W{semana}: entidades no estatales {sobran[:5]}"
                )
    if len(set(cortes.values())) > 1:
        problemas.append(f"consolidado: corte dispar entre publicados {cortes}")
    return Cobertura(
        "consolidado",
        {
            "cortes": cortes,
            "filas": int(len(df)),
            "semanas": profundidad,
            "huecos_historicos": huecos_historicos,
        },
        tuple(problemas),
    )


def _siguiente(semana: tuple[int, int]) -> tuple[int, int]:
    """La semana MMWR que sigue a `semana`; si la semana no es válida, una que nunca casa."""
    try:
        return semana_siguiente(semana[0], semana[1], 1)
    except ValueError:
        return (-1, -1)


def revisa_aditivo(
    base: Path,
    candidato: Path,
    contrato: ContratoCobertura,
    padecimientos_autorizados: Iterable[str],
) -> Cobertura:
    """El candidato CONTIENE la base, fila a fila y con los mismos valores. Sólo añade.

    Es el ancla absoluta: la profundidad mínima dice cuánto hay que traer, esto dice que lo
    ya publicado sigue ahí, intacto. Una corrección de una fila ya publicada no se cuela
    en un refresh semanal; se declara y se sella aparte.
    """
    autorizados = {slug(p) for p in padecimientos_autorizados}
    claves = ["Anio", "Semana", "Entidad", "Padecimiento"]
    columnas_base = list(pd.read_csv(base, nrows=0).columns)
    columnas_cand = list(pd.read_csv(candidato, nrows=0).columns)
    valores = [c for c in COLUMNAS_VALOR if c in columnas_base and c in columnas_cand]
    problemas: list[str] = []
    if faltan_columnas := [c for c in columnas_base if c not in columnas_cand]:
        problemas.append(f"el candidato perdió columnas del consolidado base: {faltan_columnas}")

    def carga(ruta: Path) -> pd.DataFrame:
        df = pd.read_csv(ruta, usecols=claves + valores, low_memory=False)
        df["pad"] = df["Padecimiento"].map(slug)
        df = df[df["pad"].isin(autorizados)].copy()
        df["ent"] = df["Entidad"].map(lambda e: contrato.entidad_canonica(e) or f"?{slug(e)}")
        return df.set_index(["pad", "Anio", "Semana", "ent"])[valores]

    df_base, df_cand = carga(base), carga(candidato)
    if df_base.index.has_duplicates or df_cand.index.has_duplicates:
        problemas.append("filas duplicadas por clave (padecimiento, año, semana, entidad)")
        return Cobertura("aditivo", {"filas_base": int(len(df_base))}, tuple(problemas))
    faltan = df_base.index.difference(df_cand.index)
    if len(faltan):
        problemas.append(
            f"el candidato perdió {len(faltan)} fila(s) de la base: {list(faltan[:3])}"
        )
    comunes = df_base.index.intersection(df_cand.index)
    b, c = df_base.loc[comunes], df_cand.loc[comunes]
    iguales = (b == c) | (b.isna() & c.isna())
    if not iguales.all().all():
        cambiadas = comunes[~iguales.all(axis=1)]
        problemas.append(
            f"el candidato cambió {len(cambiadas)} fila(s) ya publicadas: {list(cambiadas[:3])}"
        )
    return Cobertura(
        "aditivo",
        {"filas_base": int(len(df_base)), "filas_nuevas": int(len(df_cand) - len(comunes))},
        tuple(problemas),
    )


def revisa_forecasts(
    directorio: Path, contrato: ContratoCobertura, motores: tuple[str, ...] = MOTORES_LEGACY
) -> Cobertura:
    """Cada motor legacy trae exactamente las 432 series del contrato."""
    return revisa_forecasts_listados(
        [directorio / motor / f"all_forecast_{motor}.csv" for motor in motores], contrato
    )


def revisa_forecasts_listados(
    rutas: Iterable[Path],
    contrato: ContratoCobertura,
    *,
    esperadas: frozenset[Clave] | None = None,
    fuente: str = "forecasts",
) -> Cobertura:
    """Cada archivo de forecast listado trae exactamente las series esperadas.

    Por defecto, todas las del contrato (motores legacy: 432). Un motor de una cohorte
    (NBGLM, sólo Dengue) declara su propio conjunto esperado.
    """
    esperadas = contrato.claves_esperadas() if esperadas is None else esperadas
    problemas: list[str] = []
    cifras: dict[str, Any] = {}
    for ruta in rutas:
        motor = ruta.parent.name
        if not ruta.is_file():
            problemas.append(f"forecasts/{motor}: falta {ruta.name}")
            continue
        df = pd.read_csv(
            ruta,
            usecols=["ds", "meta_padecimiento", "meta_entidad", "meta_modo"],
            low_memory=False,
        )
        df["clave"] = [
            _clave(contrato, p, e, m)
            for p, e, m in zip(
                df["meta_padecimiento"], df["meta_entidad"], df["meta_modo"], strict=True
            )
        ]
        # Antes se deduplicaba por clave ANTES de comparar, y una serie repetida —dos
        # bloques de la misma clave, con fechas repetidas— era invisible. Se compara el
        # conjunto de claves, y aparte se exige que ninguna (clave, ds) se repita.
        nuevos, cifras[motor] = _compara_conjuntos(
            f"forecasts/{motor}", df["clave"].drop_duplicates(), esperadas
        )
        problemas.extend(nuevos)
        repetidas = df[df.duplicated(["clave", "ds"], keep=False)]
        if not repetidas.empty:
            ejemplos = sorted({str(k) for k in repetidas["clave"]})[:3]
            problemas.append(
                f"forecasts/{motor}: {repetidas['clave'].nunique()} serie(s) con fechas "
                f"repetidas: {ejemplos}"
            )
    return Cobertura(fuente, cifras, tuple(problemas))


def revisa_tabla_produccion(ruta: Path, contrato: ContratoCobertura) -> Cobertura:
    """La tabla de producción: 432 claves exactas, sin duplicados."""
    df = pd.read_excel(ruta, sheet_name=0, usecols=["padecimiento", "entidad", "sexo"])
    claves = [
        _clave(contrato, p, e, s)
        for p, e, s in zip(df["padecimiento"], df["entidad"], df["sexo"], strict=True)
    ]
    problemas, cifras = _compara_conjuntos("tabla_produccion", claves, contrato.claves_esperadas())
    return Cobertura("tabla_produccion", {**cifras, "filas": int(len(df))}, tuple(problemas))


def revisa_produccion_dengue(ruta: Path, contrato: ContratoCobertura) -> Cobertura:
    """Las 99 series de Dengue, exactas."""
    df = pd.read_csv(ruta, usecols=["padecimiento", "entidad", "sexo"])
    claves = [
        _clave(contrato, p, e, s)
        for p, e, s in zip(df["padecimiento"], df["entidad"], df["sexo"], strict=True)
    ]
    esperadas = frozenset().union(*(contrato.productos(p) for p in contrato.conteo))
    problemas, cifras = _compara_conjuntos("produccion_dengue", claves, esperadas)
    return Cobertura("produccion_dengue", {**cifras, "filas": int(len(df))}, tuple(problemas))


def revisa_entradas(
    raiz_backend: Path, contrato: ContratoCobertura, padecimientos_autorizados: Iterable[str]
) -> list[Cobertura]:
    """Todos los controles sobre las entradas hidratadas de un backend (sandbox o real)."""
    return [
        revisa_consolidado(raiz_backend / RUTA_CONSOLIDADO, contrato, padecimientos_autorizados),
        revisa_forecasts(raiz_backend / DIR_FORECASTS, contrato),
        revisa_tabla_produccion(raiz_backend / RUTA_TABLA_PRODUCCION, contrato),
        revisa_produccion_dengue(raiz_backend / RUTA_PRODUCCION_DENGUE, contrato),
    ]


def revisa_candidato(raiz_dashboard: Path, contrato: ContratoCobertura) -> list[Cobertura]:
    """Lo que el candidato publica: modelos de producción del EpiBot y galería/zoom.

    Es el control del otro lado: si la hidratación fue corta o un generador degradó, el
    sitio candidato lo delata aunque sus archivos existan y parezcan plausibles.
    """
    resultados: list[Cobertura] = []
    conocimiento = raiz_dashboard / "epibot" / "knowledge.json"
    if conocimiento.is_file():
        k = json.loads(conocimiento.read_text(encoding="utf-8"))
        modelos = k.get("prod_models") or []
        claves = [
            _clave(contrato, m.get("padecimiento"), m.get("entidad"), m.get("sexo"))
            for m in modelos
        ]
        esperadas = frozenset().union(*(contrato.productos(p) for p in contrato.neuro))
        problemas, cifras = _compara_conjuntos("knowledge.prod_models", claves, esperadas)
        rosters = k.get("rosters") or {}
        esperado_rosters = {
            "total_series": len(contrato.claves_esperadas()),
            "gallery_items": len(contrato.zoom_esperado()),
        }
        for campo, valor in esperado_rosters.items():
            if rosters.get(campo) != valor:
                problemas.append(
                    f"knowledge.rosters.{campo} = {rosters.get(campo)!r}, contrato {valor}"
                )
        resultados.append(Cobertura("knowledge.json", cifras, tuple(problemas)))
    zoom = raiz_dashboard / "epibot" / "zoom_series.json"
    if zoom.is_file():
        z = json.loads(zoom.read_text(encoding="utf-8"))
        claves = []
        for clave in z:
            partes = str(clave).split("|")
            if len(partes) != 3:
                claves.append((f"?{clave}", "?", "?"))
                continue
            claves.append(_clave(contrato, *partes))
        problemas, cifras = _compara_conjuntos("zoom_series", claves, contrato.zoom_esperado())
        resultados.append(Cobertura("zoom_series.json", cifras, tuple(problemas)))
    return resultados


def exige_todo(coberturas: Iterable[Cobertura]) -> None:
    problemas = [p for c in coberturas for p in c.problemas]
    if problemas:
        raise StagingError("cobertura fuera de contrato:\n  - " + "\n  - ".join(problemas))
