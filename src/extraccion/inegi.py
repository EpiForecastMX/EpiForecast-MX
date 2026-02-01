import json
import requests
import pandas as pd
import typer

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

app = typer.Typer(add_completion=False)
log = typer.echo

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
    Solo loggea si hay inconsistencias.
    """
    diff = df_wide["Total"] - (df_wide["Hombres"] + df_wide["Mujeres"])
    errores = df_wide[diff != 0]

    if not errores.empty:
        ejemplos = errores[
            ["Entidad federativa", "Hombres", "Mujeres", "Total"]
        ].head(5).to_string(index=False)

        log(
            "⚠️ Inconsistencias detectadas: Hombres + Mujeres ≠ Total.\n"
            "Revisa estos registros:\n"
            f"{ejemplos}"
        )


def run():
    log(">>>🚀 Consultando PxWeb (INEGI)...")
    data = descargar_jsonstat_pxweb(DB, TABLA_PX, QUERY)

    log(">>>🔄 Convirtiendo JSON-STAT a DataFrame (formato long)...")
    df = jsonstat_a_dataframe(data)

    log(">>>🧮 Convirtiendo 'valor' a numérico...")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    log(">>>🧩 Verificando columna 'Grupo quinquenal de edad'...")
    if "Grupo quinquenal de edad" not in df.columns:
        df["Grupo quinquenal de edad"] = "Total"

    log(">>>🧹 Filtrando solo 'Total' en grupo quinquenal de edad...")
    df2 = df[df["Grupo quinquenal de edad"] == "Total"].copy()

    log(">>>🗑️ Eliminando columna 'Grupo quinquenal de edad'...")
    df2 = df2.drop(columns=["Grupo quinquenal de edad"])

    log(">>>🔁 Convirtiendo a formato wide (Sexo → columnas)...")
    df3 = df2.set_index(["Entidad federativa", "Periodo", "Sexo"])
    df_wide = df3["valor"].unstack("Sexo").reset_index()

    log(">>>✅ Validando Hombres + Mujeres = Total...")
    validar_hombres_mujeres_vs_total(df_wide)

    log(">>>🎯 Filtrando solo el periodo 2020")
    print("==" * 60)
    df_2020 = df_wide[df_wide["Periodo"] == "2020"].copy() # Filtrando por 2020 solamente
    df_2020 = df_2020.reset_index(drop=True) # Reset al indice
    df_2020 = df_2020.drop(columns=["Periodo"]) # Se hace drop a periodo (ya no se ocupa)
    df_2020.columns.name = None # Se quita el nombre al indice
    print(df_2020)
    print("==" * 60)

    log(">>>🎯 Calculando clasificaciones")
    print("==" * 60)
    df_cat = df_2020.copy()
    df_cat["ratio_h_m"] = df_cat["Hombres"] / df_cat["Mujeres"]  # Se calcula la proporción hombres / mujeres
    df_cat["ratio_h_m_cat"] = pd.cut(  # Se categoriza el ratio en 3 grupos interpretables
        df_cat["ratio_h_m"],
        bins=[-float("inf"), 0.99, 1.01, float("inf")],
        labels=["Mayormente mujeres", "Balanceado", "Mayormente hombres"]
    )
    df_cat["tamano_poblacional_predefinido"] = pd.cut(  # Se clasifica el tamaño poblacional por rangos fijos
        df_cat["Total"],
        bins=[0, 1_000_000, 3_000_000, 6_000_000, df_cat["Total"].max()],
        labels=["0-1M", "1-3M", "3-6M", "6M+"]
    )
    df_cat["tamano_poblacional_grupo_percentil"] = pd.qcut(  # Se agrupa el tamaño poblacional por cuartiles
        df_cat["Total"],
        q=4,
        labels=["Población baja", "Media-baja", "Media-alta", "Alta"]
    )
    df_cat = df_cat[  # Se deja el DataFrame final solo con las columnas requeridas
        [
            "Entidad federativa",
            "Hombres",
            "Mujeres",
            "Total",
            "ratio_h_m_cat",
            "tamano_poblacional_predefinido",
            "tamano_poblacional_grupo_percentil",
        ]
    ]

    print(df_cat)
    print("==" * 60)


@app.command()
def main():
    run()

if __name__ == "__main__":
    app()