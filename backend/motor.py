"""Motor de posicionamento: assina os scans do ESP32 por MQTT, classifica e
publica a posição estimada para o dashboard.

Uso:  python motor.py [--config config.json]
"""
import argparse
import json
import os

import config as cfgmod
import engine
from mqtt_util import novo_cliente


def carregar_coordenadas(caminho):
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    print(f"[AVISO] {caminho} não encontrado: a posição sairá com x=y=0 "
          f"(use gerador_de_coordenadas.py).")
    return {}


def scan_valido(obj) -> bool:
    return isinstance(obj, dict) and all(
        isinstance(k, str) and isinstance(v, (int, float)) for k, v in obj.items()
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    cfg = cfgmod.carregar(ap.parse_args().config)

    coordenadas = carregar_coordenadas(cfg["arquivo_coordenadas"])
    estado = {"mapa": None, "fila": []}
    suav = engine.Suavizador(cfg["janela"])

    # Se já houver calibração salva, o motor funciona antes de o ESP32 reenviar.
    if os.path.exists(cfg["arquivo_calibracao"]):
        with open(cfg["arquivo_calibracao"], encoding="utf-8") as f:
            estado["mapa"] = engine.montar_mapa(json.load(f), coordenadas)
        print(f"[OK] Calibração local carregada: {len(estado['mapa'])} ponto(s).")

    def publicar(client, scan):
        resultado = engine.classificar(suav.adicionar(scan), estado["mapa"])
        print(f"[POSIÇÃO] {resultado['local']:28s} x={resultado['x']:>4} y={resultado['y']:>4} "
              f"dist={resultado['distancia_db']} dB  conf={resultado['confianca']}")
        client.publish(cfg["topico_saida"], json.dumps(resultado, ensure_ascii=False), retain=True)

    def ao_conectar(client, userdata, flags, rc, *args):
        print(f"[OK] Conectado a {cfg['broker']} (rc={rc})")
        client.subscribe([(cfg["topico_calibracao"], 0), (cfg["topico_brutos"], 0)])
        print(f"     calibração: {cfg['topico_calibracao']}")
        print(f"     scans     : {cfg['topico_brutos']}")
        print(f"     saída     : {cfg['topico_saida']}\n")

    def ao_receber(client, userdata, msg):
        try:
            dados = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            print("[ERRO] Payload inválido ignorado.")
            return

        if msg.topic == cfg["topico_calibracao"]:
            if not isinstance(dados, dict) or "assinaturas" not in dados:
                print("[ERRO] Calibração sem o campo 'assinaturas'.")
                return
            with open(cfg["arquivo_calibracao"], "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=2, ensure_ascii=False)
            estado["mapa"] = engine.montar_mapa(dados, coordenadas)
            suav.reset()
            print(f"[Cal] {len(estado['mapa'])} ponto(s) recebidos e salvos.")
            for scan in estado["fila"]:
                publicar(client, scan)
            estado["fila"].clear()
            return

        if not scan_valido(dados):
            print("[ERRO] Scan com formato inesperado ignorado.")
            return
        if estado["mapa"] is None:
            estado["fila"].append(dados)
            print(f"[Fila] Aguardando calibração ({len(estado['fila'])} scan(s)).")
            return
        publicar(client, dados)

    client = novo_cliente("ips_motor")
    client.on_connect = ao_conectar
    client.on_message = ao_receber
    print(f"Conectando a {cfg['broker']}:{cfg['porta']} ...")
    client.connect(cfg["broker"], cfg["porta"], 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
