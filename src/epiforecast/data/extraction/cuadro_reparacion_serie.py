"""Reparaciones declaradas de la serie extraída y recorte declarado de su inicio.

Separado de ``cuadro_reparaciones`` (que repara la tabla de UN boletín) porque estas reglas
necesitan varios boletines o sólo el nombre del archivo. Todo es opt-in por grupo de
``config/data/cuadros.yaml`` y por padecimiento; un grupo que no lo declara queda byte-idéntico.

``reparaciones`` (lista; hoy un solo tipo)::

    reparaciones:
      - tipo: sem_desde_delta_acumulado
        diseases: [<id>]
        desde: "AAAA_semNN"     # primer boletín reparado (incluido)
        hasta: "AAAA_semNN"     # último boletín reparado (incluido)
        motivo: "<por qué, con la medición que lo sostiene>"

Regla escrita de ``sem_desde_delta_acumulado``: para cada boletín del rango y cada entidad,
``Casos_semana := A(b) - A(b-1)``, donde ``A`` es el acumulado del año impreso (``H + M``, o
``Acumulado_total`` sin desglose por sexo) y ``b-1`` el boletín de la semana fuente anterior.
Si el periodo objetivo del boletín (``observation_lag_weeks``) es la semana 1 de su año, el
acumulado se reinicia y ``Casos_semana := A(b)`` sin boletín previo. Falla cerrado
(:class:`ReparacionError`) si un boletín del rango o su previo falta, si una entidad no trae
acumulado o si el acumulado baja (diferencia negativa): nunca recorta, imputa ni redondea.

``inicio_serie`` (lista)::

    inicio_serie:
      - diseases: [<id>]
        desde: "AAAA_semNN"     # primer boletín que se extrae
        motivo: "<por qué>"

Los boletines anteriores a ``desde`` quedan ``excluded`` en el manifiesto, sin periodo vacío.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pandas as pd

from epiforecast.data.epi_calendar import shift, target_period

TIPO_DELTA = "sem_desde_delta_acumulado"
TIPOS_REPARACION = frozenset({TIPO_DELTA})
_BOLETIN = re.compile(r"^(\d{4})_sem(\d{2})$")
_ARCHIVO = re.compile(r"^(\d{4})_sem(\d{2})\.pdf$")


class ReparacionError(ValueError):
    """La reparación declarada no puede aplicarse sin inventar datos: la extracción se detiene."""


def _boletin(texto: object, campo: str) -> tuple[int, int]:
    m = _BOLETIN.match(str(texto))
    if m is None:
        raise ReparacionError(f"{campo} inválido: {texto!r} (se espera AAAA_semNN)")
    return int(m.group(1)), int(m.group(2))


def _etiqueta(b: tuple[int, int]) -> str:
    return f"{b[0]}_sem{b[1]:02d}"


def exclusion_por_inicio(
    spec: dict[str, Any], filename: str, disease_id: str
) -> dict[str, Any] | None:
    """Exclusión sintética si el boletín es anterior al ``inicio_serie`` declarado del padecimiento."""
    m = _ARCHIVO.match(filename)
    if m is None:
        return None
    boletin = (int(m.group(1)), int(m.group(2)))
    for regla in spec.get("inicio_serie") or []:
        if disease_id not in (regla.get("diseases") or []):
            continue
        desde = _boletin(regla.get("desde"), "inicio_serie.desde")
        motivo = str(regla.get("motivo") or "").strip()
        if not motivo:
            raise ReparacionError("inicio_serie sin motivo")
        if boletin < desde:
            return {
                "file": filename,
                "diseases": [disease_id],
                "reason": f"anterior al inicio declarado de la serie ({regla['desde']}): {motivo}",
                "keep_period": False,
            }
    return None


def reparaciones_de(spec: dict[str, Any], disease_id: str) -> list[dict[str, Any]]:
    """Reparaciones del padecimiento, validadas (tipo, rango y motivo)."""
    out = []
    for regla in spec.get("reparaciones") or []:
        if disease_id not in (regla.get("diseases") or []):
            continue
        if regla.get("tipo") not in TIPOS_REPARACION:
            raise ReparacionError(f"tipo de reparación desconocido: {regla.get('tipo')!r}")
        desde = _boletin(regla.get("desde"), "reparaciones.desde")
        hasta = _boletin(regla.get("hasta"), "reparaciones.hasta")
        if hasta < desde:
            raise ReparacionError(f"rango de reparación vacío: {regla['desde']}..{regla['hasta']}")
        if not str(regla.get("motivo") or "").strip():
            raise ReparacionError("reparación sin motivo")
        out.append({**regla, "_desde": desde, "_hasta": hasta})
    return out


def _acumulado(serie: pd.DataFrame) -> pd.Series:
    if "Acumulado_total" in serie.columns:
        return pd.to_numeric(serie["Acumulado_total"], errors="coerce")
    h = pd.to_numeric(serie["Acumulado_hombres"], errors="coerce")
    return h + pd.to_numeric(serie["Acumulado_mujeres"], errors="coerce")


def _por_entidad(serie: pd.DataFrame, b: tuple[int, int]) -> pd.Series | None:
    filas = serie[(serie["Anio"].astype(int) == b[0]) & (serie["Semana"].astype(int) == b[1])]
    if filas.empty:
        return None
    return pd.Series(_acumulado(filas).to_numpy(), index=filas["Entidad"].to_numpy())


def aplica_reparaciones(
    serie: pd.DataFrame, spec: dict[str, Any], disease_id: str
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """Aplica las reparaciones declaradas del padecimiento a la serie larga ya extraída.

    Devuelve la serie reparada, el registro por fila (boletín, entidad, valor impreso, acumulados
    y valor reparado) y el motivo por boletín para el manifiesto. Sin reparaciones declaradas
    devuelve la misma serie, sin copiarla. Reúne todos los defectos antes de fallar.
    """
    reglas = reparaciones_de(spec, disease_id)
    if not reglas:
        return serie, pd.DataFrame(), {}
    lag = int(spec.get("observation_lag_weeks", 0))
    serie = serie.copy()
    anio = serie["Anio"].astype(int)
    semana = serie["Semana"].astype(int)
    boletines = sorted(set(zip(anio, semana, strict=True)))
    registros: list[dict[str, Any]] = []
    motivos: dict[str, str] = {}
    errores: list[str] = []
    for regla in reglas:
        rango = [b for b in boletines if regla["_desde"] <= b <= regla["_hasta"]]
        esperados = []
        b = regla["_desde"]
        while b <= regla["_hasta"]:
            esperados.append(b)
            b = shift(b[0], b[1], 1)
        faltan = sorted(set(esperados) - set(rango))
        errores += [f"{_etiqueta(b)}: boletín del rango sin datos" for b in faltan]
        for b in rango:
            actual = _por_entidad(serie, b)
            if actual is None:
                continue
            objetivo = target_period(b[0], b[1], lag)
            reinicio = objetivo.epi_week == 1
            previo_b = None if reinicio else shift(b[0], b[1], -1)
            previo = None if previo_b is None else _por_entidad(serie, previo_b)
            if previo_b is not None and previo is None:
                errores.append(f"{_etiqueta(b)}: falta el boletín previo {_etiqueta(previo_b)}")
                continue
            for entidad, a_b in actual.items():
                a_p = 0.0 if previo is None else previo.get(entidad, float("nan"))
                if pd.isna(a_b) or pd.isna(a_p):
                    errores.append(f"{_etiqueta(b)} {entidad}: acumulado ausente")
                    continue
                delta = int(a_b) - int(a_p)
                if delta < 0:
                    errores.append(
                        f"{_etiqueta(b)} {entidad}: el acumulado baja ({int(a_p)} -> {int(a_b)})"
                    )
                    continue
                mask = (anio == b[0]) & (semana == b[1]) & (serie["Entidad"] == entidad)
                registros.append(
                    {
                        "Anio": b[0],
                        "Semana": f"{b[1]:02d}",
                        "Entidad": entidad,
                        "Casos_semana_impreso": serie.loc[mask, "Casos_semana"].iloc[0],
                        "Acumulado_boletin": int(a_b),
                        "Boletin_previo": "" if previo_b is None else _etiqueta(previo_b),
                        "Acumulado_previo": int(a_p),
                        "Casos_semana_reparado": delta,
                        "Regla": "reinicio_anual" if reinicio else "delta_acumulado",
                        "Tipo": regla["tipo"],
                    }
                )
                serie.loc[mask, "Casos_semana"] = delta
            regla_txt = (
                "reinicio anual, Sem. = acumulado"
                if reinicio
                else f"Sem. = Δ acumulado respecto de {_etiqueta(previo_b)}"  # type: ignore[arg-type]
            )
            motivos[f"{_etiqueta(b)}.pdf"] = f"ok; reparación {regla['tipo']} ({regla_txt})"
    if errores:
        raise ReparacionError(
            f"{disease_id}: reparación declarada imposible ({len(errores)} defectos): "
            + "; ".join(errores)
        )
    return serie, pd.DataFrame(registros), motivos


def ruta_registro(serie_path: Path) -> Path:
    """Archivo del registro por fila, junto a la serie (``<slug>_reparaciones.csv``)."""
    return serie_path.with_name(serie_path.name.replace("_boletin.csv", "_reparaciones.csv"))
