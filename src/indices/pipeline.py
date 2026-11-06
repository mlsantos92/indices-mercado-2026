"""Monta a base, calcula as métricas e gera tabelas e gráficos em outputs/.

Uso:
    python -m indices.pipeline            # tenta a API do BCB; se falhar, usa a base
    python -m indices.pipeline --offline  # só a base do repositório
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import carteira, coleta, graficos, historico, metricas

RAIZ = Path(__file__).resolve().parents[2]
SAIDAS = RAIZ / "outputs"


def main(usar_api: bool = True) -> None:
    SAIDAS.mkdir(exist_ok=True)
    longo = coleta.montar(usar_api=usar_api)
    (RAIZ / "data" / "processed").mkdir(parents=True, exist_ok=True)
    longo.to_csv(RAIZ / "data" / "processed" / "indices_mensal.csv", index=False)

    largo = coleta.em_colunas(longo)
    ano = int(largo.index.max().year)
    ultimo = largo.index.max().strftime("%m/%Y")
    largo_ano = largo[largo.index.year == ano]

    res = metricas.resumo(largo, ano)
    res.round(2).to_csv(SAIDAS / "resumo.csv", index=False)
    metricas.acumulado_por_ano(largo).round(2).to_csv(SAIDAS / "acumulado_por_ano.csv")

    meta = metricas.acumulado(metricas.benchmark_ipca_mais(largo_ano))
    ipca_ano = metricas.acumulado(largo_ano["IPCA"])

    graficos.evolucao_base100(metricas.indice_base100(largo_ano), SAIDAS / "evolucao_ano.png",
                              f"R$ 100 aplicados em janeiro de {ano} (até {ultimo})")
    graficos.barras_no_ano(res, f"no_ano_{ano}", ipca_ano, SAIDAS / "no_ano.png",
                           f"Retorno acumulado em {ano} (até {ultimo})")
    graficos.mapa_mensal(largo.tail(12), SAIDAS / "mapa_mensal.png", "Retorno mês a mês (%), últimos 12 meses")

    # ---------------- histórico 2011–2026 e carteira de exemplo
    anuais, meses = historico.com_ano_parcial(historico.ler_anual(), largo)
    ini, fim = int(anuais.index.min()), int(anuais.index.max())
    per = historico.periodo(anuais, meses, ini, fim)
    per.round(2).to_csv(SAIDAS / "acumulado_periodo.csv")
    anuais.round(2).to_csv(SAIDAS / "retorno_anual.csv")
    historico.tabela_periodica(anuais, ini, fim).to_csv(SAIDAS / "tabela_periodica.csv")
    n_meses = int(meses.sum())
    meta_per = ((1 + per.loc["IPCA", "acumulado_pct"] / 100) * 1.04 ** (n_meses / 12) - 1) * 100
    graficos.acumulado_periodo(per, meta_per, SAIDAS / "acumulado_periodo.png",
                               f"Acumulado de {ini} a {ultimo} ({n_meses // 12} anos e {n_meses % 12} meses)")

    cart = carteira.Carteira(carteira.EXEMPLO)
    df = cart.anual(anuais, meses, ini, fim)
    rc, rk = cart.resumo(df), cart.risco(df)
    cmp = carteira.comparar_sharpe(cart, df, anuais)
    df.round(2).to_csv(SAIDAS / "carteira_exemplo.csv")
    graficos.carteira_evolucao(df, SAIDAS / "carteira_exemplo.png",
                               f"Carteira de exemplo × CDI, IPCA e meta ({ini}–{ultimo})")
    graficos.sharpe_comparado(cmp, SAIDAS / "sharpe_mercado.png",
                              f"Sharpe da carteira × índices de mercado ({cmp.attrs['anos']})")

    previas = longo[longo["previa"]]
    print(f"Período: {largo.index.min()} a {largo.index.max()} | fontes: {sorted(longo['fonte'].unique())}")
    if not previas.empty:
        print("Valores ainda preliminares:", ", ".join(f"{r.indice} {r.mes}" for r in previas.itertuples()))
    print(f"\nIPCA no ano: {ipca_ano:.2f}% | meta IPCA + 4% a.a. no ano: {meta:.2f}%\n")
    print(res.round(2).to_string(index=False))
    print(f"\nCarteira de exemplo {rc['inicio']}–{rc['fim']}: {rc['acumulado_pct']:.1f}% "
          f"({rc['ao_ano_pct']:.1f}% a.a., IPCA + {rc['real_aa_pct']:.1f}% a.a.) | CDI {rc['cdi_pct']:.1f}% | "
          f"meta {rc['meta_pct']:.1f}% | volatilidade {rk['vol_pct']:.1f}% | Sharpe {rk['sharpe']:.2f} "
          f"(média dos índices {cmp.attrs['media_indices']:.2f})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    main(usar_api=not ap.parse_args().offline)
