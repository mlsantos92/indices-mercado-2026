import numpy as np
import pandas as pd
import pytest

from indices import janelas


def _anuais():
    return pd.DataFrame({"A": [10.0, -10.0, 20.0], "B": [5.0, np.nan, 5.0]}, index=[2011, 2012, 2013])


def test_acumulado_composto_e_volatilidade_na_janela():
    j = janelas.por_janela(_anuais())
    a = j["2011-2013"]["A"]
    # 1,10 x 0,90 x 1,20 - 1 = 18,8%
    assert a["acum"] == pytest.approx(18.8, abs=0.01)
    assert a["anos"] == 3
    assert a["vol"] == pytest.approx(np.std([10, -10, 20], ddof=1), abs=0.01)


def test_ativo_sem_dado_na_janela_usa_so_os_anos_disponiveis():
    j = janelas.por_janela(_anuais())
    b = j["2012-2013"]["B"]
    assert b["anos"] == 1
    assert b["vol"] is None


def test_volatilidade_mensal_do_ano_anualizada():
    mensal = pd.DataFrame({"A": [1.0, -1.0, 1.0, -1.0]})
    v = janelas.vol_mensal_no_ano(mensal)
    assert v["A"] == pytest.approx(np.std([1, -1, 1, -1], ddof=1) * np.sqrt(12), abs=0.01)
