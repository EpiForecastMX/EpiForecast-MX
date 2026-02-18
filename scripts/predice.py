#scripts/predice.py
import pandas as pd
from pathlib import Path
from src.modelado.forecast import ForecastModelLoader
from src.configuraciones.config_params import conf, logger

def parse_nombre_modelo(stem: str) -> dict:
    parts = stem.split("_")
    if len(parts) < 4:
        raise ValueError(f"Nombre de modelo inconsistente: {stem}")

    modelo = parts[0]
    padecimiento = parts[1]
    fecha = parts[-1]
    modo = parts[-2]

    # Si falta entidad (solo 4 partes), la marcamos blank
    if len(parts) == 4:
        entidad = ""
    else:
        entidad = " ".join(parts[2:-2])

    return {
        "Predict_Modelo": modelo,
        "Predict_Padecimiento": padecimiento,
        "Predict_Entidad": entidad,
        "Predict_Modo": modo,
        "Predict_Fecha": fecha,
    }


def main():
    base_models = Path(conf["data"]["model_train"])
    out_file = Path(conf["data"]["forecast"])
    out_file.parent.mkdir(parents=True, exist_ok=True)

    modelos = list(base_models.rglob("*.pkl"))
    total = len(modelos)
    if total == 0:
        raise FileNotFoundError(f"No encontré .pkl en {base_models}")
    logger.info(f">>> {total} modelos detectados. Iniciando predicciones.")

    frames = []

    for i, pkl in enumerate(modelos, start=1):
        pct = int(i*100 / total)
        logger.info(f"[{i}/{total}] {pct}% → {pkl}")
        
        meta = parse_nombre_modelo(pkl.stem)
        df = ForecastModelLoader(60, model_path=pkl).run()
        for k, v in meta.items():
            df[k] = v
        frames.append(df)
        
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(out_file, index=False)
    logger.info(f"Predicciones completadas. Archivo CSV guardado: {out_file}")
    

if __name__ == "__main__":
    main()