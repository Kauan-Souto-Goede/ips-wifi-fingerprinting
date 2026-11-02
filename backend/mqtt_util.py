"""Cria um cliente paho-mqtt compatível com as versões 1.x e 2.x."""
import paho.mqtt.client as mqtt


def novo_cliente(client_id: str) -> mqtt.Client:
    if hasattr(mqtt, "CallbackAPIVersion"):  # paho-mqtt >= 2.0
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    return mqtt.Client(client_id=client_id)
