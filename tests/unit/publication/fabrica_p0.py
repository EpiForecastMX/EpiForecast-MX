"""Fábrica de datos sintéticos para las pruebas del flujo semanal sellado.

Un contrato diminuto —dos entidades, una región, un padecimiento neuro y uno de conteo— y
los archivos que lo cumplen o lo rompen a voluntad. Nada de aquí toca datos reales; sirve
para que cada control se vea fallar por su motivo y no por el montaje.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from openpyxl import Workbook

from epiforecast import registry
from epiforecast.constants import INEGI_REGIONS
from epiforecast.publication.contratos_datos import SEXOS, ContratoCobertura, slug
from epiforecast.publication.weekly_staging import (
    ARCHIVO_ENTRADAS,
    DIR_INPUTS,
    VERSION_POLITICA,
    Boletin,
    RegistroHidratacion,
    sha256_de,
)

TRUE = shutil.which("true") or "/usr/bin/true"

# Padecimientos y regiones REALES (registry y constants, que es de donde el CLI deriva el
# contrato); sólo el catálogo de entidades es diminuto: dos, con un alias.
PADECIMIENTOS_NEURO = tuple(registry.production_cohort())
PADECIMIENTOS_CONTEO = tuple(registry.standalone_members(published_only=True))
PADECIMIENTOS = (*PADECIMIENTOS_NEURO, *PADECIMIENTOS_CONTEO)
PAD_NEURO = PADECIMIENTOS_NEURO[0]
PAD_CONTEO = PADECIMIENTOS_CONTEO[0]
CONTRATO = ContratoCobertura(
    neuro=tuple(slug(p) for p in PADECIMIENTOS_NEURO),
    conteo=tuple(slug(p) for p in PADECIMIENTOS_CONTEO),
    entidades=("aguascalientes", "mexico"),
    alias={"estado de mexico": "mexico", "edomex": "mexico"},
    regiones=tuple(slug(r) for r in INEGI_REGIONS),
)
ENTIDADES = ("Aguascalientes", "México")
REGIONES = tuple(f"region_{r}" for r in INEGI_REGIONS)
SEMANAS = ((2026, 30), (2026, 31))
RUTA_CONSOLIDADO = "data/processed/dataset_boletin_epidemiologico.csv"
RUTA_FORECAST = "reports/forecasts/prophet/all_forecast_prophet.csv"
RUTA_TABLA = "reports/ProdDetails/tabla_333_modelos_produccion.xlsx"
RUTA_DENGUE = "reports/ProdDetails/produccion_dengue.csv"

CATALOGO_CSV = (
    "cve_ent,nombre_canonico,nombre_inegi,macroregion_id,macroregion_name,aliases\n"
    "01,Aguascalientes,Aguascalientes,occidente,Occidente,Ags.\n"
    "15,México,México,centro,Centro,Estado de México|Edomex\n"
)


# ── datos que cumplen (o rompen) el contrato ─────────────────────────────────


def consolidado_csv(
    *,
    cortes: dict[str, tuple[int, int]] | None = None,
    quitar: set[tuple[str, str]] = frozenset(),
    duplicar: set[tuple[str, str]] = frozenset(),
    sustituir: dict[str, str] | None = None,
) -> str:
    """Filas (Anio, Semana, Entidad, Padecimiento, Casos_semana) para el contrato pequeño.

    `cortes` fija el último corte por padecimiento (por defecto todos en 2026-W31);
    `quitar` retira (padecimiento, entidad) de la última semana; `duplicar` la repite;
    `sustituir` cambia el nombre de una entidad por otro en todas las filas.
    """
    lineas = ["Anio,Semana,Entidad,Padecimiento,Casos_semana,Acumulado_hombres,Acumulado_mujeres"]
    cortes = cortes or {}
    for pad in PADECIMIENTOS:
        ultimo = cortes.get(pad, SEMANAS[-1])
        for anio, semana in SEMANAS:
            if (anio, semana) > ultimo:
                continue
            for entidad in ENTIDADES:
                if (anio, semana) == ultimo and (pad, entidad) in quitar:
                    continue
                nombre = (sustituir or {}).get(entidad, entidad)
                veces = 2 if (anio, semana) == ultimo and (pad, entidad) in duplicar else 1
                for _ in range(veces):
                    lineas.append(f"{anio},{semana},{nombre},{pad},3,10,12")
    return "\n".join(lineas) + "\n"


def _claves(pad: str) -> list[tuple[str, str]]:
    entidades = [*ENTIDADES, "Nacional"]
    if pad in PADECIMIENTOS_NEURO:
        entidades.extend(REGIONES)
    return [(e, s) for e in entidades for s in SEXOS]


def forecast_csv(
    *, faltan: set[tuple[str, str, str]] = frozenset(), extra: tuple[str, str, str] | None = None
) -> str:
    lineas = ["ds,yhat,meta_padecimiento,meta_entidad,meta_modo"]
    for pad in PADECIMIENTOS:
        for entidad, sexo in _claves(pad):
            if (pad, entidad, sexo) in faltan:
                continue
            for ds in ("2026-08-03", "2026-08-10"):
                lineas.append(f"{ds},1.0,{pad},{entidad},{sexo}")
    if extra:
        lineas.append(f"2026-08-03,1.0,{extra[0]},{extra[1]},{extra[2]}")
    return "\n".join(lineas) + "\n"


def tabla_xlsx(ruta: Path, *, duplicar: tuple[str, str, str] | None = None) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Produccion"
    ws.append(["numero", "padecimiento", "entidad", "sexo", "modelo_produccion"])
    n = 0
    for pad in PADECIMIENTOS:
        for entidad, sexo in _claves(pad):
            n += 1
            ws.append([n, pad, entidad, sexo, "Prophet"])
    if duplicar:
        ws.append([n + 1, *duplicar, "Prophet"])
    wb.save(ruta)


def produccion_dengue_csv(*, faltan: set[tuple[str, str]] = frozenset()) -> str:
    lineas = ["padecimiento,entidad,sexo,motor_productivo"]
    for entidad, sexo in _claves(PAD_CONTEO):
        if (entidad, sexo) in faltan:
            continue
        lineas.append(f"{PAD_CONTEO},{entidad},{sexo},NBGLM")
    return "\n".join(lineas) + "\n"


def knowledge_json(
    *,
    max_semana: int = 31,
    faltan: set[tuple[str, str]] = frozenset(),
    rosters_ok: bool = True,
) -> str:
    modelos = [
        {"padecimiento": pad, "entidad": entidad, "sexo": sexo, "modelo_produccion": "Prophet"}
        for pad in PADECIMIENTOS_NEURO
        for entidad, sexo in _claves(pad)
        if pad != PAD_NEURO or (entidad, sexo) not in faltan
    ]
    rosters = {
        "total_series": len(CONTRATO.claves_esperadas()) if rosters_ok else 999,
        "gallery_items": len(CONTRATO.zoom_esperado()),
        "por_cohorte": {"neuro": 21 * len(PADECIMIENTOS_NEURO), "dengue": 9},
    }
    return json.dumps(
        {"_version": "1.0", "max_semana": max_semana, "prod_models": modelos, "rosters": rosters},
        ensure_ascii=False,
    )


def zoom_json(*, faltan: set[str] = frozenset(), dengue_con_alias: bool = True) -> str:
    claves: dict[str, Any] = {}
    entidades = (
        "aguascalientes",
        "mexico",
        "nacional",
        *(f"region {r}" for r in CONTRATO.regiones),
    )
    for pad in CONTRATO.padecimientos:
        for entidad in entidades:
            nombre = entidad
            if pad == "dengue" and entidad == "mexico" and dengue_con_alias:
                nombre = "estado de mexico"
            for sexo in SEXOS:
                clave = f"{pad}|{nombre}|{sexo}"
                if clave in faltan:
                    continue
                claves[clave] = {"y": [1, 2, 3]}
    return json.dumps(claves)


# ── política, allowlist y repositorios ───────────────────────────────────────


def gate(nombre: str, argv: list[str] | None = None, *, cwd: str = "dashboard/") -> dict[str, Any]:
    return {
        "id": nombre,
        "argv": argv or [TRUE],
        "cwd": cwd,
        "timeout_s": 30,
        "entorno": {"heredar": [], "fijar": {}},
    }


def politica_cruda(
    superficies: tuple[str, ...],
    *,
    retirables: tuple[str, ...] = (),
    gates: list[dict[str, Any]] | None = None,
    prefijos: tuple[str, ...] = ("backend/reports/ProdDetails/", "dashboard/"),
) -> dict[str, Any]:
    return {
        "version": VERSION_POLITICA,
        "prefijos_administrados": sorted(prefijos),
        "patron_superficie": {
            "prefijo": "dashboard/",
            "sufijos": [".html", ".json"],
            "directorios_excluidos": ["node_modules"],
        },
        "superficies_verificables": sorted(set(superficies) | set(retirables)),
        "retirables": sorted(retirables),
        "gates": gates or [gate("cifras")],
    }


def lista_entradas_cruda(
    entradas: list[tuple[str, str, bool]] | None = None,
) -> dict[str, Any]:
    entradas = entradas or [
        (RUTA_CONSOLIDADO, "consolidado", True),
        (RUTA_FORECAST, "forecast", True),
    ]
    return {
        "version": "entradas/1",
        "directorio_boletines": "data/raw_PDFs",
        "entradas": [{"ruta": r, "rol": rol, "obligatoria": ob} for r, rol, ob in entradas],
    }


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def repo_git(
    raiz: Path,
    rastreados: dict[str, str | bytes],
    sin_rastrear: dict[str, str | bytes] | None = None,
) -> tuple[Path, str]:
    """Repositorio de usar y tirar: `rastreados` en el commit, `sin_rastrear` sólo en disco."""
    raiz.mkdir(parents=True, exist_ok=True)
    for rel, contenido in rastreados.items():
        destino = raiz / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contenido, bytes):
            destino.write_bytes(contenido)
        else:
            destino.write_text(contenido, encoding="utf-8")
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "prueba@ejemplo")
    _git(raiz, "config", "user.name", "Prueba")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-qm", "inicial")
    for rel, contenido in (sin_rastrear or {}).items():
        destino = raiz / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contenido, bytes):
            destino.write_bytes(contenido)
        else:
            destino.write_text(contenido, encoding="utf-8")
    return raiz.resolve(), _git(raiz, "rev-parse", "HEAD").strip()


def repo_backend(
    raiz: Path,
    *,
    politica: dict[str, Any],
    lista: dict[str, Any] | None = None,
    consolidado: str | None = None,
    forecast: str | None = None,
    extra_rastreados: dict[str, str] | None = None,
    extra_sin_rastrear: dict[str, str | bytes] | None = None,
) -> tuple[Path, str]:
    """Backend sintético: política, allowlist y catálogo en el HEAD; datos sin rastrear."""
    rastreados: dict[str, str | bytes] = {
        "config/publication/politica_censo.json": json.dumps(
            politica, indent=2, ensure_ascii=False
        )
        + "\n",
        "config/publication/entradas_semanales.json": json.dumps(
            lista or lista_entradas_cruda(), indent=2
        )
        + "\n",
        "config/geografia/entidades_mx.csv": CATALOGO_CSV,
        "reports/ProdDetails/tabla.csv": "viejo\n",
        "src/codigo.py": "print('sandbox')\n",
        ".gitignore": "data/\nreports/forecasts/\n",
    }
    rastreados.update(extra_rastreados or {})
    sin_rastrear: dict[str, str | bytes] = {
        RUTA_CONSOLIDADO: consolidado if consolidado is not None else consolidado_csv(),
        RUTA_FORECAST: forecast if forecast is not None else forecast_csv(),
    }
    sin_rastrear.update(extra_sin_rastrear or {})
    return repo_git(raiz, rastreados, sin_rastrear)


SITIO_EPIBOT: dict[str, str] = {
    "index.html": (
        "<h1>semana 31</h1>\n<script>\n"
        "  fetch('epibot/knowledge.json', { cache: 'no-store' }).then(function (r) { return r; });\n"
        "</script>\n"
    ),
    "epibot/index.html": (
        '<link rel="stylesheet" href="css/style.css?v=1">\n'
        '<script type="module" src="js/app.js?v=1"></script>\n'
    ),
    "epibot/js/app.js": (
        "import { loadKnowledge } from './kb.js?v=1';\nimport { norm } from './entities.js?v=1';\n"
    ),
    "epibot/js/kb.js": "const DATA_VERSION = '1';\nexport function loadKnowledge() {}\n",
    "epibot/js/entities.js": "export function norm(s) { return s; }\n",
    "epibot/css/style.css": "body { margin: 0; }\n",
    "epibot/knowledge.json": knowledge_json(),
    "epibot/zoom_series.json": zoom_json(),
}


def repo_dashboard(raiz: Path, archivos: dict[str, str] | None = None) -> tuple[Path, str]:
    return repo_git(raiz, dict(archivos if archivos is not None else SITIO_EPIBOT))


def superficies_de(archivos: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        sorted(f"dashboard/{rel}" for rel in archivos if rel.lower().endswith((".html", ".json")))
    )


# ── hidratación mínima para pruebas de biblioteca (sin git) ──────────────────


def hidrata_minimo(
    raiz_staging: Path,
    *,
    head_backend: str,
    consolidado: str | None = None,
    candidato: str | None = None,
    boletines: tuple[Boletin, ...] = (),
) -> RegistroHidratacion:
    """Deja en el staging lo que `hydrate` dejaría: copias bajo `inputs/`, sandbox y registro.

    `sella` relee todo esto de su sitio; las pruebas de biblioteca lo fabrican aquí en
    vez de pasar digests, que es justo lo que ya no se puede hacer.
    """
    texto_base = consolidado if consolidado is not None else consolidado_csv()
    texto_candidato = candidato if candidato is not None else texto_base
    inputs = raiz_staging / DIR_INPUTS
    (inputs / "boletines").mkdir(parents=True)
    (inputs / "consolidado_base.csv").write_text(texto_base, encoding="utf-8")
    sandbox = raiz_staging.parent / f"{raiz_staging.name}.sandbox" / "EpiForecast-MX"
    origen = sandbox / RUTA_CONSOLIDADO
    origen.parent.mkdir(parents=True)
    origen.write_text(texto_candidato, encoding="utf-8")
    entradas = {
        RUTA_CONSOLIDADO: {
            "rol": "consolidado",
            "bytes": len(texto_base.encode("utf-8")),
            "sha256": hashlib.sha256(texto_base.encode("utf-8")).hexdigest(),
        }
    }
    for boletin in boletines:
        copia = inputs / "boletines" / boletin.nombre
        copia.write_bytes(b"%PDF-" + boletin.nombre.encode())
        entradas[f"data/raw_PDFs/{boletin.nombre}"] = {
            "rol": "pdf",
            "bytes": copia.stat().st_size,
            "sha256": sha256_de(copia),
        }
    registro = RegistroHidratacion(
        head_backend=head_backend,
        lista={"version": "entradas/1", "sha256": "1" * 64},
        sandbox=str(sandbox.resolve()),
        consolidado=RUTA_CONSOLIDADO,
        entradas=entradas,
        boletines=tuple(
            Boletin(
                b.nombre,
                b.url,
                (inputs / "boletines" / b.nombre).stat().st_size,
                sha256_de(inputs / "boletines" / b.nombre),
            )
            for b in boletines
        ),
        cobertura={},
    )
    registro.escribe(raiz_staging)
    return registro


def esta_hidratado(raiz_staging: Path) -> bool:
    return (raiz_staging / ARCHIVO_ENTRADAS).is_file()
