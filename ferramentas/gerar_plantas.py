"""Gera as plantas baixas (SVG, tema claro e escuro) e o arquivo de pontos.

Saídas em docs/planta/:
  andar1-claro.svg, andar1-escuro.svg, ... (uma por andar e tema)
  pontos.json   -> andares + coordenadas (x, y em % da imagem) de cada ponto

O motor (backend/motor.py) e o dashboard leem o mesmo pontos.json.
Os nomes dos pontos são os que se digita na calibração do ESP32
(minúsculas, sem acento).

Uso:  python ferramentas/gerar_plantas.py
"""
import json
import math
import os

CANVAS = 1000          # SVG quadrado, 1000 x 1000
MARGEM = 80
TOPO = 110             # espaço do título
PAREDE = 9

TEMAS = {
    "escuro": dict(fundo="#0b131d", piso="#122030", molhado="#10283a", externo="#0e1a26",
                   parede="#d4e6f7", porta="#5f84a6", janela="#00d4ff", movel="#35587a",
                   escada="#2a4562", texto="#9fc2de", titulo="#ffffff", vao="#1d3047"),
    "claro": dict(fundo="#ffffff", piso="#f6f8fb", molhado="#e8f1f8", externo="#f1f5ec",
                  parede="#2c3e50", porta="#8a9aa8", janela="#2e86de", movel="#b5c2cf",
                  escada="#9aa9b8", texto="#34495e", titulo="#1b2a38", vao="#d5dde5"),
}

# Coordenadas de cada andar no sistema do desenho original (pixels do rascunho).
# Cômodos: (rótulo, [vértices], (x, y) do rótulo, tipo). tipo: piso | molhado | externo
ANDARES = [
    {
        "id": 1, "nome": "Térreo", "titulo": "TÉRREO",
        "comodos": [
            ("", [(365, 205), (548, 205), (548, 113), (697, 113), (697, 279), (548, 279),
                  (548, 437), (365, 437)], None, "piso"),
            (("Oratório", 12), [(321, 313), (365, 313), (365, 400), (321, 400)], (343, 330), "piso"),
            (("Banheiro", 11), [(305, 220), (365, 220), (365, 273), (305, 273)], (335, 236), "molhado"),
            ("", [(270, 400), (362, 400), (362, 437), (614, 437), (614, 515), (270, 515)], None, "molhado"),
            ("Lavanderia", [(614, 437), (690, 437), (690, 515), (614, 515)], (652, 455), "molhado"),
        ],
        "rotulos": [("Entrada", (440, 228)), ("Sala de estar", (622, 262)),
                    ("Jantar", (420, 300)), ("Cozinha", (430, 505)), (("Churrasqueira", 13), (316, 425))],
        # portas: (p1 = dobradiça, p2, ponto para onde abre, dupla?)
        "portas": [((405, 205), (457, 205), (430, 260), False),
                   ((378, 437), (460, 437), (420, 480), True),
                   ((365, 232), (365, 262), (330, 247), False),
                   ((614, 505), (614, 475), (650, 490), False)],
        "aberturas": [((365, 318), (365, 395))],
        "janelas": [((592, 279), (644, 279)), ((548, 292), (548, 432))],
        "moveis": [("ret", (441, 320, 495, 414), 4), ("ret", (550, 128, 578, 195), 2),
                   ("linha", (562, 136, 562, 188)), ("ret", (607, 121, 657, 143), 8),
                   ("ret", (665, 162, 690, 222), 8), ("ret", (465, 443, 614, 470), 2),
                   ("ret", (520, 447, 548, 466), 3)],
        "escadas": [((508, 277, 546, 405), "v", "Escada")],
        "vaos": [],
        "pontos": [
            ("entrada", "Entrada", (455, 250), "sala terreo"),
            ("sala de estar", "Sala de estar", (612, 200), "sala terreo"),
            ("mesa de jantar", "Mesa de jantar", (468, 367), "sala terreo"),
            ("oratorio", "Oratório", (343, 365), "sala terreo"),
            ("banheiro terreo", "Banheiro (térreo)", (335, 256), "banheiro terreo"),
            ("cozinha", "Cozinha", (520, 492), "cozinha terreo"),
            ("churrasqueira", "Churrasqueira", (316, 465), "cozinha terreo"),
            ("lavanderia", "Lavanderia", (652, 485), "lavanderia"),
        ],
    },
    {
        "id": 2, "nome": "2º andar", "titulo": "2º ANDAR",
        "comodos": [
            (("Banheiro\ncozinha", 14), [(339, 131), (493, 131), (493, 205), (339, 205)], (416, 150), "molhado"),
            ("Cozinha", [(339, 205), (493, 205), (493, 372), (339, 372)], (416, 255), "molhado"),
            (("Banheiro\nvó", 14), [(493, 7), (575, 7), (575, 205), (493, 205)], (534, 60), "molhado"),
            ("Quarto vó", [(575, 7), (735, 7), (735, 205), (575, 205)], (655, 60), "piso"),
            ("", [(493, 205), (735, 205), (735, 472), (339, 472), (339, 372), (493, 372)], None, "piso"),
            ("Quarto vô", [(339, 472), (607, 472), (607, 590), (339, 590)], (473, 500), "piso"),
            ("Banheiro vô", [(607, 472), (735, 472), (735, 590), (607, 590)], (671, 500), "molhado"),
        ],
        "rotulos": [("Ante sala", (425, 395)), (("Corredor", 12), (525, 360)), ("Corredor", (640, 228)),
                    ("Corredor", (646, 450))],
        "portas": [((441, 205), (478, 205), (460, 240), False),
                   ((493, 212), (493, 250), (530, 230), False),
                   ((575, 122), (575, 178), (610, 150), False),
                   ((585, 205), (633, 205), (610, 160), False),
                   ((500, 472), (560, 472), (530, 520), False),
                   ((607, 482), (607, 522), (650, 500), False)],
        "aberturas": [],
        "janelas": [],
        "moveis": [],
        "escadas": [((655, 246, 735, 420), "v", "Escada")],
        "vaos": [((557, 246, 655, 420), "Vão")],
        "pontos": [
            ("banheiro cozinha", "Banheiro da cozinha", (416, 172), "banheiro cozinha"),
            ("cozinha de cima", "Cozinha (2º andar)", (416, 300), "cozinha 2 andar"),
            ("corredor", "Corredor", (525, 310), "circulacao 2 andar"),
            ("ante sala", "Ante sala", (425, 425), "circulacao 2 andar"),
            ("banheiro da vo", "Banheiro da vó", (534, 110), "banheiro da vo"),
            ("quarto da vo", "Quarto da vó", (655, 110), "quarto da vo"),
            ("quarto do vo", "Quarto do vô", (450, 540), "quarto do vo"),
            ("banheiro do vo", "Banheiro do vô", (671, 540), "banheiro do vo"),
        ],
    },
    {
        "id": 3, "nome": "3º andar", "titulo": "3º ANDAR",
        "comodos": [
            ("Sacada", [(568, 145), (768, 145), (768, 227), (568, 227)], (668, 166), "externo"),
            ("Salão de festas", [(434, 227), (681, 227), (681, 463), (434, 463)], (557, 300), "piso"),
        ],
        "rotulos": [],
        "portas": [((598, 227), (662, 227), (630, 190), True)],
        "aberturas": [((681, 300), (681, 392))],
        "janelas": [],
        "moveis": [],
        "escadas": [((681, 227, 748, 397), "v", "Escada")],
        "vaos": [],
        "pontos": [
            ("salao de festas", "Salão de festas", (557, 345), "salao de festas"),
            ("sacada", "Sacada", (668, 196), "sacada"),
        ],
    },
]


def transformacao(andar):
    xs, ys = [], []
    for _, pts, _, _ in andar["comodos"]:
        xs += [p[0] for p in pts]
        ys += [p[1] for p in pts]
    for (x1, y1, x2, y2), *_ in andar["escadas"]:
        xs += [x1, x2]
        ys += [y1, y2]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    largura, altura = CANVAS - 2 * MARGEM, CANVAS - TOPO - MARGEM
    s = min(largura / (x1 - x0), altura / (y1 - y0))
    ox = MARGEM + (largura - s * (x1 - x0)) / 2 - s * x0
    oy = TOPO + (altura - s * (y1 - y0)) / 2 - s * y0
    return lambda x, y: (round(ox + s * x, 1), round(oy + s * y, 1)), s


def svg_andar(andar, t):
    T, s = transformacao(andar)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS} {CANVAS}" '
           f'width="{CANVAS}" height="{CANVAS}" font-family="Segoe UI, Helvetica, Arial, sans-serif">',
           f'<rect width="{CANVAS}" height="{CANVAS}" fill="{t["fundo"]}"/>']

    def poly(pts, **attrs):
        d = " ".join(f"{a},{b}" for a, b in (T(*p) for p in pts))
        extra = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
        return f'<polygon points="{d}" {extra}/>'

    def linha(p1, p2, cor, w, extra=""):
        (a, b), (c, d) = T(*p1), T(*p2)
        return f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" stroke="{cor}" stroke-width="{w}" {extra}/>'

    # Pisos
    for _, pts, _, tipo in andar["comodos"]:
        out.append(poly(pts, fill=t[tipo]))
    # Vãos (abertura entre andares): hachura em X
    for (x1, y1, x2, y2), _ in andar["vaos"]:
        out.append(poly([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], fill=t["fundo"]))
        out.append(linha((x1, y1), (x2, y2), t["vao"], 2))
        out.append(linha((x2, y1), (x1, y2), t["vao"], 2))
    # Escadas: degraus
    for (x1, y1, x2, y2), _, _ in andar["escadas"]:
        out.append(poly([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], fill=t["piso"],
                        stroke=t["escada"], stroke_width=2))
        n = max(6, int((y2 - y1) / 11))
        for i in range(1, n):
            y = y1 + (y2 - y1) * i / n
            out.append(linha((x1, y), (x2, y), t["escada"], 1.5))
        xm = (x1 + x2) / 2
        (a, b), (c, d) = T(xm, y2 - 8), T(xm, y1 + 10)
        out.append(f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" stroke="{t["escada"]}" stroke-width="2.5"/>')
        out.append(f'<polygon points="{c - 7},{d + 12} {c + 7},{d + 12} {c},{d}" fill="{t["escada"]}"/>')
    # Móveis
    for m in andar["moveis"]:
        if m[0] == "ret":
            (x1, y1, x2, y2), r = m[1], m[2]
            (a, b), (c, d) = T(x1, y1), T(x2, y2)
            out.append(f'<rect x="{a}" y="{b}" width="{round(c - a, 1)}" height="{round(d - b, 1)}" '
                       f'rx="{r * s / 2:.1f}" fill="none" stroke="{t["movel"]}" stroke-width="2"/>')
        else:
            x1, y1, x2, y2 = m[1]
            out.append(linha((x1, y1), (x2, y2), t["movel"], 4, 'stroke-linecap="round"'))
    # Paredes
    for _, pts, _, tipo in andar["comodos"]:
        if tipo == "externo":
            out.append(poly(pts, fill="none", stroke=t["parede"], stroke_width=PAREDE * 0.45,
                            stroke_dasharray="10 6"))
        else:
            out.append(poly(pts, fill="none", stroke=t["parede"], stroke_width=PAREDE,
                            stroke_linejoin="miter"))
    # Janelas
    for p1, p2 in andar["janelas"]:
        out.append(linha(p1, p2, t["fundo"], PAREDE + 1))
        out.append(linha(p1, p2, t["janela"], 3))
    # Aberturas (passagem sem porta)
    for p1, p2 in andar["aberturas"]:
        out.append(linha(p1, p2, t["piso"], PAREDE + 2))
    # Portas: vão na parede + folha + arco
    for p1, p2, dentro, dupla in andar["portas"]:
        out.append(linha(p1, p2, t["piso"], PAREDE + 2))
        folhas = [(p1, p2)]
        if dupla:
            meio = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
            folhas = [(p1, meio), (p2, meio)]
        for h, f in folhas:
            (hx, hy), (fx, fy), (dx, dy) = T(*h), T(*f), T(*dentro)
            vx, vy = fx - hx, fy - hy
            L = math.hypot(vx, vy)
            nx, ny = -vy / L, vx / L
            if nx * (dx - hx) + ny * (dy - hy) < 0:
                nx, ny = -nx, -ny
            ex, ey = hx + nx * L, hy + ny * L
            sweep = 1 if (vx * ny - vy * nx) > 0 else 0
            out.append(f'<line x1="{hx}" y1="{hy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{t["porta"]}" stroke-width="2.5"/>')
            out.append(f'<path d="M{fx},{fy} A{L:.1f},{L:.1f} 0 0 {sweep} {ex:.1f},{ey:.1f}" fill="none" '
                       f'stroke="{t["porta"]}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    # Rótulos
    def rotulo(txt, p, tam=17):
        if isinstance(txt, tuple):
            txt, tam = txt
        a, b = T(*p)
        linhas = txt.upper().split("\n")
        y0 = b - (len(linhas) - 1) * tam * 0.6
        spans = "".join(f'<tspan x="{a}" y="{y0 + i * tam * 1.2:.1f}">{l}</tspan>' for i, l in enumerate(linhas))
        return (f'<text text-anchor="middle" dominant-baseline="middle" font-size="{tam}" '
                f'font-weight="600" letter-spacing="1.5" fill="{t["texto"]}">{spans}</text>')
    for nome, _, pos, _ in andar["comodos"]:
        if nome and pos:
            out.append(rotulo(nome, pos))
    for nome, pos in andar["rotulos"]:
        out.append(rotulo(nome, pos))
    for (x1, y1, x2, y2), nome in andar["vaos"]:
        out.append(rotulo(nome, ((x1 + x2) / 2, (y1 + y2) / 2 + 24), 14))
    for (x1, y1, x2, y2), _, nome in andar["escadas"]:
        a, b = T((x1 + x2) / 2, (y1 + y2) / 2)
        out.append(f'<text x="{a}" y="{b}" text-anchor="middle" dominant-baseline="middle" font-size="13" '
                   f'font-weight="600" letter-spacing="1.5" fill="{t["texto"]}" '
                   f'transform="rotate(-90 {a} {b})" paint-order="stroke" stroke="{t["piso"]}" '
                   f'stroke-width="6">{nome.upper()}</text>')
    out.append(f'<text x="{MARGEM}" y="66" font-size="30" font-weight="700" letter-spacing="4" '
               f'fill="{t["titulo"]}">{andar["titulo"]}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    destino = os.path.join(raiz, "docs", "planta")
    os.makedirs(destino, exist_ok=True)
    dados = {"andares": [], "pontos": {}}
    for andar in ANDARES:
        for nome_tema, tema in TEMAS.items():
            with open(os.path.join(destino, f"andar{andar['id']}-{nome_tema}.svg"), "w", encoding="utf-8") as f:
                f.write(svg_andar(andar, tema))
        dados["andares"].append({"id": andar["id"], "nome": andar["nome"], "planta": f"planta/andar{andar['id']}"})
        T, _ = transformacao(andar)
        for nome, rot, p, comodo in andar["pontos"]:
            x, y = T(*p)
            dados["pontos"][nome] = {"x": round(100 * x / CANVAS, 1), "y": round(100 * y / CANVAS, 1),
                                     "andar": andar["id"], "rotulo": rot, "comodo": comodo}
    with open(os.path.join(destino, "pontos.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    print(f"{len(ANDARES)} andares, {len(dados['pontos'])} pontos -> {destino}")


if __name__ == "__main__":
    main()
