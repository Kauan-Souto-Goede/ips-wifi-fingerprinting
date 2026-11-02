"""Algoritmo de posicionamento por Wi-Fi fingerprinting (sem dependência de MQTT).

Funções puras, para poder testar sem hardware:
  - montar_mapa: junta calibração (assinaturas) com coordenadas (x, y na planta).
  - classificar: escolhe o ponto calibrado mais parecido com um scan.
  - Suavizador: média das últimas N varreduras antes de classificar.
  - classificar_legado: algoritmo da primeira versão, mantido só para comparação.

Convenção: RSSI em dBm; rede não detectada vale AUSENTE (-100 dBm).
"""
from __future__ import annotations

import math
from collections import deque

AUSENTE = -100


def montar_mapa(calibracao: dict, coordenadas: dict | None = None) -> dict:
    """Retorna {ponto: {"x", "y", "assinatura": {mac: rssi}}}.

    Pontos sem coordenadas ficam com x=y=0 (só o nome é útil). Coordenadas de
    pontos que não foram calibrados são ignoradas.
    """
    coordenadas = coordenadas or {}
    mapa = {}
    for ponto, redes in calibracao.get("assinaturas", {}).items():
        c = coordenadas.get(ponto, {})
        mapa[ponto] = {"x": c.get("x", 0), "y": c.get("y", 0), "assinatura": dict(redes)}
    return mapa


def macs_conhecidos(mapa: dict) -> list[str]:
    """União das redes vistas em qualquer ponto da calibração (ordem estável)."""
    return sorted({mac for p in mapa.values() for mac in p["assinatura"]})


def distancia_rms(scan: dict, assinatura: dict, macs: list[str]) -> float:
    """Distância RMS (dB) entre um scan e uma assinatura, sobre o MESMO conjunto
    de redes para todos os pontos.

    Comparar todos os pontos sobre as mesmas redes evita o viés da versão
    anterior, que somava só as redes de cada ponto: um ponto calibrado com poucas
    redes tinha menos termos na soma e ganhava com mais frequência.
    Redes do scan que nenhum ponto conhece afetam todos os pontos igualmente e
    não mudam o ranking, então são ignoradas.
    """
    if not macs:
        return math.inf
    soma = sum((scan.get(m, AUSENTE) - assinatura.get(m, AUSENTE)) ** 2 for m in macs)
    return math.sqrt(soma / len(macs))


def classificar(scan: dict, mapa: dict) -> dict:
    """Retorna o ponto mais parecido com o scan.

    Campos: local, x, y, distancia_db (menor = melhor), margem_db (distância do
    segundo colocado menos a do primeiro), segundo (nome do 2º colocado) e
    confianca em [0, 1): margem / (margem + distancia). Alta quando o segundo
    colocado está bem pior que o primeiro; é uma heurística, não probabilidade.
    """
    if not mapa:
        raise ValueError("mapa vazio: calibração não carregada")
    macs = macs_conhecidos(mapa)
    ranking = sorted(
        ((distancia_rms(scan, p["assinatura"], macs), nome) for nome, p in mapa.items())
    )
    d1, melhor = ranking[0]
    d2, segundo = ranking[1] if len(ranking) > 1 else (math.inf, None)
    margem = d2 - d1 if math.isfinite(d2) else math.inf
    if math.isfinite(margem):
        confianca = margem / (margem + d1) if (margem + d1) > 0 else 1.0
    else:
        confianca = 1.0
    return {
        "local": melhor,
        "x": mapa[melhor]["x"],
        "y": mapa[melhor]["y"],
        "distancia_db": round(d1, 2),
        "margem_db": round(margem, 2) if math.isfinite(margem) else None,
        "segundo": segundo,
        "confianca": round(confianca, 3),
    }


class Suavizador:
    """Média das últimas `janela` varreduras (rede ausente conta como -100).

    Reduz o efeito do ruído do RSSI, ao custo de atraso: com varredura a cada
    10 s e janela 3, a posição leva até ~30 s para refletir uma mudança de lugar.
    """

    def __init__(self, janela: int = 3):
        self.janela = max(1, int(janela))
        self._scans: deque[dict] = deque(maxlen=self.janela)

    def reset(self) -> None:
        self._scans.clear()

    def adicionar(self, scan: dict) -> dict:
        self._scans.append(scan)
        n = len(self._scans)
        macs = {m for s in self._scans for m in s}
        return {m: sum(s.get(m, AUSENTE) for s in self._scans) / n for m in macs}


def classificar_legado(scan: dict, mapa: dict) -> dict:
    """Algoritmo da primeira versão: soma dos quadrados só sobre as redes de cada
    ponto, sem normalizar. Mantido para comparar com o atual (simular.py/avaliar.py).
    """
    melhor, menor = None, math.inf
    for nome, p in mapa.items():
        soma = sum((scan.get(m, AUSENTE) - r) ** 2 for m, r in p["assinatura"].items())
        d = math.sqrt(soma)
        if d < menor:
            melhor, menor = nome, d
    return {"local": melhor, "x": mapa[melhor]["x"], "y": mapa[melhor]["y"],
            "distancia_db": round(menor, 2)}
