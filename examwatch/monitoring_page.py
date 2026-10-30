"""Camera workspace styled like the overview and session preparation pages."""
import tkinter as tk
from tkinter import ttk

from examwatch.home_page import BG, SURFACE, SIDEBAR, BORDER, FG, SECONDARY, GREEN, HomePage


class MonitoringPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        sidebar = tk.Frame(self, bg=SIDEBAR, width=200)
        sidebar.grid(row=0, column=0, sticky='ns')
        sidebar.grid_propagate(False)
        tk.Label(sidebar, text='◉  ExamWatch', bg=SIDEBAR, fg=FG,
                 font=('Segoe UI', 18, 'bold')).pack(anchor='w', padx=22, pady=(30, 4))
        tk.Label(sidebar, text='EXAM MONITORING', bg=SIDEBAR, fg=SECONDARY,
                 font=('Segoe UI', 8)).pack(anchor='w', padx=23)
        self.nav_buttons = {}
        for key, title in (('home', 'Overview'), ('live', 'New session'),
                           ('review', 'Session library'), ('evaluation', 'Accuracy evaluation'), ('settings', 'Settings')):
            button = HomePage.button(sidebar, title, lambda key=key: app.open_workspace(key),
                                     background='#233128' if key == 'live' else SIDEBAR,
                                     foreground=GREEN if key == 'live' else SECONDARY)
            button.pack(fill='x', padx=12, pady=(28 if key == 'home' else 4, 4))
            self.nav_buttons[key] = button
        tk.Label(sidebar, text='CAMERA WORKSPACE', bg=SIDEBAR, fg=GREEN,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=23, pady=(26, 8))
        tk.Label(sidebar, text='Preview first.\nMonitor when ready.', bg=SIDEBAR, fg=SECONDARY,
                 font=('Segoe UI', 9), justify='left').pack(anchor='w', padx=23)
        self.exit_button = HomePage.button(sidebar, 'Exit app', app.close,
                                           background='#302321', foreground='#efb8a9')
        self.exit_button.pack(side='bottom', fill='x', padx=22, pady=25)

        main = tk.Frame(self, bg=BG)
        main.grid(row=0, column=1, sticky='nsew', padx=26, pady=22)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)
        tk.Label(main, text='WORKSPACE  /  CAMERA SESSION', bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w')
        header = tk.Frame(main, bg=BG)
        header.grid(row=1, column=0, sticky='ew', pady=(16, 14))
        header.columnconfigure(0, weight=1)
        self.title = tk.StringVar(value='Your camera workspace.')
        self.title_label = tk.Label(header, textvariable=self.title, bg=BG, fg=FG,
                                   font=('Segoe UI', 23, 'bold'), anchor='w', justify='left')
        self.title_label.grid(row=0, column=0, sticky='ew')
        self.phase_badge = tk.Label(header, text='CAMERA OFF', bg='#233128', fg=GREEN,
                                    font=('Segoe UI', 9, 'bold'), padx=12, pady=8)
        self.phase_badge.grid(row=1, column=0, sticky='w', pady=(8, 0))

        steps = tk.Frame(main, bg=BG)
        steps.grid(row=2, column=0, sticky='ew', pady=(0, 12))
        self.step_labels = []
        for index, (label, hint) in enumerate((('01  Preview', 'Get comfortable'),
                                             ('02  Calibrate gaze', 'Follow the screen targets'),
                                             ('03  Start exam', 'Enable monitoring'))):
            steps.columnconfigure(index, weight=1, uniform='steps')
            box = tk.Frame(steps, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
            box.grid(row=0, column=index, sticky='ew', padx=(0 if index == 0 else 5, 0 if index == 2 else 5))
            title = tk.Label(box, text=label, bg=SURFACE, fg=SECONDARY,
                             font=('Segoe UI', 10, 'bold'))
            title.pack(anchor='w', padx=12, pady=(9, 2))
            tk.Label(box, text=hint, bg=SURFACE, fg=SECONDARY,
                     font=('Segoe UI', 8)).pack(anchor='w', padx=12, pady=(0, 9))
            self.step_labels.append((box, title))

        metrics = tk.Frame(main, bg=BG)
        metrics.grid(row=3, column=0, sticky='ew', pady=(0, 12))
        app.metrics = {}
        for index, (key, label, default) in enumerate((('SESSION', 'EXAM TIME', '00:00'),
                                                      ('FACES', 'FACES VISIBLE', '—'),
                                                      ('EPISODES', 'FLAGGED EVENTS', '0'))):
            metrics.columnconfigure(index, weight=1, uniform='metrics')
            card = tk.Frame(metrics, bg=SURFACE)
            card.grid(row=0, column=index, sticky='ew', padx=(0 if index == 0 else 5, 0 if index == 2 else 5))
            tk.Label(card, text=label, bg=SURFACE, fg=SECONDARY,
                     font=('Segoe UI', 8, 'bold')).pack(side='left', padx=12, pady=14)
            variable = tk.StringVar(value=default)
            tk.Label(card, textvariable=variable, bg=SURFACE, fg=FG,
                     font=('Segoe UI', 18, 'bold')).pack(side='right', padx=12)
            app.metrics[key] = variable

        app.preview_viewport = tk.Frame(main, bg='#080f0c', width=640, height=260,
                                        highlightbackground=BORDER, highlightthickness=1)
        app.preview_viewport.grid(row=4, column=0, sticky='nsew')
        app.preview_viewport.grid_propagate(False)
        app.preview = tk.Label(app.preview_viewport, bg='#080f0c', fg=SECONDARY,
                               text='CAMERA IS OFF\n\nOpen your camera to get comfortable before the exam.',
                               font=('Segoe UI', 12), borderwidth=0, highlightthickness=0, padx=0, pady=0)
        app.preview.place(relx=.5, rely=.5, anchor='center', relwidth=1, relheight=1)

        information = tk.Frame(main, bg=BG)
        information.grid(row=5, column=0, sticky='ew', pady=(12, 0))
        information.columnconfigure(0, weight=1)
        app.status = tk.StringVar(value='Ready for a camera preview')
        app.details = tk.StringVar(value='Open camera → Calibrate gaze → Start exam. Preview and calibration do not record alerts.')
        app.quality_text = tk.StringVar(value='Keep your camera and window in the same position after calibration.')
        self.status_label = tk.Label(information, textvariable=app.status, bg=BG, fg=GREEN,
                                      font=('Segoe UI', 11, 'bold'), anchor='w', justify='left')
        self.status_label.grid(row=0, column=0, sticky='ew')
        self.details_label = tk.Label(information, textvariable=app.details, bg=BG, fg=SECONDARY,
                                       font=('Segoe UI', 10), justify='left', anchor='w', wraplength=700)
        self.details_label.grid(row=1, column=0, sticky='ew', pady=(4, 0))
        self.quality_label = tk.Label(information, textvariable=app.quality_text, bg=BG, fg='#d3bc82',
                                       font=('Segoe UI', 9), justify='left', anchor='w', wraplength=700)
        self.quality_label.grid(row=2, column=0, sticky='ew', pady=(4, 0))
        style = ttk.Style()
        style.configure('Monitor.Horizontal.TProgressbar', background=GREEN, troughcolor=SURFACE,
                        bordercolor=SURFACE, lightcolor=GREEN, darkcolor=GREEN, thickness=4)
        app.progress = ttk.Progressbar(main, maximum=100, style='Monitor.Horizontal.TProgressbar')
        app.progress.grid(row=6, column=0, sticky='ew', pady=(12, 14))
        actions = tk.Frame(main, bg=BG)
        actions.grid(row=7, column=0, sticky='ew')
        app.start_button = HomePage.button(actions, 'Open camera', app.start)
        app.start_button.pack(side='left')
        app.calibrate_button = HomePage.button(actions, 'Calibrate gaze', app.begin_calibration)
        app.calibrate_button.pack(side='left', padx=8)
        app.exam_button = HomePage.button(actions, 'Start exam', app.begin_exam,
                                          background=GREEN, foreground='#152016')
        app.exam_button.pack(side='left')
        app.stop_button = HomePage.button(actions, 'Close camera', app.stop,
                                          background='#302321', foreground='#efb8a9')
        app.stop_button.pack(side='right')
        for button in (app.calibrate_button, app.exam_button, app.stop_button):
            button.configure(state='disabled', disabledforeground='#64756a')
        app.status.trace_add('write', self.status_changed)
        main.bind('<Configure>', self.resize_text)

    def resize_text(self, event):
        width = max(260, event.width - 8)
        for label in (self.title_label, self.status_label, self.details_label, self.quality_label):
            label.configure(wraplength=width)

    def status_changed(self, *_args):
        text = self.app.status.get()
        color = '#efa796' if 'ALERT' in text or 'FLAGGED' in text else GREEN
        self.status_label.configure(fg=color)

    def update_phase(self, phase):
        title = self.app.session_name.get().strip() or 'Your camera workspace.'
        self.title.set(title)
        active = 0 if phase in ('idle', 'closed', 'opening_camera', 'preview') else 1 if phase in (
            'loading_calibration', 'calibrating', 'ready') else 2
        badge = {'idle': 'CAMERA OFF', 'opening_camera': 'CONNECTING CAMERA', 'preview': 'PREVIEW ONLY',
                 'loading_calibration': 'PREPARING CALIBRATION', 'calibrating': 'GAZE CALIBRATION',
                 'ready': 'READY · MONITORING OFF', 'loading_exam': 'STARTING EXAM',
                 'exam': 'EXAM IN PROGRESS', 'video_analysis': 'VIDEO ANALYSIS', 'closed': 'CAMERA OFF'}
        self.phase_badge.configure(text=badge.get(phase, phase.upper()))
        for index, (box, label) in enumerate(self.step_labels):
            box.configure(highlightbackground=GREEN if index == active else BORDER)
            label.configure(fg=GREEN if index == active else SECONDARY)
        for button, primary in ((self.app.start_button, phase in ('idle', 'closed')),
                                (self.app.calibrate_button, phase == 'preview'),
                                (self.app.exam_button, phase == 'ready')):
            background = GREEN if primary else '#22312a'
            button.configure(bg=background, fg='#152016' if primary else FG,
                             highlightbackground=background, disabledforeground='#64756a')
        if phase == 'idle':
            self.app.preview.configure(image='', text='CAMERA IS OFF\n\nOpen your camera to get comfortable before the exam.')
