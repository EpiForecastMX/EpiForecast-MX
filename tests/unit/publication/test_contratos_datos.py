"""Controles del contrato exacto de cobertura (P0.1): conjuntos, no conteos.

Cada negativo conserva el conteo cuando puede —una entidad sustituida por otra, una clave
duplicada que rellena el hueco de otra— para que lo que falle sea la identidad del
conjunto y no una cifra.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from epiforecast.publication.contratos_datos import (
    ContratoCobertura,
    revisa_aditivo,
    revisa_candidato,
    revisa_consolidado,
    revisa_forecasts_listados,
    revisa_produccion_dengue,
    revisa_tabla_produccion,
    slug,
)
from epiforecast.publication.weekly_staging import StagingError
from tests.unit.publication import fabrica_p0 as fab


def _archivo(tmp_path: Path, nombre: str, texto: str) -> Path:
    ruta = tmp_path / nombre
    ruta.write_text(texto, encoding="utf-8")
    return ruta


# ── el contrato ───────────────────────────────────────────────────────────────


def test_los_conjuntos_se_derivan_del_contrato() -> None:
    assert len(fab.CONTRATO.productos("Depresión")) == 21  # (2 + nacional + 4 regiones) × 3
    assert len(fab.CONTRATO.productos("Dengue")) == 9  # (2 + nacional) × 3
    assert len(fab.CONTRATO.claves_esperadas()) == 72  # 3 × 21 + 9
    assert len(fab.CONTRATO.zoom_esperado()) == 84  # 4 × 7 × 3


def test_el_contrato_canonico_da_las_cifras_publicas() -> None:
    """333 neuro + 99 Dengue = 432 series; 4 × 111 = 444 en la galería. Derivadas, no escritas."""
    canonico = ContratoCobertura.canonico()

    assert len(canonico.entidades) == 32
    assert len(canonico.regiones) == 4
    assert {len(canonico.productos(p)) for p in canonico.neuro} == {111}
    assert len(canonico.claves_esperadas()) == 432
    assert len(canonico.zoom_esperado()) == 444


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("México", "mexico"),
        ("Estado de México", "mexico"),
        ("edomex", "mexico"),
        ("AGUASCALIENTES", "aguascalientes"),
        ("Nacional", "nacional"),
        ("region_Rural / dispersa", "region rural dispersa"),
        ("region urbana media", "region urbana media"),
        ("Jalisco", None),
        ("region_Norte", None),
    ],
)
def test_la_identidad_de_una_entidad_no_es_su_ortografia(
    nombre: str, esperado: str | None
) -> None:
    assert fab.CONTRATO.entidad_canonica(nombre) == esperado
    assert slug("Depresión") == "depresion"


def test_el_catalogo_se_lee_del_head_y_se_compara_con_el_worktree(tmp_path: Path) -> None:
    repo, head = fab.repo_backend(
        tmp_path / "repo", politica=fab.politica_cruda(("dashboard/index.html",))
    )

    contrato = ContratoCobertura.del_head(repo, head)
    assert contrato.entidades == ("aguascalientes", "mexico")

    (repo / "config" / "geografia" / "entidades_mx.csv").write_text(
        fab.CATALOGO_CSV + "14,Jalisco,Jalisco,occidente,Occidente,Jal.\n", encoding="utf-8"
    )
    with pytest.raises(StagingError, match="difiere de la versión"):
        ContratoCobertura.del_head(repo, head)


# ── consolidado: paridad, entidades exactas, unicidad ───────────────────────


def test_un_consolidado_completo_pasa(tmp_path: Path) -> None:
    ruta = _archivo(tmp_path, "c.csv", fab.consolidado_csv())

    cobertura = revisa_consolidado(ruta, fab.CONTRATO, fab.PADECIMIENTOS)

    assert cobertura.pasa
    assert cobertura.cifras["cortes"] == {slug(p): (2026, 31) for p in fab.PADECIMIENTOS}


def test_una_entidad_ausente_en_la_ultima_semana_falla(tmp_path: Path) -> None:
    ruta = _archivo(tmp_path, "c.csv", fab.consolidado_csv(quitar={(fab.PAD_CONTEO, "México")}))

    cobertura = revisa_consolidado(ruta, fab.CONTRATO, fab.PADECIMIENTOS)

    assert not cobertura.pasa
    assert any("dengue 2026-W31: faltan entidades ['mexico']" in p for p in cobertura.problemas)


def test_una_entidad_sustituida_conserva_el_conteo_y_aun_asi_falla(tmp_path: Path) -> None:
    """Mismo número de filas; otra entidad. Contar no lo ve, el conjunto sí."""
    ruta = _archivo(tmp_path, "c.csv", fab.consolidado_csv(sustituir={"México": "Jalisco"}))

    cobertura = revisa_consolidado(ruta, fab.CONTRATO, fab.PADECIMIENTOS)

    assert not cobertura.pasa
    assert any("fuera del catálogo ['Jalisco']" in p for p in cobertura.problemas)
    assert any("faltan entidades ['mexico']" in p for p in cobertura.problemas)


def test_un_alias_del_catalogo_no_es_una_sustitucion(tmp_path: Path) -> None:
    ruta = _archivo(
        tmp_path, "c.csv", fab.consolidado_csv(sustituir={"México": "Estado de México"})
    )

    assert revisa_consolidado(ruta, fab.CONTRATO, fab.PADECIMIENTOS).pasa


def test_una_entidad_duplicada_falla(tmp_path: Path) -> None:
    ruta = _archivo(
        tmp_path, "c.csv", fab.consolidado_csv(duplicar={(fab.PAD_NEURO, "Aguascalientes")})
    )

    cobertura = revisa_consolidado(ruta, fab.CONTRATO, fab.PADECIMIENTOS)

    assert any(
        "depresion 2026-W31: entidades duplicadas ['aguascalientes']" in p
        for p in cobertura.problemas
    )


def test_un_corte_dispar_entre_publicados_falla(tmp_path: Path) -> None:
    """Dengue en W30 y neuro en W31: publicar así deja un padecimiento rancio (P0.8)."""
    ruta = _archivo(tmp_path, "c.csv", fab.consolidado_csv(cortes={fab.PAD_CONTEO: (2026, 30)}))

    cobertura = revisa_consolidado(ruta, fab.CONTRATO, fab.PADECIMIENTOS)

    assert not cobertura.pasa
    assert any("corte dispar" in p and "(2026, 30)" in p for p in cobertura.problemas)
    with pytest.raises(StagingError, match="corte dispar"):
        cobertura.exige()


def test_un_padecimiento_autorizado_sin_filas_falla(tmp_path: Path) -> None:
    solo_neuro = "\n".join(
        linea for linea in fab.consolidado_csv().splitlines() if fab.PAD_CONTEO not in linea
    )
    ruta = _archivo(tmp_path, "c.csv", solo_neuro + "\n")

    cobertura = revisa_consolidado(ruta, fab.CONTRATO, fab.PADECIMIENTOS)

    assert any("sin filas para ['dengue']" in p for p in cobertura.problemas)


def test_un_padecimiento_fuera_del_contrato_no_se_autoriza(tmp_path: Path) -> None:
    ruta = _archivo(tmp_path, "c.csv", fab.consolidado_csv())
    with pytest.raises(StagingError, match="fuera del contrato"):
        revisa_consolidado(ruta, fab.CONTRATO, ("Depresión", "Obesidad"))


# ── forecasts, tabla y Dengue: conjuntos exactos ─────────────────────────────


def test_un_forecast_completo_pasa(tmp_path: Path) -> None:
    ruta = tmp_path / "prophet" / "all_forecast_prophet.csv"
    ruta.parent.mkdir()
    ruta.write_text(fab.forecast_csv(), encoding="utf-8")

    cobertura = revisa_forecasts_listados([ruta], fab.CONTRATO)

    assert cobertura.pasa and cobertura.cifras["prophet"] == {"claves": 72, "esperadas": 72}


def test_un_forecast_con_una_serie_de_menos_y_una_ajena_falla(tmp_path: Path) -> None:
    """Conserva el conteo (21) y aun así el conjunto no es el del contrato."""
    ruta = tmp_path / "prophet" / "all_forecast_prophet.csv"
    ruta.parent.mkdir()
    ruta.write_text(
        fab.forecast_csv(
            faltan={(fab.PAD_NEURO, "Nacional", "general")},
            extra=(fab.PAD_NEURO, "Jalisco", "general"),
        ),
        encoding="utf-8",
    )

    cobertura = revisa_forecasts_listados([ruta], fab.CONTRATO)

    assert cobertura.cifras["prophet"]["claves"] == 72
    assert any(
        "faltan 1 clave(s)" in p and "('depresion', 'nacional', 'general')" in p
        for p in cobertura.problemas
    )
    assert any("fuera del contrato" in p and "?jalisco" in p for p in cobertura.problemas)


def test_un_forecast_ausente_falla(tmp_path: Path) -> None:
    cobertura = revisa_forecasts_listados(
        [tmp_path / "deepar" / "all_forecast_deepar.csv"], fab.CONTRATO
    )
    assert any("forecasts/deepar: falta" in p for p in cobertura.problemas)


def test_la_tabla_de_produccion_no_admite_duplicados(tmp_path: Path) -> None:
    """El caso real: la tabla 333 lleva tres claves de Dengue Nacional repetidas."""
    fab.tabla_xlsx(tmp_path / "ok.xlsx")
    assert revisa_tabla_produccion(tmp_path / "ok.xlsx", fab.CONTRATO).pasa

    fab.tabla_xlsx(tmp_path / "dup.xlsx", duplicar=(fab.PAD_CONTEO, "Nacional", "general"))
    cobertura = revisa_tabla_produccion(tmp_path / "dup.xlsx", fab.CONTRATO)

    assert cobertura.cifras["filas"] == 73
    assert any("duplicadas: [('dengue', 'nacional', 'general')]" in p for p in cobertura.problemas)


def test_produccion_dengue_exige_sus_nueve_series(tmp_path: Path) -> None:
    ok = _archivo(tmp_path, "ok.csv", fab.produccion_dengue_csv())
    assert revisa_produccion_dengue(ok, fab.CONTRATO).pasa

    corto = _archivo(
        tmp_path, "corto.csv", fab.produccion_dengue_csv(faltan={("Nacional", "mujeres")})
    )
    assert any(
        "faltan 1 clave(s)" in p for p in revisa_produccion_dengue(corto, fab.CONTRATO).problemas
    )


# ── el otro lado: lo que el candidato publica ────────────────────────────────


def test_un_candidato_completo_pasa(tmp_path: Path) -> None:
    (tmp_path / "epibot").mkdir()
    (tmp_path / "epibot" / "knowledge.json").write_text(fab.knowledge_json(), encoding="utf-8")
    (tmp_path / "epibot" / "zoom_series.json").write_text(fab.zoom_json(), encoding="utf-8")

    coberturas = revisa_candidato(tmp_path, fab.CONTRATO)

    assert [c.fuente for c in coberturas] == ["knowledge.json", "zoom_series.json"]
    assert all(c.pasa for c in coberturas)


def test_un_candidato_degradado_pero_plausible_falla(tmp_path: Path) -> None:
    """Un modelo de menos en knowledge y una serie de menos en el zoom: existen y parecen
    completos; el contrato los desmiente."""
    (tmp_path / "epibot").mkdir()
    (tmp_path / "epibot" / "knowledge.json").write_text(
        fab.knowledge_json(faltan={("Nacional", "general")}, rosters_ok=False), encoding="utf-8"
    )
    (tmp_path / "epibot" / "zoom_series.json").write_text(
        fab.zoom_json(faltan={"dengue|nacional|hombres"}), encoding="utf-8"
    )

    coberturas = revisa_candidato(tmp_path, fab.CONTRATO)

    problemas = [p for c in coberturas for p in c.problemas]
    assert any("knowledge.prod_models: faltan 1 clave(s)" in p for p in problemas)
    assert any("knowledge.rosters.total_series = 999" in p for p in problemas)
    assert any(
        "zoom_series: faltan 1 clave(s)" in p and "('dengue', 'nacional', 'hombres')" in p
        for p in problemas
    )


def test_el_zoom_acepta_el_alias_de_dengue_pero_no_una_clave_rota(tmp_path: Path) -> None:
    (tmp_path / "epibot").mkdir()
    z = json.loads(fab.zoom_json())
    z["dengue|nacional"] = {"y": []}  # clave sin sexo
    (tmp_path / "epibot" / "zoom_series.json").write_text(json.dumps(z), encoding="utf-8")

    (cobertura,) = revisa_candidato(tmp_path, fab.CONTRATO)

    assert any("fuera del contrato" in p and "?dengue|nacional" in p for p in cobertura.problemas)


def test_sin_archivos_del_epibot_no_hay_nada_que_revisar(tmp_path: Path) -> None:
    assert revisa_candidato(tmp_path, fab.CONTRATO) == []


def test_un_forecast_de_cohorte_de_conteo_declara_su_propio_conjunto(tmp_path: Path) -> None:
    """NBGLM sólo modela Dengue: 99 series reales (9 aquí), no las 432."""
    ruta = tmp_path / "nbglm" / "all_forecast_nbglm.csv"
    ruta.parent.mkdir()
    lineas = [
        linea
        for linea in fab.forecast_csv().splitlines()
        if fab.PAD_CONTEO in linea or linea.startswith("ds")
    ]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    solo_conteo = frozenset().union(*(fab.CONTRATO.productos(p) for p in fab.CONTRATO.conteo))

    assert revisa_forecasts_listados(
        [ruta], fab.CONTRATO, esperadas=solo_conteo, fuente="forecasts_conteo"
    ).pasa
    assert not revisa_forecasts_listados([ruta], fab.CONTRATO).pasa, (
        "como legacy le faltarían las neuro"
    )


# ── profundidad absoluta, continuidad MMWR y el ancla aditiva ────────────────


def test_un_consolidado_mas_corto_que_la_profundidad_minima_falla(tmp_path: Path) -> None:
    """Dos semanas donde el contrato exige tres: una ventana relativa se conformaría."""
    from dataclasses import replace

    contrato = replace(fab.CONTRATO, profundidad_minima=3)
    ruta = _archivo(tmp_path, "c.csv", fab.consolidado_csv())

    cobertura = revisa_consolidado(ruta, contrato, fab.PADECIMIENTOS)

    assert not cobertura.pasa
    assert any(
        "2 semana(s), y el contrato exige al menos 3 contiguas" in p for p in cobertura.problemas
    )
    assert cobertura.cifras["semanas"] == {slug(p): 2 for p in fab.PADECIMIENTOS}


def test_un_hueco_en_las_ultimas_semanas_falla_y_uno_historico_se_informa(tmp_path: Path) -> None:
    from dataclasses import replace

    # Salto W30 -> W32 (falta la 31) dentro de la profundidad exigida.
    ruta = _archivo(tmp_path, "c.csv", fab.consolidado_csv(semanas=((2026, 30), (2026, 32))))
    cobertura = revisa_consolidado(ruta, fab.CONTRATO, fab.PADECIMIENTOS)
    assert any(
        "hueco(s) en las últimas 2 semanas: [((2026, 30), (2026, 32))]" in p
        for p in cobertura.problemas
    )

    # El mismo hueco, pero anterior a la profundidad exigida: se informa, no bloquea.
    ruta2 = _archivo(
        tmp_path, "c2.csv", fab.consolidado_csv(semanas=((2026, 28), (2026, 30), (2026, 31)))
    )
    cobertura2 = revisa_consolidado(
        ruta2, replace(fab.CONTRATO, profundidad_minima=2), fab.PADECIMIENTOS
    )
    assert cobertura2.pasa
    assert cobertura2.cifras["huecos_historicos"] == {slug(p): 1 for p in fab.PADECIMIENTOS}


def test_el_cruce_de_ano_mmwr_no_es_un_hueco(tmp_path: Path) -> None:
    """2025 tiene 53 semanas MMWR: 2025-W53 -> 2026-W1 es contiguo; 2025-W52 -> 2026-W1 no."""
    ruta = _archivo(tmp_path, "c.csv", fab.consolidado_csv(semanas=((2025, 53), (2026, 1))))
    assert revisa_consolidado(ruta, fab.CONTRATO, fab.PADECIMIENTOS).pasa
    ruta2 = _archivo(tmp_path, "c2.csv", fab.consolidado_csv(semanas=((2025, 52), (2026, 1))))
    assert not revisa_consolidado(ruta2, fab.CONTRATO, fab.PADECIMIENTOS).pasa


def test_el_candidato_contiene_la_base_intacta(tmp_path: Path) -> None:
    base = _archivo(tmp_path, "base.csv", fab.consolidado_csv())
    nuevo = _archivo(
        tmp_path, "nuevo.csv", fab.consolidado_csv(semanas=(*fab.SEMANAS, (2026, 32)))
    )
    cobertura = revisa_aditivo(base, nuevo, fab.CONTRATO, fab.PADECIMIENTOS)
    assert cobertura.pasa
    assert cobertura.cifras == {"filas_base": 16, "filas_nuevas": 8}

    # Una semana entera de la base que el candidato ya no trae: se perdió, no se añadió.
    base3 = _archivo(
        tmp_path, "base3.csv", fab.consolidado_csv(semanas=((2026, 29), (2026, 30), (2026, 31)))
    )
    cobertura = revisa_aditivo(base3, base, fab.CONTRATO, fab.PADECIMIENTOS)
    assert any("perdió 8 fila(s) de la base" in p for p in cobertura.problemas)

    cambiado = _archivo(
        tmp_path, "cambiado.csv", fab.consolidado_csv().replace("3,10,12", "3,10,13")
    )
    cobertura = revisa_aditivo(base, cambiado, fab.CONTRATO, fab.PADECIMIENTOS)
    assert any("cambió 16 fila(s) ya publicadas" in p for p in cobertura.problemas)

    # Una entidad con OTRO nombre del catálogo sigue siendo la misma fila (alias), no una pérdida.
    alias = _archivo(
        tmp_path, "alias.csv", fab.consolidado_csv(sustituir={"México": "Estado de México"})
    )
    assert revisa_aditivo(base, alias, fab.CONTRATO, fab.PADECIMIENTOS).pasa

    # Columnas perdidas: el candidato no es un superconjunto.
    sin_columna = _archivo(
        tmp_path,
        "sin.csv",
        "\n".join(",".join(linea.split(",")[:6]) for linea in fab.consolidado_csv().splitlines())
        + "\n",
    )
    assert any(
        "perdió columnas" in p
        for p in revisa_aditivo(base, sin_columna, fab.CONTRATO, fab.PADECIMIENTOS).problemas
    )


def test_un_forecast_con_una_serie_repetida_falla(tmp_path: Path) -> None:
    """Antes se deduplicaba por clave antes de comparar y la repetición era invisible."""
    repetido = fab.forecast_csv() + fab.forecast_csv().split("\n", 1)[1]
    ruta = tmp_path / "prophet" / "all_forecast_prophet.csv"
    ruta.parent.mkdir()
    ruta.write_text(repetido, encoding="utf-8")

    cobertura = revisa_forecasts_listados([ruta], fab.CONTRATO)

    assert not cobertura.pasa
    assert any("serie(s) con fechas repetidas" in p for p in cobertura.problemas)


def test_un_catalogo_con_alias_ambiguo_no_gobierna() -> None:
    ambiguo = fab.CATALOGO_CSV + "14,Jalisco,Jalisco,occidente,Occidente,Edomex\n"
    with pytest.raises(StagingError, match="ambiguo: el alias 'Edomex'"):
        ContratoCobertura.desde_catalogo(ambiguo)
    colision = fab.CATALOGO_CSV.replace("Estado de México|Edomex", "Aguascalientes")
    with pytest.raises(StagingError, match="alias que son también entidades"):
        ContratoCobertura.desde_catalogo(colision)


def test_los_padecimientos_del_contrato_salen_del_registry_del_head(tmp_path: Path) -> None:
    """El HEAD lleva un registry donde Dengue no está publicado: el contrato de ESE commit no
    lo exige, aunque el registry del intérprete (el worktree real) sí."""
    politica = fab.politica_cruda(("dashboard/index.html",))
    yaml_sin_dengue = fab.REGISTRY_YAML.replace(
        "lifecycle: published",
        "lifecycle: trained",
        fab.REGISTRY_YAML.count("lifecycle: published"),
    )
    # Sólo se despublica Dengue: se vuelve a publicar la cohorte neuro.
    import yaml as _yaml

    crudo = _yaml.safe_load(fab.REGISTRY_YAML)
    for pad in crudo["padecimientos"]:
        if pad.get("batch", "General") != "General" and pad.get("lifecycle") == "published":
            pad["lifecycle"] = "trained"
    repo, head = fab.repo_backend(
        tmp_path / "repo",
        politica=politica,
        extra_rastreados={
            "config/padecimientos.yaml": _yaml.safe_dump(
                crudo, allow_unicode=True, sort_keys=False
            )
        },
    )
    del yaml_sin_dengue

    contrato = ContratoCobertura.del_head(repo, head)

    assert contrato.neuro == fab.CONTRATO.neuro
    assert contrato.conteo == ()
    assert contrato.profundidad_minima == fab.PROFUNDIDAD_MINIMA

    # Y el worktree tiene que llevar exactamente el registry del HEAD.
    (repo / "config" / "padecimientos.yaml").write_text(fab.REGISTRY_YAML, encoding="utf-8")
    with pytest.raises(
        StagingError, match="registry de padecimientos config/padecimientos.yaml difiere"
    ):
        ContratoCobertura.del_head(repo, head)
