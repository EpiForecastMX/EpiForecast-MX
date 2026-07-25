"""C7.1/Acción 3 — contrato del validador de refit/lineage sellados.

Aquí vive la matriz completa de mutaciones (Orden 3.5): CUALQUIER alteración de la cadena de
identidad debe producir ``ArtifactValidationError`` y nunca un traceback. La conversión de ese
error en ``Problem`` (el adaptador del doctor) se prueba en ``tests/unit/test_artifact_backend.py``;
aquí no se repite.

Ninguna prueba escribe bajo ``runs/`` real: todo ocurre sobre la copia aislada del fixture.
"""

from __future__ import annotations

import csv
from pathlib import Path
import shutil

import pytest

from epiforecast import registry
from epiforecast.data.epi_dataset_spec import GeoEntity
from epiforecast.data.epi_geo_exposure import GeoCatalog, load_geo_catalog
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.artifact_validation import validate_runner_runs
from tests.unit.runner import artifact_fixtures as fx

pytestmark = pytest.mark.skipif(not fx.hay_runs(), reason="runs sellados locales no disponibles")

_RAIZ = Path(__file__).resolve().parents[3]
_MOTOR = "seasonal_mean_5y"


def _catalogo(cve_ents: list[str] | None = None) -> GeoCatalog:
    """Catálogo INYECTADO: el universo esperado no lo decide el validador.

    Sin argumentos devuelve el catálogo trackeado (lo que usa producción); con una lista de claves
    construye uno sintético para demostrar que el universo sale de aquí y no de una constante.
    """
    if cve_ents is None:
        return load_geo_catalog()
    return GeoCatalog(
        [
            GeoEntity(cve, f"Entidad {cve}", f"Entidad {cve}", "norte", "Norte", ())
            for cve in cve_ents
        ]
    )


@pytest.fixture
def sellado(tmp_path):
    """Refit + forecast + dataset copiados a `tmp_path`; las mutaciones solo tocan la copia."""
    return fx.copiar_runs_sellados(tmp_path)


def _validar(root: Path, **extra):
    d = registry.require(fx.DISEASE)
    src = d.artifact_source
    kwargs = {
        "disease_id": d.id,
        "refit_run_id": str(src.refit_run_id),
        "forecast_run_id": str(src.forecast_run_id),
        "policy_digest": str(src.policy_digest),
        "final_selection_digest": str(src.final_selection_digest),
        "runs_root": root,
        "policy_path": _RAIZ / "config" / "evaluation" / f"{d.selection_policy}.yaml",
        "geo_catalog": _catalogo(),
    }
    return validate_runner_runs(**{**kwargs, **extra})


def _indice(root: Path, engine: str = _MOTOR) -> Path:
    return fx.refit_dir(root) / "models" / engine / "model_index.json"


def _manifiesto(root: Path) -> Path:
    return fx.refit_dir(root) / "run_manifest.json"


# ── Positivos: lo que el validador DERIVA de los artefactos ────────────────────────────────────
def test_las_identidades_se_derivan_de_los_artefactos(sellado):
    v = _validar(sellado)
    assert (v.n_models, len(set(v.series))) == (64, 64)
    assert v.n_train == 653 and v.train_end == (2026, 26)
    assert len(v.engines) == 6 and sum(n for _, n in v.distribution) == 64
    assert dict(v.counts) == {"base": 64, "derived": 47, "products": 111}
    assert v.dataset_id.startswith(f"{fx.DISEASE}_")


def test_el_validador_no_necesita_el_registry_ni_el_cli(sellado):
    """Gate 3.2: las identidades esperadas pueden venir de cualquier lado, no de un global."""
    man = fx.leer(_manifiesto(sellado))
    v = validate_runner_runs(
        disease_id=man["disease_id"],
        refit_run_id=man["run_id"],
        forecast_run_id=fx.leer(fx.forecast_dir(sellado) / "run_manifest.json")["run_id"],
        policy_digest=man["policy_digest"],
        final_selection_digest=man["input_digests"]["final_selection_digest"],
        runs_root=sellado,
        policy_path=_RAIZ / "config" / "evaluation" / "rolling_cv_v1.yaml",
        geo_catalog=_catalogo(),
    )
    assert v.n_models == 64


def test_el_universo_lo_fija_el_catalogo_inyectado(sellado):
    ajeno = [f"{i:02d}" for i in range(51, 83)]  # 32 entidades, pero no las del dataset
    with pytest.raises(ArtifactValidationError, match="catálogo"):
        _validar(sellado, geo_catalog=_catalogo(ajeno))


def test_la_politica_vigente_debe_coincidir_con_el_digest_declarado(sellado, tmp_path):
    otra = tmp_path / "otra_politica.yaml"
    otra.write_text("candidates: []\n", encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match="policy_digest"):
        _validar(sellado, policy_path=otra)


# ── Negativos que rompen el SELLO (no se re-sella la copia) ────────────────────────────────────
def _resumen_alterado(root: Path) -> None:
    fx.editar(fx.refit_dir(root) / "refit_summary.json", {"n_models": 63})


def _indice_alterado(root: Path) -> None:
    fx.editar(_indice(root), {"n_models": 63})


def _envelope_alterado(root: Path) -> None:
    fx.editar(fx.un_envelope(root, _MOTOR), {"n_train": 1})


def _estado_retirado(root: Path) -> None:
    sorted((fx.refit_dir(root) / "models" / _MOTOR).glob("*.state.json"))[0].unlink()


def _estado_alterado(root: Path) -> None:
    estado = sorted((fx.refit_dir(root) / "models" / _MOTOR).glob("*.state.json"))[0]
    estado.write_text('{"alterado": true}', encoding="utf-8")


def _lineage_alterado(root: Path) -> None:
    fx.editar(fx.forecast_dir(root) / "lineage.json", {"base_series": 1})


def _forecast_alterado(root: Path) -> None:
    (fx.forecast_dir(root) / "forecast.csv").write_text("roto\n", encoding="utf-8")


def _seleccion_alterada(root: Path) -> None:
    path = fx.refit_dir(root) / "final_selection.csv"
    filas = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    filas[0]["selected_engine"] = "prophet_count_log1p"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(filas[0]))
        writer.writeheader()
        writer.writerows(filas)


def _refit_digest_ajeno(root: Path) -> None:
    path = fx.forecast_dir(root) / "run_manifest.json"
    man = fx.leer(path)
    man["input_digests"]["refit_digest"] = "0" * 64
    fx.escribir(path, man)


_SIN_RESELLAR = {
    "resumen_alterado": _resumen_alterado,
    "indice_alterado": _indice_alterado,
    "envelope_alterado": _envelope_alterado,
    "estado_retirado": _estado_retirado,
    "estado_alterado": _estado_alterado,
    "lineage_alterado": _lineage_alterado,
    "forecast_alterado": _forecast_alterado,
    "seleccion_alterada": _seleccion_alterada,
    # El manifiesto del forecast no lo sella nadie, así que su `refit_digest` sólo puede
    # contradecir al resumen SIN re-sellar: re-sellar lo recalcularía por definición.
    "refit_digest_ajeno": _refit_digest_ajeno,
}


@pytest.mark.parametrize("caso", sorted(_SIN_RESELLAR))
def test_romper_un_sello_hace_fallar_al_validador(sellado, caso):
    _SIN_RESELLAR[caso](sellado)
    with pytest.raises(ArtifactValidationError):
        _validar(sellado)


# ── Negativos que rompen la IDENTIDAD (la copia se re-sella antes de validar) ──────────────────
def _run_id_ajeno(root: Path) -> None:
    fx.editar(_manifiesto(root), {"run_id": "obesidad_refit_final_otro"})


def _disease_ajeno(root: Path) -> None:
    fx.editar(_manifiesto(root), {"disease_id": "anorexia_f50"})


def _run_fallido(root: Path) -> None:
    fx.editar(_manifiesto(root), {"status": "failed"})


def _comando_cambiado(root: Path) -> None:
    fx.editar(_manifiesto(root), {"command": "benchmark"})


def _politica_ajena(root: Path) -> None:
    fx.editar(_manifiesto(root), {"policy_digest": "0" * 64})


def _dataset_cruzado(root: Path) -> None:
    fx.editar(fx.forecast_dir(root) / "run_manifest.json", {"dataset_id": "obesidad_otro"})


def _input_digest_ajeno(root: Path) -> None:
    man = fx.leer(_manifiesto(root))
    man["input_digests"]["selection_digest"] = "0" * 64
    fx.escribir(_manifiesto(root), man)


def _motor_de_mas_en_el_manifiesto(root: Path) -> None:
    man = fx.leer(_manifiesto(root))
    man["engines"] = [*man["engines"], "motor_inventado"]
    fx.escribir(_manifiesto(root), man)


def _artefacto_no_validado(root: Path) -> None:
    man = fx.leer(_manifiesto(root))
    man["artifacts"][0]["validated"] = False
    fx.escribir(_manifiesto(root), man)


def _schema_desconocido(root: Path) -> None:
    fx.editar(fx.refit_dir(root) / "refit_summary.json", {"schema": "refit_summary.v2"})


def _schema_ausente(root: Path) -> None:
    lineage = fx.leer(fx.forecast_dir(root) / "lineage.json")
    lineage.pop("schema")
    fx.escribir(fx.forecast_dir(root) / "lineage.json", lineage)


def _resumen_sin_refit_final(root: Path) -> None:
    fx.editar(fx.refit_dir(root) / "refit_summary.json", {"final_refit": False})


def _resumen_con_tipo_incorrecto(root: Path) -> None:
    fx.editar(fx.refit_dir(root) / "refit_summary.json", {"n_models": "64"})


def _resumen_con_otro_reparto(root: Path) -> None:
    resumen = fx.leer(fx.refit_dir(root) / "refit_summary.json")
    resumen["distribution"] = {**resumen["distribution"], _MOTOR: 99}
    fx.escribir(fx.refit_dir(root) / "refit_summary.json", resumen)


def _resumen_con_otra_ventana(root: Path) -> None:
    fx.editar(fx.refit_dir(root) / "refit_summary.json", {"train_end": [2026, 25]})


def _resumen_con_otro_n_train(root: Path) -> None:
    fx.editar(fx.refit_dir(root) / "refit_summary.json", {"n_train_values": [652]})


def _resumen_con_procedencia_ajena(root: Path) -> None:
    resumen = fx.leer(fx.refit_dir(root) / "refit_summary.json")
    resumen["provenance"]["selection_digest"] = "0" * 64
    fx.escribir(fx.refit_dir(root) / "refit_summary.json", resumen)


def _modelo_faltante(root: Path) -> None:
    index = fx.leer(_indice(root))
    index["models"] = index["models"][1:]
    index["n_models"] = index["n_assigned"] = len(index["models"])
    fx.escribir(_indice(root), index)


def _modelo_duplicado(root: Path) -> None:
    index = fx.leer(_indice(root))
    index["models"] = [*index["models"], index["models"][0]]
    index["n_models"] = index["n_assigned"] = len(index["models"])
    fx.escribir(_indice(root), index)


def _envelope_de_otro_motor(root: Path) -> None:
    fx.editar(fx.un_envelope(root, _MOTOR), {"engine": "prophet_count_log1p"})


def _envelope_derivado(root: Path) -> None:
    path = fx.un_envelope(root, _MOTOR)
    env = fx.leer(path)
    env["series_key"]["geography_level"] = "region"
    fx.escribir(path, env)


def _envelope_con_sexo_agregado(root: Path) -> None:
    path = fx.un_envelope(root, _MOTOR)
    env = fx.leer(path)
    env["series_key"]["sex"] = "general"
    fx.escribir(path, env)


def _envelope_con_otra_frecuencia(root: Path) -> None:
    path = fx.un_envelope(root, _MOTOR)
    env = fx.leer(path)
    env["series_key"]["frequency"] = "mensual"
    fx.escribir(path, env)


def _envelope_con_otro_n_train(root: Path) -> None:
    fx.editar(fx.un_envelope(root, _MOTOR), {"n_train": 652})


def _envelope_con_otra_ventana(root: Path) -> None:
    fx.editar(fx.un_envelope(root, _MOTOR), {"train_end": [2026, 25]})


def _envelope_sin_refit_final(root: Path) -> None:
    fx.editar(fx.un_envelope(root, _MOTOR), {"final_refit": False})


def _envelope_con_procedencia_ajena(root: Path) -> None:
    path = fx.un_envelope(root, _MOTOR)
    env = fx.leer(path)
    env["provenance"]["dataset_id"] = "obesidad_otro"
    fx.escribir(path, env)


def _transform_digest_falso(root: Path) -> None:
    fx.editar(fx.un_envelope(root, _MOTOR), {"transform_digest": "0" * 64})


def _modelo_asignado_a_otro_motor(root: Path) -> None:
    """La serie que el envelope declara pertenece, según la selección, a OTRO motor."""
    filas = list(
        csv.DictReader(
            (fx.refit_dir(root) / "final_selection.csv").read_text(encoding="utf-8").splitlines()
        )
    )
    ajena = next(f for f in filas if f["selected_engine"] != _MOTOR)
    path = fx.un_envelope(root, _MOTOR)
    env = fx.leer(path)
    env["series_key"]["geography_id"] = ajena["geography_id"]
    env["series_key"]["sex"] = ajena["sex"]
    fx.escribir(path, env)


# ── R5-P0.1 · el veredicto de aceptación se abre, no sólo se enlaza por digest ─────────────────
def _aceptacion_ausente(root: Path) -> None:
    shutil.rmtree(fx.acceptance_dir(root))


def _aceptacion_no_aceptada(root: Path) -> None:
    fx.editar(fx.acceptance_dir(root) / "acceptance.json", {"accepted": False})


def _aceptacion_con_check_fallido(root: Path) -> None:
    path = fx.acceptance_dir(root) / "acceptance.json"
    acta = fx.leer(path)
    acta["checks"][0]["passed"] = False
    fx.escribir(path, acta)


def _aceptacion_sin_checks(root: Path) -> None:
    fx.editar(fx.acceptance_dir(root) / "acceptance.json", {"checks": []})


def _aceptacion_de_otro_stage(root: Path) -> None:
    fx.editar(fx.acceptance_dir(root) / "run_manifest.json", {"stage": "full"})


def _aceptacion_de_otro_dataset(root: Path) -> None:
    fx.editar(fx.acceptance_dir(root) / "run_manifest.json", {"dataset_id": "obesidad_otro"})


def _aceptacion_de_otra_politica(root: Path) -> None:
    fx.editar(fx.acceptance_dir(root) / "run_manifest.json", {"policy_digest": "0" * 64})


def _aceptacion_con_otra_seleccion(root: Path) -> None:
    """La selección que se aceptó deja de ser byte a byte la que refiteó el portafolio."""
    path = fx.acceptance_dir(root) / "final_selection.csv"
    path.write_text(path.read_text(encoding="utf-8") + "33,hombres,seasonal_mean_5y,x\n", "utf-8")


def _aceptacion_con_seleccion_resellada(root: Path) -> None:
    """La aceptación queda internamente coherente, pero aceptó OTRA selección que la refiteada."""
    acc = fx.acceptance_dir(root)
    path = acc / "final_selection.csv"
    path.write_text(path.read_text(encoding="utf-8") + "33,hombres,seasonal_mean_5y,x\n", "utf-8")
    acta_path = acc / "acceptance.json"
    acta = fx.leer(acta_path)
    for record in acta["artifacts"]:
        if record["path"] == "final_selection.csv":
            record["digest"] = fx.sha256(path)
    fx.escribir(acta_path, acta)


def _aceptacion_con_artefacto_no_declarado(root: Path) -> None:
    path = fx.acceptance_dir(root) / "acceptance.json"
    acta = fx.leer(path)
    acta["artifacts"] = acta["artifacts"][1:]
    fx.escribir(path, acta)


def _aceptacion_con_run_id_ajeno(root: Path) -> None:
    path = fx.acceptance_dir(root) / "acceptance.json"
    acta = fx.leer(path)
    acta["provenance"]["run_id"] = "obesidad_benchmark_test_otro"
    fx.escribir(path, acta)


# ── R7 · jobs, procedencia e inventario del veredicto ──────────────────────────────────────────
def _aceptacion_sin_jobs(root: Path) -> None:
    """Reproducción R7-P0.1: el benchmark pierde TODOS sus jobs y el veredicto sigue en pie."""
    fx.editar(fx.acceptance_dir(root) / "run_manifest.json", {"jobs": {}})


def _aceptacion_con_motor_faltante(root: Path) -> None:
    path = fx.acceptance_dir(root) / "run_manifest.json"
    man = fx.leer(path)
    man["jobs"].pop(sorted(man["jobs"])[0])
    fx.escribir(path, man)


def _aceptacion_con_motor_extra(root: Path) -> None:
    path = fx.acceptance_dir(root) / "run_manifest.json"
    man = fx.leer(path)
    man["engines"] = [*man["engines"], "motor_inventado"]
    fx.escribir(path, man)


def _aceptacion_con_job_sin_artefactos(root: Path) -> None:
    path = fx.acceptance_dir(root) / "run_manifest.json"
    man = fx.leer(path)
    man["jobs"][sorted(man["jobs"])[0]]["artifacts"] = []
    fx.escribir(path, man)


def _aceptacion_con_selection_run_id_ajeno(root: Path) -> None:
    path = fx.acceptance_dir(root) / "acceptance.json"
    acta = fx.leer(path)
    acta["provenance"]["selection_run_id"] = "obesidad_select_otro"
    fx.escribir(path, acta)


def _aceptacion_sin_artefactos_declarados(root: Path) -> None:
    fx.editar(fx.acceptance_dir(root) / "acceptance.json", {"artifacts": []})


def _aceptacion_sin_declarar_la_seleccion(root: Path) -> None:
    path = fx.acceptance_dir(root) / "acceptance.json"
    acta = fx.leer(path)
    acta["artifacts"] = [a for a in acta["artifacts"] if a["path"] != "final_selection.csv"]
    fx.escribir(path, acta)


def _forecast_con_artefacto_extra(root: Path) -> None:
    path = fx.forecast_dir(root) / "run_manifest.json"
    man = fx.leer(path)
    extra = dict(man["artifacts"][0])
    extra["path"] = "job_context.json"
    man["artifacts"] = [*man["artifacts"], extra]
    fx.escribir(path, man)


def _forecast_sin_su_reporte(root: Path) -> None:
    path = fx.forecast_dir(root) / "run_manifest.json"
    man = fx.leer(path)
    man["artifacts"] = [a for a in man["artifacts"] if a["path"] != "preliminary_report.md"]
    fx.escribir(path, man)


def _forecast_con_schema_incorrecto(root: Path) -> None:
    path = fx.forecast_dir(root) / "run_manifest.json"
    man = fx.leer(path)
    for record in man["artifacts"]:
        if record["path"] == "forecast.csv":
            record["schema"] = "forecast.v2"
    fx.escribir(path, man)


def _forecast_job_sin_su_base(root: Path) -> None:
    path = fx.forecast_dir(root) / "run_manifest.json"
    man = fx.leer(path)
    man["jobs"][sorted(man["jobs"])[0]]["artifacts"] = []
    fx.escribir(path, man)


# ── R5-P0.2 · el índice no puede contradecir al envelope ni al estado ──────────────────────────
def _indice_con_identidad_falsa(root: Path) -> None:
    """Reproducción literal de la auditoría: serie, estado y digest falsos en una entrada."""
    path = _indice(root)
    index = fx.leer(path)
    entrada = index["models"][0]
    entrada["geography_id"] = "99"
    entrada["state_path"] = "mentira.state.json"
    entrada["state_digest"] = "0" * 64
    fx.escribir(path, index)


def _indice_con_serie_falsa(root: Path) -> None:
    """Sólo la SERIE del índice miente: el envelope y el estado quedan intactos y bien sellados."""
    path = _indice(root)
    index = fx.leer(path)
    index["models"][0]["geography_id"] = "99"
    fx.escribir(path, index)


def _indice_con_ventana_falsa(root: Path) -> None:
    path = _indice(root)
    index = fx.leer(path)
    index["models"][0]["n_train"] = 1
    index["models"][0]["train_start"] = [2020, 1]
    fx.escribir(path, index)


def _archivo_de_modelo_extra(root: Path) -> None:
    (fx.refit_dir(root) / "models" / _MOTOR / "intruso.state.json").write_text("{}", "utf-8")


# ── R5-P0.3 · el manifiesto debe declarar sus salidas obligatorias ─────────────────────────────
def _manifiesto_sin_artefactos(root: Path) -> None:
    fx.editar(_manifiesto(root), {"artifacts": []})


def _job_sin_su_indice(root: Path) -> None:
    man = fx.leer(_manifiesto(root))
    man["jobs"][_MOTOR]["artifacts"] = []
    fx.escribir(_manifiesto(root), man)


def _job_con_exit_code_ajeno(root: Path) -> None:
    man = fx.leer(_manifiesto(root))
    man["jobs"][_MOTOR]["exit_code"] = 1
    fx.escribir(_manifiesto(root), man)


def _job_con_clave_ajena(root: Path) -> None:
    man = fx.leer(_manifiesto(root))
    man["jobs"][_MOTOR]["engine"] = "otro_motor"
    fx.escribir(_manifiesto(root), man)


def _forecast_sin_declarar_su_salida(root: Path) -> None:
    path = fx.forecast_dir(root) / "run_manifest.json"
    man = fx.leer(path)
    man["artifacts"] = [a for a in man["artifacts"] if a["path"] != "forecast.csv"]
    fx.escribir(path, man)


# ── R5-P0.4 · tipos JSON inválidos NO pueden escapar como AttributeError ───────────────────────
def _jobs_no_es_objeto(root: Path) -> None:
    fx.editar(_manifiesto(root), {"jobs": "x"})


def _input_digests_no_es_objeto(root: Path) -> None:
    fx.editar(_manifiesto(root), {"input_digests": []})


def _counts_no_es_objeto(root: Path) -> None:
    fx.editar(_manifiesto(root), {"counts": []})


def _artefactos_no_es_lista(root: Path) -> None:
    fx.editar(_manifiesto(root), {"artifacts": {"path": "x"}})


def _models_no_es_lista(root: Path) -> None:
    fx.editar(_indice(root), {"models": "x"})


# ── R5-P1.1 · la ventana se valida por serie, no por el total de filas ─────────────────────────
def _dataset_con_hueco_compensado(root: Path) -> None:
    """Quita un periodo de una serie y duplica otro: el TOTAL de filas no cambia."""
    path = fx.dataset_dir(root) / "epi_dataset_v2.csv"
    lineas = path.read_text(encoding="utf-8").splitlines(keepends=True)
    cabecera, filas = lineas[0], lineas[1:]
    victima = next(i for i, f in enumerate(filas) if f.startswith("obesidad,01,"))
    filas.pop(victima)
    filas.insert(victima, filas[victima])  # duplica la siguiente fila de la misma serie
    path.write_text(cabecera + "".join(filas), encoding="utf-8")


def _dataset_ausente(root: Path) -> None:
    shutil.rmtree(fx.dataset_dir(root))


# ── R9 · inventario exacto del dataset y rutas únicas ──────────────────────────────────────────
def _quitar_record(path: Path, ruta: str) -> None:
    man = fx.leer(path)
    man["artifacts"] = [a for a in man["artifacts"] if a["path"] != ruta]
    fx.escribir(path, man)


def _dataset_sin_products(root: Path) -> None:
    _quitar_record(fx.dataset_dir(root) / "dataset_manifest.json", "products.csv")


def _dataset_sin_lineage(root: Path) -> None:
    _quitar_record(fx.dataset_dir(root) / "dataset_manifest.json", "lineage.json")


def _dataset_con_artefacto_extra(root: Path) -> None:
    path = fx.dataset_dir(root) / "dataset_manifest.json"
    man = fx.leer(path)
    man["artifacts"] = [*man["artifacts"], {**man["artifacts"][0], "path": "manifest.json"}]
    fx.escribir(path, man)


def _schema_de_dataset(ruta: str):
    """Fábrica de mutaciones: el record de `ruta` declara un schema inventado."""

    def mutar(root: Path) -> None:
        path = fx.dataset_dir(root) / "dataset_manifest.json"
        man = fx.leer(path)
        for record in man["artifacts"]:
            if record["path"] == ruta:
                record["schema"] = "inventado.v99"
        fx.escribir(path, man)

    return mutar


def _dataset_con_ruta_duplicada(root: Path) -> None:
    """Dos records con la misma ruta: el diccionario por `path` los colapsaría en silencio."""
    path = fx.dataset_dir(root) / "dataset_manifest.json"
    man = fx.leer(path)
    man["artifacts"] = [*man["artifacts"], dict(man["artifacts"][0])]
    fx.escribir(path, man)


def _refit_con_ruta_duplicada(root: Path) -> None:
    man = fx.leer(_manifiesto(root))
    man["artifacts"] = [*man["artifacts"], dict(man["artifacts"][0])]
    fx.escribir(_manifiesto(root), man)


def _job_con_ruta_duplicada(root: Path) -> None:
    man = fx.leer(_manifiesto(root))
    job = man["jobs"][_MOTOR]
    job["artifacts"] = [*job["artifacts"], dict(job["artifacts"][0])]
    fx.escribir(_manifiesto(root), man)


# ── Acción 4.5 · contenido del forecast publicable ─────────────────────────────────────────────
def _fc(root: Path, nombre: str) -> Path:
    return fx.forecast_dir(root) / nombre


def _csv(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def _quitar_fila(path: Path, indice: int = 1) -> None:
    lineas = _csv(path)
    del lineas[indice]
    path.write_text("".join(lineas), encoding="utf-8")


def _duplicar_fila(path: Path, indice: int = 1) -> None:
    lineas = _csv(path)
    lineas.insert(indice, lineas[indice])
    path.write_text("".join(lineas), encoding="utf-8")


def _reemplazar_campo(path: Path, columna: str, valor: str, fila: int = 1) -> None:
    lineas = _csv(path)
    idx = lineas[0].rstrip("\n").split(",").index(columna)
    campos = lineas[fila].rstrip("\n").split(",")
    campos[idx] = valor
    lineas[fila] = ",".join(campos) + "\n"
    path.write_text("".join(lineas), encoding="utf-8")


def _base_con_fila_faltante(root: Path) -> None:
    _quitar_fila(_fc(root, "forecast_base.csv"))


def _base_con_fila_duplicada(root: Path) -> None:
    _duplicar_fila(_fc(root, "forecast_base.csv"))


def _base_con_horizonte_ajeno(root: Path) -> None:
    _reemplazar_campo(_fc(root, "forecast_base.csv"), "horizon", "99")


def _base_con_origen_ajeno(root: Path) -> None:
    _reemplazar_campo(_fc(root, "forecast_base.csv"), "origin_epi_week", "25")


def _base_con_ds_incoherente(root: Path) -> None:
    _reemplazar_campo(_fc(root, "forecast_base.csv"), "ds", "2020-01-05")


def _base_con_valor_negativo(root: Path) -> None:
    _reemplazar_campo(_fc(root, "forecast_base.csv"), "y_pred_cases", "-1.0")


def _base_con_nan(root: Path) -> None:
    _reemplazar_campo(_fc(root, "forecast_base.csv"), "y_pred_cases", "nan")


def _base_con_infinito(root: Path) -> None:
    _reemplazar_campo(_fc(root, "forecast_base.csv"), "y_pred_cases", "inf")


def _base_con_un_solo_intervalo(root: Path) -> None:
    _reemplazar_campo(_fc(root, "forecast_base.csv"), "yhat_lower", "0.0")


def _base_con_motor_ajeno(root: Path) -> None:
    _reemplazar_campo(_fc(root, "forecast_base.csv"), "engine", "prophet_count_log1p")


def _base_con_fold_ajeno(root: Path) -> None:
    _reemplazar_campo(_fc(root, "forecast_base.csv"), "fold", "development_2024")


def _base_sin_columna(root: Path) -> None:
    path = _fc(root, "forecast_base.csv")
    lineas = _csv(path)
    lineas[0] = lineas[0].replace("yhat_upper", "otra_columna")
    path.write_text("".join(lineas), encoding="utf-8")


def _base_truncada(root: Path) -> None:
    path = _fc(root, "forecast_base.csv")
    path.write_text(_csv(path)[0], encoding="utf-8")


def _job_que_no_coincide(root: Path) -> None:
    """El job declara otro valor que el consolidado para la misma serie y periodo."""
    _reemplazar_campo(
        _fc(root, "artifacts/seasonal_mean_5y/forecast_base.csv"), "y_pred_cases", "0.0"
    )


def _consolidado_con_producto_faltante(root: Path) -> None:
    _quitar_fila(_fc(root, "forecast.csv"))


def _consolidado_con_producto_extra(root: Path) -> None:
    _duplicar_fila(_fc(root, "forecast.csv"))


def _nacional_alterado(root: Path) -> None:
    """Una fila nacional deja de ser la suma de sus contribuyentes."""
    path = _fc(root, "forecast.csv")
    lineas = _csv(path)
    cab = lineas[0].rstrip("\n").split(",")
    nivel, valor = cab.index("geography_level"), cab.index("y_pred_cases")
    for i, linea in enumerate(lineas[1:], start=1):
        campos = linea.rstrip("\n").split(",")
        if campos[nivel] == "nacional":
            campos[valor] = str(float(campos[valor]) + 1.0)
            lineas[i] = ",".join(campos) + "\n"
            break
    path.write_text("".join(lineas), encoding="utf-8")


def _region_alterada(root: Path) -> None:
    path = _fc(root, "forecast.csv")
    lineas = _csv(path)
    cab = lineas[0].rstrip("\n").split(",")
    nivel, valor = cab.index("geography_level"), cab.index("y_pred_cases")
    for i, linea in enumerate(lineas[1:], start=1):
        campos = linea.rstrip("\n").split(",")
        if campos[nivel] == "region":
            campos[valor] = str(float(campos[valor]) * 2)
            lineas[i] = ",".join(campos) + "\n"
            break
    path.write_text("".join(lineas), encoding="utf-8")


def _editar_inventario(root: Path, mutar) -> None:
    """`model_inventory.csv` lleva comas dentro de `train_end`: hay que parsearlo como CSV real."""
    path = _fc(root, "model_inventory.csv")
    filas = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    mutar(filas)
    with path.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)


def _inventario_con_motor_ajeno(root: Path) -> None:
    def mutar(filas):
        filas[0]["engine"] = "prophet_rate_log1p"

    _editar_inventario(root, mutar)


def _inventario_con_n_train_ajeno(root: Path) -> None:
    def mutar(filas):
        filas[0]["n_train"] = "1"

    _editar_inventario(root, mutar)


def _inventario_con_estado_repetido(root: Path) -> None:
    def mutar(filas):
        filas[1]["state_digest"] = filas[0]["state_digest"]

    _editar_inventario(root, mutar)


def _inventario_sin_una_serie(root: Path) -> None:
    _editar_inventario(root, lambda filas: filas.pop(0))


def _lineage_con_horizonte_ajeno(root: Path) -> None:
    fx.editar(_fc(root, "lineage.json"), {"horizon": 51})


# ── R11 · los siete falsos verdes de la tercera auditoría del forecast ─────────────────────────
def _inventario_con_digest_ajeno(root: Path) -> None:
    """R11-F1: digest único, pero que no es el del estado sellado de esa serie."""

    def mutar(filas):
        filas[0]["state_digest"] = "f" * 64

    _editar_inventario(root, mutar)


def _inventario_con_formato_ajeno(root: Path) -> None:
    def mutar(filas):
        filas[0]["state_format"] = "inventado.v99"

    _editar_inventario(root, mutar)


def _job(root: Path, engine: str = _MOTOR) -> Path:
    return _fc(root, f"artifacts/{engine}/forecast_base.csv")


def _job_con_run_id_ajeno(root: Path) -> None:
    """R11-F2: metadata ajena que el número de la predicción ocultaba."""
    _reemplazar_campo(_job(root), "run_id", "run_ajeno")


def _job_con_disease_ajeno(root: Path) -> None:
    _reemplazar_campo(_job(root), "disease_id", "anorexia_f50")


def _job_con_motor_ajeno(root: Path) -> None:
    _reemplazar_campo(_job(root), "engine", "prophet_rate_log1p")


def _job_con_fold_ajeno(root: Path) -> None:
    _reemplazar_campo(_job(root), "fold", "development_2024")


def _job_con_origen_ajeno(root: Path) -> None:
    _reemplazar_campo(_job(root), "origin_epi_week", "25")


def _job_con_un_solo_intervalo(root: Path) -> None:
    _reemplazar_campo(_job(root), "yhat_lower", "0.0")


def _job_con_fila_faltante(root: Path) -> None:
    _quitar_fila(_job(root))


def _job_con_serie_de_otro_motor(root: Path) -> None:
    """Una fila del job declara una serie que la selección asignó a otro motor."""
    _reemplazar_campo(_job(root), "geography_id", "02")


def _con_bandas(path: Path) -> None:
    """R11-F3: bandas COMPLETAS y válidas (lower <= pred <= upper): el contrato genérico las acepta."""
    lineas = _csv(path)
    cab = lineas[0].rstrip("\n").split(",")
    pred, lo, hi = (cab.index(c) for c in ("y_pred_cases", "yhat_lower", "yhat_upper"))
    for i, linea in enumerate(lineas[1:], start=1):
        campos = linea.rstrip("\n").split(",")
        valor = float(campos[pred])
        campos[lo], campos[hi] = str(valor * 0.9), str(valor * 1.1)
        lineas[i] = ",".join(campos) + "\n"
    path.write_text("".join(lineas), encoding="utf-8")


def _base_con_bandas_validas(root: Path) -> None:
    _con_bandas(_fc(root, "forecast_base.csv"))


def _consolidado_con_bandas_validas(root: Path) -> None:
    _con_bandas(_fc(root, "forecast.csv"))


def _job_con_bandas_validas(root: Path) -> None:
    _con_bandas(_job(root))


def _conteo_negativo(root: Path) -> None:
    path = fx.dataset_dir(root) / "dataset_manifest.json"
    man = fx.leer(path)
    man["counts"]["derived"] = -1
    fx.escribir(path, man)


def _conteos_incoherentes(root: Path) -> None:
    """`products` deja de ser `base + derived`: la materialización no cuadraría."""
    path = fx.dataset_dir(root) / "dataset_manifest.json"
    man = fx.leer(path)
    man["counts"]["products"] = man["counts"]["base"] + man["counts"]["derived"] + 1
    fx.escribir(path, man)


def _conteo_ausente(root: Path) -> None:
    path = fx.dataset_dir(root) / "dataset_manifest.json"
    man = fx.leer(path)
    man["counts"].pop("derived")
    fx.escribir(path, man)


def _semana_no_entera(root: Path) -> None:
    """Una semana deja de ser un entero: `int()` la habría "arreglado" (R7.2)."""
    path = fx.dataset_dir(root) / "epi_dataset_v2.csv"
    lineas = path.read_text(encoding="utf-8").splitlines(keepends=True)
    cabecera = lineas[0].rstrip("\n").split(",")
    columna = cabecera.index("epi_week")
    campos = lineas[1].rstrip("\n").split(",")
    campos[columna] = "no_entero"
    lineas[1] = ",".join(campos) + "\n"
    path.write_text("".join(lineas), encoding="utf-8")


def _dataset_de_otro_padecimiento(root: Path) -> None:
    fx.editar(fx.dataset_dir(root) / "dataset_manifest.json", {"disease_id": "anorexia_f50"})


def _dataset_con_otro_conteo(root: Path) -> None:
    path = fx.dataset_dir(root) / "dataset_manifest.json"
    man = fx.leer(path)
    man["counts"]["derived"] = 46
    fx.escribir(path, man)


def _dataset_recortado(root: Path) -> None:
    path = fx.dataset_dir(root) / "epi_dataset_v2.csv"
    lineas = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(lineas[:-10]), encoding="utf-8")


def _manifiesto_truncado(root: Path) -> None:
    _manifiesto(root).write_text('{"schema": "run_', encoding="utf-8")


def _resumen_truncado(root: Path) -> None:
    (fx.refit_dir(root) / "refit_summary.json").write_text('{"schema"', encoding="utf-8")


def _indice_truncado(root: Path) -> None:
    _indice(root).write_text('{"models": [', encoding="utf-8")


def _envelope_truncado(root: Path) -> None:
    fx.un_envelope(root, _MOTOR).write_text('{"series_key"', encoding="utf-8")


def _lineage_truncado(root: Path) -> None:
    (fx.forecast_dir(root) / "lineage.json").write_text("{", encoding="utf-8")


def _dataset_manifest_truncado(root: Path) -> None:
    (fx.dataset_dir(root) / "dataset_manifest.json").write_text("{{", encoding="utf-8")


_CON_RESELLADO = {
    "run_id_ajeno": _run_id_ajeno,
    "disease_ajeno": _disease_ajeno,
    "run_fallido": _run_fallido,
    "comando_cambiado": _comando_cambiado,
    "politica_ajena": _politica_ajena,
    "dataset_cruzado": _dataset_cruzado,
    "input_digest_ajeno": _input_digest_ajeno,
    "motor_de_mas_en_el_manifiesto": _motor_de_mas_en_el_manifiesto,
    "artefacto_no_validado": _artefacto_no_validado,
    "schema_desconocido": _schema_desconocido,
    "schema_ausente": _schema_ausente,
    "resumen_sin_refit_final": _resumen_sin_refit_final,
    "resumen_con_tipo_incorrecto": _resumen_con_tipo_incorrecto,
    "resumen_con_otro_reparto": _resumen_con_otro_reparto,
    "resumen_con_otra_ventana": _resumen_con_otra_ventana,
    "resumen_con_otro_n_train": _resumen_con_otro_n_train,
    "resumen_con_procedencia_ajena": _resumen_con_procedencia_ajena,
    "modelo_faltante": _modelo_faltante,
    "modelo_duplicado": _modelo_duplicado,
    "modelo_asignado_a_otro_motor": _modelo_asignado_a_otro_motor,
    "envelope_de_otro_motor": _envelope_de_otro_motor,
    "envelope_derivado": _envelope_derivado,
    "envelope_con_sexo_agregado": _envelope_con_sexo_agregado,
    "envelope_con_otra_frecuencia": _envelope_con_otra_frecuencia,
    "envelope_con_otro_n_train": _envelope_con_otro_n_train,
    "envelope_con_otra_ventana": _envelope_con_otra_ventana,
    "envelope_sin_refit_final": _envelope_sin_refit_final,
    "envelope_con_procedencia_ajena": _envelope_con_procedencia_ajena,
    "transform_digest_falso": _transform_digest_falso,
    # R5-P0.1 — el veredicto de aceptación
    "aceptacion_ausente": _aceptacion_ausente,
    "aceptacion_no_aceptada": _aceptacion_no_aceptada,
    "aceptacion_con_check_fallido": _aceptacion_con_check_fallido,
    "aceptacion_sin_checks": _aceptacion_sin_checks,
    "aceptacion_de_otro_stage": _aceptacion_de_otro_stage,
    "aceptacion_de_otro_dataset": _aceptacion_de_otro_dataset,
    "aceptacion_de_otra_politica": _aceptacion_de_otra_politica,
    "aceptacion_con_otra_seleccion": _aceptacion_con_otra_seleccion,
    "aceptacion_con_seleccion_resellada": _aceptacion_con_seleccion_resellada,
    "aceptacion_con_artefacto_no_declarado": _aceptacion_con_artefacto_no_declarado,
    "aceptacion_con_run_id_ajeno": _aceptacion_con_run_id_ajeno,
    # R5-P0.2 — índice ↔ envelope ↔ estado
    "indice_con_identidad_falsa": _indice_con_identidad_falsa,
    "indice_con_serie_falsa": _indice_con_serie_falsa,
    "indice_con_ventana_falsa": _indice_con_ventana_falsa,
    "archivo_de_modelo_extra": _archivo_de_modelo_extra,
    # R5-P0.3 — manifiestos autoritativos
    "manifiesto_sin_artefactos": _manifiesto_sin_artefactos,
    "job_sin_su_indice": _job_sin_su_indice,
    "job_con_exit_code_ajeno": _job_con_exit_code_ajeno,
    "job_con_clave_ajena": _job_con_clave_ajena,
    "forecast_sin_declarar_su_salida": _forecast_sin_declarar_su_salida,
    # R5-P0.4 — fronteras de tipos
    "jobs_no_es_objeto": _jobs_no_es_objeto,
    "input_digests_no_es_objeto": _input_digests_no_es_objeto,
    "counts_no_es_objeto": _counts_no_es_objeto,
    "artefactos_no_es_lista": _artefactos_no_es_lista,
    "models_no_es_lista": _models_no_es_lista,
    # R7-P0.1 / R7-P1.1 — jobs y procedencia del veredicto
    "aceptacion_sin_jobs": _aceptacion_sin_jobs,
    "aceptacion_con_motor_faltante": _aceptacion_con_motor_faltante,
    "aceptacion_con_motor_extra": _aceptacion_con_motor_extra,
    "aceptacion_con_job_sin_artefactos": _aceptacion_con_job_sin_artefactos,
    "aceptacion_con_selection_run_id_ajeno": _aceptacion_con_selection_run_id_ajeno,
    "aceptacion_sin_artefactos_declarados": _aceptacion_sin_artefactos_declarados,
    "aceptacion_sin_declarar_la_seleccion": _aceptacion_sin_declarar_la_seleccion,
    # R7-P1.2 — inventario exacto del forecast
    "forecast_con_artefacto_extra": _forecast_con_artefacto_extra,
    "forecast_sin_su_reporte": _forecast_sin_su_reporte,
    "forecast_con_schema_incorrecto": _forecast_con_schema_incorrecto,
    "forecast_job_sin_su_base": _forecast_job_sin_su_base,
    # R5-P1.1 / R7-P0.2 — ventana por serie y conteos sin coerción
    "dataset_con_hueco_compensado": _dataset_con_hueco_compensado,
    "dataset_ausente": _dataset_ausente,
    # Acción 4.5 — contenido del forecast publicable
    "base_con_fila_faltante": _base_con_fila_faltante,
    "base_con_fila_duplicada": _base_con_fila_duplicada,
    "base_con_horizonte_ajeno": _base_con_horizonte_ajeno,
    "base_con_origen_ajeno": _base_con_origen_ajeno,
    "base_con_ds_incoherente": _base_con_ds_incoherente,
    "base_con_valor_negativo": _base_con_valor_negativo,
    "base_con_nan": _base_con_nan,
    "base_con_infinito": _base_con_infinito,
    "base_con_un_solo_intervalo": _base_con_un_solo_intervalo,
    "base_con_motor_ajeno": _base_con_motor_ajeno,
    "base_con_fold_ajeno": _base_con_fold_ajeno,
    "base_sin_columna": _base_sin_columna,
    "base_truncada": _base_truncada,
    "job_que_no_coincide": _job_que_no_coincide,
    "consolidado_con_producto_faltante": _consolidado_con_producto_faltante,
    "consolidado_con_producto_extra": _consolidado_con_producto_extra,
    "nacional_alterado": _nacional_alterado,
    "region_alterada": _region_alterada,
    "inventario_con_motor_ajeno": _inventario_con_motor_ajeno,
    "inventario_con_n_train_ajeno": _inventario_con_n_train_ajeno,
    "inventario_con_estado_repetido": _inventario_con_estado_repetido,
    "inventario_sin_una_serie": _inventario_sin_una_serie,
    "lineage_con_horizonte_ajeno": _lineage_con_horizonte_ajeno,
    # R11 — los siete falsos verdes: identidad del inventario, contrato por job y point-only
    "inventario_con_digest_ajeno": _inventario_con_digest_ajeno,
    "inventario_con_formato_ajeno": _inventario_con_formato_ajeno,
    "job_con_run_id_ajeno": _job_con_run_id_ajeno,
    "job_con_disease_ajeno": _job_con_disease_ajeno,
    "job_con_motor_ajeno": _job_con_motor_ajeno,
    "job_con_fold_ajeno": _job_con_fold_ajeno,
    "job_con_origen_ajeno": _job_con_origen_ajeno,
    "job_con_un_solo_intervalo": _job_con_un_solo_intervalo,
    "job_con_fila_faltante": _job_con_fila_faltante,
    "job_con_serie_de_otro_motor": _job_con_serie_de_otro_motor,
    "job_con_bandas_validas": _job_con_bandas_validas,
    "base_con_bandas_validas": _base_con_bandas_validas,
    "consolidado_con_bandas_validas": _consolidado_con_bandas_validas,
    # R9.1 / R9.2 — inventario exacto del dataset y rutas de artefacto únicas
    "dataset_sin_products": _dataset_sin_products,
    "dataset_sin_lineage": _dataset_sin_lineage,
    "dataset_con_artefacto_extra": _dataset_con_artefacto_extra,
    "dataset_schema_del_csv": _schema_de_dataset("epi_dataset_v2.csv"),
    "dataset_schema_de_products": _schema_de_dataset("products.csv"),
    "dataset_schema_de_lineage": _schema_de_dataset("lineage.json"),
    "dataset_con_ruta_duplicada": _dataset_con_ruta_duplicada,
    "refit_con_ruta_duplicada": _refit_con_ruta_duplicada,
    "job_con_ruta_duplicada": _job_con_ruta_duplicada,
    "conteo_negativo": _conteo_negativo,
    "conteos_incoherentes": _conteos_incoherentes,
    "conteo_ausente": _conteo_ausente,
    "semana_no_entera": _semana_no_entera,
    "dataset_de_otro_padecimiento": _dataset_de_otro_padecimiento,
    "dataset_con_otro_conteo": _dataset_con_otro_conteo,
    "dataset_recortado": _dataset_recortado,
    "manifiesto_truncado": _manifiesto_truncado,
    "resumen_truncado": _resumen_truncado,
    "indice_truncado": _indice_truncado,
    "envelope_truncado": _envelope_truncado,
    "lineage_truncado": _lineage_truncado,
    "dataset_manifest_truncado": _dataset_manifest_truncado,
}


@pytest.mark.parametrize("caso", sorted(_CON_RESELLADO))
def test_romper_la_identidad_hace_fallar_al_validador(sellado, caso):
    """Con los sellos recalculados, el único motivo posible de fallo es la identidad."""
    _CON_RESELLADO[caso](sellado)
    fx.resellar(sellado)
    with pytest.raises(ArtifactValidationError):
        _validar(sellado)


def test_resellar_por_si_solo_no_invalida_la_copia(sellado):
    """Control: el fixture de re-sellado no es lo que hace fallar a las pruebas anteriores."""
    fx.resellar(sellado)
    assert _validar(sellado).n_models == 64


@pytest.mark.parametrize("valor", ["no_entero", True, 64.0, None, float("nan")])
def test_un_conteo_no_entero_es_error_tipado_y_no_se_coerciona(sellado, valor):
    """R7.2: `int(valor)` "arreglaba" metadata inválida y escapaba como `ValueError` crudo."""
    path = fx.dataset_dir(sellado) / "dataset_manifest.json"
    man = fx.leer(path)
    man["counts"]["base"] = valor
    fx.escribir(path, man)
    fx.resellar(sellado)
    with pytest.raises(ArtifactValidationError, match="counts"):
        _validar(sellado)


def test_el_inventario_repite_la_identidad_sellada_de_cada_modelo(sellado):
    """Control positivo de R11.1: inventario, estados, jobs y consolidado canónicos concuerdan."""
    v = _validar(sellado)
    inventario = list(
        csv.DictReader(
            (fx.forecast_dir(sellado) / "model_inventory.csv")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    )
    sellados = {m.series: m for m in v.models}
    assert len(inventario) == len(sellados) == 64
    for fila in inventario:
        modelo = sellados[(fila["geography_id"], fila["sex"])]
        assert fila["engine"] == modelo.engine
        assert fila["state_digest"] == modelo.state_digest
        assert fila["state_format"] == modelo.state_format


def test_el_dataset_canonico_declara_sus_tres_artefactos(sellado):
    """Control positivo de R9.1: el inventario exacto es el que el dataset ya tiene."""
    man = fx.leer(fx.dataset_dir(sellado) / "dataset_manifest.json")
    assert sorted(a["path"] for a in man["artifacts"]) == [
        "epi_dataset_v2.csv",
        "lineage.json",
        "products.csv",
    ]
    assert _validar(sellado).n_models == 64


def test_el_veredicto_de_aceptacion_queda_verificado(sellado):
    """R5.1: no basta con que el digest cuadre; el veredicto se abre y debe ser positivo."""
    v = _validar(sellado)
    assert v.acceptance_run_id.startswith(f"{fx.DISEASE}_benchmark_test_")
    assert v.acceptance_scopes == ("smape_bases", "smape_all", "smape_nacional_general")
