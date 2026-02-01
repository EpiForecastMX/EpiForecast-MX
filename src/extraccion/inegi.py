import json
import requests
import pandas as pd
import typer
import matplotlib.pyplot as plt
from src.extraccion.inegi_eda import eda_inegi


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

URL_SUPERFICIE = (
        "https://www.inegi.org.mx/app/api/indicadores/interna_v1_3/API.svc/"
        "ValorIndicador/1001000001/"
        "01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32/"
        "null/es/null/null/3/n/0/1/null/null/1/6/json/"
        "563cbaa8-58bb-fef8-6763-1f1dae318f99"
    )

ESTADOS_DICT = {
    "Ags.": "Aguascalientes", "BC": "Baja California", "BCS": "Baja California Sur",
    "Camp.": "Campeche", "Chih.": "Chihuahua", "Chis.": "Chiapas",
    "CDMX": "Ciudad de México", "Coah.": "Coahuila de Zaragoza", "Col.": "Colima",
    "Dgo.": "Durango", "Gto.": "Guanajuato", "Gro.": "Guerrero",
    "Hgo.": "Hidalgo", "Jal.": "Jalisco", "Mex.": "México",
    "Mich.": "Michoacán de Ocampo", "Mor.": "Morelos", "Nay.": "Nayarit",
    "NL": "Nuevo León", "Oax.": "Oaxaca", "Pue.": "Puebla",
    "Qro.": "Querétaro", "Q. Roo": "Quintana Roo", "SLP": "San Luis Potosí",
    "Sin.": "Sinaloa", "Son.": "Sonora", "Tab.": "Tabasco",
    "Tamps.": "Tamaulipas", "Tlax.": "Tlaxcala",
    "Ver.": "Veracruz de Ignacio de la Llave", "Yuc.": "Yucatán",
    "Zac.": "Zacatecas"
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

def get_superficie_estados(url, catalogo):
    data = requests.get(url, timeout=30).json()
    return pd.DataFrame({
        "Entidad federativa": [
            catalogo[e] for e in data["dimension"]["municipality"]["category"]["index"]
        ],
        "Superficie_km2": data["value"]
    })

def run():
    log(">>>🚀 Consultando PxWeb (INEGI)...")
    data = descargar_jsonstat_pxweb(DB, TABLA_PX, QUERY)

    log(">>>🔄 Convirtiendo JSON-STAT a DataFrame (formato long)...")
    df = jsonstat_a_dataframe(data)

    log(">>>🧮 Ajustando DataFrame")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce") # Convirtiendo a numéricos
    if "Grupo quinquenal de edad" not in df.columns: # Eliminando Grupo quinquenal de edad
        df["Grupo quinquenal de edad"] = "Total"
    df = df[df["Grupo quinquenal de edad"] == "Total"].copy()
    df = df.drop(columns=["Grupo quinquenal de edad"])
    df = df.set_index(["Entidad federativa", "Periodo", "Sexo"]) #Convirtiendo a formato wide (Sexo → columnas)
    df = df["valor"].unstack("Sexo").reset_index()

    log(">>>✅ Validando Hombres + Mujeres = Total...")
    validar_hombres_mujeres_vs_total(df)

    log(">>>🎯 Filtrando solo el periodo 2020")
    df_2020 = df[df["Periodo"] == "2020"].copy() # Filtrando por 2020 solamente
    df_2020 = df_2020.reset_index(drop=True) # Reset al indice
    df_2020 = df_2020.drop(columns=["Periodo"]) # Se hace drop a periodo (ya no se ocupa)
    df_2020.columns.name = None # Se quita el nombre al indice

    log(">>>🚀 Descargabndo datos de extensión territorial")
    df_superficie = get_superficie_estados(url=URL_SUPERFICIE, catalogo=ESTADOS_DICT)
    df_superficie["Superficie_km2"] = pd.to_numeric(df_superficie["Superficie_km2"].str.replace(",", "", regex=False), errors="coerce")
    
    log(">>>🎯 Combinando DataFrames")
    df_2020 = df_superficie.merge(df_2020, on="Entidad federativa", how="inner")
    df_2020 = df_2020.sort_values("Entidad federativa").reset_index(drop=True)
        
    log(">>>🎯 Calculando clasificaciones")
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
    df_cat["densidad_poblacion"] = df_cat["Total"] / df_cat["Superficie_km2"]

    df_cat["extension_territorial_percentil"] = pd.qcut(
        df_cat["Superficie_km2"],
        q=4,
        labels=["Territorio pequeño", "Medio-pequeño", "Medio-grande", "Grande"]
    )

    df_cat["densidad_poblacional_percentil"] = pd.qcut(
        df_cat["densidad_poblacion"],
        q=4,
        labels=["Baja", "Media-baja", "Media-alta", "Alta"]
    )
    
    log(">>>✅ DataFrame Finalizado con éxito")
    log(">>>✅ Iniciando EDA")
    
    eda_inegi(df_cat)

@app.command()
def main():
    run()

if __name__ == "__main__":
    app()