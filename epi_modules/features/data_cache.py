"""ProjectDataCache: carga lazy de datos del proyecto para el CLI."""

from pathlib import Path
from typing import Any

from omegaconf import OmegaConf
import pandas as pd


class ProjectDataCache:
    """Cache lazy de datos del proyecto para uso en CLI interactivo."""

    def __init__(self) -> None:
        self._boletin: pd.DataFrame | None = None
        self._tableau: pd.DataFrame | None = None
        self._prod_models: pd.DataFrame | None = None
        self._config: dict[str, Any] | None = None
        self._model_inventory: dict[str, int] | None = None

    @property
    def boletin(self) -> pd.DataFrame | None:
        """Carga lazy del boletin epidemiologico."""
        if self._boletin is None:
            path = Path("data/processed/dataset_boletin_epidemiologico.csv")
            if path.exists():
                try:
                    self._boletin = pd.read_csv(path, low_memory=False)
                except Exception:
                    return None
        return self._boletin

    @property
    def tableau(self) -> pd.DataFrame | None:
        """Carga lazy de tableau_model.xlsx (relacional) o tableau.csv (legacy)."""
        if self._tableau is None:
            xlsx_path = Path("data/processed/tableau_model.xlsx")
            csv_path = Path("data/processed/tableau.csv")
            try:
                if xlsx_path.exists():
                    self._tableau = self._load_tableau_xlsx(xlsx_path)
                elif csv_path.exists():
                    self._tableau = pd.read_csv(csv_path, low_memory=False)
            except Exception:
                return None
        return self._tableau

    @staticmethod
    def _load_tableau_xlsx(path: Path) -> pd.DataFrame:
        """Lee tableau_model.xlsx y une las hojas en un DataFrame plano."""
        forecast = pd.read_excel(path, sheet_name="forecast")
        metricas = pd.read_excel(path, sheet_name="metricas")
        real = pd.read_excel(path, sheet_name="real")

        # Unir forecast + metricas (por entidad, padecimiento, meta_modo)
        join_keys = ["entidad", "padecimiento", "meta_modo"]
        df = forecast.merge(metricas, on=join_keys, how="left")

        # Unir con real (por ds, entidad, padecimiento — sin meta_modo)
        real_keys = ["ds", "entidad", "padecimiento"]
        return df.merge(real, on=real_keys, how="left")

    @property
    def prod_models(self) -> pd.DataFrame | None:
        """Carga lazy de la tabla de 333 modelos de produccion."""
        if self._prod_models is None:
            path = Path("reports/ProdDetails/tabla_333_modelos_produccion.xlsx")
            if path.exists():
                try:
                    self._prod_models = pd.read_excel(path, sheet_name=0)
                except Exception:
                    return None
        return self._prod_models

    @property
    def config(self) -> dict[str, Any] | None:
        """Carga lazy de la configuracion YAML."""
        if self._config is None:
            base_path = Path("config/base.yaml")
            if base_path.exists():
                try:
                    cfg = OmegaConf.load(base_path)
                    self._config = OmegaConf.to_container(cfg, resolve=False)
                except Exception:
                    return None
        return self._config

    @property
    def modelo_activo(self) -> str:
        """Retorna el modelo activo de la configuracion."""
        cfg = self.config
        if cfg and "modelo_activo" in cfg:
            return str(cfg["modelo_activo"])
        return "desconocido"

    @property
    def model_inventory(self) -> dict[str, int]:
        """Escanea models/ contando .pkl por modelo."""
        if self._model_inventory is None:
            self._model_inventory = {}
            models_root = Path("models")
            if models_root.exists():
                for subdir in models_root.iterdir():
                    if subdir.is_dir() and not subdir.name.startswith("."):
                        count = len(list(subdir.glob("**/*.pkl")))
                        if count > 0:
                            self._model_inventory[subdir.name] = count
        return self._model_inventory

    def invalidate(self) -> None:
        """Invalida todo el cache."""
        self._boletin = None
        self._tableau = None
        self._prod_models = None
        self._config = None
        self._model_inventory = None

    def build_ai_context(self) -> str:
        """Construye contexto rico (~2000 tokens) para system prompt de Gemini."""
        parts = ["=== CONTEXTO DEL PROYECTO EpiForecast-MX ===\n"]

        # Config
        cfg = self.config
        if cfg:
            parts.append(f"Modelo activo: {cfg.get('modelo_activo', '?')}")
            pad = cfg.get("padecimiento", {})
            parts.append(f"Padecimiento: {pad.get('tipo', '?')}")
            parts.append(f"Horizonte: {cfg.get('prediccion', {}).get('periodo', 52)} semanas")

        # Inventario de modelos
        inv = self.model_inventory
        if inv:
            parts.append("\nModelos entrenados (.pkl):")
            for name, count in sorted(inv.items()):
                parts.append(f"  {name}: {count} archivos")

        # Boletin
        df = self.boletin
        if df is not None:
            parts.append(f"\nBoletin epidemiologico: {len(df):,} registros")
            if "Padecimiento" in df.columns:
                for pad in df["Padecimiento"].unique():
                    n = len(df[df["Padecimiento"] == pad])
                    parts.append(f"  {pad}: {n:,} registros")
            if "Entidad" in df.columns:
                parts.append(f"  Entidades: {df['Entidad'].nunique()}")
            date_cols = [c for c in df.columns if "fecha" in c.lower() or "semana" in c.lower()]
            if date_cols:
                col = date_cols[0]
                parts.append(f"  Rango: {df[col].min()} a {df[col].max()}")

        # Modelos de produccion
        prod = self.prod_models
        if prod is not None:
            parts.append(f"\nModelos de produccion: {len(prod)} series")
            if "modelo_produccion" in prod.columns:
                for motor, count in prod["modelo_produccion"].value_counts().items():
                    parts.append(f"  {motor}: {count}")
            if "smape_prod" in prod.columns:
                smape_mean = prod["smape_prod"].mean()
                parts.append(f"  SMAPE promedio: {smape_mean:.1f}%")
            if "overfitting" in prod.columns:
                ov = prod["overfitting"].astype(str)
                alto = ov.str.contains("Alto", na=False).sum()
                moderado = ov.str.contains("Moderado", na=False).sum()
                ok = ov.str.startswith("OK").sum()
                parts.append(f"  Overfitting: OK={ok}, Moderado={moderado}, Alto={alto}")

        parts.append("\nPadecimientos: Depresion (F32), Parkinson (G20), Alzheimer (G30)")
        parts.append("Cobertura: 32 entidades federativas de Mexico")
        parts.append("Institucion: IMSS (Instituto Mexicano del Seguro Social)")

        return "\n".join(parts)
