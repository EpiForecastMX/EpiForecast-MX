"""C7.1 — el backend de artefactos decide qué es evidencia; un directorio existente no lo es."""

from __future__ import annotations

import json

import pytest

from epiforecast import registry
from epiforecast.registry_doctor import diagnose
from tests.unit.runner import artifact_fixtures as fx

_OBESIDAD = "obesidad"
# Se captura ANTES de sustituir `registry.require`: el doctor lee el registry por dentro.
_REAL_OBESIDAD = registry.require(_OBESIDAD)


def _errores(nombre: str) -> list[str]:
    return [p.message for p in diagnose(nombre, check_artifacts=True) if p.severity == "error"]


def _hay_runs() -> bool:
    return fx.hay_runs()


def test_backends_declarados():
    assert {"legacy_models", "runner_runs", "runner_release"} == registry.ARTIFACT_BACKENDS


def test_los_cuatro_publicados_siguen_en_legacy():
    for nombre in ("Depresión", "Parkinson", "Alzheimer", "Dengue"):
        spec = registry.require(nombre)
        assert spec.artifact_backend == registry.BACKEND_LEGACY
        assert spec.training_engines  # el carril legacy sí declara motores


def test_obesidad_declara_su_release_bundle_y_ningun_motor_legacy():
    """C7.2-B: la evidencia de Obesidad es el release inmutable, no `runs/` ni models/<motor>/.

    `runs/` está gitignored y fuera de DVC, así que nadie más podía verificarlo; el bundle tiene
    puntero DVC dedicado. Los IDs de los runs no desaparecen: viajan en el `chain` del release.
    """
    spec = registry.require(_OBESIDAD)
    assert spec.artifact_backend == registry.BACKEND_RUNNER_RELEASE
    # Vaciar los motores legacy es lo que impide que un PKL preliminar se haga pasar por artefacto.
    assert spec.training_engines == () and spec.eligible_engines == ()
    assert spec.artifact_source.release_id == "obesidad_release_2517e7858901"
    assert spec.artifact_source.to_dict() == {
        "backend": "runner_release",
        "release_id": "obesidad_release_2517e7858901",
    }
    # `runner_release` es admisible con `trained`: declararlo NO publica nada.
    assert spec.lifecycle == "trained"


# ── Acción 2: gate positivo y negativo del loader ──────────────────────────────────────────────
_RUNS_OK = {
    "backend": "runner_runs",
    "refit_run_id": "r",
    "forecast_run_id": "f",
    "policy_digest": "d",
    "final_selection_digest": "s",
}
_RELEASE_OK = {"backend": "runner_release", "release_id": "obesidad_release_abc123"}


def _cargar(tmp_path, nombre, *, source=None, lifecycle="trained", omitir=False):
    base = json.loads(json.dumps(_registro_minimo()))
    entrada = base["padecimientos"][0]
    entrada["lifecycle"] = lifecycle
    if omitir:
        entrada.pop("artifact_source", None)
    elif source is not None:
        entrada["artifact_source"] = source
    cfg = tmp_path / f"reg_{nombre}.yaml"
    cfg.write_text(_a_yaml(base), encoding="utf-8")
    return registry.load_registry(cfg)


@pytest.mark.parametrize(
    ("nombre", "source", "lifecycle", "backend"),
    [
        ("omitido", None, "trained", registry.BACKEND_LEGACY),
        ("legacy", {"backend": "legacy_models"}, "published", registry.BACKEND_LEGACY),
        ("runs", _RUNS_OK, "trained", registry.BACKEND_RUNNER_RUNS),
        ("release_trained", _RELEASE_OK, "trained", registry.BACKEND_RUNNER_RELEASE),
        ("release_published", _RELEASE_OK, "published", registry.BACKEND_RUNNER_RELEASE),
    ],
)
def test_loader_acepta_las_combinaciones_validas(tmp_path, nombre, source, lifecycle, backend):
    reg = _cargar(tmp_path, nombre, source=source, lifecycle=lifecycle, omitir=source is None)
    spec = reg.diseases[0]
    assert spec.artifact_backend == backend
    assert isinstance(spec.artifact_source, registry.ArtifactSource)


def test_artifact_source_es_inmutable(tmp_path):
    spec = _cargar(tmp_path, "inmutable", source=_RUNS_OK).diseases[0]
    with pytest.raises((AttributeError, TypeError)):
        spec.artifact_source.backend = "legacy_models"  # type: ignore[misc]
    assert spec.artifact_source.to_dict() == _RUNS_OK


@pytest.mark.parametrize(
    ("nombre", "source", "lifecycle", "patron"),
    [
        ("desconocido", {"backend": "inventado"}, "trained", "backend desconocido"),
        ("sin_backend", {"refit_run_id": "r"}, "trained", "backend desconocido"),
        ("backend_no_str", {"backend": 7}, "trained", "backend desconocido"),
        ("runs_incompleto", {"backend": "runner_runs"}, "trained", "claves faltantes"),
        ("runs_clave_extra", {**_RUNS_OK, "inventada": "x"}, "trained", "desconocidas"),
        ("release_vacio", {"backend": "runner_release", "release_id": ""}, "trained", "vacío"),
        (
            "release_espacios",
            {"backend": "runner_release", "release_id": "   "},
            "trained",
            "vacío",
        ),
        ("valor_no_str", {**_RUNS_OK, "refit_run_id": 3}, "trained", "debe ser string"),
        ("valor_bool", {**_RUNS_OK, "policy_digest": True}, "trained", "debe ser string"),
        ("valor_nulo", {**_RUNS_OK, "policy_digest": None}, "trained", "debe ser string"),
        ("runs_publicado", _RUNS_OK, "published", "no es admisible"),
        ("runs_configurado", _RUNS_OK, "configured", "no es admisible"),
        ("release_configurado", _RELEASE_OK, "configured", "no es admisible"),
    ],
)
def test_loader_rechaza_las_combinaciones_invalidas(tmp_path, nombre, source, lifecycle, patron):
    with pytest.raises(registry.RegistryError, match=patron):
        _cargar(tmp_path, nombre, source=source, lifecycle=lifecycle)


def test_matriz_lifecycle_backend_declarada():
    # `runner_runs` NUNCA publica; publicar exige legacy o un release restaurable.
    assert registry._BACKEND_LIFECYCLES[registry.BACKEND_RUNNER_RUNS] == {"trained"}
    assert "published" in registry._BACKEND_LIFECYCLES[registry.BACKEND_RUNNER_RELEASE]
    assert "published" in registry._BACKEND_LIFECYCLES[registry.BACKEND_LEGACY]


def test_obesidad_ya_no_declara_grid_legacy_de_prophet():
    assert registry.require(_OBESIDAD).prophet_grid_key is None


@pytest.mark.skipif(not _hay_runs(), reason="runs locales no disponibles")
def test_obesidad_valida_por_sellos_no_por_carpetas():
    assert _errores("Obesidad") == []
    # Los 790 PKL preliminares del carril viejo siguen en disco y ya no autorizan nada.
    from epiforecast.registry_doctor import _models_dir

    assert (_models_dir() / "prophet" / "Obesidad").exists()


@pytest.fixture
def sellado(tmp_path):
    """Copia AISLADA del refit, el forecast y el dataset sellados (ver `artifact_fixtures`)."""
    if not _hay_runs():
        pytest.skip("runs locales no disponibles")
    return fx.copiar_runs_sellados(tmp_path)


def _errores_en(root, monkeypatch=None) -> list[str]:
    """Errores del doctor sobre la copia sellada, forzando el carril ``runner_runs``.

    Desde C7.2-B el registry declara ``runner_release``; estas pruebas son el contrato del ADAPTADOR
    de `runner_runs`, que sigue vivo (es el que valida la cadena antes de promover). Se sustituye el
    padecimiento por uno equivalente con la cadena SELLADA del release, sin escribir IDs a mano.
    """
    # La cadena se resuelve ANTES de sustituir `registry.require`: resolverla dentro provocaría
    # una recursión infinita, porque leer el release pasa por el propio registry.
    sustituto = _obesidad_runner_runs()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(registry, "require", lambda _: sustituto)
        return [
            p.message
            for p in diagnose(_OBESIDAD, check_artifacts=True, runs_root=root)
            if p.severity == "error"
        ]


def _obesidad_runner_runs() -> registry.Disease:
    import dataclasses

    from tests.unit.runner.release_fixtures import chain_source

    return dataclasses.replace(_REAL_OBESIDAD, artifact_source=chain_source())


def test_la_copia_sellada_valida_igual_que_la_canonica(sellado):
    assert _errores_en(sellado) == []


def test_retirar_un_estado_sellado_hace_fallar_al_doctor(sellado):
    refit = fx.refit_dir(sellado)
    sorted((refit / "models" / "seasonal_mean_5y").glob("*.state.json"))[0].unlink()
    errores = _errores_en(sellado)
    assert errores and "seasonal_mean_5y" in errores[0]


def test_alterar_un_estado_sellado_hace_fallar_al_doctor(sellado):
    refit = fx.refit_dir(sellado)
    estado = sorted((refit / "models" / "ridge_harmonic_log1p").glob("*.state.json"))[0]
    estado.write_text('{"coef": [0.0]}', encoding="utf-8")
    errores = _errores_en(sellado)
    assert errores and ("alterado" in errores[0] or "no cargables" in errores[0])


def test_alterar_el_forecast_sellado_hace_fallar_al_doctor(sellado):
    fc = fx.forecast_dir(sellado)
    (fc / "lineage.json").write_text('{"base_series": 1, "derived_products": 1}', encoding="utf-8")
    assert _errores_en(sellado)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("jobs", "x"), ("input_digests", []), ("counts", []), ("artifacts", {"path": "x"})],
)
def test_un_tipo_json_invalido_produce_problem_y_no_traceback(sellado, campo, valor):
    """R5.4: el doctor sólo traduce `ArtifactValidationError`; ningún tipo ajeno puede escapar.

    Se ejercita el ADAPTADOR completo (`diagnose`), no sólo la función pura: es donde un
    `AttributeError` se convertiría en traceback y rc indefinido en lugar de un diagnóstico.
    """
    fx.editar(fx.refit_dir(sellado) / "run_manifest.json", {campo: valor})
    fx.resellar(sellado)
    errores = _errores_en(sellado)
    assert len(errores) == 1 and campo in errores[0]


def test_el_doctor_reporta_un_inventario_de_dataset_incompleto(sellado):
    """R9.1/R9.2 vistos desde el doctor: falso verde convertido en `Problem`, sin traceback."""
    path = fx.dataset_dir(sellado) / "dataset_manifest.json"
    man = fx.leer(path)
    man["artifacts"] = [a for a in man["artifacts"] if a["path"] == "epi_dataset_v2.csv"]
    fx.escribir(path, man)
    fx.resellar(sellado)
    errores = _errores_en(sellado)
    assert len(errores) == 1 and "inventario" in errores[0]


def test_el_doctor_reporta_una_ruta_de_artefacto_duplicada(sellado):
    path = fx.dataset_dir(sellado) / "dataset_manifest.json"
    man = fx.leer(path)
    man["artifacts"] = [*man["artifacts"], dict(man["artifacts"][0])]
    fx.escribir(path, man)
    fx.resellar(sellado)
    errores = _errores_en(sellado)
    assert len(errores) == 1 and "dos veces" in errores[0]


def test_el_doctor_reporta_un_veredicto_de_aceptacion_negativo(sellado):
    """R5.1 vista desde el doctor: un `accepted=false` es un `Problem`, no un verde."""
    fx.editar(fx.acceptance_dir(sellado) / "acceptance.json", {"accepted": False})
    fx.resellar(sellado)
    assert _errores_en(sellado) == ["aceptacion: el veredicto no es accepted=true"]


def test_obesidad_sigue_trained_e_invisible():
    assert registry.require(_OBESIDAD).lifecycle == "trained"
    assert registry.names(published_only=True) == ["Depresión", "Parkinson", "Alzheimer", "Dengue"]
    assert "anorexia_f50" not in [n.lower() for n in registry.names(published_only=True)]


def _registro_minimo() -> dict:
    return {
        "version": 1,
        "motores_conocidos": ["prophet"],
        "perfiles": {
            "p": {
                "cohorte_id": "c",
                "unidad": "conteos",
                "rate_scale": 100000,
                "prophet_log_transform": False,
                "prophet_covid_holidays": False,
                "ensemble_covid_holidays": False,
                "prophet_cv_weights": False,
                "prophet_enso": False,
                "nbglm_enso": False,
                "ensemble_clamp": False,
                "stacking_clamp": False,
                "deepar_short_series": False,
                "fallback_regional": False,
                "excluir_outliers": False,
                "invert_log_predict": False,
                "motor_rate": {"prophet": False},
            }
        },
        "padecimientos": [
            {
                "id": "x",
                "data_name": "X",
                "artifact_key": "X",
                "slug": "x",
                "display_name": "X",
                "cie_codes": ["X00"],
                "aliases": ["x"],
                "profile": "p",
                "batch": "standalone",
                "extraction_group": "g",
                "lifecycle": "trained",
                "channels": [],
                "training_engines": [],
                "eligible_engines": [],
                "selection_policy": "rolling_cv_v1",
                "prophet_grid_key": None,
                "deepar_grid_key": None,
                "aggregate_national": False,
                "gallery_enabled": False,
                "web": {"color": "#000", "label": "X"},
                "artifact_source": {
                    "backend": "runner_runs",
                    "refit_run_id": "r",
                    "forecast_run_id": "f",
                    "policy_digest": "d",
                    "final_selection_digest": "s",
                },
            }
        ],
    }


def _a_yaml(data: dict) -> str:
    import yaml

    return yaml.safe_dump(data, allow_unicode=True)
