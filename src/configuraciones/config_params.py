# src/configuraciones/config_params.py
from __future__ import annotations

from omegaconf import OmegaConf
from loguru import logger
from pathlib import Path
from datetime import datetime

import os, sys, platform

try:
    conf_params = OmegaConf.load("config/params.yaml")
    conf_logging = OmegaConf.load("config/logging.yaml")
except FileNotFoundError as e:
    logger.error(f"Archivo de configuración no encontrado: {e}")
    sys.exit(1)


conf = OmegaConf.merge(conf_params, conf_logging)
conf = OmegaConf.to_container(conf, resolve=True)

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


    yaml_path = Path("config/logging.yaml").resolve()
    env = os.getenv("APP_ENV", "local")
    cwd = Path.cwd()
    pyv = platform.python_version()
    pid = os.getpid()

    sinks_conf = conf.get("logging", {}).get("sinks", [])
    sinks_count = len(sinks_conf)
    sinks_types = ",".join(sorted({s.get("type", "stderr") for s in sinks_conf})) or "stderr"

    logger.info(
    f"Logging inicializado | status=ok | env={env} | cwd={cwd} | python={pyv} | timestamp={datetime.now():%Y-%m-%d %H:%M:%S}"
    )

    logger.debug(
    f"Logging inicializado | status=ok | env={env} | config={yaml_path} | sinks={sinks_count} ({sinks_types}) | "
    f"cwd={cwd} | pid={pid} | python={pyv} | timestamp={datetime.now():%Y-%m-%d %H:%M:%S}"
    )
