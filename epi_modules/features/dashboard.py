"""Panel de control multipanel Rich Layout."""

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table

from .data_cache import ProjectDataCache


def _build_data_panel(cache: ProjectDataCache) -> Panel:
    """Panel de datos."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("K", style="gris", min_width=14)
    table.add_column("V", style="blanco")

    df = cache.boletin
    if df is not None:
        table.add_row("Registros", f"[dorado]{len(df):,}[/dorado]")
        if "Padecimiento" in df.columns:
            table.add_row("Padecimientos", str(df["Padecimiento"].nunique()))
        if "Entidad" in df.columns:
            table.add_row("Entidades", str(df["Entidad"].nunique()))
        date_cols = [c for c in df.columns if "semana" in c.lower() or "fecha" in c.lower()]
        if date_cols:
            col = date_cols[0]
            table.add_row("Última", str(df[col].max()))
    else:
        table.add_row("[gris]Sin datos[/gris]", "")

    return Panel(table, title="[verde]DATOS[/verde]", border_style="verde.dim", padding=(0, 1))


def _build_models_panel(cache: ProjectDataCache) -> Panel:
    """Panel de modelos de produccion."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("K", style="gris", min_width=14)
    table.add_column("V", style="blanco")

    prod = cache.prod_models
    if prod is not None:
        table.add_row("Total", f"[dorado]{len(prod)}[/dorado]")
        if "modelo_produccion" in prod.columns:
            for motor, count in prod["modelo_produccion"].value_counts().items():
                pct = count / len(prod) * 100
                table.add_row(str(motor), f"{count} ({pct:.0f}%)")
    else:
        inv = cache.model_inventory
        if inv:
            total = sum(inv.values())
            table.add_row("Total .pkl", f"[dorado]{total}[/dorado]")
            for name, count in sorted(inv.items()):
                table.add_row(name, str(count))
        else:
            table.add_row("[gris]Sin modelos[/gris]", "")

    return Panel(
        table,
        title="[verde]MODELOS PRODUCCIÓN[/verde]",
        border_style="verde.dim",
        padding=(0, 1),
    )


def _build_metrics_panel(cache: ProjectDataCache) -> Panel:
    """Panel de metricas SMAPE."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("K", style="gris", min_width=14)
    table.add_column("V", style="blanco")

    prod = cache.prod_models
    if prod is not None and "smape_prod" in prod.columns and "padecimiento" in prod.columns:
        for pad in sorted(prod["padecimiento"].unique()):
            subset = prod[prod["padecimiento"] == pad]
            smape = subset["smape_prod"].mean()
            color = "verde" if smape < 30 else "dorado" if smape < 50 else "guinda"
            table.add_row(str(pad), f"[{color}]{smape:.1f}%[/{color}]")
        # General
        smape_all = prod["smape_prod"].mean()
        table.add_row("", "")
        table.add_row("Promedio", f"[dorado]{smape_all:.1f}%[/dorado]")
    else:
        table.add_row("[gris]Sin métricas[/gris]", "")

    return Panel(
        table,
        title="[verde]MÉTRICAS (SMAPE)[/verde]",
        border_style="verde.dim",
        padding=(0, 1),
    )


def _build_config_panel(cache: ProjectDataCache) -> Panel:
    """Panel de configuracion."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("K", style="gris", min_width=14)
    table.add_column("V", style="blanco")

    cfg = cache.config
    if cfg:
        table.add_row("Activo", f"[dorado]{cfg.get('modelo_activo', '?')}[/dorado]")
        pad = cfg.get("padecimiento", {})
        table.add_row("Padecimiento", str(pad.get("tipo", "General")))
        pred = cfg.get("prediccion", {})
        table.add_row("Horizonte", f"{pred.get('periodo', 52)} sem")
    else:
        table.add_row("[gris]Sin config[/gris]", "")

    import platform

    table.add_row("Python", platform.python_version())

    return Panel(
        table,
        title="[verde]CONFIGURACIÓN[/verde]",
        border_style="verde.dim",
        padding=(0, 1),
    )


def _build_alerts_panel(cache: ProjectDataCache) -> Panel:
    """Panel de alertas."""
    alerts = []

    prod = cache.prod_models
    if prod is not None:
        if "smape_prod" in prod.columns:
            bad = (prod["smape_prod"] > 100).sum()
            if bad > 0:
                alerts.append(f"[guinda][!] {bad} modelos con SMAPE > 100%[/guinda]")
            else:
                alerts.append("[verde][OK] Todos los modelos SMAPE < 100%[/verde]")

        if "overfitting" in prod.columns:
            alto = prod["overfitting"].astype(str).str.contains("Alto", na=False).sum()
            if alto > 0:
                alerts.append(f"[dorado][!] {alto} modelos con overfitting Alto[/dorado]")

        if "leakage" in prod.columns:
            sospechoso = (
                prod["leakage"]
                .astype(str)
                .str.contains(
                    "Sospechoso",
                    na=False,
                )
                .sum()
            )
            if sospechoso > 0:
                alerts.append(f"[guinda][!] {sospechoso} modelos con sospecha de leakage[/guinda]")
            else:
                alerts.append("[verde][OK] Sin sospecha de leakage[/verde]")
    else:
        alerts.append("[gris]Sin datos de producción para diagnosticar[/gris]")

    content = "\n".join(alerts) if alerts else "[gris]Sin alertas[/gris]"
    return Panel(
        content,
        title="[verde]ALERTAS[/verde]",
        border_style="verde.dim",
        padding=(0, 1),
    )


def show_dashboard(console: Console, cache: ProjectDataCache) -> None:
    """Muestra dashboard multipanel."""
    console.print()

    # Construir paneles
    data_panel = _build_data_panel(cache)
    models_panel = _build_models_panel(cache)
    metrics_panel = _build_metrics_panel(cache)
    config_panel = _build_config_panel(cache)
    alerts_panel = _build_alerts_panel(cache)

    # Layout
    layout = Layout()
    layout.split_column(
        Layout(name="top", size=10),
        Layout(name="mid", size=10),
        Layout(name="bottom", size=6),
    )
    layout["top"].split_row(
        Layout(data_panel, name="data"),
        Layout(models_panel, name="models"),
    )
    layout["mid"].split_row(
        Layout(metrics_panel, name="metrics"),
        Layout(config_panel, name="config"),
    )
    layout["bottom"].update(alerts_panel)

    console.print(
        Panel(
            layout,
            title="[dorado]DASHBOARD · EpiForecast-MX[/dorado]",
            border_style="dorado",
            padding=(0, 0),
        )
    )
    console.print()
