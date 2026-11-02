# IPS — Posicionamento interno por Wi-Fi (fingerprinting)

Sistema que estima em qual ponto de uma residência um ESP32 está, comparando a
intensidade de sinal (RSSI) das redes Wi-Fi ao redor com assinaturas calibradas
de cada ponto. A posição aparece em tempo real sobre a planta baixa, numa página web.

Projeto da disciplina EEL7802 (Projeto em Eletrônica II, UFSC). Esta é a segunda
versão do repositório [Indoor-Positioning-System-IPS-](https://github.com/Kauan-Souto-Goede/Indoor-Positioning-System-IPS-),
com algoritmo revisado, ferramentas de teste em campo e configuração fora do código.

## Como funciona

```
ESP32 ──(scans e calibração, MQTT)──▶ broker HiveMQ ◀──▶ motor Python ──(posição)──▶ dashboard web
```

1. **Calibração (uma vez por ambiente):** o ESP32 fica em cada ponto, faz 5 varreduras e guarda
   a média do RSSI por rede (BSSID) que apareceu em pelo menos 3 delas, na flash (LittleFS).
2. **Operação:** o ESP32 varre o Wi-Fi a cada `SCAN_INTERVALO_MS` e publica `{MAC: RSSI}` por
   MQTT. No boot, ele também publica a calibração (mensagem *retained*).
3. **Motor Python (`backend/motor.py`):** compara o scan com cada assinatura e publica o
   ponto mais parecido, com coordenadas x/y da planta.
4. **Dashboard (`docs/`):** página estática que assina a posição por MQTT sobre WebSocket
   seguro e desenha o ponto na planta.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `firmware/` | Projeto PlatformIO com dois ambientes: `producao` (scan + MQTT) e `calibracao` (Serial) |
| `backend/` | `engine.py` (algoritmo), `motor.py`, `coletor.py`, `avaliar.py`, `simular.py`, `gerador_de_coordenadas.py`, testes |
| `docs/` | Dashboard (`index.html`, `indexv1.html`, `indexv2.html`) e `Image/Planta.png`; pronto para o GitHub Pages |

## Começando

### 1. Firmware

```bash
cd firmware
cp include/secrets.h.example include/secrets.h     # edite Wi-Fi e TOPIC_PREFIX
pio run -e calibracao -t upload                    # para calibrar
pio run -e producao  -t upload                     # para operar
```

`TOPIC_PREFIX` precisa ser **único e difícil de adivinhar**: o broker HiveMQ público é compartilhado
e sem autenticação.

### 2. Calibração

Abra o Monitor Serial (9600 baud) com o ambiente `calibracao` gravado. Comandos:
`C` calibra um ponto (digite o nome), `S` salva na flash, `P` imprime o JSON, `L` lista, `R` apaga tudo.
Fique parado em cada ponto durante a calibração. Depois de salvar, grave o ambiente `producao`: a
calibração continua na flash e é enviada ao motor a cada boot.

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
cp config.example.json config.json                 # mesmo topic_prefix do firmware
python gerador_de_coordenadas.py                   # marca cada ponto na planta -> coordenadas.json
python motor.py
```

### 4. Dashboard

Publique a pasta `docs/` no GitHub Pages (*Settings → Pages → Deploy from a branch → `/docs`*) e abra
`https://<usuario>.github.io/<repo>/indexv2.html?t=<seu topic_prefix>`. Sem `?t=`, a página usa o
prefixo `ips/demo`. Para testar localmente, abra `docs/indexv2.html` num navegador.

## Algoritmo (`backend/engine.py`)

- **Distância RMS sobre o mesmo conjunto de redes.** A versão 1 somava os quadrados só sobre as redes de cada
  ponto, então um ponto calibrado com poucas redes tinha menos termos na soma e ganhava mais vezes
  (há um teste que reproduz esse erro). Agora todos os pontos são comparados sobre a união das redes calibradas.
- **Redes ausentes valem −100 dBm.** Redes novas no scan que nenhum ponto conhece afetam todos os pontos igualmente
  e não mudam o ranking.
- **Média das últimas N varreduras** (`janela` em `config.json`, padrão 3). Reduz ruído, mas atrasa a resposta:
  com varredura a cada 10 s e janela 3, a posição pode levar ~30 s para acompanhar uma mudança. Use `janela: 1` para desligar.
- **Saída publicada:** `local`, `x`, `y`, `distancia_db`, `margem_db`, `segundo` e `confianca` ∈ [0, 1).
  `confianca = margem / (margem + distância)` é uma heurística (quão melhor o 1º ponto é que o 2º), não uma probabilidade.

## Medir a acurácia de verdade

```bash
cd backend
# fique em cada ponto e colete scans NOVOS (use SCAN_INTERVALO_MS 5000 no firmware durante a coleta)
python coletor.py --ponto "sala" --n 20
python coletor.py --ponto "quarto" --n 20
python avaliar.py "dados_campo/*.jsonl" --saida relatorio.md
```

`avaliar.py` compara a versão antiga e a atual sobre os mesmos dados e mostra acurácia por ponto, por cômodo
(adicione `"comodo": "..."` em cada ponto de `coordenadas.json`), pontos mais confundidos e erro de posição
(informe `--largura-m` e `--altura-m` para sair em metros). `python simular.py` gera uma **simulação** a partir
da calibração; ela serve para ajustar parâmetros e não substitui a medição em campo.

Testes automatizados do algoritmo: `cd backend && python -m pytest`.

## Limitações

- O broker público não tem autenticação; qualquer pessoa que descubra o prefixo pode ler ou publicar.
  Para uso além de demonstração, use um broker próprio com usuário e senha.
- O motor Python roda num computador; o dashboard no GitHub Pages só funciona com ele em execução.
- A calibração vale para o local e os roteadores existentes; se algum for movido ou trocado, recalibre.
- RSSI varia com pessoas, móveis e hora do dia; pontos com assinaturas parecidas podem ser confundidos.

## Licença

MIT. Veja `LICENSE`.
