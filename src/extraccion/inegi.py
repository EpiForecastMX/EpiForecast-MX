import json
import requests
import pandas as pd


# ========= Configuración =========
BASE_PXWEB = "https://www.inegi.org.mx/app/tabulados/pxwebv2/api/v1/es"
DB = "Poblacion"
TABLA_PX = "Poblacion_01.px"

QUERY = {
    "query": [
        # 0 = Total nacional, 1..32 = estados
        {"code": "Entidad federativa",
         "selection": {"filter": "item", "values": [str(i) for i in range(1, 33)]}},
        {"code": "Periodo",
         "selection": {"filter": "item", "values": ["4", "5", "3"]}},
        {"code": "Sexo",
         "selection": {"filter": "item", "values": ["0", "1", "2"]}},
    ],
    "response": {"format": "json-stat"},
}


# ========= Descarga en memoria =========
def descargar_jsonstat_pxweb(db: str, tabla_px: str, consulta: dict, timeout: int = 60) -> dict:
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
    return resp.json()


# ========= Conversión JSON-STAT v2 -> DataFrame =========
def _codigos_en_orden(indice_categoria, n: int) -> list:
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


def jsonstat_a_dataframe(data: dict) -> pd.DataFrame:
    """
    Convierte un JSON-STAT v2 (PxWeb) a DataFrame tabular.
    """
    ds = data["dataset"]
    dims = ds["dimension"]

    ids = dims["id"]
    size = dims["size"]

    # Todas las combinaciones posibles según el orden oficial
    tabla_dim = pd.MultiIndex.from_product(
        [range(s) for s in size],
        names=ids
    ).to_frame(index=False)

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
    Imprime un resumen y ejemplos si hay inconsistencias.
    """
    diff = df_wide["Total"] - (df_wide["Hombres"] + df_wide["Mujeres"])
    errores = df_wide[diff != 0]

    print(f"Filas totales: {len(df_wide)}")
    print(f"Filas con error (H+M != Total): {len(errores)}")

    if not errores.empty:
        print("\nEjemplos con error:")
        print(
            errores[
                ["Entidad federativa", "Periodo", "Hombres", "Mujeres", "Total"]
            ].head(10)
        )
    else:
        print("\nValidación OK: Hombres + Mujeres = Total en todas las filas.")


def run():
    # 1) Descarga los datos desde PxWeb (INEGI) y los mantiene en memoria
    data = descargar_jsonstat_pxweb(DB, TABLA_PX, QUERY)

    # 2) Convierte el JSON-STAT a un DataFrame en formato largo (long)
    df = jsonstat_a_dataframe(data)

    # 3) Filtra únicamente el total por grupo quinquenal de edad. Elimina grupos específicos y "No especificado", quedandose solo con Total
    df2 = df[df["Grupo quinquenal de edad"] == "Total"].copy()

    # 4) Elimina la columna de edad porque ya no aporta información
    df2 = df2.drop(columns=["Grupo quinquenal de edad"])

    # 5) Define un índice jerárquico para preparar el cambio a formato wide. Cada combinación (Entidad, Periodo, Sexo) tendrá un solo valor
    df3 = df2.set_index(["Entidad federativa", "Periodo", "Sexo"])

    # 6) Convierte la columna "Sexo" en columnas (wide format). El valor numérico queda en columnas separadas: Total, Hombres, Mujeres
    df_wide = df3["valor"].unstack("Sexo").reset_index()

    # 7) Muestra el resultado final
    print(df_wide)

    # 8) Validar que cantidad de hombres + cantidad de mujeres = Total
    validar_hombres_mujeres_vs_total(df_wide)

run()