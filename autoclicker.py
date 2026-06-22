"""
AutoClicker — автокликер с GUI
Зависимости: pip install pynput
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from pynput import mouse, keyboard
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController, Listener as KeyboardListener

# ──────────────────────────────────────────────
#  Константы
# ──────────────────────────────────────────────
MOUSE_BUTTONS = {
    "Левая кнопка мыши":  Button.left,
    "Правая кнопка мыши": Button.right,
    "Средняя кнопка мыши": Button.middle,
}

SPECIAL_KEYS = {
    "Enter": Key.enter, "Space": Key.space, "Tab": Key.tab,
    "Escape": Key.esc, "Backspace": Key.backspace, "Delete": Key.delete,
    "Home": Key.home, "End": Key.end, "Page Up": Key.page_up,
    "Page Down": Key.page_down,
    "F1": Key.f1, "F2": Key.f2, "F3": Key.f3, "F4": Key.f4,
    "F5": Key.f5, "F6": Key.f6, "F7": Key.f7, "F8": Key.f8,
    "F9": Key.f9, "F10": Key.f10, "F11": Key.f11, "F12": Key.f12,
    "↑ Up": Key.up, "↓ Down": Key.down, "← Left": Key.left, "→ Right": Key.right,
}

COLORS = {
    "bg":       "#1a1a2e",
    "panel":    "#16213e",
    "accent":   "#0f3460",
    "green":    "#4ecca3",
    "red":      "#e94560",
    "text":     "#eaeaea",
    "muted":    "#8892a4",
    "border":   "#0f3460",
    "entry_bg": "#0d1b2a",
}

# ──────────────────────────────────────────────
#  Логика автокликера
# ──────────────────────────────────────────────
class AutoClicker:
    def __init__(self):
        self.mouse_ctrl   = MouseController()
        self.key_ctrl     = KeyboardController()
        self._running     = False
        self._thread      = None

    @property
    def is_running(self):
        return self._running

    def start(self, action_type, action_value, interval, count):
        """action_type: 'mouse' | 'keyboard'"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            args=(action_type, action_value, interval, count),
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self, action_type, action_value, interval, count):
        done = 0
        infinite = (count == 0)
        while self._running and (infinite or done < count):
            if action_type == "mouse":
                self.mouse_ctrl.click(action_value)
            else:
                self.key_ctrl.press(action_value)
                self.key_ctrl.release(action_value)
            done += 1
            # Прерываемый sleep — проверяем флаг каждые 50 мс
            elapsed = 0.0
            while self._running and elapsed < interval:
                time.sleep(0.05)
                elapsed += 0.05
        self._running = False


# ──────────────────────────────────────────────
#  GUI
# ──────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoClicker")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])

        self.clicker = AutoClicker()
        self._hotkey_keys = set()          # текущие зажатые клавиши хоткея
        self._hotkey_combo = set()         # записанный хоткей
        self._recording_hotkey = False
        self._hotkey_listener = None
        self._armed = False                # True = настроен и ждёт хоткея

        self._build_ui()
        self._start_hotkey_listener()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Построение интерфейса ──────────────────
    def _build_ui(self):
        pad = {"padx": 18, "pady": 10}

        # Заголовок
        header = tk.Frame(self, bg=COLORS["accent"], pady=14)
        header.pack(fill="x")

        # Лампочка — правый верхний угол хедера
        self._lamp = tk.Label(
            header, text="●", font=("Segoe UI", 22),
            bg=COLORS["accent"], fg="#3a5a8a",   # синий = предохранитель
        )
        self._lamp.place(relx=1.0, rely=0.0, anchor="ne", x=-12, y=6)

        tk.Label(
            header, text="⚡ AutoClicker",
            font=("Segoe UI", 20, "bold"),
            bg=COLORS["accent"], fg=COLORS["green"],
        ).pack()
        tk.Label(
            header, text="Настройте действие и горячую клавишу",
            font=("Segoe UI", 9), bg=COLORS["accent"], fg=COLORS["muted"],
        ).pack()

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, **pad)

        # ── 1. Тип действия ──────────────────────
        self._section(body, "1  Тип действия")

        self._action_type = tk.StringVar(value="mouse")
        row = tk.Frame(body, bg=COLORS["bg"])
        row.pack(fill="x", pady=(0, 6))
        for text, val in [("🖱  Мышь", "mouse"), ("⌨  Клавиатура", "keyboard")]:
            rb = tk.Radiobutton(
                row, text=text, variable=self._action_type, value=val,
                command=self._on_type_change,
                bg=COLORS["bg"], fg=COLORS["text"], selectcolor=COLORS["panel"],
                activebackground=COLORS["bg"], activeforeground=COLORS["green"],
                font=("Segoe UI", 11), indicatoron=0,
                relief="flat", bd=0, padx=14, pady=6, cursor="hand2",
            )
            rb.pack(side="left", padx=(0, 8))

        # ── 2. Кнопка / клавиша ──────────────────
        self._section(body, "2  Выберите кнопку / клавишу")

        # Мышь
        self._mouse_frame = tk.Frame(body, bg=COLORS["bg"])
        self._mouse_frame.pack(fill="x", pady=(0, 4))
        self._mouse_var = tk.StringVar(value=list(MOUSE_BUTTONS.keys())[0])
        self._mouse_menu = self._dropdown(self._mouse_frame, self._mouse_var, list(MOUSE_BUTTONS.keys()))

        # Клавиатура
        self._kb_frame = tk.Frame(body, bg=COLORS["bg"])
        # Два варианта: список спец-клавиш или ввод символа
        self._kb_mode = tk.StringVar(value="char")
        kb_mode_row = tk.Frame(self._kb_frame, bg=COLORS["bg"])
        kb_mode_row.pack(fill="x")
        for text, val in [("Символ", "char"), ("Спец. клавиша", "special")]:
            tk.Radiobutton(
                kb_mode_row, text=text, variable=self._kb_mode, value=val,
                command=self._on_kb_mode_change,
                bg=COLORS["bg"], fg=COLORS["muted"], selectcolor=COLORS["panel"],
                activebackground=COLORS["bg"], font=("Segoe UI", 9),
                indicatoron=1,
            ).pack(side="left", padx=(0, 12))

        # Поле ввода символа
        self._char_frame = tk.Frame(self._kb_frame, bg=COLORS["bg"])
        self._char_frame.pack(fill="x", pady=(4, 0))
        self._char_var = tk.StringVar(value="a")
        char_entry = tk.Entry(
            self._char_frame, textvariable=self._char_var,
            width=6, font=("Segoe UI", 14, "bold"),
            bg=COLORS["entry_bg"], fg=COLORS["green"],
            insertbackground=COLORS["green"], relief="flat",
            justify="center",
        )
        char_entry.pack(side="left")
        char_entry.bind("<KeyRelease>", lambda e: self._char_var.set(self._char_var.get()[-1] if self._char_var.get() else "a"))
        tk.Label(self._char_frame, text="  (один символ)",
                 bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 9)).pack(side="left")

        # Список спец-клавиш
        self._special_frame = tk.Frame(self._kb_frame, bg=COLORS["bg"])
        self._special_var = tk.StringVar(value=list(SPECIAL_KEYS.keys())[0])
        self._dropdown(self._special_frame, self._special_var, list(SPECIAL_KEYS.keys()))

        # ── 3. Интервал ───────────────────────────
        self._section(body, "3  Интервал между нажатиями")
        interval_row = tk.Frame(body, bg=COLORS["bg"])
        interval_row.pack(fill="x", pady=(0, 4))

        self._interval_ms = tk.IntVar(value=100)
        self._interval_slider = tk.Scale(
            interval_row, from_=10, to=5000, orient="horizontal",
            variable=self._interval_ms, command=self._update_interval_label,
            bg=COLORS["bg"], fg=COLORS["text"], troughcolor=COLORS["panel"],
            highlightthickness=0, bd=0, length=260, showvalue=False,
        )
        self._interval_slider.pack(side="left")
        self._interval_label = tk.Label(
            interval_row, text="100 мс", width=8,
            bg=COLORS["bg"], fg=COLORS["green"], font=("Segoe UI", 11, "bold"),
        )
        self._interval_label.pack(side="left", padx=(8, 0))

        # Быстрые пресеты
        preset_row = tk.Frame(body, bg=COLORS["bg"])
        preset_row.pack(fill="x", pady=(0, 6))
        for label, ms in [("10мс", 10), ("50мс", 50), ("100мс", 100), ("500мс", 500), ("1с", 1000), ("5с", 5000)]:
            btn = tk.Button(
                preset_row, text=label,
                command=lambda v=ms: self._set_interval(v),
                bg=COLORS["panel"], fg=COLORS["muted"],
                activebackground=COLORS["accent"], activeforeground=COLORS["green"],
                relief="flat", padx=8, pady=2, cursor="hand2", font=("Segoe UI", 8),
            )
            btn.pack(side="left", padx=2)

        # ── 4. Количество нажатий ─────────────────
        self._section(body, "4  Количество нажатий")
        count_row = tk.Frame(body, bg=COLORS["bg"])
        count_row.pack(fill="x", pady=(0, 4))

        # Галочка «Зафиксировать количество» + замок-эмодзи
        self._infinite = tk.BooleanVar(value=True)
        self._fixed_check = tk.Checkbutton(
            count_row, variable=self._infinite,
            onvalue=False, offvalue=True,
            command=self._toggle_count,
            bg=COLORS["bg"], fg=COLORS["text"], selectcolor=COLORS["panel"],
            activebackground=COLORS["bg"], activeforeground=COLORS["green"],
            font=("Segoe UI", 10),
        )
        self._fixed_check.pack(side="left")
        self._lock_label = tk.Label(
            count_row, text="🔓 Бесконечно",
            bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 10),
            cursor="hand2",
        )
        self._lock_label.pack(side="left")
        self._lock_label.bind("<Button-1>", lambda e: (
            self._infinite.set(not self._infinite.get()), self._toggle_count()
        ))

        # Контейнер с полем и кнопками +/−
        self._count_frame = tk.Frame(count_row, bg=COLORS["bg"])
        self._count_frame.pack(side="left", padx=(14, 0))

        self._count_raw = tk.StringVar(value="10")

        btn_minus = tk.Button(
            self._count_frame, text="−", width=2,
            command=self._count_dec,
            bg=COLORS["panel"], fg=COLORS["text"],
            activebackground=COLORS["accent"], activeforeground=COLORS["green"],
            relief="flat", font=("Segoe UI", 11, "bold"), cursor="hand2",
        )
        btn_minus.pack(side="left")

        self._count_entry = tk.Entry(
            self._count_frame, textvariable=self._count_raw,
            width=6, font=("Segoe UI", 11),
            bg=COLORS["entry_bg"], fg=COLORS["green"],
            insertbackground=COLORS["green"], relief="flat",
            justify="center", state="disabled",
        )
        self._count_entry.pack(side="left", padx=3)
        # Принимать только цифры
        self._count_entry.bind("<FocusOut>", self._validate_count)

        btn_plus = tk.Button(
            self._count_frame, text="+", width=2,
            command=self._count_inc,
            bg=COLORS["panel"], fg=COLORS["text"],
            activebackground=COLORS["accent"], activeforeground=COLORS["green"],
            relief="flat", font=("Segoe UI", 11, "bold"), cursor="hand2",
        )
        btn_plus.pack(side="left")

        # Кнопки тоже изначально неактивны
        self._count_btns = [btn_minus, btn_plus]
        for b in self._count_btns:
            b.config(state="disabled")

        # ── 5. Хоткей ─────────────────────────────
        self._section(body, "5  Горячая клавиша (старт / стоп)")
        hotkey_row = tk.Frame(body, bg=COLORS["bg"])
        hotkey_row.pack(fill="x", pady=(0, 6))

        self._hotkey_label = tk.Label(
            hotkey_row, text="Не назначен", width=22,
            bg=COLORS["entry_bg"], fg=COLORS["muted"],
            font=("Consolas", 11), relief="flat", pady=6, anchor="w", padx=8,
        )
        self._hotkey_label.pack(side="left")

        self._record_btn = tk.Button(
            hotkey_row, text="Записать",
            command=self._toggle_record_hotkey,
            bg=COLORS["accent"], fg=COLORS["text"],
            activebackground=COLORS["green"], activeforeground=COLORS["bg"],
            relief="flat", padx=12, pady=5, cursor="hand2", font=("Segoe UI", 9),
        )
        self._record_btn.pack(side="left", padx=(8, 0))

        tk.Button(
            hotkey_row, text="✕ Сбросить",
            command=self._clear_hotkey,
            bg=COLORS["panel"], fg=COLORS["muted"],
            activebackground=COLORS["red"], activeforeground="white",
            relief="flat", padx=10, pady=5, cursor="hand2", font=("Segoe UI", 9),
        ).pack(side="left", padx=(6, 0))

        # ── Кнопки Вооружить / Сброс ──────────────
        separator = tk.Frame(body, bg=COLORS["border"], height=1)
        separator.pack(fill="x", pady=(12, 10))

        btn_row = tk.Frame(body, bg=COLORS["bg"])
        btn_row.pack(fill="x", pady=(0, 4))

        self._arm_btn = tk.Button(
            btn_row, text="🎯  ВООРУЖИТЬ",
            command=self._arm,
            bg=COLORS["green"], fg=COLORS["bg"],
            activebackground="#3ab88f", activeforeground=COLORS["bg"],
            relief="flat", padx=20, pady=10,
            font=("Segoe UI", 12, "bold"), cursor="hand2",
        )
        self._arm_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self._disarm_btn = tk.Button(
            btn_row, text="✕  СБРОС",
            command=self._disarm,
            bg=COLORS["panel"], fg=COLORS["muted"],
            activebackground=COLORS["red"], activeforeground="white",
            relief="flat", padx=20, pady=10,
            font=("Segoe UI", 12, "bold"), cursor="hand2",
            state="disabled",
        )
        self._disarm_btn.pack(side="left", expand=True, fill="x")

        # Статусная строка
        self._status_var = tk.StringVar(value="⬜ Настройте параметры и нажмите «Вооружить»")
        self._status_label = tk.Label(
            body, textvariable=self._status_var,
            bg=COLORS["bg"], fg=COLORS["muted"],
            font=("Segoe UI", 9), anchor="center", wraplength=340,
        )
        self._status_label.pack(pady=(6, 0))

        # Инициализировать видимость виджетов
        self._on_type_change()
        self._on_kb_mode_change()

        # Глобальный сброс фокуса при клике на любой виджет, кроме Entry
        self._bind_defocus(self)

    def _section(self, parent, text):
        tk.Label(
            parent, text=text, bg=COLORS["bg"], fg=COLORS["green"],
            font=("Segoe UI", 9, "bold"), anchor="w",
        ).pack(fill="x", pady=(10, 2))

    def _dropdown(self, parent, var, options):
        cb = ttk.Combobox(
            parent, textvariable=var, values=options,
            state="readonly", font=("Segoe UI", 10), width=26,
        )
        cb.pack(side="left")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox",
            fieldbackground=COLORS["entry_bg"],
            background=COLORS["entry_bg"],
            foreground=COLORS["text"],
            selectbackground=COLORS["accent"],
            arrowcolor=COLORS["green"],
        )
        return cb

    # ── Логика переключений ────────────────────
    def _on_type_change(self):
        t = self._action_type.get()
        if t == "mouse":
            self._kb_frame.pack_forget()
            self._mouse_frame.pack(fill="x", pady=(0, 4))
        else:
            self._mouse_frame.pack_forget()
            self._kb_frame.pack(fill="x", pady=(0, 4))

    def _on_kb_mode_change(self):
        if self._kb_mode.get() == "char":
            self._special_frame.pack_forget()
            self._char_frame.pack(fill="x", pady=(4, 0))
        else:
            self._char_frame.pack_forget()
            self._special_frame.pack(fill="x", pady=(4, 0))

    def _toggle_count(self):
        # _infinite=True → бесконечно (галочка снята); False → фиксированное (галочка стоит)
        fixed = not self._infinite.get()
        state = "normal" if fixed else "disabled"
        self._count_entry.config(state=state)
        for b in self._count_btns:
            b.config(state=state)
        if fixed:
            self._lock_label.config(text="🔒 Зафиксировано", fg=COLORS["green"])
        else:
            self._lock_label.config(text="🔓 Бесконечно", fg=COLORS["muted"])

    def _bind_defocus(self, widget):
        """Рекурсивно вешаем на все виджеты: клик → снять фокус, если это не Entry."""
        def maybe_defocus(e):
            w = e.widget
            if not isinstance(w, (tk.Entry, tk.Spinbox)):
                self.focus_set()
        widget.bind("<Button-1>", maybe_defocus, add="+")
        for child in widget.winfo_children():
            self._bind_defocus(child)

    def _update_lamp(self, state):
        """state: 'safe' (синий) | 'ready' (красный) | 'running' (зелёный)"""
        colors = {
            "safe":    "#3a6ea5",   # синий — предохранитель
            "ready":   COLORS["red"],
            "running": COLORS["green"],
        }
        self._lamp.config(fg=colors.get(state, "#3a6ea5"))

    def _count_inc(self):
        try:
            v = int(self._count_raw.get())
        except ValueError:
            v = 1
        self._count_raw.set(str(min(v + 1, 99999)))

    def _count_dec(self):
        try:
            v = int(self._count_raw.get())
        except ValueError:
            v = 2
        self._count_raw.set(str(max(v - 1, 1)))

    def _validate_count(self, _=None):
        try:
            v = int(self._count_raw.get())
            self._count_raw.set(str(max(1, min(v, 99999))))
        except ValueError:
            self._count_raw.set("10")

    def _update_interval_label(self, _=None):
        ms = self._interval_ms.get()
        if ms >= 1000:
            self._interval_label.config(text=f"{ms/1000:.1f} с")
        else:
            self._interval_label.config(text=f"{ms} мс")

    def _set_interval(self, ms):
        self._interval_ms.set(ms)
        self._update_interval_label()

    # ── Хоткей ────────────────────────────────
    def _toggle_record_hotkey(self):
        if self._recording_hotkey:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._recording_hotkey = True
        self._hotkey_keys.clear()
        self._hotkey_label.config(text="Нажмите комбинацию...", fg=COLORS["green"])
        self._record_btn.config(text="Остановить запись", bg=COLORS["red"])

    def _stop_recording(self):
        self._recording_hotkey = False
        self._record_btn.config(text="Записать", bg=COLORS["accent"])
        if self._hotkey_combo:
            self._hotkey_label.config(
                text=self._combo_str(self._hotkey_combo), fg=COLORS["green"])
        else:
            self._hotkey_label.config(text="Не назначен", fg=COLORS["muted"])

    def _clear_hotkey(self):
        self._hotkey_combo.clear()
        self._hotkey_label.config(text="Не назначен", fg=COLORS["muted"])

    def _combo_str(self, combo):
        parts = []
        for k in sorted(combo, key=str):
            if hasattr(k, "name"):
                parts.append(k.name.capitalize())
            elif hasattr(k, "char") and k.char:
                parts.append(k.char.upper())
            else:
                parts.append(str(k))
        return " + ".join(parts)

    def _start_hotkey_listener(self):
        self._held_keys = set()

        def on_press(key):
            if self._recording_hotkey:
                self._hotkey_keys.add(key)
                self._hotkey_combo = set(self._hotkey_keys)
                self.after(0, lambda: self._hotkey_label.config(
                    text=self._combo_str(self._hotkey_combo),
                    fg=COLORS["green"]))
            else:
                self._held_keys.add(key)
                # Не срабатываем, если фокус в поле ввода
                focused = self.focus_get()
                if focused and isinstance(focused, (tk.Entry, tk.Spinbox)):
                    return
                if self._hotkey_combo and self._hotkey_combo == self._held_keys:
                    self.after(0, self._hotkey_triggered)

        def on_release(key):
            self._held_keys.discard(key)
            if self._recording_hotkey:
                self._hotkey_keys.discard(key)

        self._hotkey_listener = KeyboardListener(on_press=on_press, on_release=on_release)
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()

    def _hotkey_triggered(self):
        if not self._armed:
            return
        if self.clicker.is_running:
            self._stop_running()
        else:
            self._run()

    # ── Вооружить / Сброс (кнопки GUI) ───────────
    def _arm(self):
        """Проверяем настройки и переходим в режим ожидания хоткея."""
        action_type, action_value = self._get_action()
        if action_value is None:
            messagebox.showwarning("Ошибка", "Введите символ для нажатия.")
            return
        if not self._hotkey_combo:
            messagebox.showwarning("Ошибка", "Назначьте горячую клавишу.")
            return

        self._armed = True
        self._arm_btn.config(state="disabled")
        self._disarm_btn.config(state="normal", bg=COLORS["red"], fg="white")
        hotkey_str = self._combo_str(self._hotkey_combo)
        self._set_status(f"🟡 Ожидание хоткея  [{hotkey_str}]", COLORS["green"])
        self._update_lamp("ready")

    def _disarm(self):
        """Полный сброс — останавливаем если работает, снимаем вооружение."""
        self.clicker.stop()
        self._armed = False
        self._arm_btn.config(state="normal")
        self._disarm_btn.config(state="disabled", bg=COLORS["panel"], fg=COLORS["muted"])
        self._set_status("⬜ Настройте параметры и нажмите «Вооружить»", COLORS["muted"])
        self._update_lamp("safe")

    # ── Запуск / Остановка цикла ──────────────────
    def _run(self):
        """Запустить цикл кликов (только из хоткея, пока вооружён)."""
        action_type, action_value = self._get_action()
        if action_value is None:
            return

        interval = self._interval_ms.get() / 1000.0
        if self._infinite.get():
            count = 0
        else:
            self._validate_count()
            try:
                count = int(self._count_raw.get())
            except ValueError:
                count = 10

        self.clicker.start(action_type, action_value, interval, count)
        label = f"{count} раз" if count else "∞"
        hotkey_str = self._combo_str(self._hotkey_combo)
        self._set_status(f"🟢 Работает · {label} · {self._interval_ms.get()} мс  [{hotkey_str}] = стоп", COLORS["green"])
        self._update_lamp("running")
        self._poll_status()

    def _stop_running(self):
        """Остановить цикл и сбросить счётчик — готов к следующему запуску."""
        self.clicker.stop()
        hotkey_str = self._combo_str(self._hotkey_combo)
        self._set_status(f"🟡 Остановлен · ожидание  [{hotkey_str}]", COLORS["green"])
        self._update_lamp("ready")

    # ── Вспомогательные ───────────────────────────
    def _get_action(self):
        if self._action_type.get() == "mouse":
            return "mouse", MOUSE_BUTTONS[self._mouse_var.get()]
        else:
            if self._kb_mode.get() == "char":
                ch = self._char_var.get()
                if not ch:
                    return None, None
                return "keyboard", ch
            else:
                return "keyboard", SPECIAL_KEYS[self._special_var.get()]

    def _set_status(self, text, color):
        self._status_var.set(text)
        self._status_label.config(fg=color)

    def _poll_status(self):
        """Отслеживаем авто-завершение по счётчику."""
        if not self.clicker.is_running and self._armed:
            hotkey_str = self._combo_str(self._hotkey_combo)
            self._set_status(f"✅ Цикл завершён · ожидание  [{hotkey_str}]", COLORS["green"])
            self._update_lamp("ready")
        elif self.clicker.is_running:
            self.after(200, self._poll_status)

    def _on_close(self):
        self.clicker.stop()
        self._armed = False
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        self.destroy()


# ──────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()