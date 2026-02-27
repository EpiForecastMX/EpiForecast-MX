# scripts/compara_modelos.py
"""CLI script to generate model comparison charts."""

from epiforecast.utils.config import logger
from epiforecast.visualization.comparison_plots import generar_graficos_comparativos


def main():
    logger.info("Iniciando generación de comparativas de modelos...")
    generar_graficos_comparativos()
    logger.success("Proceso de comparativa finalizado.")


if __name__ == "__main__":
    main()
