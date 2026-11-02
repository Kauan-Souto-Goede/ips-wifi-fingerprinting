import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os

try:
    from PIL import Image, ImageTk
except ImportError:
    print("Erro: A biblioteca Pillow não está instalada.")
    print("Execute 'pip install Pillow' no terminal para resolver.")
    exit(1)

class FloorPlanMapper:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerador de Coordenadas de Planta Baixa")
        self.root.geometry("1000x700")
        
        self.rooms = {}
        self.pins = {}  # Guarda as referências dos desenhos no canvas
        self.pending_room = None
        self.img_width = 0
        self.img_height = 0
        self.tk_image = None
        
        self._setup_ui()
        self._init_presets()

    def _setup_ui(self):
        # --- Barra de Ferramentas (Topo) ---
        toolbar = tk.Frame(self.root, padx=10, pady=10, bg="#f3f4f6")
        toolbar.pack(fill=tk.X)
        
        tk.Button(toolbar, text="📂 Carregar Planta", command=self.load_image, bg="white").pack(side=tk.LEFT, padx=5)
        
        self.room_entry = tk.Entry(toolbar, width=20)
        self.room_entry.pack(side=tk.LEFT, padx=(20, 5))
        self.room_entry.bind('<Return>', lambda e: self.add_room())
        
        tk.Button(toolbar, text="+ Adicionar", command=self.add_room, bg="white").pack(side=tk.LEFT, padx=5)
        
        self.instruction_label = tk.Label(toolbar, text="Carregue uma imagem para começar", fg="#185fa5", bg="#e6f1fb", padx=10, pady=2)
        self.instruction_label.pack(side=tk.LEFT, padx=20)

        # --- Área Principal ---
        main_frame = tk.Frame(self.root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Esquerda: Canvas (Planta)
        canvas_frame = tk.Frame(main_frame, bd=1, relief=tk.SOLID)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg="#ffffff", cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        
        # Direita: Painel Lateral
        right_panel = tk.Frame(main_frame, width=250, padx=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        
        tk.Label(right_panel, text="Cômodos:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        self.room_listbox = tk.Listbox(right_panel, height=12, selectmode=tk.SINGLE, activestyle="none")
        self.room_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.room_listbox.bind('<<ListboxSelect>>', self.on_listbox_select)
        
        tk.Button(right_panel, text="❌ Remover Selecionado", command=self.remove_room, bg="#fee2e2", fg="#991b1b").pack(fill=tk.X, pady=5)
        
        tk.Label(right_panel, text="JSON Output:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(15, 0))
        
        self.json_text = tk.Text(right_panel, height=12, width=30, font=("Courier", 9), bg="#f9fafb")
        self.json_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        tk.Button(right_panel, text="📋 Copiar JSON", command=self.copy_json).pack(fill=tk.X, pady=5)
        
        # NOVO BOTÃO: Salvar o arquivo no disco
        tk.Button(right_panel, text="💾 Salvar coordenadas.json", command=self.save_to_file, bg="#dcfce7", fg="#166534").pack(fill=tk.X, pady=5)

    def _init_presets(self):
        presets = ['Sala', 'Cozinha', 'Quarto Pais', 'Banheiro Pais', 'Quarto Visitas', 'Quarto Kauan', 'Banheiro', 'Sala de Jantar', 'Corredor']
        for p in presets:
            self.rooms[p] = None
        self.update_listbox()

    def load_image(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp")]
        )
        if not filepath:
            return
            
        img = Image.open(filepath)
        img.thumbnail((800, 600), Image.Resampling.LANCZOS)
        
        self.img_width, self.img_height = img.size
        self.tk_image = ImageTk.PhotoImage(img)
        
        self.canvas.config(width=self.img_width, height=self.img_height)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        
        for room in self.rooms:
            self.rooms[room] = None
        self.pins.clear()
        
        self.select_next_room()
        self.update_json()

    def add_room(self):
        room_name = self.room_entry.get().strip()
        if room_name and room_name not in self.rooms:
            self.rooms[room_name] = None
            self.room_entry.delete(0, tk.END)
            self.select_room(room_name)

    def remove_room(self):
        room_name = self.pending_room
        if not room_name:
            return
            
        if room_name in self.rooms:
            del self.rooms[room_name]
            self.clear_pin(room_name)
            self.select_next_room()
            self.update_json()

    def select_room(self, room_name):
        self.pending_room = room_name
        self.instruction_label.config(text=f"Clique na planta: '{room_name}'", fg="#185fa5", bg="#e6f1fb")
        self.update_listbox()

    def select_next_room(self):
        for room, pos in self.rooms.items():
            if pos is None:
                self.select_room(room)
                return
        self.pending_room = None
        self.instruction_label.config(text="Todos os cômodos mapeados!", fg="#3b6d11", bg="#eefaec")
        self.update_listbox()

    def on_listbox_select(self, event):
        selection = self.room_listbox.curselection()
        if not selection: 
            return
        raw_text = self.room_listbox.get(selection[0])
        room_name = raw_text.split(" ", 1)[1].replace(" ⬅", "").strip()
        self.select_room(room_name)

    def on_canvas_click(self, event):
        if not self.pending_room or not self.tk_image:
            return
            
        if event.x > self.img_width or event.y > self.img_height:
            return
            
        px = round((event.x / self.img_width) * 100)
        py = round((event.y / self.img_height) * 100)
        
        self.rooms[self.pending_room] = {'x': px, 'y': py}
        self.draw_pin(self.pending_room, event.x, event.y)
        self.select_next_room()
        self.update_json()

    def draw_pin(self, room_name, x, y):
        self.clear_pin(room_name)
        
        r = 5
        dot = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill="#e24b4a", outline="white", width=2)
        
        text_bg = self.canvas.create_rectangle(x-35, y-28, x+35, y-10, fill="#141414", outline="")
        text = self.canvas.create_text(x, y-19, text=room_name[:12], fill="white", font=("Arial", 8, "bold"))
        
        self.pins[room_name] = (dot, text_bg, text)

    def clear_pin(self, room_name):
        if room_name in self.pins:
            for item in self.pins[room_name]:
                self.canvas.delete(item)
            del self.pins[room_name]

    def update_listbox(self):
        self.room_listbox.delete(0, tk.END)
        for i, (room, pos) in enumerate(self.rooms.items()):
            prefix = "●" if pos is not None else "○"
            marker = " ⬅" if room == self.pending_room else ""
            
            self.room_listbox.insert(tk.END, f"{prefix} {room}{marker}")
            
            if room == self.pending_room:
                self.room_listbox.itemconfig(i, {'bg': '#e6f1fb', 'fg': '#185fa5'})
            elif pos is not None:
                self.room_listbox.itemconfig(i, {'fg': '#3b6d11'})
            else:
                self.room_listbox.itemconfig(i, {'fg': '#4b5563'})

    def update_json(self):
        placed = {k: v for k, v in self.rooms.items() if v is not None}
        self.json_text.delete(1.0, tk.END)
        if placed:
            self.json_text.insert(tk.END, json.dumps(placed, indent=2, ensure_ascii=False))

    def copy_json(self):
        json_data = self.json_text.get(1.0, tk.END).strip()
        if json_data:
            self.root.clipboard_clear()
            self.root.clipboard_append(json_data)
            messagebox.showinfo("Sucesso", "JSON copiado para a área de transferência!")

    # NOVA FUNÇÃO: Salvar o arquivo no disco
    def save_to_file(self):
        placed = {k: v for k, v in self.rooms.items() if v is not None}
        
        if not placed:
            messagebox.showwarning("Aviso", "Não há nenhum cômodo mapeado para salvar.")
            return
            
        # Descobre a pasta exata onde este script Python está rodando
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(script_dir, "coordenadas.json")
        
        try:
            # Escreve o arquivo JSON (ensure_ascii=False garante que acentos fiquem corretos)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(placed, f, indent=2, ensure_ascii=False)
                
            messagebox.showinfo("Sucesso", f"Arquivo salvo com sucesso!\n\nLocal: {filepath}")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível salvar o arquivo:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FloorPlanMapper(root)
    root.mainloop()