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
from typing import Any
import unicodedata

import pandas as pd

from epiforecast import registry
from epiforecast.constants import INEGI_REGIONS
from epiforecast.publication.errores import StagingError

SEXOS: tuple[str, ...] = ("general", "hombres", "mujeres")
NACIONAL = "nacional"
_REPO = Path(__file__).resolve().parents[3]
CATALOGO_ENTIDADES = _REPO / "config" / "geografia" / "entidades_mx.csv"
RUTA_CATALOGO = "config/geografia/entidades_mx.csv"
MOTORES_LEGACY: tuple[str, ...] = ("prophet", "deepar", "ensemble", "stacking")

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
        """El catálogo geográfico se lee del HEAD que se sella y se compara con el worktree.

        Igual que la política: el conjunto de entidades que gobierna el contrato no puede
        venir de un archivo suelto. Los padecimientos publicados siguen saliendo del registry.
        """
        salida = subprocess.run(
            ["git", "-C", str(repo), "show", f"{head}:{RUTA_CATALOGO}"], capture_output=True
        )
        if salida.returncode != 0:
            raise StagingError(
                f"el catálogo geográfico {RUTA_CATALOGO} no está en {head[:12]}: "
                f"{salida.stderr.decode(errors='replace').strip()}"
            )
        ruta = repo / RUTA_CATALOGO
        if ruta.is_symlink() or not ruta.is_file() or ruta.read_bytes() != salida.stdout:
            raise StagingError(
                f"el catálogo geográfico {RUTA_CATALOGO} difiere de la versión de {head[:12]}"
            )
        return ContratoCobertura.desde_catalogo(salida.stdout.decode("utf-8"))

    @staticmethod
    def desde_catalogo(texto: str) -> ContratoCobertura:
        entidades: list[str] = []
        alias: dict[str, str] = {}
        if True:
            for fila in csv.DictReader(texto.splitlines()):
                canonico = slug(fila["nombre_canonico"])
                entidades.append(canonico)
                for nombre in (fila.get("nombre_inegi", ""), *fila.get("aliases", "").split("|")):
                    s = slug(nombre)
                    if s and s != canonico:
                        alias[s] = canonico
        if len(set(entidades)) != len(entidades) or not entidades:
            raise StagingError("catálogo geográfico con entidades duplicadas o vacío")
        return ContratoCobertura(
            neuro=tuple(slug(p) for p in registry.production_cohort()),
            conteo=tuple(slug(p) for p in registry.standalone_members(published_only=True)),
            entidades=tuple(entidades),
            alias=alias,
            regiones=tuple(slug(r) for r in INEGI_REGIONS),
        )


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
    esperadas = frozenset(contrato.entidades)
    for pad, grupo in df.groupby("pad"):
        semanas = sorted(
            {(int(a), int(s)) for a, s in zip(grupo["Anio"], grupo["Semana"], strict=True)}
        )
        cortes[str(pad)] = semanas[-1]
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
    return Cobertura("consolidado", {"cortes": cortes, "filas": int(len(df))}, tuple(problemas))


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
            ruta, usecols=["meta_padecimiento", "meta_entidad", "meta_modo"], low_memory=False
        ).drop_duplicates()
        claves = [
            _clave(contrato, p, e, m)
            for p, e, m in zip(
                df["meta_padecimiento"], df["meta_entidad"], df["meta_modo"], strict=True
            )
        ]
        nuevos, cifras[motor] = _compara_conjuntos(f"forecasts/{motor}", claves, esperadas)
        problemas.extend(nuevos)
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
