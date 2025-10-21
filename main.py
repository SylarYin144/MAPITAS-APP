#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib
from matplotlib.colors import SymLogNorm, ListedColormap
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os # Añadido para manejo de archivos
import traceback # Añadido para logging de errores

# FilterComponent ha sido eliminado.
FilterComponent = None # Mantener para evitar errores si alguna lógica residual lo verifica.

# evitar ventanas externas
matplotlib.use("Agg")

class MapTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)

        # Estado de la aplicación
        self.df_original = None
        self.df_filtered = None
        self.gdf_data = None
        self.fig_canvas = None
        self.filepath_var = tk.StringVar()

        self.state_col_var = tk.StringVar()
        self.value_col_var = tk.StringVar()
        self.agg_method_var = tk.StringVar(value="count")
        self.show_labels = tk.BooleanVar(value=True)
        self.invert_cmap = tk.BooleanVar(value=False)
        self.state_entries = {}
        self.cases_data = None
        self.zoom_region_var = tk.StringVar()

        self.MANUAL_STATE_DATA_OPTION = "(Usar Datos de Estado Manuales)"
        self.geojson_state_column_name = None

        self.create_widgets()

    def create_widgets(self):
        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill=tk.BOTH, expand=True)
        frm_left = ttk.Frame(paned); paned.add(frm_left, weight=1)

        ctrl_main = ttk.LabelFrame(frm_left, text="Configuración del Mapa")
        ctrl_main.pack(fill=tk.X, padx=5, pady=5)

        file_frame = ttk.Frame(ctrl_main)
        file_frame.pack(fill=tk.X, pady=5)
        ttk.Button(file_frame, text="Cargar GeoJSON", command=self.load_shapefile).pack(side=tk.LEFT, padx=5)

        # Botones para nuevas funcionalidades
        ttk.Button(file_frame, text="Exportar Datos (Excel)", command=self.export_to_excel).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Cargar Casos/Pob (Excel/CSV)", command=self.load_case_data_from_file).pack(side=tk.LEFT, padx=5)

        ttk.Entry(file_frame, textvariable=self.filepath_var, width=30, state="readonly").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        select_frame = ttk.Frame(ctrl_main)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Visualización:").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.visualization_var = tk.StringVar(value="Prevalencia")
        self.visualization_combo = ttk.Combobox(select_frame, textvariable=self.visualization_var, values=["Prevalencia", "Casos Totales", "Población"], state="readonly", width=15)
        self.visualization_combo.grid(row=3, column=1, padx=5, pady=2, sticky="w")

        select_frame.columnconfigure(1, weight=1)

        state_data_lf = ttk.LabelFrame(frm_left, text="Datos por Región")
        state_data_lf.pack(fill=tk.X, padx=5, pady=5)
        state_data_canvas_frame = ttk.Frame(state_data_lf); state_data_canvas_frame.pack(fill=tk.BOTH, expand=True)
        state_data_canvas = tk.Canvas(state_data_canvas_frame); state_data_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        state_data_scrollbar = ttk.Scrollbar(state_data_canvas_frame, orient=tk.VERTICAL, command=state_data_canvas.yview); state_data_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        state_data_canvas.configure(yscrollcommand=state_data_scrollbar.set)
        self.state_data_frame = ttk.Frame(state_data_canvas); state_data_canvas.create_window((0, 0), window=self.state_data_frame, anchor="nw")
        self.state_data_frame.bind("<Configure>", lambda e: state_data_canvas.configure(scrollregion=state_data_canvas.bbox("all")))

        ctrl_appearance = ttk.LabelFrame(frm_left, text="Apariencia del Mapa"); ctrl_appearance.pack(fill=tk.X, padx=5, pady=5)
        appearance_row1 = ttk.Frame(ctrl_appearance); appearance_row1.pack(fill=tk.X, pady=2)
        ttk.Label(appearance_row1, text="Paleta:").pack(side=tk.LEFT, padx=5)
        palettes = ["viridis","plasma","inferno","magma","cividis","turbo","Spectral","coolwarm","copper","winter","summer","autumn","spring","hot","bone"]
        self.cmb_palette = ttk.Combobox(appearance_row1, values=palettes, state="readonly", width=10); self.cmb_palette.pack(side=tk.LEFT, padx=5); self.cmb_palette.set("Spectral")
        ttk.Label(appearance_row1, text="N° colores:").pack(side=tk.LEFT, padx=5)
        self.ent_pal_n = ttk.Entry(appearance_row1, width=5); self.ent_pal_n.pack(side=tk.LEFT, padx=5); self.ent_pal_n.insert(0,"0")
        ttk.Checkbutton(appearance_row1, text="Invertir", variable=self.invert_cmap).pack(side=tk.LEFT, padx=5)
        appearance_row2 = ttk.Frame(ctrl_appearance); appearance_row2.pack(fill=tk.X, pady=2)
        ttk.Label(appearance_row2, text="Escala:").pack(side=tk.LEFT, padx=5)
        self.cmb_scale = ttk.Combobox(appearance_row2, values=["Regular","Logarítmica"], state="readonly", width=10); self.cmb_scale.pack(side=tk.LEFT, padx=5); self.cmb_scale.set("Logarítmica")
        ttk.Label(appearance_row2, text="Rango (min–max):").pack(side=tk.LEFT, padx=5)
        self.ent_vmin = ttk.Entry(appearance_row2, width=8); self.ent_vmin.pack(side=tk.LEFT, padx=5); self.ent_vmin.insert(0,"0")
        self.ent_vmax = ttk.Entry(appearance_row2, width=8); self.ent_vmax.pack(side=tk.LEFT, padx=5)
        appearance_row3 = ttk.Frame(ctrl_appearance); appearance_row3.pack(fill=tk.X, pady=2)
        ttk.Label(appearance_row3, text="N° Ticks CB:").pack(side=tk.LEFT, padx=5)
        self.ent_nt = ttk.Entry(appearance_row3,width=5); self.ent_nt.pack(side=tk.LEFT, padx=5); self.ent_nt.insert(0,"6")
        ttk.Label(appearance_row3, text="Valores CB (coma):").pack(side=tk.LEFT, padx=5)
        self.ent_vals = ttk.Entry(appearance_row3,width=15); self.ent_vals.pack(side=tk.LEFT, padx=5)
        appearance_row4 = ttk.Frame(ctrl_appearance); appearance_row4.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(appearance_row4, text="Mostrar etiquetas estados", variable=self.show_labels).pack(side=tk.LEFT, padx=5)
        ttk.Label(appearance_row4, text="DPI:").pack(side=tk.LEFT, padx=15)
        self.ent_dpi = ttk.Entry(appearance_row4,width=5); self.ent_dpi.pack(side=tk.LEFT, padx=5); self.ent_dpi.insert(0,"100")
        ttk.Label(appearance_row4, text="Grosor línea:").pack(side=tk.LEFT, padx=5)
        self.ent_lw = ttk.Entry(appearance_row4,width=5); self.ent_lw.pack(side=tk.LEFT, padx=5); self.ent_lw.insert(0,"1.0")
        appearance_row5 = ttk.Frame(ctrl_appearance); appearance_row5.pack(fill=tk.X, pady=2)
        ttk.Label(appearance_row5, text="Título:").pack(side=tk.LEFT, padx=5)
        self.ent_title = ttk.Entry(appearance_row5,width=20); self.ent_title.pack(side=tk.LEFT, padx=5); self.ent_title.insert(0,"Mapa de México")
        ttk.Label(appearance_row5, text="Color:").pack(side=tk.LEFT, padx=5)
        self.ent_tcol = ttk.Entry(appearance_row5,width=8); self.ent_tcol.pack(side=tk.LEFT, padx=5); self.ent_tcol.insert(0,"black")
        ttk.Label(appearance_row5, text="Tamaño:").pack(side=tk.LEFT, padx=5)
        self.ent_tsz = ttk.Entry(appearance_row5,width=5); self.ent_tsz.pack(side=tk.LEFT, padx=5); self.ent_tsz.insert(0,"14")
        appearance_row6 = ttk.Frame(ctrl_appearance); appearance_row6.pack(fill=tk.X, pady=2)
        ttk.Label(appearance_row6, text="Subtítulo:").pack(side=tk.LEFT, padx=5)
        self.ent_sub = ttk.Entry(appearance_row6,width=20); self.ent_sub.pack(side=tk.LEFT, padx=5); self.ent_sub.insert(0,"(Valor Agregado)")
        ttk.Label(appearance_row6, text="Color:").pack(side=tk.LEFT, padx=5)
        self.ent_scol = ttk.Entry(appearance_row6,width=8); self.ent_scol.pack(side=tk.LEFT, padx=5); self.ent_scol.insert(0,"gray")
        ttk.Label(appearance_row6, text="Tamaño:").pack(side=tk.LEFT, padx=5)
        self.ent_ssz = ttk.Entry(appearance_row6,width=5); self.ent_ssz.pack(side=tk.LEFT, padx=5); self.ent_ssz.insert(0,"10")
        appearance_row7 = ttk.Frame(ctrl_appearance); appearance_row7.pack(fill=tk.X, pady=2)
        ttk.Label(appearance_row7, text="Título CB:").pack(side=tk.LEFT, padx=5)
        self.ent_cbt = ttk.Entry(appearance_row7,width=20); self.ent_cbt.pack(side=tk.LEFT, padx=5); self.ent_cbt.insert(0,"Valor")
        ttk.Label(appearance_row7, text="Color:").pack(side=tk.LEFT, padx=5)
        self.ent_cbtcol = ttk.Entry(appearance_row7,width=8); self.ent_cbtcol.pack(side=tk.LEFT, padx=5); self.ent_cbtcol.insert(0,"black")
        ttk.Label(appearance_row7, text="Tamaño:").pack(side=tk.LEFT, padx=5)
        self.ent_cbtsz = ttk.Entry(appearance_row7,width=5); self.ent_cbtsz.pack(side=tk.LEFT, padx=5); self.ent_cbtsz.insert(0,"10")
        appearance_row8 = ttk.Frame(ctrl_appearance); appearance_row8.pack(fill=tk.X, pady=2)
        ttk.Label(appearance_row8, text="Etiquetas CB Color:").pack(side=tk.LEFT, padx=5)
        self.ent_cbkcol = ttk.Entry(appearance_row8,width=8); self.ent_cbkcol.pack(side=tk.LEFT, padx=5); self.ent_cbkcol.insert(0,"black")
        ttk.Label(appearance_row8, text="Tamaño:").pack(side=tk.LEFT, padx=5)
        self.ent_cbksz = ttk.Entry(appearance_row8,width=5); self.ent_cbksz.pack(side=tk.LEFT, padx=5); self.ent_cbksz.insert(0,"8")

        self.prevalence_var = tk.StringVar()
        ttk.Label(appearance_row8, text="Prevalencia:").pack(side=tk.LEFT, padx=15)
        ttk.Label(appearance_row8, textvariable=self.prevalence_var).pack(side=tk.LEFT, padx=5)

        appearance_row9 = ttk.Frame(ctrl_appearance); appearance_row9.pack(fill=tk.X, pady=2)
        ttk.Label(appearance_row9, text="Zoom a Región:").pack(side=tk.LEFT, padx=5)
        self.zoom_region_combo = ttk.Combobox(appearance_row9, textvariable=self.zoom_region_var, state="readonly", width=20)
        self.zoom_region_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(appearance_row9, text="Zoom", command=self.show_map).pack(side=tk.LEFT, padx=5)
        ttk.Button(appearance_row9, text="Restaurar", command=self.restore_zoom).pack(side=tk.LEFT, padx=5)

        action_frame = ttk.Frame(frm_left); action_frame.pack(fill=tk.X, padx=5, pady=10)
        ttk.Button(action_frame, text="Generar Mapa", command=self.show_map).pack(side=tk.LEFT, padx=10)
        ttk.Button(action_frame, text="Guardar Mapa", command=self.save_map).pack(side=tk.LEFT, padx=10)
        self.txt_out = tk.Text(frm_left, height=4); self.txt_out.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)
        frm_right = ttk.Frame(paned); paned.add(frm_right, weight=2)
        self.canvas_map = tk.Canvas(frm_right,bg="white"); self.canvas_map.pack(fill=tk.BOTH,expand=True)
        v2 = ttk.Scrollbar(frm_right,orient="vertical",command=self.canvas_map.yview); v2.pack(side=tk.RIGHT,fill=tk.Y)
        h2 = ttk.Scrollbar(frm_right,orient="horizontal",command=self.canvas_map.xview); h2.pack(side=tk.BOTTOM,fill=tk.X)
        self.canvas_map.configure(yscrollcommand=v2.set, xscrollcommand=h2.set)
        self.frm_map = ttk.Frame(self.canvas_map); self.canvas_map.create_window((0,0),window=self.frm_map,anchor="nw")
        self.frm_map.bind("<Configure>", lambda e: self.canvas_map.configure(scrollregion=self.canvas_map.bbox("all")))

    def export_to_excel(self):
        if not self.state_entries:
            messagebox.showerror("Error", "No hay datos para exportar.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            title="Guardar archivo de Excel"
        )
        if not filepath:
            return

        data = []
        for state_name, (pop_entry, case_entry) in self.state_entries.items():
            data.append({
                self.geojson_state_column_name: state_name,
                "Poblacion": pop_entry.get(),
                "Casos": case_entry.get()
            })

        df = pd.DataFrame(data)

        try:
            df.to_excel(filepath, index=False)
            messagebox.showinfo("Éxito", f"Archivo de Excel guardado en {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el archivo de Excel: {e}")

    def load_case_data_from_file(self):
        if self.gdf_data is None:
            messagebox.showerror("Error", "Cargue primero un archivo GeoJSON.")
            return

        filepath = filedialog.askopenfilename(
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")],
            title="Cargar archivo de datos (Casos/Población)"
        )
        if not filepath:
            return

        try:
            if filepath.endswith('.csv'):
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)

            required_cols = ["Poblacion", "Casos", self.geojson_state_column_name]
            if not all(col in df.columns for col in required_cols):
                messagebox.showerror("Error de Archivo", f"El archivo debe contener las columnas: {', '.join(required_cols)}")
                return

            for index, row in df.iterrows():
                state_name = row[self.geojson_state_column_name]
                population_value = row["Poblacion"]
                cases_value = row["Casos"]

                if state_name in self.state_entries:
                    pop_entry, case_entry = self.state_entries[state_name]
                    pop_entry.delete(0, tk.END)
                    pop_entry.insert(0, str(population_value))
                    case_entry.delete(0, tk.END)
                    case_entry.insert(0, str(cases_value))

            self.cases_data = df
            messagebox.showinfo("Éxito", "Datos de casos y población cargados correctamente.")

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el archivo: {e}")

    def restore_zoom(self):
        self.zoom_region_var.set("")
        self.show_map()

    def load_shapefile(self):
        path = filedialog.askopenfilename(title="GeoJSON", filetypes=[("GeoJSON","*.json"),("All","*.*")])
        if not path: return
        try:
            # UNIQUE COMMENT TO TEST OVERWRITE 123
            if hasattr(self, 'state_data_frame') and self.state_data_frame.winfo_exists():
                for widget in self.state_data_frame.winfo_children():
                    widget.destroy()
            if hasattr(self, 'state_entries'):
                self.state_entries.clear()
            self.geojson_state_column_name = None

            self.gdf_data = gpd.read_file(path)

            string_columns = [col for col in self.gdf_data.columns if self.gdf_data[col].dtype == 'object']

            if not string_columns:
                messagebox.showerror("Error GeoJSON", "No se encontraron columnas de texto en el GeoJSON para usar como nombres de región.")
                self.gdf_data = None
                return

            # Crear un diálogo para que el usuario elija la columna
            dialog = tk.Toplevel(self)
            dialog.title("Seleccionar Columna de Región")
            ttk.Label(dialog, text="Elige la columna que contiene los nombres de las regiones:").pack(padx=10, pady=10)

            col_var = tk.StringVar()
            col_combo = ttk.Combobox(dialog, textvariable=col_var, values=string_columns, state="readonly")
            col_combo.pack(padx=10, pady=5)
            col_combo.set(string_columns[0])

            def on_ok():
                self.geojson_state_column_name = col_var.get()
                dialog.destroy()

            ttk.Button(dialog, text="OK", command=on_ok).pack(pady=10)

            self.wait_window(dialog) # Esperar a que el usuario seleccione

            if not self.geojson_state_column_name: # Si el usuario cerró el diálogo
                self.gdf_data = None
                return

            # Añadir encabezados a la tabla
            ttk.Label(self.state_data_frame, text="Región", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, padx=5, pady=2, sticky="w")
            ttk.Label(self.state_data_frame, text="Población", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=1, padx=5, pady=2, sticky="w")
            ttk.Label(self.state_data_frame, text="Casos", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=2, padx=5, pady=2, sticky="w")

            for index, row_data in self.gdf_data.iterrows():
                state_name_from_geojson = row_data[self.geojson_state_column_name]

                if not isinstance(state_name_from_geojson, str):
                    state_name_from_geojson = str(state_name_from_geojson)

                lbl = ttk.Label(self.state_data_frame, text=state_name_from_geojson)
                lbl.grid(row=index + 1, column=0, padx=5, pady=2, sticky="w")

                pop_entry = ttk.Entry(self.state_data_frame, width=15)
                pop_entry.grid(row=index + 1, column=1, padx=5, pady=2, sticky="ew")

                case_entry = ttk.Entry(self.state_data_frame, width=15)
                case_entry.grid(row=index + 1, column=2, padx=5, pady=2, sticky="ew")

                pop_entry.insert(0, "0")
                case_entry.insert(0, "0")

                if hasattr(self, 'state_entries'):
                    self.state_entries[state_name_from_geojson] = (pop_entry, case_entry)

            # Actualizar el combobox de zoom
            region_names = sorted(list(self.state_entries.keys()))
            self.zoom_region_combo['values'] = region_names
            self.zoom_region_var.set("") # Limpiar selección anterior

            if hasattr(self, 'state_data_frame') and self.state_data_frame.winfo_exists():
                 self.state_data_frame.update_idletasks()

            self.txt_out.insert(tk.END, f"Shapefile: {os.path.basename(path)} (Columna Estado GeoJSON: {self.geojson_state_column_name})\n")
            messagebox.showinfo("Éxito", f"Cargado shapefile: {os.path.basename(path)}")

        except Exception as e:
            self.log(f"Error en load_shapefile: {e}", "ERROR")
            traceback.print_exc()
            messagebox.showerror("Error al cargar GeoJSON", f"Detalles: {str(e)}")
            self.gdf_data = None
            self.geojson_state_column_name = None
            if hasattr(self, 'state_data_frame') and self.state_data_frame.winfo_exists():
                for widget in self.state_data_frame.winfo_children():
                    widget.destroy()
            if hasattr(self, 'state_entries'):
                self.state_entries.clear()

    def show_map(self):
        fig = self.make_fig()
        if not fig: return
        if self.fig_canvas: self.fig_canvas.get_tk_widget().destroy()
        self.fig_canvas = FigureCanvasTkAgg(fig,master=self.frm_map); self.fig_canvas.draw(); self.fig_canvas.get_tk_widget().pack(fill=tk.BOTH,expand=True)
        self.canvas_map.config(scrollregion=self.canvas_map.bbox("all"))

    def make_fig(self):
        if not self.state_entries or self.gdf_data is None:
            messagebox.showwarning("Aviso", "Cargue un archivo GeoJSON y asegúrese de que haya datos de regiones.")
            return None

        # Construir DataFrame directamente desde las entradas de la UI
        data = []
        for state_name, (pop_entry, case_entry) in self.state_entries.items():
            try:
                poblacion = float(pop_entry.get())
            except ValueError:
                poblacion = 0.0
            try:
                casos = float(case_entry.get())
            except ValueError:
                casos = 0.0
            data.append({self.geojson_state_column_name: state_name, "Poblacion": poblacion, "Casos": casos})

        df_from_ui = pd.DataFrame(data)

        gdf = self.gdf_data.merge(df_from_ui, on=self.geojson_state_column_name, how="left")

        pal,ncol,inv,scale,dpi,lw,vmin,vmax_s,nt,vals = self.cmb_palette.get(),int(self.ent_pal_n.get()) if self.ent_pal_n.get().isdigit() else 0,self.invert_cmap.get(),self.cmb_scale.get(),int(self.ent_dpi.get()),float(self.ent_lw.get()),float(self.ent_vmin.get()),self.ent_vmax.get().strip(),int(self.ent_nt.get()),self.ent_vals.get().strip()
        vmax = float(vmax_s) if vmax_s else None
        title,tcol,tsz,subt,scol,ssz,cbt,cbtcol,cbtsz,cbkcol,cbksz = self.ent_title.get().strip(),self.ent_tcol.get().strip() or "black",float(self.ent_tsz.get()),self.ent_sub.get().strip(),self.ent_scol.get().strip() or "gray",float(self.ent_ssz.get()),self.ent_cbt.get().strip(),self.ent_cbtcol.get().strip() or "black",float(self.ent_cbtsz.get()),self.ent_cbkcol.get().strip() or "black",float(self.ent_cbksz.get())

        visualization = self.visualization_var.get()
        if visualization == "Prevalencia":
            col_to_plot = "Prevalencia"
            gdf["Poblacion"] = pd.to_numeric(gdf["Poblacion"], errors='coerce').fillna(0)
            gdf["Casos"] = pd.to_numeric(gdf["Casos"], errors='coerce').fillna(0)
            gdf[col_to_plot] = gdf.apply(lambda row: row['Casos'] / row['Poblacion'] if row['Poblacion'] > 0 else 0, axis=1)

        elif visualization == "Casos Totales":
            col_to_plot = "Casos"
            gdf[col_to_plot] = pd.to_numeric(gdf[col_to_plot], errors='coerce').fillna(0)

        elif visualization == "Población":
            col_to_plot = "Poblacion"
            gdf[col_to_plot] = pd.to_numeric(gdf[col_to_plot], errors='coerce').fillna(0)

        if vmax is None: vmax = gdf[col_to_plot].max() if not gdf[col_to_plot].empty else 1
        thresh = 0.1 if vmax > 10 else 0.01
        if scale=="Logarítmica": norm = SymLogNorm(linthresh=thresh, linscale=1, vmin=vmin, vmax=vmax)
        else: norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax)
        base = matplotlib.colormaps[pal]
        if ncol>0: colors = base(np.linspace(0,1,ncol)); cmap = ListedColormap(colors)
        else: cmap = base
        if inv: cmap = cmap.reversed()
        fig = Figure(figsize=(10,8), dpi=dpi); ax = fig.add_subplot(111)
        gdf.plot(column=col_to_plot, cmap=cmap, norm=norm, edgecolor="black", linewidth=lw, ax=ax, missing_kwds={'color': 'lightgrey', "hatch": "///", "label": "Sin datos"})

        # Lógica de Zoom
        zoom_region = self.zoom_region_var.get()
        if zoom_region:
            region_geom = gdf[gdf[self.geojson_state_column_name] == zoom_region]
            if not region_geom.empty:
                bounds = region_geom.total_bounds
                ax.set_xlim(bounds[0] - 0.1, bounds[2] + 0.1)
                ax.set_ylim(bounds[1] - 0.1, bounds[3] + 0.1)

        ax.set_axis_off()
        metric_display = "Datos Manuales"
        subtitle_display_state_col = self.geojson_state_column_name
        default_title = title if title else f"Mapa Coroplético - {metric_display}"
        default_subtitle = subt if subt else f"Agregado por {subtitle_display_state_col}"
        ax.set_title(default_title, color=tcol, fontsize=tsz, pad=20)
        ax.text(0.5, 0.96, default_subtitle, transform=ax.transAxes, ha='center', color=scol, fontsize=ssz)
        sm = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap); sm._A=[]
        if vals:
            try: ticks = [float(x) for x in vals.split(",")]
            except: ticks = np.linspace(vmin,vmax,nt)
        else: ticks = np.linspace(vmin,vmax,nt)
        cbar = fig.colorbar(sm, ax=ax, ticks=ticks)
        for spine in cbar.ax.spines.values(): spine.set_edgecolor(cbtcol); spine.set_linewidth(1)
        cbar.ax.tick_params(color=cbkcol, labelcolor=cbkcol, width=1)
        cbar.ax.set_yticklabels([f"{t:.2f}" for t in ticks], fontsize=cbksz, color=cbkcol)
        default_cbt = cbt if cbt else metric_display
        cbar.set_label(default_cbt, fontsize=cbtsz, color=cbtcol)
        if self.show_labels.get():
            for _,r in gdf.iterrows():
                if r.geometry is not None and pd.notnull(r[col_to_plot]):
                    pt = r.geometry.representative_point();
                    if pt.is_empty or not pt.is_valid: continue
                    val_to_show = r[col_to_plot]
                    if abs(val_to_show) >= 1000: txt = f"{val_to_show:,.0f}"
                    elif abs(val_to_show) >= 10: txt = f"{val_to_show:,.1f}"
                    elif abs(val_to_show) >= 0.1: txt = f"{val_to_show:.2f}"
                    else: txt = f"{val_to_show:.2e}"
                    ax.annotate(txt, xy=(pt.x,pt.y), ha='center', fontsize=cbksz, color=cbkcol)

        self.prevalence_var.set(f"{gdf[col_to_plot].sum():.4f}")
        fig.tight_layout(); return fig

    def save_map(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG","*.png"),("JPG","*.jpg"),("All","*.*")])
        if not path: return
        fig = self.make_fig()
        if not fig: return
        try: fig.savefig(path); messagebox.showinfo("Éxito", f"Guardado en:\n{path}")
        except Exception as e: messagebox.showerror("Error", str(e))

    def log(self, message, level="INFO"):
        try: self.txt_out.insert(tk.END, f"[{level}] {message}\n"); self.txt_out.see(tk.END)
        except Exception as e: print(f"Error en log: {e}")

if __name__=="__main__":
    root = tk.Tk()
    root.title("Visualizador de Mapas Coropléticos")
    app = MapTab(root)
    app.pack(fill=tk.BOTH, expand=True)
    root.mainloop()
