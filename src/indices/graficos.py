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
    # escala robusta: o Bitcoin (até ±28% no mês) não pode apagar as cores dos demais
    lim = float(np.nanpercentile(np.abs(d.to_numpy()), 95))
    fig, ax = plt.subplots(figsize=(10, 4.6), facecolor=SUPERFICIE)
    ax.imshow(np.clip(d.to_numpy(), -lim, lim), cmap=DIVERGENTE, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
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


# ------------------------------------------------------------ histórico anual
def acumulado_periodo(per: pd.DataFrame, meta_pct: float, caminho: Path, titulo: str) -> None:
    """Barras do acumulado no período, com IPCA e meta IPCA + 4% a.a. como referências."""
    ipca = float(per.loc["IPCA", "acumulado_pct"])
    d = per.drop(index="IPCA").sort_values("acumulado_pct")
    # valores muito acima dos demais (Bitcoin) são cortados para não achatar o resto
    vals = d["acumulado_pct"].astype(float)
    segundo = vals.sort_values().iloc[-2]
    teto = segundo * 1.35 if vals.max() > 3 * segundo else None
    fig, ax = plt.subplots(figsize=(9, 5.2), facecolor=SUPERFICIE)
    _base(ax)
    ax.grid(axis="x", color=GRADE, linewidth=0.7)
    mostrar = vals.clip(upper=teto) if teto else vals
    cores = ["#2a78d6" if v >= meta_pct else "#8fb6e8" if v >= ipca else NEUTRO for v in vals]
    rot = [f"{i} (desde {int(d.loc[i, 'desde'])})" if int(d.loc[i, "desde"]) > int(per["desde"].min()) else i
           for i in d.index]
    ax.barh(rot, mostrar, color=cores, height=0.62)
    for k, (nome, x, cor, est) in enumerate((("IPCA", ipca, "#1baf7a", "--"), ("IPCA + 4% a.a.", meta_pct, TINTA, ":"))):
        ax.axvline(x, color=cor, linestyle=est, linewidth=1.6)
        # rótulos em alturas diferentes, abaixo do eixo, para não se sobreporem
        ax.annotate(f"{nome} {_br(x, 0)}", (x, -0.75 - 0.45 * k), xytext=(4, 0), textcoords="offset points",
                    color=TINTA, fontsize=8.5, va="center", annotation_clip=False)
    for y, (v, m, aa) in enumerate(zip(vals, mostrar, d["ao_ano_pct"].astype(float))):
        txt = f"{'↑ ' if teto and v > teto else ''}{_br(v, 0)} ({aa:.1f}".replace(".", ",") + "% a.a.)"
        ax.annotate(txt, (m, y), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.5, color=TINTA)
    ax.set_title(titulo, loc="left", color=TINTA, fontweight="bold")
    ax.set_xlabel("acumulado no período · azul escuro: bateu IPCA + 4% a.a. · azul claro: só a inflação · cinza: perdeu da inflação", color=TINTA2)
    ax.margins(x=0.22)
    ax.set_ylim(-1.5, len(d) - 0.5)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


def carteira_evolucao(df: pd.DataFrame, caminho: Path, titulo: str, meta_real_aa: float = 4.0) -> None:
    """Acumulado ano a ano da carteira contra CDI, IPCA e a meta IPCA + 4% a.a."""
    inicio = int(df.index.min()) - 1
    meses = df["meses"].cumsum()
    acum = lambda s: ((1 + s / 100).cumprod() - 1) * 100  # noqa: E731
    series = {"Carteira": acum(df["carteira"]), "CDI": acum(df["cdi"]), "IPCA": acum(df["ipca"])}
    series["IPCA + 4% a.a."] = ((1 + series["IPCA"] / 100) * (1 + meta_real_aa / 100) ** (meses / 12) - 1) * 100
    estilo = {"Carteira": (TINTA, "-", 2.6), "CDI": ("#eb6834", "-", 1.8),
              "IPCA": ("#1baf7a", "--", 1.6), "IPCA + 4% a.a.": (TINTA2, ":", 1.8)}
    x = [str(inicio)] + [("2026*" if a == 2026 else str(a)) for a in df.index]
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=SUPERFICIE)
    _base(ax)
    ax.grid(axis="y", color=GRADE, linewidth=0.7)
    fins = {}
    for nome, s in series.items():
        cor, est, lw = estilo[nome]
        y = [0.0] + list(s)
        ax.plot(range(len(x)), y, color=cor, linestyle=est, linewidth=lw, label=nome)
        fins[nome] = y[-1]
    folga = max(fins.values()) * 0.04
    for nome, y in _afastar(fins, folga).items():
        ax.annotate(f"{nome} {_br(fins[nome], 0)}", (len(x) - 1, y), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8.5, color=estilo[nome][0])
    passo = max(1, len(x) // 9)
    ax.set_xticks(range(0, len(x), passo), [("início" if i == 0 else x[i]) for i in range(0, len(x), passo)])
    ax.set_ylabel("retorno acumulado (%)", color=TINTA2)
    ax.set_title(titulo, loc="left", color=TINTA, fontweight="bold")
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    ax.set_xlim(-0.3, len(x) + 1.8)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


def sharpe_comparado(tab: pd.DataFrame, caminho: Path, titulo: str) -> None:
    """Sharpe da carteira (destacada) ao lado dos índices, com a média dos índices tracejada."""
    d = tab["sharpe"].sort_values()
    media = tab.attrs["media_indices"]
    fig, ax = plt.subplots(figsize=(8, 4.4), facecolor=SUPERFICIE)
    _base(ax)
    ax.grid(axis="x", color=GRADE, linewidth=0.7)
    ax.barh(d.index, d.values, height=0.6,
            color=[TINTA if i == "Carteira" else ("#2a78d6" if v >= 0 else "#c43d3c") for i, v in d.items()])
    ax.axvline(0, color=TINTA2, linewidth=0.8)
    ax.axvline(media, color=TINTA2, linestyle="--", linewidth=1.4)
    ax.annotate(f"média dos índices {media:.2f}".replace(".", ","), (media, len(d) - 0.4), xytext=(4, 0),
                textcoords="offset points", fontsize=8.5, color=TINTA)
    for y, v in enumerate(d.values):
        ax.annotate(f"{v:.2f}".replace(".", ","), (v, y), xytext=(4 if v >= 0 else -4, 0), textcoords="offset points",
                    ha="left" if v >= 0 else "right", va="center", fontsize=8.5, color=TINTA)
    for lbl in ax.get_yticklabels():
        if lbl.get_text() == "Carteira":
            lbl.set_fontweight("bold")
    ax.set_title(titulo, loc="left", color=TINTA, fontweight="bold")
    ax.set_xlabel("Sharpe anual: excesso médio sobre o CDI ÷ desvio do excesso", color=TINTA2)
    ax.margins(x=0.18)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)
