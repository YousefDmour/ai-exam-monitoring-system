"""Dark session preparation page, separate from active monitoring."""
import tkinter as tk
from tkinter import ttk

from examwatch.home_page import BG, SURFACE, SIDEBAR, BORDER, FG, SECONDARY, GREEN, HomePage
from examwatch.exam_rules import SUPPORTED_OBJECTS


class NewSessionPage(tk.Frame):
    def __init__(self, parent, dashboard):
        super().__init__(parent, bg=BG)
        self.app = dashboard
        style = ttk.Style()
        for name in ('Setup.TCombobox', 'Setup.TSpinbox'):
            style.configure(name, fieldbackground='#24332b', background='#24332b', foreground=FG,
                            arrowcolor=GREEN, bordercolor=BORDER, padding=6)
            style.map(name, fieldbackground=[('readonly', '#24332b'), ('disabled', '#17211f')],
                      foreground=[('readonly', FG), ('disabled', SECONDARY)],
                      selectbackground=[('readonly', '#24332b')], selectforeground=[('readonly', FG)])
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
            button = HomePage.button(sidebar, title, lambda key=key: dashboard.open_workspace(key),
                        background='#233128' if key == 'live' else SIDEBAR,
                        foreground=GREEN if key == 'live' else SECONDARY)
            button.pack(fill='x', padx=12, pady=(28 if key == 'home' else 4, 4))
        self.exit_button = HomePage.button(sidebar, 'Exit app', dashboard.close,
                                           background='#302321', foreground='#efb8a9')
        self.exit_button.pack(side='bottom', fill='x', padx=22, pady=25)
        main = tk.Frame(self, bg=BG)
        main.grid(row=0, column=1, sticky='nsew', padx=26, pady=22)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)
        tk.Label(main, text='WORKSPACE  /  NEW SESSION', bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w')
        heading = tk.Frame(main, bg=BG)
        heading.grid(row=1, column=0, sticky='ew', pady=(18, 18))
        tk.Label(heading, text='Set up your next session.', bg=BG, fg=FG,
                 font=('Segoe UI', 24, 'bold')).pack(anchor='w')
        tk.Label(heading, text='Choose a source, define the exam rules, and start when you are ready.',
                 bg=BG, fg=SECONDARY, font=('Segoe UI', 10), wraplength=650,
                 justify='left').pack(anchor='w', pady=(6, 0))

        body = tk.Frame(main, bg=BG)
        body.grid(row=2, column=0, sticky='nsew')
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        container = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        container.grid(row=0, column=0, sticky='nsew', padx=(0, 16))
        canvas = tk.Canvas(container, bg=SURFACE, highlightthickness=0, width=360)
        self.form_canvas = canvas
        scrollbar = ttk.Scrollbar(container, command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        form = tk.Frame(canvas, bg=SURFACE)
        window = canvas.create_window((0, 0), window=form, anchor='nw')
        form.bind('<Configure>', lambda _event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=event.width))
        def scroll_form(event):
            widget = event.widget
            if widget.winfo_class() in ('TSpinbox', 'TCombobox'):
                return
            while widget is not None:
                if widget == canvas:
                    canvas.yview_scroll(int(-event.delta / 120), 'units')
                    break
                widget = getattr(widget, 'master', None)
        parent.bind('<MouseWheel>', scroll_form, add='+')
        self.controls = []

        def label(text, section=False):
            tk.Label(form, text=text, bg=SURFACE, fg=FG if section else SECONDARY,
                     font=('Segoe UI', 13 if section else 10, 'bold' if section else 'normal')).pack(
                         anchor='w', padx=18, pady=(18 if section else 10, 6))

        def entry(variable):
            widget = tk.Entry(form, textvariable=variable, bg='#24332b', fg=FG, insertbackground=FG,
                              relief='flat', font=('Segoe UI', 11))
            widget.pack(fill='x', padx=18, ipady=7)
            self.controls.append(widget)
            return widget

        label('01  Session details', True)
        label('Session name (optional)')
        entry(dashboard.session_name)
        label('02  Input source', True)
        source = ttk.Combobox(form, textvariable=dashboard.source_type, values=('Camera', 'Video file'),
                              state='readonly', style='Setup.TCombobox')
        source.pack(fill='x', padx=18)
        self.source_choice = source
        self.controls.append(source)
        source.bind('<<ComboboxSelected>>', lambda _event: self.update_source())
        self.camera_group = tk.Frame(form, bg=SURFACE)
        self.camera_group.pack(fill='x', padx=18, pady=10)
        tk.Label(self.camera_group, text='Camera index', bg=SURFACE, fg=SECONDARY).pack(anchor='w')
        camera = ttk.Spinbox(self.camera_group, from_=0, to=10, textvariable=dashboard.camera,
                             width=8, style='Setup.TSpinbox')
        camera.pack(anchor='w', pady=6)
        self.controls.append(camera)
        self.video_group = tk.Frame(form, bg=SURFACE)
        browse = HomePage.button(self.video_group, 'Choose video...', dashboard.choose_video)
        browse.pack(fill='x')
        self.controls.append(browse)
        tk.Label(self.video_group, textvariable=dashboard.video_label, bg=SURFACE, fg=SECONDARY,
                 wraplength=290, justify='left').pack(anchor='w', pady=6)
        # Both groups share a fixed position above the next section.
        self.source_anchor = tk.Frame(form, bg=SURFACE, height=1)
        self.source_anchor.pack(fill='x')
        label('03  Exam rules', True)
        label('Forbidden objects')
        tk.Label(form, text='Only objects in this list trigger object alerts.', bg=SURFACE, fg=SECONDARY,
                 wraplength=300, justify='left', font=('Segoe UI', 9)).pack(anchor='w', padx=18)
        self.object_choice = ttk.Combobox(form, values=[name.title() for name in SUPPORTED_OBJECTS],
                                          state='readonly', style='Setup.TCombobox')
        self.object_choice.pack(fill='x', padx=18, pady=(10, 6))
        self.object_choice.current(0)
        self.controls.append(self.object_choice)
        actions = tk.Frame(form, bg=SURFACE)
        actions.pack(fill='x', padx=18)
        add = HomePage.button(actions, '+ Add', self.add_object)
        remove = HomePage.button(actions, 'Remove selected', self.remove_object)
        add.pack(side='left')
        remove.pack(side='left', padx=8)
        self.controls += [add, remove]
        self.objects = tk.Listbox(form, height=4, bg='#101a15', fg=FG, selectbackground='#395c39',
                                 selectforeground=FG, highlightthickness=0, relief='flat',
                                 exportselection=False, font=('Segoe UI', 10))
        self.objects.pack(fill='x', padx=18, pady=10)
        self.controls.append(self.objects)
        self.rule_feedback = tk.StringVar(value='Choose from supported model categories; custom objects require a trained model.')
        tk.Label(form, textvariable=self.rule_feedback, bg=SURFACE, fg=SECONDARY,
                 wraplength=300, justify='left', font=('Segoe UI', 9)).pack(anchor='w', padx=18)
        clips = tk.Checkbutton(form, text='Save event clips', variable=dashboard.save_clips,
                               bg=SURFACE, fg=FG, selectcolor='#24332b', activebackground=SURFACE,
                               activeforeground=FG, command=self.update_clip_controls)
        clips.pack(anchor='w', padx=15, pady=(18, 6))
        self.controls.append(clips)
        label('Clip duration · total seconds (5–15)')
        self.duration = ttk.Spinbox(form, from_=5, to=15, increment=1,
                                    textvariable=dashboard.clip_duration, width=10, style='Setup.TSpinbox')
        self.duration.pack(anchor='w', padx=18)
        self.controls.append(self.duration)
        tk.Label(form, text='Half before the alert, half after. Shorter near session boundaries.', bg=SURFACE,
                 fg=SECONDARY, wraplength=300, justify='left', font=('Segoe UI', 9)).pack(anchor='w', padx=18, pady=8)
        self.advanced_button = HomePage.button(form, '▸  Advanced settings', self.toggle_advanced)
        self.advanced_button.pack(fill='x', padx=18, pady=14)
        self.advanced = tk.Frame(form, bg=SURFACE)
        for title, variable, low, high, step in (
                ('Confirm after (seconds)', dashboard.minimum, .1, 30, .1),
                ('Face absence (seconds)', dashboard.absence, .1, 60, .5),
                ('Object confidence', dashboard.confidence, .05, 1, .05)):
            tk.Label(self.advanced, text=title, bg=SURFACE, fg=SECONDARY).pack(anchor='w', pady=(6, 4))
            spin = ttk.Spinbox(self.advanced, textvariable=variable, from_=low, to=high,
                               increment=step, style='Setup.TSpinbox')
            spin.pack(fill='x')
            self.controls.append(spin)
        reset = HomePage.button(self.advanced, 'Reset to defaults', self.reset_defaults)
        reset.pack(anchor='w', pady=12)
        self.controls.append(reset)
        self.controls.append(self.advanced_button)

        ready = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        ready.grid(row=0, column=1, sticky='nsew')
        tk.Label(ready, text='Before you begin', bg=SURFACE, fg=FG,
                 font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=20, pady=(22, 14))
        self.readiness = tk.StringVar()
        tk.Label(ready, textvariable=self.readiness, bg=SURFACE, fg=GREEN,
                 font=('Segoe UI', 12, 'bold'), wraplength=220, justify='left').pack(anchor='w', padx=20)
        for title, text in (('01  Frame your face', 'Use good lighting and keep one person visible.'),
                            ('02  Calibrate', 'Camera opens in preview only. Choose Calibrate gaze, follow the five screen targets, then Start exam.'),
                            ('03  Review later', 'Your reports, notes, and evidence are saved on this device.')):
            tk.Label(ready, text=title, bg=SURFACE, fg=FG, font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=20, pady=(22, 6))
            tk.Label(ready, text=text, bg=SURFACE, fg=SECONDARY, font=('Segoe UI', 10),
                     wraplength=215, justify='left').pack(anchor='w', padx=20)
        self.feedback = tk.StringVar(value='Your camera stays off until you start.')
        tk.Label(main, textvariable=self.feedback, bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9), wraplength=700, justify='left').grid(row=3, column=0, sticky='w', pady=(12, 8))
        footer = tk.Frame(main, bg=BG)
        footer.grid(row=4, column=0, sticky='ew')
        HomePage.button(footer, '← Back to overview', dashboard.show_home).pack(side='left')
        self.start_button = HomePage.button(footer, 'Start session  →', dashboard.start_configured_session,
                                            background=GREEN, foreground='#152016')
        self.start_button.pack(side='right')
        self.refresh()

    def refresh(self):
        self.objects.delete(0, 'end')
        for name in self.app.forbidden_objects:
            self.objects.insert('end', name.title())
        self.update_source()
        self.update_clip_controls()

    def update_source(self):
        self.camera_group.pack_forget()
        self.video_group.pack_forget()
        group = self.video_group if self.app.source_type.get() == 'Video file' else self.camera_group
        group.pack(fill='x', padx=18, pady=10, before=self.source_anchor)
        self.readiness.set('Video selected' if self.app.video_path.get() and self.app.source_type.get() == 'Video file'
                           else 'Choose your video' if self.app.source_type.get() == 'Video file'
                           else 'Live camera session')
        self.start_button.configure(text='Analyze video  →' if self.app.source_type.get() == 'Video file' else 'Open camera  →')

    def add_object(self):
        name = self.object_choice.get().upper()
        if name not in SUPPORTED_OBJECTS:
            self.rule_feedback.set('Choose a supported category from the list.')
        elif name in self.app.forbidden_objects:
            self.rule_feedback.set('This object is already forbidden.')
        else:
            self.app.forbidden_objects.append(name)
            self.rule_feedback.set(name.title() + ' added to forbidden objects.')
            self.refresh()

    def remove_object(self):
        selected = self.objects.curselection()
        if selected:
            name = self.app.forbidden_objects.pop(selected[0])
            self.rule_feedback.set(name.title() + ' removed. It will not trigger an object alert.')
            self.refresh()

    def update_clip_controls(self):
        self.duration.configure(state='normal' if self.app.save_clips.get() else 'disabled')

    def toggle_advanced(self):
        if self.advanced.winfo_manager():
            self.advanced.pack_forget()
            self.advanced_button.configure(text='▸  Advanced settings')
        else:
            self.advanced.pack(fill='x', padx=18, pady=(0, 16))
            self.advanced_button.configure(text='▾  Advanced settings')

    def reset_defaults(self):
        self.app.minimum.set(str(self.app.preferences['minimum_duration']))
        self.app.absence.set(str(self.app.preferences['absence_duration']))
        self.app.confidence.set(str(self.app.preferences['confidence']))
