"""Explorador de datos interactivo del boletin epidemiologico."""

import unicodedata

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .data_cache import ProjectDataCache


def _strip_accents(s: str) -> str:
    """Elimina acentos para comparacion insensible."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# Barra Unicode para graficos inline
BAR_CHARS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"


def _bar(value: float, max_val: float, width: int = 20) -> str:
    """Genera barra Unicode proporcional."""
    if max_val == 0:
        return ""
    ratio = value / max_val
    filled = int(ratio * width)
    return (
        f"[dorado]{BAR_CHARS[-1] * filled}[/dorado][gris]{BAR_CHARS[0] * (width - filled)}[/gris]"
    )


def _show_full_summary(console: Console, cache: ProjectDataCache) -> None:
    """Muestra resumen completo del boletin."""
    df = cache.boletin
    if df is None:
        console.print("[gris]  No se encontró el boletín epidemiológico.[/gris]")
        return

    console.print()

    # Resumen general
    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("K", style="gris")
    info_table.add_column("V", style="blanco")
    info_table.add_row("Registros totales", f"[dorado]{len(df):,}[/dorado]")
    info_table.add_row("Columnas", str(len(df.columns)))

    if "Entidad" in df.columns:
        info_table.add_row("Entidades", str(df["Entidad"].nunique()))
    if "Padecimiento" in df.columns:
        info_table.add_row("Padecimientos", str(df["Padecimiento"].nunique()))

    date_cols = [c for c in df.columns if "semana" in c.lower() or "fecha" in c.lower()]
    if date_cols:
        col = date_cols[0]
        info_table.add_row("Rango temporal", f"{df[col].min()} a {df[col].max()}")

    console.print(
        Panel(
            info_table,
            title="[dorado]BOLETÍN EPIDEMIOLÓGICO[/dorado]",
            border_style="verde.dim",
            padding=(1, 2),
        )
    )

    # Desglose por padecimiento
    if "Padecimiento" in df.columns:
        pad_table = Table(
            title="[dorado]DESGLOSE POR PADECIMIENTO[/dorado]",
            show_header=True,
            header_style="dorado",
            box=box.SIMPLE,
            padding=(0, 1),
            expand=True,
        )
        pad_table.add_column("Padecimiento", style="blanco", min_width=15)
        pad_table.add_column("Registros", justify="right", style="dorado")
        pad_table.add_column("Porcentaje", justify="right", style="gris")
        pad_table.add_column("Distribución", min_width=22)

        counts = df["Padecimiento"].value_counts()
        max_count = counts.max()
        for pad, count in counts.items():
            pct = count / len(df) * 100
            bar = _bar(count, max_count)
            pad_table.add_row(str(pad), f"{count:,}", f"{pct:.1f}%", bar)

        console.print(pad_table)

    # Top 5 estados
    if "Entidad" in df.columns:
        val_cols = [c for c in df.columns if "caso" in c.lower() or "incidencia" in c.lower()]
        if val_cols:
            val_col = val_cols[0]
            top_states = df.groupby("Entidad")[val_col].sum().nlargest(5)
        else:
            top_states = df["Entidad"].value_counts().head(5)

        state_table = Table(
            title="[dorado]TOP 5 ENTIDADES[/dorado]",
            show_header=True,
            header_style="dorado",
            box=box.SIMPLE,
            padding=(0, 1),
            expand=True,
        )
        state_table.add_column("#", width=3, style="gris")
        state_table.add_column("Entidad", style="blanco", min_width=25)
        state_table.add_column("Valor", justify="right", style="dorado")
        state_table.add_column("", min_width=22)

        max_val = top_states.max()
        for i, (state, val) in enumerate(top_states.items(), 1):
            bar = _bar(val, max_val)
            state_table.add_row(str(i), str(state), f"{int(val):,}", bar)

        console.print(state_table)

    console.print()


def _show_filtered(
    console: Console,
    cache: ProjectDataCache,
    filtro: str,
) -> None:
    """Muestra datos filtrados por padecimiento o estado."""
    df = cache.boletin
    if df is None:
        console.print("[gris]  No se encontró el boletín epidemiológico.[/gris]")
        return

    filtro_norm = _strip_accents(filtro.lower())
    subset = None
    label = filtro

    # Filtrar por padecimiento
    if "Padecimiento" in df.columns:
        for pad in df["Padecimiento"].unique():
            if filtro_norm in _strip_accents(str(pad).lower()):
                subset = df[df["Padecimiento"] == pad]
                label = str(pad)
                break

    # Filtrar por entidad
    if subset is None and "Entidad" in df.columns:
        for ent in df["Entidad"].unique():
            if filtro_norm in _strip_accents(str(ent).lower()):
                subset = df[df["Entidad"] == ent]
                label = str(ent)
                break

    if subset is None or subset.empty:
        console.print(
            f"[alerta]No se encontraron datos para '{filtro}'.[/alerta]",
        )
        return

    console.print()
    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("K", style="gris")
    info_table.add_column("V", style="blanco")
    info_table.add_row("Filtro", f"[dorado]{label}[/dorado]")
    info_table.add_row("Registros", f"{len(subset):,}")

    if "Entidad" in subset.columns:
        info_table.add_row("Entidades", str(subset["Entidad"].nunique()))

    date_cols = [c for c in subset.columns if "semana" in c.lower() or "fecha" in c.lower()]
    if date_cols:
        col = date_cols[0]
        info_table.add_row("Rango", f"{subset[col].min()} a {subset[col].max()}")

    console.print(
        Panel(
            info_table,
            title=f"[dorado]DATOS: {label}[/dorado]",
            border_style="verde.dim",
            padding=(1, 2),
        )
    )
    console.print()


def show_data_explorer(
    console: Console,
    cache: ProjectDataCache,
    args: str = "",
) -> None:
    """Punto de entrada del explorador de datos."""
    filtro = args.strip()
    if filtro:
        _show_filtered(console, cache, filtro)
    else:
        _show_full_summary(console, cache)
