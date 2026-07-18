"""Tkinter GUI for the Photo Converter. All heavy lifting lives in conversion.py;
this module only handles the window, user options and logging.
"""

import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from pathlib import Path
from datetime import datetime

from .constants import (ALL_SUPPORTED, DARK_BG, PANEL_BG, FIELD_BG, FIELD_HI,
                        TEXT_FG, MUTED_FG, ACCENT, ACCENT_HI, SUCCESS, ERROR_CLR,
                        WARN_CLR, FONT_MAIN, FONT_MONO)
from . import conversion


class PhotoConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Photo Converter')
        self.geometry('760x640')
        self.configure(bg=DARK_BG)
        self.resizable(True, True)
        self._running = False
        self._build_ui()
        self._check_deps()

    # ---- Build UI ----

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TProgressbar', troughcolor=PANEL_BG, background=ACCENT, thickness=8)

        # Title
        hdr = tk.Frame(self, bg=DARK_BG)
        hdr.pack(fill='x', padx=20, pady=(16, 8))
        tk.Label(hdr, text='Photo Converter', font=('Segoe UI', 16, 'bold'),
                 bg=DARK_BG, fg=TEXT_FG).pack(side='left')

        # Settings
        cfg = tk.Frame(self, bg=PANEL_BG, bd=0)
        cfg.pack(fill='x', padx=20, pady=4)
        cfg.columnconfigure(1, weight=1)

        def row(parent, label, row_idx):
            tk.Label(parent, text=label, bg=PANEL_BG, fg=MUTED_FG,
                     font=FONT_MAIN, anchor='w').grid(row=row_idx, column=0,
                     sticky='w', padx=12, pady=6)

        def folder_row(label, row_idx, default, browse_cmd):
            row(cfg, label, row_idx)
            var = tk.StringVar(value=default)
            frame = tk.Frame(cfg, bg=PANEL_BG)
            frame.grid(row=row_idx, column=1, sticky='ew', padx=(0, 12), pady=6)
            tk.Entry(frame, textvariable=var, bg=FIELD_BG, fg=TEXT_FG,
                     insertbackground=TEXT_FG, relief='flat', font=FONT_MAIN,
                     bd=6).pack(side='left', fill='x', expand=True)
            tk.Button(frame, text='...', command=browse_cmd, bg=FIELD_BG, fg=TEXT_FG,
                      relief='flat', bd=0, highlightthickness=0, activebackground=FIELD_HI,
                      activeforeground=TEXT_FG, font=FONT_MAIN, padx=8).pack(side='right', padx=(4, 0))
            return var

        self.src_var = folder_row('Source:', 0, r'C:\Users\Jonas\Pictures\iCloud Photos\Photos', self._browse_src)
        self.dst_var = folder_row('Destination:', 1, r'C:\Users\Jonas\Pictures\Photos_Sorted', self._browse_dst)

        # Folder structure
        row(cfg, 'Structure:', 2)
        self.structure_var = tk.StringVar(value='Year/Month')
        struct_f = tk.Frame(cfg, bg=PANEL_BG)
        struct_f.grid(row=2, column=1, sticky='w', padx=(0, 12), pady=6)
        for val in ['Year', 'Year/Month', 'Year/Month/Day']:
            tk.Radiobutton(struct_f, text=val, variable=self.structure_var,
                           value=val, bg=PANEL_BG, fg=TEXT_FG, selectcolor=FIELD_BG,
                           activebackground=PANEL_BG, activeforeground=TEXT_FG,
                           highlightthickness=0, font=FONT_MAIN).pack(side='left', padx=8)

        # Options
        row(cfg, 'Options:', 3)
        opt_f = tk.Frame(cfg, bg=PANEL_BG)
        opt_f.grid(row=3, column=1, sticky='w', padx=(0, 12), pady=6)
        self.skip_existing_var = tk.BooleanVar(value=True)
        self.skip_online_var   = tk.BooleanVar(value=True)
        self.lowercase_ext_var = tk.BooleanVar(value=True)

        def check(text, var, r):
            tk.Checkbutton(opt_f, text=text, variable=var, bg=PANEL_BG, fg=TEXT_FG,
                           selectcolor=FIELD_BG, activebackground=PANEL_BG,
                           activeforeground=TEXT_FG, highlightthickness=0,
                           font=FONT_MAIN, anchor='w').grid(row=r, column=0, sticky='w')

        check('Skip files that already exist', self.skip_existing_var, 0)
        check('Skip files not downloaded from iCloud', self.skip_online_var, 1)
        check('Lowercase extensions (.jpg)', self.lowercase_ext_var, 2)

        # Progress
        prog_f = tk.Frame(self, bg=DARK_BG)
        prog_f.pack(fill='x', padx=20, pady=(8, 0))
        self.progress = ttk.Progressbar(prog_f, mode='determinate', style='TProgressbar')
        self.progress.pack(fill='x')
        self.status_var = tk.StringVar(value='Ready.')
        tk.Label(prog_f, textvariable=self.status_var, bg=DARK_BG,
                 fg=MUTED_FG, font=FONT_MAIN, anchor='w').pack(fill='x', pady=(2, 0))

        # Log
        log_f = tk.Frame(self, bg=DARK_BG)
        log_f.pack(fill='both', expand=True, padx=20, pady=8)
        tk.Label(log_f, text='Log', bg=DARK_BG, fg=MUTED_FG,
                 font=FONT_MAIN, anchor='w').pack(fill='x')
        self.log = scrolledtext.ScrolledText(
            log_f, bg=PANEL_BG, fg=TEXT_FG, font=FONT_MONO,
            relief='flat', bd=0, insertbackground=TEXT_FG,
            state='disabled', wrap='none')
        self.log.pack(fill='both', expand=True)
        self.log.tag_config('ok',   foreground=SUCCESS)
        self.log.tag_config('err',  foreground=ERROR_CLR)
        self.log.tag_config('warn', foreground=WARN_CLR)
        self.log.tag_config('info', foreground=MUTED_FG)

        # Buttons
        btn_f = tk.Frame(self, bg=DARK_BG)
        btn_f.pack(pady=(0, 16))

        def button(text, cmd, primary=False, disabled=False):
            b = tk.Button(
                btn_f, text=text, command=cmd,
                bg=(ACCENT if primary else FIELD_BG), fg=('white' if primary else TEXT_FG),
                activebackground=(ACCENT_HI if primary else FIELD_HI),
                activeforeground=('white' if primary else TEXT_FG),
                disabledforeground=('#cfe6ff' if primary else MUTED_FG),
                font=('Segoe UI', 10, 'bold') if primary else FONT_MAIN,
                relief='flat', bd=0, highlightthickness=0, padx=32, pady=9,
                cursor='hand2', state='disabled' if disabled else 'normal')
            b.pack(side='left', padx=6)
            return b

        self.start_btn = button('Start', self._start, primary=True)
        self.stop_btn  = button('Stop', self._stop, disabled=True)
        self.save_btn  = button('Save log', self._save_log)

    # ---- Helper methods ----

    def _browse_src(self):
        d = filedialog.askdirectory(title='Choose source folder')
        if d: self.src_var.set(d)

    def _browse_dst(self):
        d = filedialog.askdirectory(title='Choose destination folder')
        if d: self.dst_var.set(d)

    def _log(self, msg, tag=''):
        self.log.config(state='normal')
        self.log.insert('end', msg + '\n', tag)
        self.log.see('end')
        self.log.config(state='disabled')

    def _save_log(self):
        text = self.log.get('1.0', 'end').strip()
        if not text:
            self.status_var.set('Nothing to save - the log is empty.')
            return
        default = f'photo-converter-log_{datetime.now():%Y-%m-%d_%H%M}.txt'
        path = filedialog.asksaveasfilename(
            title='Save log as', defaultextension='.txt', initialfile=default,
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')])
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text + '\n')
            self._log(f'Log saved to: {path}', 'info')
        except Exception as e:
            self._log(f'Could not save log: {e}', 'err')

    def _check_deps(self):
        missing = []
        for module, package in [('rawpy', 'rawpy'), ('PIL', 'Pillow'),
                                ('exifread', 'exifread'), ('piexif', 'piexif'),
                                ('pillow_heif', 'pillow-heif')]:
            try:
                __import__(module)
            except ImportError:
                missing.append(package)

        if missing:
            self._log(f'WARNING: Missing packages: {", ".join(missing)}', 'err')
            self._log('Please run install_und_starten.bat or execute:', 'info')
            self._log(f'  pip install {" ".join(missing)}', 'info')
        else:
            self._log('All packages available. Ready!', 'ok')

        if not conversion.ffmpeg_available():
            self._log('WARNING: ffmpeg not found - video conversion unavailable.', 'err')
            self._log('  Download: https://ffmpeg.org/download.html', 'info')

    # ---- Processing ----

    def _start(self):
        src = Path(self.src_var.get())
        dst = Path(self.dst_var.get())
        if not src.exists():
            self._log(f'Source folder not found: {src}', 'err')
            return
        if src == dst:
            self._log('Source and destination must not be the same!', 'err')
            return
        self._running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.log.config(state='normal')
        self.log.delete('1.0', 'end')
        self.log.config(state='disabled')
        threading.Thread(target=self._process, args=(src, dst), daemon=True).start()

    def _stop(self):
        self._running = False
        self.status_var.set('Stopping...')

    def _process(self, src: Path, dst: Path):
        # Read options once (main-thread state) before the worker loop
        structure     = self.structure_var.get()
        skip_existing = self.skip_existing_var.get()
        skip_online   = self.skip_online_var.get()
        lower_ext     = self.lowercase_ext_var.get()
        ffmpeg_ok     = conversion.ffmpeg_available()

        self._log(f'Scanning files in: {src}', 'info')
        all_files = [f for f in src.rglob('*')
                     if f.is_file() and f.suffix.lower() in ALL_SUPPORTED]
        total = len(all_files)
        self._log(f'Found: {total} files\n', 'info')
        self.progress.config(maximum=max(total, 1))

        counts = {'ok': 0, 'exists': 0, 'online': 0, 'noffmpeg': 0, 'error': 0}
        no_date = 0

        for i, fp in enumerate(all_files):
            if not self._running:
                break
            self.progress['value'] = i + 1
            self.status_var.set(f'{i+1}/{total}  {fp.name}')
            self.update_idletasks()

            outcome = conversion.process_file(
                fp, dst, structure, skip_existing, skip_online, lower_ext, ffmpeg_ok)
            counts[outcome.category] += 1
            if outcome.no_date:
                no_date += 1
            self._log(outcome.message, outcome.tag)

        total_skipped = counts['exists'] + counts['online'] + counts['noffmpeg']
        self._log(
            f'\n{"=" * 50}\n'
            f'Done!  OK: {counts["ok"]}  |  Errors: {counts["error"]}  |  Skipped: {total_skipped}\n'
            f'  - already existed:          {counts["exists"]}\n'
            f'  - not downloaded (iCloud):  {counts["online"]}\n'
            f'  - no ffmpeg:                {counts["noffmpeg"]}\n'
            f'  - no EXIF date (file date): {no_date}\n'
            f'Destination: {dst}',
            'info')
        self.status_var.set(
            f'Done - {counts["ok"]} OK, {counts["error"]} errors, {total_skipped} skipped')
        self.progress['value'] = total
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self._running = False
