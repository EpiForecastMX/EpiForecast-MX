# scripts/descarga_inegi.py
from src.epiforecast.utils.config import conf, logger
from src.epiforecast.data.ingestion.inegi import GetInegi


def main() -> None:
    ruta_inegi = conf["data"]["inegi"]
    forzar_descarga = conf["inegi"]["force"]

    logger.info(
        "Iniciando descarga INEGI | destino: {} | forzar: {}",
        ruta_inegi,
        forzar_descarga,
    )

    try:
        descargador = GetInegi(forzar=forzar_descarga)
        descargador.run()
    except RuntimeError as ex:
        logger.error("Error al descargar datos INEGI: {}", ex)
        raise SystemExit(1) from ex

    logger.success("Descarga INEGI finalizada.")


if __name__ == "__main__":
    main()
