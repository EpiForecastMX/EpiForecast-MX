"""Refresca la entrada semanal de Novedades (news.json) del sitio con la semana integrada.

Genera/actualiza el item "Datos" de la semana vigente en ``news.json`` (fuente de verdad que
renderizan tanto la landing como ``novedades.html``) y bumpea los datelines "Edición de la
semana N, AAAA" + el fallback estatico del lead en ``index.html``.

Ronda W39 (plan de cierre del 14-oct-2026): la nota ya NO lee ``data/processed/tableau.csv`` —
congelado en W8 y excluido de esta entrega—. Sus entradas son explícitas y se declaran con su hash:

* el consolidado del boletín (``--boletin``): la semana vigente es la última en la que los cuatro
  padecimientos publicados tienen sus 32 entidades; si no comparten la misma semana, falla;
* el seguimiento posterior al corte (``--seguimiento``): debe terminar en esa misma semana y da
  el corte de los modelos y las semanas evaluadas;
* el catálogo canónico (``--catalogo``): el número de gráficos de la galería, que debe coincidir
  con las series productivas;
* el agregado estatal canónico (``--agregado``): debe hablar del mismo corte.

La nota NO publica cifras de desempeño (decisión del autor, 14-oct-2026): ni la desviación del
acumulado ni SMAPE/MASE; los dos puntos del seguimiento no se presentan como precisión del producto.
Idempotente: repetir la misma semana con las mismas entradas no añade ni reescribe la nota.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import html as html_mod
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd

from epiforecast.utils.semana_epi import fin_semana_boletin, inicio_semana_boletin

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = REPO_ROOT.parent / "EpiForecast-IMSS-Dashboard"
PROD_DETAILS = REPO_ROOT / "reports" / "ProdDetails"

PUBLICADOS = ["Depresión", "Parkinson", "Alzheimer", "Dengue"]
N_ENTIDADES = 32
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


def _fecha_es(d: Any) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def semana_vigente(boletin: Path) -> tuple[int, int]:
    """La última semana del boletín con las 32 entidades, común a los cuatro publicados."""
    df = pd.read_csv(boletin, usecols=["Anio", "Semana", "Entidad", "Padecimiento"])
    df["Entidad"] = df["Entidad"].replace({"Distrito Federal": "Ciudad de México"})
    n = df.groupby(["Padecimiento", "Anio", "Semana"])["Entidad"].nunique().reset_index()
    completas = n[n["Entidad"] >= N_ENTIDADES]
    ultimas = {}
    for pad in PUBLICADOS:
        g = completas[completas["Padecimiento"] == pad]
        if g.empty:
            raise ValueError(f"{pad} sin ninguna semana completa en el boletín")
        ultimas[pad] = max(zip(g["Anio"].astype(int), g["Semana"].astype(int), strict=True))
    if len(set(ultimas.values())) != 1:
        raise ValueError(f"corte desigual entre los padecimientos publicados: {ultimas}")
    return next(iter(ultimas.values()))


def compute_data(
    boletin: Path, seguimiento: Path, catalogo: Path, agregado: Path
) -> dict[str, Any]:
    """Semana integrada, corte y vistas disponibles, comprobados entre sí; con la procedencia."""
    year, wk = semana_vigente(boletin)
    seg = json.loads(seguimiento.read_text(encoding="utf-8"))
    ult = seg.get("ultima_semana_observada") or {}
    if (ult.get("anio"), ult.get("semana")) != (year, wk):
        raise ValueError(
            f"el seguimiento termina en {ult.get('etiqueta')} y el boletín en {year}-W{wk:02d}"
        )
    corte = seg["corte"]["etiqueta"]
    evaluadas = [s["etiqueta"] for s in seg.get("semanas", [])]
    if not evaluadas or len(evaluadas) != seg.get("semanas_evaluadas"):
        raise ValueError("el seguimiento no declara sus semanas evaluadas")
    cat = json.loads(catalogo.read_text(encoding="utf-8"))
    graficos = cat.get("gallery_item_count")
    if graficos is None or graficos != cat.get("production_series_count"):
        raise ValueError(
            f"catálogo: {graficos} gráficos frente a {cat.get('production_series_count')} series"
        )
    ag = json.loads(agregado.read_text(encoding="utf-8"))
    if ag.get("corte") != corte:
        raise ValueError(f"el agregado estatal habla del corte {ag.get('corte')}, no de {corte}")
    return {
        "year": year,
        "week": wk,
        "inicio": inicio_semana_boletin(year, wk),
        "fin": fin_semana_boletin(year, wk),
        "corte": corte,
        "semanas_evaluadas": evaluadas,
        "graficos": int(graficos),
        "procedencia": {str(p): _sha(p) for p in (boletin, seguimiento, catalogo, agregado)},
    }


def _semana_txt(etiqueta: str) -> str:
    return str(int(etiqueta.split("-W")[1]))


def build_item(data: dict[str, Any], fecha: datetime | None = None) -> dict[str, Any]:
    year, wk = data["year"], data["week"]
    hoy = fecha or datetime.now()
    ini, fin = data["inicio"], data["fin"]
    periodo = f"{ini.day} de {MESES[ini.month - 1]} al {fin.day} de {MESES[fin.month - 1]}"
    sem = [_semana_txt(e) for e in data["semanas_evaluadas"]]
    sem_txt = sem[0] if len(sem) == 1 else ", ".join(sem[:-1]) + " y " + sem[-1]
    corte = _semana_txt(data["corte"])
    body0 = (
        f'Se integró el Boletín SINAVE hasta la <strong style="{CREAM}">semana {wk} '
        f"de {year}</strong> ({periodo}) en los cuatro padecimientos, con las "
        f"{N_ENTIDADES} entidades."
    )
    body1 = (
        f"Los pronósticos son los de los modelos con corte en la semana {corte}; no hubo "
        f"reentrenamiento. La galería publica {data['graficos']} gráficos y la validación "
        f"muestra el seguimiento de las semanas {sem_txt}: el pronóstico guardado frente a lo "
        f"observado esa misma semana, sin calificarlo. Son semanas de diagnóstico, no el "
        f"resultado general del modelo."
    )
    return {
        "date": _fecha_es(hoy),
        "iso": hoy.strftime("%Y-%m-%d"),
        "type": "datos",
        "tag": "Datos",
        "featured": False,
        "title": f"Ya contamos con la semana epidemiológica {wk} de {year}",
        "body": [body0, body1],
        "link": {
            "href": "Reports/index.html",
            "text": "Ver observado y pronóstico en la galería",
            "svg": (
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="2.5"><path d="M5 12h14"/><path d="M12 5l7 7-7 7"/></svg>'
            ),
        },
    }


def upsert_news(item: dict[str, Any], news_path: Path) -> dict[str, Any]:
    """Pone la nota semanal primero, sin duplicarla. Devuelve la nota que quedó publicada.

    Si ya existe la de la misma semana (mismo título) con el mismo contenido, no se toca: la
    fecha original se conserva y el archivo no se reescribe (re-aplicar W39 no añade nada).
    """
    d = json.loads(news_path.read_text(encoding="utf-8"))
    previas: list[dict[str, Any]] = d.get("items", [])
    igual: dict[str, Any] | None = next(
        (it for it in previas if it.get("title") == item["title"]), None
    )
    clave = ("type", "tag", "featured", "title", "body", "link")
    if igual is not None and all(igual.get(k) == item.get(k) for k in clave):
        if previas and previas[0] is igual:
            return igual
        item = igual
    items = [it for it in previas if it.get("title") != item["title"]]
    d["items"] = [item] + items
    d["_generated"] = item["iso"]
    news_path.write_text(json.dumps(d, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    return item


SUB_NEUTRAL = (
    "Se integró el Boletín SINAVE en los cuatro padecimientos; el detalle por padecimiento "
    "aparece en esta sección."
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dashboard", type=Path, default=DASHBOARD)
    ap.add_argument(
        "--boletin",
        type=Path,
        default=REPO_ROOT / "data/processed/dataset_boletin_epidemiologico.csv",
    )
    ap.add_argument(
        "--seguimiento", type=Path, default=PROD_DETAILS / "seguimiento_post_corte.json"
    )
    ap.add_argument(
        "--catalogo", type=Path, default=PROD_DETAILS / "catalogo_canonico_counts.json"
    )
    ap.add_argument("--agregado", type=Path, default=PROD_DETAILS / "agregado_estatal_neuro.json")
    ap.add_argument("--fecha", default=None, help="AAAA-MM-DD de la nota (por defecto, hoy)")
    ap.add_argument("--evidencia", type=Path, default=None, help="JSON con entradas y hashes")
    args = ap.parse_args(argv)

    data = compute_data(args.boletin, args.seguimiento, args.catalogo, args.agregado)
    fecha = datetime.strptime(args.fecha, "%Y-%m-%d") if args.fecha else None
    item = upsert_news(build_item(data, fecha), args.dashboard / "news.json")
    bump_static_html(data, item, args.dashboard)
    if args.evidencia is not None:
        args.evidencia.write_text(
            json.dumps(
                {
                    "semana": f"{data['year']}-W{data['week']:02d}",
                    "corte": data["corte"],
                    "semanas_evaluadas": data["semanas_evaluadas"],
                    "graficos": data["graficos"],
                    "procedencia": data["procedencia"],
                    "nota": item["title"],
                    "fecha_nota": item["iso"],
                    "lee_tableau": False,
                },
                ensure_ascii=False,
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )
    print(
        f"  news.json -> sem {data['week']}/{data['year']} · corte {data['corte']} · "
        f"{data['graficos']} gráficos · nota del {item['iso']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
