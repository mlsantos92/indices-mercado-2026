"""Selo de situação do estudo: dados do BCB do último dia útil fechado e testes passando.

Verde:    CDI e dólar do último pregão (ou dia útil anterior, no caso do CDI) e testes ok.
Amarelo:  dado do BCB defasado em relação ao último dia útil fechado.
Vermelho: API do BCB indisponível ou testes falharam.

Uso:
    python -m indices.selo          # usa TESTES_OK=1|0 do ambiente (workflow)
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BRT = ZoneInfo("America/Sao_Paulo")
RAIZ = Path(__file__).resolve().parents[2]


def _dia_util(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def ultimo_fechamento(agora: datetime) -> date:
    """Último dia útil já encerrado em Brasília (o dia corrente conta depois das 18h)."""
    agora = agora.astimezone(BRT)
    d = agora.date() if agora.hour >= 18 else agora.date() - timedelta(days=1)
    return _dia_util(d)


def dia_util_antes(d: date) -> date:
    return _dia_util(d - timedelta(days=1))


def avaliar(dolar_ultimo: date | None, cdi_ultimo: date | None, esperado: date, testes_ok: bool,
            agora: datetime | None = None) -> dict:
    agora = (agora or datetime.now(BRT)).astimezone(BRT)
    if dolar_ultimo is None or cdi_ultimo is None or not testes_ok:
        cor, motivo = "vermelho", "API do BCB indisponível ou testes falharam"
    elif dolar_ultimo < esperado or cdi_ultimo < dia_util_antes(esperado):
        cor = "amarelo"
        motivo = (f"dólar até {dolar_ultimo:%d/%m}, CDI até {cdi_ultimo:%d/%m}; "
                  f"esperado {esperado:%d/%m}")
    else:
        cor, motivo = "verde", "dados do BCB do último dia útil e testes passando"
    return {
        "cor": cor,
        "motivo": motivo,
        "pregao_esperado": esperado.isoformat(),
        "dolar_ate": dolar_ultimo.isoformat() if dolar_ultimo else None,
        "cdi_ate": cdi_ultimo.isoformat() if cdi_ultimo else None,
        "testes": "ok" if testes_ok else "falha",
        "atualizado_em": agora.strftime("%Y-%m-%d %H:%M"),
    }


def _ultima_data(serie) -> date | None:
    return serie.index.max().date() if len(serie) else None


def main() -> None:
    from .coleta import sgs

    agora = datetime.now(BRT)
    esperado = ultimo_fechamento(agora)
    ini = esperado - timedelta(days=20)
    try:
        dolar_ultimo = _ultima_data(sgs(1, ini, agora.date()))
        cdi_ultimo = _ultima_data(sgs(12, ini, agora.date()))
    except Exception as erro:  # rede, API fora do ar ou resposta inesperada
        print(f"BCB indisponível: {erro}")
        dolar_ultimo = cdi_ultimo = None

    info = avaliar(dolar_ultimo, cdi_ultimo, esperado, os.environ.get("TESTES_OK", "0") == "1", agora)
    docs = RAIZ / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "status.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Selo:", info["cor"], "-", info["motivo"])


if __name__ == "__main__":
    main()
