"""Coleta dos índices.

Duas fontes:
1. **Base mensal** (``data/raw/indices_mensal_base.csv``): retornos mensais de
   9 índices compilados de relatório de mercado. Fica no repositório como
   ponto de partida reproduzível.
2. **API SGS do Banco Central** (pública, sem cadastro): CDI, IPCA e dólar
   são baixados direto da fonte oficial e substituem a base quando a API
   responde. As divergências são registradas, não escondidas.

Séries SGS usadas (códigos conferidos na documentação):
- 12  : CDI diário, % ao dia  -> encadeado para % no mês
- 433 : IPCA, % no mês
- 1   : dólar comercial (venda), R$ por US$, diário -> variação do último
        valor de cada mês
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ / "data" / "raw" / "indices_mensal_base.csv"
URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

CLASSES = {
    "IBOV": "Ações Brasil", "S&P 500": "Ações EUA", "IMA-B": "RF Inflação",
    "CDI": "RF Pós", "IFIX": "Imobiliário", "IRF-M": "RF Pré",
    "IPCA": "Inflação", "IHFA": "Multimercado", "Dólar": "Dólar",
}


def ler_base(caminho: Path = BASE) -> pd.DataFrame:
    """Lê a base no formato longo: uma linha por mês e índice."""
    df = pd.read_csv(caminho)
    df["mes"] = pd.PeriodIndex(df["mes"], freq="M")
    df["previa"] = df["previa"].astype(bool)
    df["fonte"] = "base"
    return df


# ------------------------------------------------------------------ API SGS
def sgs(codigo: int, inicio: date, fim: date, timeout: int = 30) -> pd.Series:
    """Baixa uma série do SGS entre duas datas (a API exige dataFinal)."""
    params = {"formato": "json", "dataInicial": inicio.strftime("%d/%m/%Y"),
              "dataFinal": fim.strftime("%d/%m/%Y")}
    r = requests.get(URL_SGS.format(codigo=codigo), params=params, timeout=timeout)
    r.raise_for_status()
    d = pd.DataFrame(r.json())
    d["data"] = pd.to_datetime(d["data"], dayfirst=True)
    return d.set_index("data")["valor"].astype(float)


def cdi_mensal(diario: pd.Series) -> pd.Series:
    """Encadeia as taxas diárias: (1+d1)(1+d2)... - 1, em %."""
    fator = (1 + diario / 100).groupby(diario.index.to_period("M")).prod()
    return (fator - 1) * 100


def variacao_mensal_fim_de_mes(diario: pd.Series) -> pd.Series:
    """Variação % entre o último valor de cada mês e o do mês anterior."""
    ultimo = diario.groupby(diario.index.to_period("M")).last()
    return ultimo.pct_change() * 100


def baixar_bcb(inicio: date, fim: date) -> pd.DataFrame:
    """CDI, IPCA e dólar mensais a partir das séries oficiais."""
    # um mês a mais no começo para calcular a primeira variação do dólar
    antes = (pd.Timestamp(inicio) - pd.offsets.MonthBegin(1)).date()
    series = {
        "CDI": cdi_mensal(sgs(12, inicio, fim)),
        "IPCA": sgs(433, inicio, fim).pipe(lambda s: s.set_axis(s.index.to_period("M"))),
        "Dólar": variacao_mensal_fim_de_mes(sgs(1, antes, fim)),
    }
    linhas = []
    for indice, s in series.items():
        for mes, v in s.dropna().items():
            if mes >= pd.Period(inicio, "M"):
                linhas.append({"mes": mes, "classe": CLASSES[indice], "indice": indice,
                               "retorno_pct": round(float(v), 2), "previa": False,
                               "fonte": "BCB/SGS"})
    return pd.DataFrame(linhas)


def montar(usar_api: bool = True, verbose: bool = True) -> pd.DataFrame:
    """Base + dados oficiais do BCB por cima (quando disponíveis).

    Meses que existem na base e ainda não saíram no BCB (ex.: IPCA de um mês
    com só a prévia IPCA-15) continuam vindo da base, marcados como prévia.
    """
    base = ler_base()
    if not usar_api:
        return base
    try:
        oficial = baixar_bcb(base["mes"].min().start_time.date(), date.today())
    except requests.RequestException as erro:
        if verbose:
            print(f"API do BCB indisponível ({erro.__class__.__name__}); usando só a base.")
        return base

    chave = ["mes", "indice"]
    comp = base.merge(oficial, on=chave, suffixes=("_base", "_bcb"))
    comp["diferenca"] = (comp["retorno_pct_bcb"] - comp["retorno_pct_base"]).round(2)
    divergentes = comp[comp["diferenca"].abs() > 0.05]
    if verbose and not divergentes.empty:
        print("Diferenças base x BCB acima de 0,05 p.p. (vale o BCB):")
        print(divergentes[chave + ["retorno_pct_base", "retorno_pct_bcb"]].to_string(index=False))

    fica = base.merge(oficial[chave], on=chave, how="left", indicator=True)
    fica = fica[fica["_merge"] == "left_only"].drop(columns="_merge")
    oficial = oficial[oficial["mes"] <= base["mes"].max()]
    return pd.concat([fica, oficial], ignore_index=True).sort_values(chave).reset_index(drop=True)


def em_colunas(longo: pd.DataFrame) -> pd.DataFrame:
    """Formato largo: meses nas linhas, índices nas colunas (retorno em %)."""
    largo = longo.pivot(index="mes", columns="indice", values="retorno_pct")
    return largo[[c for c in CLASSES if c in largo.columns]].astype(float)
