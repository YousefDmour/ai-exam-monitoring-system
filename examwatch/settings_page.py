"""Saved defaults for display, exam rules, and evidence recording."""
import tkinter as tk
from tkinter import ttk, messagebox
from copy import deepcopy

from examwatch.home_page import BG, SURFACE, SIDEBAR, BORDER, FG, SECONDARY, GREEN, HomePage
from examwatch.exam_rules import SUPPORTED_OBJECTS
from examwatch.preferences import DEFAULT_PREFERENCES


class SettingsPage(tk.Frame):
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
        for key, title in (('home', 'Overview'), ('live', 'New session'), ('review', 'Session library'),
                           ('evaluation', 'Accuracy evaluation'), ('settings', 'Settings')):
            HomePage.button(sidebar, title, lambda key=key: app.open_workspace(key),
                            background='#233128' if key == 'settings' else SIDEBAR,
                            foreground=GREEN if key == 'settings' else SECONDARY).pack(
                                fill='x', padx=12, pady=(28 if key == 'home' else 4, 4))
        self.exit_button = HomePage.button(sidebar, 'Exit app', app.close,
                                           background='#302321', foreground='#efb8a9')
        self.exit_button.pack(side='bottom', fill='x', padx=22, pady=25)
        main = tk.Frame(self, bg=BG)
        main.grid(row=0, column=1, sticky='nsew', padx=26, pady=22)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)
        tk.Label(main, text='WORKSPACE  /  SETTINGS', bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w')
        heading = tk.Frame(main, bg=BG)
        heading.grid(row=1, column=0, sticky='ew', pady=(18, 20))
        tk.Label(heading, text='Make it your workspace.', bg=BG, fg=FG,
                 font=('Segoe UI', 24, 'bold')).pack(anchor='w')
        tk.Label(heading, text='Save defaults for future sessions. Each session can still have its own rules.',
                 bg=BG, fg=SECONDARY, font=('Segoe UI', 10), wraplength=650, justify='left').pack(anchor='w', pady=(6, 0))
        outer = tk.Frame(main, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        outer.grid(row=2, column=0, sticky='nsew')
        canvas = tk.Canvas(outer, bg=SURFACE, highlightthickness=0)
        self.canvas = canvas
        scroll = ttk.Scrollbar(outer, command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        form = tk.Frame(canvas, bg=SURFACE)
        window = canvas.create_window((0, 0), window=form, anchor='nw')
        form.bind('<Configure>', lambda _event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=event.width))

        def wheel(event):
            widget = event.widget
            if widget.winfo_class() == 'TSpinbox':
                return
            while widget is not None:
                if widget == canvas:
                    canvas.yview_scroll(int(-event.delta / 120), 'units')
                    break
                widget = getattr(widget, 'master', None)
        parent.bind('<MouseWheel>', wheel, add='+')
        self.variables = {}

        def title(text):
            tk.Label(form, text=text, bg=SURFACE, fg=FG,
                     font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=20, pady=(20, 10))

        def check(key, text):
            variable = tk.BooleanVar()
            self.variables[key] = variable
            widget = tk.Checkbutton(form, text=text, variable=variable, bg=SURFACE, fg=FG,
                                    selectcolor='#24332b', activebackground=SURFACE, activeforeground=FG,
                                    font=('Segoe UI', 10))
            widget.pack(anchor='w', padx=17, pady=4)
            return widget

        title('01  Display')
        check('fullscreen', 'Open the app in fullscreen')
        tk.Label(form, text='Esc exits fullscreen. F11 toggles it without changing the saved default.',
                 bg=SURFACE, fg=SECONDARY, font=('Segoe UI', 9), wraplength=640, justify='left').pack(anchor='w', padx=22)
        title('02  Session defaults')
        inputs = tk.Frame(form, bg=SURFACE)
        inputs.pack(fill='x', padx=20)
        inputs.columnconfigure(0, weight=1)
        inputs.columnconfigure(1, weight=1)
        style = ttk.Style()
        style.configure('Settings.TSpinbox', fieldbackground='#24332b', background='#24332b',
                        foreground=FG, arrowcolor=GREEN, padding=7)
        for index, (key, text, low, high, step) in enumerate((
                ('camera', 'Camera index', 0, 10, 1), ('confidence', 'Object confidence', .05, 1, .05),
                ('minimum_duration', 'Confirm alerts after (seconds)', .1, 30, .1),
                ('absence_duration', 'Face absence threshold (seconds)', .1, 60, .5))):
            variable = tk.StringVar()
            self.variables[key] = variable
            group = tk.Frame(inputs, bg=SURFACE)
            group.grid(row=index // 2, column=index % 2, sticky='ew', padx=(0, 16), pady=8)
            tk.Label(group, text=text, bg=SURFACE, fg=SECONDARY,
                     font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 5))
            ttk.Spinbox(group, textvariable=variable, from_=low, to=high, increment=step,
                         width=12, style='Settings.TSpinbox').pack(fill='x')
        title('03  Evidence recording')
        clip_check = check('save_clips', 'Save silent event clips by default')
        self.variables['clip_duration_seconds'] = tk.StringVar()
        tk.Label(form, text='Total clip duration · 5–15 seconds, split evenly before and after the alert',
                 bg=SURFACE, fg=SECONDARY, font=('Segoe UI', 9), wraplength=630,
                 justify='left').pack(anchor='w', padx=22, pady=(8, 5))
        self.clip_duration = ttk.Spinbox(form, textvariable=self.variables['clip_duration_seconds'], from_=5, to=15,
                                         increment=1, width=10, style='Settings.TSpinbox')
        self.clip_duration.pack(anchor='w', padx=22)
        clip_check.configure(command=self.update_clip_state)
        title('04  Default forbidden objects')
        choices = tk.Frame(form, bg=SURFACE)
        choices.pack(fill='x', padx=18, pady=(0, 18))
        self.object_variables = {}
        for index, name in enumerate(SUPPORTED_OBJECTS):
            variable = tk.BooleanVar()
            self.object_variables[name] = variable
            choices.columnconfigure(index % 3, weight=1)
            tk.Checkbutton(choices, text=name.title(), variable=variable, bg=SURFACE, fg=FG,
                           selectcolor='#24332b', activebackground=SURFACE, activeforeground=FG,
                           font=('Segoe UI', 10)).grid(row=index // 3, column=index % 3, sticky='w', pady=5)
        self.feedback = tk.StringVar(value=app.settings_warning or 'Settings are saved on this device. Existing sessions are not changed.')
        self.feedback_label = tk.Label(main, textvariable=self.feedback, bg=BG, fg=SECONDARY,
                                       font=('Segoe UI', 9), wraplength=700, justify='left')
        self.feedback_label.grid(row=3, column=0, sticky='w', pady=(12, 10))
        footer = tk.Frame(main, bg=BG)
        footer.grid(row=4, column=0, sticky='ew')
        self.reset_button = HomePage.button(footer, 'Restore defaults', self.restore)
        self.reset_button.pack(side='left')
        self.save_button = HomePage.button(footer, 'Save settings', self.save, background=GREEN, foreground='#152016')
        self.save_button.pack(side='right')
        main.bind('<Configure>', lambda event: self.feedback_label.configure(wraplength=max(260, event.width - 8)))
        self.load_fields(app.preferences)

    def load_fields(self, preferences):
        for key, variable in self.variables.items():
            variable.set(preferences[key])
        for name, variable in self.object_variables.items():
            variable.set(name in preferences['forbidden_objects'])
        self.update_clip_state()

    def update_clip_state(self):
        self.clip_duration.configure(state='normal' if self.variables['save_clips'].get() else 'disabled')

    def restore(self):
        self.load_fields(deepcopy(DEFAULT_PREFERENCES))
        self.feedback.set('Default values loaded. Click Save settings to keep them.')

    def save(self):
        values = {key: variable.get() for key, variable in self.variables.items()}
        values['forbidden_objects'] = [name for name, variable in self.object_variables.items() if variable.get()]
        try:
            self.feedback.set(self.app.save_app_preferences(values))
        except (OSError, ValueError, TypeError) as error:
            messagebox.showerror('Settings not saved', str(error))
