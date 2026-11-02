#include <Arduino.h>
#include <WiFi.h>
#include <map>
#include <LittleFS.h> 

// ─── Estados da máquina ───────────────────────────────────────────────────────
enum Estado { AGUARDANDO_COMANDO, AGUARDANDO_COMODO };
Estado estadoAtual = AGUARDANDO_COMANDO;

// ─── Dados globais ────────────────────────────────────────────────────────────
std::map<String, std::map<String, int>> calibracoes;
String inputBuffer = "";

#define ARQUIVO_JSON "/calibracoes.json"

// ─── Funções auxiliares ───────────────────────────────────────────────────────
void imprimirMenu() {
  Serial.println("\n==========================================");
  Serial.println("        MODO DE CALIBRACAO ROBUSTA");
  Serial.println("==========================================");
  Serial.println("  [C] Calibrar um novo comodo");
  Serial.println("  [S] Salvar JSON no arquivo");
  Serial.println("  [P] Printar JSON salvo na Serial");
  Serial.println("  [L] Listar comodos calibrados");
  Serial.println("  [R] Resetar todas as calibracoes");
  Serial.println("==========================================");
  Serial.println("Aguardando comando...\n");
}

void realizarCalibracao(const String& comodo) {
  Serial.print("\n>> Calibrando: \"");
  Serial.print(comodo);
  Serial.println("\"");
  Serial.println("   Mantenha o ESP32 parado...\n");

  std::map<String, int> somaRSSI;
  std::map<String, int> contagem;
  const int AMOSTRAS = 5;

  for (int n = 1; n <= AMOSTRAS; n++) {
    Serial.print("   Amostra ");
    Serial.print(n);
    Serial.print("/");
    Serial.println(AMOSTRAS);

    int redes = WiFi.scanNetworks();
    for (int i = 0; i < redes; i++) {
      String mac = WiFi.BSSIDstr(i);
      mac.replace(":", "");
      somaRSSI[mac] += WiFi.RSSI(i);
      contagem[mac]++;
    }
    WiFi.scanDelete();
    delay(500);
  }

  if (somaRSSI.empty()) {
    Serial.println("   [ERRO] Nenhuma rede encontrada!");
    return;
  }

  std::map<String, int> redesFiltradas;
  for (auto const& par : somaRSSI) {
    if (contagem[par.first] >= 3) {
      redesFiltradas[par.first] = par.second / contagem[par.first];
    }
  }

  if (redesFiltradas.empty()) {
    Serial.println("   [AVISO] Nenhuma rede estavel encontrada. Tente novamente.");
    return;
  }

  calibracoes[comodo] = redesFiltradas;

  Serial.print("   [OK] Salvo em memoria: ");
  Serial.print(redesFiltradas.size());
  Serial.println(" redes estaveis.");
}

void listarComodos() {
  if (calibracoes.empty()) {
    Serial.println("\n   Nenhum comodo calibrado ainda.");
    return;
  }
  Serial.println("\n   Comodos calibrados:");
  for (auto const& c : calibracoes) {
    Serial.print("     - ");
    Serial.print(c.first);
    Serial.print("  (");
    Serial.print(c.second.size());
    Serial.println(" redes)");
  }
}

// ─── Gera string JSON e retorna ───────────────────────────────────────────────
String construirJSON() {
  if (calibracoes.empty()) return "";

  String json = "{\n  \"assinaturas\": {\n";

  int totalComodos = calibracoes.size();
  int indiceComodo = 0;

  for (auto const& comodo : calibracoes) {
    indiceComodo++;
    json += "    \"" + comodo.first + "\": {\n";

    int totalRedes = comodo.second.size();
    int indiceRede = 0;

    for (auto const& rede : comodo.second) {
      indiceRede++;
      json += "      \"" + rede.first + "\": " + String(rede.second);
      json += (indiceRede < totalRedes) ? ",\n" : "\n";
    }

    json += "    }";
    json += (indiceComodo < totalComodos) ? ",\n" : "\n";
  }

  json += "  }\n}";
  return json;
}

// ─── Salva JSON no LittleFS ───────────────────────────────────────────────────
void salvarJSON() {
  if (calibracoes.empty()) {
    Serial.println("\n   [AVISO] Nenhuma calibracao para salvar.");
    return;
  }

  String json = construirJSON();

  File arquivo = LittleFS.open(ARQUIVO_JSON, "w");
  if (!arquivo) {
    Serial.println("\n   [ERRO] Nao foi possivel abrir o arquivo para escrita!");
    return;
  }

  arquivo.print(json);
  arquivo.close();

  Serial.println("\n   [OK] JSON salvo em " ARQUIVO_JSON);
  Serial.print("   Tamanho: ");
  Serial.print(json.length());
  Serial.println(" bytes");
}

// ─── Lê e printa o arquivo salvo ──────────────────────────────────────────────
void printarArquivo() {
  if (!LittleFS.exists(ARQUIVO_JSON)) {
    Serial.println("\n   [AVISO] Arquivo nao encontrado. Use [S] para salvar primeiro.");
    return;
  }

  File arquivo = LittleFS.open(ARQUIVO_JSON, "r");
  if (!arquivo) {
    Serial.println("\n   [ERRO] Nao foi possivel abrir o arquivo para leitura!");
    return;
  }

  Serial.println("\n--- CONTEUDO DE " ARQUIVO_JSON " ---");
  while (arquivo.available()) {
    Serial.write(arquivo.read());
  }
  arquivo.close();
  Serial.println("\n------------------------------------\n");
}

// ─── Setup & Loop ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  // Inicializa o sistema de arquivos
  if (!LittleFS.begin(true)) {  // true = formata se falhar
    Serial.println("[ERRO FATAL] Falha ao montar LittleFS!");
    while (true) delay(1000);
  }
  Serial.println("[OK] LittleFS montado.");

  imprimirMenu();
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();

    // ── Lendo o nome do cômodo ────────────────────────────────────────────────
    if (estadoAtual == AGUARDANDO_COMODO) {
      if (c == '\n' || c == '\r') {
        inputBuffer.trim();
        if (inputBuffer.length() > 0) {
          realizarCalibracao(inputBuffer);
          inputBuffer = "";
          estadoAtual = AGUARDANDO_COMANDO;
          imprimirMenu();
        }
      } else {
        inputBuffer += c;
      }
      return;
    }

    // ── Processando comandos ──────────────────────────────────────────────────
    switch (c) {
      case 'c': case 'C':
        Serial.println("\nNome do comodo (Enter para confirmar):");
        Serial.print("> ");
        inputBuffer = "";
        estadoAtual = AGUARDANDO_COMODO;
        break;

      case 's': case 'S':
        salvarJSON();
        imprimirMenu();
        break;

      case 'p': case 'P':
        printarArquivo();
        imprimirMenu();
        break;

      case 'l': case 'L':
        listarComodos();
        imprimirMenu();
        break;

      case 'r': case 'R':
        calibracoes.clear();
        LittleFS.remove(ARQUIVO_JSON);
        Serial.println("\n   [OK] Calibracoes e arquivo apagados.");
        imprimirMenu();
        break;
    }
  }
}