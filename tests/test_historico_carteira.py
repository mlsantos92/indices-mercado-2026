import pandas as pd
import pytest

from indices import carteira, coleta, historico


def test_sp_em_reais_combina_bolsa_e_cambio():
    # bolsa +10% em dólar e dólar +10%: +21% para quem investe em reais
    assert coleta.em_reais(pd.Series([10.0]), pd.Series([10.0])).iloc[0] == pytest.approx(21)


def test_sp_aparece_em_dolar_e_em_reais():
    largo = coleta.em_colunas(coleta.ler_base())
    assert {coleta.SP_DOLAR, coleta.SP_REAIS} <= set(largo.columns)
    assert "S&P 500" not in largo.columns


def test_anual_completo_e_bitcoin_so_desde_2020():
    a = historico.ler_anual()
    assert list(a.index) == list(range(2011, 2026))
    assert a.drop(columns="BTC").notna().all().all()
    assert a["BTC"].first_valid_index() == 2020
    assert a["BTC"].notna().sum() == 6


def test_ano_parcial_usa_os_meses_fechados():
    anuais, meses = historico.com_ano_parcial(historico.ler_anual(), coleta.em_colunas(coleta.ler_base()))
    assert meses.loc[2026] == 10 and meses.loc[2025] == 12
    # 2026 do CDI = composição dos meses de jan a out
    assert anuais.loc[2026, "CDI"] == pytest.approx(11.68, abs=0.01)


def _base(pre=None, pesos=None):
    anuais = pd.DataFrame({"CDI": [10.0, 10.0, 10.0], "IPCA": [5.0, 5.0, 5.0],
                           "IRF-M": [20.0, 0.0, 10.0], "IMA-B": [15.0, 5.0, 10.0]}, index=[2023, 2024, 2025])
    meses = pd.Series(12, index=anuais.index)
    c = carteira.Carteira(pesos or {"CDI": 70, "IRF-M": 30}, pre_aa=pre)
    return c, c.anual(anuais, meses, 2023, 2025), anuais


def test_rebalanceamento_anual_e_media_ponderada():
    _, df, _ = _base()
    assert df.loc[2023, "carteira"] == pytest.approx(0.7 * 10 + 0.3 * 20)


def test_taxa_prefixada_rende_a_taxa_mas_oscila_como_o_irfm():
    c, df, _ = _base(pre=12)
    assert df["carteira"].std() == pytest.approx(0)             # retorno: taxa contratada todo ano
    risco = c.risco(df)
    assert risco["vol_pct"] == pytest.approx(0.3 * df["irfm"].std())  # risco: marcação a mercado
    assert c.com_marcacao(df).mean() == pytest.approx(df["carteira"].mean())


def test_sharpe_comparado_com_indices():
    c, df, anuais = _base(pesos={"CDI": 50, "IMA-B": 50})
    tab = carteira.comparar_sharpe(c, df, anuais)
    assert "CDI" not in tab.index and "IPCA" not in tab.index
    assert tab.attrs["n_indices"] == 2                           # IRF-M e IMA-B
    assert tab.attrs["media_indices"] == pytest.approx(tab.drop(index="Carteira")["sharpe"].mean())


def test_aporte_anual_entra_no_inicio_de_cada_ano():
    df = pd.DataFrame({"carteira": [10.0, 10.0], "ipca": [5.0, 5.0], "meses": [12, 12]}, index=[2024, 2025])
    s = carteira.Carteira.simular_aportes(df, inicial=1000, anual=100)
    assert s["aportado"] == 1200
    assert s["saldo"] == pytest.approx(((1000 + 100) * 1.1 + 100) * 1.1)


def test_bitcoin_faz_a_carteira_comecar_em_2020():
    anuais, meses = historico.com_ano_parcial(historico.ler_anual(), coleta.em_colunas(coleta.ler_base()))
    df = carteira.Carteira({"CDI": 90, "BTC": 10}).anual(anuais, meses, 2011, 2026)
    assert df.index.min() == 2020
