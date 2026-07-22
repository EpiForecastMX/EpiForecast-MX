"""E3: regla canónica de selección (sMAPE -> MASE -> RMSE -> orden estable)."""

from __future__ import annotations

from epiforecast.selection import Candidate, is_low_incidence, select_engine


def test_ganador_claro_por_smape():
    cands = [
        Candidate("prophet", smape=10.0),
        Candidate("deepar", smape=30.0),
        Candidate("ensemble", smape=50.0),
    ]
    assert select_engine(cands) == "prophet"


def test_dentro_de_banda_desempata_por_mase():
    # deepar y prophet dentro del 5% de sMAPE -> gana el de menor MASE.
    cands = [
        Candidate("prophet", smape=10.0, mase=0.9),
        Candidate("deepar", smape=10.4, mase=0.7),  # 10.4 <= 10*1.05=10.5 -> en banda
        Candidate("stacking", smape=20.0, mase=0.1),  # fuera de banda
    ]
    assert select_engine(cands) == "deepar"


def test_empate_mase_desempata_por_rmse():
    cands = [
        Candidate("prophet", smape=10.0, mase=0.8, rmse=5.0),
        Candidate("deepar", smape=10.2, mase=0.8, rmse=3.0),  # mismo MASE, menor RMSE
    ]
    assert select_engine(cands) == "deepar"


def test_empate_total_orden_estable_por_nombre():
    cands = [
        Candidate("prophet", smape=10.0, mase=0.8, rmse=5.0),
        Candidate("deepar", smape=10.0, mase=0.8, rmse=5.0),
    ]
    assert select_engine(cands) == "deepar"  # alfabético: deepar < prophet


def test_sin_smape_devuelve_none():
    assert select_engine([Candidate("prophet"), Candidate("deepar")]) is None


def test_ignora_candidatos_sin_smape():
    cands = [Candidate("prophet", smape=None), Candidate("deepar", smape=12.0)]
    assert select_engine(cands) == "deepar"


def test_baja_incidencia():
    assert is_low_incidence(4) is True
    assert is_low_incidence(5) is False
    assert is_low_incidence(0) is True
