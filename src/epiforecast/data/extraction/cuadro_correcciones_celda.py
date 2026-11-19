"""Correcciones declaradas de celdas sueltas de la serie extraída (opt-in por grupo).

Para la decisión nominal del autor sobre una celda concreta de un boletín: fijar un valor o
imputarla. No adivina nada: la celda debe existir y su valor extraído debe ser exactamente el
declarado en ``esperado``; si no, la extracción falla cerrada (:class:`CorreccionError`) sin
escribir. Un grupo que no declara ``correcciones_celda`` queda byte-idéntico.

``correcciones_celda`` (lista)::

    correcciones_celda:
      - archivo: "AAAA_semNN.pdf"
        diseases: [<id>]
        entidad: "<Entidad tal como sale del extractor>"
        columna: Casos_semana
        esperado: <valor extraído antes de corregir; null si el extractor lo lee vacío>
        valor: <entero no negativo>      # o bien
        imputar: true                    # sólo Casos_semana: queda vacía y el dataset v2 la imputa
        motivo: "<qué imprime la fuente, medido>"
        autoridad: "<decisión nominal que la ordena>"

``imputar`` deja ``Casos_semana`` vacía: ``epi_reconcile`` la trata como total faltante
(``total_imputed`` con imputación causal y fallback sexual), igual que un «n.e.». Toda celda
tocada se registra por fila en ``<slug>_correcciones.csv`` y por boletín en el manifiesto.
"""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any

import pandas as pd

COLUMNAS = frozenset(
    {
        "Casos_semana",
        "Acumulado_hombres",
        "Acumulado_mujeres",
        "Acumulado_total",
        "Acumulado_anio_anterior",
    }
)
_ARCHIVO = re.compile(r"^(\d{4})_sem(\d{2})\.pdf$")
Celda = tuple[int, int, str]


class CorreccionError(ValueError):
    """La corrección declarada no cuadra con la celda extraída: la extracción se detiene."""


def _vacio(v: object) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _valida(regla: dict[str, Any]) -> list[str]:
    errores = []
    if _ARCHIVO.match(str(regla.get("archivo"))) is None:
        errores.append(f"archivo inválido: {regla.get('archivo')!r}")
    if not str(regla.get("entidad") or "").strip():
        errores.append("entidad vacía")
    if regla.get("columna") not in COLUMNAS:
        errores.append(f"columna no admitida: {regla.get('columna')!r}")
    if "esperado" not in regla:
        errores.append("falta «esperado» (valor extraído antes de corregir; null si vacío)")
    imputar, tiene_valor = regla.get("imputar") is True, "valor" in regla
    if imputar == tiene_valor:
        errores.append("declara exactamente uno de «valor» o «imputar: true»")
    if imputar and regla.get("columna") != "Casos_semana":
        errores.append("«imputar» sólo vale para Casos_semana")
    if tiene_valor:
        v = regla.get("valor")
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            errores.append(f"valor no es entero no negativo: {v!r}")
    for campo in ("motivo", "autoridad"):
        if not str(regla.get(campo) or "").strip():
            errores.append(f"falta {campo}")
    return errores


def correcciones_de(spec: dict[str, Any], disease_id: str) -> list[dict[str, Any]]:
    """Correcciones del padecimiento, validadas; reúne todos los defectos antes de fallar."""
    reglas = [
        r for r in spec.get("correcciones_celda") or [] if disease_id in (r.get("diseases") or [])
    ]
    errores, vistas = [], set()
    for regla in reglas:
        clave = (regla.get("archivo"), regla.get("entidad"), regla.get("columna"))
        errores += [f"{clave}: {e}" for e in _valida(regla)]
        if clave in vistas:
            errores.append(f"{clave}: corrección duplicada")
        vistas.add(clave)
    if errores:
        raise CorreccionError(f"{disease_id}: correcciones_celda inválidas: " + "; ".join(errores))
    return reglas


def _celda(regla: dict[str, Any]) -> Celda:
    m = _ARCHIVO.match(str(regla["archivo"]))
    assert m is not None  # validado en correcciones_de
    return int(m.group(1)), int(m.group(2)), str(regla["entidad"])


def celdas_casos(spec: dict[str, Any], disease_id: str) -> set[Celda]:
    """Celdas de ``Casos_semana`` corregidas: una reparación de serie no las recalcula."""
    return {_celda(r) for r in correcciones_de(spec, disease_id) if r["columna"] == "Casos_semana"}


def aplica_correcciones(
    serie: pd.DataFrame, spec: dict[str, Any], disease_id: str
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """Aplica las correcciones declaradas; devuelve serie, registro por fila y nota por boletín."""
    reglas = correcciones_de(spec, disease_id)
    if not reglas:
        return serie, pd.DataFrame(), {}
    serie = serie.copy()
    anio, semana = serie["Anio"].astype(int), serie["Semana"].astype(int)
    registros: list[dict[str, Any]] = []
    notas: dict[str, list[str]] = {}
    errores: list[str] = []
    for regla in reglas:
        y, w, entidad = _celda(regla)
        columna = regla["columna"]
        mask = (anio == y) & (semana == w) & (serie["Entidad"] == entidad)
        if int(mask.sum()) != 1 or columna not in serie.columns:
            errores.append(f"{regla['archivo']} {entidad} {columna}: la celda no existe")
            continue
        antes = serie.loc[mask, columna].iloc[0]
        antes = None if pd.isna(antes) else float(antes)
        esperado = regla["esperado"]
        esperado = None if _vacio(esperado) else float(esperado)
        if antes != esperado:
            errores.append(
                f"{regla['archivo']} {entidad} {columna}: extraído {antes!r}, esperado {esperado!r}"
            )
            continue
        imputar = regla.get("imputar") is True
        # Sin cambiar el dtype de la columna: la serie sale byte-idéntica fuera de la celda.
        serie.loc[mask, columna] = None if imputar else int(regla["valor"])
        accion = "imputar" if imputar else "valor"
        registros.append(
            {
                "Archivo": regla["archivo"],
                "Entidad": entidad,
                "Columna": columna,
                "Valor_extraido": "" if antes is None else int(antes),
                "Valor_corregido": "" if imputar else int(regla["valor"]),
                "Accion": accion,
                "Motivo": str(regla["motivo"]).strip(),
                "Autoridad": str(regla["autoridad"]).strip(),
            }
        )
        destino = "imputada" if imputar else str(regla["valor"])
        notas.setdefault(regla["archivo"], []).append(
            f"{entidad} {columna} {'vacía' if antes is None else int(antes)} -> {destino}"
        )
    if errores:
        raise CorreccionError(
            f"{disease_id}: corrección de celda imposible ({len(errores)} defectos): "
            + "; ".join(errores)
        )
    motivos = {f: "corrección de celda declarada: " + "; ".join(n) for f, n in notas.items()}
    return serie, pd.DataFrame(registros), motivos


def ruta_registro(serie_path: Path) -> Path:
    """Archivo del registro por fila, junto a la serie (``<slug>_correcciones.csv``)."""
    return serie_path.with_name(serie_path.name.replace("_boletin.csv", "_correcciones.csv"))
