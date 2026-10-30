"""Dark evaluation workspace: independent labels, measured metrics, saved results."""
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from examwatch.evaluation import annotation_template, evaluate_report
from examwatch.home_page import BG, SURFACE, SIDEBAR, BORDER, FG, SECONDARY, GREEN, HomePage


class EvaluationPanel(tk.Frame):
    def __init__(self, parent, root_path, navigate, close):
        super().__init__(parent, bg=BG)
        self.root_path = root_path
        self.metric_result = None
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
            HomePage.button(sidebar, title, lambda key=key: navigate(key),
                            background='#233128' if key == 'evaluation' else SIDEBAR,
                            foreground=GREEN if key == 'evaluation' else SECONDARY).pack(
                                fill='x', padx=12, pady=(28 if key == 'home' else 4, 4))
        self.exit_button = HomePage.button(sidebar, 'Exit app', close,
                                           background='#302321', foreground='#efb8a9')
        self.exit_button.pack(side='bottom', fill='x', padx=22, pady=25)
        main = tk.Frame(self, bg=BG)
        main.grid(row=0, column=1, sticky='nsew', padx=26, pady=22)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(6, weight=1)
        tk.Label(main, text='WORKSPACE  /  ACCURACY EVALUATION', bg=BG, fg=SECONDARY,
                 font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w')
        heading = tk.Frame(main, bg=BG)
        heading.grid(row=1, column=0, sticky='ew', pady=(18, 16))
        tk.Label(heading, text='Measure what matters.', bg=BG, fg=FG,
                 font=('Segoe UI', 24, 'bold')).pack(anchor='w')
        tk.Label(heading, text='Compare detected events with independent labels, then inspect the results.',
                 bg=BG, fg=SECONDARY, font=('Segoe UI', 10), wraplength=650,
                 justify='left').pack(anchor='w', pady=(6, 0))
        selector = tk.Frame(main, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        selector.grid(row=2, column=0, sticky='ew')
        selector.columnconfigure(0, weight=1)
        tk.Label(selector, text='SAVED SESSION', bg=SURFACE, fg=SECONDARY,
                 font=('Segoe UI', 8, 'bold')).grid(row=0, column=0, sticky='w', padx=14, pady=(12, 5))
        style = ttk.Style()
        style.configure('Eval.TCombobox', fieldbackground='#24332b', background='#24332b', foreground=FG,
                        arrowcolor=GREEN, padding=7)
        style.map('Eval.TCombobox', fieldbackground=[('readonly', '#24332b')], foreground=[('readonly', FG)])
        self.choice = ttk.Combobox(selector, state='readonly', width=30, style='Eval.TCombobox')
        self.choice.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 12))
        self.choice.bind('<<ComboboxSelected>>', lambda _event: self.clear_result())
        self.refresh_button = HomePage.button(selector, 'Refresh sessions', self.refresh)
        self.refresh_button.grid(row=1, column=1, padx=(0, 14), pady=(0, 12))
        actions = tk.Frame(main, bg=BG)
        actions.grid(row=3, column=0, sticky='ew', pady=(12, 0))
        self.export_button = HomePage.button(actions, '1  Export label template', self.export_template)
        self.export_button.pack(side='left')
        self.import_button = HomePage.button(actions, '2  Import labels & evaluate', self.run,
                                              background=GREEN, foreground='#152016')
        self.import_button.pack(side='left', padx=8)
        self.chart = tk.Canvas(main, height=118, bg=BG, highlightthickness=0)
        self.chart.grid(row=4, column=0, sticky='ew', pady=(16, 12))
        self.chart.bind('<Configure>', lambda _event: self.draw_metrics())
        self.result_text = tk.StringVar()
        result_label = tk.Label(main, textvariable=self.result_text, bg=BG, fg=SECONDARY,
                               font=('Segoe UI', 10), wraplength=700, justify='left', anchor='w')
        result_label.grid(row=5, column=0, sticky='ew', pady=(0, 12))
        table_frame = tk.Frame(main, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        table_frame.grid(row=6, column=0, sticky='nsew')
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        style.configure('Eval.Treeview', background=SURFACE, fieldbackground=SURFACE, foreground=FG,
                        rowheight=32, borderwidth=0, font=('Segoe UI', 9))
        style.configure('Eval.Treeview.Heading', background='#202d27', foreground=SECONDARY,
                        padding=9, relief='flat', font=('Segoe UI', 9))
        self.table = ttk.Treeview(table_frame, columns=('reason', 'tp', 'fp', 'fn'), show='headings',
                                  height=4, style='Eval.Treeview')
        for key, label, width in (('reason', 'REASON', 200), ('tp', 'MATCHED', 110),
                                  ('fp', 'FALSE ALERTS', 110), ('fn', 'MISSED', 110)):
            self.table.heading(key, text=label, anchor='w')
            self.table.column(key, width=width, minwidth=80, anchor='w')
        self.table.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(table_frame, command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.table.configure(yscrollcommand=scrollbar.set)
        self.method_label = tk.Label(main,
            text='Label the entire processed timeline independently. Matching uses one-to-one intervals per reason at IoU ≥ 0.30.\n'
                 'N/A means insufficient denominators. These metrics do not establish overall cheating-detection accuracy.',
            bg=BG, fg=SECONDARY, font=('Segoe UI', 9), wraplength=700, justify='left', anchor='w')
        self.method_label.grid(row=7, column=0, sticky='ew', pady=(12, 0))
        main.bind('<Configure>', lambda event: (
            result_label.configure(wraplength=max(260, event.width - 8)),
            self.method_label.configure(wraplength=max(260, event.width - 8))))
        self.refresh()

    def refresh(self):
        selected_path = self.reports[self.choice.current()] if hasattr(self, 'reports') and 0 <= self.choice.current() < len(self.reports) else None
        self.reports = sorted((self.root_path / 'outputs/session_reports').glob('*.json'), reverse=True)
        labels = []
        for path in self.reports:
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                labels.append(f"{data.get('session_name') or path.stem} | {path.stem}")
            except (OSError, ValueError, AttributeError):
                labels.append(path.stem)
        self.choice['values'] = labels
        if labels:
            self.choice.current(self.reports.index(selected_path) if selected_path in self.reports else 0)
        else:
            self.choice.set('')
        self.export_button.configure(state='normal' if labels else 'disabled')
        self.import_button.configure(state='normal' if labels else 'disabled')
        self.clear_result()

    def clear_result(self):
        self.metric_result = None
        self.draw_metrics()
        self.result_text.set('No evaluation yet. Import independently completed labels to see measured results.')
        self.table.delete(*self.table.get_children())
        try:
            path, report = self.selected()
            saved = self.root_path / 'outputs/evaluations' / (path.stem + '_evaluation.json')
            if saved.is_file():
                result = json.loads(saved.read_text(encoding='utf-8'))
                if result.get('session_id') == report.get('session_id'):
                    self.display(result, report)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            self.metric_result = None
            self.draw_metrics()
            self.table.delete(*self.table.get_children())

    def selected(self):
        index = self.choice.current()
        if not 0 <= index < len(self.reports):
            raise ValueError('Select a saved session first.')
        return self.reports[index], json.loads(self.reports[index].read_text(encoding='utf-8'))

    def export_template(self):
        try:
            path, report = self.selected()
            target = filedialog.asksaveasfilename(title='Save ground-truth template',
                defaultextension='.json', initialfile=path.stem + '_labels.json', filetypes=[('JSON', '*.json')])
            if target:
                from pathlib import Path
                Path(target).write_text(json.dumps(annotation_template(report), indent=2, ensure_ascii=False), encoding='utf-8')
                messagebox.showinfo('Template saved', 'Label all target events with start_seconds, end_seconds, and reasons. Set complete=true only after reviewing the entire video.')
        except (OSError, ValueError, KeyError, TypeError) as error:
            messagebox.showerror('Template error', str(error))

    def run(self):
        try:
            path, report = self.selected()
            source = filedialog.askopenfilename(title='Import completed ground-truth labels', filetypes=[('JSON', '*.json')])
            if not source:
                return
            from pathlib import Path
            result = evaluate_report(report, json.loads(Path(source).read_text(encoding='utf-8')))
            directory = self.root_path / 'outputs/evaluations'
            directory.mkdir(parents=True, exist_ok=True)
            destination = directory / (path.stem + '_evaluation.json')
            destination.write_text(json.dumps(result, indent=2), encoding='utf-8')
            self.display(result, report)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            messagebox.showerror('Evaluation error', str(error))

    def draw_metrics(self):
        self.chart.delete('all')
        width = max(300, self.chart.winfo_width())
        card_width = (width - 20) / 3
        for index, (key, label) in enumerate((('precision', 'PRECISION'), ('recall', 'RECALL'), ('f1', 'F1 SCORE'))):
            x = index * (card_width + 10)
            value = self.metric_result.get(key) if self.metric_result else None
            self.chart.create_rectangle(x, 1, x + card_width - 1, 116, fill=SURFACE, outline=BORDER)
            self.chart.create_text(x + 14, 21, text=label, fill=SECONDARY, anchor='w', font=('Segoe UI', 9, 'bold'))
            self.chart.create_text(x + 14, 55, text='N/A' if value is None else f'{value:.1%}', fill=FG,
                                   anchor='w', font=('Segoe UI', 25, 'bold'))
            self.chart.create_rectangle(x + 14, 88, x + card_width - 15, 94, fill='#293c30', outline='')
            if value is not None:
                self.chart.create_rectangle(x + 14, 88, x + 14 + (card_width - 29) * max(0, min(1, value)),
                                             94, fill=GREEN, outline='')
            self.chart.create_text(x + 14, 106, text='Independent interval matching', fill=SECONDARY,
                                   anchor='w', font=('Segoe UI', 8))

    def display(self, result, report):
        self.metric_result = result
        speed = report.get('processing_fps')
        fps = 'N/A' if speed is None else f'{speed:.1f} FPS'
        self.result_text.set(f"Matched: {result['tp']} | False alerts: {result['fp']} | Missed: {result['fn']} | "
                             f"False alerts/min: {result['false_alerts_per_minute']:.2f}\n"
                             f"Processing speed: {fps} | Results saved in outputs/evaluations")
        self.draw_metrics()
        self.table.delete(*self.table.get_children())
        for reason, counts in result['per_reason'].items():
            self.table.insert('', 'end', values=(reason, counts['tp'], counts['fp'], counts['fn']))
