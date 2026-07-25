"""C7.2-A/R15.2 — insumos de ejecución del bundle: catálogo y exposición PROYECTADA.

R15-C3: ``inputs/exposure_<source_id>.csv`` tiene schema por ``cve_ent`` y NO es el raw INEGI que
espera ``load_exposure_snapshot``; fingir que son intercambiables es la vía rápida a un bundle que
"carga" con la exposición equivocada. Aquí se fija un loader propio, puro y fail-closed, que lee
sólo desde el bundle y exige que el builder haya contrastado esos valores contra el dataset sellado.

Sin padecimientos ni conteos escritos: el universo sale del catálogo trackeado que se copia al
temporal, nunca de `runs/`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil

import pytest

from epiforecast.data.epi_dataset_spec import BASE_SEXES
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.release_contract import RUNTIME_CONFIG_SCHEMA, sha256_bytes
from epiforecast.runner.release_runtime import (
    RUNTIME_CONFIG_FILE,
    RUNTIME_DIR,
    load_runtime_inputs,
    read_projected_exposure,
)

CATALOGO = Path("config/geografia/entidades_mx.csv")
COLUMNS_BY_SEX = {"hombres": "Hombres", "mujeres": "Mujeres"}
TOTAL_COLUMN = "Total"
DATASET_DIGEST = "d" * 64


def _cve_ents() -> list[str]:
    with CATALOGO.open(encoding="utf-8") as fh:
        return sorted(fila["cve_ent"] for fila in csv.DictReader(fh))


def _escribir_exposicion(path: Path, cve_ents: list[str], **rarezas: object) -> None:
    filas = []
    for i, cve in enumerate(cve_ents, start=1):
        hombres, mujeres = 1000 * i, 1100 * i
        filas.append(
            {
                "cve_ent": cve,
                "Hombres": hombres,
                "Mujeres": mujeres,
                TOTAL_COLUMN: hombres + mujeres,
            }
        )
    for clave, valor in rarezas.items():
        if clave == "duplicar":
            filas.append(dict(filas[0]))
        elif clave == "quitar":
            filas.pop()
        elif clave == "extra":
            filas.append({"cve_ent": "99", "Hombres": 1, "Mujeres": 1, TOTAL_COLUMN: 2})
        else:
            filas[0][clave] = valor
    with path.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=["cve_ent", "Hombres", "Mujeres", TOTAL_COLUMN])
        escritor.writeheader()
        escritor.writerows(filas)


def _bundle(tmp_path: Path, **rarezas: object) -> Path:
    """Bundle mínimo con sólo ``runtime_inputs/`` (lo demás no lo mira este loader)."""
    raiz = tmp_path / "bundle"
    destino = raiz / RUNTIME_DIR
    destino.mkdir(parents=True)
    shutil.copy2(CATALOGO, destino / CATALOGO.name)
    exposicion = destino / "exposure_fuente_x.csv"
    _escribir_exposicion(exposicion, _cve_ents(), **rarezas)
    _escribir_config(raiz)
    return raiz


def _config(raiz: Path, **cambios: object) -> dict[str, object]:
    catalogo = raiz / RUNTIME_DIR / CATALOGO.name
    exposicion = raiz / RUNTIME_DIR / "exposure_fuente_x.csv"
    datos: dict[str, object] = {
        "schema": RUNTIME_CONFIG_SCHEMA,
        "disease_id": "x",
        "calendar": {"kind": "epi_mmwr", "observation_lag_weeks": 1},
        "expected_n_states": len(_cve_ents()),
        "geo_catalog": {
            "path": f"{RUNTIME_DIR}/{CATALOGO.name}",
            "sha256": sha256_bytes(catalogo.read_bytes()),
        },
        "exposure": {
            "path": f"{RUNTIME_DIR}/{exposicion.name}",
            "sha256": sha256_bytes(exposicion.read_bytes()),
            "source_id": "fuente_x",
            "reference": "CPV 2020",
            "cutoff": "2020-03-15",
            "columns_by_sex": dict(COLUMNS_BY_SEX),
            "total_column": TOTAL_COLUMN,
            "source_digest": "a" * 64,
            "dataset_check": {
                "dataset_id": "x_1",
                "dataset_digest": DATASET_DIGEST,
                "series": len(_cve_ents()) * len(BASE_SEXES),
                "verified": True,
            },
        },
        "dataset_config_digest": "b" * 64,
    }
    datos.update(cambios)
    return datos


def _escribir_config(raiz: Path, **cambios: object) -> None:
    (raiz / RUNTIME_DIR / RUNTIME_CONFIG_FILE).write_text(
        json.dumps(_config(raiz, **cambios), indent=2, sort_keys=True), encoding="utf-8"
    )


def _romper(raiz: Path, ruta: list[str], valor: object) -> None:
    path = raiz / RUNTIME_DIR / RUNTIME_CONFIG_FILE
    datos = json.loads(path.read_text(encoding="utf-8"))
    cursor = datos
    for clave in ruta[:-1]:
        cursor = cursor[clave]
    if valor is None:
        cursor.pop(ruta[-1], None)
    else:
        cursor[ruta[-1]] = valor
    path.write_text(json.dumps(datos, indent=2, sort_keys=True), encoding="utf-8")


# ── Camino verde ──────────────────────────────────────────────────────────────────────────────
def test_carga_catalogo_y_exposición_solo_desde_el_bundle(tmp_path):
    inputs = load_runtime_inputs(_bundle(tmp_path), expected_dataset_digest=DATASET_DIGEST)
    cve_ents = _cve_ents()
    assert inputs.catalog.cve_ents() == cve_ents
    assert sorted(inputs.exposure) == sorted((c, s) for c in cve_ents for s in BASE_SEXES)
    assert inputs.exposure[(cve_ents[0], "hombres")] == 1000
    assert inputs.exposure[(cve_ents[0], "mujeres")] == 1100
    assert inputs.source_id == "fuente_x"
    assert inputs.exposure_source_digest == "a" * 64


def test_read_projected_exposure_es_puro_y_no_lee_configuración_global(tmp_path):
    cve_ents = _cve_ents()
    path = tmp_path / "e.csv"
    _escribir_exposicion(path, cve_ents)
    mapa = read_projected_exposure(path, COLUMNS_BY_SEX, TOTAL_COLUMN, cve_ents, "x")
    assert len(mapa) == len(cve_ents) * len(BASE_SEXES)


# ── Rechazos del CSV proyectado ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("rareza", "patron"),
    [
        ({"duplicar": True}, "duplicad"),
        ({"quitar": True}, "cobertura"),
        ({"extra": True}, "cobertura"),
        ({"Hombres": 0}, "no positiv"),
        ({"Hombres": -5}, "no positiv"),
        ({"Hombres": 1.5}, "entero"),
        ({"Hombres": "muchos"}, "entero"),
        ({TOTAL_COLUMN: 7}, "Total"),
    ],
)
def test_la_exposición_proyectada_falla_cerrado(tmp_path, rareza, patron):
    raiz = _bundle(tmp_path, **rareza)
    _escribir_config(raiz)  # re-sella: la prueba mide el contenido, no el digest
    with pytest.raises(ArtifactValidationError, match=patron):
        load_runtime_inputs(raiz, expected_dataset_digest=DATASET_DIGEST)


def test_la_exposición_sin_la_columna_declarada_falla(tmp_path):
    raiz = _bundle(tmp_path)
    _romper(raiz, ["exposure", "columns_by_sex"], {"hombres": "Varones", "mujeres": "Mujeres"})
    with pytest.raises(ArtifactValidationError, match="columna"):
        load_runtime_inputs(raiz, expected_dataset_digest=DATASET_DIGEST)


def test_columns_by_sex_debe_cubrir_exactamente_los_sexos_base(tmp_path):
    raiz = _bundle(tmp_path)
    _romper(raiz, ["exposure", "columns_by_sex"], {"hombres": "Hombres"})
    with pytest.raises(ArtifactValidationError, match="sexos base"):
        load_runtime_inputs(raiz, expected_dataset_digest=DATASET_DIGEST)


# ── Rechazos de identidad de los insumos ──────────────────────────────────────────────────────
def test_un_byte_alterado_en_el_catálogo_invalida_el_bundle(tmp_path):
    raiz = _bundle(tmp_path)
    path = raiz / RUNTIME_DIR / CATALOGO.name
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ArtifactValidationError, match="digest"):
        load_runtime_inputs(raiz, expected_dataset_digest=DATASET_DIGEST)


def test_un_byte_alterado_en_la_exposición_invalida_el_bundle(tmp_path):
    raiz = _bundle(tmp_path)
    path = raiz / RUNTIME_DIR / "exposure_fuente_x.csv"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ArtifactValidationError, match="digest"):
        load_runtime_inputs(raiz, expected_dataset_digest=DATASET_DIGEST)


@pytest.mark.parametrize("archivo", [CATALOGO.name, "exposure_fuente_x.csv"])
def test_un_insumo_ausente_invalida_el_bundle(tmp_path, archivo):
    raiz = _bundle(tmp_path)
    (raiz / RUNTIME_DIR / archivo).unlink()
    with pytest.raises(ArtifactValidationError, match="ausente|ilegible"):
        load_runtime_inputs(raiz, expected_dataset_digest=DATASET_DIGEST)


@pytest.mark.parametrize(
    "ruta", [["schema"], ["disease_id"], ["geo_catalog"], ["exposure"], ["expected_n_states"]]
)
def test_una_clave_ausente_del_runtime_config_falla_cerrado(tmp_path, ruta):
    raiz = _bundle(tmp_path)
    _romper(raiz, ruta, None)
    with pytest.raises(ArtifactValidationError):
        load_runtime_inputs(raiz, expected_dataset_digest=DATASET_DIGEST)


def test_el_runtime_config_rechaza_un_schema_desconocido(tmp_path):
    raiz = _bundle(tmp_path)
    _romper(raiz, ["schema"], "runtime_config.v99")
    with pytest.raises(ArtifactValidationError, match="schema"):
        load_runtime_inputs(raiz, expected_dataset_digest=DATASET_DIGEST)


@pytest.mark.parametrize("ruta", ["/etc/passwd", "../fuera.csv", "runtime_inputs/../fuera.csv"])
def test_el_runtime_config_rechaza_rutas_absolutas_o_con_traversal(tmp_path, ruta):
    raiz = _bundle(tmp_path)
    _romper(raiz, ["geo_catalog", "path"], ruta)
    with pytest.raises(ArtifactValidationError):
        load_runtime_inputs(raiz, expected_dataset_digest=DATASET_DIGEST)


def test_el_runtime_config_no_lleva_rutas_del_workspace(tmp_path):
    """Ni una ruta absoluta ni `config/…` del repo: el bundle no depende del equipo que lo hizo."""
    raiz = _bundle(tmp_path)
    texto = (raiz / RUNTIME_DIR / RUNTIME_CONFIG_FILE).read_text(encoding="utf-8")
    assert str(tmp_path) not in texto
    assert '"config/' not in texto


# ── El contraste contra el dataset sellado (R15-C3) ───────────────────────────────────────────
def test_exige_que_el_builder_haya_contrastado_la_exposición_con_el_dataset(tmp_path):
    raiz = _bundle(tmp_path)
    _romper(raiz, ["exposure", "dataset_check", "verified"], False)
    with pytest.raises(ArtifactValidationError, match="contrast"):
        load_runtime_inputs(raiz, expected_dataset_digest=DATASET_DIGEST)


def test_el_contraste_debe_ser_contra_el_dataset_de_la_cadena(tmp_path):
    raiz = _bundle(tmp_path)
    with pytest.raises(ArtifactValidationError, match="dataset_digest"):
        load_runtime_inputs(raiz, expected_dataset_digest="c" * 64)


def test_el_contraste_debe_cubrir_todas_las_series_base(tmp_path):
    raiz = _bundle(tmp_path)
    _romper(raiz, ["exposure", "dataset_check", "series"], 3)
    with pytest.raises(ArtifactValidationError, match="series"):
        load_runtime_inputs(raiz, expected_dataset_digest=DATASET_DIGEST)
