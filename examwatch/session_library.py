"""Searchable saved sessions. Actions always use report paths, not names."""
import tkinter as tk
from tkinter import ttk

from examwatch.home_page import BG, SURFACE, SIDEBAR, BORDER, FG, SECONDARY, GREEN, HomePage, session_overview

FILTERS = ('All sessions', 'Needs review', 'Reviewed', 'No events')


def filter_sessions(rows, query='', status='All sessions'):
    query = query.strip().casefold()
    return [row for row in rows if query in str(row['name']).casefold()
            and (status == 'All sessions' or row['status'] == status)]


def duration_label(seconds):
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:d}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes:02d}:{seconds:02d}'


class SessionLibrary(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.rows, self.visible_rows = [], []
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        sidebar = tk.Frame(self, bg=SIDEBAR, width=200)
        sidebar.grid(row=0, column=0, sticky='ns')
        sidebar.grid_propagate(False)
        tk.Label(sidebar, text='◉  ExamWatch', bg=SIDEBAR, fg=FG,
                 font=('Segoe UI', 18, 'bold')).pack(anchor='w', padx=22, pady=(30, 4))
        tk.Label(sidebar, text='EXAM MONITORING', bg=SIDEBAR, fg=SECONDARY,
                 font=('Segoe UI', 8)).pack(anchor='w', padx=23)
        for key, text in (('home', 'Overview'), ('live', 'New session'),
                          ('review', 'Session library'), ('evaluation', 'Accuracy evaluation'), ('settings', 'Settings')):
            button = HomePage.button(sidebar, text, lambda key=key: app.open_workspace(key),
                                     background='#233128' if key == 'review' else SIDEBAR,
                                     foreground=GREEN if key == 'review' else SECONDARY)
            button.pack(fill='x', padx=12, pady=(28 if key == 'home' else 4, 4))
        tk.Label(sidebar, text='LOCAL SESSION LIBRARY', bg=SIDEBAR, fg=GREEN,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=23, pady=(26, 8))
        tk.Label(sidebar, text='Find a session.\nReview with context.', bg=SIDEBAR, fg=SECONDARY,
                 font=('Segoe UI', 9), justify='left').pack(anchor='w', padx=23)
        self.exit_button = HomePage.button(sidebar, 'Exit app', app.close,
                                           background='#302321', foreground='#efb8a9')
        self.exit_button.pack(side='bottom', fill='x', padx=22, pady=25)

        main = tk.Frame(self, bg=BG)
        main.grid(row=0, column=1, sticky='nsew', padx=26, pady=22)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)
        tk.Label(main, text='WORKSPACE  /  SESSION LIBRARY', bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w')
        heading = tk.Frame(main, bg=BG)
        heading.grid(row=1, column=0, sticky='ew', pady=(18, 20))
        tk.Label(heading, text='Every session, in one place.', bg=BG, fg=FG,
                 font=('Segoe UI', 24, 'bold')).pack(anchor='w')
        tk.Label(heading, text='Find a recording, check its review status, and revisit the details.',
                 bg=BG, fg=SECONDARY, font=('Segoe UI', 10), wraplength=650,
                 justify='left').pack(anchor='w', pady=(6, 0))

        stats = tk.Frame(main, bg=BG)
        stats.grid(row=2, column=0, sticky='ew', pady=(0, 20))
        self.metrics = {}
        for index, (key, label) in enumerate((('total', 'SAVED SESSIONS'), ('pending', 'AWAITING REVIEW'),
                                             ('reviewed', 'REVIEWED SESSIONS'))):
            stats.columnconfigure(index, weight=1, uniform='cards')
            card = tk.Frame(stats, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=0, column=index, sticky='ew', padx=(0 if index == 0 else 5, 0 if index == 2 else 5))
            tk.Label(card, text=label, bg=SURFACE, fg=SECONDARY,
                     font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=14, pady=(12, 2))
            value = tk.StringVar(value='0')
            tk.Label(card, textvariable=value, bg=SURFACE, fg=GREEN if key == 'pending' else FG,
                     font=('Segoe UI', 24, 'bold')).pack(anchor='w', padx=14, pady=(0, 10))
            self.metrics[key] = value

        filters = tk.Frame(main, bg=BG)
        filters.grid(row=3, column=0, sticky='ew', pady=(0, 14))
        filters.columnconfigure(0, weight=1)
        tk.Label(filters, text='Search session name', bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w', pady=(0, 6))
        tk.Label(filters, text='Review status', bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=0, column=1, sticky='w', padx=10)
        self.query = tk.StringVar()
        self.status_filter = tk.StringVar(value='All sessions')
        self.search = tk.Entry(filters, textvariable=self.query, bg=SURFACE, fg=FG, insertbackground=FG,
                               relief='flat', font=('Segoe UI', 11), highlightthickness=1,
                               highlightbackground=BORDER, highlightcolor=GREEN)
        self.search.grid(row=1, column=0, sticky='ew', ipady=9)
        style = ttk.Style()
        style.configure('Library.TCombobox', fieldbackground=SURFACE, background=SURFACE,
                        foreground=FG, arrowcolor=GREEN, padding=8)
        style.map('Library.TCombobox', fieldbackground=[('readonly', SURFACE)], foreground=[('readonly', FG)])
        self.filter_choice = ttk.Combobox(filters, textvariable=self.status_filter, values=FILTERS,
                                          state='readonly', width=17, style='Library.TCombobox')
        self.filter_choice.grid(row=1, column=1, padx=10, sticky='ns')
        HomePage.button(filters, 'Clear', self.clear_filters).grid(row=1, column=2, padx=(0, 8), sticky='ns')
        self.refresh_button = HomePage.button(filters, 'Refresh', self.refresh)
        self.refresh_button.grid(row=1, column=3, sticky='ns')

        table_frame = tk.Frame(main, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        table_frame.grid(row=4, column=0, sticky='nsew')
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        style.configure('Library.Treeview', background=SURFACE, fieldbackground=SURFACE,
                        foreground=FG, rowheight=54, font=('Segoe UI', 10), borderwidth=0)
        style.configure('Library.Treeview.Heading', background='#202d27', foreground=SECONDARY,
                        font=('Segoe UI', 9), padding=10, relief='flat')
        style.map('Library.Treeview', background=[('selected', '#314a37')], foreground=[('selected', '#ffffff')])
        columns = ('name', 'date', 'duration', 'events', 'status')
        self.table = ttk.Treeview(table_frame, columns=columns, show='headings',
                                  selectmode='browse', height=4, style='Library.Treeview')
        for key, text, width in (('name', 'SESSION', 240), ('date', 'DATE', 175), ('duration', 'DURATION', 90),
                                  ('events', 'EVENTS', 65), ('status', 'REVIEW', 125)):
            self.table.heading(key, text=text, anchor='w')
            self.table.column(key, width=width, minwidth=55, anchor='w', stretch=key == 'name')
        self.table.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(table_frame, command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.tag_configure('pending', foreground='#dfc18d')
        self.table.tag_configure('reviewed', foreground=GREEN)
        self.table.bind('<<TreeviewSelect>>', self.selection_changed)
        self.table.bind('<Double-1>', self.open_selected)
        self.table.bind('<Return>', self.open_selected)
        self.empty = tk.Label(table_frame, bg=SURFACE, fg=SECONDARY,
                              font=('Segoe UI', 11), justify='center')
        self.selection_text = tk.StringVar(value='Select a session to see its available actions.')
        self.selection_label = tk.Label(main, textvariable=self.selection_text, bg=BG, fg=SECONDARY,
                                        font=('Segoe UI', 9), anchor='w', justify='left', wraplength=700)
        self.selection_label.grid(row=5, column=0, sticky='ew', pady=(12, 10))
        actions = tk.Frame(main, bg=BG)
        actions.grid(row=6, column=0, sticky='ew')
        self.open_button = HomePage.button(actions, 'Open review  →', self.open_selected,
                                            background=GREEN, foreground='#152016')
        self.open_button.pack(side='left')
        self.pdf_button = HomePage.button(actions, 'Export PDF', self.export_selected)
        self.pdf_button.pack(side='left', padx=8)
        self.delete_button = HomePage.button(actions, 'Delete session', self.delete_selected,
                                              background='#302321', foreground='#efb8a9')
        self.delete_button.pack(side='right')
        self.footer_text = tk.StringVar()
        tk.Label(main, textvariable=self.footer_text, bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=7, column=0, sticky='w', pady=(14, 0))
        main.bind('<Configure>', lambda event: self.selection_label.configure(wraplength=max(260, event.width - 8)))
        self.query.trace_add('write', lambda *_args: self.render())
        self.status_filter.trace_add('write', lambda *_args: self.render())
        self.refresh()

    def selected_path(self):
        selection = self.table.selection()
        return self.visible_rows[int(selection[0])]['path'] if selection else None

    def refresh(self):
        selected = self.selected_path() if self.visible_rows else None
        self.rows, self.unreadable = session_overview(self.app_root / 'outputs/session_reports')
        self.metrics['total'].set(str(len(self.rows)))
        self.metrics['pending'].set(str(sum(row['status'] == 'Needs review' for row in self.rows)))
        self.metrics['reviewed'].set(str(sum(row['status'] == 'Reviewed' for row in self.rows)))
        self.render(selected)

    @property
    def app_root(self):
        # Passed by the dashboard so tests and alternate workspaces stay isolated.
        return self.app.root_path

    def render(self, selected=None):
        selected = selected or self.selected_path()
        self.visible_rows = filter_sessions(self.rows, self.query.get(), self.status_filter.get())
        self.table.delete(*self.table.get_children())
        for index, row in enumerate(self.visible_rows):
            self.table.insert('', 'end', iid=str(index), values=(row['name'], row['date'],
                duration_label(row['duration_seconds']), row['events'], row['status']),
                tags=('pending' if row['pending'] else 'reviewed' if row['events'] else 'normal',))
            if row['path'] == selected:
                self.table.selection_set(str(index))
        if self.visible_rows:
            self.empty.place_forget()
        else:
            self.empty.configure(text='No matching sessions\n\nTry another name or clear the filters.' if self.rows else
                                 'No sessions yet\n\nYour saved sessions will appear here after an exam.')
            self.empty.place(relx=.5, rely=.5, anchor='center')
        warning = f' · {self.unreadable} unreadable report(s) skipped' if self.unreadable else ''
        self.footer_text.set(f'Showing {len(self.visible_rows)} of {len(self.rows)} sessions{warning}')
        self.selection_changed()

    def selection_changed(self, _event=None):
        path = self.selected_path()
        for button in (self.open_button, self.pdf_button, self.delete_button):
            button.configure(state='normal' if path else 'disabled', disabledforeground='#64756a')
        if path:
            row = next(row for row in self.visible_rows if row['path'] == path)
            self.selection_text.set(f"{row['name']} · {row['source']} · {row['pending']} event(s) awaiting review")
        else:
            self.selection_text.set('Select a session to open its review, export a PDF, or delete it.')

    def clear_filters(self):
        self.query.set('')
        self.status_filter.set('All sessions')

    def open_selected(self, _event=None):
        path = self.selected_path()
        if path is not None:
            self.app.open_home_session(path)

    def export_selected(self):
        path = self.selected_path()
        if path is not None and self.app.select_report(path):
            self.app.export_pdf()

    def delete_selected(self):
        path = self.selected_path()
        if path is not None and self.app.select_report(path):
            self.app.delete_selected_session()
            self.refresh()
