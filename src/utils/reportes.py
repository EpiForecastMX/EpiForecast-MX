import matplotlib.pyplot as plt
from pathlib import Path
from loguru import logger


from src.configuraciones.config_params import conf

def histograma(df,columna):
    
    """
    Genera un histograma de la columna indicada y lo guarda en reports/figures.
    """

    imagen_salida = Path(conf["paths"]["figures"])
        
       
    # Conteo por valores únicos de la columna
    conteo = df.groupby(columna).size()

    # Graficar histograma
    plt.figure(figsize=(10, 6))
    conteo.plot(kind="bar", color="steelblue", edgecolor="black")

    plt.title(f"Distribución de {columna} - Enfermedad de Parkinson")
    plt.xlabel(columna)
    plt.ylabel("Frecuencia")
    plt.xticks(rotation=45)

    for i, value in enumerate(conteo):
        plt.text(i, value + 50, str(value), ha="center", va="bottom", fontsize=9)

        # Guardar figura
    output_file = imagen_salida / f"histograma_{columna}.png"
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    
    logger.info(f"Histograma guardado en: {output_file}")
