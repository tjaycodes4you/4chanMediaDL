import asyncio
import ctypes
import logging
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from main import load_proxy_lines, run, set_proxies
from utils.root import get_project_root


def dbg(msg):
    try:
        with open(str(Path(get_project_root()) / 'debug.log'), 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except Exception:
        pass

BG = '#04040a'
PANEL = '#0a0a14'
NEON_GREEN = '#9aff18'
CYAN = '#00e5ff'
MAGENTA = '#ff2eb9'
RED = '#ff2e4c'
DIM = '#5a7a66'
TEXT = '#d8f5e3'

TITLE_FONT = ('Bahnschrift', 16, 'bold')
MONO = ('Cascadia Mono', 10)
MONO_SMALL = ('Cascadia Mono', 9)
SECTION_FONT = ('Cascadia Mono', 10, 'bold')

LEVEL_TAGS = {
    'INFO': 'info',
    'WARNING': 'warn',
    'ERROR': 'err',
    'CRITICAL': 'err',
    'DEBUG': 'dim',
}

LOG_COLORS = {
    'info': '#7cfc9e',
    'warn': '#ffd75e',
    'err': '#ff5c7a',
    'dim': '#5a7a66',
    'head': CYAN,
}


def asset(name: str) -> str | None:
    bases = []
    if getattr(sys, 'frozen', False):
        bases.append(Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)))
        bases.append(Path(sys.executable).parent)
    bases.append(Path(__file__).parent)
    for base in bases:
        p = base / 'assets' / name
        if p.exists():
            return str(p)
    return None


PROXY_FILE = Path(get_project_root()) / 'user_data' / 'proxies.txt'


def load_saved_proxies() -> str:
    try:
        return PROXY_FILE.read_text(encoding='utf-8').strip()
    except OSError:
        return ''


def save_proxies(text: str):
    text = text.strip()
    if not text:
        return
    try:
        PROXY_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROXY_FILE.write_text(text + '\n', encoding='utf-8')
    except OSError:
        pass


def bind_drag(widget, on_press, on_motion):
    widget.bind('<Button-1>', on_press)
    widget.bind('<B1-Motion>', on_motion)
    for child in widget.winfo_children():
        bind_drag(child, on_press, on_motion)


class QueueLogHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord):
        try:
            self.q.put(('log', (record.levelname, self.format(record))))
        except Exception:
            pass


class Splash(ctk.CTkToplevel):
    def __init__(self, root):
        super().__init__(root)
        self.overrideredirect(True)
        self.configure(fg_color=BG)
        w, h = 480, 640
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f'{w}x{h}+{x}+{y}')

        self.frames = self.load_gif(asset('splash.gif'))
        self.idx = 0
        self.img_label = tk.Label(self, bg=BG, image=self.frames[0], highlightthickness=0)
        self.img_label.pack(pady=(36, 14))

        ctk.CTkLabel(self, text='4CHANMEDIA', font=('Bahnschrift', 28, 'bold'), text_color=NEON_GREEN).pack()
        ctk.CTkLabel(self, text='D O W N L O A D E R', font=('Cascadia Mono', 11, 'bold'),
                     text_color=CYAN).pack(pady=(2, 18))

        self.bar = tk.Canvas(self, height=8, bg=BG, highlightthickness=0)
        self.bar.pack(fill='x', padx=70)
        self.status = ctk.CTkLabel(self, text='INITIALIZING...', font=MONO, text_color=DIM)
        self.status.pack(pady=(12, 0))
        ctk.CTkLabel(self, text='v2.1 // neon build', font=MONO_SMALL, text_color='#2a3a2e').pack(pady=(26, 0))

        self.t = 0
        self.tick()
        self.animate_bar()
        self.cycle_status()

    def load_gif(self, path):
        im = Image.open(path)
        frames = []
        for i in range(im.n_frames):
            im.seek(i)
            frames.append(ImageTk.PhotoImage(im.convert('RGBA')))
        return frames

    def tick(self):
        if self.frames:
            self.img_label.configure(image=self.frames[self.idx])
            self.idx = (self.idx + 1) % len(self.frames)
            self.after(45, self.tick)

    def animate_bar(self):
        c = self.bar
        c.delete('all')
        w = max(c.winfo_width(), 2)
        seg = 90
        x = (self.t * 9) % (w + seg) - seg
        c.create_rectangle(0, 1, w, 7, fill='#0d1a12', outline='')
        c.create_rectangle(x, 1, x + seg, 7, fill=NEON_GREEN, outline='')
        c.create_rectangle(x + 6, 1, x + seg, 7, fill='#d4ff8a', outline='')
        c.create_line(0, 0, w, 0, fill='#1a2b3c')
        c.create_line(0, 7, w, 7, fill='#1a2b3c')
        self.t += 1
        self.after(16, self.animate_bar)

    def cycle_status(self):
        msgs = ['INITIALIZING MODULES', 'LOADING TLS STACK', 'WAKING THE CLIENT', 'ARMING DOWNLOADER']
        self.status.configure(text=msgs[(self.t // 25) % len(msgs)])
        self.after(400, self.cycle_status)


class App:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title('4chanMediaDL')
        self.q = queue.Queue()
        self.cancel = threading.Event()
        self.worker_thread = None
        self.total = 0
        self.done = 0
        self.failed = 0

        self.qh = QueueLogHandler(self.q)
        self.qh.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        self.qh.setLevel(logging.INFO)
        logging.getLogger('main').addHandler(self.qh)

        self.clover_img = None
        icon = asset('icon.ico')
        if icon:
            try:
                self.root.iconbitmap(icon)
            except Exception:
                pass
            try:
                self.clover_img = ImageTk.PhotoImage(Image.open(asset('clover.png')).resize((22, 22), Image.LANCZOS))
            except Exception:
                pass

        self.build()
        self.root.bind('<Map>', self.force_taskbar)
        self.poll()

    def build(self):
        self.root.configure(fg_color=CYAN)
        self.shell = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        self.shell.pack(fill='both', expand=True, padx=1, pady=1)

        self.build_titlebar()
        self.build_body()

    def build_titlebar(self):
        bar = ctk.CTkFrame(self.shell, fg_color='#07070d', corner_radius=0)
        bar.pack(fill='x')

        left = ctk.CTkFrame(bar, fg_color='transparent')
        left.pack(side='left', padx=(14, 0), pady=8)
        if self.clover_img:
            tk.Label(left, image=self.clover_img, bg='#07070d', highlightthickness=0).pack(side='left', padx=(0, 8))
        ctk.CTkLabel(left, text='4CHANMEDIA', font=TITLE_FONT, text_color=NEON_GREEN).pack(side='left')
        ctk.CTkLabel(left, text='DOWNLOADER', font=('Cascadia Mono', 10, 'bold'), text_color=CYAN).pack(
            side='left', padx=(8, 0), pady=(3, 0))

        right = ctk.CTkFrame(bar, fg_color='transparent')
        right.pack(side='right', padx=8, pady=6)
        self.min_btn = ctk.CTkButton(right, text='–', width=30, height=26, corner_radius=6,
                                     fg_color='transparent', hover_color='#12283c',
                                     border_width=0, text_color=TEXT, font=('Bahnschrift', 14),
                                     command=self.root.iconify)
        self.min_btn.pack(side='left', padx=2)
        self.close_btn = ctk.CTkButton(right, text='✕', width=30, height=26, corner_radius=6,
                                       fg_color='transparent', hover_color='#3a1020',
                                       border_width=0, text_color=TEXT, font=('Bahnschrift', 13),
                                       command=self.on_close)
        self.close_btn.pack(side='left', padx=(2, 0))

        self._dx = 0
        self._dy = 0
        bind_drag(bar, self.drag_start, self.drag_move)

    def drag_start(self, e):
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()

    def drag_move(self, e):
        self.root.geometry(f'+{e.x_root - self._dx}+{e.y_root - self._dy}')

    def build_body(self):
        body = ctk.CTkFrame(self.shell, fg_color=BG, corner_radius=0)
        body.pack(fill='both', expand=True, padx=18, pady=(12, 6))

        ctk.CTkLabel(body, text='// TARGET THREAD', font=SECTION_FONT, text_color=CYAN).pack(anchor='w')
        self.url_entry = ctk.CTkEntry(body, height=38, placeholder_text='https://boards.4chan.org/b/thread/1234567  (empty = site.html)',
                                      placeholder_text_color='#3a4d40', font=('Cascadia Mono', 11),
                                      border_color='#1c3a2a', text_color='#c8ffd8')
        self.url_entry.pack(fill='x', pady=(4, 14))

        ctk.CTkLabel(body, text='// OUTPUT DIRECTORY', font=SECTION_FONT, text_color=CYAN).pack(anchor='w')
        out_row = ctk.CTkFrame(body, fg_color='transparent')
        out_row.pack(fill='x', pady=(4, 16))
        self.out_entry = ctk.CTkEntry(out_row, height=38, font=('Cascadia Mono', 11),
                                      border_color='#1c3a2a', text_color='#c8ffd8')
        self.out_entry.insert(0, str(Path(get_project_root()) / 'output'))
        self.out_entry.pack(side='left', fill='x', expand=True)
        ctk.CTkButton(out_row, text='BROWSE', width=110, height=38, font=('Bahnschrift', 12, 'bold'),
                      text_color=CYAN, border_color='#12507a', fg_color='#06121e',
                      hover_color='#0a2136', command=self.browse).pack(side='left', padx=(8, 0))

        ctk.CTkLabel(body, text='// PROXY POOL — ISP / DC  (host:port:user:pass per line, or a .txt path)',
                     font=SECTION_FONT, text_color=CYAN).pack(anchor='w')
        self.proxy_box = ctk.CTkTextbox(body, height=58, font=MONO_SMALL, wrap='none',
                                        border_color='#1c3a2a', text_color='#c8ffd8',
                                        activate_scrollbars=True)
        self.proxy_box.pack(fill='x', pady=(4, 16))
        saved = load_saved_proxies()
        if saved:
            self.proxy_box.insert('1.0', saved)

        action_row = ctk.CTkFrame(body, fg_color='transparent')
        action_row.pack(fill='x', pady=(0, 14))
        self.dl_btn = ctk.CTkButton(action_row, text='▶  DOWNLOAD', height=44, font=('Bahnschrift', 15, 'bold'),
                                    text_color='#04140a', fg_color=NEON_GREEN, hover_color='#b8ff4a',
                                    border_color=NEON_GREEN, border_width=1,
                                    command=self.start)
        self.dl_btn.pack(side='left', fill='x', expand=True)
        self.cancel_btn = ctk.CTkButton(action_row, text='✕ ABORT', width=120, height=44,
                                        font=('Bahnschrift', 12, 'bold'), text_color=RED,
                                        border_color='#5a1220', fg_color='#16060c',
                                        hover_color='#2a0a14', state='disabled', command=self.stop)
        self.cancel_btn.pack(side='left', padx=(8, 0))
        ctk.CTkButton(action_row, text='FOLDER', width=110, height=44, font=('Bahnschrift', 12, 'bold'),
                      text_color=CYAN, border_color='#12507a', fg_color='#06121e',
                      hover_color='#0a2136', command=self.open_folder).pack(side='left', padx=(8, 0))

        self.bar_canvas = tk.Canvas(body, height=12, bg=BG, highlightthickness=0)
        self.bar_canvas.pack(fill='x', pady=(0, 4))
        self.draw_bar(0)
        status_row = ctk.CTkFrame(body, fg_color='transparent')
        status_row.pack(fill='x', pady=(0, 12))
        self.status_var = tk.StringVar(value='IDLE')
        ctk.CTkLabel(status_row, textvariable=self.status_var, font=MONO, text_color=DIM).pack(side='left')
        self.led = tk.Canvas(status_row, width=10, height=10, bg=BG, highlightthickness=0)
        self.led.pack(side='right')
        self.blink_led(False)

        ctk.CTkLabel(body, text='// EVENT LOG', font=SECTION_FONT, text_color=CYAN).pack(anchor='w', pady=(0, 4))
        self.log_area = ctk.CTkTextbox(body, font=MONO, wrap='none', activate_scrollbars=True)
        self.log_area.pack(fill='both', expand=True)
        for level, tag in LEVEL_TAGS.items():
            self.log_area.tag_config(tag, foreground=LOG_COLORS[tag])
        self.log_area.configure(state='disabled')

        foot = ctk.CTkFrame(self.shell, fg_color='#07070d', corner_radius=0)
        foot.pack(fill='x')
        ctk.CTkLabel(foot, text='SYS.READY', font=MONO_SMALL, text_color=DIM).pack(side='left', padx=14, pady=5)
        ctk.CTkLabel(foot, text='4chanmedia v2.1 // neon build', font=MONO_SMALL,
                     text_color='#2a3a2e').pack(side='right', padx=14, pady=5)

    def blink_led(self, on: bool):
        self.led.delete('all')
        color = '#7cfc9e' if on else '#1c3a2a'
        self.led.create_oval(2, 2, 8, 8, fill=color, outline='')
        self._led_on = not on
        self.root.after(800, lambda: self.blink_led(self._led_on))

    def draw_bar(self, frac: float):
        c = self.bar_canvas
        c.delete('all')
        w = max(c.winfo_width(), 2)
        h = 12
        c.create_rectangle(0, 1, w, h - 1, fill='#0d1a12', outline='')
        if frac > 0:
            fw = max(int(w * frac), 6)
            c.create_rectangle(2, 2, fw, h - 2, fill=NEON_GREEN, outline='')
            c.create_rectangle(2, 2, fw, 4, fill='#d4ff8a', outline='')
        c.create_line(0, 0, w, 0, fill='#1a2b3c')
        c.create_line(0, h - 1, w, h - 1, fill='#1a2b3c')

    def browse(self):
        folder = filedialog.askdirectory(initialdir=self.out_entry.get() or str(Path(get_project_root())))
        if folder:
            self.out_entry.delete(0, 'end')
            self.out_entry.insert(0, folder)

    def open_folder(self):
        folder = self.out_entry.get().strip() or str(Path(get_project_root()) / 'output')
        Path(folder).mkdir(parents=True, exist_ok=True)
        try:
            import os
            os.startfile(folder)
        except OSError:
            messagebox.showerror('4chanMediaDL', f'Could not open folder: {folder}')

    def start(self):
        url = self.url_entry.get().strip() or None
        out = self.out_entry.get().strip() or None
        raw = self.proxy_box.get('1.0', 'end').strip()
        save_proxies(raw)
        count = set_proxies(load_proxy_lines(raw) if raw else [])
        self.log(('INFO', f'Proxy pool: {count} line(s)' if count else 'Proxy pool: direct'))
        self.cancel.clear()
        self.total = 0
        self.done = 0
        self.failed = 0
        self.draw_bar(0)
        self.status_var.set('STARTING...')
        self.dl_btn.configure(state='disabled')
        self.cancel_btn.configure(state='normal')
        self.worker_thread = threading.Thread(target=self.worker, args=(url, out), daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.cancel.set()
        self.log(('INFO', 'Cancelling after current file...'))
        self.cancel_btn.configure(state='disabled')

    def worker(self, url, out):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def on_total(n):
            self.q.put(('total', n))

        def on_done(name, status):
            self.q.put(('done', (name, status)))

        try:
            loop.run_until_complete(run(url, out, on_done=on_done, on_total=on_total, cancel=self.cancel))
            self.q.put(('finished', None))
        except Exception as e:
            self.q.put(('error', str(e)))
        finally:
            loop.close()

    def poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == 'total':
                    self.total = payload
                    self.status_var.set(f'0 / {self.total}')
                elif kind == 'done':
                    name, status = payload
                    if status == 'failed':
                        self.failed += 1
                        self.log(('ERROR', f'[FAIL] {name}'), tag='err')
                        continue
                    self.done += 1
                    self.draw_bar(self.done / max(self.total, 1))
                    self.status_var.set(f'{self.done} / {self.total}' + (f' - {self.failed} failed' if self.failed else ''))
                    if status == 'skipped':
                        self.log(('INFO', f'[SKIP] {name}'), tag='warn')
                    else:
                        self.log(('INFO', f'[OK]   {name}'), tag='info')
                elif kind == 'finished':
                    if self.cancel.is_set():
                        self.status_var.set(f'CANCELLED - {self.done} files')
                        self.log(('INFO', 'Cancelled.'))
                    elif self.done == 0:
                        self.status_var.set('NO MEDIA FOUND - CHECK LOG')
                        self.log(('ERROR', 'No media found. If the URL is empty, put site.html next to the exe.'))
                    else:
                        tail = f' - {self.failed} failed' if self.failed else ''
                        self.status_var.set(f'DONE - {self.done} files{tail}')
                        self.log((('ERROR' if self.failed else 'INFO'),
                                  f'Done. {self.done} downloaded, {self.failed} failed.'))
                    self.dl_btn.configure(state='normal')
                    self.cancel_btn.configure(state='disabled')
                    self.cancel.clear()
                elif kind == 'log':
                    self.log(payload)
                elif kind == 'error':
                    self.log(('ERROR', f'Error: {payload}'))
                    self.status_var.set('FAILED')
                    self.dl_btn.configure(state='normal')
                    self.cancel_btn.configure(state='disabled')
                    self.cancel.clear()
                    messagebox.showerror('4chanMediaDL', payload)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def log(self, payload, tag=None):
        level, text = payload
        tag = tag or LEVEL_TAGS.get(level, 'info')
        self.log_area.configure(state='normal')
        self.log_area.insert('end', text + '\n', tag)
        self.log_area.see('end')
        self.log_area.configure(state='disabled')

    def force_taskbar(self, *_):
        try:
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            hwnds = {self.root.winfo_id(), user32.GetParent(self.root.winfo_id())}
            for hwnd in hwnds:
                if not hwnd:
                    continue
                style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                new_style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
                if new_style != style:
                    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
        except Exception:
            pass

    def on_close(self):
        if self.worker_thread and self.worker_thread.is_alive():
            if not messagebox.askyesno('4chanMediaDL', 'Download in progress. Quit anyway?'):
                return
            self.cancel.set()
        save_proxies(self.proxy_box.get('1.0', 'end'))
        self.root.destroy()


def main():
    dbg('== main start ==')
    ctk.set_appearance_mode('dark')
    theme = asset('cyber.json')
    if theme:
        ctk.set_default_color_theme(theme)

    root = ctk.CTk()
    root.geometry('760x700')
    root.withdraw()
    dbg('root withdrawn')

    splash = Splash(root)
    dbg('splash created')
    app = App(root)
    dbg('app built')

    def reveal():
        dbg('reveal start')
        splash.destroy()
        root.overrideredirect(True)
        root.deiconify()
        dbg('deiconified, mapped=%s' % root.winfo_ismapped())
        app.force_taskbar()
        root.after(400, app.force_taskbar)
        dbg('reveal end')

    root.after(1400, reveal)
    dbg('entering mainloop')
    root.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        dbg('CRASH:\n' + traceback.format_exc())
