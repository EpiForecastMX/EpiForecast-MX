"""Refresca la entrada semanal de Novedades (news.json) del sitio con cifras frescas.

Genera/actualiza el item "Datos" de la semana vigente en
``EpiForecast-IMSS-Dashboard/news.json`` (fuente de verdad que renderizan tanto
la landing como ``novedades.html``) y bumpea los datelines "Edición de la
semana N, AAAA" + el fallback estatico del lead en ``index.html``.

Se corre dentro de ``make update-week`` (paso landing) para que la seccion de
Novedades NO vuelva a quedar stale tras un boletin nuevo. Idempotente: si ya
existe la entrada de la misma semana/anio, la reemplaza (no duplica).

Cifras (todas: pronostico productivo vs real fresco del boletin, in-sample):
  - desviacion del acumulado 2026 por padecimiento (sum yhat / sum real - 1),
  - SMAPE/MASE de la serie nacional por padecimiento.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import html as html_mod
import json
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = REPO_ROOT.parent / "EpiForecast-IMSS-Dashboard"

NEURO = ["Depresión", "Parkinson", "Alzheimer"]
MESES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
CREAM = "color:var(--cream)"


def _pct(x: float) -> str:
    """+4.0&#37; / &#8722;31.4&#37; (signo tipografico, entidad de %)."""
    sign = "+" if x >= 0 else "&#8722;"
    return f"{sign}{abs(x):.1f}&#37;"


def _fecha_es(d: datetime) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _iso_wk(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.isocalendar().week.astype(int)


def _iso_yr(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.isocalendar().year.astype(int)


def compute_figures() -> dict[str, Any]:
    """Calcula semana vigente, desviacion del acumulado y SMAPE/MASE nacional."""
    real = pd.read_csv(REPO_ROOT / "data/processed/dataset_boletin_epidemiologico.csv")
    year = int(real["Anio"].max())
    r = real[real["Anio"] == year]
    real_nac = r.groupby(["Padecimiento", "Semana"])["Casos_semana"].sum()

    tab = pd.read_csv(REPO_ROOT / "data/processed/tableau.csv", low_memory=False)
    tab = tab[(tab["entidad"] == "Nacional") & (tab["meta_modo"] == "general")].copy()
    tab["yr"], tab["wk"] = _iso_yr(tab["ds"]), _iso_wk(tab["ds"])
    tab = tab[tab["yr"] == year]

    figs: dict[str, dict[str, float]] = {}
    wk_headline = 0
    for p in NEURO:
        rr = real_nac.loc[p]
        wk_obs = int(rr.index.max())
        wk_headline = max(wk_headline, wk_obs)
        real_tot = float(rr.loc[rr.index <= wk_obs].sum())
        g = tab[tab["padecimiento"] == p]
        pron_tot = float(g[g["wk"] <= wk_obs]["yhat"].sum())
        figs[p] = {
            "dev": (pron_tot / real_tot - 1) * 100,
            "smape": float(g["smape"].iloc[0]),
            "mase": float(g["mase"].iloc[0]),
        }

    figs["Dengue"], wk_d = _dengue_figures(real_nac, year)
    wk_headline = max(wk_headline, wk_d)
    return {"year": year, "week": wk_headline, "figs": figs}


def _dengue_figures(real_nac: pd.Series, year: int) -> tuple[dict[str, float], int]:
    """Dengue nacional: motor productivo (produccion_dengue) vs real fresco."""
    prod = pd.read_csv(REPO_ROOT / "reports/ProdDetails/produccion_dengue.csv")
    row = prod[(prod["entidad"] == "Nacional") & (prod["sexo"] == "general")].iloc[0]
    motor = str(row["motor_productivo"]).lower()
    smape = float(row["smape_ganador"])

    fc = pd.read_csv(
        REPO_ROOT / f"reports/forecasts/{motor}/all_forecast_{motor}.csv", low_memory=False
    )
    fc = fc[
        (fc["meta_padecimiento"] == "Dengue")
        & (fc["meta_entidad"] == "Nacional")
        & (fc["meta_modo"] == "general")
    ].copy()
    fc["yr"], fc["wk"] = _iso_yr(fc["ds"]), _iso_wk(fc["ds"])
    fc = fc[fc["yr"] == year]

    rr = real_nac.loc["Dengue"]
    wk_obs = int(rr.index.max())
    real_tot = float(rr.loc[rr.index <= wk_obs].sum())
    pron_tot = float(fc[fc["wk"] <= wk_obs]["yhat"].sum())

    # MASE = MAE(modelo) / MAE(naive estacional, real anio-1 misma semana)
    m = pd.DataFrame({"wk": rr.index, "y": rr.to_numpy()})
    m = m[m["wk"] <= wk_obs].merge(fc[["wk", "yhat"]], on="wk", how="inner")
    mae = float(np.mean(np.abs(m["yhat"] - m["y"]))) if len(m) else float("nan")
    mase = _dengue_mase(year, mae)
    return {"dev": (pron_tot / real_tot - 1) * 100, "smape": smape, "mase": mase}, wk_obs


def _dengue_mase(year: int, mae: float) -> float:
    """MAE del modelo / MAE naive estacional (real anio-1, misma semana)."""
    real = pd.read_csv(REPO_ROOT / "data/processed/dataset_boletin_epidemiologico.csv")
    dg = real[real["Padecimiento"] == "Dengue"]
    cur = dg[dg["Anio"] == year].groupby("Semana")["Casos_semana"].sum()
    prev = dg[dg["Anio"] == year - 1].groupby("Semana")["Casos_semana"].sum()
    naive = [abs(cur[s] - prev[s]) for s in cur.index if s in prev.index]
    mae_naive = float(np.mean(naive)) if naive else float("nan")
    return mae / mae_naive if mae_naive and not np.isnan(mae_naive) else float("nan")


def build_item(data: dict[str, Any]) -> dict[str, Any]:
    year, wk, f = data["year"], data["week"], data["figs"]
    today = datetime.now()

    def s(p: str) -> str:
        return f"{f[p]['smape']:.1f}&#37; / {f[p]['mase']:.2f}"

    body0 = (
        f'Se integró el Boletín SINAVE hasta la <strong style="{CREAM}">semana {wk} '
        f"de {year}</strong> en los cuatro padecimientos. Sobre las semanas transcurridas "
        f"del año, el total pronosticado se desvía del realmente observado en "
        f'<strong style="{CREAM}">{_pct(f["Depresión"]["dev"])} en Depresión</strong>, '
        f'<strong style="{CREAM}">{_pct(f["Parkinson"]["dev"])} en Parkinson</strong>, '
        f'<strong style="{CREAM}">{_pct(f["Alzheimer"]["dev"])} en Alzheimer</strong> y '
        f'<strong style="{CREAM}">{_pct(f["Dengue"]["dev"])} en Dengue</strong>. '
        f"Las series de conteo bajo (Alzheimer, Parkinson) muestran mayor variación entre "
        f"recalibraciones; el acumulado se ajusta con cada reentrenamiento de modelos."
    )
    body1 = (
        f'Precisión de la serie nacional por padecimiento (<strong style="{CREAM}">SMAPE / '
        f'MASE</strong>): Depresión <strong style="{CREAM}">{s("Depresión")}</strong>, '
        f'Parkinson <strong style="{CREAM}">{s("Parkinson")}</strong>, '
        f'Alzheimer <strong style="{CREAM}">{s("Alzheimer")}</strong> y '
        f'Dengue <strong style="{CREAM}">{s("Dengue")}</strong>. '
        f"El MASE por debajo de 1 indica que el modelo supera a la persistencia estacional "
        f"(repetir el mismo periodo del año anterior)."
    )
    return {
        "date": _fecha_es(today),
        "iso": today.strftime("%Y-%m-%d"),
        "type": "datos",
        "tag": "Datos",
        "featured": False,
        "title": f"Ya contamos con la semana epidemiológica {wk} de {year}",
        "body": [body0, body1],
        "link": {
            "href": "Reports/index.html",
            "text": "Ver real vs pronóstico en la galería",
            "svg": (
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="2.5"><path d="M5 12h14"/><path d="M12 5l7 7-7 7"/></svg>'
            ),
        },
    }


def upsert_news(item: dict[str, Any], news_path: Path) -> None:
    d = json.loads(news_path.read_text(encoding="utf-8"))
    # dedupe por titulo (codifica semana+anio): re-correr la misma semana reemplaza.
    items = [it for it in d.get("items", []) if it.get("title") != item["title"]]
    d["items"] = [item] + items
    d["_generated"] = item["iso"]
    news_path.write_text(json.dumps(d, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


SUB_NEUTRAL = (
    "Se integró el Boletín SINAVE en los cuatro padecimientos; el detalle por padecimiento "
    "y las métricas SMAPE/MASE aparecen en esta sección."
)
_RE_BANNER = re.compile(
    r'(<div class="news-banner-row" id="newsBannerRow">)(.*?)(\n {8}</div>)', re.DOTALL
)


def _plain(fragmento: str) -> str:
    """Texto sin etiquetas y con blancos colapsados (espejo de `plain()` del JS)."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragmento or "")).strip()


def _summary(it: dict[str, Any]) -> str:
    """Espejo de `summary()` del JS: `summary` explícito o el primer párrafo, a 150 chars."""
    if it.get("summary"):
        return str(it["summary"])
    t = _plain(html_mod.unescape((it.get("body") or [""])[0]))
    if len(t) > 150:
        t = re.sub(r"\s+\S*$", "", t[:147]) + "…"
    return t


def _esc(x: Any) -> str:
    return html_mod.escape(str(x if x is not None else ""), quote=False)


def render_news_banner(items: list[dict[str, Any]]) -> str:
    """HTML interior de `#newsBannerRow`: lead = items[0], minis = items[1:3].

    Es el fallback que se ve cuando falla el fetch de `news.json`, así que replica lo que
    pinta el JS (`leadHtml`/`miniHtml`) para que estático y dinámico digan lo mismo. Para la
    nota semanal el subtítulo es neutral y estable (las cifras las inyecta el JS).
    """
    if not items:
        raise ValueError("news.json sin items: no hay con qué escribir el fallback estático")
    top = items[:3]
    lead = top[0]
    tipo = lead.get("type") or "datos"
    sub = SUB_NEUTRAL if tipo == "datos" else _summary(lead)
    partes = [
        '          <a href="novedades.html" class="news-lead">',
        '            <div class="news-lead-meta">',
        f'              <span class="news-date">{_esc(lead.get("date"))}</span>',
        f'              <span class="news-tag news-tag--{_esc(tipo)}">{_esc(lead.get("tag"))}</span>',
        "            </div>",
        f'            <div class="news-lead-title">{_esc(lead.get("title"))}</div>',
        f'            <div class="news-lead-sub">{_esc(sub)}</div>',
        "          </a>",
        '          <div class="news-mini-list">',
    ]
    for it in top[1:]:
        t = it.get("type") or "datos"
        partes += [
            '            <a href="novedades.html" class="news-mini">',
            f'              <span class="news-tag news-tag--{_esc(t)}">{_esc(it.get("tag"))}</span>',
            f'              <span class="news-mini-title">{_esc(it.get("title"))}</span>',
            f'              <span class="news-mini-date">{_esc(it.get("date"))}</span>',
            "            </a>",
        ]
    partes.append("          </div>")
    return "\n" + "\n".join(partes)


def _items_para_el_banner(dashboard: Path, item: dict[str, Any]) -> list[dict[str, Any]]:
    """Los items de `news.json` del destino, exigiendo que la nota semanal vaya primero."""
    news_path = dashboard / "news.json"
    if not news_path.is_file():
        raise FileNotFoundError(
            f"falta {news_path}: el fallback estático se escribe desde news.json"
        )
    items: list[dict[str, Any]] = json.loads(news_path.read_text(encoding="utf-8")).get(
        "items", []
    )
    if not items or items[0].get("title") != item["title"]:
        raise ValueError(
            "news.json no tiene la nota semanal como primer item; corre upsert_news antes"
        )
    return items


def bump_static_html(data: dict[str, Any], item: dict[str, Any], dashboard: Path) -> None:
    """Datelines 'Edición de la semana N, AAAA' + fallback estático completo del banner.

    `dashboard` es obligatorio. Antes se ignoraba la ruta recibida por `main` y se
    escribia sobre la constante global, de modo que `news.json` iba al destino pedido
    pero `index.html` y `novedades.html` acababan siempre en el sitio real. En el
    refresh semanal eso significaba dos cosas a la vez: el sello quedaba incompleto,
    porque esos dos archivos nunca entraban en el inventario, y el sitio se modificaba
    aunque la corrida no publicara nada.

    El banner estático se reescribe ENTERO desde `news.json` (lead + minis). Antes sólo se
    sustituían fecha y subtítulo sin condición y el titular sólo si ya era una nota semanal:
    con el CALASS destacado a mano, W33 salió a producción con titular del CALASS, fecha y
    subtítulo de W33 y la lista secundaria sin actualizar (2-sep-2026).
    """
    wk, year = data["week"], data["year"]
    for name in ("index.html", "novedades.html"):
        p = dashboard / name
        if not p.exists():
            continue
        html = p.read_text(encoding="utf-8")
        html = re.sub(
            r"Edición de la semana \d+, \d{4}", f"Edición de la semana {wk}, {year}", html
        )
        if name == "index.html":
            bloque = render_news_banner(_items_para_el_banner(dashboard, item))
            encontrados = list(_RE_BANNER.finditer(html))
            n = len(encontrados)
            if n == 1:
                m = encontrados[0]
                html = html[: m.start(2)] + bloque + html[m.end(2) :]
            if n != 1:
                raise ValueError(
                    'index.html sin el bloque <div class="news-banner-row" id="newsBannerRow">: '
                    "no se puede escribir el fallback estático"
                )
        p.write_text(html, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dashboard", type=Path, default=DASHBOARD)
    args = ap.parse_args()
    news_path = args.dashboard / "news.json"

    data = compute_figures()
    f = data["figs"]
    # guard: las 4 series con desviacion finita; si la forma del dato se rompe,
    # falla aqui en vez de publicar una nota a medias.
    assert set(f) == {"Depresión", "Parkinson", "Alzheimer", "Dengue"}, f"figs={set(f)}"
    assert all(np.isfinite(f[p]["dev"]) for p in f), "desviacion no finita"
    assert 1 <= data["week"] <= 53, f"semana invalida: {data['week']}"

    item = build_item(data)
    upsert_news(item, news_path)
    bump_static_html(data, item, args.dashboard)

    print(
        f"  news.json -> sem {data['week']}/{data['year']} | "
        + " ".join(
            f"{p[:3]} {f[p]['dev']:+.1f}%"
            for p in ["Depresión", "Parkinson", "Alzheimer", "Dengue"]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
