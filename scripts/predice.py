# scripts/predice.py
import re
import pandas as pd
from pathlib import Path
import unicodedata

from src.modelado.forecast import ForecastModelLoader, generar_graficos_pronostico
from src.configuraciones.config_params import conf, logger
from src.utils import directory_manager


def _normalizar(s: str) -> str:
    """Normaliza para nombres de archivo (debe coincidir con entrena.normalizar)."""
    out = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    out = out.replace("/", "-")
    return re.sub(r"\s+", "_", out)


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
    entidad = " ".join(parts[2:-1]) if len(parts) > 3 else "Nacional"

    return {
        "meta_padecimiento": padecimiento,
        "meta_entidad": entidad,
        "meta_modo": modo,
    }

def estandarizar_valores(df: pd.DataFrame) -> pd.DataFrame:
    import unicodedata

    # Normaliza texto para poder comparar minúsculas, sin acentos, sin espacios extra
    def key(x) -> str:
        s = "" if x is None else str(x).strip().lower()
        s = unicodedata.normalize("NFKD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))
        s = " ".join(s.split())
        return s

    # Diccionario de estandarización de padecimientos
    # clave: forma normalizada
    # valor: forma final deseada
    PADECIMIENTOS = {
        "depresion": "Depresión",
    }

    # Diccionario de estandarización de entidades
    ENTIDADES = {
        "ciudad de mexico": "Ciudad de México",
        "mexico": "México",
        "michoacan": "Michoacán",
        "nuevo leon": "Nuevo León",
        "queretaro": "Querétaro",
        "san luis potosi": "San Luis Potosí",
        "yucatan": "Yucatán",
    }

    # Aplica la estandarización a las columnas relevantes
    # Solo modifica el valor si existe en el diccionario
    for col, mapping in [
        ("meta_padecimiento", PADECIMIENTOS),
        ("Padecimiento", PADECIMIENTOS),
        ("meta_entidad", ENTIDADES),
        ("Entidad", ENTIDADES),
    ]:
        if col in df.columns:
            df[col] = df[col].map(lambda v: mapping.get(key(v), v))

    return df

def _cargar_mapeo_hibrido(base_models: Path) -> dict:
    """Lee _completo.csv de cada padecimiento y construye mapeo hibrido.

    Returns:
        dict: {stem_insuficiente: {"pkl_regional": str, "poblacion": float, "entidad": str}}
              Solo incluye modelos insuficientes que tienen usar_regional asignado.
    """
    mapeo = {}
    for csv_path in sorted(base_models.rglob("*_completo.csv")):
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            continue
        if "usar_regional" not in df.columns:
            continue
        for _, row in df.iterrows():
            if pd.notna(row.get("usar_regional")) and row.get("confianza") == "insuficiente":
                stem = row["archivo_modelo"].replace(".pkl", "")
                mapeo[stem] = {
                    "pkl_regional": row["usar_regional"],
                    "poblacion": row.get("poblacion"),
                    "entidad": row.get("Entidad"),
                    "padecimiento": row.get("padecimiento"),
                    "sexo": row.get("sexo"),
                }
    return mapeo

def _cargar_metricas_completos(base_models: Path) -> pd.DataFrame:
    frames = []
    for csv_path in sorted(base_models.rglob("*_completo.csv")):
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            continue
        if "archivo_modelo" not in df.columns:
            continue
        df["archivo_modelo"] = df["archivo_modelo"].astype(str)

        cols = [c for c in ["archivo_modelo","rmse","mae","mape","mase","confianza","normalizado","poblacion"] if c in df.columns]
        frames.append(df[cols].copy())

    if not frames:
        return pd.DataFrame(columns=["archivo_modelo"])

    met = pd.concat(frames, ignore_index=True).drop_duplicates("archivo_modelo")
    return met

def main():
    periodo = conf["prediccion"]["periodo"]
    base_models = Path(conf["paths"]["models"])
    out_file = Path(conf["data"]["forecast"])
    modelado_hibrido = bool(conf["padecimiento"].get("modelado_hibrido", False))

    directory_manager.asegurar_ruta(out_file.parent)

    modelos = sorted(base_models.rglob("*.pkl"))
    total = len(modelos)
    if total == 0:
        raise FileNotFoundError(f"No se encontraron modelos .pkl en: {base_models}")

    # Cargar mapeo híbrido si aplica
    mapeo_hibrido = _cargar_mapeo_hibrido(base_models) if modelado_hibrido else {}
    stems_insuf = set(mapeo_hibrido.keys())
    # Modelos region_* solo se usan como fallback, no generan forecast propio
    stems_regional = {
        pkl.stem for pkl in modelos
        if pkl.stem.startswith("Prophet_") and "_region_" in pkl.stem
    }

    if mapeo_hibrido:
        logger.info(
            "Modo híbrido activo: {} modelos insuficientes con fallback regional",
            len(mapeo_hibrido),
        )

    logger.info("Modelos detectados: {} | periodo: {} semanas | salida: {}", total, periodo, out_file)

    frames = []
    errores = []

    for i, pkl in enumerate(modelos, start=1):
        pct = int(i * 100 / total)

        # Skip modelos insuficientes (se reemplazan con fallback regional)
        if pkl.stem in stems_insuf:
            logger.info(
                "[{}/{}] {}% → SKIP insuficiente (fallback): {}",
                i, total, pct, pkl.name,
            )
            continue

        # Skip modelos region_* (solo se usan como fallback, no directamente)
        if pkl.stem in stems_regional:
            logger.info("[{}/{}] {}% → SKIP regional (solo fallback): {}", i, total, pct, pkl.name)
            continue

        logger.info("[{}/{}] {}% → {}", i, total, pct, pkl.name)

        try:
            meta = parse_nombre_modelo(pkl.stem)
            df = ForecastModelLoader(periodo=periodo, model_path=pkl).run()
            for k, v in meta.items():
                df[k] = v
            df["archivo_modelo_usado"] = pkl.name
            frames.append(df)
        except Exception as e:
            logger.warning("Error en {}: {}", pkl.name, e)
            errores.append(pkl.name)

    # --- Fallback regional: predecir con modelo regional, desnormalizar con población estatal ---
    if mapeo_hibrido:
        logger.info("Generando {} predicciones con fallback regional...", len(mapeo_hibrido))
        for stem_insuf, info in mapeo_hibrido.items():
            pkl_regional_name = info["pkl_regional"]
            padecimiento = info["padecimiento"]
            pad_norm = _normalizar(padecimiento)
            pkl_regional = base_models / pad_norm / pkl_regional_name

            if not pkl_regional.exists():
                logger.warning("Modelo regional no encontrado: {}", pkl_regional)
                errores.append(f"fallback:{stem_insuf}")
                continue

            try:
                loader = ForecastModelLoader(periodo=periodo, model_path=pkl_regional)
                loader.load()
                # Reemplazar población regional por la del estado individual
                if info.get("poblacion"):
                    loader.poblacion = info["poblacion"]
                df = loader.predict()

                # Metadatos del estado (no de la región)
                meta = parse_nombre_modelo(stem_insuf)
                for k, v in meta.items():
                    df[k] = v
                df["archivo_modelo_usado"] = pkl_regional_name
                frames.append(df)
                logger.info(
                    "Fallback regional: {} → {} (pob={:,.0f})",
                    stem_insuf, pkl_regional_name,
                    info.get("poblacion", 0),
                )
            except Exception as e:
                logger.warning("Error en fallback {}: {}", stem_insuf, e)
                errores.append(f"fallback:{stem_insuf}")

    if not frames:
        raise RuntimeError("Ninguna predicción generada.")

    out = pd.concat(frames, ignore_index=True)
    out = estandarizar_valores(out)
    
    met = _cargar_metricas_completos(base_models)
    out = out.merge(
        met,
        how="left",
        left_on="archivo_modelo_usado",
        right_on="archivo_modelo",
        validate="m:1",
    ).drop(columns=["archivo_modelo"])

    out.to_csv(out_file, index=False)

    logger.success("Predicciones guardadas: {} | modelos: {} | errores: {}", out_file, len(frames), len(errores))
    if errores:
        for nombre in errores:
            logger.warning("  Falló: {}", nombre)

    generar_graficos_pronostico()


if __name__ == "__main__":
    main()
