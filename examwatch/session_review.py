"""Dark event review page: timeline, evidence, decisions, and persistent notes."""
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from examwatch.home_page import BG, SURFACE, SIDEBAR, BORDER, FG, SECONDARY, GREEN, HomePage
from examwatch.session_storage import REVIEW_STATUSES
from examwatch.evidence_viewer import EvidenceViewer


class SessionReviewPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.current_event = None
        self.loading = False
        self.saved_values = ('Unreviewed', '')
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
        tk.Label(sidebar, text='SESSION REVIEW', bg=SIDEBAR, fg=GREEN,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=23, pady=(26, 8))
        tk.Label(sidebar, text='Inspect the context.\nSave your decision.', bg=SIDEBAR, fg=SECONDARY,
                 font=('Segoe UI', 9), justify='left').pack(anchor='w', padx=23)
        self.exit_button = HomePage.button(sidebar, 'Exit app', app.close,
                                           background='#302321', foreground='#efb8a9')
        self.exit_button.pack(side='bottom', fill='x', padx=22, pady=25)
        main = tk.Frame(self, bg=BG)
        main.grid(row=0, column=1, sticky='nsew', padx=26, pady=22)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)
        tk.Label(main, text='WORKSPACE  /  SESSION REVIEW', bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w')
        self.title = tk.StringVar(value='Review your session.')
        tk.Label(main, textvariable=self.title, bg=BG, fg=FG,
                 font=('Segoe UI', 23, 'bold'), anchor='w', wraplength=700).grid(row=1, column=0, sticky='ew', pady=(16, 6))
        app.summary = tk.StringVar(value='Select a session from the library.')
        self.summary_label = tk.Label(main, textvariable=app.summary, bg=BG, fg=SECONDARY,
                                     font=('Segoe UI', 9), wraplength=700, justify='left', anchor='w')
        self.summary_label.grid(row=2, column=0, sticky='ew')
        progress_row = tk.Frame(main, bg=BG)
        progress_row.grid(row=3, column=0, sticky='ew', pady=(12, 16))
        self.completion = tk.StringVar(value='No events to review')
        tk.Label(progress_row, textvariable=self.completion, bg=BG, fg=GREEN,
                 font=('Segoe UI', 10)).pack(side='left')
        style = ttk.Style()
        style.configure('Review.Horizontal.TProgressbar', background=GREEN, troughcolor=SURFACE,
                        lightcolor=GREEN, darkcolor=GREEN, bordercolor=SURFACE, thickness=5)
        self.progress = ttk.Progressbar(progress_row, maximum=100, length=140, style='Review.Horizontal.TProgressbar')
        self.progress.pack(side='right')
        body = tk.Frame(main, bg=BG)
        body.grid(row=4, column=0, sticky='nsew')
        body.columnconfigure(0, weight=2, minsize=250)
        body.columnconfigure(1, weight=3, minsize=320)
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        tk.Label(left, text='Event timeline', bg=SURFACE, fg=FG,
                 font=('Segoe UI', 13, 'bold')).grid(row=0, column=0, sticky='w', padx=14, pady=14)
        style.configure('Review.Treeview', background=SURFACE, fieldbackground=SURFACE, foreground=FG,
                        rowheight=52, borderwidth=0, font=('Segoe UI', 9))
        style.configure('Review.Treeview.Heading', background='#202d27', foreground=SECONDARY,
                        padding=7, relief='flat', font=('Segoe UI', 8))
        style.map('Review.Treeview', background=[('selected', '#314a37')], foreground=[('selected', '#ffffff')])
        timeline = tk.Frame(left, bg=SURFACE)
        timeline.grid(row=1, column=0, sticky='nsew')
        timeline.columnconfigure(0, weight=1)
        timeline.rowconfigure(0, weight=1)
        app.table = ttk.Treeview(timeline, columns=('start', 'duration', 'reasons', 'review'),
                                 displaycolumns=('start', 'reasons', 'review'), show='headings',
                                 selectmode='browse', style='Review.Treeview', height=4)
        for key, text, width in (('start', 'TIME', 55), ('duration', 'LENGTH', 55),
                                 ('reasons', 'REASON', 130), ('review', 'REVIEW', 100)):
            app.table.heading(key, text=text, anchor='w')
            app.table.column(key, width=width, minwidth=55 if key != 'reasons' else 70, stretch=key == 'reasons')
        app.table.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(timeline, command=app.table.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        app.table.configure(yscrollcommand=scroll.set)
        app.table.tag_configure('pending', foreground='#dfc18d')
        app.table.tag_configure('reviewed', foreground=GREEN)
        app.table.bind('<<TreeviewSelect>>', app.show_evidence)
        self.empty = tk.Label(timeline, text='No confirmed events\n\nThere is nothing to review.',
                              bg=SURFACE, fg=SECONDARY, font=('Segoe UI', 10), justify='center')
        event_controls = tk.Frame(left, bg=SURFACE)
        event_controls.grid(row=2, column=0, sticky='ew', padx=10, pady=10)
        self.previous_button = HomePage.button(event_controls, '← Previous', lambda: self.move(-1))
        self.previous_button.pack(side='left')
        self.next_button = HomePage.button(event_controls, 'Next →', lambda: self.move(1))
        self.next_button.pack(side='right')

        right = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        right.grid(row=0, column=1, sticky='nsew')
        right.grid_propagate(False)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        self.event_title = tk.StringVar(value='Select an event')
        self.event_label = tk.Label(right, textvariable=self.event_title, bg=SURFACE, fg=FG,
                                    font=('Segoe UI', 11, 'bold'), anchor='w', justify='left', wraplength=360)
        self.event_label.grid(row=0, column=0, sticky='ew', padx=14, pady=(14, 10))
        self.viewer = EvidenceViewer(right, self.player_state)
        self.viewer.grid(row=1, column=0, sticky='nsew', padx=12)
        self.viewer.grid_propagate(False)
        app.evidence = self.viewer.label
        tools = tk.Frame(right, bg=SURFACE)
        tools.grid(row=2, column=0, sticky='ew', padx=12, pady=8)
        self.snapshot_button = HomePage.button(tools, 'Screenshot', self.show_snapshot)
        app.clip_button = HomePage.button(tools, 'Play clip', app.play_clip)
        self.pause_button = HomePage.button(tools, 'Pause', self.viewer.toggle)
        self.restart_button = HomePage.button(tools, 'Restart', self.viewer.restart)
        for button in (self.snapshot_button, app.clip_button, self.pause_button, self.restart_button):
            button.configure(padx=8, pady=8, font=('Segoe UI', 9))
            button.pack(side='left', padx=(0, 5))
        tk.Label(right, text='Review decision', bg=SURFACE, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=3, column=0, sticky='w', padx=14, pady=(4, 5))
        app.review_status = tk.StringVar(value='Unreviewed')
        style.configure('Review.TCombobox', fieldbackground='#24332b', background='#24332b',
                        foreground=FG, arrowcolor=GREEN, padding=6)
        style.map('Review.TCombobox', fieldbackground=[('readonly', '#24332b')], foreground=[('readonly', FG)])
        app.review_choice = ttk.Combobox(right, textvariable=app.review_status, values=REVIEW_STATUSES,
                                         state='disabled', style='Review.TCombobox')
        app.review_choice.grid(row=4, column=0, sticky='ew', padx=14)
        tk.Label(right, text='Reviewer notes', bg=SURFACE, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=5, column=0, sticky='w', padx=14, pady=(10, 5))
        app.review_notes = tk.Text(right, height=3, width=20, wrap='word', bg='#101a15', fg=FG,
                                   insertbackground=FG, relief='flat', font=('Segoe UI', 10), state='disabled')
        app.review_notes.grid(row=6, column=0, sticky='ew', padx=14)
        app.review_feedback = tk.StringVar(value='Select an event to review.')
        tk.Label(right, textvariable=app.review_feedback, bg=SURFACE, fg=GREEN,
                 font=('Segoe UI', 9)).grid(row=7, column=0, sticky='w', padx=14, pady=10)
        footer = tk.Frame(main, bg=BG)
        footer.grid(row=5, column=0, sticky='ew', pady=(16, 0))
        HomePage.button(footer, '← Session library', lambda: app.open_workspace('review')).pack(side='left')
        self.pdf_button = HomePage.button(footer, 'Export PDF', app.export_pdf)
        self.pdf_button.pack(side='left', padx=8)
        app.save_review_button = HomePage.button(footer, 'Save review', app.save_review,
                                                  background=GREEN, foreground='#152016')
        app.save_review_button.pack(side='right')
        tk.Label(main, text='Review the context before deciding. Flags alone do not establish cheating.',
                 bg=BG, fg=SECONDARY, font=('Segoe UI', 9)).grid(row=6, column=0, sticky='w', pady=(12, 0))
        app.review_status.trace_add('write', self.track_changes)
        app.review_notes.bind('<<Modified>>', self.notes_modified)
        main.bind('<Configure>', lambda event: self.summary_label.configure(wraplength=max(260, event.width - 8)))
        right.bind('<Configure>', lambda event: self.event_label.configure(wraplength=max(200, event.width - 28)))
        self.reset()

    def player_state(self, available, playing):
        for button in (getattr(self, 'pause_button', None), getattr(self, 'restart_button', None)):
            if button is not None:
                button.configure(state='normal' if available else 'disabled', disabledforeground='#64756a')
        if hasattr(self, 'pause_button'):
            self.pause_button.configure(text='Pause' if playing else 'Play')

    def reset(self):
        self.current_event = None
        self.saved_values = ('Unreviewed', '')
        self.viewer.clear()
        self.event_title.set('Select an event')
        for button in (self.snapshot_button, self.app.clip_button, self.app.save_review_button,
                       self.previous_button, self.next_button):
            button.configure(state='disabled', disabledforeground='#64756a')
        self.app.save_review_button.configure(bg='#22312a', highlightbackground='#22312a')

    def refresh_report(self, report):
        self.title.set(str(report.get('session_name') or report.get('session_id') or 'Session review'))
        self.refresh_progress()
        if self.app.report_events:
            self.empty.place_forget()
        else:
            self.empty.place(relx=.5, rely=.5, anchor='center')
        self.pdf_button.configure(state='normal' if self.app.loaded_report is not None else 'disabled')

    def refresh_progress(self):
        events = self.app.report_events
        reviewed = sum(event.get('review', {}).get('status') in ('Reviewed', 'False alarm') for event in events)
        self.completion.set(f'{reviewed} of {len(events)} events reviewed · {len(events) - reviewed} remaining')
        self.progress['value'] = reviewed / len(events) * 100 if events else 0
        for index, event in enumerate(events):
            self.app.table.item(str(index), tags=('reviewed' if event.get('review', {}).get('status') in
                                                  ('Reviewed', 'False alarm') else 'pending',))

    def show_event(self, index):
        self.current_event = index
        self.app.save_review_button.configure(bg=GREEN, highlightbackground=GREEN)
        event = self.app.report_events[index]
        start = event.get('start_seconds', 0)
        end = event.get('end_seconds', event.get('last_signal_seconds', start))
        self.event_title.set(f"Event {index + 1} · {start:.1f}s–{end:.1f}s ({max(0, end - start):.1f}s)\n" +
                             ', '.join(event.get('reasons', [])))
        self.saved_values = (self.app.review_status.get(), self.app.review_notes.get('1.0', 'end-1c'))
        self.app.review_notes.edit_modified(False)
        self.snapshot_button.configure(state='normal' if event.get('screenshot') else 'disabled')
        self.previous_button.configure(state='normal' if index > 0 else 'disabled')
        self.next_button.configure(state='normal' if index + 1 < len(self.app.report_events) else 'disabled')
        self.show_snapshot()

    def show_snapshot(self):
        if self.current_event is None:
            return
        name = self.app.report_events[self.current_event].get('screenshot')
        if not name:
            self.viewer.clear('No screenshot was saved for this event.\nTry its clip if available.')
            return
        try:
            path = Path(name)
            path = (path if path.is_absolute() else self.app.root_path / path).resolve()
            path.relative_to((self.app.root_path / 'outputs/screenshots').resolve())
            self.viewer.load_image(path)
        except (OSError, ValueError, ImportError):
            self.viewer.clear('Screenshot unavailable. The file may have been moved or removed.')

    def move(self, direction):
        if self.current_event is not None:
            index = self.current_event + direction
            if 0 <= index < len(self.app.report_events):
                self.app.table.selection_set(str(index))
                self.app.table.see(str(index))
                self.app.show_evidence()

    def has_unsaved(self):
        return self.current_event is not None and self.saved_values != (
            self.app.review_status.get(), self.app.review_notes.get('1.0', 'end-1c'))

    def can_leave(self):
        if not self.has_unsaved():
            return True
        discard = messagebox.askyesno('Unsaved review',
            'Discard unsaved changes?\n\nChoose No to return and save your review first.', default='no', icon='warning')
        if discard:
            self.saved_values = (self.app.review_status.get(), self.app.review_notes.get('1.0', 'end-1c'))
        return discard

    def mark_saved(self):
        self.saved_values = (self.app.review_status.get(), self.app.review_notes.get('1.0', 'end-1c'))
        self.refresh_progress()

    def track_changes(self, *_args):
        if not self.loading and self.has_unsaved():
            self.app.review_feedback.set('Unsaved changes · click Save review')

    def notes_modified(self, _event=None):
        if self.app.review_notes.edit_modified():
            self.track_changes()
            self.app.review_notes.edit_modified(False)

    def hide(self):
        self.viewer.stop()
        self.place_forget()
