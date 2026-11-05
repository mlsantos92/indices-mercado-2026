import pandas as pd
import pytest

from indices import coleta, metricas


def test_retornos_compoem_nao_somam():
    assert metricas.acumulado(pd.Series([1.0, 1.0])) == pytest.approx(2.01)


def test_retorno_real():
    # 10% nominal com 10% de inflação = ganho real zero
    assert metricas.retorno_real(10, 10) == pytest.approx(0)


def test_drawdown():
    # sobe 10%, cai 20%: a queda do pico é 20%
    assert metricas.max_drawdown(pd.Series([10.0, -20.0])) == pytest.approx(-20)


def test_cdi_mensal_encadeia_diarias():
    dias = pd.date_range("2026-01-02", periods=20, freq="B")
    s = pd.Series(0.05, index=dias)  # 0,05% ao dia, 20 dias úteis
    assert coleta.cdi_mensal(s).iloc[0] == pytest.approx((1.0005**20 - 1) * 100)


def test_base_completa():
    b = coleta.ler_base()
    assert set(b["indice"]) == set(coleta.CLASSES)
    assert not b.duplicated(["mes", "indice"]).any()
    largo = coleta.em_colunas(b)
    assert largo.index.is_monotonic_increasing


def test_meta_ipca_mais_4():
    largo = pd.DataFrame({"IPCA": [0.0] * 12})
    assert metricas.acumulado(metricas.benchmark_ipca_mais(largo, 4.0)) == pytest.approx(4.0)
