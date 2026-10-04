#!/usr/bin/env python3
import argparse
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from pynput import keyboard, mouse
except ImportError:
    print("Missing dependency: pynput")
    print("Install it with: python -m pip install -r requirements.txt")
    sys.exit(1)


DEFAULT_PORT = "50505"
DEFAULT_HOTKEY = "cmd+option+control+q"
DEFAULT_WINDOWS_HOTKEY = "cmd+option+control+w"
DEFAULT_ANDROID_HOTKEY = "cmd+option+control+a"
DEFAULT_ANDROID_ROTATE_HOTKEY = "cmd+option+control+r"
CONFIG_PATH = os.path.join(
    os.path.expanduser("~"),
    "Library",
    "Application Support",
    "CarrotKeyboard",
    "config.json",
)
RECONNECT_DELAY = 1.0
MOUSE_MOVE_INTERVAL = 0.01

HOTKEY_ALIASES = {
    "command": "cmd",
    "meta": "cmd",
    "control": "ctrl",
    "ctl": "ctrl",
    "option": "alt",
    "escape": "esc",
    "return": "enter",
}

MODIFIER_BASE_NAMES = {
    "alt_l": "alt",
    "alt_r": "alt",
    "cmd_l": "cmd",
    "cmd_r": "cmd",
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "shift_l": "shift",
    "shift_r": "shift",
}

HOTKEY_DISPLAY = {
    "alt": "⌥",
    "cmd": "⌘",
    "ctrl": "⌃",
    "shift": "⇧",
    "esc": "Esc",
    "enter": "Enter",
    "space": "Space",
    "tab": "Tab",
}

HOTKEY_DISPLAY_ORDER = ("cmd", "alt", "ctrl", "shift")


def safe_key(name):
    return getattr(keyboard.Key, name, None)


def key_to_payload(key):
    if isinstance(key, keyboard.KeyCode):
        return {"type": "char", "char": key.char, "vk": key.vk}

    name = getattr(key, "name", None)
    if name:
        return {"type": "special", "name": name}

    return None


def normalize_hotkey_token(token):
    token = token.strip().lower()
    if not token:
        return ""
    token = token.replace(" ", "_")
    token = HOTKEY_ALIASES.get(token, token)
    return MODIFIER_BASE_NAMES.get(token, token)


def parse_hotkey(value):
    tokens = {normalize_hotkey_token(part) for part in value.split("+")}
    tokens.discard("")
    if not tokens:
        raise ValueError("Hotkey cannot be empty.")
    return tokens


def format_hotkey(tokens):
    ordered = [token for token in HOTKEY_DISPLAY_ORDER if token in tokens]
    ordered.extend(sorted(token for token in tokens if token not in HOTKEY_DISPLAY_ORDER))
    return " + ".join(HOTKEY_DISPLAY.get(token, token.upper() if len(token) == 1 else token) for token in ordered)


def serialize_hotkey(tokens):
    ordered = [token for token in HOTKEY_DISPLAY_ORDER if token in tokens]
    ordered.extend(sorted(token for token in tokens if token not in HOTKEY_DISPLAY_ORDER))
    return "+".join(ordered)


def key_to_hotkey_token(key):
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        if key.vk is not None:
            return f"vk:{key.vk}"
        return None

    name = getattr(key, "name", None)
    if not name:
        return None
    return normalize_hotkey_token(name)


def tk_keysym_to_hotkey_token(keysym):
    token = normalize_hotkey_token(keysym)
    if token in {"alt_l", "alt_r", "cmd_l", "cmd_r", "ctrl_l", "ctrl_r", "shift_l", "shift_r"}:
        return MODIFIER_BASE_NAMES[token]

    tk_aliases = {
        "command": "cmd",
        "meta_l": "cmd",
        "meta_r": "cmd",
        "super_l": "cmd",
        "super_r": "cmd",
        "control_l": "ctrl",
        "control_r": "ctrl",
        "option_l": "alt",
        "option_r": "alt",
        "alt_l": "alt",
        "alt_r": "alt",
        "shift_l": "shift",
        "shift_r": "shift",
        "return": "enter",
        "escape": "esc",
    }
    token = tk_aliases.get(token, token)
    if len(token) == 1:
        return token.lower()
    return token


def get_screen_size():
    root = tk.Tk()
    root.withdraw()
    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
    root.destroy()
    return max(width, 1), max(height, 1)


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(data):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


class MacSender:
    def __init__(
        self,
        host,
        port,
        suppress_keyboard,
        forward_mouse,
        suppress_mouse,
        hotkey,
        target_name,
        rotate_hotkey=None,
    ):
        self.host = host
        self.port = int(port)
        self.suppress_keyboard = suppress_keyboard
        self.forward_mouse = forward_mouse
        self.suppress_mouse = suppress_mouse
        self.hotkey = hotkey
        self.target_name = target_name
        self.rotate_hotkey = rotate_hotkey or set()
        self.sock = None
        self.send_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.pressed = set()
        self.rotate_armed = True
        self.screen_width, self.screen_height = get_screen_size()
        self.last_mouse_move = 0.0

    def connect(self):
        while not self.stop_event.is_set():
            try:
                self.sock = socket.create_connection((self.host, self.port), timeout=5)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                print(f"Connected to {self.target_name} at {self.host}:{self.port}", flush=True)
                return
            except OSError as exc:
                print(f"Waiting for {self.target_name} {self.host}:{self.port} ({exc})", flush=True)
                time.sleep(RECONNECT_DELAY)

    def send_json(self, data):
        if self.sock is None:
            return

        line = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
        try:
            with self.send_lock:
                self.sock.sendall(line.encode("utf-8"))
        except OSError:
            print("Connection lost. Reconnecting...", flush=True)
            self.close_socket()
            self.connect()

    def close_socket(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def should_quit(self):
        return self.hotkey.issubset(self.pressed)

    def should_rotate_android(self):
        return (
            self.target_name == "Android Phone"
            and self.rotate_hotkey
            and self.rotate_hotkey.issubset(self.pressed)
        )

    def on_press(self, key):
        token = key_to_hotkey_token(key)
        if token:
            self.pressed.add(token)
        if self.should_quit():
            print("Stop hotkey pressed.", flush=True)
            self.stop_event.set()
            return False

        if self.rotate_armed and self.should_rotate_android():
            self.rotate_armed = False
            print("Android rotate hotkey pressed.", flush=True)
            self.send_json({"device": "system", "action": "rotate"})
            return

        payload = key_to_payload(key)
        if payload:
            self.send_json({"device": "keyboard", "action": "press", "key": payload})

    def on_release(self, key):
        token = key_to_hotkey_token(key)
        if token:
            self.pressed.discard(token)
        if not self.should_rotate_android():
            self.rotate_armed = True
        payload = key_to_payload(key)
        if payload:
            self.send_json({"device": "keyboard", "action": "release", "key": payload})

    def on_mouse_move(self, x, y):
        now = time.monotonic()
        if now - self.last_mouse_move < MOUSE_MOVE_INTERVAL:
            return
        self.last_mouse_move = now
        self.send_json(
            {
                "device": "mouse",
                "action": "move",
                "x_ratio": max(0.0, min(1.0, x / self.screen_width)),
                "y_ratio": max(0.0, min(1.0, y / self.screen_height)),
            }
        )

    def on_mouse_click(self, x, y, button, pressed):
        self.send_json(
            {
                "device": "mouse",
                "action": "press" if pressed else "release",
                "button": getattr(button, "name", "left"),
                "x_ratio": max(0.0, min(1.0, x / self.screen_width)),
                "y_ratio": max(0.0, min(1.0, y / self.screen_height)),
            }
        )

    def on_mouse_scroll(self, x, y, dx, dy):
        self.send_json(
            {
                "device": "mouse",
                "action": "scroll",
                "dx": dx,
                "dy": dy,
            }
        )

    def run(self):
        self.connect()
        if self.stop_event.is_set():
            return

        print(f"Forwarding Mac keyboard to {self.target_name}.", flush=True)
        if self.forward_mouse:
            print(f"Forwarding Mac mouse to {self.target_name}.", flush=True)
        print(f"Stop hotkey: {'+'.join(sorted(self.hotkey))}", flush=True)

        mouse_listener = None
        if self.forward_mouse:
            mouse_listener = mouse.Listener(
                on_move=self.on_mouse_move,
                on_click=self.on_mouse_click,
                on_scroll=self.on_mouse_scroll,
                suppress=self.suppress_mouse,
            )
            mouse_listener.start()

        with keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release,
            suppress=self.suppress_keyboard,
        ) as listener:
            listener.join()

        if mouse_listener:
            mouse_listener.stop()

        self.close_socket()


class HotkeyRecorder(tk.Toplevel):
    def __init__(self, parent, initial_hotkey, default_hotkey, title="Record Hotkey"):
        super().__init__(parent)
        self.parent = parent
        self.title("Record Hotkey")
        self.geometry("420x220")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.active_tokens = set()
        self.recorded_tokens = set(initial_hotkey)
        self.default_hotkey = set(default_hotkey)
        self.dialog_title = title
        self.result = None

        self.display_var = tk.StringVar(value=format_hotkey(self.recorded_tokens))
        self.status_var = tk.StringVar(value="Press the key combination you want to use.")

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<KeyPress>", self.on_key_press)
        self.bind("<KeyRelease>", self.on_key_release)
        self.focus_force()

    def create_widgets(self):
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)

        ttk.Label(root, text=self.dialog_title, font=("TkDefaultFont", 16, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(root, textvariable=self.status_var).grid(row=1, column=0, sticky="w", pady=(6, 14))

        display = ttk.Label(root, textvariable=self.display_var, font=("TkDefaultFont", 22, "bold"))
        display.grid(row=2, column=0, sticky="ew", pady=(0, 16))

        buttons = ttk.Frame(root)
        buttons.grid(row=3, column=0, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="↺ Reset", command=self.reset).grid(row=0, column=1, padx=(0, 8), ipadx=8, ipady=6)
        ttk.Button(buttons, text="Cancel", command=self.cancel).grid(row=0, column=2, padx=(0, 8), ipadx=8, ipady=6)
        ttk.Button(buttons, text="✓ Save", command=self.save).grid(row=0, column=3, ipadx=12, ipady=6)

    def on_key_press(self, event):
        token = tk_keysym_to_hotkey_token(event.keysym)
        if not token:
            return

        self.active_tokens.add(token)
        self.recorded_tokens = set(self.active_tokens)
        self.refresh_display()

    def on_key_release(self, event):
        token = tk_keysym_to_hotkey_token(event.keysym)
        if token:
            self.active_tokens.discard(token)

    def refresh_display(self):
        if self.recorded_tokens:
            self.display_var.set(format_hotkey(self.recorded_tokens))
            self.status_var.set("Release the keys, then Save.")
        else:
            self.display_var.set("Press keys...")
            self.status_var.set("Press the key combination you want to use.")

    def reset(self):
        self.active_tokens.clear()
        self.recorded_tokens = set(self.default_hotkey)
        self.refresh_display()

    def save(self):
        if not self.recorded_tokens:
            messagebox.showerror("Record Hotkey", "Please press a key combination first.")
            return
        self.result = set(self.recorded_tokens)
        self.close()

    def cancel(self):
        self.result = None
        self.close()

    def close(self):
        self.grab_release()
        self.destroy()


class MacGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CarrotKeyboard Mac")
        self.geometry("760x660")
        self.minsize(700, 620)

        self.process = None
        self.output_queue = queue.Queue()
        self.config = load_config()
        config_windows_hotkey = self.config.get("windows_hotkey", DEFAULT_WINDOWS_HOTKEY)
        config_android_hotkey = self.config.get("android_hotkey", DEFAULT_ANDROID_HOTKEY)
        config_android_rotate_hotkey = self.config.get("android_rotate_hotkey", DEFAULT_ANDROID_ROTATE_HOTKEY)
        try:
            windows_hotkey_tokens = parse_hotkey(config_windows_hotkey)
        except ValueError:
            config_windows_hotkey = DEFAULT_WINDOWS_HOTKEY
            windows_hotkey_tokens = parse_hotkey(DEFAULT_WINDOWS_HOTKEY)
        try:
            android_hotkey_tokens = parse_hotkey(config_android_hotkey)
        except ValueError:
            config_android_hotkey = DEFAULT_ANDROID_HOTKEY
            android_hotkey_tokens = parse_hotkey(DEFAULT_ANDROID_HOTKEY)
        try:
            android_rotate_hotkey_tokens = parse_hotkey(config_android_rotate_hotkey)
        except ValueError:
            config_android_rotate_hotkey = DEFAULT_ANDROID_ROTATE_HOTKEY
            android_rotate_hotkey_tokens = parse_hotkey(DEFAULT_ANDROID_ROTATE_HOTKEY)

        self.target_var = tk.StringVar(value=self.config.get("target", "Windows PC"))
        self.windows_host_var = tk.StringVar(value=self.config.get("windows_host", self.config.get("host", "")))
        self.android_host_var = tk.StringVar(value=self.config.get("android_host", ""))
        self.port_var = tk.StringVar(value=str(self.config.get("port", DEFAULT_PORT)))
        self.suppress_keyboard_var = tk.BooleanVar(value=bool(self.config.get("suppress_keyboard", True)))
        self.forward_mouse_var = tk.BooleanVar(value=bool(self.config.get("forward_mouse", True)))
        self.suppress_mouse_var = tk.BooleanVar(value=bool(self.config.get("suppress_mouse", False)))
        self.auto_start_var = tk.BooleanVar(value=bool(self.config.get("auto_start", False)))
        self.windows_hotkey_var = tk.StringVar(value=config_windows_hotkey)
        self.windows_hotkey_display_var = tk.StringVar(value=format_hotkey(windows_hotkey_tokens))
        self.android_hotkey_var = tk.StringVar(value=config_android_hotkey)
        self.android_hotkey_display_var = tk.StringVar(value=format_hotkey(android_hotkey_tokens))
        self.android_rotate_hotkey_var = tk.StringVar(value=config_android_rotate_hotkey)
        self.android_rotate_hotkey_display_var = tk.StringVar(value=format_hotkey(android_rotate_hotkey_tokens))
        self.status_var = tk.StringVar(value="Stopped")
        self.gui_pressed = set()
        self.hotkey_armed = True
        self.hotkey_listener = None
        self.recording_hotkey = False

        self.create_widgets()
        self.bind_config_saves()
        self.start_hotkey_listener()
        self.after(100, self.drain_output)
        self.after(500, self.maybe_auto_start)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        style = ttk.Style(self)
        style.configure("Action.TButton", font=("TkDefaultFont", 14, "bold"), padding=(18, 12))
        style.configure("SecondaryAction.TButton", font=("TkDefaultFont", 12), padding=(14, 10))

        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(10, weight=1)

        ttk.Label(root, text="CarrotKeyboard Mac", font=("TkDefaultFont", 18, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(root, text="Send this Mac keyboard and mouse to Windows or Android.").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(2, 14)
        )

        ttk.Label(root, text="Windows PC IP").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.windows_host_var).grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=4
        )

        ttk.Label(root, text="Android Phone IP").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.android_host_var).grid(
            row=3, column=1, columnspan=2, sticky="ew", pady=4
        )

        ttk.Label(root, text="Port").grid(row=4, column=0, sticky="w", pady=4)
        options = ttk.Frame(root)
        options.grid(row=4, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Entry(options, textvariable=self.port_var, width=10).pack(side="left")
        ttk.Checkbutton(
            options,
            text="Block keys on Mac while forwarding",
            variable=self.suppress_keyboard_var,
        ).pack(side="left", padx=(16, 0))

        mouse_options = ttk.Frame(root)
        mouse_options.grid(row=5, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Checkbutton(
            mouse_options,
            text="Forward mouse to target",
            variable=self.forward_mouse_var,
        ).pack(side="left")
        ttk.Checkbutton(
            mouse_options,
            text="Block mouse on Mac",
            variable=self.suppress_mouse_var,
        ).pack(side="left", padx=(16, 0))
        ttk.Checkbutton(
            mouse_options,
            text="Auto Start",
            variable=self.auto_start_var,
            command=self.save_current_config,
        ).pack(side="left", padx=(16, 0))

        ttk.Label(root, text="Windows hotkey").grid(row=6, column=0, sticky="w", pady=4)
        windows_hotkey_frame = ttk.Frame(root)
        windows_hotkey_frame.grid(row=6, column=1, columnspan=2, sticky="ew", pady=4)
        windows_hotkey_frame.columnconfigure(0, weight=1)
        ttk.Label(
            windows_hotkey_frame,
            textvariable=self.windows_hotkey_display_var,
            font=("TkDefaultFont", 13, "bold"),
            relief="sunken",
            padding=(10, 6),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(windows_hotkey_frame, text="● Record", command=self.record_windows_hotkey).grid(
            row=0, column=1, padx=(8, 0), ipadx=8, ipady=3
        )

        ttk.Label(root, text="Android hotkey").grid(row=7, column=0, sticky="w", pady=4)
        android_hotkey_frame = ttk.Frame(root)
        android_hotkey_frame.grid(row=7, column=1, columnspan=2, sticky="ew", pady=4)
        android_hotkey_frame.columnconfigure(0, weight=1)
        ttk.Label(
            android_hotkey_frame,
            textvariable=self.android_hotkey_display_var,
            font=("TkDefaultFont", 13, "bold"),
            relief="sunken",
            padding=(10, 6),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(android_hotkey_frame, text="● Record", command=self.record_android_hotkey).grid(
            row=0, column=1, padx=(8, 0), ipadx=8, ipady=3
        )

        ttk.Label(root, text="Android rotate hotkey").grid(row=8, column=0, sticky="w", pady=4)
        android_rotate_hotkey_frame = ttk.Frame(root)
        android_rotate_hotkey_frame.grid(row=8, column=1, columnspan=2, sticky="ew", pady=4)
        android_rotate_hotkey_frame.columnconfigure(0, weight=1)
        ttk.Label(
            android_rotate_hotkey_frame,
            textvariable=self.android_rotate_hotkey_display_var,
            font=("TkDefaultFont", 13, "bold"),
            relief="sunken",
            padding=(10, 6),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(android_rotate_hotkey_frame, text="● Record", command=self.record_android_rotate_hotkey).grid(
            row=0, column=1, padx=(8, 0), ipadx=8, ipady=3
        )

        ttk.Label(root, textvariable=self.status_var).grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(8, 8)
        )

        self.log_text = tk.Text(root, height=9, wrap="word", state="disabled")
        self.log_text.grid(row=10, column=0, columnspan=3, sticky="nsew")

        buttons = ttk.Frame(root)
        buttons.grid(row=11, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        buttons.columnconfigure(0, weight=1)
        self.windows_button = ttk.Button(
            buttons,
            text="▶ Windows",
            command=lambda: self.toggle_target("Windows PC"),
            style="Action.TButton",
        )
        self.windows_button.grid(row=0, column=1)
        self.android_button = ttk.Button(
            buttons,
            text="▶ Android",
            command=lambda: self.toggle_target("Android Phone"),
            style="Action.TButton",
        )
        self.android_button.grid(row=0, column=2, padx=(10, 0))
        ttk.Button(buttons, text="⌫ Clear Log", command=self.clear_log, style="SecondaryAction.TButton").grid(
            row=0, column=3, padx=(10, 0)
        )

    def build_command(self, target=None):
        target = target or self.target_var.get()
        host = self.get_host_for_target(target)
        port = self.port_var.get().strip()
        if not host:
            raise ValueError(f"{target} IP is required.")
        if not port.isdigit():
            raise ValueError("Port must be a number.")
        if target == "Android Phone":
            hotkey = parse_hotkey(self.android_hotkey_var.get())
            rotate_hotkey = parse_hotkey(self.android_rotate_hotkey_var.get())
        else:
            hotkey = parse_hotkey(self.windows_hotkey_var.get())
            rotate_hotkey = set()

        command = [
            sys.executable,
            "-u",
            os.path.abspath(__file__),
            "--send",
            "--host",
            host,
            "--port",
            port,
            "--target",
            target,
        ]
        if not self.suppress_keyboard_var.get():
            command.append("--no-suppress")
        if not self.forward_mouse_var.get():
            command.append("--no-mouse")
        if self.suppress_mouse_var.get():
            command.append("--suppress-mouse")
        command += ["--hotkey", serialize_hotkey(hotkey)]
        if rotate_hotkey:
            command += ["--rotate-hotkey", serialize_hotkey(rotate_hotkey)]
        return command

    def bind_config_saves(self):
        for variable in (
            self.windows_host_var,
            self.android_host_var,
            self.target_var,
            self.port_var,
            self.windows_hotkey_var,
            self.android_hotkey_var,
            self.android_rotate_hotkey_var,
            self.suppress_keyboard_var,
            self.forward_mouse_var,
            self.suppress_mouse_var,
            self.auto_start_var,
        ):
            variable.trace_add("write", lambda *_: self.save_current_config())

    def current_config(self):
        return {
            "windows_host": self.windows_host_var.get().strip(),
            "android_host": self.android_host_var.get().strip(),
            "target": self.target_var.get(),
            "port": self.port_var.get().strip() or DEFAULT_PORT,
            "suppress_keyboard": bool(self.suppress_keyboard_var.get()),
            "forward_mouse": bool(self.forward_mouse_var.get()),
            "suppress_mouse": bool(self.suppress_mouse_var.get()),
            "auto_start": bool(self.auto_start_var.get()),
            "windows_hotkey": self.windows_hotkey_var.get(),
            "android_hotkey": self.android_hotkey_var.get(),
            "android_rotate_hotkey": self.android_rotate_hotkey_var.get(),
        }

    def save_current_config(self):
        try:
            save_config(self.current_config())
        except OSError as exc:
            self.append_log(f"Could not save config: {exc}")

    def maybe_auto_start(self):
        if not self.auto_start_var.get():
            return
        if self.process and self.process.poll() is None:
            return
        if not self.get_host_for_target(self.target_var.get()):
            self.append_log("Auto Start skipped: missing target IP.")
            return
        self.append_log("Auto Start enabled.")
        self.toggle_target(self.target_var.get())

    def get_host_for_target(self, target):
        if target == "Android Phone":
            return self.android_host_var.get().strip()
        return self.windows_host_var.get().strip()

    def set_windows_hotkey(self, tokens):
        self.windows_hotkey_var.set(serialize_hotkey(tokens))
        self.windows_hotkey_display_var.set(format_hotkey(tokens))
        self.gui_pressed.clear()
        self.hotkey_armed = True
        self.save_current_config()

    def set_android_hotkey(self, tokens):
        self.android_hotkey_var.set(serialize_hotkey(tokens))
        self.android_hotkey_display_var.set(format_hotkey(tokens))
        self.gui_pressed.clear()
        self.hotkey_armed = True
        self.save_current_config()

    def set_android_rotate_hotkey(self, tokens):
        self.android_rotate_hotkey_var.set(serialize_hotkey(tokens))
        self.android_rotate_hotkey_display_var.set(format_hotkey(tokens))
        self.gui_pressed.clear()
        self.hotkey_armed = True
        self.save_current_config()

    def record_windows_hotkey(self):
        self.record_target_hotkey(
            self.windows_hotkey_var,
            self.set_windows_hotkey,
            DEFAULT_WINDOWS_HOTKEY,
            "Record Windows Hotkey",
        )

    def record_android_hotkey(self):
        self.record_target_hotkey(
            self.android_hotkey_var,
            self.set_android_hotkey,
            DEFAULT_ANDROID_HOTKEY,
            "Record Android Hotkey",
        )

    def record_android_rotate_hotkey(self):
        self.record_target_hotkey(
            self.android_rotate_hotkey_var,
            self.set_android_rotate_hotkey,
            DEFAULT_ANDROID_ROTATE_HOTKEY,
            "Record Android Rotate Hotkey",
        )

    def record_target_hotkey(self, variable, setter, default_value, title):
        try:
            current_hotkey = parse_hotkey(variable.get())
        except ValueError:
            current_hotkey = parse_hotkey(default_value)
        default_hotkey = parse_hotkey(default_value)

        self.recording_hotkey = True
        recorder = HotkeyRecorder(self, current_hotkey, default_hotkey, title)
        self.wait_window(recorder)
        self.recording_hotkey = False
        self.gui_pressed.clear()
        self.hotkey_armed = True

        if recorder.result:
            setter(recorder.result)

    def toggle_target(self, target):
        if self.process and self.process.poll() is None:
            if self.target_var.get() == target:
                self.stop_process()
                return
            self.stop_process()

        self.target_var.set(target)
        try:
            command = self.build_command(target)
        except ValueError as exc:
            messagebox.showerror("CarrotKeyboard Mac", str(exc))
            return

        self.append_log("$ " + " ".join(command))
        self.save_current_config()
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self.read_process_output, daemon=True).start()
        self.status_var.set(f"Running: {target}")
        self.update_target_buttons()

    def start_hotkey_listener(self):
        self.hotkey_listener = keyboard.Listener(
            on_press=self.on_gui_hotkey_press,
            on_release=self.on_gui_hotkey_release,
            suppress=False,
        )
        self.hotkey_listener.start()

    def on_gui_hotkey_press(self, key):
        if self.recording_hotkey:
            return

        token = key_to_hotkey_token(key)
        if token:
            self.gui_pressed.add(token)

        try:
            windows_hotkey = parse_hotkey(self.windows_hotkey_var.get())
        except ValueError:
            windows_hotkey = set()
        try:
            android_hotkey = parse_hotkey(self.android_hotkey_var.get())
        except ValueError:
            android_hotkey = set()

        if self.hotkey_armed and windows_hotkey and windows_hotkey.issubset(self.gui_pressed):
            self.hotkey_armed = False
            self.after(0, lambda: self.toggle_target("Windows PC"))
        elif self.hotkey_armed and android_hotkey and android_hotkey.issubset(self.gui_pressed):
            self.hotkey_armed = False
            self.after(0, lambda: self.toggle_target("Android Phone"))

    def on_gui_hotkey_release(self, key):
        if self.recording_hotkey:
            return

        token = key_to_hotkey_token(key)
        if token:
            self.gui_pressed.discard(token)

        target_hotkeys = []
        for variable in (self.windows_hotkey_var, self.android_hotkey_var):
            try:
                target_hotkeys.append(parse_hotkey(variable.get()))
            except ValueError:
                pass

        if not any(hotkey and hotkey.issubset(self.gui_pressed) for hotkey in target_hotkeys):
            self.hotkey_armed = True

    def toggle(self):
        self.toggle_target(self.target_var.get())

    def stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        self.status_var.set("Stopped")
        self.update_target_buttons()
        self.append_log("Stopped.")

    def read_process_output(self):
        if not self.process or not self.process.stdout:
            return
        for line in self.process.stdout:
            self.output_queue.put(line.rstrip())
        code = self.process.wait()
        self.output_queue.put(f"Process exited with code {code}.")

    def drain_output(self):
        while True:
            try:
                line = self.output_queue.get_nowait()
            except queue.Empty:
                break
            self.append_log(line)
            if line.startswith("Process exited"):
                self.process = None
                self.status_var.set("Stopped")
                self.update_target_buttons()
        self.after(100, self.drain_output)

    def update_target_buttons(self):
        running = bool(self.process and self.process.poll() is None)
        active = self.target_var.get()
        if hasattr(self, "windows_button"):
            self.windows_button.configure(text="■ Windows" if running and active == "Windows PC" else "▶ Windows")
        if hasattr(self, "android_button"):
            self.android_button.configure(text="■ Android" if running and active == "Android Phone" else "▶ Android")

    def append_log(self, line):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def on_close(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.stop_process()
        self.destroy()


def parse_args():
    parser = argparse.ArgumentParser(description="Mac sender for CarrotKeyboard.")
    parser.add_argument("--send", action="store_true", help="Run sender without GUI.")
    parser.add_argument("--host", help="Windows PC IP address.")
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--no-suppress", action="store_true")
    parser.add_argument("--no-mouse", action="store_true", help="Do not forward mouse events.")
    parser.add_argument("--suppress-mouse", action="store_true", help="Block mouse events on Mac.")
    parser.add_argument("--hotkey", default=DEFAULT_HOTKEY, help="Stop hotkey, such as cmd+option+control+q.")
    parser.add_argument(
        "--rotate-hotkey",
        default="",
        help="Android-only hotkey that toggles phone orientation while Android sender is active.",
    )
    parser.add_argument("--target", default="Windows PC", help="Target label used in logs.")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.send:
        if not args.host:
            print("--host is required in sender mode.")
            sys.exit(1)
        try:
            hotkey = parse_hotkey(args.hotkey)
        except ValueError as exc:
            print(f"Invalid hotkey: {exc}")
            sys.exit(1)
        try:
            rotate_hotkey = parse_hotkey(args.rotate_hotkey) if args.rotate_hotkey else set()
        except ValueError as exc:
            print(f"Invalid rotate hotkey: {exc}")
            sys.exit(1)
        MacSender(
            args.host,
            args.port,
            suppress_keyboard=not args.no_suppress,
            forward_mouse=not args.no_mouse,
            suppress_mouse=args.suppress_mouse,
            hotkey=hotkey,
            target_name=args.target,
            rotate_hotkey=rotate_hotkey,
        ).run()
        return

    MacGui().mainloop()


if __name__ == "__main__":
    main()
