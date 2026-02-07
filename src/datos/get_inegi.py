# src/datos/get_inegi.py
import json
import requests
import pandas as pd
from src.extraccion.inegi_eda import eda_inegi
from src.configuraciones.config_params import conf, logger
from src.utils import directory_manager
from typing import Dict, Any

class GetInegi:

    def __init__(self, forzar = False):
        self.sobreescribe = forzar
        self.conf_paths = conf.get("data")
        self.utils_path = conf['paths']['utils']
        self.inegi_path = conf['data']['inegi']
        
        self.BASE_PXWEB = "https://www.inegi.org.mx/app/tabulados/pxwebv2/api/v1/es"
        self.DB = "Poblacion"
        self.TABLA_PX = "Poblacion_01.px"

        self.df = pd.DataFrame
        self.df_superficie = pd.DataFrame

        self.QUERY = {
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

        self.URL_SUPERFICIE = (
            "https://www.inegi.org.mx/app/api/indicadores/interna_v1_3/API.svc/"
            "ValorIndicador/1001000001/"
            "01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32/"
            "null/es/null/null/3/n/0/1/null/null/1/6/json/"
            "563cbaa8-58bb-fef8-6763-1f1dae318f99"
        )

        self.ESTADOS_DICT = {
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

        self.REGION_SALUD_MENTAL = {
            # Altamente urbanas / metropolitanas
            "Ciudad de México": "Metropolitana alta",
            "México": "Metropolitana alta",
            "Nuevo León": "Metropolitana alta",
            "Jalisco": "Metropolitana alta",

            # Urbanas medias e industrializadas
            "Aguascalientes": "Urbana media",
            "Baja California": "Urbana media",
            "Baja California Sur": "Urbana media",
            "Chihuahua": "Urbana media",
            "Coahuila de Zaragoza": "Urbana media",
            "Colima": "Urbana media",
            "Durango": "Urbana media",
            "Guanajuato": "Urbana media",
            "Morelos": "Urbana media",
            "Querétaro": "Urbana media",
            "San Luis Potosí": "Urbana media",
            "Sinaloa": "Urbana media",
            "Sonora": "Urbana media",
            "Tamaulipas": "Urbana media",
            "Zacatecas": "Urbana media",

            # Rurales y dispersas
            "Guerrero": "Rural / dispersa",
            "Hidalgo": "Rural / dispersa",
            "Michoacán de Ocampo": "Rural / dispersa",
            "Nayarit": "Rural / dispersa",
            "Puebla": "Rural / dispersa",
            "Tlaxcala": "Rural / dispersa",
            "Veracruz de Ignacio de la Llave": "Rural / dispersa",

            # Sur-Sureste estructuralmente vulnerable
            "Campeche": "Sur-Sureste vulnerable",
            "Chiapas": "Sur-Sureste vulnerable",
            "Oaxaca": "Sur-Sureste vulnerable",
            "Tabasco": "Sur-Sureste vulnerable",
            "Yucatán": "Sur-Sureste vulnerable",
            "Quintana Roo": "Sur-Sureste vulnerable"
        }


        # ========= Descarga en memoria =========

    def descargar_jsonstat_pxweb(self, db: str, tabla_px: str, consulta: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:

            url = f"{self.BASE_PXWEB.rstrip('/')}/{db.strip('/')}/{tabla_px.lstrip('/')}"
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; PxWebClient/1.0)",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://www.inegi.org.mx",
                "Referer": "https://www.inegi.org.mx/",
            }
            logger.info(f"PxWeb: POST url= {url} db= {db} tabla= {tabla_px} timeout= {timeout}" )

            try:
                resp = requests.post(url, headers=headers, json=consulta, timeout=timeout)
                logger.debug(f"PxWeb: status= {resp.status_code} url={url}")
                resp.raise_for_status()
                data = resp.json()
                logger.info(f"PxWeb OK: status= {resp.status_code} bytes= {len(resp.content or b"")}")
                return data
            
            except requests.RequestException as ex:
                logger.error("PxWeb fallo HTTP/red: %s", ex, exc_info=True)
                raise self.PxWebError(f"Falla al consultar PxWeb: {ex}") from ex
            
            except ValueError as ex:
                logger.error("PxWeb respuesta no-JSON: %s", ex, exc_info=True)
                raise self.PxWebError("La respuesta de PxWeb no es JSON válido.") from ex


    # ========= Conversión JSON-STAT v2 -> DataFrame =========
    def _codigos_en_orden(self,indice_categoria, n: int) -> list:
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

    def jsonstat_a_dataframe(self,data: dict) -> pd.DataFrame:

        logger.info("jsonstat_a_dataframe: iniciando conversión")

        ds = data["dataset"]
        dims = ds["dimension"]

        ids = dims["id"]
        size = dims["size"]

        logger.debug(f"Dimensiones: ids= {ids} size= {size}")

        # Crear combinaciones
        tabla_dim = pd.MultiIndex.from_product(
            [range(s) for s in size],
            names=ids
        ).to_frame(index=False)

        # Expandir cada dimensión
        for dim, n in zip(ids, size):
            logger.debug(f"Procesando dimensión {dim}' ({n} elementos)")

            cat = dims[dim]["category"]
            codigos = self._codigos_en_orden(cat["index"], n)
            etiquetas = cat.get("label", {})

            # Índice → código
            tabla_dim[dim] = tabla_dim[dim].map(lambda i: codigos[int(i)])

            # Código → etiqueta (si existe)
            if etiquetas:
                tabla_dim[dim] = tabla_dim[dim].map(lambda x: etiquetas.get(x, x))

        # Asignar los valores
        df = tabla_dim.copy()
        df["valor"] = ds["value"]

        logger.info(f"jsonstat_a_dataframe: terminado. filas= {len(df)}")
        return df
    
    def ajusta_dataframe(self) -> None: 

        self.df["valor"] = pd.to_numeric(self.df["valor"], errors="coerce") # Convirtiendo a numéricos
        if "Grupo quinquenal de edad" not in self.df.columns: # Eliminando Grupo quinquenal de edad
            self.df["Grupo quinquenal de edad"] = "Total"

        self.df = self.df[self.df["Grupo quinquenal de edad"] == "Total"].copy()
        self.df = self.df.drop(columns=["Grupo quinquenal de edad"])
        self.df = self.df.set_index(["Entidad federativa", "Periodo", "Sexo"]) #Convirtiendo a formato wide (Sexo → columnas)
        self.df = self.df["valor"].unstack("Sexo").reset_index()


    
    def validar_hombres_mujeres_vs_total(self) -> None:

        diff = self.df["Total"] - (self.df["Hombres"] + self.df["Mujeres"])
        errores = self.df[diff != 0]

        if not errores.empty:
            ejemplos = errores[
                ["Entidad federativa", "Hombres", "Mujeres", "Total"]
            ].head(5).to_string(index=False)

            logger.error("Inconsistencias detectadas: Hombres + Mujeres ≠ Total")
            logger.error("Revisa estos registros:\n"
                f"{ejemplos}"
            )

    def filtra_periodo_max(self) -> None:

        self.df = (
            self.df[self.df["Periodo"] == self.df["Periodo"].max()]  # Filtrar por el máximo periodo
            .copy()                                                  # Copiar para evitar advertencias
            .reset_index(drop=True)                                  # Resetear índice
            .drop(columns=["Periodo"])                               # Eliminar columna 'Periodo'
        )

        self.df.columns.name = None


    def get_superficie_estados(self) -> None:
        data = requests.get(self.URL_SUPERFICIE, timeout=30).json()
        
        self.df_superficie = pd.DataFrame({
                "Entidad federativa": [
                    self.ESTADOS_DICT[e] for e in data["dimension"]["municipality"]["category"]["index"]
                ],
                "Superficie_km2": data["value"]
            }) 
        
        self.df_superficie["Superficie_km2"] = pd.to_numeric(self.df_superficie["Superficie_km2"].str.replace(",", "", regex=False), errors="coerce")
        
        self.df = (
            self.df_superficie
            .merge(self.df, on="Entidad federativa", how="inner")
            .sort_values("Entidad federativa")
            .reset_index(drop=True)
        )

        


    def clasificaciones(self):

        self.df["region_salud_mental"] = self.df["Entidad federativa"].map(self.REGION_SALUD_MENTAL)
        faltantes = self.df[self.df["region_salud_mental"].isna()]["Entidad federativa"].unique()
        if len(faltantes) > 0:
            logger.warning(f"Estados sin REGION_SALUD_MENTAL: {', '.join(sorted(faltantes))}")

        self.df["ratio_h_m"] = self.df["Hombres"] / self.df["Mujeres"]  # Se calcula la proporción hombres / mujeres
        self.df["ratio_h_m_cat"] = pd.cut(  # Se categoriza el ratio en 3 grupos interpretables
        self.df["ratio_h_m"],
        bins=[-float("inf"), 0.99, 1.01, float("inf")],
        labels=["Mayormente mujeres", "Balanceado", "Mayormente hombres"]
        )

        self.df["tamano_poblacional_predefinido"] = pd.cut(  # Se clasifica el tamaño poblacional por rangos fijos
        self.df["Total"],
        bins=[0, 1_000_000, 3_000_000, 6_000_000, self.df["Total"].max()],
        labels=["0-1M", "1-3M", "3-6M", "6M+"]
        )

        self.df["tamano_poblacional_grupo_percentil"] = pd.qcut(  # Se agrupa el tamaño poblacional por cuartiles
        self.df["Total"],
        q=4,
        labels=["Población baja", "Media-baja", "Media-alta", "Alta"]
        )

        self.df["densidad_poblacion"] = self.df["Total"] / self.df["Superficie_km2"]

        self.df["extension_territorial_percentil"] = pd.qcut(
        self.df["Superficie_km2"],
        q=4,
        labels=["Territorio pequeño", "Medio-pequeño", "Medio-grande", "Grande"]
        )

        self.df["densidad_poblacional_percentil"] = pd.qcut(
        self.df["densidad_poblacion"],
        q=4,
        labels=["Baja", "Media-baja", "Media-alta", "Alta"]
        )
        
  

    def run(self):

        if not directory_manager.existe_archivo(self.inegi_path) or self.sobreescribe:
            
            logger.info(f"Generando archivo {self.inegi_path}")
        
            data = self.descargar_jsonstat_pxweb(self.DB, self.TABLA_PX, self.QUERY)
            self.df = self.jsonstat_a_dataframe(data)
            self.ajusta_dataframe()
            self.validar_hombres_mujeres_vs_total()
            self.filtra_periodo_max()
            self.get_superficie_estados()
            self.clasificaciones()

            directory_manager.asegurar_ruta(self.utils_path)
  
            if directory_manager.existe_archivo(self.inegi_path):
                logger.warning(f"archivo {self.inegi_path} encontrado. El archivo será sobrescrito.")

            else:
                logger.success(f"archivo {self.inegi_path} no localizado. Guardando archivo.")

            self.df.to_csv(self.inegi_path, index=False, encoding="utf-8")
        
        else:
            if directory_manager.existe_archivo(self.inegi_path):
                logger.error(f"Archivo {self.inegi_path} localizado")
            
            else: 
                logger.error(f"Archivo no generado")

