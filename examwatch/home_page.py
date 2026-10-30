"""Overview design preview. Uses saved session data and never opens a camera."""
import json
import math
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk

BG = '#101716'
SURFACE = '#17211f'
SIDEBAR = '#0c1211'
BORDER = '#2b3833'
FG = '#eef3ef'
SECONDARY = '#97aaa0'
GREEN = '#b8e89c'


def session_overview(directory):
    """Skip unreadable reports; keep real session paths as row identities."""
    sessions, unreadable = [], 0
    for path in sorted(Path(directory).glob('*.json'), reverse=True):
        try:
            report = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(report, dict) or not isinstance(report.get('events', []), list):
                raise ValueError('Invalid report')
            events = report.get('events', [])
            duration = float(report.get('duration_seconds', 0))
            if not math.isfinite(duration) or duration < 0:
                raise ValueError('Invalid session duration')
            pending = sum(event.get('review', {}).get('status', 'Unreviewed') not in
                          ('Reviewed', 'False alarm') for event in events)
            identifier = report.get('session_id', '')
            try:
                date = datetime.strptime(identifier[:15], '%Y%m%d_%H%M%S').strftime('%d %b %Y · %H:%M')
            except (ValueError, TypeError):
                date = 'Date unavailable'
            sessions.append({'path': path, 'name': report.get('session_name') or identifier or path.stem,
                             'date': date, 'events': len(events), 'pending': pending,
                             'duration_seconds': duration, 'source': str(report.get('source_name') or 'Camera'),
                             'status': 'Needs review' if pending else 'Reviewed' if events else 'No events'})
        except (OSError, ValueError, TypeError, AttributeError):
            unreadable += 1
    return sessions, unreadable


class HomePage(tk.Frame):
    def __init__(self, parent, root_path, navigate, open_session, close):
        super().__init__(parent, bg=BG)
        self.root_path, self.navigate, self.open_session = root_path, navigate, open_session
        self.rows = []
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        sidebar = tk.Frame(self, bg=SIDEBAR, width=200)
        sidebar.grid(row=0, column=0, sticky='ns')
        sidebar.grid_propagate(False)
        tk.Label(sidebar, text='◉  ExamWatch', bg=SIDEBAR, fg=FG,
                 font=('Segoe UI', 18, 'bold')).pack(anchor='w', padx=22, pady=(30, 4))
        tk.Label(sidebar, text='EXAM MONITORING', bg=SIDEBAR, fg=SECONDARY,
                 font=('Segoe UI', 8)).pack(anchor='w', padx=23)
        tk.Label(sidebar, text='WORKSPACE', bg=SIDEBAR, fg=SECONDARY,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=23, pady=(42, 12))
        self.nav_buttons = {}
        for key, label in (('home', 'Overview'), ('live', 'New session'),
                           ('review', 'Session library'), ('evaluation', 'Accuracy evaluation'), ('settings', 'Settings')):
            button = self.button(sidebar, label, lambda key=key: navigate(key),
                                 background='#233128' if key == 'home' else SIDEBAR,
                                 foreground=GREEN if key == 'home' else SECONDARY)
            button.configure(anchor='w', padx=16)
            button.pack(fill='x', padx=12, pady=4)
            self.nav_buttons[key] = button
        bottom = tk.Frame(sidebar, bg=SIDEBAR)
        bottom.pack(side='bottom', fill='x', padx=22, pady=25)
        self.exit_button = self.button(bottom, 'Exit app', close,
                                       background='#302321', foreground='#efb8a9')
        self.exit_button.pack(fill='x', pady=(0, 20))
        tk.Label(bottom, text='LOCAL WORKSPACE', bg=SIDEBAR, fg=GREEN,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w')
        tk.Label(bottom, text='Your sessions stay\non this device.', justify='left',
                 bg=SIDEBAR, fg=SECONDARY, font=('Segoe UI', 9)).pack(anchor='w', pady=(8, 0))

        main = tk.Frame(self, bg=BG)
        main.grid(row=0, column=1, sticky='nsew', padx=28, pady=22)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)
        header = tk.Frame(main, bg=BG)
        header.grid(row=0, column=0, sticky='ew')
        tk.Label(header, text='WORKSPACE  /  OVERVIEW', bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).pack(side='left')

        hero = tk.Frame(main, bg=BG)
        hero.grid(row=1, column=0, sticky='ew', pady=(30, 24))
        tk.Label(hero, text='Every session. A clearer picture.', bg=BG, fg=FG,
                 font=('Segoe UI', 25, 'bold'), anchor='w').pack(anchor='w')
        tk.Label(hero, text='Start an exam session, revisit events, and keep your reviews in one place.',
                 bg=BG, fg=SECONDARY, font=('Segoe UI', 10), wraplength=650,
                 justify='left').pack(anchor='w', pady=(8, 18))
        self.start_button = self.button(hero, '+  New session', lambda: navigate('live'),
                                        background=GREEN, foreground='#152016')
        self.start_button.pack(anchor='w')

        cards = tk.Frame(main, bg=BG)
        cards.grid(row=2, column=0, sticky='ew', pady=(0, 24))
        self.metrics = {}
        for index, (key, label, help_text) in enumerate((
                ('sessions', 'SAVED SESSIONS', 'Your recorded exam sessions'),
                ('pending', 'AWAITING REVIEW', 'Sessions with unresolved events'),
                ('events', 'FLAGGED EVENTS', 'Observations for human review'))):
            cards.columnconfigure(index, weight=1, uniform='cards')
            card = tk.Frame(cards, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=0, column=index, sticky='ew', padx=(0 if index == 0 else 6, 0 if index == 2 else 6))
            tk.Label(card, text=label, bg=SURFACE, fg=SECONDARY,
                     font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=16, pady=(14, 0))
            value = tk.StringVar(value='0')
            tk.Label(card, textvariable=value, bg=SURFACE, fg=GREEN if key == 'pending' else FG,
                     font=('Segoe UI', 27, 'bold')).pack(anchor='w', padx=16, pady=2)
            tk.Label(card, text=help_text, bg=SURFACE, fg=SECONDARY, font=('Segoe UI', 8),
                     wraplength=195, justify='left').pack(anchor='w', padx=16, pady=(0, 14))
            self.metrics[key] = value

        recent_header = tk.Frame(main, bg=BG)
        recent_header.grid(row=3, column=0, sticky='ew', pady=(0, 10))
        tk.Label(recent_header, text='Recent sessions', bg=BG, fg=FG,
                 font=('Segoe UI', 15, 'bold')).pack(side='left')
        self.button(recent_header, 'View library  →', lambda: navigate('review')).pack(side='right')
        library = tk.Frame(main, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        library.grid(row=4, column=0, sticky='nsew')
        library.columnconfigure(0, weight=1)
        library.rowconfigure(0, weight=1)
        style = ttk.Style()
        style.configure('Home.Treeview', background=SURFACE, fieldbackground=SURFACE,
                        foreground=FG, borderwidth=0, rowheight=52, font=('Segoe UI', 10))
        style.configure('Home.Treeview.Heading', background='#202d27', foreground=SECONDARY,
                        relief='flat', font=('Segoe UI', 9), padding=10)
        style.map('Home.Treeview', background=[('selected', '#314a37')],
                  foreground=[('selected', '#ffffff')])
        self.table = ttk.Treeview(library, columns=('name', 'date', 'events', 'status'),
                                  show='headings', height=3, style='Home.Treeview')
        for key, title, width in (('name', 'SESSION', 230), ('date', 'DATE', 165),
                                  ('events', 'EVENTS', 65), ('status', 'REVIEW', 120)):
            self.table.heading(key, text=title, anchor='w')
            self.table.column(key, width=width, minwidth=55, anchor='w', stretch=key == 'name')
        self.table.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(library, command=self.table.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        self.table.configure(yscrollcommand=scroll.set)
        self.table.bind('<Double-1>', self.open_selected)
        self.table.bind('<Return>', self.open_selected)
        self.empty = tk.Label(library, text='No sessions yet\n\nStart your first session to build your review library.',
                              bg=SURFACE, fg=SECONDARY, font=('Segoe UI', 11), justify='center')
        footer = tk.Frame(main, bg=BG)
        footer.grid(row=5, column=0, sticky='ew', pady=(12, 0))
        self.info = tk.StringVar(value='Select a session and open it to review its events.')
        tk.Label(footer, textvariable=self.info, bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).pack(side='left')
        self.open_button = self.button(footer, 'Open selected  →', self.open_selected)
        self.open_button.pack(side='right')
        tk.Label(main, text='A review assistant. Flags do not establish cheating.', bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=6, column=0, sticky='w', pady=(20, 0))
        self.refresh()

    @staticmethod
    def button(parent, text, command, background='#22312a', foreground=FG):
        button = tk.Button(parent, text=text, command=command, bg=background, fg=foreground,
                           activebackground='#36513c', activeforeground='#ffffff',
                           relief='flat', borderwidth=0, highlightthickness=1,
                           highlightbackground=background, highlightcolor=GREEN,
                           cursor='hand2', font=('Segoe UI', 10), padx=14, pady=10)
        return button

    def refresh(self):
        self.rows, unreadable = session_overview(self.root_path / 'outputs/session_reports')
        self.metrics['sessions'].set(str(len(self.rows)))
        self.metrics['pending'].set(str(sum(row['pending'] > 0 for row in self.rows)))
        self.metrics['events'].set(str(sum(row['events'] for row in self.rows)))
        self.table.delete(*self.table.get_children())
        for index, row in enumerate(self.rows[:20]):
            self.table.insert('', 'end', iid=str(index), values=(row['name'], row['date'], row['events'], row['status']))
        if self.rows:
            self.empty.place_forget()
            self.open_button.configure(state='normal')
        else:
            self.empty.place(relx=.5, rely=.5, anchor='center')
            self.open_button.configure(state='disabled')
        self.info.set(f'{unreadable} unreadable report(s) skipped.' if unreadable else
                      'Select a session, then open its review.' if self.rows else 'Your camera stays off until you start a session.')

    def open_selected(self, _event=None):
        selected = self.table.selection()
        if selected:
            self.open_session(self.rows[int(selected[0])]['path'])
