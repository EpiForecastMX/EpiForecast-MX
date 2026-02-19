# scripts/predice.py
import pandas as pd
from pathlib import Path

from src.modelado.forecast import ForecastModelLoader, generar_graficos_pronostico
from src.configuraciones.config_params import conf, logger
from src.utils import directory_manager


def parse_nombre_modelo(stem: str) -> dict:
    """Extrae metadatos del nombre del archivo .pkl.

    Formato esperado: Prophet_{padecimiento}[_{entidad}]_{modo}
    Ejemplo: Prophet_Alzheimer_Nuevo_Leon_hombres
    """
    parts = stem.split("_")
    if len(parts) < 3:
        raise ValueError(f"Nombre de modelo inesperado: {stem!r}")

    padecimiento = parts[1]
    modo = parts[-1]
    entidad = " ".join(parts[2:-1]) if len(parts) > 3 else ""

    return {
        "meta_padecimiento": padecimiento,
        "meta_entidad": entidad,
        "meta_modo": modo,
    }


def main():
    periodo = conf["prediccion"]["periodo"]
    base_models = Path(conf["paths"]["models"])
    out_file = Path(conf["data"]["forecast"])

    directory_manager.asegurar_ruta(out_file.parent)

    modelos = sorted(base_models.rglob("*.pkl"))
    total = len(modelos)
    if total == 0:
        raise FileNotFoundError(f"No se encontraron modelos .pkl en: {base_models}")

    logger.info("Modelos detectados: {} | periodo: {} semanas | salida: {}", total, periodo, out_file)

    frames = []
    errores = []

    for i, pkl in enumerate(modelos, start=1):
        pct = int(i * 100 / total)
        logger.info("[{}/{}] {}% → {}", i, total, pct, pkl.name)

        try:
            meta = parse_nombre_modelo(pkl.stem)
            df = ForecastModelLoader(periodo=periodo, model_path=pkl).run()
            for k, v in meta.items():
                df[k] = v
            frames.append(df)
        except Exception as e:
            logger.warning("Error en {}: {}", pkl.name, e)
            errores.append(pkl.name)

    if not frames:
        raise RuntimeError("Ninguna predicción generada.")

    out = pd.concat(frames, ignore_index=True)
    out.to_csv(out_file, index=False)

    logger.success("Predicciones guardadas: {} | modelos: {} | errores: {}", out_file, len(frames), len(errores))
    if errores:
        for nombre in errores:
            logger.warning("  Falló: {}", nombre)

    #modelo, forecast, serie 
    generar_graficos_pronostico()


if __name__ == "__main__":
    main()
