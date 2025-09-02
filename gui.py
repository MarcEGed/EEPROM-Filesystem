"""
GUI for arduinoDrive.ino
allows for a more comfortable use of the arduino filesystem
Requires: pip install pyserial
"""

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from tkinter.scrolledtext import ScrolledText
import serial
import time

#Config
PORT_DEFAULT = "COM9"
BAUD = 9600
FILE_COUNT = 3
READ_TIMEOUT = 0.5

#Utilities
def escape_for_arduino(s: str) -> str:
    s = s.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r')
    return s

def unescape_from_arduino(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == 'n': out.append('\n')
            elif nxt == 'r': out.append('\r')
            elif nxt == '\\': out.append('\\')
            else: out.append(nxt)
            i += 2
        else:
            out.append(s[i])
            i += 1
    return ''.join(out)

def bytes_to_text(b: bytes) -> str:
    return ''.join(chr(x) if 32 <= x <= 126 or x in (10,) else '' for x in b)

#Serial Client
class SerialClient:
    def __init__(self, port=PORT_DEFAULT, baud=BAUD, timeout=0.1):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = None

    def connect(self):
        if self.ser:
            self.close()
        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
        time.sleep(0.15)
        self.ser.reset_input_buffer()

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def is_open(self):
        return self.ser is not None and self.ser.is_open

    def send_line(self, line: str) -> bytes:
        if not self.is_open(): return b''
        self.ser.reset_input_buffer()
        self.ser.write((line + '\n').encode('utf-8', errors='ignore'))
        buf, start = b'', time.time()
        while time.time() - start < READ_TIMEOUT:
            avail = self.ser.in_waiting
            if avail: buf += self.ser.read(avail)
            else: time.sleep(0.01)
        return buf

#GUI
class ModernEEPROM(tk.Tk):
    BG = "#111217"
    FG = "#E6EEF3"
    PANEL = "#14161A"
    ACCENT = "#2A9D8F"
    MUTED = "#9AA5AD"

    def __init__(self):
        super().__init__()
        self.title("EEPROM Explorer (Dark)")
        self.geometry("900x540")
        self.configure(bg=self.BG)

        self.client = SerialClient(PORT_DEFAULT)
        self._build_style()
        self._build_ui()
        try:
            self.client.connect()
            self._set_status(f"Connected {self.client.port}")
            self.refresh_files()
        except:
            self._set_status("Not connected")

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.FG)
        style.configure("TButton", background=self.PANEL, foreground=self.FG, borderwidth=0)
        style.map("TButton", background=[('active', self.ACCENT)])
        style.configure("Treeview",
                        background=self.PANEL,
                        foreground=self.FG,
                        fieldbackground=self.PANEL,
                        rowheight=24)
        style.configure("Treeview.Heading",
                        background=self.BG,
                        foreground=self.MUTED)
        style.map("Treeview",
                  background=[('selected', self.ACCENT)],
                  foreground=[('selected', self.BG)])
        style.configure("Status.TLabel", background=self.BG, foreground=self.MUTED)

    def _build_ui(self):
        # Top toolbar
        top = ttk.Frame(self)
        top.pack(side='top', fill='x', padx=10, pady=6)
        ttk.Label(top, text="Port:").pack(side='left')
        self.port_var = tk.StringVar(value=PORT_DEFAULT)
        ttk.Entry(top, textvariable=self.port_var, width=10).pack(side='left', padx=6)
        self.btn_connect = ttk.Button(top, text="Connect", command=self.toggle_connect)
        self.btn_connect.pack(side='left')
        ttk.Button(top, text="Refresh", command=self.refresh_files).pack(side='left', padx=6)
        self.status_lbl = ttk.Label(top, text="Not connected", style="Status.TLabel")
        self.status_lbl.pack(side='left', padx=10)

        # Main panels
        main = ttk.Frame(self)
        main.pack(side='top', fill='both', expand=True, padx=10, pady=6)

        # Left: file list
        left_frame = ttk.Frame(main, width=250)
        left_frame.pack(side='left', fill='y')
        columns = ("name", "size")
        self.tree = ttk.Treeview(left_frame, columns=columns, show='headings', selectmode='browse')
        self.tree.heading('name', text='Name')
        self.tree.heading('size', text='Size')
        self.tree.column('name', width=180, anchor='w')
        self.tree.column('size', width=60, anchor='center')
        self.tree.pack(fill='y', expand=True)
        self.tree.bind("<Double-1>", lambda e: self.read_selected())

        # Buttons under tree
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(pady=6)
        ttk.Button(btn_frame, text="Read", command=self.read_selected).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Write", command=self.write_selected).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Rename", command=self.rename_selected).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Delete", command=self.delete_selected).pack(side='left', padx=2)

        # Right: editor
        right_frame = ttk.Frame(main)
        right_frame.pack(side='left', fill='both', expand=True, padx=(12,0))
        self.filename_label = ttk.Label(right_frame, text="No file selected")
        self.filename_label.pack(anchor='w')
        self.editor = ScrolledText(right_frame, wrap='word',
                                   bg=self.PANEL, fg=self.FG, insertbackground=self.FG,
                                   relief='flat')
        self.editor.pack(fill='both', expand=True, pady=(6,0))

        # Bottom status
        bottom = ttk.Frame(self)
        bottom.pack(side='bottom', fill='x', padx=10, pady=6)
        self.footer_lbl = ttk.Label(bottom, text="Ready", style="Status.TLabel")
        self.footer_lbl.pack(side='left')

    #Status
    def _set_status(self, txt):
        self.status_lbl.config(text=txt)
        self.footer_lbl.config(text=txt)

    #Connection
    def toggle_connect(self):
        if self.client.is_open():
            self.client.close()
            self.btn_connect.config(text="Connect")
            self._set_status("Disconnected")
        else:
            port = self.port_var.get().strip()
            if not port:
                messagebox.showwarning("Port required", "Enter serial port")
                return
            self.client.port = port
            try:
                self.client.connect()
                self._set_status(f"Connected {port}")
                self.btn_connect.config(text="Disconnect")
                self.refresh_files()
            except Exception as e:
                messagebox.showerror("Failed", f"Could not open {port}\n{e}")
                self._set_status("Not connected")

    #File Operations
    def refresh_files(self):
        if not self.client.is_open():
            return
        raw = self.client.send_line("LIST")
        txt = bytes_to_text(raw)
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        self.tree.delete(*self.tree.get_children())
        for i in range(FILE_COUNT):
            label = f"(empty)"
            size = 0
            for ln in lines:
                if ln.startswith(f"{i+1}:"):
                    try:
                        name = ln.split(':',1)[1].split('(')[0].strip()
                        s = int(ln.split('(')[1].split()[0])
                        label = name
                        size = s
                    except: pass
                    break
            self.tree.insert('', 'end', iid=str(i+1), values=(label, f"{size} B"))

    def _get_selected_index(self):
        sel = self.tree.selection()
        if not sel: return None
        return int(sel[0])

    def read_selected(self):
        idx = self._get_selected_index()
        if idx is None or not self.client.is_open(): return
        raw = self.client.send_line(f"READ {idx}")
        text = unescape_from_arduino(bytes_to_text(raw))
        self.editor.delete('1.0','end')
        self.editor.insert('1.0', text)
        try: name = self.tree.set(str(idx), 'name'); self.filename_label.config(text=f"{idx}: {name}")
        except: self.filename_label.config(text=f"{idx}")

    def write_selected(self):
        idx = self._get_selected_index()
        if idx is None or not self.client.is_open(): return
        text = self.editor.get('1.0','end').rstrip('\n')
        escaped = escape_for_arduino(text)
        self.client.send_line(f"WRITE {idx} {escaped}")
        time.sleep(0.02)
        self._set_status(f"Wrote file {idx}")
        self.refresh_files()

    def rename_selected(self):
        idx = self._get_selected_index()
        if idx is None or not self.client.is_open(): return
        newname = simpledialog.askstring("Rename", "New filename (max 9 chars)")
        if not newname: return
        self.client.send_line(f"WRITE_NAME {idx} {newname[:9]}")
        time.sleep(0.02)
        self._set_status(f"Renamed file {idx}")
        self.refresh_files()

    def delete_selected(self):
        idx = self._get_selected_index()
        if idx is None or not self.client.is_open(): return
        if not messagebox.askyesno("Delete", f"Delete file {idx}?"): return
        self.client.send_line(f"DELETE {idx}")
        self.editor.delete('1.0','end')
        self._set_status(f"Deleted file {idx}")
        self.refresh_files()

if __name__ == "__main__":
    app = ModernEEPROM()
    app.mainloop()
