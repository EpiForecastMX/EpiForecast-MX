import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from src.extraccion.pipeline import run_pipeline


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Extractor de Datos: Boletín Epidemiológico de México")
        self.geometry("900x600")

        self.test_mode = False
        self.test_input_dir = "/Users/luisgss10/Documents/To be deleted/2014"
        self.test_output_dir = "/Users/luisgss10/Documents/To be deleted/output2014"

        self.input_dir = tk.StringVar(value=self.test_input_dir if self.test_mode else os.getcwd())
        self.output_dir = tk.StringVar(value=self.test_output_dir if self.test_mode else os.getcwd())

        self.keywords = tk.StringVar(value="Depresión, Parkinson, Alzheimer")
        self.save_pages = tk.BooleanVar(value=True)
        self.save_individual_tables = tk.BooleanVar(value=True)
        self.show_preview = tk.BooleanVar(value=True)

        self._build_ui()
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def _show_keywords_help(self):
        top = tk.Toplevel(self)
        top.title("Ayuda: KEYWORDS")
        top.geometry("600x350")

        txt = tk.Text(top, wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        texto_ayuda="""KEYWORDS

        NOTA: Esta función se encuentra deshabilitada por desarrollo.
        De momento disponible solamente para Depresión, Parkinson, Alzheimer.


- Escribe las enfermedades a buscar dentro del PDF.
- Se usan para encontrar la página donde está la tabla.
- Separa cada una con coma.
- Deben ir en el mismo orden en que aparecen en la tabla del boletín.
- Agrega solamente las 2 o 3 enfermedades, tal cual están en el encabezado de la tabla deseada.
- Ejemplo: Depresión, Parkinson, Alzheimer)."""

        txt.insert("1.0", texto_ayuda)
        txt.config(state="disabled")

        ttk.Button(top, text="Cerrar", command=top.destroy).pack(pady=(0, 10))

    
    
    def _build_ui(self):
        pad = 10
        frm = ttk.Frame(self)
        frm.pack(fill="x", padx=pad, pady=pad)

        ttk.Label(frm, text="Carpeta de entrada (PDFs):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.input_dir, width=70).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(frm, text="Browse", command=self._browse_input).grid(row=0, column=2)

        ttk.Label(frm, text="Carpeta de salida:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frm, textvariable=self.output_dir, width=70).grid(row=1, column=1, sticky="we", padx=6, pady=(6, 0))
        ttk.Button(frm, text="Browse", command=self._browse_output).grid(row=1, column=2, pady=(6, 0))

        ttk.Label(frm, text="KEYWORDS:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        kw_frame = ttk.Frame(frm)
        kw_frame.grid(row=2, column=1, sticky="we", padx=6, pady=(6, 0))

        ttk.Entry(kw_frame, textvariable=self.keywords, state="disabled").pack(side="left", fill="x", expand=True)

        ttk.Button(kw_frame, text="?", width=3, command=self._show_keywords_help).pack(side="left", padx=(6, 0))

        ttk.Checkbutton(frm, text="Guardar página match", variable=self.save_pages).grid(
            row=3, column=1, sticky="w", pady=(8, 0)
        )

        ttk.Checkbutton(frm, text="Guardar CSV individuales", variable=self.save_individual_tables).grid(
            row=4, column=1, sticky="w", pady=(4, 0)
        )

        ttk.Checkbutton(frm, text="Mostrar preview al finalizar", variable=self.show_preview).grid(
            row=5, column=1, sticky="w", pady=(4, 0)
        )

        ttk.Button(frm, text="RUN", command=self._run_clicked).grid(row=5, column=2, sticky="e", pady=(4, 0))

        frm.columnconfigure(1, weight=1)

        self.log = tk.Text(self, height=25, wrap="word")
        self.log.pack(fill="both", expand=True, padx=pad, pady=(0, pad))
        texto_bienvenida = """============================================================
Extractor de tablas: Boletín Epidemiológico (México)
============================================================

Este programa procesa boletines en PDF y genera:
1) Un CSV consolidado listo para análisis.
2) Páginas individuales en PDF de la tabla seleccionada. 
3) Tablas (csv) individuales por PDF de la tabla seleccionada.

El boletín se actualiza semanalmente por el Sistema Nacional de Vigilancia Epidemiológica (SINAVE).
Link: https://www.gob.mx/salud/acciones-y-programas/direccion-general-de-epidemiologia-boletin-epidemiologico

Pasos:
1) Selecciona la carpeta con los PDFs (entrada).
2) Selecciona la carpeta donde se guardarán los resultados (salida).
3) Escribe los padecimientos (KEYWORDS) de la tabla a extraer, separadas por coma (ej. Depresión, Parkinson, Alzheimer).
   Nota: Optimizado para Depresión, Parkinson y Alzheimer. Procesamiento de otras tablas aún en desarrollo.
4) (Opcional) Activa “Guardar CSVs individuales” para guardar un CSV por cada PDF procesado.
5) (Opcional) Activa “Guardar página match” para guardar la(s) página(s) donde se encontró la tabla.
6) Presiona RUN.

Salida:
- dataset_boletin_epidemiologico.csv
- csv_tablas_individuales/ (si activas “Guardar CSVs individuales”)
- pdf_matched_pages/ (si activas “Guardar página match”)
"""

        self._log(texto_bienvenida)
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=10, pady=(0, 10))
        texto_acercade="""
Acerca de:
Extractor de tablas - Boletín Epidemiológico SINAVE
Versión: 1.0.0

Este proyecto fue realizado académicamente en colaboración del Tecnológico de Monterrey y el IMSS como parte del curso de Proyecto Integrador de la Maestría en Inteligencia Artificial Aplicada (MNA), periodo Enero-Abril, 2026.

Equipo:
A01795941@tec.mx - Juan Carlos Pérez
A01795838@tec.mx - Javier Rebull 
A01232963@tec.mx - Luis Sánchez
"""
        ttk.Button(
            footer,
            text="Acerca de...",
            command=lambda: messagebox.showinfo("Acerca de", texto_acercade)
        ).pack(side="left")

        ttk.Button(footer, text="Salir", command=self.destroy).pack(side="right")



    def _browse_input(self):
        initialdir = self.test_input_dir if self.test_mode else (self.input_dir.get() or os.getcwd())
        d = filedialog.askdirectory(initialdir=initialdir)
        if d:
            self.input_dir.set(d)

    def _browse_output(self):
        initialdir = self.test_output_dir if self.test_mode else (self.output_dir.get() or os.getcwd())
        d = filedialog.askdirectory(initialdir=initialdir)
        if d:
            self.output_dir.set(d)

    
    def _show_csv_preview(self, csv_path: str, n_rows: int = 50):
        import pandas as pd
        from tkinter import ttk
        import tkinter as tk

        if not os.path.exists(csv_path):
            messagebox.showwarning("Preview", f"No se encontró el archivo:\n{csv_path}")
            return

        df = pd.read_csv(csv_path).head(n_rows)

        top = tk.Toplevel(self)
        top.title(f"Preview: {os.path.basename(csv_path)} (primeras {len(df)} filas)")
        top.geometry("1000x500")

        frame = ttk.Frame(top)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        cols = list(df.columns)
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        vsb.pack(side="right", fill="y")
        tree.configure(yscrollcommand=vsb.set)

        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=140, anchor="w")

        for _, row in df.iterrows():
            tree.insert("", "end", values=[row[c] for c in cols])

        ttk.Button(top, text="Cerrar", command=top.destroy).pack(pady=(0, 10))

    
    def _log(self, msg: str):
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.update_idletasks()

    def _log_safe(self, msg: str):
        self.after(0, lambda m=msg: self._log(m))

    def _run_clicked(self):
        inp = self.input_dir.get().strip()
        out = self.output_dir.get().strip()
        kw = [k.strip() for k in self.keywords.get().split(",") if k.strip()]
        save_pages = bool(self.save_pages.get())
        save_tables = bool(self.save_individual_tables.get())

        def worker():
            try:
                self._log_safe("\n=== Inicio ===")
                self.current_file = None
                run_pipeline(
                    inp, out, kw,
                    save_matched_pages=save_pages,
                    save_individual_tables=save_tables,
                    log_fn=self._log_safe,
                    on_file=lambda f: setattr(self, "current_file", f),
                )
                self._log_safe("\n=== Fin ===")
                if self.show_preview.get():
                    output_csv = os.path.join(out, "dataset_boletin_epidemiologico.csv")
                    self.after(0, lambda: self._show_csv_preview(output_csv))

            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                self._log_safe(f"\nERROR ({type(e).__name__}): {e}\n{tb}")
                fname = getattr(self, "current_file", "desconocido")
                msg = f"⚠️ Procesamiento fallido. Archivo: {fname}\n{type(e).__name__}: {e}"
                self.after(0, lambda msg=msg: messagebox.showerror("Error", msg))

        threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    App().mainloop()