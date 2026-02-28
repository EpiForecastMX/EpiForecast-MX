# scripts/compara_modelos.py
"""CLI script to generate model comparison charts."""

from epiforecast.utils.config import logger
from epiforecast.visualization.comparison_plots import generar_graficos_comparativos
from epiforecast.visualization.comparison_report import generar_reporte_html


def main():
    logger.info("Iniciando generacion de comparativas de modelos...")
    generar_graficos_comparativos()
    generar_reporte_html()
    logger.success("Proceso de comparativa finalizado.")


if __name__ == "__main__":
    main()
