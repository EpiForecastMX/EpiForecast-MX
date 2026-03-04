"""Tema IMSS y constantes Unicode para el CLI."""

from rich.theme import Theme

# Paleta IMSS oficial (PANTONE)
IMSS_THEME = Theme(
    {
        "verde": "#006847",
        "verde.dim": "#00483A",
        "dorado": "#BC955C",
        "dorado.dim": "#8B6D3F",
        "guinda": "#9F2241",
        "guinda.dim": "#6F1830",
        "blanco": "#F5F5F0",
        "gris": "#8C8C8C",
        "exito": "bold #006847",
        "alerta": "bold #BC955C",
        "error": "bold #9F2241",
        "info": "#6BA4A0",
        "sutil": "dim #8C8C8C",
    }
)

VERSION = "3.0.0"

# Iconos Unicode (sin emojis)
ICO_OK = "[verde]\u25cf[/verde]"  # ●
ICO_FAIL = "[guinda]\u25cb[/guinda]"  # ○
ICO_CHECK = "[verde]\u2714[/verde]"  # ✔
ICO_CROSS = "[guinda]\u2716[/guinda]"  # ✖
ICO_ARROW = "[dorado]\u25b6[/dorado]"  # ▶
ICO_DOT = "[gris]\u00b7[/gris]"  # ·
ICO_WARN = "[alerta]\u26a0[/alerta]"  # ⚠
ICO_CIRCLE_G = "[verde]\u25cf[/verde]"
ICO_CIRCLE_Y = "[dorado]\u25cf[/dorado]"
ICO_CIRCLE_R = "[guinda]\u25cf[/guinda]"

# Categorias de riesgo por target
RISK_LEVELS = {
    "low": [
        "lint",
        "format",
        "check",
        "test",
        "report",
        "status",
        "info",
        "docs",
        "help",
        "show",
        "list",
        "validate",
        "describe",
        "summary",
        "coverage",
        "audit",
    ],
    "medium": [
        "train",
        "forecast",
        "predict",
        "extract",
        "process",
        "transform",
        "pipeline",
        "run",
        "build",
        "evaluate",
        "cv",
        "cross",
        "optimize",
        "tune",
        "compare",
        "benchmark",
    ],
    "high": [
        "clean",
        "delete",
        "remove",
        "purge",
        "reset",
        "deploy",
        "push",
        "destroy",
        "drop",
        "overwrite",
        "migrate",
        "init",
        "setup",
    ],
}

RISK_COLORS = {"low": "verde", "medium": "dorado", "high": "guinda"}
RISK_ICONS = {"low": ICO_CIRCLE_G, "medium": ICO_CIRCLE_Y, "high": ICO_CIRCLE_R}
RISK_LABELS = {"low": "BAJO", "medium": "MEDIO", "high": "ALTO"}
