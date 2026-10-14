"""Retirada de las métricas de selección de las vistas públicas operativas (ronda W37).

En la liberación W37 las métricas por serie y por motor (``*_prod``, ``smape_2026_*``,
``smape_real_*``…) son el error de la ventana de selección W28–W37: sirvieron para ELEGIR el motor
de cada serie y por eso no son una evaluación independiente del pronóstico publicado. Decisión del
autor (13-oct-2026): retirarlas de las vistas públicas operativas y conservarlas en la evidencia de
revisión con el rótulo :data:`ROTULO`.

:func:`separa_metricas` recorre el ``knowledge.json`` y separa toda clave de métrica de error
(sMAPE, MASE, RMSE, MAE, sus rankings y la precisión histórica), salvo las definiciones de
glosario. Devuelve el knowledge público, que declara la retirada en :data:`CLAVE_DECLARACION`, y
los valores retirados, que van a la evidencia de revisión y nunca al sitio.
"""

from __future__ import annotations

import re
from typing import Any

ROTULO = "diagnóstico de selección W28–W37; no evaluación independiente"
CLAVE_DECLARACION = "metricas_seleccion"

# Claves de métrica de error: smape/mase/rmse/mae como palabra (smape_prod_median, mase_med,
# smape, top5_smape…) y la precisión histórica. ``ranking_entidades`` (casos) no es métrica.
_METRICA = re.compile(r"(^|_)(smape|mase|rmse|mae)(_|$)|^precision_historica", re.IGNORECASE)
# Secciones que son sólo métricas de selección: se retiran enteras.
_SECCIONES = ("rendimiento_2026",)
# Glosario: nombra las métricas pero no publica valores.
_EXENTAS = ("definiciones",)


def es_metrica(clave: str) -> bool:
    return bool(_METRICA.search(clave))


def _separa(obj: Any) -> tuple[Any, Any]:
    """(público, retirado) de un subárbol; ``retirado`` es None si no había nada que retirar."""
    if isinstance(obj, dict):
        publico: dict[str, Any] = {}
        retirado: dict[str, Any] = {}
        for k, v in obj.items():
            if es_metrica(str(k)):
                retirado[k] = v
                continue
            p, r = _separa(v)
            publico[k] = p
            if r is not None:
                retirado[k] = r
        return publico, (retirado or None)
    if isinstance(obj, list):
        pares = [_separa(v) for v in obj]
        if all(r is None for _, r in pares):
            return [p for p, _ in pares], None
        return [p for p, _ in pares], [r for _, r in pares]
    return obj, None


def separa_metricas(knowledge: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Separa el knowledge en (público sin métricas de selección, evidencia retirada)."""
    publico: dict[str, Any] = {}
    retirado: dict[str, Any] = {}
    for k, v in knowledge.items():
        if k in _EXENTAS:
            publico[k] = v
        elif k in _SECCIONES or es_metrica(str(k)):
            retirado[k] = v
        else:
            p, r = _separa(v)
            publico[k] = p
            if r is not None:
                retirado[k] = r
    publico[CLAVE_DECLARACION] = {
        "publicadas": False,
        "ventana": "W28–W37",
        "rotulo": ROTULO,
        "nota": (
            "Las métricas de error de esta ronda midieron la ventana con la que se eligió el "
            "motor de cada serie; no se publican como desempeño del pronóstico."
        ),
    }
    return publico, {"rotulo": ROTULO, "retirado": retirado}


def claves_metrica(obj: Any, ruta: str = "") -> list[str]:
    """Rutas de toda clave de métrica que quede en ``obj`` (fuera del glosario): debe ser vacía."""
    rutas: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            r = f"{ruta}.{k}" if ruta else str(k)
            if ruta == "" and k in _EXENTAS:
                continue
            if es_metrica(str(k)) or (ruta == "" and k in _SECCIONES):
                rutas.append(r)
            else:
                rutas.extend(claves_metrica(v, r))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            rutas.extend(claves_metrica(v, f"{ruta}[{i}]"))
    return rutas
