"""La base de conocimiento publica no puede filtrar padecimientos sin autorizar.

El 2026-08-18 el knowledge.json preparado para publicar contenia los casos historicos
reales de obesidad (7,603,953) bajo ``stats.demo_historica``. El roster si filtraba por
lifecycle, pero la demografia se calculaba sobre TODO el consolidado, que incluye los
carriles que aun no tienen autorizacion. La comprobacion que se habia hecho miraba el
sitio ya desplegado, no el artefacto que se iba a desplegar, asi que no lo detecto.

Estas pruebas cierran esa via: una sobre el calculo, sin depender de artefactos, y otra
sobre el archivo generado cuando existe.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from epi_modules.features.knowledge_base import KnowledgeBase
import pandas as pd
import pytest

from epiforecast import registry

REPO_ROOT = Path(__file__).resolve().parents[2]


def _boletin_sintetico() -> pd.DataFrame:
    """Un boletin con un padecimiento publicado y dos que no lo estan."""
    filas = []
    for pad, casos in (("Depresión", 100), ("Obesidad", 5000), ("Anorexia F50", 7)):
        for semana in (26, 27):
            filas.append(
                {
                    "Anio": 2026,
                    "Semana": semana,
                    "Entidad": "Jalisco",
                    "Padecimiento": pad,
                    "Casos_semana": casos,
                    "Acumulado_hombres": casos * semana,
                    "Acumulado_mujeres": casos * semana,
                    "Acumulado_anio_anterior": None,
                }
            )
    return pd.DataFrame(filas)


class _CacheFalso:
    """Cache minimo. `_ensure_stats` retorna temprano sin modelos, asi que hace falta
    una tabla de produccion aunque la demografia solo dependa del boletin."""

    def __init__(self, boletin: pd.DataFrame) -> None:
        self._boletin = boletin
        self._prod = pd.DataFrame(
            [
                {
                    "padecimiento": "Depresion",
                    "entidad": "Jalisco",
                    "sexo": "general",
                    "modelo_produccion": "Prophet",
                }
            ]
        )

    @property
    def boletin(self) -> pd.DataFrame:
        return self._boletin

    @property
    def prod_models(self) -> pd.DataFrame:
        return self._prod

    def __getattr__(self, nombre: str) -> Any:
        return None


def test_la_demografia_historica_excluye_los_no_publicados() -> None:
    kb = KnowledgeBase(_CacheFalso(_boletin_sintetico()))  # type: ignore[arg-type]
    demo = kb._ensure_stats().get("demo_historica", {})

    assert "Depresión" in demo, "el padecimiento publicado debe seguir presente"
    assert "Obesidad" not in demo
    assert "Anorexia F50" not in demo


def test_el_filtro_sale_del_registry_y_no_de_una_lista_escrita_a_mano() -> None:
    """Si se publica un padecimiento nuevo, debe aparecer sin tocar el codigo."""
    publicados = set(registry.names(published_only=True))
    todos = set(registry.names())

    assert publicados < todos, "la prueba pierde sentido si todo esta publicado"
    assert "Obesidad" in todos - publicados


# El del dashboard es el que se publica; vive fuera de este repositorio.
_ARTEFACTOS = (
    REPO_ROOT / "web_dashboard" / "knowledge.json",
    REPO_ROOT.parent / "EpiForecast-IMSS-Dashboard" / "epibot" / "knowledge.json",
)


@pytest.mark.parametrize("completa", _ARTEFACTOS, ids=("local", "dashboard"))
def test_el_artefacto_generado_no_menciona_padecimientos_sin_autorizar(completa: Path) -> None:
    """Gate sobre lo que de verdad se publica, no sobre lo que ya esta desplegado."""
    if not completa.is_file():
        pytest.skip(f"artefacto ausente: {completa}")

    texto = json.dumps(json.loads(completa.read_text(encoding="utf-8")), ensure_ascii=False)
    sin_autorizar = set(registry.names()) - set(registry.names(published_only=True))

    filtrados = [nombre for nombre in sin_autorizar if nombre.lower() in texto.lower()]
    assert not filtrados, f"{completa.name} menciona padecimientos sin autorizar: {filtrados}"
