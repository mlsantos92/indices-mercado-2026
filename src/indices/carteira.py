"""Carteira teórica montada com os índices como base (mesmas regras do dashboard).

- **Rebalanceamento anual**: no início de cada ano a carteira volta aos pesos
  informados; o retorno do ano é a média ponderada dos índices.
- **Taxa do cliente** na renda fixa substitui o índice quando informada:
  * CDI: ``x% do CDI`` sobre o CDI diário (21 dias úteis por mês);
  * IMA-B: ``IPCA + x% a.a.`` sobre o IPCA do mesmo ano;
  * IRF-M: ``x% a.a.`` prefixado, proporcional aos meses.
- **Risco do prefixado**: com taxa do cliente, a RF Pré rende a taxa contratada,
  mas a oscilação usada na volatilidade e no Sharpe é a do IRF-M no período
  (marcação a mercado). Levar ao vencimento não apaga o risco de quem precisa
  vender antes.
- **Sharpe** = excesso médio sobre o CDI ÷ desvio do excesso, em anos completos,
  comparado com o Sharpe de cada índice de mercado nos mesmos anos.
- **Aportes**: inicial no começo do período e anual no início de cada ano.
- Índices que só existem a partir de certo ano (Bitcoin, 2020) fazem o
  período da carteira começar nesse ano.

Uso pela linha de comando:
    python -m indices.carteira
    python -m indices.carteira --pesos "CDI=60,IMA-B=40" --taxa-cdi 110 --ipca-mais 6 --inicio 2016
    python -m indices.carteira --pesos "CDI=70,IRF-M=30" --pre 12 --aporte-inicial 100000 --aporte-anual 24000
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import coleta, historico

EXEMPLO = {"CDI": 35, "IMA-B": 20, "IRF-M": 10, "IHFA": 5, "IBOV": 10, coleta.SP_REAIS: 10, "IFIX": 10}
DIAS_UTEIS_MES = 21
META_REAL_AA = 4.0
# fora da comparação de Sharpe: a referência, a inflação e o índice em outra moeda
FORA_MERCADO = ("CDI", "IPCA", coleta.SP_DOLAR)


@dataclass
class Carteira:
    pesos: dict[str, float]
    taxa_cdi_pct: float | None = None   # ex.: 110 -> 110% do CDI
    ipca_mais_aa: float | None = None   # ex.: 6 -> IPCA + 6% a.a.
    pre_aa: float | None = None         # ex.: 12 -> 12% a.a.
    pesos_norm: dict[str, float] = field(init=False)

    def __post_init__(self) -> None:
        total = sum(v for v in self.pesos.values() if v > 0)
        if total <= 0:
            raise ValueError("Informe ao menos um peso maior que zero.")
        self.pesos_norm = {k: v / total for k, v in self.pesos.items() if v > 0}

    def retorno_indice(self, indice: str, base: float, meses: int, ipca: float, cdi: float) -> float:
        """Retorno (%) de um índice no período, com a taxa do cliente quando houver."""
        if indice == "CDI" and self.taxa_cdi_pct is not None:
            du = max(1, round(DIAS_UTEIS_MES * meses))
            diario = (1 + cdi / 100) ** (1 / du) - 1
            return ((1 + self.taxa_cdi_pct / 100 * diario) ** du - 1) * 100
        if indice == "IMA-B" and self.ipca_mais_aa is not None:
            return ((1 + ipca / 100) * (1 + self.ipca_mais_aa / 100) ** (meses / 12) - 1) * 100
        if indice == "IRF-M" and self.pre_aa is not None:
            return ((1 + self.pre_aa / 100) ** (meses / 12) - 1) * 100
        return base

    # ------------------------------------------------------------- retornos
    def anual(self, anuais: pd.DataFrame, meses: pd.Series, inicio: int, fim: int) -> pd.DataFrame:
        """Retorno da carteira ano a ano, com CDI, IPCA e IRF-M do mesmo ano.

        Anos em que falta algum índice da carteira ficam de fora (ex.: Bitcoin antes de 2020).
        """
        faltam = [k for k in self.pesos_norm if k not in anuais.columns]
        if faltam:
            raise KeyError(f"Índices desconhecidos: {faltam}. Use: {list(anuais.columns)}")
        linhas = []
        for ano in range(inicio, fim + 1):
            if ano not in anuais.index:
                continue
            r = anuais.loc[ano]
            if r[list(self.pesos_norm)].isna().any():
                continue
            m = int(meses.loc[ano])
            ret = sum(w * self.retorno_indice(k, r[k], m, r["IPCA"], r["CDI"]) for k, w in self.pesos_norm.items())
            linhas.append({"ano": ano, "carteira": ret, "cdi": r["CDI"], "ipca": r["IPCA"],
                           "irfm": r["IRF-M"], "meses": m})
        if not linhas:
            raise ValueError("Nenhum ano do período tem todos os índices da carteira.")
        return pd.DataFrame(linhas).set_index("ano")

    def resumo(self, df: pd.DataFrame) -> dict[str, float]:
        """Acumulado, ao ano, ganho real e meta IPCA + 4% a.a. no período."""
        n = int(df["meses"].sum())
        f = lambda s: float((1 + s / 100).prod())  # noqa: E731
        fc, fi, fd = f(df["carteira"]), f(df["ipca"]), f(df["cdi"])
        return {
            "inicio": int(df.index.min()), "fim": int(df.index.max()), "meses": n,
            "acumulado_pct": (fc - 1) * 100, "ao_ano_pct": (fc ** (12 / n) - 1) * 100,
            "cdi_pct": (fd - 1) * 100, "ipca_pct": (fi - 1) * 100,
            "real_aa_pct": ((fc / fi) ** (12 / n) - 1) * 100,
            "meta_pct": (fi * (1 + META_REAL_AA / 100) ** (n / 12) - 1) * 100,
        }

    # ----------------------------------------------------------------- risco
    def com_marcacao(self, df: pd.DataFrame) -> pd.Series:
        """Retornos da carteira para medir risco.

        Sem taxa prefixada, é o próprio retorno. Com ela, soma-se o desvio do
        IRF-M em torno da sua média no período, ponderado pelo peso da RF Pré:
        a média continua a da taxa contratada; a oscilação passa a ser a do mercado.
        """
        w = self.pesos_norm.get("IRF-M", 0) if self.pre_aa is not None else 0
        return df["carteira"] + w * (df["irfm"] - df["irfm"].mean())

    def risco(self, df: pd.DataFrame) -> dict[str, float]:
        """Volatilidade e Sharpe em anos completos (ano parcial fica de fora)."""
        cheios = df[df["meses"] == 12]
        if len(cheios) < 2:
            raise ValueError("São precisos ao menos 2 anos completos.")
        ret = self.com_marcacao(cheios)
        exc = ret - cheios["cdi"]
        return {"anos": len(cheios), "vol_pct": float(ret.std(ddof=1)), "vol_cdi_pct": float(cheios["cdi"].std(ddof=1)),
                "excesso_medio_pp": float(exc.mean()), "sharpe": float(exc.mean() / exc.std(ddof=1)),
                "anos_abaixo_cdi": int((exc < 0).sum())}

    # ---------------------------------------------------------------- reais
    @staticmethod
    def simular_aportes(df: pd.DataFrame, inicial: float = 0.0, anual: float = 0.0) -> dict[str, float]:
        """Aporte inicial no começo do período e anual no início de cada ano (inclusive o primeiro)."""
        if inicial <= 0 and anual <= 0:
            raise ValueError("Informe um aporte inicial, um aporte anual ou os dois.")
        saldo = corrigido = aportado = 0.0
        for i, (_, a) in enumerate(df.iterrows()):
            ap = (inicial if i == 0 else 0.0) + anual
            aportado += ap
            saldo = (saldo + ap) * (1 + a["carteira"] / 100)
            corrigido = (corrigido + ap) * (1 + a["ipca"] / 100)
        saldo, corrigido = float(saldo), float(corrigido)
        return {"aportado": aportado, "saldo": saldo, "aportes_corrigidos_ipca": corrigido,
                "ganho_bruto": saldo - aportado, "ganho_real": saldo - corrigido,
                "bruto_pct": (saldo / aportado - 1) * 100, "real_pct": (saldo / corrigido - 1) * 100}

    def valor_hoje(self, df: pd.DataFrame, valor_atual: float) -> dict[str, float]:
        """A partir do saldo de hoje, o valor no início e os ganhos bruto e real do período."""
        r = self.resumo(df)
        v0 = valor_atual / (1 + r["acumulado_pct"] / 100)
        corr = v0 * (1 + r["ipca_pct"] / 100)
        v0, corr = float(v0), float(corr)
        return {"valor_inicio": v0, "ganho_bruto": valor_atual - v0, "ganho_real": valor_atual - corr}


def sharpe_mercado(anuais: pd.DataFrame, anos: list[int]) -> pd.Series:
    """Sharpe de cada índice de mercado nos mesmos anos (só quem tem todos os anos)."""
    janela = anuais.loc[anos]
    exc = janela.drop(columns=[c for c in FORA_MERCADO if c in janela.columns]).sub(janela["CDI"], axis=0)
    exc = exc.dropna(axis=1)
    return (exc.mean() / exc.std(ddof=1)).sort_values(ascending=False)


def comparar_sharpe(carteira: Carteira, df: pd.DataFrame, anuais: pd.DataFrame) -> pd.DataFrame:
    """Sharpe da carteira ao lado do de cada índice e da média dos índices."""
    risco = carteira.risco(df)
    anos = list(df[df["meses"] == 12].index)
    mercado = sharpe_mercado(anuais, anos)
    tab = pd.concat([mercado, pd.Series({"Carteira": risco["sharpe"]})]).sort_values(ascending=False)
    out = tab.to_frame("sharpe")
    out.attrs.update(media_indices=float(mercado.mean()), acima_de=int((risco["sharpe"] > mercado).sum()),
                     n_indices=len(mercado), anos=f"{anos[0]}–{anos[-1]}")
    return out


# ------------------------------------------------------------------------ CLI
def _ler_pesos(txt: str) -> dict[str, float]:
    pesos = {}
    for parte in txt.split(","):
        k, v = parte.rsplit("=", 1)
        pesos[k.strip()] = float(v)
    return pesos


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pesos", default=",".join(f"{k}={v}" for k, v in EXEMPLO.items()))
    ap.add_argument("--inicio", type=int, default=2011)
    ap.add_argument("--fim", type=int, default=2026)
    ap.add_argument("--taxa-cdi", type=float)
    ap.add_argument("--ipca-mais", type=float)
    ap.add_argument("--pre", type=float)
    ap.add_argument("--aporte-inicial", type=float, default=0.0)
    ap.add_argument("--aporte-anual", type=float, default=0.0)
    ap.add_argument("--valor-hoje", type=float)
    a = ap.parse_args(argv)

    anuais, meses = historico.com_ano_parcial(historico.ler_anual(), coleta.em_colunas(coleta.ler_base()))
    c = Carteira(_ler_pesos(a.pesos), a.taxa_cdi, a.ipca_mais, a.pre)
    df = c.anual(anuais, meses, a.inicio, a.fim)
    r = c.resumo(df)
    print(f"Carteira {r['inicio']}–{r['fim']} ({r['meses']} meses): {r['acumulado_pct']:.1f}% "
          f"({r['ao_ano_pct']:.1f}% a.a.) | CDI {r['cdi_pct']:.1f}% | IPCA {r['ipca_pct']:.1f}% | "
          f"real {r['real_aa_pct']:.1f}% a.a. | meta IPCA+4% {r['meta_pct']:.1f}%")
    print(df.round(2).to_string())
    try:
        rk, cmp = c.risco(df), comparar_sharpe(c, df, anuais)
        print(f"\nVolatilidade {rk['vol_pct']:.1f}% a.a. | Sharpe {rk['sharpe']:.2f} | média dos índices "
              f"{cmp.attrs['media_indices']:.2f} | carteira acima de {cmp.attrs['acima_de']} de {cmp.attrs['n_indices']}")
        print(cmp.round(2).to_string())
    except ValueError as e:
        print("\nRisco:", e)
    if a.aporte_inicial or a.aporte_anual:
        s = c.simular_aportes(df, a.aporte_inicial, a.aporte_anual)
        print(f"\nAportado R$ {s['aportado']:,.2f} -> R$ {s['saldo']:,.2f} | ganho real R$ {s['ganho_real']:,.2f}")
    if a.valor_hoje:
        v = c.valor_hoje(df, a.valor_hoje)
        print(f"\nValor no início R$ {v['valor_inicio']:,.2f} | ganho bruto R$ {v['ganho_bruto']:,.2f} | "
              f"ganho real R$ {v['ganho_real']:,.2f}")


if __name__ == "__main__":
    main()
