import customtkinter as ctk


class StepWidget(ctk.CTkFrame):
    """Displays one automation step row with colour coding, move, and delete controls."""

    ACTION_COLORS = {
        "Type":   "#3a7ebf",
        "Select": "#3a7ebf",
        "Click":  "#2e8b57",
        "Smart":  "#2e8b57",
        "Double": "#2e8b57",
        "Clear":  "#8b6914",
        "Back":   "#8b6914",
        "Press":  "#6a4c93",
        "Wait":   "#555555",
        "SAP":    "#c0392b",
    }

    def __init__(self, master, index, step_data, delete_cb, move_cb):
        super().__init__(master, fg_color="#2b2b2b", corner_radius=6)
        self.columnconfigure(2, weight=1)

        action  = step_data.get("action",  "")
        column  = step_data.get("column",  "")
        element = step_data.get("element", "")
        delay   = step_data.get("delay",   0)

        accent = next(
            (col for key, col in self.ACTION_COLORS.items() if action.startswith(key)),
            "#888888"
        )

        ctk.CTkLabel(
            self, text=str(index + 1), width=28,
            font=("Arial", 11, "bold"),
            fg_color=accent, corner_radius=4, text_color="white"
        ).grid(row=0, column=0, padx=(6, 4), pady=6, sticky="ns")

        needs_col    = column and "Wait" not in action and "SAP" not in action
        action_label = f"{action}  [{column}]" if needs_col else action
        ctk.CTkLabel(
            self, text=action_label, width=230, anchor="w",
            font=("Arial", 11), text_color=accent
        ).grid(row=0, column=1, padx=4, pady=6, sticky="w")

        display = (element[:48] + "…") if len(element) > 48 else element
        ctk.CTkLabel(
            self, text=display, anchor="w",
            text_color="#aaaaaa", font=("Arial", 10)
        ).grid(row=0, column=2, padx=4, pady=6, sticky="ew")

        if delay > 0:
            ctk.CTkLabel(
                self, text=f"⏱ {delay}s", width=55,
                text_color="#3a7ebf", font=("Arial", 10, "bold")
            ).grid(row=0, column=3, padx=4)

        btn = dict(width=26, height=26, corner_radius=4, font=("Arial", 11))
        ctk.CTkButton(self, text="▲", **btn, fg_color="#3d3d3d", hover_color="#555",
                      command=lambda: move_cb(index, -1)
                      ).grid(row=0, column=4, padx=2)
        ctk.CTkButton(self, text="▼", **btn, fg_color="#3d3d3d", hover_color="#555",
                      command=lambda: move_cb(index, 1)
                      ).grid(row=0, column=5, padx=2)
        ctk.CTkButton(self, text="✕", **btn, fg_color="#7a2020", hover_color="#a83232",
                      command=lambda: delete_cb(index)
                      ).grid(row=0, column=6, padx=(2, 8))