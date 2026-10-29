"""Ground-truth import, evaluation metrics, and a small dashboard."""
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from examwatch.evaluation import annotation_template, evaluate_report


class EvaluationPanel(ttk.Frame):
    def __init__(self, parent, root_path):
        super().__init__(parent)
        self.root_path = root_path
        top = ttk.Frame(self)
        top.pack(fill='x', pady=18)
        self.choice = ttk.Combobox(top, state='readonly', width=55)
        self.choice.pack(side='left', fill='x', expand=True)
        self.choice.bind('<<ComboboxSelected>>', lambda _event: self.clear_result())
        ttk.Button(top, text='Refresh sessions', command=self.refresh).pack(side='left', padx=8)
        actions = ttk.Frame(self)
        actions.pack(fill='x')
        ttk.Button(actions, text='Export annotation template', command=self.export_template).pack(side='left')
        ttk.Button(actions, text='Import labels & evaluate', command=self.run).pack(side='left', padx=8)
        ttk.Label(self, text='Independently label the entire session timeline. Review decisions alone cannot measure missed events.',
                  wraplength=900).pack(anchor='w', pady=14)
        self.result_text = tk.StringVar(value='No evaluation yet. Export a template, label events, set complete=true, then import it.')
        ttk.Label(self, textvariable=self.result_text, wraplength=1000).pack(anchor='w', pady=10)
        self.chart = tk.Canvas(self, height=160, bg='#131f32', highlightthickness=0)
        self.chart.pack(fill='x', pady=12)
        self.table = ttk.Treeview(self, columns=('reason', 'tp', 'fp', 'fn'), show='headings', height=8)
        for key, heading in (('reason', 'Reason'), ('tp', 'Matched alerts'), ('fp', 'False alerts'), ('fn', 'Missed events')):
            self.table.heading(key, text=heading)
            self.table.column(key, width=160)
        self.table.pack(fill='x')
        ttk.Label(self, text='Matching: one-to-one by reason, interval IoU >= 0.30. Multi-reason episodes share one interval.\n'
                  'N/A means the metric denominator is zero; this is not overall cheating-detection accuracy.',
                  wraplength=1000).pack(anchor='w', pady=12)
        self.refresh()

    def refresh(self):
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
            self.choice.current(0)
        else:
            self.choice.set('')
        self.clear_result()

    def clear_result(self):
        self.result_text.set('Import completed ground-truth labels to evaluate the selected session.')
        self.chart.delete('all')
        self.table.delete(*self.table.get_children())
        try:
            path, report = self.selected()
            saved = self.root_path / 'outputs/evaluations' / (path.stem + '_evaluation.json')
            if saved.is_file():
                result = json.loads(saved.read_text(encoding='utf-8'))
                if result.get('session_id') == report.get('session_id'):
                    self.display(result, report)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass

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

    def display(self, result, report):
        self.result_text.set(f"Matched: {result['tp']} | False alerts: {result['fp']} | Missed: {result['fn']} | "
                             f"False alerts/min: {result['false_alerts_per_minute']:.2f}\n"
                             f"Processing speed: {report.get('processing_fps', 0):.1f} FPS | Results saved in outputs/evaluations")
        self.chart.delete('all')
        for index, (key, label) in enumerate((('precision', 'Precision'), ('recall', 'Recall'), ('f1', 'F1'))):
            y, value = 20 + index * 46, result[key]
            self.chart.create_text(16, y + 10, anchor='w', text=label, fill='#e6edf7')
            self.chart.create_rectangle(115, y, 615, y + 22, fill='#25334a', outline='')
            if value is not None:
                self.chart.create_rectangle(115, y, 115 + 500 * value, y + 22, fill='#31d4b0', outline='')
            self.chart.create_text(635, y + 10, anchor='w', text='N/A' if value is None else f'{value:.1%}', fill='#e6edf7')
        self.table.delete(*self.table.get_children())
        for reason, counts in result['per_reason'].items():
            self.table.insert('', 'end', values=(reason, counts['tp'], counts['fp'], counts['fn']))
