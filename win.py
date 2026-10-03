#!/usr/bin/env python3
import argparse
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from pynput import keyboard, mouse
except ImportError:
    print("Missing dependency: pynput")
    print("Install it with: python -m pip install -r requirements.txt")
    sys.exit(1)


DEFAULT_PORT = "50505"


def safe_key(name):
    return getattr(keyboard.Key, name, None)


SPECIAL_KEY_NAMES = (
    "alt",
    "alt_l",
    "alt_r",
    "backspace",
    "caps_lock",
    "cmd",
    "cmd_l",
    "cmd_r",
    "ctrl",
    "ctrl_l",
    "ctrl_r",
    "delete",
    "down",
    "end",
    "enter",
    "esc",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
    "home",
    "insert",
    "left",
    "menu",
    "num_lock",
    "page_down",
    "page_up",
    "pause",
    "print_screen",
    "right",
    "scroll_lock",
    "shift",
    "shift_l",
    "shift_r",
    "space",
    "tab",
    "up",
)

SPECIAL_KEYS = {
    name: key
    for name in SPECIAL_KEY_NAMES
    for key in (safe_key(name),)
    if key is not None
}

MAC_TO_WINDOWS_KEY = {
    "cmd": "ctrl",
    "cmd_l": "ctrl_l",
    "cmd_r": "ctrl_r",
}


def get_lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def payload_to_key(payload):
    if payload.get("type") == "char":
        char = payload.get("char")
        if char is not None:
            return keyboard.KeyCode.from_char(char)

        vk = payload.get("vk")
        if vk is not None:
            return keyboard.KeyCode.from_vk(vk)

    if payload.get("type") == "special":
        name = MAC_TO_WINDOWS_KEY.get(payload.get("name"), payload.get("name"))
        return SPECIAL_KEYS.get(name)

    return None


def get_screen_size():
    root = tk.Tk()
    root.withdraw()
    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
    root.destroy()
    return max(width, 1), max(height, 1)


def payload_to_button(name):
    return getattr(mouse.Button, name or "left", mouse.Button.left)


class JsonLineReader:
    def __init__(self, sock):
        self.sock = sock
        self.file = sock.makefile("r", encoding="utf-8", newline="\n")

    def read(self):
        line = self.file.readline()
        if not line:
            return None
        return json.loads(line)

    def close(self):
        try:
            self.file.close()
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class WindowsReceiver:
    def __init__(self, host, port):
        self.host = host
        self.port = int(port)
        self.keyboard_controller = keyboard.Controller()
        self.mouse_controller = mouse.Controller()
        self.pressed_keys = set()
        self.pressed_buttons = set()
        self.screen_width, self.screen_height = get_screen_size()

    def release_all(self):
        for key in list(self.pressed_keys):
            try:
                self.keyboard_controller.release(key)
            except Exception:
                pass
            self.pressed_keys.discard(key)

        for button in list(self.pressed_buttons):
            try:
                self.mouse_controller.release(button)
            except Exception:
                pass
            self.pressed_buttons.discard(button)

    def handle_event(self, event):
        if event.get("device", "keyboard") == "mouse":
            self.handle_mouse_event(event)
            return

        self.handle_keyboard_event(event)

    def handle_keyboard_event(self, event):
        key = payload_to_key(event.get("key", {}))
        if key is None:
            return

        action = event.get("action")
        try:
            if action == "press":
                self.keyboard_controller.press(key)
                self.pressed_keys.add(key)
            elif action == "release":
                self.keyboard_controller.release(key)
                self.pressed_keys.discard(key)
        except Exception as exc:
            print(f"Could not replay key {event}: {exc}", flush=True)

    def handle_mouse_event(self, event):
        action = event.get("action")
        try:
            if action in {"move", "press", "release"}:
                x_ratio = float(event.get("x_ratio", 0.0))
                y_ratio = float(event.get("y_ratio", 0.0))
                x = round(max(0.0, min(1.0, x_ratio)) * (self.screen_width - 1))
                y = round(max(0.0, min(1.0, y_ratio)) * (self.screen_height - 1))
                self.mouse_controller.position = (x, y)

            if action == "press":
                button = payload_to_button(event.get("button"))
                self.mouse_controller.press(button)
                self.pressed_buttons.add(button)
            elif action == "release":
                button = payload_to_button(event.get("button"))
                self.mouse_controller.release(button)
                self.pressed_buttons.discard(button)
            elif action == "scroll":
                self.mouse_controller.scroll(int(event.get("dx", 0)), int(event.get("dy", 0)))
        except Exception as exc:
            print(f"Could not replay mouse event {event}: {exc}", flush=True)

    def serve_client(self, conn, address):
        print(f"Mac connected from {address[0]}:{address[1]}", flush=True)
        reader = JsonLineReader(conn)
        try:
            while True:
                event = reader.read()
                if event is None:
                    break
                self.handle_event(event)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Client disconnected: {exc}", flush=True)
        finally:
            self.release_all()
            reader.close()
            print("Mac disconnected. Waiting for another connection...", flush=True)

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen(1)
            print(f"Listening on {self.host}:{self.port}", flush=True)
            print(f"This PC IP: {get_lan_ip()}", flush=True)
            print(f"Screen size: {self.screen_width}x{self.screen_height}", flush=True)
            print("Run mac.py on the Mac and connect to this IP.", flush=True)

            while True:
                conn, address = server.accept()
                self.serve_client(conn, address)


class WindowsGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CarrotKeyboard Windows")
        self.geometry("560x390")
        self.minsize(520, 360)

        self.process = None
        self.output_queue = queue.Queue()
        self.port_var = tk.StringVar(value=DEFAULT_PORT)
        self.ip_var = tk.StringVar(value=get_lan_ip())
        self.status_var = tk.StringVar(value="Stopped")

        self.create_widgets()
        self.after(100, self.drain_output)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        style = ttk.Style(self)
        style.configure("Action.TButton", font=("TkDefaultFont", 14, "bold"), padding=(18, 12))
        style.configure("SecondaryAction.TButton", font=("TkDefaultFont", 12), padding=(14, 10))

        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(5, weight=1)

        ttk.Label(root, text="CarrotKeyboard Windows", font=("TkDefaultFont", 18, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(root, text="Receive keyboard and mouse input from the Mac.").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(2, 14)
        )

        ttk.Label(root, text="This PC IP").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.ip_var, state="readonly").grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=4
        )

        ttk.Label(root, text="Port").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.port_var, width=10).grid(
            row=3, column=1, sticky="w", pady=4
        )

        ttk.Label(root, textvariable=self.status_var).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(8, 8)
        )

        self.log_text = tk.Text(root, height=9, wrap="word", state="disabled")
        self.log_text.grid(row=5, column=0, columnspan=3, sticky="nsew")

        buttons = ttk.Frame(root)
        buttons.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        buttons.columnconfigure(0, weight=1)
        self.toggle_button = ttk.Button(buttons, text="▶ Start", command=self.toggle, style="Action.TButton")
        self.toggle_button.grid(row=0, column=1)
        ttk.Button(buttons, text="⌫ Clear Log", command=self.clear_log, style="SecondaryAction.TButton").grid(
            row=0, column=2, padx=(10, 0)
        )

    def build_command(self):
        port = self.port_var.get().strip()
        if not port.isdigit():
            raise ValueError("Port must be a number.")
        return [sys.executable, "-u", os.path.abspath(__file__), "--receive", "--port", port]

    def toggle(self):
        if self.process and self.process.poll() is None:
            self.stop_process()
            return

        try:
            command = self.build_command()
        except ValueError as exc:
            messagebox.showerror("CarrotKeyboard Windows", str(exc))
            return

        self.append_log("$ " + " ".join(command))
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self.read_process_output, daemon=True).start()
        self.status_var.set("Running")
        self.toggle_button.configure(text="■ Stop")

    def stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        self.status_var.set("Stopped")
        self.toggle_button.configure(text="▶ Start")
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
                self.toggle_button.configure(text="▶ Start")
        self.after(100, self.drain_output)

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
        self.stop_process()
        self.destroy()


def parse_args():
    parser = argparse.ArgumentParser(description="Windows receiver for CarrotKeyboard.")
    parser.add_argument("--receive", action="store_true", help="Run receiver without GUI.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=DEFAULT_PORT)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.receive:
        WindowsReceiver(args.host, args.port).run()
        return

    WindowsGui().mainloop()


if __name__ == "__main__":
    main()
