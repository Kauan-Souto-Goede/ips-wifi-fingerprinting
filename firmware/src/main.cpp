#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <LittleFS.h>

// ─── Configurações ─────────────────────────────────────────────────────────────
// Credenciais e tópicos ficam em include/secrets.h (fora do git).
// Copie include/secrets.h.example para include/secrets.h e edite.
#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "Crie include/secrets.h a partir de include/secrets.h.example"
#endif

#define MQTT_TOPIC_BRUTOS       TOPIC_PREFIX "/dados_brutos"
#define MQTT_TOPIC_CALIBRACAO   TOPIC_PREFIX "/calibracao"
#define MQTT_BUFFER_SIZE        8192   // cabe o JSON de calibração
#define ARQUIVO_CALIBRACAO      "/calibracoes.json"

#ifndef SCAN_INTERVALO_MS
#define SCAN_INTERVALO_MS       10000
#endif
#define MQTT_RETRY_MS           5000
#define MAX_REDES               40

// ─── Estruturas ────────────────────────────────────────────────────────────────
struct DadosRede {
  char mac[13];
  int  rssi;
};

struct PacoteRedes {
  DadosRede redes[MAX_REDES];
  uint8_t   quantidade;
};

// ─── Globais ───────────────────────────────────────────────────────────────────
WiFiClient    espClient;
PubSubClient  mqttClient(espClient);
QueueHandle_t filaPacotes;

// ─── Utilitários de conexão ────────────────────────────────────────────────────
void conectarWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] Conectando");
  while (WiFi.status() != WL_CONNECTED) {
    vTaskDelay(pdMS_TO_TICKS(500));
    Serial.print(".");
  }
  Serial.printf("\n[WiFi] Conectado! IP: %s  RSSI: %d dBm\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
}

void reconectarMQTT() {
  while (!mqttClient.connected()) {
    char clientId[32];
    snprintf(clientId, sizeof(clientId), "ESP32_Radar_%08X", (uint32_t)esp_random());
    Serial.printf("[MQTT] Conectando como %s...\n", clientId);
    if (mqttClient.connect(clientId)) {
      Serial.println("[MQTT] Conectado ao broker!");
    } else {
      Serial.printf("[MQTT] Falha (cod %d). Nova tentativa em %ds...\n",
                    mqttClient.state(), MQTT_RETRY_MS / 1000);
      vTaskDelay(pdMS_TO_TICKS(MQTT_RETRY_MS));
    }
  }
}

// ─── Publica calibração no boot ────────────────────────────────────────────────
// Lê o arquivo JSON inteiro da flash e manda de uma vez para o Python salvar.
// O Python assina o tópico com retain=false, então só precisa estar online
// quando o ESP32 boota — mas como usamos retained=true no publish, ele
// receberá mesmo que conecte depois.
void publicarCalibracao() {
  if (!LittleFS.exists(ARQUIVO_CALIBRACAO)) {
    Serial.println("[Cal] Arquivo de calibracao nao encontrado na flash. Pulando.");
    return;
  }

  File f = LittleFS.open(ARQUIVO_CALIBRACAO, "r");
  if (!f) {
    Serial.println("[Cal] Erro ao abrir arquivo de calibracao.");
    return;
  }

  size_t tamanho = f.size();
  if (tamanho == 0 || tamanho >= MQTT_BUFFER_SIZE) {
    Serial.printf("[Cal] Tamanho invalido: %d bytes. Pulando.\n", tamanho);
    f.close();
    return;
  }

  // Lê tudo em um buffer estático (evita heap)
  static char bufCal[MQTT_BUFFER_SIZE];
  size_t lido = f.readBytes(bufCal, tamanho);
  bufCal[lido] = '\0';
  f.close();

  // retained = true → Python recebe mesmo se conectar depois do boot
  if (mqttClient.publish(MQTT_TOPIC_CALIBRACAO, bufCal, /*retained=*/true)) {
    Serial.printf("[Cal] Calibracao publicada: %d bytes → %s\n",
                  lido, MQTT_TOPIC_CALIBRACAO);
  } else {
    Serial.println("[Cal] Falha ao publicar calibracao (verifique MQTT_BUFFER_SIZE).");
  }
}

// ─── Core 0: Escaneamento ──────────────────────────────────────────────────────
void taskEscaneamento(void *pvParameters) {
  while (true) {
    Serial.println("[Scan] Iniciando varredura...");

    int encontradas = WiFi.scanNetworks(false, false);

    if (encontradas > 0) {
      PacoteRedes pacote;
      pacote.quantidade = (uint8_t)min(encontradas, MAX_REDES);

      for (int i = 0; i < pacote.quantidade; i++) {
        String mac = WiFi.BSSIDstr(i);
        mac.replace(":", "");
        mac.toUpperCase();
        strncpy(pacote.redes[i].mac, mac.c_str(), sizeof(pacote.redes[i].mac));
        pacote.redes[i].rssi = WiFi.RSSI(i);
      }
      WiFi.scanDelete();

      Serial.printf("[Scan] %d redes capturadas.\n", pacote.quantidade);

      if (xQueueSend(filaPacotes, &pacote, 0) != pdPASS) {
        Serial.println("[Scan] Fila cheia — ciclo descartado.");
      }
    } else {
      WiFi.scanDelete();
      Serial.println("[Scan] Nenhuma rede encontrada.");
    }

    vTaskDelay(pdMS_TO_TICKS(SCAN_INTERVALO_MS));
  }
}

// ─── Core 1: Publicação MQTT ───────────────────────────────────────────────────
void taskMQTT(void *pvParameters) {
  PacoteRedes pacote;
  static char jsonBuffer[MQTT_BUFFER_SIZE];

  // Garante conexão e publica calibração uma única vez no boot
  if (WiFi.status() != WL_CONNECTED) conectarWiFi();
  reconectarMQTT();
  publicarCalibracao();   // ← publicação única no boot

  while (true) {
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[MQTT] Wi-Fi perdido. Reconectando...");
      conectarWiFi();
    }
    if (!mqttClient.connected()) reconectarMQTT();
    mqttClient.loop();

    if (xQueueReceive(filaPacotes, &pacote, pdMS_TO_TICKS(100)) != pdPASS) {
      continue;
    }

    // Monta JSON com os dados brutos do scan
    int offset = snprintf(jsonBuffer, sizeof(jsonBuffer), "{");
    for (int i = 0; i < pacote.quantidade; i++) {
      bool ultima = (i == pacote.quantidade - 1);
      offset += snprintf(jsonBuffer + offset, sizeof(jsonBuffer) - offset,
                         "\"%s\":%d%s",
                         pacote.redes[i].mac,
                         pacote.redes[i].rssi,
                         ultima ? "" : ",");
      if (offset >= (int)sizeof(jsonBuffer) - 2) {
        Serial.println("[MQTT] Buffer cheio — payload truncado.");
        break;
      }
    }
    snprintf(jsonBuffer + offset, sizeof(jsonBuffer) - offset, "}");

    if (mqttClient.publish(MQTT_TOPIC_BRUTOS, jsonBuffer)) {
      Serial.printf("[MQTT] Brutos publicados: %d redes | %d bytes\n",
                    pacote.quantidade, (int)strlen(jsonBuffer));
    } else {
      Serial.println("[MQTT] Falha ao publicar dados brutos.");
    }
  }
}

// ─── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  Serial.println("\n======================================");
  Serial.println("     ESP32 — RADAR DE POSICIONAMENTO");
  Serial.println("======================================\n");

  // Monta filesystem (false = não formata, preserva calibracao.json)
  if (!LittleFS.begin(false)) {
    Serial.println("[FS] LittleFS nao montado — sem calibracao disponivel.");
  } else {
    Serial.println("[FS] LittleFS montado.");
  }

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  // WiFi é conectado dentro da taskMQTT antes da publicação da calibração

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setBufferSize(MQTT_BUFFER_SIZE);
  mqttClient.setKeepAlive(30);

  filaPacotes = xQueueCreate(3, sizeof(PacoteRedes));

  xTaskCreatePinnedToCore(taskEscaneamento, "Scan", 8192, NULL, 2, NULL, 0);
  xTaskCreatePinnedToCore(taskMQTT,        "MQTT", 8192, NULL, 1, NULL, 1);
}

void loop() {
  vTaskDelete(NULL);
}
