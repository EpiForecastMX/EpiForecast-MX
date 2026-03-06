# src/epiforecast/utils/config.py
"""Unified configuration loader for EpiForecast-MX.

Merges all YAML files from config/ into a single `conf` dict.
All modules access configuration via `from epiforecast.utils.config import conf, logger`.
"""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import platform
import sys
from typing import Any, cast
import warnings as _warnings

from loguru import logger
from omegaconf import OmegaConf

__all__ = ["conf", "logger"]

# Suprimir warnings ruidosos de leaked semaphores (joblib/loky en Windows/Linux)
_warnings.filterwarnings("ignore", message=".*resource_tracker.*")
_warnings.filterwarnings("ignore", message=".*leaked.*")

try:
    conf_base = OmegaConf.load("config/base.yaml")
    conf_data = OmegaConf.load("config/data/preprocessing.yaml")
    conf_features = OmegaConf.load("config/features/feature_engineering.yaml")

    # Cargar todos los modelos disponibles en config/models/
    conf_models = cast(Any, OmegaConf.create())
    for model_cfg in Path("config/models").glob("*.yaml"):
        conf_models = OmegaConf.merge(conf_models, OmegaConf.load(model_cfg))

    conf_viz = OmegaConf.load("config/visualization/plots.yaml")
    conf_infra = OmegaConf.load("config/infrastructure/logging.yaml")
except FileNotFoundError as e:
    logger.error("Archivo de configuración no encontrado: {}", e)
    sys.exit(1)

_merged = OmegaConf.merge(conf_base, conf_data, conf_features, conf_models, conf_viz, conf_infra)

# Allow CLI overrides via dotlist (e.g. python script.py padecimiento.solo_nacional=True)
cli_conf = OmegaConf.from_cli()
_merged = OmegaConf.merge(_merged, cli_conf)

conf: dict[str, Any] = cast(dict[str, Any], OmegaConf.to_container(_merged, resolve=True))

# Configurar logger según YAML
if "logging" in conf:
    sinks = conf["logging"].get("sinks", [])
    logger.remove()

    for sink in sinks:
        if sink["type"] == "stderr":
            logger.add(
                sys.stderr,
                level=sink.get("level", "INFO"),
                colorize=sink.get("colorize", True),
                format=sink.get("format"),
                enqueue=sink.get("enqueue", True),
                backtrace=sink.get("backtrace", True),
                diagnose=sink.get("diagnose", False),
            )
        elif sink["type"] == "file":
            logger.add(
                sink.get("path", "./logs/app.log"),
                level=sink.get("level", "DEBUG"),
                colorize=sink.get("colorize", False),
                format=sink.get("format"),
                rotation=sink.get("rotation", "00:00"),
                retention=sink.get("retention", "7 days"),
                compression=sink.get("compression", "zip"),
                enqueue=sink.get("enqueue", True),
                backtrace=sink.get("backtrace", True),
                diagnose=sink.get("diagnose", False),
            )

    yaml_path = Path("config/infrastructure/logging.yaml").resolve()
    env = os.getenv("APP_ENV", "local")
    cwd = Path.cwd()
    pyv = platform.python_version()
    pid = os.getpid()

    sinks_conf = conf.get("logging", {}).get("sinks", [])
    sinks_count = len(sinks_conf)
    sinks_types = ",".join(sorted({s.get("type", "stderr") for s in sinks_conf})) or "stderr"

    logger.debug(
        "Logging inicializado | status=ok | env={} | config={} | sinks={} ({}) | "
        "cwd={} | pid={} | python={} | timestamp={}",
        env,
        yaml_path,
        sinks_count,
        sinks_types,
        cwd,
        pid,
        pyv,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
