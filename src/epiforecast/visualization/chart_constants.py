"""Layout, font, and styling constants for forecast charts."""

# ── Layout ───────────────────────────────────────────────────────────
FIGSIZE = (20, 8)
MARGINS = {"bottom": 0.13, "top": 0.89, "left": 0.05, "right": 0.975}
SUPTITLE_Y = 0.96
LEGEND_ANCHOR = (0.515, 0.04)

# ── Font sizes ───────────────────────────────────────────────────────
FS_SUPTITLE = 16
FS_SUBTITLE = 11
FS_LABEL = 11
FS_LEGEND = 9.5
FS_COVID = 6.5
FS_TICK = 10

# ── Line / marker styling ───────────────────────────────────────────
LW_FORECAST = 2.2
LW_SPINE = 0.5
LW_OUTLIER_EDGE = 1.0
ALPHA_BAND = 0.20
ALPHA_OBS = 0.45
ALPHA_FORECAST_ZONE = 0.04
ALPHA_COVID = 0.05
ALPHA_GRID = 0.25
SIZE_OBS = 15
ROLLING_OBS = 4  # ventana de suavizado para observaciones (semanas)
SIZE_OUTLIER = 70
