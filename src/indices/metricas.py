"""Métricas de retorno e risco a partir de retornos mensais em %.

Regra de ouro: retornos se COMPÕEM, não se somam.
    acumulado = (1 + r1) x (1 + r2) x ... - 1
Somar 1% + 1% dá 2%; o correto é 2,01%. Em 12 meses a diferença pesa.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def acumulado(r: pd.Series) -> float:
    """Retorno acumulado (%) de uma série de retornos mensais (%)."""
    r = r.dropna()
    return float(((1 + r / 100).prod() - 1) * 100) if len(r) else np.nan


def indice_base100(largo: pd.DataFrame) -> pd.DataFrame:
    """Evolução de R$ 100 aplicados no início do período."""
    return 100 * (1 + largo.fillna(0) / 100).cumprod()


def retorno_real(nominal_pct: float, inflacao_pct: float) -> float:
    """Ganho acima da inflação: (1+nominal)/(1+inflação) - 1, em %."""
    return ((1 + nominal_pct / 100) / (1 + inflacao_pct / 100) - 1) * 100


def max_drawdown(r: pd.Series) -> float:
    """Maior queda (%) de um pico até um vale, na série de valores acumulados."""
    v = (1 + r.dropna() / 100).cumprod()
    v = pd.concat([pd.Series([1.0]), v.reset_index(drop=True)])
    return float(((v / v.cummax()) - 1).min() * 100)


def resumo(largo: pd.DataFrame, ano: int, inflacao: str = "IPCA", livre_risco: str = "CDI",
           sem_sharpe: tuple[str, ...] = ("S&P 500 (US$)",)) -> pd.DataFrame:
    """Tabela-resumo por índice: no ano, 12 meses, real, volatilidade, Sharpe, drawdown.

    Sharpe não é calculado para o CDI (é a referência), para a inflação e para
    índices em outra moeda (``sem_sharpe``): comparar S&P em dólar com CDI em
    reais misturaria moedas.
    """
    ultimos12 = largo.tail(12)
    no_ano = largo[largo.index.year == ano]
    ipca_ano, ipca_12 = acumulado(no_ano[inflacao]), acumulado(ultimos12[inflacao])

    linhas = []
    for col in largo.columns:
        r12 = ultimos12[col]
        excesso = (r12 - ultimos12[livre_risco]).dropna()
        vol = r12.std(ddof=1) * np.sqrt(12)
        sharpe = (excesso.mean() / excesso.std(ddof=1) * np.sqrt(12)
                  if col not in (livre_risco, inflacao, *sem_sharpe) and excesso.std(ddof=1) > 0 else np.nan)
        linhas.append({
            "indice": col,
            f"no_ano_{ano}": acumulado(no_ano[col]),
            "real_no_ano": retorno_real(acumulado(no_ano[col]), ipca_ano) if col != inflacao else np.nan,
            "ult_12m": acumulado(r12),
            "real_12m": retorno_real(acumulado(r12), ipca_12) if col != inflacao else np.nan,
            "vol_anual": vol,
            "sharpe_12m": sharpe,
            "max_drawdown_12m": max_drawdown(r12),
            "meses_positivos": int((r12 > 0).sum()),
        })
    return pd.DataFrame(linhas).sort_values(f"no_ano_{ano}", ascending=False).reset_index(drop=True)


def acumulado_por_ano(largo: pd.DataFrame) -> pd.DataFrame:
    return largo.groupby(largo.index.year).apply(lambda g: g.apply(acumulado)).T


def benchmark_ipca_mais(largo: pd.DataFrame, spread_aa: float = 4.0, inflacao: str = "IPCA") -> pd.Series:
    """Meta "IPCA + X% ao ano", convertida para mensal e somada mês a mês."""
    spread_m = (1 + spread_aa / 100) ** (1 / 12) - 1
    return ((1 + largo[inflacao] / 100) * (1 + spread_m) - 1) * 100
