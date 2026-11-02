"""Coleta de varreduras rotuladas para testes em campo.

Fique no ponto indicado e rode, por exemplo:
    python coletor.py --ponto "poltrona sala" --n 20
Cada scan recebido do ESP32 é gravado em dados_campo/<data>.jsonl com o rótulo.
Dica: grave o firmware com SCAN_INTERVALO_MS 5000 durante a coleta.
Use varreduras NOVAS, em horários diferentes da calibração, para a acurácia valer.
"""
import argparse
import datetime
import json
import os

import config as cfgmod
from mqtt_util import novo_cliente


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ponto", required=True, help="nome do ponto, igual ao da calibração")
    ap.add_argument("--n", type=int, default=20, help="quantidade de scans")
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()
    cfg = cfgmod.carregar(args.config)

    os.makedirs("dados_campo", exist_ok=True)
    arquivo = os.path.join("dados_campo", datetime.date.today().isoformat() + ".jsonl")
    contador = {"n": 0}
    client = novo_cliente("ips_coletor")

    def ao_conectar(c, u, f, rc, *a):
        c.subscribe(cfg["topico_brutos"])
        print(f"Coletando {args.n} scans em '{args.ponto}' -> {arquivo}")

    def ao_receber(c, u, msg):
        try:
            redes = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(redes, dict):
            return
        registro = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                    "ponto": args.ponto, "redes": redes}
        with open(arquivo, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        contador["n"] += 1
        print(f"  scan {contador['n']}/{args.n} ({len(redes)} redes)")
        if contador["n"] >= args.n:
            c.disconnect()

    client.on_connect = ao_conectar
    client.on_message = ao_receber
    client.connect(cfg["broker"], cfg["porta"], 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
