"""Registries fijados para pruebas: el previo a la activación C7.7 y el de C7.7 publicado.

Registry previo a la activación C7.7, para las pruebas del carril CANDIDATO.

El carril candidato (C7.2–C7.6: readiness, compilación ``candidate``, Tableau staging) describe por
definición un release que todavía no está publicado. Desde el 4-nov-2026 el registry real declara
Obesidad ``published`` con canales ``[web, epibot, reports]``; estas pruebas siguen ejercitando el
estado anterior —``trained`` con los cuatro canales candidatos— sobre el MISMO yaml real, cambiando
sólo esas dos líneas del bloque de Obesidad. Todo lo demás (perfiles, release_id, F50) es el real.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import tempfile

from epiforecast import registry

_YAML_REAL = Path(__file__).resolve().parents[2] / "config" / "padecimientos.yaml"
_CANALES_C77 = "channels: [web, epibot, reports]"
_CANALES_CANDIDATOS = "channels: [web, epibot, reports, tableau]"


def _bloque_obesidad(texto: str, de: tuple[str, str], a: tuple[str, str]) -> str:
    cabeza, separador, resto = texto.partition("\n  - id: obesidad\n")
    if not separador:
        raise AssertionError("el registry real ya no declara el bloque de Obesidad")
    bloque, siguiente, cola = resto.partition("\n  - id: ")
    bloque = bloque.replace(f"lifecycle: {de[0]}", f"lifecycle: {a[0]}", 1)
    bloque = bloque.replace(de[1], a[1], 1)
    return cabeza + separador + bloque + siguiente + cola


def _diabetes_sin_publicar(texto: str) -> str:
    """Las pruebas C7.7 describen un solo release publicado: Diabetes vuelve a ``trained``."""
    for disease_id in ("anorexia_f50", "diabetes_t1", "diabetes_t2"):
        cabeza, separador, resto = texto.partition(f"\n  - id: {disease_id}\n")
        if not separador:
            continue
        bloque, siguiente, cola = resto.partition("\n  - id: ")
        bloque = bloque.replace("lifecycle: published", "lifecycle: trained", 1)
        bloque = bloque.replace(_CANALES_C77, "channels: []", 1)
        texto = cabeza + separador + bloque + siguiente + cola
    return texto


def yaml_pre_c77(texto: str | None = None) -> str:
    """El yaml real con Obesidad devuelta a ``trained`` y a sus cuatro canales candidatos."""
    texto = _YAML_REAL.read_text(encoding="utf-8") if texto is None else texto
    texto = _diabetes_sin_publicar(texto)
    return _bloque_obesidad(texto, ("published", _CANALES_C77), ("trained", _CANALES_CANDIDATOS))


def yaml_c77(texto: str | None = None) -> str:
    """El yaml real con Obesidad ``published`` en sus canales C7.7.

    Las pruebas de lo que C7.7 añadió (nota con cinco publicados, hidratación del manifiesto)
    fijan este estado en vez de leer el registry vivo: así siguen ejercitando ese código aunque
    el rollback de la guía devuelva Obesidad a ``trained`` (y sin cambiar el número de skips).
    """
    texto = _YAML_REAL.read_text(encoding="utf-8") if texto is None else texto
    texto = _diabetes_sin_publicar(texto)
    return _bloque_obesidad(texto, ("trained", _CANALES_CANDIDATOS), ("published", _CANALES_C77))


def _carga(texto: str) -> registry._Registry:
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "padecimientos.yaml"
        ruta.write_text(texto, encoding="utf-8")
        return registry.load_registry(ruta)


def registro_pre_c77() -> registry._Registry:
    return _carga(yaml_pre_c77())


@contextmanager
def registry_pre_c77() -> Iterator[registry._Registry]:
    """Instala el registry pre-C7.7 como el cacheado y restaura el real al salir."""
    anterior = registry._CACHE
    registro = registro_pre_c77()
    registry._CACHE = registro
    try:
        yield registro
    finally:
        registry._CACHE = anterior


@contextmanager
def registry_c77() -> Iterator[registry._Registry]:
    """Instala el registry con Obesidad publicada (C7.7) y restaura el real al salir."""
    anterior = registry._CACHE
    registro = _carga(yaml_c77())
    registry._CACHE = registro
    try:
        yield registro
    finally:
        registry._CACHE = anterior
