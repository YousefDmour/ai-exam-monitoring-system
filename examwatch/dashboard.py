"""Local desktop dashboard. Launch with python app.py."""

import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

from examwatch.monitoring_runner import ROOT, run_monitoring
from examwatch.session_storage import delete_session, save_event_review, REVIEW_STATUSES
from examwatch.evaluation_panel import EvaluationPanel

BG = "#0b1220"
PANEL = "#131f32"
TEXT = "#e6edf7"
MUTED = "#94a8c4"
ACCENT = "#31d4b0"


class Dashboard:
    def __init__(self, root):
        self.root = root
        self.worker = None
        self.messages = queue.Queue(maxsize=2)
        self.stop_event = threading.Event()
        self.recalibrate_event = threading.Event()
        self.closing = False
        self.reports = []
        self.photo = None
        root.title("ExamWatch")
        root.geometry("1260x850")
        root.minsize(1000, 740)
        self.fullscreen = True
        root.attributes("-fullscreen", True)
        root.bind("<Escape>", lambda _event: self.set_fullscreen(False))
        root.bind("<F11>", lambda _event: self.set_fullscreen(not self.fullscreen))
        root.configure(bg=BG)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 11))
        style.configure("TButton", font=("Segoe UI", 10), padding=10)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(22, 12), font=("Segoe UI", 11))
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=TEXT, rowheight=32, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT)

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=28, pady=(22, 16))
        self.exit_button = ttk.Button(header, text="Exit app", command=self.close)
        self.exit_button.pack(side="right", anchor="n", padx=(8, 0))
        self.fullscreen_button = ttk.Button(header, text="Exit fullscreen (Esc)",
                                             command=lambda: self.set_fullscreen(not self.fullscreen))
        self.fullscreen_button.pack(side="right", anchor="n")
        tk.Label(header, text="◉  ExamWatch", bg=BG, fg=TEXT,
                 font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(header, text="AI EXAM MONITORING", bg=BG,
                 fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))
        tabs = ttk.Notebook(root)
        tabs.pack(fill="both", expand=True, padx=28, pady=(0, 12))
        live, review = ttk.Frame(tabs), ttk.Frame(tabs)
        tabs.add(live, text="Live monitoring")
        tabs.add(review, text="Session reports")
        self.build_live(live)
        self.build_review(review)
        self.evaluation_panel = EvaluationPanel(tabs, ROOT)
        tabs.add(self.evaluation_panel, text="Accuracy evaluation")
        tk.Label(root, text="Review assistant • Flags need human review; they do not establish cheating.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(pady=(0, 14))
        self.refresh_reports()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(80, self.poll)

    def set_fullscreen(self, enabled):
        self.fullscreen = bool(enabled)
        self.root.attributes("-fullscreen", self.fullscreen)
        self.fullscreen_button.configure(
            text="Exit fullscreen (Esc)" if self.fullscreen else "Fullscreen (F11)")

    def build_live(self, parent):
        sidebar = tk.Frame(parent, bg=PANEL, width=270)
        sidebar.pack(side="right", fill="y", padx=(18, 0), pady=18)
        sidebar.pack_propagate(False)
        canvas = tk.Canvas(sidebar, bg=PANEL, highlightthickness=0, width=250)
        scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        side = tk.Frame(canvas, bg=PANEL)
        window = canvas.create_window((0, 0), window=side, anchor="nw")
        side.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        tk.Label(side, text="Session settings", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18, pady=18)
        self.camera = tk.StringVar(value="0")
        self.minimum = tk.StringVar(value="1.0")
        self.absence = tk.StringVar(value="3.0")
        self.confidence = tk.StringVar(value="0.40")
        self.inputs = []
        self.session_name = tk.StringVar()
        tk.Label(side, text="Session name (optional)", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(0, 5))
        name_entry = ttk.Entry(side, textvariable=self.session_name)
        name_entry.pack(fill="x", padx=18)
        self.inputs.append(name_entry)
        self.source_type = tk.StringVar(value="Camera")
        self.video_path = tk.StringVar()
        tk.Label(side, text="Input source", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(10, 5))
        source_choice = ttk.Combobox(side, textvariable=self.source_type,
                                     values=("Camera", "Video file"), state="readonly")
        source_choice.pack(fill="x", padx=18)
        self.source_choice = source_choice
        self.inputs.append(source_choice)
        browse = ttk.Button(side, text="Choose video...", command=self.choose_video)
        browse.pack(fill="x", padx=18, pady=(6, 0))
        self.inputs.append(browse)
        self.save_clips = tk.BooleanVar(value=True)
        clip_check = ttk.Checkbutton(side, text="Save event clips (5s + 5s)", variable=self.save_clips)
        clip_check.pack(anchor="w", padx=18, pady=6)
        self.inputs.append(clip_check)
        self.video_label = tk.StringVar(value="No video selected")
        tk.Label(side, textvariable=self.video_label, bg=PANEL, fg=MUTED,
                 wraplength=200, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=4)
        for title, variable, low, high, step in (
            ("Camera index", self.camera, 0, 10, 1),
            ("Confirm after (seconds)", self.minimum, .1, 30, .1),
            ("Face absence (seconds)", self.absence, .1, 60, .5),
            ("Object confidence", self.confidence, .05, 1, .05),
        ):
            tk.Label(side, text=title, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(10, 5))
            spin = ttk.Spinbox(side, textvariable=variable, from_=low, to=high,
                               increment=step, width=20)
            spin.pack(fill="x", padx=18)
            self.inputs.append(spin)
        tk.Label(side, text="Allowed objects", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(22, 5))
        self.allowed = {}
        for name, label in (("CLOCK", "Clock"), ("BOOK", "Book"), ("CELL PHONE", "Phone")):
            var = tk.BooleanVar(value=name == "CLOCK")
            self.allowed[name] = var
            check = ttk.Checkbutton(side, text=label, variable=var)
            check.pack(anchor="w", padx=18, pady=3)
            self.inputs.append(check)
        tk.Label(side, text="Settings apply to the next session.\nLook forward during calibration.",
                 justify="left", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(
                     anchor="w", padx=18, pady=20)

        content = ttk.Frame(parent)
        content.pack(side="left", fill="both", expand=True, pady=18)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)
        metrics = ttk.Frame(content)
        metrics.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.metrics = {}
        for title, default in (("SESSION", "00:00"), ("FACES", "—"), ("EPISODES", "0")):
            card = tk.Frame(metrics, bg=PANEL)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))
            tk.Label(card, text=title, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(12, 2))
            var = tk.StringVar(value=default)
            tk.Label(card, textvariable=var, bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=16, pady=(0, 12))
            self.metrics[title] = var
        # The viewport owns its size; images must never change layout requests.
        self.preview_viewport = tk.Frame(content, bg="#070d17", width=640, height=300)
        self.preview_viewport.grid(row=1, column=0, sticky="nsew")
        self.preview_viewport.grid_propagate(False)
        self.preview = tk.Label(self.preview_viewport,
                                text="CAMERA PREVIEW\n\nStart a session to connect your camera",
                                bg="#070d17", fg=MUTED, font=("Segoe UI", 14),
                                borderwidth=0, highlightthickness=0, padx=0, pady=0)
        self.preview.place(relx=0.5, rely=0.5, anchor="center", relwidth=1, relheight=1)
        self.status = tk.StringVar(value="Ready to start")
        self.details = tk.StringVar(value="Camera stays off until you start a session.")
        tk.Label(content, textvariable=self.status, bg=BG, fg=ACCENT,
                 font=("Segoe UI", 13, "bold")).grid(row=2, column=0, sticky="w", pady=(12, 4))
        tk.Label(content, textvariable=self.details, bg=BG, fg=MUTED,
                 font=("Segoe UI", 10), wraplength=730, justify="left").grid(row=3, column=0, sticky="w")
        self.progress = ttk.Progressbar(content, maximum=100)
        self.quality_text = tk.StringVar(value="Quality guidance will appear after the session starts.")
        tk.Label(content, textvariable=self.quality_text, bg=BG, fg="#e7bf72",
                 font=("Segoe UI", 10), wraplength=650, justify="left").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.progress.grid(row=5, column=0, sticky="ew", pady=10)
        controls = ttk.Frame(content)
        controls.grid(row=6, column=0, sticky="ew")
        self.start_button = ttk.Button(controls, text="▶  Start session", command=self.start)
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = ttk.Button(controls, text="■  End & save", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=(0, 8))
        self.calibrate_button = ttk.Button(controls, text="Recalibrate", command=self.recalibrate_event.set,
                                           state="disabled")
        self.calibrate_button.pack(side="left")

    def build_review(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=18)
        self.report_choice = ttk.Combobox(top, state="readonly", width=58)
        self.report_choice.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.report_choice.bind("<<ComboboxSelected>>", self.load_report)
        self.delete_button = ttk.Button(top, text="Delete session", command=self.delete_selected_session,
                                        state="disabled")
        self.delete_button.pack(side="left", padx=(0, 8))
        ttk.Button(top, text="Refresh reports", command=self.refresh_reports).pack(side="left")
        ttk.Button(top, text="Export PDF", command=self.export_pdf).pack(side="left", padx=(8, 0))
        self.summary = tk.StringVar(value="No sessions yet. End a session to save its report.")
        ttk.Label(parent, textvariable=self.summary, wraplength=1100).pack(anchor="w", pady=(0, 12))
        columns = ("start", "duration", "reasons", "review")
        self.table = ttk.Treeview(parent, columns=columns, show="headings", height=8)
        for key, label, width in (("start", "Start (s)", 100), ("duration", "Duration (s)", 110),
                                  ("reasons", "Review reasons", 440), ("review", "Review status", 170)):
            self.table.heading(key, text=label)
            self.table.column(key, width=width)
        self.table.pack(fill="x")
        self.table.bind("<<TreeviewSelect>>", self.show_evidence)
        editor = ttk.Frame(parent)
        editor.pack(fill="x", pady=(12, 0))
        ttk.Label(editor, text="Review status").pack(side="left", padx=(0, 10))
        self.review_status = tk.StringVar(value="Unreviewed")
        self.review_choice = ttk.Combobox(editor, textvariable=self.review_status,
                                          values=REVIEW_STATUSES, state="disabled", width=20)
        self.review_choice.pack(side="left")
        self.save_review_button = ttk.Button(editor, text="Save review", command=self.save_review,
                                             state="disabled")
        self.save_review_button.pack(side="left", padx=10)
        self.clip_button = ttk.Button(editor, text="Play clip", command=self.play_clip, state="disabled")
        self.clip_button.pack(side="left", padx=(0, 10))
        self.review_feedback = tk.StringVar(value="Select an event to review.")
        ttk.Label(editor, textvariable=self.review_feedback).pack(side="left")
        ttk.Label(parent, text="Notes — save before selecting another event or session.").pack(
            anchor="w", pady=(8, 4))
        self.review_notes = tk.Text(parent, height=3, wrap="word", bg=PANEL, fg=TEXT,
                                    insertbackground=TEXT, font=("Segoe UI", 10), state="disabled")
        self.review_notes.pack(fill="x")
        evidence_viewport = tk.Frame(parent, bg="#070d17", height=160)
        evidence_viewport.pack(fill="both", expand=True, pady=14)
        self.evidence = tk.Label(evidence_viewport, text="Select an event to view its captured frame.",
                                 bg="#070d17", fg=MUTED)
        self.evidence.place(relwidth=1, relheight=1)
        self.report_events = []
        self.loaded_report = None

    def reset_review_editor(self):
        self.review_status.set("Unreviewed")
        self.review_choice.configure(state="disabled")
        self.review_notes.configure(state="normal")
        self.review_notes.delete("1.0", "end")
        self.review_notes.configure(state="disabled")
        self.save_review_button.configure(state="disabled")
        self.clip_button.configure(state="disabled")
        self.review_feedback.set("Select an event to review.")

    def save_review(self):
        selection = self.table.selection()
        if not selection or self.loaded_report is None:
            return
        index = int(selection[0])
        try:
            review = save_event_review(ROOT, self.loaded_report, index,
                                       self.review_status.get(), self.review_notes.get("1.0", "end-1c"))
        except (OSError, ValueError, TypeError, AttributeError) as error:
            messagebox.showerror("Review not saved", str(error))
            return
        self.report_events[index]["review"] = review
        self.table.set(selection[0], "review", review["status"])
        self.review_feedback.set("Review saved.")

    def play_clip(self):
        selection = self.table.selection()
        if not selection:
            return
        name = self.report_events[int(selection[0])].get('clip')
        if not name:
            return
        try:
            path = Path(name)
            path = (path if path.is_absolute() else ROOT / path).resolve()
            path.relative_to((ROOT / 'outputs/clips').resolve())
            from examwatch.clip_player import open_clip
            open_clip(self.root, path)
        except (OSError, ValueError, ImportError) as error:
            messagebox.showerror('Clip unavailable', str(error))

    def export_pdf(self):
        if self.loaded_report is None:
            messagebox.showinfo('Select session', 'Select a saved session first. Save any review edits before exporting.')
            return
        directory = ROOT / 'outputs/pdf'
        directory.mkdir(parents=True, exist_ok=True)
        target = filedialog.asksaveasfilename(title='Export session PDF', initialdir=str(directory),
                     initialfile=self.loaded_report.stem + '.pdf', defaultextension='.pdf',
                     filetypes=[('PDF report', '*.pdf')])
        if not target:
            return
        try:
            from examwatch.pdf_report import export_pdf
            export_pdf(ROOT, self.loaded_report, target)
            messagebox.showinfo('PDF saved', f'Session report exported to:\n{target}')
        except (OSError, ValueError, ImportError, KeyError, TypeError) as error:
            messagebox.showerror('PDF export failed', str(error))

    def emit(self, message):
        # Only the latest preview is needed; worker threads never touch Tk.
        try:
            self.messages.put_nowait(message)
        except queue.Full:
            try:
                self.messages.get_nowait()
            except queue.Empty:
                pass
            self.messages.put_nowait(message)

    def choose_video(self):
        path = filedialog.askopenfilename(title="Choose exam video", filetypes=(
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.webm *.wmv"), ("All files", "*.*")))
        if path:
            self.video_path.set(path)
            self.video_label.set(Path(path).name)
            self.source_type.set("Video file")

    def start(self):
        if self.worker is not None and self.worker.is_alive():
            return
        try:
            settings = {"camera": int(self.camera.get()), "minimum_duration": float(self.minimum.get()),
                        "session_name": self.session_name.get().strip(),
                        "source_type": self.source_type.get(), "video_path": self.video_path.get(),
                        "save_clips": self.save_clips.get(),
                        "absence_duration": float(self.absence.get()), "confidence": float(self.confidence.get()),
                        "allowed_objects": [key for key, value in self.allowed.items() if value.get()]}
            if not (0 <= settings["camera"] <= 10 and .1 <= settings["minimum_duration"] <= 30
                    and .1 <= settings["absence_duration"] <= 60 and .05 <= settings["confidence"] <= 1):
                raise ValueError()
        except ValueError:
            messagebox.showerror("Invalid settings", "Enter valid numbers within the settings ranges.")
            return
        if settings["source_type"] == "Video file" and not Path(settings["video_path"]).is_file():
            messagebox.showerror("Select video", "Choose an existing video file before starting.")
            return
        self.stop_event.clear()
        self.recalibrate_event.clear()
        self.progress["value"] = 0
        for key, value in (("SESSION", "00:00"), ("FACES", "—"), ("EPISODES", "0")):
            self.metrics[key].set(value)
        self.status.set("Starting session...")
        self.quality_text.set("Checking lighting, sharpness, and face position...")
        self.set_running(True)
        def work():
            try:
                run_monitoring(settings, self.emit, self.stop_event, self.recalibrate_event)
            except Exception as error:
                self.emit({"error": str(error)})
            finally:
                self.emit({"done": True})
        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()

    def set_running(self, running):
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.calibrate_button.configure(state="normal" if running else "disabled")
        for control in self.inputs:
            control.configure(state="disabled" if running else "normal")
        self.source_choice.configure(state="disabled" if running else "readonly")

    def stop(self):
        self.stop_event.set()
        self.status.set("Ending session and saving reports...")
        self.stop_button.configure(state="disabled")

    def poll(self):
        try:
            while True:
                msg = self.messages.get_nowait()
                if "frame" in msg:
                    import cv2
                    frame = msg["frame"]
                    width = max(1, self.preview_viewport.winfo_width())
                    height = max(1, self.preview_viewport.winfo_height())
                    scale = min(width / frame.shape[1], height / frame.shape[0])
                    frame = cv2.resize(frame, (max(1, int(frame.shape[1] * scale)),
                                               max(1, int(frame.shape[0] * scale))))
                    ok, data = cv2.imencode(".png", frame)
                    if ok:
                        self.photo = tk.PhotoImage(data=data.tobytes())
                        self.preview.configure(image=self.photo, text="")
                    seconds = int(msg["elapsed"])
                    self.metrics["SESSION"].set(f"{seconds // 60:02d}:{seconds % 60:02d}")
                    self.metrics["FACES"].set(str(msg["faces"]))
                    self.metrics["EPISODES"].set(str(msg["events"]))
                    self.status.set(msg["status"])
                    self.progress["value"] = msg["calibration"] * 100
                    reasons = ", ".join(msg["reasons"]) or "None"
                    self.details.set(f"Head: {msg['head']}  •  Pitch: {msg['pitch']}  •  Gaze: {msg['gaze']}\nReasons: {reasons}")
                    quality = msg.get('quality', {})
                    warnings = quality.get('warnings', [])
                    self.quality_text.set(('Quality: ' + '; '.join(warnings)) if warnings else
                                          ('Quality OK | ' + f"Processing: {msg.get('processing_fps', 0):.1f} FPS"))
                if "message" in msg:
                    self.status.set(msg["message"])
                if "error" in msg:
                    self.status.set("Session could not continue")
                    if not self.closing:
                        messagebox.showerror("Monitoring error", msg["error"] +
                            "\n\nUse your configured Python environment, install requirements.txt, and check the model files and camera.")
                if msg.get("done"):
                    self.set_running(False)
                    if self.stop_event.is_set():
                        self.status.set("Session ended. Reports saved.")
                    self.refresh_reports()
                    self.evaluation_panel.refresh()
        except queue.Empty:
            pass
        if self.closing and (self.worker is None or not self.worker.is_alive()):
            self.root.destroy()
            return
        self.root.after(80, self.poll)

    def refresh_reports(self):
        directory = ROOT / "outputs/session_reports"
        self.reports = sorted(directory.glob("*.json"), reverse=True)
        labels = []
        for path in self.reports:
            identifier = path.stem.replace("session_report_", "")
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
                name = report.get("session_name") if isinstance(report, dict) else None
            except (OSError, ValueError):
                name = None
            labels.append(f"{name}  |  {identifier}" if name else identifier)
        self.report_choice["values"] = labels
        self.delete_button.configure(state="normal" if self.reports else "disabled")
        if self.reports:
            self.report_choice.current(0)
            self.load_report()
        else:
            self.report_choice.set("")
            self.loaded_report = None
            self.reset_review_editor()
            self.report_events = []
            self.table.delete(*self.table.get_children())
            self.summary.set("No sessions yet. End a session to save its report.")
            self.evidence.configure(image="", text="No session selected.")

    def delete_selected_session(self):
        index = self.report_choice.current()
        if index < 0 or index >= len(self.reports):
            return
        name = self.report_choice.get()
        if not messagebox.askyesno(
                "Delete session", f"Delete this session?\n\n{name}\n\n"
                "Reports, unshared images/clips, and default PDF/evaluation files will be deleted.",
                icon="warning", default="no"):
            return
        try:
            delete_session(ROOT, self.reports[index])
        except (OSError, ValueError, TypeError, AttributeError) as error:
            messagebox.showerror("Delete failed", str(error))
        self.refresh_reports()

    def load_report(self, _event=None):
        self.loaded_report = None
        self.reset_review_editor()
        index = self.report_choice.current()
        if index < 0:
            return
        try:
            data = json.loads(self.reports[index].read_text(encoding="utf-8"))
            self.report_events = data.get("events", [])
            self.loaded_report = self.reports[index]
            self.summary.set(f"{data.get('session_name') or data.get('session_id', 'Session')}   |   "
                             f"Source: {data.get('source_name', 'Camera')}   |   "
                             f"Duration: {data.get('duration_seconds', 0):.1f}s   |   "
                             f"Confirmed episodes: {data.get('confirmed_episodes', len(self.report_events))}")
            self.table.delete(*self.table.get_children())
            self.evidence.configure(image="", text="Select an event to view its captured frame.")
            for i, event in enumerate(self.report_events):
                start = event.get("start_seconds", 0)
                end = event.get("end_seconds", event.get("last_signal_seconds", start))
                self.table.insert("", "end", iid=str(i), values=(f"{start:.1f}", f"{max(0, end-start):.1f}",
                                                                               ", ".join(event.get("reasons", [])),
                                                                               event.get("review", {}).get("status", "Unreviewed")))
        except (OSError, ValueError, TypeError) as error:
            self.summary.set(f"Could not read this report: {error}")

    def show_evidence(self, _event=None):
        selection = self.table.selection()
        if not selection:
            self.reset_review_editor()
            return
        event = self.report_events[int(selection[0])]
        review = event.get("review", {})
        self.review_status.set(review.get("status", "Unreviewed"))
        self.review_choice.configure(state="readonly")
        self.review_notes.configure(state="normal")
        self.review_notes.delete("1.0", "end")
        self.review_notes.insert("1.0", review.get("notes", ""))
        self.save_review_button.configure(state="normal")
        self.review_feedback.set("Edit status and notes, then save.")
        self.clip_button.configure(state='normal' if event.get('clip') else 'disabled')
        path = event.get("screenshot")
        if not path:
            self.evidence.configure(image="", text="No screenshot was saved for this event.")
            return
        candidate = Path(path)
        candidate = candidate if candidate.is_absolute() else ROOT / candidate
        try:
            candidate = candidate.resolve()
            candidate.relative_to((ROOT / "outputs/screenshots").resolve())
            from PIL import Image, ImageTk
            with Image.open(candidate) as image:
                image.thumbnail((950, 300))
                self.evidence_photo = ImageTk.PhotoImage(image.copy())
            self.evidence.configure(image=self.evidence_photo, text="")
        except (OSError, ValueError, ImportError):
            self.evidence.configure(image="", text="Screenshot unavailable. Check the file and Pillow installation.")

    def close(self):
        self.closing = True
        self.exit_button.configure(state="disabled", text="Closing...")
        if self.worker is not None and self.worker.is_alive():
            self.stop()
        else:
            self.root.destroy()
