"""Monta a base, calcula as métricas e gera tabelas e gráficos em outputs/.

Uso:
    python -m indices.pipeline            # tenta a API do BCB; se falhar, usa a base
    python -m indices.pipeline --offline  # só a base do repositório
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import coleta, graficos, metricas

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

    previas = longo[longo["previa"]]
    print(f"Período: {largo.index.min()} a {largo.index.max()} | fontes: {sorted(longo['fonte'].unique())}")
    if not previas.empty:
        print("Valores ainda preliminares:", ", ".join(f"{r.indice} {r.mes}" for r in previas.itertuples()))
    print(f"\nIPCA no ano: {ipca_ano:.2f}% | meta IPCA + 4% a.a. no ano: {meta:.2f}%\n")
    print(res.round(2).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    main(usar_api=not ap.parse_args().offline)
