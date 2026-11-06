"""Histórico anual de 2011 a 2026 (2026 parcial).

- **2011–2025**: retornos anuais da tabela "15 anos" da Meu Patrimônio
  (``data/raw/indices_anual.csv``). Bitcoin só de 2020 em diante (Mais Retorno,
  MarketVector Bitcoin Benchmark Rate, convertido para reais): antes disso o
  peso dele num estudo de carteira é irrelevante e as fontes não se conversam.
- **2026**: composição dos retornos mensais já fechados (mesma base da análise
  do ano), com o número de meses guardado para calcular o "ao ano".

Retornos de anos se compõem como os de meses: (1 + r1)(1 + r2)... - 1.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import coleta, metricas

ANUAL = coleta.RAIZ / "data" / "raw" / "indices_anual.csv"


def ler_anual(caminho: Path = ANUAL) -> pd.DataFrame:
    """Anos nas linhas, índices nas colunas (com S&P em US$ e em R$)."""
    return coleta.em_colunas(pd.read_csv(caminho))


def com_ano_parcial(anuais: pd.DataFrame, mensal_largo: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Acrescenta o ano corrente (parcial) composto dos meses e devolve os meses de cada ano."""
    ano = int(mensal_largo.index.max().year)
    meses_ano = mensal_largo[mensal_largo.index.year == ano]
    parcial = meses_ano.apply(metricas.acumulado)
    # S&P em reais do ano parcial: composto dos meses em reais, não do total
    tudo = pd.concat([anuais, parcial.to_frame(ano).T.reindex(columns=anuais.columns)])
    tudo.index = tudo.index.astype(int)
    meses = pd.Series(12, index=tudo.index)
    meses.loc[ano] = len(meses_ano)
    return tudo, meses


def periodo(anuais: pd.DataFrame, meses: pd.Series, inicio: int, fim: int) -> pd.DataFrame:
    """Acumulado e equivalente ao ano de cada índice entre dois anos (inclusive).

    O "ao ano" usa os meses que o índice de fato tem no período: um índice que
    começa depois (Bitcoin) é anualizado só sobre os seus anos.
    """
    janela = anuais.loc[inicio:fim]
    linhas = {}
    for col in janela.columns:
        s = janela[col].dropna()
        if s.empty:
            continue
        fator = float((1 + s / 100).prod())
        n = int(meses.loc[s.index].sum())
        linhas[col] = {"acumulado_pct": (fator - 1) * 100, "ao_ano_pct": (fator ** (12 / n) - 1) * 100,
                       "desde": int(s.index.min()), "meses": n}
    return pd.DataFrame(linhas).T.sort_values("acumulado_pct", ascending=False)


def tabela_periodica(anuais: pd.DataFrame, inicio: int, fim: int) -> pd.DataFrame:
    """Para cada ano, os índices do melhor para o pior (a "tabela periódica")."""
    colunas = {}
    for ano, linha in anuais.loc[inicio:fim].iterrows():
        ordem = linha.dropna().drop(labels=[coleta.SP_DOLAR], errors="ignore").sort_values(ascending=False)
        colunas[ano] = [f"{k} {v:+.1f}%".replace(".", ",") for k, v in ordem.items()]
    n = max(len(v) for v in colunas.values())
    return pd.DataFrame({k: v + [""] * (n - len(v)) for k, v in colunas.items()}, index=np.arange(1, n + 1))
