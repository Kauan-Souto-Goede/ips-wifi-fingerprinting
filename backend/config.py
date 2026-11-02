"""Leitura da configuração (config.json), com valores padrão."""
import json
import os

PADRAO = {
    "broker": "broker.hivemq.com",
    "porta": 1883,
    "topic_prefix": "ips/demo",
    "janela": 3,
    "arquivo_calibracao": "calibracao.json",
    "arquivo_coordenadas": "coordenadas.json",
}


def carregar(caminho: str = "config.json") -> dict:
    cfg = dict(PADRAO)
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            cfg.update(json.load(f))
    else:
        print(f"[AVISO] {caminho} não encontrado; usando valores padrão "
              f"(copie config.example.json para config.json).")
    cfg["topico_calibracao"] = cfg["topic_prefix"] + "/calibracao"
    cfg["topico_brutos"] = cfg["topic_prefix"] + "/dados_brutos"
    cfg["topico_saida"] = cfg["topic_prefix"] + "/localizacao_final"
    return cfg
