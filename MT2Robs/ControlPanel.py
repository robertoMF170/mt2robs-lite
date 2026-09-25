# -*- coding: utf-8 -*-
"""MT2Robs LITE - Painel externo (log das energias + localizador)."""
from __future__ import print_function
import os
import time

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    import Tkinter as tk
    import ttk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, 'mt2robs.txt')


class Panel(object):
    def __init__(self, root):
        self.root = root
        root.title('MT2Robs LITE')
        root.geometry('500x300')
        self.status = tk.StringVar(value='pronto')
        ttk.Label(root, textvariable=self.status).pack(anchor='w', padx=10, pady=6)
        frame = ttk.Frame(root)
        frame.pack(fill='both', expand=True, padx=10, pady=6)
        self.text = tk.Text(frame, wrap='none', state='disabled', background='#111', foreground='#ddd')
        sb = ttk.Scrollbar(frame, orient='vertical', command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.root.after(2000, self.poll)

    def refresh(self):
        try:
            with open(LOG, 'r') as f:
                lines = f.readlines()[-150:]
            data = ''.join(lines)
        except Exception:
            data = 'sem log'
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('end', data)
        self.text.see('end')
        self.text.configure(state='disabled')

    def poll(self):
        self.refresh()
        self.root.after(2000, self.poll)


if __name__ == '__main__':
    root = tk.Tk()
    Panel(root)
    root.mainloop()
