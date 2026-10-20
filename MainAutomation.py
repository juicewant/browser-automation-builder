import customtkinter as ctk
from tkinter import filedialog, messagebox
import pandas as pd
import threading
import time
import json

from engine import AutomationEngine
from ui_components import StepWidget


class AutomationApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SAP / Salesforce Automation — v3")
        self.geometry("1180x1020")
        self.minsize(900, 700)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self.excel_path  = ""
        self.steps       = []
        self.history     = []
        self.sheet_names = []

        self.engine = AutomationEngine(
            log_callback        = self.log_message,
            status_callback     = self.update_controls_state,
            row_update_callback = self.update_row_entry,
            capture_callback    = self.on_xpath_captured,
        )
        self._build_ui()

    # ══════════════════════════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ui(self):
        ctk.CTkLabel(self, text="SAP / Salesforce Automation",
                     font=("Arial", 22, "bold")
                     ).grid(row=0, column=0, pady=(14, 4), sticky="ew")
        self._build_platform_bar()
        self._build_top_controls()
        self._build_step_builder()
        self._build_sequence_list()
        self._build_settings()
        self._build_bottom_controls()

    # ── Platform selector ─────────────────────────────────────────────────────
    def _build_platform_bar(self):
        f = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=8)
        f.grid(row=1, column=0, padx=18, pady=(0, 4), sticky="ew")
        f.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(f, text="Platform:", font=("Arial", 12, "bold"),
                     text_color="#aaaaaa").grid(row=0, column=0, padx=(12, 6), pady=8)

        self.platform_var = ctk.StringVar(value="SAP")

        self.sap_btn = ctk.CTkButton(
            f, text="🏭 SAP", width=110, height=32,
            fg_color="#1f538d", hover_color="#2a6aad",
            command=lambda: self._set_platform("SAP")
        )
        self.sap_btn.grid(row=0, column=1, padx=4, pady=8)

        self.sf_btn = ctk.CTkButton(
            f, text="☁️ Salesforce", width=120, height=32,
            fg_color="#3d3d3d", hover_color="#555",
            command=lambda: self._set_platform("Salesforce")
        )
        self.sf_btn.grid(row=0, column=2, padx=4, pady=8)

        self.platform_info = ctk.CTkLabel(
            f, text="SAP mode — automatic frame search, no manual frame steps needed",
            text_color="#666", font=("Arial", 10)
        )
        self.platform_info.grid(row=0, column=3, padx=12, sticky="w")

        self.block_resources_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(
            f, text="🚫 Block Images/Fonts (faster)",
            variable=self.block_resources_var,
            font=("Arial", 11)
        ).grid(row=0, column=4, padx=16, pady=8)

    # ── URL + Excel / sheet controls ──────────────────────────────────────────
    def _build_top_controls(self):
        f = ctk.CTkFrame(self)
        f.grid(row=2, column=0, padx=18, pady=4, sticky="ew")
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="Site URL:").grid(row=0, column=0, padx=10, pady=(10, 4))
        self.url_entry = ctk.CTkEntry(f)
        self.url_entry.insert(0, "https://crmoc1.mt.mtnet/sap/bc/bsp/sap/crm_ui_start/default.htm")
        self.url_entry.grid(row=0, column=1, padx=5, pady=(10, 4), sticky="ew")

        for col, (label, cmd, color) in enumerate([
            ("📁 Excel",     self.browse_file,    "#1f538d"),
            ("💾 Save JSON", self.save_json_steps, "#5d6d7e"),
            ("📂 Load JSON", self.load_json_steps, "#5d6d7e"),
            ("🗑 Clear All", self.clear_all_steps, "#a83232"),
        ], start=2):
            ctk.CTkButton(f, text=label, command=cmd, fg_color=color, width=100)\
                .grid(row=0, column=col, padx=4, pady=(10, 4))

        ctk.CTkLabel(f, text="Sheet:").grid(row=1, column=0, padx=10, pady=(2, 8), sticky="e")
        self.sheet_picker = ctk.CTkOptionMenu(
            f, values=["— load Excel first —"], width=220,
            command=self._on_sheet_changed
        )
        self.sheet_picker.grid(row=1, column=1, padx=5, pady=(2, 8), sticky="w")
        self.file_label = ctk.CTkLabel(
            f, text="No file loaded", text_color="gray", font=("Arial", 10), anchor="w"
        )
        self.file_label.grid(row=1, column=2, columnspan=4, padx=8, pady=(2, 8), sticky="w")

    # ── Step builder ──────────────────────────────────────────────────────────
    def _build_step_builder(self):
        f = ctk.CTkFrame(self)
        f.grid(row=3, column=0, padx=18, pady=4, sticky="ew")
        f.grid_columnconfigure(2, weight=1)

        # Actions list — Switch to Frame/Default Content removed (no longer needed)
        # SAP Form Submit added for reliable SAP navigation
        actions = [
            # ── Typing ───────────────────────────────────────
            "Type (Standard)",
            "Type & Tab",
            "Type & Select",
            # ── Field ops ────────────────────────────────────
            "Clear Field",
            "Backspace (Key)",
            # ── Clicking ─────────────────────────────────────
            "Click Element",
            "Double Click Element",
            "Click Button",
            "Click Link",
            "Smart Click (Column)",
            # ── Keyboard ─────────────────────────────────────
            "Press Enter",
            "Press Tab",
            # ── SAP specific ──────────────────────────────────
            "SAP Form Submit",
            # ── Flow ─────────────────────────────────────────
            "Wait (Custom)",
            "Wait for Loading (Action)",
        ]

        self.action_var = ctk.StringVar(value="Click Element")
        self.action_menu = ctk.CTkOptionMenu(
            f, values=actions, variable=self.action_var,
            width=200, command=self._on_action_changed
        )
        self.action_menu.grid(row=0, column=0, padx=5, pady=10)

        col_frame = ctk.CTkFrame(f, fg_color="transparent")
        col_frame.grid(row=0, column=1, padx=5)
        ctk.CTkLabel(col_frame, text="Column:", font=("Arial", 11)).pack(anchor="w")
        self.col_picker = ctk.CTkOptionMenu(
            col_frame, values=["— load Excel first —"], width=160
        )
        self.col_picker.pack()
        self.col_picker.configure(state="disabled")

        self.ele_entry = ctk.CTkComboBox(f, values=["(no history)"], height=32)
        self.ele_entry.set("")
        self.ele_entry.grid(row=0, column=2, padx=5, sticky="ew")

        self.record_btn = ctk.CTkButton(
            f, text="🎯 Inspect", width=80, fg_color="#cc7a00",
            command=self.engine.toggle_inspector
        )
        self.record_btn.grid(row=0, column=3, padx=5)

        self.add_btn = ctk.CTkButton(
            f, text="＋ Add Step", width=95, fg_color="#1f538d",
            command=self.add_step
        )
        self.add_btn.grid(row=0, column=4, padx=5)

        delay_frame = ctk.CTkFrame(f, fg_color="transparent")
        delay_frame.grid(row=1, column=0, columnspan=5, padx=8, pady=(0, 8), sticky="w")
        ctk.CTkLabel(delay_frame, text="Step delay:").pack(side="left", padx=(0, 6))
        self.step_delay_slider = ctk.CTkSlider(
            delay_frame, from_=0, to=10, number_of_steps=20,
            width=180, command=self._update_step_delay_lbl
        )
        self.step_delay_slider.set(0)
        self.step_delay_slider.pack(side="left")
        self.step_delay_lbl = ctk.CTkLabel(
            delay_frame, text="Use global speed", text_color="gray", width=130
        )
        self.step_delay_lbl.pack(side="left", padx=8)

    # ── Scrollable step list ──────────────────────────────────────────────────
    def _build_sequence_list(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid(row=4, column=0, padx=18, pady=4, sticky="nsew")
        self.step_scroll = ctk.CTkScrollableFrame(f, label_text="Automation Steps")
        self.step_scroll.pack(fill="both", expand=True)

    # ── Speed + debug settings ────────────────────────────────────────────────
    def _build_settings(self):
        f = ctk.CTkFrame(self)
        f.grid(row=5, column=0, padx=18, pady=4, sticky="ew")
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="Global Speed:").grid(row=0, column=0, padx=10)
        self.global_speed_slider = ctk.CTkSlider(
            f, from_=0.1, to=5.0, command=self._update_global_lbl
        )
        self.global_speed_slider.set(1.5)
        self.global_speed_slider.grid(row=0, column=1, padx=6, sticky="ew")
        self.global_val_label = ctk.CTkLabel(
            f, text="1.5s", text_color="#3a7ebf", font=("Arial", 13, "bold"), width=46
        )
        self.global_val_label.grid(row=0, column=2, padx=8)

        self.visual_debug_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(f, text="👁 Visual Debug", variable=self.visual_debug_var)\
            .grid(row=0, column=3, padx=20)

        ctk.CTkLabel(f, text="Start Row:").grid(row=0, column=4, padx=6)
        self.row_entry = ctk.CTkEntry(f, width=55)
        self.row_entry.insert(0, "1")
        self.row_entry.grid(row=0, column=5, padx=6)

    # ── Run controls + log ────────────────────────────────────────────────────
    def _build_bottom_controls(self):
        f = ctk.CTkFrame(self)
        f.grid(row=6, column=0, padx=18, pady=8, sticky="ew")
        f.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.launch_btn = ctk.CTkButton(
            f, text="1. Open Browser", height=42,
            command=self._launch_browser
        )
        self.launch_btn.grid(row=0, column=0, padx=5, pady=10, sticky="ew")

        self.run_btn = ctk.CTkButton(
            f, text="2. ▶ Start", height=42, fg_color="#2e7d32",
            state="normal", command=self.start_automation
        )
        self.run_btn.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        self.stop_btn = ctk.CTkButton(
            f, text="🛑 STOP", height=42, fg_color="#b71c1c",
            state="normal", command=self.engine.stop_execution
        )
        self.stop_btn.grid(row=0, column=2, padx=5, pady=10, sticky="ew")

        ctk.CTkButton(
            f, text="📊 Export Report", height=42, fg_color="#555",
            command=self.export_report
        ).grid(row=0, column=3, padx=5, pady=10, sticky="ew")

        self.status_log = ctk.CTkTextbox(
            self, height=110, fg_color="#141414",
            text_color="#00e676", font=("Consolas", 11)
        )
        self.status_log.grid(row=7, column=0, padx=18, pady=(0, 16), sticky="ew")

    # ══════════════════════════════════════════════════════════════════════════
    # PLATFORM CONTROL
    # ══════════════════════════════════════════════════════════════════════════
    def _set_platform(self, platform):
        self.platform_var.set(platform)
        self.engine.set_platform(platform)
        if platform == "SAP":
            self.sap_btn.configure(fg_color="#1f538d")
            self.sf_btn.configure(fg_color="#3d3d3d")
            self.platform_info.configure(
                text="SAP mode — automatic frame search, no manual frame steps needed"
            )
            if "salesforce" in self.url_entry.get().lower():
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, "https://crmoc1.mt.mtnet/sap/bc/bsp/sap/crm_ui_start/default.htm")
        else:
            self.sap_btn.configure(fg_color="#3d3d3d")
            self.sf_btn.configure(fg_color="#0070d2")
            self.platform_info.configure(
                text="Salesforce mode — standard DOM search, no iframe workarounds needed"
            )
            if "mtnet" in self.url_entry.get().lower() or "sap" in self.url_entry.get().lower():
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, "https://mt-ap1.my.salesforce.com/home/home.jsp")
        self.log_message(f"🔄 Switched to {platform} mode")

    def _launch_browser(self):
        threading.Thread(
            target=self.engine.launch_browser,
            args=(self.url_entry.get(), self.block_resources_var.get()),
            daemon=True
        ).start()

    # ══════════════════════════════════════════════════════════════════════════
    # THREAD-SAFE CALLBACKS
    # ══════════════════════════════════════════════════════════════════════════
    def log_message(self, msg):
        self.after(0, lambda: (
            self.status_log.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n"),
            self.status_log.see("end")
        ))

    def update_controls_state(self, browser_open=None, running=None, inspecting=None):
        def _apply():
            if browser_open is True:
                self.run_btn.configure(state="normal")
            if running is True:
                self.run_btn.configure(state="disabled")
                self.stop_btn.configure(state="normal")
            elif running is False:
                self.run_btn.configure(state="normal")
                self.stop_btn.configure(state="normal")
                self.log_message("✅ Sequence finished.")
            if inspecting is True:
                self.record_btn.configure(text="🛑 Stop", fg_color="#a83232")
            elif inspecting is False:
                self.record_btn.configure(text="🎯 Inspect", fg_color="#cc7a00")
        self.after(0, _apply)

    def update_row_entry(self, row_num):
        self.after(0, lambda: (
            self.row_entry.delete(0, "end"),
            self.row_entry.insert(0, str(row_num))
        ))

    def on_xpath_captured(self, path):
        def _apply():
            self.ele_entry.set(path)
            if path and path not in self.history:
                self.history.insert(0, path)
                self.ele_entry.configure(values=self.history[:15])
        self.after(0, _apply)

    # ══════════════════════════════════════════════════════════════════════════
    # UI CALLBACKS
    # ══════════════════════════════════════════════════════════════════════════
    def _on_action_changed(self, action):
        needs = any(k in action for k in ("Type", "Select", "Smart Click (Column)"))
        self.col_picker.configure(state="normal" if needs else "disabled")

    def _on_sheet_changed(self, sheet_name):
        if not self.excel_path or sheet_name == "— load Excel first —":
            return
        try:
            df   = pd.read_excel(self.excel_path, sheet_name=sheet_name, nrows=1)
            cols = df.columns.tolist()
            self.col_picker.configure(values=cols)
            self.col_picker.set(cols[0])
            self.log_message(f"📋 Sheet '{sheet_name}' → {len(cols)} columns")
        except Exception as e:
            self.log_message(f"⚠️ Could not read sheet '{sheet_name}': {e}")

    def _update_step_delay_lbl(self, val):
        v = float(val)
        self.step_delay_lbl.configure(
            text="Use global speed" if v == 0 else f"Wait: {v:.1f}s"
        )

    def _update_global_lbl(self, val):
        self.global_val_label.configure(text=f"{float(val):.1f}s")

    # ══════════════════════════════════════════════════════════════════════════
    # FILE HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if not path:
            return
        self.excel_path = path
        try:
            xl = pd.ExcelFile(path)
            self.sheet_names = xl.sheet_names
        except Exception as e:
            self.log_message(f"⚠️ Could not read workbook: {e}")
            return

        self.sheet_picker.configure(values=self.sheet_names)
        self.sheet_picker.set(self.sheet_names[0])

        try:
            df   = pd.read_excel(path, sheet_name=self.sheet_names[0], nrows=1)
            cols = df.columns.tolist()
            self.col_picker.configure(values=cols)
            self.col_picker.set(cols[0])
        except Exception as e:
            self.log_message(f"⚠️ Could not read columns: {e}")
            return

        fname = path.replace("\\", "/").split("/")[-1]
        self.file_label.configure(
            text=f"{fname}  |  {len(self.sheet_names)} sheet(s)  |  {len(cols)} columns",
            text_color="#aaaaaa"
        )
        self.log_message(
            f"📁 {fname}  |  Sheets: {', '.join(self.sheet_names)}  |  {len(cols)} columns"
        )
        self._on_action_changed(self.action_var.get())

    def _get_selected_sheet(self):
        val = self.sheet_picker.get()
        return None if (val == "— load Excel first —" or not self.sheet_names) else val

    def save_json_steps(self):
        p = filedialog.asksaveasfilename(defaultextension=".json",
                                          filetypes=[("JSON files", "*.json")])
        if p:
            with open(p, "w") as f:
                json.dump(self.steps, f, indent=2)
            self.log_message(f"💾 Saved {len(self.steps)} steps → {p}")

    def load_json_steps(self):
        p = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if p:
            with open(p, "r") as f:
                self.steps = json.load(f)
            self._refresh_step_list()
            self.log_message(f"📂 Loaded {len(self.steps)} steps from {p}")

    def clear_all_steps(self):
        if messagebox.askyesno("Confirm", "Delete ALL steps?"):
            self.steps.clear()
            self._refresh_step_list()
            self.log_message("🗑 All steps cleared.")

    def export_report(self):
        if not self.engine.report_data:
            messagebox.showinfo("Info", "No report data yet.")
            return
        p = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                          filetypes=[("Excel files", "*.xlsx")])
        if p:
            pd.DataFrame(self.engine.report_data).to_excel(p, index=False)
            self.log_message(f"📊 Report exported → {p}")

    # ══════════════════════════════════════════════════════════════════════════
    # STEP MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════
    def add_step(self):
        delay  = round(self.step_delay_slider.get(), 1)
        action = self.action_var.get()
        step   = {
            "action":  action,
            "column":  self.col_picker.get(),
            "element": self.ele_entry.get().strip(),
            "delay":   delay,
        }

        no_element_actions = {"Wait (Custom)", "Wait for Loading (Action)"}
        if not step["element"] and action not in no_element_actions:
            tip = ""
            if action == "SAP Form Submit":
                tip = ("\n\nFor SAP Form Submit, use 🎯 Inspect to capture the element's XPath\n"
                       "or type its @title text (e.g. 'Accounts & Products').\n"
                       "The engine reads the dynamic ID automatically at runtime.")
            messagebox.showwarning("Missing Element",
                                   f"Please enter or inspect an element target.{tip}")
            return

        self.steps.append(step)
        if step["element"] and step["element"] not in self.history:
            self.history.insert(0, step["element"])
            self.ele_entry.configure(values=self.history[:15])

        self._refresh_step_list()
        self.log_message(
            f"＋ Step {len(self.steps)}: {step['action']}  →  {step['element'][:50]}"
        )

    def _delete_step(self, i):
        self.steps.pop(i)
        self._refresh_step_list()

    def _move_step(self, i, direction):
        j = i + direction
        if 0 <= j < len(self.steps):
            self.steps[i], self.steps[j] = self.steps[j], self.steps[i]
            self._refresh_step_list()

    def _refresh_step_list(self):
        for w in self.step_scroll.winfo_children():
            w.destroy()
        for i, s in enumerate(self.steps):
            StepWidget(self.step_scroll, i, s,
                       self._delete_step, self._move_step).pack(fill="x", pady=2, padx=4)

    # ══════════════════════════════════════════════════════════════════════════
    # RUN
    # ══════════════════════════════════════════════════════════════════════════
    def start_automation(self):
        if not self.engine.driver:
            messagebox.showwarning("Browser Not Open", "Click '1. Open Browser' first.")
            return
        if not self.excel_path:
            messagebox.showwarning("Missing File", "Please select an Excel file first.")
            return
        if not self.steps:
            messagebox.showwarning("No Steps", "Add at least one automation step.")
            return

        sheet = self._get_selected_sheet()
        if sheet is None:
            sheet = self.sheet_names[0] if self.sheet_names else None
        if sheet is None:
            messagebox.showwarning("No Sheet", "Could not determine worksheet.")
            return

        try:
            start_row = max(0, int(self.row_entry.get()) - 1)
        except ValueError:
            messagebox.showerror("Invalid Row", "Start Row must be a number.")
            return

        platform = self.platform_var.get()
        self.engine.set_platform(platform)
        self.log_message(f"▶ Starting [{platform}] — sheet: '{sheet}', row {start_row + 1}")

        threading.Thread(
            target=self.engine.execute_sequence,
            args=(self.excel_path, sheet, start_row, self.steps,
                  self.global_speed_slider.get(), self.visual_debug_var.get()),
            daemon=True
        ).start()


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = AutomationApp()
    app.mainloop()