"""Avalia o algoritmo com varreduras reais rotuladas (geradas pelo coletor.py).

Uso:
    python avaliar.py dados_campo/*.jsonl [--janela 3] [--saida relatorio.md]
                      [--largura-m 10 --altura-m 12]

Compara três variantes sobre os MESMOS dados:
  legado         soma dos quadrados só sobre as redes de cada ponto
  atual          distância RMS sobre o conjunto comum de redes
  atual+janela   o mesmo, com média das últimas N varreduras

Para acurácia por cômodo, adicione "comodo": "<nome>" a cada ponto em
coordenadas.json. Os erros de posição saem em % da planta (e em metros se
largura/altura forem informadas).
"""
import argparse
import glob
import json
import math
from collections import Counter, defaultdict

import engine


def carregar_registros(padroes):
    regs = []
    for p in padroes:
        for caminho in sorted(glob.glob(p)):
            with open(caminho, encoding="utf-8") as f:
                regs += [json.loads(l) for l in f if l.strip()]
    return regs


def erro_pos(prev, real, largura, altura):
    dx, dy = prev["x"] - real["x"], prev["y"] - real["y"]
    if largura and altura:
        return math.hypot(dx * largura / 100, dy * altura / 100)
    return math.hypot(dx, dy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivos", nargs="+")
    ap.add_argument("--calibracao", default="calibracao.json")
    ap.add_argument("--coordenadas", default="coordenadas.json")
    ap.add_argument("--janela", type=int, default=3)
    ap.add_argument("--saida", default=None, help="grava o relatório em Markdown")
    ap.add_argument("--largura-m", type=float, default=None)
    ap.add_argument("--altura-m", type=float, default=None)
    a = ap.parse_args()

    with open(a.calibracao, encoding="utf-8") as f:
        calibracao = json.load(f)
    try:
        with open(a.coordenadas, encoding="utf-8") as f:
            coords = json.load(f)
    except FileNotFoundError:
        coords = {}
    mapa = engine.montar_mapa(calibracao, coords)
    comodo = {p: coords.get(p, {}).get("comodo") for p in mapa}
    tem_comodos = all(comodo.values()) and bool(comodo)

    regs = carregar_registros(a.arquivos)
    ignorados = Counter(r["ponto"] for r in regs if r["ponto"] not in mapa)
    regs = [r for r in regs if r["ponto"] in mapa]
    if not regs:
        raise SystemExit("Nenhum scan com rótulo presente na calibração.")

    variantes = ["legado", "atual", f"atual+janela{a.janela}"]
    prev = {v: [] for v in variantes}
    suav = engine.Suavizador(a.janela)
    ultimo = None
    for r in regs:
        if r["ponto"] != ultimo:
            suav.reset()
            ultimo = r["ponto"]
        scan = r["redes"]
        prev["legado"].append(engine.classificar_legado(scan, mapa))
        prev["atual"].append(engine.classificar(scan, mapa))
        prev[variantes[2]].append(engine.classificar(suav.adicionar(scan), mapa))

    linhas = [f"# Avaliação em campo ({len(regs)} varreduras, {len({r['ponto'] for r in regs})} pontos)", ""]
    unid = "m" if (a.largura_m and a.altura_m) else "% da planta"
    cab = "| Variante | Acurácia por ponto |" + (" Acurácia por cômodo |" if tem_comodos else "") + f" Erro médio de posição ({unid}) |"
    linhas += [cab, "|" + "---|" * (cab.count("|") - 1)]
    for v in variantes:
        ok = sum(p["local"] == r["ponto"] for p, r in zip(prev[v], regs))
        row = f"| {v} | {100 * ok / len(regs):.1f}% |"
        if tem_comodos:
            okc = sum(comodo[p["local"]] == comodo[r["ponto"]] for p, r in zip(prev[v], regs))
            row += f" {100 * okc / len(regs):.1f}% |"
        err = sum(erro_pos(p, coords.get(r["ponto"], {"x": 0, "y": 0}), a.largura_m, a.altura_m)
                  for p, r in zip(prev[v], regs)) / len(regs)
        linhas.append(row + f" {err:.1f} |")

    principal = variantes[2]
    por_ponto = defaultdict(lambda: [0, 0])
    conf = defaultdict(Counter)
    for p, r in zip(prev[principal], regs):
        por_ponto[r["ponto"]][1] += 1
        por_ponto[r["ponto"]][0] += p["local"] == r["ponto"]
        conf[r["ponto"]][p["local"]] += 1
    linhas += ["", f"## Por ponto ({principal})", "", "| Ponto | Scans | Acertos | Mais confundido com |", "|---|---|---|---|"]
    for ponto, (ok, n) in sorted(por_ponto.items(), key=lambda kv: kv[1][0] / kv[1][1]):
        erros = Counter({k: v for k, v in conf[ponto].items() if k != ponto})
        top = f"{erros.most_common(1)[0][0]} ({erros.most_common(1)[0][1]}x)" if erros else "—"
        linhas.append(f"| {ponto} | {n} | {100 * ok / n:.0f}% | {top} |")
    if ignorados:
        linhas += ["", "Ignorados (ponto não calibrado): " + ", ".join(f"{k} ({v})" for k, v in ignorados.items())]
    texto = "\n".join(linhas)
    print(texto)
    if a.saida:
        with open(a.saida, "w", encoding="utf-8") as f:
            f.write(texto + "\n")
        print(f"\nRelatório salvo em {a.saida}")


if __name__ == "__main__":
    main()
