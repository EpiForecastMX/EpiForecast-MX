"""Pruebas estadísticas del banco y búsqueda anidada de hiperparámetros (sin Optuna)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from epiforecast.banco import ajuste, ajuste_flujo, estadistica

pytestmark = pytest.mark.unit


def test_holm_coincide_con_el_ejemplo_clasico() -> None:
    p = [0.01, 0.04, 0.03, 0.005]
    assert estadistica.holm(p) == pytest.approx([0.03, 0.06, 0.06, 0.02])


def test_holm_es_monotono_y_acotado() -> None:
    aj = estadistica.holm([0.5, 0.9, 0.001])
    assert aj[2] == pytest.approx(0.003)
    assert max(aj) <= 1.0
    assert aj[1] >= aj[0]


def test_wilcoxon_detecta_mejora_y_signo_del_efecto() -> None:
    rng = np.random.default_rng(0)
    b = rng.uniform(20, 60, 60)
    a = b * 0.8
    w = estadistica.wilcoxon_pareado(a, b)
    assert w["n"] == 60
    assert w["p"] < 1e-6
    assert w["r_rb"] == pytest.approx(-1.0)
    assert w["mediana_dif"] < 0


def test_wilcoxon_ignora_faltantes_y_rechaza_muestras_chicas() -> None:
    a = np.array([1.0, 2.0, np.nan, 4.0])
    w = estadistica.wilcoxon_pareado(a, a + 1)
    assert w["n"] == 3
    assert np.isnan(w["p"])


def test_signo_y_bootstrap() -> None:
    b = np.linspace(10, 50, 40)
    a = b * 0.9
    s = estadistica.prueba_signo(a, b)
    assert (s["gana"], s["pierde"]) == (40, 0)
    bs = estadistica.bootstrap_mejora(a, b, repeticiones=500)
    assert bs["mediana_pct"] == pytest.approx(-10.0)
    assert bs["ic_bajo"] == pytest.approx(-10.0) == bs["ic_alto"]


def test_friedman_ordena_y_calcula_diferencia_critica() -> None:
    rng = np.random.default_rng(1)
    base = rng.uniform(20, 40, (50, 1))
    t = pd.DataFrame(np.hstack([base, base * 1.2, base * 1.5]), columns=["a", "b", "c"])
    fr = estadistica.friedman_nemenyi(t)
    assert list(fr["rangos_medios"]) == ["a", "b", "c"]
    assert fr["rangos_medios"]["a"] == pytest.approx(1.0)
    assert fr["p_chi2"] < 1e-10
    # Demšar (2006): q_0.05 para k = 3 es 2.343.
    assert fr["q_alfa"] == pytest.approx(2.343, abs=1e-3)


def test_contra_referencia_aplica_holm_y_veredicto() -> None:
    b = np.linspace(10, 50, 40)
    t = pd.DataFrame({"ref": b, "mejor": b * 0.8, "peor": b * 1.3, "igual": b})
    df = estadistica.contra_referencia(t, "ref").set_index("engine")
    assert df.loc["mejor", "veredicto"] == "mejor"
    assert df.loc["peor", "veredicto"] == "peor"
    assert "igual" not in df.index  # idéntico a la referencia: no se prueba
    assert (df["wilcoxon_p_holm"].dropna() >= df["wilcoxon_p"].dropna()).all()


def _matriz(semanas: int = 52 * 6, series: int = 3) -> tuple[np.ndarray[Any, Any], np.ndarray]:
    t = np.arange(semanas)
    y = np.vstack([10 + 5 * np.sin(2 * np.pi * t / 52) + i for i in range(series)])
    return np.maximum(y, 0), (t % 52) + 1


def test_defaults_reproducen_motores_simples() -> None:
    y, sem = _matriz()
    sem_ho = np.arange(1, 53)
    naive = ajuste.estacional_nivel(y, sem, sem_ho, ajuste.ESPACIOS["estacional_nivel"][2], {})
    assert np.allclose(naive, y[:, -52:])
    media = ajuste.media_movil(y, sem, sem_ho, {"ventana": 52}, {})
    assert np.allclose(media, y[:, -52:].mean(axis=1, keepdims=True))


def test_nivel_x_perfil_sin_encogimiento_es_plano_y_con_uno_es_estacional() -> None:
    y, sem = _matriz()
    sem_ho = np.arange(1, 53)
    p = {"nivel_ventana": 52, "anios_perfil": 5, "estadistico_perfil": "media"}
    plano = ajuste.nivel_x_perfil(y, sem, sem_ho, p | {"encogimiento": 0.0}, {})
    assert np.allclose(plano, y[:, -52:].mean(axis=1, keepdims=True))
    estacional = ajuste.nivel_x_perfil(y, sem, sem_ho, p | {"encogimiento": 1.0}, {})
    assert np.allclose(estacional, y[:, -52:], rtol=1e-6)


def test_topdown_conserva_el_total_nacional() -> None:
    y, sem = _matriz()
    total = np.full(52, 90.0)
    p = {"motor_nacional": "ets", "variante_ets": "x", "ventana_pesos": 104}
    out = ajuste.topdown(y, sem, np.arange(1, 53), p, {"ets_nacional": {"x": total}})
    assert np.allclose(out.sum(axis=0), total)


def test_tsb_con_alfa_y_beta_cero_es_media_de_positivos_por_probabilidad() -> None:
    y = np.array([[0.0, 4.0, 0.0, 6.0]])
    out = ajuste.tsb(y, np.arange(1, 5), np.arange(1, 3), {"alfa": 0.0, "beta": 0.0}, {})
    assert np.allclose(out, 0.5 * 5.0)


def _padecimiento(dev: list[int]) -> ajuste_flujo.Padecimiento:
    y, sem = _matriz(52 * 8)
    anios = np.repeat(np.arange(2017, 2025), 52)
    return ajuste_flujo.Padecimiento("demo", y, anios, sem, dev)


def test_pliegues_internos_y_externos_no_se_mezclan() -> None:
    p = _padecimiento([2021, 2022, 2023, 2024])
    assert p.externos == [2023, 2024]
    assert p.internos(2023) == [2021, 2022]
    assert p.internos(2024) == [2021, 2022, 2023]
    assert p.internos(ajuste_flujo.TRANSFERENCIA) == [2021, 2022, 2023, 2024]
    ytr, _, sem_ho, yho = p.corte(2024)
    assert ytr.shape[1] == 52 * 7 and yho.shape[1] == len(sem_ho) == 52
    assert _padecimiento([2025]).historia_corta
    assert _padecimiento([2023, 2024]).externos == [2024]


def test_corte_rechaza_anios_que_no_son_de_desarrollo() -> None:
    p = _padecimiento([2023, 2024])
    with pytest.raises(ValueError, match="no es año de desarrollo"):
        p.corte(2022)


def test_cargar_trunca_en_el_ultimo_anio_de_desarrollo(monkeypatch: pytest.MonkeyPatch) -> None:
    periodos = [(a, w) for a in range(2020, 2027) for w in range(1, 53)]
    serie = np.arange(len(periodos), dtype=float)
    monkeypatch.setattr(ajuste_flujo.flujo, "anios", lambda d: ([2022, 2023, 2024], {2025}))
    monkeypatch.setattr(
        ajuste_flujo.flujo, "historia", lambda d: (periodos, {("01", "hombres"): serie})
    )
    p = ajuste_flujo.cargar("demo")
    assert p.anios.max() == 2024
    assert p.y.shape[1] == 52 * 5
    assert 2025 not in set(p.anios)


def test_objetivo_solo_lee_pliegues_internos(monkeypatch: pytest.MonkeyPatch) -> None:
    p = _padecimiento([2022, 2023, 2024])
    vistos: list[int] = []
    real = ajuste_flujo.smape_pliegue

    def espia(pd_: Any, motor: str, params: dict[str, Any], anio: int) -> float:
        vistos.append(anio)
        return real(pd_, motor, params, anio)

    monkeypatch.setattr(ajuste_flujo, "smape_pliegue", espia)
    trial = _Fijo({"ventana": 30})
    ajuste_flujo.objetivo([p], "media_movil", 2024)(trial)
    assert set(vistos) == {2022, 2023}
    vistos.clear()
    ajuste_flujo.objetivo([p], "media_movil", 2023)(trial)
    assert set(vistos) == {2022}


def test_objetivo_es_relativo_al_naive() -> None:
    p = _padecimiento([2022, 2023, 2024])
    naive = ajuste.ESPACIOS["estacional_nivel"][2]
    valor = ajuste_flujo.objetivo([p], "estacional_nivel", 2024)(_Fijo(naive))
    assert valor == pytest.approx(0.0)


class _Fijo:
    def __init__(self, crudos: dict[str, Any]) -> None:
        self.crudos = crudos

    def suggest_int(self, name: str, low: int, high: int) -> int:
        return int(self.crudos[name])

    def suggest_float(self, name: str, low: float, high: float, *, log: bool = False) -> float:
        return float(self.crudos[name])

    def suggest_categorical(self, name: str, choices: list[Any]) -> Any:
        return self.crudos[name]


def test_pronostico_no_finito_se_penaliza() -> None:
    p = _padecimiento([2023, 2024])
    p.ets[2024] = {"x": np.full(52, np.nan)}
    params = {"motor_nacional": "ets", "variante_ets": "x", "ventana_pesos": 52}
    assert ajuste_flujo.smape_pliegue(p, "topdown", params, 2024) == ajuste_flujo.PENALIZACION


def test_params_de_reconstruye_condicionales() -> None:
    crudos = {"anios": 2, "estadistico": "mediana", "con_nivel": False}
    p = ajuste_flujo.params_de("estacional_nivel", crudos)
    assert p["nivel_ventana"] == 13 and p["anios"] == 2
    for motor, (_, _, default) in ajuste.ESPACIOS.items():
        assert ajuste_flujo.params_de(motor, default) == default


def _metricas() -> pd.DataFrame:
    filas = []
    for i in range(12):
        for fold in (2021, 2022):
            base = 30.0 + i
            for engine, v in (
                ("naive_lag52", base),
                ("media_52s", base * 0.8),
                ("media_3y", base),  # idéntico al naive: no aplica
                ("nivel_x_perfil_5y", base * 0.9 if fold == 2021 else np.nan),
            ):
                filas.append(
                    {
                        "disease_id": f"d{i}",
                        "fold": fold,
                        "engine": engine,
                        "completo": bool(np.isfinite(v)),
                        "smape_nacional": v,
                        "mae_nacional": v,
                        "smape_bases": v,
                    }
                )
    return pd.DataFrame(filas)


def test_pares_empareja_por_pliegue_y_marca_identicos() -> None:
    from epiforecast.banco import estadistica_banco as eb

    m = eb.completos(_metricas())
    p = eb.pares(m, "nivel_x_perfil_5y", "naive_lag52")
    assert (p["pliegues"] == 1).all()  # sólo 2021 está completo en ambos
    assert p["identico"].sum() == 0
    assert eb.pares(m, "media_3y", "naive_lag52")["identico"].all()


def test_contra_separa_familias_y_excluye_no_aplica() -> None:
    from epiforecast.banco import estadistica_banco as eb

    m = eb.completos(_metricas())
    c = eb.contra(
        m, "naive_lag52", ["media_52s", "media_3y", "nivel_x_perfil_5y"], "smape_nacional"
    )
    c = c.set_index("engine")
    assert c.loc["media_3y", "no_aplica"] == 12
    assert c.loc["media_52s", "familia"] == "confirmatoria"
    assert c.loc["nivel_x_perfil_5y", "familia"] == "exploratoria"
    assert c.loc["media_52s", "veredicto"] == "mejor"
    assert c.loc["media_52s", "mae_rel_geo"] == pytest.approx(0.8)
