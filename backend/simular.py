"""Simulação de acurácia a partir de uma calibração (NÃO é medição em campo).

Gera varreduras sintéticas a partir das assinaturas calibradas, com ruído
gaussiano por rede, redes fracas que somem aleatoriamente e redes intrusas
(vizinhos) que não estão na calibração, e compara o algoritmo legado com o atual.
Serve para escolher parâmetros e detectar regressões; os números de campo vêm do
coletor.py + avaliar.py.

Uso:  python simular.py [--calibracao calibracao.json] [--sigma 4] [--n 200] [--seed 1]
"""
import argparse
import json
import random

import engine


def amostra(assinatura, sigma, rng):
    scan = {}
    for mac, rssi in assinatura.items():
        if rssi < -85 and rng.random() < 0.4:      # rede fraca some em parte das varreduras
            continue
        scan[mac] = round(rssi + rng.gauss(0, sigma))
    for i in range(rng.randint(0, 3)):              # vizinhos que não estavam na calibração
        scan[f"FFFFFF{rng.randrange(16**6):06X}"] = rng.randint(-95, -70)
    return scan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibracao", default="calibracao.json")
    ap.add_argument("--sigma", type=float, default=4.0, help="desvio do ruído em dB")
    ap.add_argument("--n", type=int, default=200, help="scans por ponto")
    ap.add_argument("--janela", type=int, default=3)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    with open(a.calibracao, encoding="utf-8") as f:
        mapa = engine.montar_mapa(json.load(f))
    rng = random.Random(a.seed)
    acertos = {"legado": 0, "atual": 0, f"atual+janela{a.janela}": 0}
    total = 0
    for ponto, p in mapa.items():
        suav = engine.Suavizador(a.janela)
        for _ in range(a.n):
            scan = amostra(p["assinatura"], a.sigma, rng)
            total += 1
            acertos["legado"] += engine.classificar_legado(scan, mapa)["local"] == ponto
            acertos["atual"] += engine.classificar(scan, mapa)["local"] == ponto
            acertos[f"atual+janela{a.janela}"] += engine.classificar(suav.adicionar(scan), mapa)["local"] == ponto
    print(f"SIMULAÇÃO: {len(mapa)} pontos, {a.n} scans/ponto, ruído σ={a.sigma} dB, seed={a.seed}")
    for nome, ok in acertos.items():
        print(f"  {nome:16s} {100 * ok / total:5.1f}%")


if __name__ == "__main__":
    main()
