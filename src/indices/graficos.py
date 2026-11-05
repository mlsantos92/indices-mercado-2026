"""Gráficos estáticos (PNG) para o README e o notebook."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

SUPERFICIE, TINTA, TINTA2, GRADE, NEUTRO = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#b9b8b2"
# ordem fixa de cores categóricas (paleta validada para daltonismo)
CORES = {"IBOV": "#2a78d6", "CDI": "#eb6834", "IPCA": "#1baf7a", "Dólar": "#eda100"}
DIVERGENTE = LinearSegmentedColormap.from_list("div", ["#c43d3c", "#f0efec", "#256abf"])


def _base(ax):
    ax.set_facecolor(SUPERFICIE)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(NEUTRO)
    ax.tick_params(colors=TINTA2, labelsize=9)
    ax.set_axisbelow(True)


MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _mes(p: pd.Period) -> str:
    return f"{MESES[p.month - 1]}/{str(p.year)[2:]}"


def _afastar(valores: dict[str, float], folga: float) -> dict[str, float]:
    """Separa verticalmente rótulos de fim de linha que ficariam sobrepostos."""
    ordem = sorted(valores, key=valores.get)
    pos, anterior = {}, None
    for k in ordem:
        y = valores[k] if anterior is None else max(valores[k], anterior + folga)
        pos[k], anterior = y, y
    return pos


def _br(v: float, casas: int = 1) -> str:
    return f"{v:+.{casas}f}%".replace(".", ",")


def evolucao_base100(base100: pd.DataFrame, caminho: Path, titulo: str) -> None:
    # ponto de partida: R$ 100 no fim do mês anterior ao primeiro retorno
    inicio = base100.index[0] - 1
    b = pd.concat([pd.DataFrame(100.0, index=[inicio], columns=base100.columns), base100])
    x = np.arange(len(b))
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=SUPERFICIE)
    _base(ax)
    ax.grid(axis="y", color=GRADE, linewidth=0.7)
    fim = b.iloc[-1]
    folga = (b.max().max() - b.min().min()) * 0.035
    ypos = _afastar(fim.to_dict(), folga)
    for c in b.columns:
        destaque = c in CORES
        ax.plot(x, b[c], color=CORES.get(c, NEUTRO), linewidth=2.2 if destaque else 1.2,
                label=c if destaque else None, zorder=3 if destaque else 2)
        ax.annotate(f"{c} {fim[c]:.0f}" if destaque else c, (x[-1], ypos[c]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9 if destaque else 8,
                    color=TINTA if destaque else TINTA2, fontweight="bold" if destaque else "normal")
    ax.axhline(100, color=TINTA2, linewidth=0.8)
    ax.set_xticks(x, ["início"] + [_mes(p) for p in base100.index])
    ax.set_ylabel("R$ 100 aplicados no início", color=TINTA2)
    ax.set_title(titulo, loc="left", color=TINTA, fontweight="bold")
    ax.legend(frameon=False, loc="upper left", fontsize=9, ncol=4)
    ax.set_xlim(-0.3, x[-1] + 1.6)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


def barras_no_ano(resumo: pd.DataFrame, coluna: str, ipca: float, caminho: Path, titulo: str) -> None:
    d = resumo[resumo["indice"] != "IPCA"].sort_values(coluna)
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=SUPERFICIE)
    _base(ax)
    ax.grid(axis="x", color=GRADE, linewidth=0.7)
    cores = ["#2a78d6" if v >= ipca else NEUTRO for v in d[coluna]]
    ax.barh(d["indice"], d[coluna], color=cores, height=0.62)
    ax.axvline(ipca, color="#1baf7a", linestyle="--", linewidth=1.6)
    ax.annotate(f"IPCA {_br(ipca)}", (ipca, len(d) - 0.4), xytext=(4, 0), textcoords="offset points",
                color=TINTA, fontsize=9)
    ax.axvline(0, color=TINTA2, linewidth=0.8)
    for y, v in enumerate(d[coluna]):
        ax.annotate(_br(v), (v, y), xytext=(4 if v >= 0 else -4, 0), textcoords="offset points",
                    ha="left" if v >= 0 else "right", va="center", fontsize=9, color=TINTA)
    ax.set_title(titulo, loc="left", color=TINTA, fontweight="bold")
    ax.set_xlabel("retorno acumulado (azul = venceu a inflação)", color=TINTA2)
    ax.margins(x=0.15)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


def mapa_mensal(largo: pd.DataFrame, caminho: Path, titulo: str) -> None:
    d = largo.T
    lim = np.nanmax(np.abs(d.to_numpy()))
    fig, ax = plt.subplots(figsize=(10, 4.6), facecolor=SUPERFICIE)
    ax.imshow(d.to_numpy(), cmap=DIVERGENTE, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    ax.set_xticks(range(d.shape[1]), [_mes(p) for p in d.columns], fontsize=8, color=TINTA2)
    ax.set_yticks(range(d.shape[0]), d.index, fontsize=9, color=TINTA)
    for i in range(d.shape[0]):
        for j in range(d.shape[1]):
            v = d.iat[i, j]
            if pd.notna(v):
                forte = abs(v) > 0.6 * lim
                ax.text(j, i, f"{v + 0.0:.1f}".replace(".", ",").replace("-0,0", "0,0"), ha="center", va="center", fontsize=7.5,
                        color="white" if forte else TINTA)
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.set_title(titulo, loc="left", color=TINTA, fontweight="bold")
    fig.tight_layout()
    fig.savefig(caminho, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)
