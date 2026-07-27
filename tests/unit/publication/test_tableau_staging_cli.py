"""C7.6-ADAPTERS-B0 — el CLI operativo y la recuperación explícita.

Lo que protege: que `inspect` no mute, que `stage` y `recover` sean dry-run de verdad, que
`--apply` esté cerrado con cuatro llaves y que la recuperación se proponga —ligada al inventario que
la justifica— antes de tocar nada.

Ninguna prueba abre una hoja: el sink se inyecta y el entorno también.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pandas as pd
import pytest
from scripts.tableau_staging import RC_ERROR, RC_OK, RC_REFUSED, main, namespace_declarado

from epiforecast.publication.recovery import (
    ACTION_CONSOLIDATE_BACKUP,
    ACTION_DROP_NEXT,
    ACTION_RESTORE_BACKUP,
    ACTION_RESTORE_PREVIOUS,
    PLAN_SCHEMA,
    SOURCE_BACKUP,
    SOURCE_NONE,
    SOURCE_PREVIOUS,
    STATE_BACKUP_ORPHAN,
    STATE_CLEAN,
    STATE_NEXT_RESIDUE,
    STATE_RECOVERY_REQUIRED,
    apply_recovery,
    plan_bytes,
    recovery_plan,
    table_inventory,
)
from epiforecast.publication.sheets_sink import PRODUCTION_ID_ENV, STAGING_ID_ENV
from epiforecast.publication.tableau_adapter import (
    SUFFIX_BACKUP,
    SUFFIX_NEXT,
    SUFFIX_PREVIOUS,
    TABLE_FORECAST,
    TABLE_RELEASES,
    MemorySink,
    build_tables,
    managed_tables,
    promote,
)
from tests.unit.publication.test_tableau_adapter import _shard

ID_STAGING = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF"
ID_PRODUCCION = "1ZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZ"
ENTORNO = {STAGING_ID_ENV: ID_STAGING, PRODUCTION_ID_ENV: ID_PRODUCCION}


def _correr(argv, sink=None, entorno=ENTORNO):
    salida = io.StringIO()
    rc = main(argv, sink=sink, entorno=entorno, salida=salida)
    return rc, salida.getvalue()


def _json(texto: str) -> dict:
    return json.loads(texto.strip())


def _promovido(tmp_path):
    """Sink con una promoción ya hecha: activas + __previous, sin residuos."""
    tablas = build_tables(_shard(tmp_path, filas=3))
    sink = MemorySink(
        {
            TABLE_FORECAST: pd.DataFrame([{"x": "vieja"}]),
            TABLE_RELEASES: tablas.releases.assign(verdict="PASS"),
        }
    )
    promote(sink, tablas)
    sink.operaciones.clear()
    return sink, tablas


# ── Condiciones de seguridad ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("comando", [["inspect"], ["recover"]])
def test_sin_hoja_de_staging_declarada_no_corre_ningun_comando(comando):
    rc, salida = _correr(comando, sink=MemorySink(), entorno={})
    assert rc == RC_REFUSED
    assert STAGING_ID_ENV in salida and salida.startswith("REFUSED")


def test_si_staging_y_produccion_son_la_misma_hoja_se_niega():
    entorno = {STAGING_ID_ENV: ID_STAGING, PRODUCTION_ID_ENV: ID_STAGING}
    rc, salida = _correr(["inspect"], sink=MemorySink(), entorno=entorno)
    assert rc == RC_REFUSED
    assert "MISMA hoja" in salida


@pytest.mark.parametrize(
    ("extra", "patron"),
    [
        ([], "--expect-inventory"),
        (["--expect-inventory", "0" * 64], "--confirm-spreadsheet-id"),
        (["--expect-inventory", "0" * 64, "--confirm-spreadsheet-id", ID_PRODUCCION], "confirm"),
    ],
)
def test_apply_sin_las_cuatro_condiciones_se_niega_antes_de_tocar_nada(tmp_path, extra, patron):
    sink, _ = _promovido(tmp_path)
    rc, salida = _correr(["recover", "--apply", *extra], sink=sink)
    assert rc == RC_REFUSED
    assert patron in salida
    assert sink.operaciones == [], "ni una operación sobre el sink"


def test_apply_con_un_inventario_distinto_no_aplica(tmp_path):
    sink, _ = _promovido(tmp_path)
    rc, salida = _correr(
        [
            "recover",
            "--apply",
            "--expect-inventory",
            "f" * 64,
            "--confirm-spreadsheet-id",
            ID_STAGING,
        ],
        sink=sink,
    )
    assert rc == RC_ERROR
    assert "no es el inventario actual" in salida
    assert not [op for op in sink.operaciones if op.startswith(("write:", "rename:", "drop:"))]


def test_el_namespace_no_se_amplia_por_bandera():
    assert namespace_declarado() == managed_tables()
    assert len(namespace_declarado()) == 8


# ── inspect ────────────────────────────────────────────────────────────────────────────────────
def test_inspect_no_muta_y_reporta_lo_ajeno_sin_tocarlo(tmp_path):
    sink, _ = _promovido(tmp_path)
    sink.write_table("scaffold", pd.DataFrame([{"x": "legacy"}]))
    sink.operaciones.clear()

    rc, salida = _correr(["inspect"], sink=sink)
    datos = _json(salida)

    assert rc == RC_OK
    assert datos["mutating"] is False
    assert sink.operaciones == []
    assert datos["foreign"] == ["scaffold"], "se ve, y no se toca"
    assert set(datos["tables"]) == {
        TABLE_FORECAST,
        TABLE_RELEASES,
        f"{TABLE_FORECAST}{SUFFIX_PREVIOUS}",
        f"{TABLE_RELEASES}{SUFFIX_PREVIOUS}",
    }
    assert datos["states"] == {TABLE_FORECAST: STATE_CLEAN, TABLE_RELEASES: STATE_CLEAN}
    assert len(datos["inventory_digest"]) == 64


def test_inspect_es_byte_determinista(tmp_path):
    sink, _ = _promovido(tmp_path)
    assert _correr(["inspect"], sink=sink)[1] == _correr(["inspect"], sink=sink)[1]


# ── stage ──────────────────────────────────────────────────────────────────────────────────────
def test_stage_dry_run_ensena_el_plan_y_no_escribe(tmp_path):
    sink, _ = _promovido(tmp_path)
    raiz = _shard(tmp_path, filas=3)

    rc, salida = _correr(["stage", "--shard", str(raiz)], sink=sink)
    datos = _json(salida)

    assert rc == RC_OK
    assert datos["applied"] is False
    assert sink.operaciones == [], "dry-run no es un ensayo con escritura"
    assert datos["steps"] == [
        f"write:{TABLE_FORECAST}{SUFFIX_NEXT}",
        f"write:{TABLE_RELEASES}{SUFFIX_NEXT}",
        f"rename:{TABLE_FORECAST}->{TABLE_FORECAST}{SUFFIX_BACKUP}",
        f"rename:{TABLE_FORECAST}{SUFFIX_NEXT}->{TABLE_FORECAST}",
        f"rename:{TABLE_RELEASES}->{TABLE_RELEASES}{SUFFIX_BACKUP}",
        f"rename:{TABLE_RELEASES}{SUFFIX_NEXT}->{TABLE_RELEASES}",
        f"drop:{TABLE_FORECAST}{SUFFIX_PREVIOUS}",
        f"rename:{TABLE_FORECAST}{SUFFIX_BACKUP}->{TABLE_FORECAST}{SUFFIX_PREVIOUS}",
        f"drop:{TABLE_RELEASES}{SUFFIX_PREVIOUS}",
        f"rename:{TABLE_RELEASES}{SUFFIX_BACKUP}->{TABLE_RELEASES}{SUFFIX_PREVIOUS}",
    ]
    assert datos["rows"] == {TABLE_FORECAST: 3, TABLE_RELEASES: 1}


def test_stage_sobre_una_hoja_vacia_no_propone_consolidar(tmp_path):
    raiz = _shard(tmp_path, filas=2)
    rc, salida = _correr(["stage", "--shard", str(raiz)], sink=MemorySink())
    pasos = _json(salida)["steps"]
    assert rc == RC_OK
    assert not [p for p in pasos if SUFFIX_BACKUP in p], "sin activas no hay nada que respaldar"
    assert pasos == [
        f"write:{TABLE_FORECAST}{SUFFIX_NEXT}",
        f"write:{TABLE_RELEASES}{SUFFIX_NEXT}",
        f"rename:{TABLE_FORECAST}{SUFFIX_NEXT}->{TABLE_FORECAST}",
        f"rename:{TABLE_RELEASES}{SUFFIX_NEXT}->{TABLE_RELEASES}",
    ]


def test_stage_con_residuos_falla_por_el_preflight_al_aplicar(tmp_path):
    sink, _ = _promovido(tmp_path)
    sink.write_table(f"{TABLE_FORECAST}{SUFFIX_NEXT}", pd.DataFrame([{"x": "a medio camino"}]))
    inventario = table_inventory(sink)
    sink.operaciones.clear()

    rc, salida = _correr(
        [
            "stage",
            "--shard",
            str(_shard(tmp_path, filas=2)),
            "--apply",
            "--expect-inventory",
            inventario["inventory_digest"],
            "--confirm-spreadsheet-id",
            ID_STAGING,
        ],
        sink=sink,
    )
    assert rc == RC_ERROR
    assert "RECOVERY_REQUIRED" in salida
    assert not [op for op in sink.operaciones if op.startswith(("write:", "rename:", "drop:"))]


# ── recover ────────────────────────────────────────────────────────────────────────────────────
def test_un_namespace_limpio_no_propone_nada(tmp_path):
    sink, _ = _promovido(tmp_path)
    rc, salida = _correr(["recover"], sink=sink)
    datos = _json(salida)
    assert rc == RC_OK
    assert datos["status"] == "CLEAN"
    assert datos["actions"] == []
    assert sink.operaciones == []


def test_el_plan_de_recuperacion_es_byte_determinista(tmp_path):
    sink, _ = _promovido(tmp_path)
    sink.write_table(f"{TABLE_RELEASES}{SUFFIX_NEXT}", pd.DataFrame([{"x": 1}]))
    uno = plan_bytes(recovery_plan(sink))
    otro = plan_bytes(recovery_plan(sink))
    assert uno == otro
    assert b"timestamp" not in uno and b"generated_at" not in uno


def test_un_next_huerfano_se_clasifica_y_se_propone_retirar(tmp_path):
    sink, _ = _promovido(tmp_path)
    sink.write_table(f"{TABLE_FORECAST}{SUFFIX_NEXT}", pd.DataFrame([{"x": "nunca se activó"}]))

    plan = recovery_plan(sink)
    assert plan["states"][TABLE_FORECAST] == STATE_NEXT_RESIDUE
    assert plan["actions"] == [
        {"action": ACTION_DROP_NEXT, "table": TABLE_FORECAST, "state": STATE_NEXT_RESIDUE}
    ]

    resultado = apply_recovery(sink, plan)
    assert resultado["status"] == "RECOVERED"
    assert f"{TABLE_FORECAST}{SUFFIX_NEXT}" not in sink.list_tables()
    assert resultado["states_after"][TABLE_FORECAST] == STATE_CLEAN


def test_una_activa_ausente_se_restaura_desde_su_respaldo(tmp_path):
    """El caso peor: la promoción murió entre el respaldo y la activación."""
    sink, _ = _promovido(tmp_path)
    vieja = sink.read_table(TABLE_FORECAST)
    sink.rename_table(TABLE_FORECAST, f"{TABLE_FORECAST}{SUFFIX_BACKUP}")

    plan = recovery_plan(sink)
    assert plan["states"][TABLE_FORECAST] == STATE_RECOVERY_REQUIRED
    assert plan["actions"][0]["action"] == ACTION_RESTORE_BACKUP

    resultado = apply_recovery(sink, plan)
    assert resultado["status"] == "RECOVERED"
    pd.testing.assert_frame_equal(sink.read_table(TABLE_FORECAST), vieja)
    assert f"{TABLE_FORECAST}{SUFFIX_BACKUP}" not in sink.list_tables()


def test_un_respaldo_junto_a_la_activa_se_consolida_sin_perder_el_punto_de_retorno(tmp_path):
    sink, _ = _promovido(tmp_path)
    respaldo = pd.DataFrame([{"x": "la de la promoción anterior"}])
    sink.write_table(f"{TABLE_RELEASES}{SUFFIX_BACKUP}", respaldo)
    activa = sink.read_table(TABLE_RELEASES)

    plan = recovery_plan(sink)
    assert plan["states"][TABLE_RELEASES] == STATE_BACKUP_ORPHAN
    assert plan["actions"] == [
        {
            "action": ACTION_CONSOLIDATE_BACKUP,
            "table": TABLE_RELEASES,
            "state": STATE_BACKUP_ORPHAN,
        }
    ]

    apply_recovery(sink, plan)
    pd.testing.assert_frame_equal(sink.read_table(TABLE_RELEASES), activa)
    pd.testing.assert_frame_equal(sink.read_table(f"{TABLE_RELEASES}{SUFFIX_PREVIOUS}"), respaldo)
    assert f"{TABLE_RELEASES}{SUFFIX_BACKUP}" not in sink.list_tables()


def test_aplicar_un_plan_viejo_se_rechaza(tmp_path):
    sink, _ = _promovido(tmp_path)
    sink.write_table(f"{TABLE_FORECAST}{SUFFIX_NEXT}", pd.DataFrame([{"x": 1}]))
    plan = recovery_plan(sink)
    sink.drop_table(f"{TABLE_FORECAST}{SUFFIX_NEXT}")  # alguien más se adelantó

    with pytest.raises(Exception, match="inventario cambió"):
        apply_recovery(sink, plan)


def test_la_recuperacion_no_borra_fuera_del_namespace(tmp_path):
    sink, _ = _promovido(tmp_path)
    for ajena in ("scaffold", "real", "otra_cosa"):
        sink.write_table(ajena, pd.DataFrame([{"x": ajena}]))
    sink.write_table(f"{TABLE_FORECAST}{SUFFIX_NEXT}", pd.DataFrame([{"x": 1}]))
    plan = recovery_plan(sink)
    sink.operaciones.clear()

    apply_recovery(sink, plan)
    tocadas = {op.split(":")[1].split("->")[0] for op in sink.operaciones if ":" in op}
    assert not tocadas - set(managed_tables()), f"tocó algo ajeno: {tocadas}"
    for ajena in ("scaffold", "real", "otra_cosa"):
        assert ajena in sink.list_tables()


def test_el_plan_declara_su_esquema_y_su_inventario(tmp_path):
    sink, _ = _promovido(tmp_path)
    plan = recovery_plan(sink)
    assert plan["schema"] == PLAN_SCHEMA
    assert plan["inventory_digest"] == table_inventory(sink)["inventory_digest"]


# ── Shard real ─────────────────────────────────────────────────────────────────────────────────
RAIZ_REAL = os.getenv("C7_SHARD_ROOT")


@pytest.mark.skipif(not RAIZ_REAL, reason="requiere C7_SHARD_ROOT con el staging del shard real")
def test_shard_real_produce_5772_mas_1_y_el_plan_de_tabs_esperado():
    raices = sorted(Path(RAIZ_REAL or "").glob("*/*/shard_manifest.json"))
    assert raices, "no hay shard bajo C7_SHARD_ROOT"
    shard = raices[0].parent

    rc, salida = _correr(["stage", "--shard", str(shard)], sink=MemorySink())
    datos = _json(salida)

    assert rc == RC_OK
    assert datos["rows"] == {TABLE_FORECAST: 5772, TABLE_RELEASES: 1}
    assert datos["steps"] == [
        f"write:{TABLE_FORECAST}{SUFFIX_NEXT}",
        f"write:{TABLE_RELEASES}{SUFFIX_NEXT}",
        f"rename:{TABLE_FORECAST}{SUFFIX_NEXT}->{TABLE_FORECAST}",
        f"rename:{TABLE_RELEASES}{SUFFIX_NEXT}->{TABLE_RELEASES}",
    ]
    assert datos["applied"] is False
    assert set(datos["digests"]) == {TABLE_FORECAST, TABLE_RELEASES}


# ── Regresiones de la auditoría R102 ──────────────────────────────────────────────────────────
def test_apply_sin_la_variable_productiva_se_niega(tmp_path):
    """R102-P0-1: sin ella, «staging ≠ producción» no falla — es que no se puede comprobar."""
    sink, _ = _promovido(tmp_path)
    inventario = table_inventory(sink)
    sink.operaciones.clear()

    rc, salida = _correr(
        [
            "recover",
            "--apply",
            "--expect-inventory",
            inventario["inventory_digest"],
            "--confirm-spreadsheet-id",
            ID_STAGING,
        ],
        sink=sink,
        entorno={STAGING_ID_ENV: ID_STAGING},
    )
    assert rc == RC_REFUSED
    assert PRODUCTION_ID_ENV in salida
    assert sink.operaciones == [], "ni una operación, ni una autenticación"


def test_los_dry_run_si_corren_con_solo_la_hoja_de_staging(tmp_path):
    """Mirar no es escribir: para inspeccionar basta declarar staging."""
    sink, _ = _promovido(tmp_path)
    for argv in (["inspect"], ["recover"]):
        rc, _ = _correr(argv, sink=sink, entorno={STAGING_ID_ENV: ID_STAGING})
        assert rc == RC_OK, argv
    assert sink.operaciones == []


def test_solo_next_y_nada_mas_no_se_borra_nada(tmp_path):
    """R102-P0-2: antes borraba los dos __next y luego informaba error, con el namespace vacío."""
    tablas = build_tables(_shard(tmp_path, filas=3))
    sink = MemorySink(
        {
            f"{TABLE_FORECAST}{SUFFIX_NEXT}": tablas.forecast,
            f"{TABLE_RELEASES}{SUFFIX_NEXT}": tablas.releases,
        }
    )
    antes = {n: sink.read_table(n) for n in sink.list_tables()}
    sink.operaciones.clear()

    plan = recovery_plan(sink)
    assert plan["status"] == "RECOVERY_REQUIRED"
    assert plan["actions"] == [], "no se propone nada que empeore el estado"
    assert plan["blocked"] == [TABLE_FORECAST, TABLE_RELEASES]
    assert plan["sources"] == {TABLE_FORECAST: SOURCE_NONE, TABLE_RELEASES: SOURCE_NONE}

    with pytest.raises(Exception, match="no tiene activa, respaldo ni previa"):
        apply_recovery(sink, plan)

    assert sink.operaciones == [], "el sink queda byte-idéntico"
    assert sorted(sink.list_tables()) == sorted(antes)
    for nombre, frame in antes.items():
        pd.testing.assert_frame_equal(sink.read_table(nombre), frame)


def test_una_activa_ausente_con_previa_se_restaura_explicitamente(tmp_path):
    """Gate 9: o se restaura desde __previous y se verifica, o no se toca. Nunca queda peor."""
    sink, _ = _promovido(tmp_path)
    previa = sink.read_table(f"{TABLE_FORECAST}{SUFFIX_PREVIOUS}")
    sink.drop_table(TABLE_FORECAST)  # sin activa y sin respaldo

    plan = recovery_plan(sink)
    assert plan["sources"][TABLE_FORECAST] == SOURCE_PREVIOUS
    assert plan["blocked"] == []
    assert plan["actions"] == [
        {
            "action": ACTION_RESTORE_PREVIOUS,
            "table": TABLE_FORECAST,
            "state": STATE_RECOVERY_REQUIRED,
        }
    ]

    resultado = apply_recovery(sink, plan)
    assert resultado["status"] == "RECOVERED"
    pd.testing.assert_frame_equal(sink.read_table(TABLE_FORECAST), previa)
    assert f"{TABLE_FORECAST}{SUFFIX_PREVIOUS}" not in sink.list_tables()


def test_el_respaldo_gana_a_la_previa_como_origen(tmp_path):
    """Con las dos disponibles, la activa vuelve del respaldo: es la copia más reciente."""
    sink, _ = _promovido(tmp_path)
    respaldo = pd.DataFrame([{"x": "la que se apartó"}])
    sink.drop_table(TABLE_FORECAST)
    sink.write_table(f"{TABLE_FORECAST}{SUFFIX_BACKUP}", respaldo)

    plan = recovery_plan(sink)
    assert plan["sources"][TABLE_FORECAST] == SOURCE_BACKUP
    apply_recovery(sink, plan)
    pd.testing.assert_frame_equal(sink.read_table(TABLE_FORECAST), respaldo)


def test_una_combinacion_mixta_no_ejecuta_media_recuperacion(tmp_path):
    """Gate 10: una tabla arreglable y la otra no ⇒ no se toca ninguna."""
    sink, _ = _promovido(tmp_path)
    # runner_releases sí puede volver desde su respaldo…
    releases = sink.read_table(TABLE_RELEASES)
    sink.drop_table(TABLE_RELEASES)
    sink.write_table(f"{TABLE_RELEASES}{SUFFIX_BACKUP}", releases)
    # …y runner_forecast no tiene de dónde volver.
    sink.drop_table(TABLE_FORECAST)
    sink.drop_table(f"{TABLE_FORECAST}{SUFFIX_PREVIOUS}")
    sink.write_table(f"{TABLE_FORECAST}{SUFFIX_NEXT}", pd.DataFrame([{"x": "a medias"}]))
    antes = {n: sink.read_table(n) for n in sink.list_tables()}
    sink.operaciones.clear()

    plan = recovery_plan(sink)
    assert plan["blocked"] == [TABLE_FORECAST]
    assert plan["sources"][TABLE_RELEASES] == SOURCE_BACKUP, "sí tenía arreglo"
    assert plan["actions"] == [], "y aun así no se propone ninguna"

    with pytest.raises(Exception, match="no tiene activa, respaldo ni previa"):
        apply_recovery(sink, plan)

    assert sink.operaciones == []
    assert sorted(sink.list_tables()) == sorted(antes)
    for nombre, frame in antes.items():
        pd.testing.assert_frame_equal(sink.read_table(nombre), frame)


def test_el_cli_reporta_el_bloqueo_sin_mutar(tmp_path):
    tablas = build_tables(_shard(tmp_path, filas=2))
    sink = MemorySink({f"{TABLE_FORECAST}{SUFFIX_NEXT}": tablas.forecast})
    sink.operaciones.clear()

    rc, salida = _correr(["recover"], sink=sink)
    datos = _json(salida)
    assert rc == RC_OK, "el dry-run informa; no es él quien falla"
    assert datos["status"] == "RECOVERY_REQUIRED"
    assert datos["blocked"] == [TABLE_FORECAST, TABLE_RELEASES]
    assert datos["actions"] == []
    assert "reason" in datos
    assert sink.operaciones == []
