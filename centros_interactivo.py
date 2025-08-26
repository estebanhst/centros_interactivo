# Implementado por Nelson Esteban Hernandez Soto durante el curso de Diseño Sísmico de Mampostería
# e-mail: nhernandez@unal.edu.co
# Universidad Nacional de Colombia - 2025

"""
La Calculadora de Centro de Rigidez es una aplicación interactiva desarrollada utilizando Tkinter
para el análisis y visualización de centros de rigidez en configuraciones estructurales. El software 
permite a los ingenieros estructurales modelar columnas y muros, calcular automáticamente los centros
de rigidez y visualizar la excentricidad respecto a un centro de masa dado por el usuario.
"""

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import math
import json
import os
import copy

# --- Constantes y Configuración ---
PIXELS_PER_METER = 40
GRID_COLOR = "#333333" 
RULER_BG_COLOR = "#1e1e1e"; RULER_FG_COLOR = "#a0a0a0"; CANVAS_BG_COLOR = "#282828"
COLUMN_COLOR = "#4a90e2"; WALL_COLOR = "#f5a623"
SELECTION_COLOR = "#e0e0e0"
CR_COLOR = "cyan"; CM_COLOR = "magenta"
GRID_MIN_PIXEL_SPACING = 50

# --- Clases del Modelo de Datos ---
class StructuralElement:
    def __init__(self, x, y): self.x, self.y = float(x), float(y)
    def get_center(self): return self.x, self.y
    def get_rigidity_x(self): raise NotImplementedError
    def get_rigidity_y(self): raise NotImplementedError
    def draw(self, canvas, app_instance): raise NotImplementedError
    def is_hit(self, model_x, model_y): raise NotImplementedError
    def move(self, dx, dy): self.x, self.y = self.x + dx, self.y + dy
class Column(StructuralElement):
    count = 0
    def __init__(self, x, y, width, height):
        super().__init__(x, y); Column.count += 1; self.id = Column.count
        self.width, self.height = float(width), float(height)
    def get_rigidity_x(self): return self.height * (self.width ** 3)
    def get_rigidity_y(self): return self.width * (self.height ** 3)
    def get_bounding_box(self):
        half_w, half_h = self.width / 2, self.height / 2
        return (self.x - half_w, self.y - half_h, self.x + half_w, self.y + half_h)
    def draw(self, canvas, app, is_selected=False):
        x0, y0, x1, y1 = self.get_bounding_box(); vx0, vy0, vx1, vy1 = *app.model_to_view(x0, y0), *app.model_to_view(x1, y1)
        outline_color, outline_width = (SELECTION_COLOR, 3) if is_selected else (COLUMN_COLOR, 1)
        canvas.create_rectangle(vx0, vy0, vx1, vy1, fill=COLUMN_COLOR, outline=outline_color, width=outline_width)
        cx, cy = app.model_to_view(self.x, self.y); canvas.create_text(cx, cy, text=f"C{self.id}", fill="white", font=("Arial", 8))
    def is_hit(self, model_x, model_y):
        x0, y0, x1, y1 = self.get_bounding_box(); return x0 <= model_x <= x1 and y0 <= model_y <= y1
class Wall(StructuralElement):
    count = 0
    def __init__(self, x, y, length, thickness, orientation):
        super().__init__(x, y); Wall.count += 1; self.id = Wall.count
        self.length, self.thickness, self.orientation = float(length), float(thickness), orientation
    def get_rigidity_y(self): return self.thickness * (self.length ** 3) if self.orientation == 'V' else self.length * (self.thickness ** 3)
    def get_rigidity_x(self): return self.thickness * (self.length ** 3) if self.orientation == 'H' else self.length * (self.thickness ** 3)
    def get_bounding_box(self):
        if self.orientation == 'V':
            half_t, half_l = self.thickness / 2, self.length / 2
            return (self.x - half_t, self.y - half_l, self.x + half_t, self.y + half_l)
        else:
            half_l, half_t = self.length / 2, self.thickness / 2
            return (self.x - half_l, self.y - half_t, self.x + half_l, self.y + half_t)
    def draw(self, canvas, app, is_selected=False):
        x0, y0, x1, y1 = self.get_bounding_box(); vx0, vy0, vx1, vy1 = *app.model_to_view(x0, y0), *app.model_to_view(x1, y1)
        outline_color, outline_width = (SELECTION_COLOR, 3) if is_selected else (WALL_COLOR, 1)
        canvas.create_rectangle(vx0, vy0, vx1, vy1, fill=WALL_COLOR, outline=outline_color, width=outline_width)
        cx, cy = app.model_to_view(self.x, self.y); canvas.create_text(cx, cy, text=f"M{self.id}", fill="black", font=("Arial", 8))
    def is_hit(self, model_x, model_y):
        x0, y0, x1, y1 = self.get_bounding_box(); return x0 <= model_x <= x1 and y0 <= model_y <= y1

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.elements = []; self.center_of_mass, self.center_of_rigidity = (0.0, 0.0), None
        self.zoom, self.pan_offset_x, self.pan_offset_y = 1.0, 0, 0
        self.selected_element, self.drag_start_pos, self.pan_start_pos = None, None, None
        self.current_filepath = None
        self.undo_stack = []; self.undo_limit = 20
        self.move_step = tk.DoubleVar(value=0.1)
        self.create_widgets(); self.bind_events()
        self.update_window_title(); self.update_calculations(); self.fit_to_view()

    def create_widgets(self):
        menubar = tk.Menu(self); self.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0); menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(label="Nuevo", command=self.clear_configuration, accelerator="Ctrl+N")
        file_menu.add_command(label="Abrir...", command=self.load_configuration, accelerator="Ctrl+O")
        file_menu.add_separator(); file_menu.add_command(label="Guardar", command=self.save_configuration, accelerator="Ctrl+S")
        file_menu.add_command(label="Guardar como...", command=self.save_configuration_as, accelerator="Ctrl+Shift+S")
        main_frame = ttk.Frame(self); main_frame.pack(fill=tk.BOTH, expand=True)
        control_panel = ttk.Frame(main_frame, width=250); control_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10); control_panel.pack_propagate(False)
        self.canvas = tk.Canvas(main_frame, bg=CANVAS_BG_COLOR); self.canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        ttk.Label(control_panel, text="Controles", font=("Arial", 16, "bold")).pack(pady=10)
        ttk.Button(control_panel, text="Añadir Columna", command=self.add_column).pack(fill=tk.X, pady=5)
        ttk.Button(control_panel, text="Añadir Muro", command=self.add_wall).pack(fill=tk.X, pady=5)
        ttk.Button(control_panel, text="Ajustar Vista", command=self.fit_to_view).pack(fill=tk.X, pady=5)
        ttk.Button(control_panel, text="Deshacer", command=self.undo_last_action).pack(fill=tk.X, pady=5)
        ttk.Separator(control_panel, orient='horizontal').pack(fill='x', pady=15)
        move_frame = ttk.LabelFrame(control_panel, text="Movimiento Preciso"); move_frame.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(move_frame, text="Paso (m):").pack(side=tk.LEFT, padx=5); ttk.Entry(move_frame, textvariable=self.move_step, width=8).pack(side=tk.LEFT, padx=5)
        cm_frame = ttk.LabelFrame(control_panel, text="Centro de Masa (m)"); cm_frame.pack(fill=tk.X, pady=5)
        self.cm_x_var = tk.StringVar(value=str(self.center_of_mass[0])); self.cm_y_var = tk.StringVar(value=str(self.center_of_mass[1]))
        ttk.Label(cm_frame, text="X:").grid(row=0, column=0, padx=5, pady=2); ttk.Entry(cm_frame, textvariable=self.cm_x_var, width=8).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(cm_frame, text="Y:").grid(row=1, column=0, padx=5, pady=2); ttk.Entry(cm_frame, textvariable=self.cm_y_var, width=8).grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(cm_frame, text="Actualizar", command=self.update_cm).grid(row=2, columnspan=2, pady=5)
        cr_frame = ttk.LabelFrame(control_panel, text="Centro de Rigidez (m)"); cr_frame.pack(fill=tk.X, pady=10)
        self.cr_x_label = ttk.Label(cr_frame, text="X: N/A"); self.cr_x_label.pack(anchor='w', padx=5)
        self.cr_y_label = ttk.Label(cr_frame, text="Y: N/A"); self.cr_y_label.pack(anchor='w', padx=5)
        ex_frame = ttk.LabelFrame(control_panel, text="Excentricidad (m)"); ex_frame.pack(fill=tk.X, pady=10)
        self.ex_label = ttk.Label(ex_frame, text="ex: N/A"); self.ex_label.pack(anchor='w', padx=5)
        self.ey_label = ttk.Label(ex_frame, text="ey: N/A"); self.ey_label.pack(anchor='w', padx=5)
        self.inspector_frame = ttk.LabelFrame(control_panel, text="Inspector de Elemento"); self.inspector_frame.pack(fill=tk.X, pady=10)
        self.inspector_labels = {}
        for field in ["Tipo", "ID", "X", "Y", "Dim 1", "Dim 2", "Orientación"]:
            label_widget = ttk.Label(self.inspector_frame, text=f"{field}:"); label_widget.pack(anchor='w', padx=5); self.inspector_labels[field.lower().replace(" ", "_")] = label_widget
        self._update_inspector_panel()

    def bind_events(self):
        self.bind_all("<Control-n>", lambda e: self.clear_configuration()); self.bind_all("<Control-o>", lambda e: self.load_configuration())
        self.bind_all("<Control-s>", lambda e: self.save_configuration()); self.bind_all("<Control-Shift-S>", lambda e: self.save_configuration_as())
        self.bind_all("<Control-z>", lambda e: self.undo_last_action())
        for key in ["<Up>", "<Down>", "<Left>", "<Right>"]: self.bind_all(key, self._move_with_keys)
        self.canvas.bind("<Configure>", self.redraw_canvas); self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start); self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down); self.canvas.bind("<B1-Motion>", self.on_mouse_move); self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<ButtonPress-3>", self.show_context_menu)

    def _save_state_for_undo(self):
        state = {'elements': copy.deepcopy(self.elements), 'center_of_mass': copy.deepcopy(self.center_of_mass), 'column_count': Column.count, 'wall_count': Wall.count}
        self.undo_stack.append(state)
        if len(self.undo_stack) > self.undo_limit: self.undo_stack.pop(0)

    def undo_last_action(self):
        if not self.undo_stack: return
        state = self.undo_stack.pop(); self.elements = state['elements']; self.center_of_mass = state['center_of_mass']
        Column.count = state['column_count']; Wall.count = state['wall_count']
        self.cm_x_var.set(str(self.center_of_mass[0])); self.cm_y_var.set(str(self.center_of_mass[1]))
        self.selected_element = None; self._update_inspector_panel(); self.update_and_redraw()

    def _update_inspector_panel(self):
        elem = self.selected_element
        if elem:
            self.inspector_labels['tipo'].config(text=f"Tipo: {elem.__class__.__name__}"); self.inspector_labels['id'].config(text=f"ID: {elem.id}")
            self.inspector_labels['x'].config(text=f"X: {elem.x:.3f}"); self.inspector_labels['y'].config(text=f"Y: {elem.y:.3f}")
            if isinstance(elem, Column):
                self.inspector_labels['dim_1'].config(text=f"Ancho (X): {elem.width:.3f}"); self.inspector_labels['dim_2'].config(text=f"Alto (Y): {elem.height:.3f}")
                self.inspector_labels['orientación'].config(text="Orientación: N/A")
            elif isinstance(elem, Wall):
                self.inspector_labels['dim_1'].config(text=f"Longitud: {elem.length:.3f}"); self.inspector_labels['dim_2'].config(text=f"Espesor: {elem.thickness:.3f}")
                self.inspector_labels['orientación'].config(text=f"Orientación: {elem.orientation}")
        else:
            for key, label in self.inspector_labels.items(): label.config(text=f"{key.replace('_', ' ').capitalize()}: N/A")

    def _move_with_keys(self, event):
        if not self.selected_element: return
        try: step = self.move_step.get()
        except tk.TclError: return
        dx, dy = 0, 0
        if event.keysym == "Up": dy = step
        elif event.keysym == "Down": dy = -step
        elif event.keysym == "Left": dx = -step
        elif event.keysym == "Right": dx = step
        else: return
        self._save_state_for_undo(); self.selected_element.move(dx, dy); self._update_inspector_panel(); self.update_and_redraw()

    def add_element(self, element_class, properties):
        self._save_state_for_undo()
        try:
            new_element = element_class(**properties)
            self.elements.append(new_element); self.selected_element = new_element
            self._update_inspector_panel(); self.update_and_redraw()
        except (ValueError, TypeError): messagebox.showerror("Error", "Valores inválidos.")
    def add_column(self):
        dialog = ElementDialog(self, title="Añadir Columna");
        if dialog.result: self.add_element(Column, dialog.result)
    def add_wall(self):
        dialog = ElementDialog(self, title="Añadir Muro", is_wall=True);
        if dialog.result: self.add_element(Wall, dialog.result)
    def edit_element(self, element):
        self._save_state_for_undo()
        is_wall = isinstance(element, Wall)
        dialog = ElementDialog(self, title=f"Editar {'Muro' if is_wall else 'Columna'}", element=element, is_wall=is_wall)
        if dialog.result:
            for key, value in dialog.result.items(): setattr(element, key, value)
            self._update_inspector_panel(); self.update_and_redraw()
    def duplicate_element(self, element):
        is_wall = isinstance(element, Wall)
        dialog = ElementDialog(self, title=f"Duplicar {'Muro' if is_wall else 'Columna'}", element=element, is_wall=is_wall)
        if dialog.result: self.add_element(element.__class__, dialog.result)
    def delete_element(self, element):
        self._save_state_for_undo()
        if messagebox.askyesno("Confirmar", f"¿Seguro que quieres borrar el elemento?"):
            self.elements.remove(element)
            if self.selected_element == element: self.selected_element = None
            self._update_inspector_panel(); self.update_and_redraw()

    def on_zoom(self, event):
        factor = 1.1 if event.delta > 0 else 1 / 1.1; new_zoom = self.zoom * factor
        if 0.2 <= new_zoom <= 5.0:
            mx, my = self.view_to_model(event.x, event.y); self.zoom = new_zoom; vx, vy = self.model_to_view(mx, my)
            self.pan_offset_x -= (vx - event.x); self.pan_offset_y -= (vy - event.y); self.redraw_canvas()
    def on_pan_start(self, event): self.pan_start_pos = (event.x, event.y); self.canvas.config(cursor="fleur")
    def on_pan_drag(self, event):
        if self.pan_start_pos:
            dx, dy = event.x - self.pan_start_pos[0], event.y - self.pan_start_pos[1]
            self.pan_offset_x += dx; self.pan_offset_y += dy; self.pan_start_pos = (event.x, event.y); self.redraw_canvas()
    def on_mouse_down(self, event):
        mx, my = self.view_to_model(event.x, event.y)
        hit_element = next((elem for elem in reversed(self.elements) if elem.is_hit(mx, my)), None)
        if self.selected_element != hit_element:
             self.selected_element = hit_element; self.redraw_canvas(); self._update_inspector_panel()
        if hit_element: self.drag_start_pos = (mx, my); self._save_state_for_undo()
    def on_mouse_move(self, event):
        if self.selected_element and self.drag_start_pos:
            new_mx, new_my=self.view_to_model(event.x,event.y); dx,dy=new_mx-self.drag_start_pos[0], new_my-self.drag_start_pos[1]
            self.selected_element.move(dx, dy); self.drag_start_pos = (new_mx, new_my)
            self._update_inspector_panel(); self.update_and_redraw()
    def on_mouse_up(self, event): self.drag_start_pos, self.pan_start_pos = None, None; self.canvas.config(cursor="")
    def update_cm(self):
        self._save_state_for_undo()
        try:
            self.center_of_mass=(float(self.cm_x_var.get()), float(self.cm_y_var.get())); self.redraw_canvas()
            self.update_eccentricity()
        except ValueError: messagebox.showerror("Error", "Coordenadas del CM inválidas.")
    def clear_configuration(self): self.undo_stack=[]; self.elements=[]; Column.count=0; Wall.count=0; self.selected_element=None; self.center_of_mass=(0.0,0.0); self.cm_x_var.set("0.0"); self.cm_y_var.set("0.0"); self.current_filepath=None; self.update_window_title(); self._update_inspector_panel(); self.update_and_redraw()
    def save_configuration_as(self):
        filepath=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("Archivos JSON","*.json")],title="Guardar como...")
        if not filepath: return False
        data_to_save={"center_of_mass":self.center_of_mass,"elements":[]}
        for elem in self.elements: elem_data=elem.__dict__.copy();elem_data['type']=elem.__class__.__name__.lower();data_to_save["elements"].append(elem_data)
        try:
            with open(filepath,'w') as f: json.dump(data_to_save, f, indent=4)
            self.current_filepath=filepath; self.update_window_title(); return True
        except Exception as e: messagebox.showerror("Error al Guardar",f"No se pudo guardar:\n{e}"); return False
    def save_configuration(self):
        if not self.current_filepath: self.save_configuration_as()
        else:
            data_to_save={"center_of_mass":self.center_of_mass,"elements":[]}
            for elem in self.elements: elem_data=elem.__dict__.copy();elem_data['type']=elem.__class__.__name__.lower();data_to_save["elements"].append(elem_data)
            try:
                with open(self.current_filepath,'w') as f: json.dump(data_to_save,f,indent=4)
            except Exception as e: messagebox.showerror("Error al Guardar",f"No se pudo guardar:\n{e}")
    def load_configuration(self):
        self.undo_stack=[]
        filepath=filedialog.askopenfilename(filetypes=[("Archivos JSON","*.json")],title="Abrir configuración")
        if not filepath: return
        try:
            with open(filepath,'r') as f: data=json.load(f)
            self.clear_configuration()
            cm=data.get("center_of_mass",[0.0,0.0]); self.center_of_mass=tuple(cm)
            self.cm_x_var.set(str(cm[0])); self.cm_y_var.set(str(cm[1]))
            for elem_data in data.get("elements",[]):
                elem_type=elem_data.pop('type',None); elem_data.pop('id',None)
                if elem_type=='column': self.elements.append(Column(**elem_data))
                elif elem_type=='wall': self.elements.append(Wall(**elem_data))
            self.current_filepath=filepath; self.update_window_title()
            self.update_and_redraw(); self.fit_to_view()
        except Exception as e: messagebox.showerror("Error al cargar",f"Archivo inválido:\n{e}")
    def update_window_title(self):
        if self.current_filepath: self.title(f"Calculadora de CR - {os.path.basename(self.current_filepath)}")
        else: self.title("Calculadora de CR - [Sin Título]")
    def update_eccentricity(self):
        if self.center_of_mass and self.center_of_rigidity:
            cm_x,cm_y=self.center_of_mass; cr_x,cr_y=self.center_of_rigidity; ex=cr_x-cm_x; ey=cr_y-cm_y
            self.ex_label.config(text=f"ex: {ex:.3f}"); self.ey_label.config(text=f"ey: {ey:.3f}")
        else: self.ex_label.config(text="ex: N/A"); self.ey_label.config(text="ey: N/A")
    def get_canvas_center(self): return self.canvas.winfo_width()/2, self.canvas.winfo_height()/2
    def model_to_view(self, mx, my): cx,cy=self.get_canvas_center();scale=self.zoom*PIXELS_PER_METER; return cx+self.pan_offset_x+mx*scale, cy+self.pan_offset_y-my*scale
    def view_to_model(self, vx, vy): cx,cy=self.get_canvas_center();scale=self.zoom*PIXELS_PER_METER; return (vx-cx-self.pan_offset_x)/scale, -(vy-cy-self.pan_offset_y)/scale
    def redraw_canvas(self, event=None): self.canvas.delete("all"); self.draw_grid_and_rulers(); self.draw_elements(); self.draw_markers()
    def draw_grid_and_rulers(self):
        scale=self.zoom*PIXELS_PER_METER; potential_steps=[0.1,0.2,0.5,1,2,5,10,20,50,100]; model_step=1.0
        for step in potential_steps:
            if step*scale > GRID_MIN_PIXEL_SPACING: model_step=step; break
        vx_min,vy_min,vx_max,vy_max=0,0,self.canvas.winfo_width(),self.canvas.winfo_height()
        mx_min,my_max=self.view_to_model(vx_min,vy_min); mx_max,my_min=self.view_to_model(vx_max,vy_max)
        vx_origin,vy_origin=self.model_to_view(0,0); num_decimals=1 if model_step < 1 else 0
        start_x=math.floor(mx_min/model_step)*model_step
        for mx in [i*model_step for i in range(round(start_x/model_step), round(mx_max/model_step)+1)]:
            vx,_=self.model_to_view(mx,0); is_origin=abs(mx)<1e-9; color,width=("gray50",2) if is_origin else (GRID_COLOR,1)
            self.canvas.create_line(vx, vy_min, vx, vy_max, fill=color, width=width, tags="grid")
            self.canvas.create_text(vx, 15, text=f"{mx:.{num_decimals}f}", fill=RULER_FG_COLOR, font=("Arial",9))
            if not is_origin: self.canvas.create_text(vx, vy_origin+10, text=f"{mx:.{num_decimals}f}", fill=RULER_FG_COLOR, font=("Arial",8), anchor="n")
        start_y=math.floor(my_min/model_step)*model_step
        for my in [i*model_step for i in range(round(start_y/model_step), round(my_max/model_step)+1)]:
            _,vy=self.model_to_view(0,my); is_origin=abs(my)<1e-9; color,width=("gray50",2) if is_origin else (GRID_COLOR,1)
            self.canvas.create_line(vx_min, vy, vx_max, vy, fill=color, width=width, tags="grid")
            if not is_origin:
                self.canvas.create_text(20,vy, text=f"{my:.{num_decimals}f}", fill=RULER_FG_COLOR, font=("Arial",9))
                self.canvas.create_text(vx_origin-10,vy, text=f"{my:.{num_decimals}f}", fill=RULER_FG_COLOR, font=("Arial",8), anchor="e")
        self.canvas.create_rectangle(0,0,vx_max,30,fill=RULER_BG_COLOR,outline=""); self.canvas.create_rectangle(0,0,40,vy_max,fill=RULER_BG_COLOR,outline=""); self.canvas.tag_lower("grid")
    def draw_elements(self):
        for elem in self.elements: elem.draw(self.canvas, self, (elem==self.selected_element))
    def draw_markers(self):
        if self.center_of_rigidity:
            vx,vy=self.model_to_view(*self.center_of_rigidity); size=12
            self.canvas.create_line(vx-size,vy,vx+size,vy,fill=CR_COLOR,width=2); self.canvas.create_line(vx,vy-size,vx,vy+size,fill=CR_COLOR,width=2)
            self.canvas.create_text(vx+size+2,vy, text="CR", anchor="w", fill=CR_COLOR, font=("Arial",10,"bold"))
        if self.center_of_mass:
            vx,vy=self.model_to_view(*self.center_of_mass); size=10
            self.canvas.create_oval(vx-size,vy-size,vx+size,vy+size, outline=CM_COLOR, width=2)
            self.canvas.create_text(vx+size+2,vy, text="CM", anchor="w", fill=CM_COLOR, font=("Arial",10,"bold"))
    def update_calculations(self):
        if not self.elements: 
            self.center_of_rigidity=None;
            self.cr_x_label.config(text="X: N/A");
            self.cr_y_label.config(text="Y: N/A");
            self.update_eccentricity();
            return
        sum_kx,sum_ky=sum(e.get_rigidity_x() for e in self.elements), sum(e.get_rigidity_y() for e in self.elements)
        if sum_ky==0 or sum_kx==0:
            self.center_of_rigidity=None;
            self.cr_x_label.config(text="X: Inestable");
            self.cr_y_label.config(text="Y: Inestable");
            self.update_eccentricity(); 
            return
        sum_kxy,sum_kyx=sum(e.get_rigidity_y()*e.x for e in self.elements), sum(e.get_rigidity_x()*e.y for e in self.elements)
        self.center_of_rigidity=(sum_kxy/sum_ky, sum_kyx/sum_kx)
        self.cr_x_label.config(text=f"X: {self.center_of_rigidity[0]:.3f}"); self.cr_y_label.config(text=f"Y: {self.center_of_rigidity[1]:.3f}")
        self.update_eccentricity()
    def show_context_menu(self, event):
        mx,my=self.view_to_model(event.x,event.y)
        hit_element=next((elem for elem in reversed(self.elements) if elem.is_hit(mx,my)), None)
        if hit_element:
            if self.selected_element != hit_element:
                self.selected_element=hit_element; self.redraw_canvas(); self._update_inspector_panel()
            menu=tk.Menu(self,tearoff=0)
            menu.add_command(label="Editar", command=lambda: self.edit_element(hit_element))
            menu.add_command(label="Duplicar", command=lambda: self.duplicate_element(hit_element))
            menu.add_separator(); menu.add_command(label="Borrar", command=lambda: self.delete_element(hit_element))
            menu.post(event.x_root,event.y_root)
    def fit_to_view(self):
        if not self.elements: self.pan_offset_x,self.pan_offset_y,self.zoom=0,0,1.0; self.redraw_canvas(); return
        min_x=min(e.get_bounding_box()[0] for e in self.elements); min_y=min(e.get_bounding_box()[1] for e in self.elements)
        max_x=max(e.get_bounding_box()[2] for e in self.elements); max_y=max(e.get_bounding_box()[3] for e in self.elements)
        margin=max((max_x-min_x)*0.1, (max_y-min_y)*0.1, 5)
        min_x,min_y,max_x,max_y=min_x-margin,min_y-margin,max_x+margin,max_y+margin
        model_width,model_height=max_x-min_x,max_y-min_y
        if model_width==0 or model_height==0: return
        canvas_w,canvas_h=self.canvas.winfo_width(),self.canvas.winfo_height()
        self.zoom=min((canvas_w/model_width)/PIXELS_PER_METER, (canvas_h/model_height)/PIXELS_PER_METER, 5.0)
        model_cx,model_cy=(min_x+max_x)/2,(min_y+max_y)/2
        view_cx,view_cy=self.model_to_view(model_cx,model_cy); canvas_cx,canvas_cy=self.get_canvas_center()
        self.pan_offset_x-=(view_cx-canvas_cx); self.pan_offset_y-=(view_cy-canvas_cy); self.redraw_canvas()
    def update_and_redraw(self): self.update_calculations(); self.redraw_canvas()

class ElementDialog(simpledialog.Dialog):
    def __init__(self, parent, title, element=None, is_wall=False): self.element,self.is_wall=element,is_wall; super().__init__(parent,title)
    def body(self, master):
        self.entries={}; self.vars={}; fields=[("X","x"),("Y","y")]
        fields.extend([("Longitud","length"),("Espesor","thickness")] if self.is_wall else [("Ancho (X)","width"),("Alto (Y)","height")])
        for i,(label,key) in enumerate(fields):
            ttk.Label(master,text=f"{label}:").grid(row=i,column=0,sticky="w",padx=5,pady=2)
            default_value=""
            if self.element: default_value=str(getattr(self.element,key,""))
            var=tk.StringVar(value=default_value); self.vars[key]=var
            entry=ttk.Entry(master,textvariable=var); entry.grid(row=i,column=1,sticky="ew",padx=5,pady=2); self.entries[key]=entry
        if self.is_wall:
            ttk.Label(master,text="Orientación:").grid(row=len(fields),column=0,sticky="w",padx=5,pady=2)
            default_orient='V'
            if self.element: default_orient=getattr(self.element,'orientation','V')
            self.orientation_var=tk.StringVar(value=default_orient)
            combo=ttk.Combobox(master,textvariable=self.orientation_var,values=['V','H'],state="readonly"); combo.grid(row=len(fields),column=1,sticky="ew",padx=5,pady=2)
        return self.entries[fields[0][1]]
    def apply(self):
        self.result={}; 
        try:
            for key,var in self.vars.items(): self.result[key]=float(var.get())
            if self.is_wall: self.result["orientation"]=self.orientation_var.get()
        except ValueError: messagebox.showerror("Entrada inválida","Todos los campos deben ser números.",parent=self); self.result=None

if __name__ == "__main__":
    Column.count, Wall.count = 0, 0
    app = App()
    app.mainloop()