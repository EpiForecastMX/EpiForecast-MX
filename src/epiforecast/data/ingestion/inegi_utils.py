"""INEGI API utility functions: URL construction, response parsing."""

from typing import Any

from loguru import logger
import pandas as pd
import requests

# ========= Configuración =========
BASE_PXWEB = "https://www.inegi.org.mx/app/tabulados/pxwebv2/api/v1/es"
DB = "Poblacion"
TABLA_PX = "Poblacion_01.px"


QUERY = {
    "query": [
        # 0 = Total nacional, 1..32 = estados
        {
            "code": "Entidad federativa",
            "selection": {"filter": "item", "values": [str(i) for i in range(1, 33)]},
        },
        {"code": "Periodo", "selection": {"filter": "item", "values": ["4", "5", "3"]}},
        {"code": "Sexo", "selection": {"filter": "item", "values": ["0", "1", "2"]}},
    ],
    "response": {"format": "json-stat"},
}

URL_SUPERFICIE = (
    "https://www.inegi.org.mx/app/api/indicadores/interna_v1_3/API.svc/"
    "ValorIndicador/1001000001/"
    "01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32/"
    "null/es/null/null/3/n/0/1/null/null/1/6/json/"
    "563cbaa8-58bb-fef8-6763-1f1dae318f99"
)


# ========= Descarga en memoria =========
def descargar_jsonstat_pxweb(
    db: str, tabla_px: str, consulta: dict[str, Any], timeout: int = 60
) -> dict[str, Any]:
    """
    Consulta PxWeb (INEGI) y regresa el JSON-STAT como dict en memoria.
    """
    url = f"{BASE_PXWEB}/{db}/{tabla_px}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://www.inegi.org.mx",
        "Referer": "https://www.inegi.org.mx/",
    }

    resp = requests.post(url, headers=headers, json=consulta, timeout=timeout)
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


# ========= Conversión JSON-STAT v2 -> DataFrame =========
def _codigos_en_orden(indice_categoria: Any, n: int) -> list[Any]:
    """
    Normaliza category['index'] a lista [pos -> codigo].
    """
    if isinstance(indice_categoria, list):
        return indice_categoria

    if isinstance(indice_categoria, dict):
        codigos = [None] * n
        for codigo, pos in indice_categoria.items():
            codigos[int(pos)] = codigo
        return codigos

    raise TypeError(f"Tipo inesperado para category['index']: {type(indice_categoria)}")


def jsonstat_a_dataframe(data: dict[str, Any]) -> pd.DataFrame:
    """
    Convierte un JSON-STAT v2 (PxWeb) a DataFrame tabular.
    """
    ds = data["dataset"]
    dims = ds["dimension"]

    ids = dims["id"]
    size = dims["size"]

    # Todas las combinaciones posibles según el orden oficial
    tabla_dim = pd.MultiIndex.from_product([range(s) for s in size], names=ids).to_frame(
        index=False
    )

    for dim, n in zip(ids, size):
        cat = dims[dim]["category"]
        codigos = _codigos_en_orden(cat["index"], n)
        etiquetas = cat.get("label", {})

        tabla_dim[dim] = tabla_dim[dim].map(lambda i, c=codigos: c[int(i)])
        if etiquetas:
            tabla_dim[dim] = tabla_dim[dim].map(lambda x, e=etiquetas: e.get(x, x))

    df = tabla_dim.copy()
    df["valor"] = ds["value"]
    return df


def validar_hombres_mujeres_vs_total(df_wide: pd.DataFrame) -> None:
    """
    Valida que Hombres + Mujeres == Total por fila.
    Solo loggea si hay inconsistencias.
    """
    diff = df_wide["Total"] - (df_wide["Hombres"] + df_wide["Mujeres"])
    errores = df_wide[diff != 0]

    if not errores.empty:
        ejemplos = (
            errores[["Entidad federativa", "Hombres", "Mujeres", "Total"]]
            .head(5)
            .to_string(index=False)
        )
        logger.warning(
            "Inconsistencias detectadas: Hombres + Mujeres != Total.\nRevisa estos registros:\n{}",
            ejemplos,
        )


def get_superficie_estados(url: str, catalogo: dict[str, str]) -> pd.DataFrame:
    """Descarga la superficie territorial de cada estado desde la API de INEGI.

    Args:
        url:      URL del endpoint de la API de indicadores INEGI.
        catalogo: Dict de mapeo ``{abreviatura: nombre_completo}`` de estados.

    Returns:
        DataFrame con columnas ``Entidad federativa`` y ``Superficie_km2``.
    """
    data = requests.get(url, timeout=30).json()
    return pd.DataFrame(
        {
            "Entidad federativa": [
                catalogo[e] for e in data["dimension"]["municipality"]["category"]["index"]
            ],
            "Superficie_km2": data["value"],
        }
    )
