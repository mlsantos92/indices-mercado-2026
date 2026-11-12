"""Métricas por janela de anos: acumulado, retorno ao ano e volatilidade.

A volatilidade de uma janela é o desvio-padrão dos retornos anuais dentro dela
(amostral). Com só 15 retornos anuais, ela é uma estimativa grosseira: serve para
comparar os ativos entre si na mesma janela, não como medida precisa.

A volatilidade "no ano" só existe para 2026, porque é o único ano com retornos
mensais na base; para os anos anteriores a fonte traz só o retorno anual.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _arred(x) -> float | None:
    if x is None or pd.isna(x):
        return None
    return round(float(x), 2)


def por_janela(anuais: pd.DataFrame) -> dict:
    """Todas as janelas contíguas de anos: chave "inicio-fim" -> ativo -> métricas."""
    anos = list(anuais.index)
    saida = {}
    for i, inicio in enumerate(anos):
        for fim in anos[i:]:
            sub = anuais.loc[inicio:fim]
            por_ativo = {}
            for col in anuais.columns:
                s = sub[col].dropna()
                n = len(s)
                if n == 0:
                    por_ativo[col] = None
                    continue
                acum = ((1 + s / 100).prod() - 1) * 100
                ao_ano = ((1 + acum / 100) ** (1 / n) - 1) * 100
                vol = s.std(ddof=1) if n >= 2 else np.nan
                por_ativo[col] = {"acum": _arred(acum), "ao_ano": _arred(ao_ano),
                                  "vol": _arred(vol), "anos": n}
            saida[f"{inicio}-{fim}"] = por_ativo
    return saida


def vol_mensal_no_ano(largo_ano: pd.DataFrame) -> dict:
    """Volatilidade anualizada dos retornos mensais do ano corrente (desvio × √12)."""
    vol = largo_ano.std(ddof=1) * np.sqrt(12)
    return {col: _arred(v) for col, v in vol.items()}


def volatilidade_movel(anuais: pd.DataFrame, n: int | None) -> dict:
    """Volatilidade dos retornos anuais em cada ano, usando os últimos ``n`` anos
    até ele (``n=None``: desde o início da série). Chave: ano -> ativo -> %."""
    anos = list(anuais.index)
    saida = {}
    for i, ano in enumerate(anos):
        inicio = anos[0] if n is None else anos[max(0, i - n + 1)]
        sub = anuais.loc[inicio:ano]
        por_ativo = {}
        for col in anuais.columns:
            s = sub[col].dropna()
            por_ativo[col] = _arred(s.std(ddof=1)) if len(s) >= 2 else None
        saida[int(ano)] = por_ativo
    return saida
