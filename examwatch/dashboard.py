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
from examwatch.home_page import HomePage
from examwatch.new_session_page import NewSessionPage
from examwatch.exam_rules import SUPPORTED_OBJECTS, validate_forbidden, clip_window
from examwatch.screen_calibration import CameraControls
from examwatch.monitoring_page import MonitoringPage
from examwatch.session_library import SessionLibrary
from examwatch.session_review import SessionReviewPage
from examwatch.settings_page import SettingsPage
from examwatch.preferences import load_preferences, save_preferences

BG = "#0d0a0b"
PANEL = "#454955"
TEXT = "#f3eff5"
MUTED = "#72b01d"
ACCENT = "#3f7d20"


class Dashboard:
    def __init__(self, root):
        self.root = root
        self.root_path = ROOT
        self.preferences, self.settings_warning = load_preferences(ROOT)
        self.pending_defaults = False
        self.worker = None
        self.messages = queue.Queue(maxsize=2)
        self.stop_event = threading.Event()
        self.recalibrate_event = threading.Event()
        self.closing = False
        self.reports = []
        self.photo = None
        self.forbidden_objects = list(self.preferences['forbidden_objects'])
        self.camera_controls = None
        self.phase = 'idle'
        self.report_saved = False
        self.calibration_geometry = None
        root.title("ExamWatch")
        root.geometry("1260x850")
        root.minsize(1000, 740)
        self.fullscreen = self.preferences['fullscreen']
        root.attributes("-fullscreen", self.fullscreen)
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
        # Retain state bindings without mapping the old chrome behind the new pages.
        self.exit_button = ttk.Button(header, text="Exit app", command=self.close)
        self.exit_button.pack(side="right", anchor="n", padx=(8, 0))
        self.fullscreen_button = ttk.Button(header, text="Exit fullscreen (Esc)",
                                             command=lambda: self.set_fullscreen(not self.fullscreen))
        if not self.fullscreen:
            self.fullscreen_button.configure(text='Fullscreen (F11)')
        self.fullscreen_button.pack(side="right", anchor="n")
        ttk.Button(header, text="← Overview", command=self.show_home).pack(side="right", padx=8)
        tk.Label(header, text="◉  ExamWatch", bg=BG, fg=TEXT,
                 font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(header, text="AI EXAM MONITORING", bg=BG,
                 fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))
        tabs = ttk.Notebook(root)
        self.tabs = tabs
        live, review = ttk.Frame(tabs), ttk.Frame(tabs)
        self.workspace_pages = {'live': live, 'review': review}
        tabs.add(live, text="Live monitoring")
        tabs.add(review, text="Session reports")
        self.build_live(live)
        self.build_review(review)
        evaluation_stub = ttk.Frame(tabs)
        tabs.add(evaluation_stub, text="Accuracy evaluation")
        self.workspace_pages['evaluation'] = evaluation_stub
        self.evaluation_panel = EvaluationPanel(root, ROOT, self.open_workspace, self.close)
        self.home = HomePage(root, ROOT, self.open_workspace, self.open_home_session,
                             self.close)
        self.new_session = NewSessionPage(root, self)
        self.source_choice = self.new_session.source_choice
        self.monitor_page = MonitoringPage(root, self)
        self.library_page = SessionLibrary(root, self)
        self.review_page = SessionReviewPage(root, self)
        self.settings_page = SettingsPage(root, self)
        self.gaze_target = tk.Canvas(root, width=64, height=64, bg='#101716',
                                     highlightthickness=0, borderwidth=0)
        self.gaze_target.create_oval(8, 8, 56, 56, outline='#b8e89c', width=2)
        self.gaze_target.create_oval(27, 27, 37, 37, fill='#b8e89c', outline='')
        self.gaze_target.create_line(32, 15, 32, 23, fill='#b8e89c')
        self.gaze_target.create_line(32, 41, 32, 49, fill='#b8e89c')
        self.gaze_target.create_line(15, 32, 23, 32, fill='#b8e89c')
        self.gaze_target.create_line(41, 32, 49, 32, fill='#b8e89c')
        self.refresh_reports()
        self.show_home()
        tabs.bind('<<NotebookTabChanged>>', self.on_workspace_tab_changed)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(80, self.poll)

    def set_fullscreen(self, enabled):
        self.fullscreen = bool(enabled)
        self.root.attributes("-fullscreen", self.fullscreen)
        self.fullscreen_button.configure(
            text="Exit fullscreen (Esc)" if self.fullscreen else "Fullscreen (F11)")

    def show_home(self):
        if hasattr(self, 'review_page') and self.review_page.winfo_manager() and not self.review_page.can_leave():
            return
        if hasattr(self, 'review_page'):
            self.review_page.hide()
        for name in ('settings_page', 'evaluation_panel'):
            if hasattr(self, name):
                getattr(self, name).place_forget()
        if hasattr(self, 'home'):
            if hasattr(self, 'gaze_target'):
                self.gaze_target.place_forget()
            if self.camera_controls is not None:
                self.camera_controls.shown_target = -1
            if hasattr(self, 'new_session'):
                self.new_session.place_forget()
            if hasattr(self, 'monitor_page'):
                self.monitor_page.place_forget()
            if hasattr(self, 'library_page'):
                self.library_page.place_forget()
            self.home.refresh()
            self.home.place(x=0, y=0, relwidth=1, relheight=1)
            self.home.lift()

    def open_workspace(self, page):
        if hasattr(self, 'review_page') and self.review_page.winfo_manager() and not self.review_page.can_leave():
            return False
        if hasattr(self, 'review_page'):
            self.review_page.hide()
        self.settings_page.place_forget()
        self.evaluation_panel.place_forget()
        if hasattr(self, 'library_page'):
            self.library_page.place_forget()
        if hasattr(self, 'monitor_page'):
            self.monitor_page.place_forget()
        if hasattr(self, 'gaze_target'):
            self.gaze_target.place_forget()
        if self.camera_controls is not None:
            self.camera_controls.shown_target = -1
        if page == 'home':
            self.show_home()
            return
        self.home.place_forget()
        if page == 'live' and not (self.worker is not None and self.worker.is_alive()):
            if self.pending_defaults:
                self.apply_session_defaults()
            self.new_session.refresh()
            self.new_session.place(x=0, y=0, relwidth=1, relheight=1)
            self.new_session.lift()
            return
        self.new_session.place_forget()
        if page == 'settings':
            self.settings_page.place(x=0, y=0, relwidth=1, relheight=1)
            self.settings_page.lift()
            return
        if page == 'event_review':
            self.tabs.select(self.workspace_pages['review'])
            self.refresh_reports()
            self.review_page.place(x=0, y=0, relwidth=1, relheight=1)
            self.review_page.lift()
            return True
        if page == 'monitor':
            page = 'live'
        self.tabs.select(self.workspace_pages[page])
        if page == 'live':
            self.show_monitor()
        elif page == 'review':
            self.refresh_reports()
            self.library_page.place(x=0, y=0, relwidth=1, relheight=1)
            self.library_page.lift()
        elif page == 'evaluation':
            self.evaluation_panel.refresh()
            self.evaluation_panel.place(x=0, y=0, relwidth=1, relheight=1)
            self.evaluation_panel.lift()

    def show_monitor(self):
        self.monitor_page.update_phase(self.phase)
        self.update_phase_controls()
        self.monitor_page.place(x=0, y=0, relwidth=1, relheight=1)
        self.monitor_page.lift()

    def on_workspace_tab_changed(self, _event=None):
        if any(getattr(self, name).winfo_manager() for name in (
                'home', 'new_session', 'monitor_page', 'library_page', 'review_page', 'settings_page', 'evaluation_panel')):
            return
        if (self.tabs.select() == str(self.workspace_pages['live']) and
                not self.home.winfo_manager() and not self.new_session.winfo_manager()):
            self.show_monitor()
        elif self.tabs.select() == str(self.workspace_pages['evaluation']):
            self.open_workspace('evaluation')
        elif self.tabs.select() == str(self.workspace_pages['review']):
            self.open_workspace('review')

    def save_app_preferences(self, values):
        self.preferences = save_preferences(ROOT, values)
        self.pending_defaults = True
        if self.worker is not None and self.worker.is_alive():
            return 'Saved locally. The active session is unchanged; defaults and display changes apply when you next open New session.'
        self.set_fullscreen(self.preferences['fullscreen'])
        return 'Settings saved locally. Session defaults apply when you next open New session.'

    def apply_session_defaults(self):
        defaults = self.preferences
        for key, variable in (('camera', self.camera), ('minimum_duration', self.minimum),
                              ('absence_duration', self.absence), ('confidence', self.confidence),
                              ('clip_duration_seconds', self.clip_duration), ('save_clips', self.save_clips)):
            variable.set(defaults[key])
        self.forbidden_objects = list(defaults['forbidden_objects'])
        self.set_fullscreen(defaults['fullscreen'])
        self.pending_defaults = False

    def open_home_session(self, path):
        if self.open_workspace('event_review') is False:
            return
        if self.select_report(path, refresh=False) and self.report_events:
            self.table.selection_set('0')
            self.show_evidence()

    def select_report(self, path, refresh=True):
        if refresh:
            self.refresh_reports()
        if path not in self.reports:
            return False
        self.report_choice.current(self.reports.index(path))
        self.load_report()
        return self.loaded_report == path

    def start_configured_session(self):
        if self.start():
            self.open_workspace('monitor')

    def build_live(self, parent):
        # Preparation lives on New session; keep this page focused on the camera.
        self.camera = tk.StringVar(value=str(self.preferences['camera']))
        self.minimum = tk.StringVar(value=str(self.preferences['minimum_duration']))
        self.absence = tk.StringVar(value=str(self.preferences['absence_duration']))
        self.confidence = tk.StringVar(value=str(self.preferences['confidence']))
        self.session_name = tk.StringVar()
        self.source_type = tk.StringVar(value="Camera")
        self.video_path = tk.StringVar()
        self.video_label = tk.StringVar(value="No video selected")
        self.save_clips = tk.BooleanVar(value=self.preferences['save_clips'])
        self.clip_duration = tk.StringVar(value=str(self.preferences['clip_duration_seconds']))
        self.inputs = []

    def begin_calibration(self):
        if self.camera_controls is not None and self.phase in ('preview', 'ready'):
            self.calibration_geometry = (self.root.winfo_width(), self.root.winfo_height(),
                                         self.root.winfo_rootx(), self.root.winfo_rooty())
            self.camera_controls.calibrate.set()
            self.phase = 'loading_calibration'
            self.status.set('Preparing gaze calibration...')
            self.update_phase_controls()
        elif self.phase == 'video_analysis':
            self.recalibrate_event.set()

    def begin_exam(self):
        if self.phase == 'ready' and self.camera_controls is not None:
            current_geometry = (self.root.winfo_width(), self.root.winfo_height(),
                                self.root.winfo_rootx(), self.root.winfo_rooty())
            if self.calibration_geometry is not None and current_geometry != self.calibration_geometry:
                messagebox.showinfo('Recalibration needed', 'The window moved or resized. Calibrate gaze again before starting the exam.')
                return
            self.camera_controls.begin_exam.set()
            self.phase = 'loading_exam'
            self.status.set('Starting exam monitoring...')
            self.gaze_target.place_forget()
            self.update_phase_controls()

    def update_phase_controls(self):
        self.start_button.configure(text='Analyze video' if self.source_type.get() == 'Video file' else 'Open camera')
        self.calibrate_button.configure(state='normal' if self.phase in ('preview', 'ready', 'video_analysis') else 'disabled')
        self.exam_button.configure(state='normal' if self.phase == 'ready' else 'disabled')
        self.stop_button.configure(text='End & save' if self.phase in ('exam', 'video_analysis') else 'Close camera')
        self.monitor_page.update_phase(self.phase)

    def update_gaze_target(self, message):
        point = message.get('target')
        visible = (not self.home.winfo_manager() and not self.new_session.winfo_manager()
                   and bool(self.monitor_page.winfo_manager())
                   and self.tabs.select() == str(self.workspace_pages['live']))
        if point and visible and self.phase in ('preview', 'calibrating'):
            self.gaze_target.place(relx=point[0], rely=point[1], anchor='center')
            tk.Misc.lift(self.gaze_target)
            if self.phase == 'calibrating' and self.camera_controls is not None:
                self.camera_controls.shown_target = message['target_index']
        else:
            self.gaze_target.place_forget()

    def build_review(self, parent):
        # Hidden selector retained for report identity and library actions.
        # The visible editor is owned by SessionReviewPage.
        self.report_choice = ttk.Combobox(parent, state="readonly")
        self.report_choice.bind("<<ComboboxSelected>>", self.load_report)
        self.delete_button = ttk.Button(parent, command=self.delete_selected_session, state="disabled")
        self.report_events = []
        self.loaded_report = None

    def reset_review_editor(self):
        self.review_page.reset()
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
        self.review_page.mark_saved()
        return True

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
            self.review_page.viewer.play(path)
        except (OSError, ValueError, ImportError) as error:
            messagebox.showerror('Clip unavailable', str(error))

    def export_pdf(self):
        if self.review_page.has_unsaved():
            messagebox.showinfo('Save review first', 'Save your review edits before exporting the PDF.')
            return
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
            if hasattr(self, 'new_session'):
                self.new_session.update_source()

    def start(self):
        if self.worker is not None and self.worker.is_alive():
            return
        try:
            settings = {"camera": int(self.camera.get()), "minimum_duration": float(self.minimum.get()),
                        "session_name": self.session_name.get().strip(),
                        "source_type": self.source_type.get(), "video_path": self.video_path.get(),
                        "save_clips": self.save_clips.get(),
                        "clip_duration_seconds": float(self.clip_duration.get()) if self.save_clips.get() else 10.0,
                        "forbidden_objects": validate_forbidden(self.forbidden_objects),
                        "absence_duration": float(self.absence.get()), "confidence": float(self.confidence.get()),
                        "allowed_objects": sorted(set(SUPPORTED_OBJECTS) - set(self.forbidden_objects))}
            clip_window(settings['clip_duration_seconds'])
            if not (0 <= settings["camera"] <= 10 and .1 <= settings["minimum_duration"] <= 30
                    and .1 <= settings["absence_duration"] <= 60 and .05 <= settings["confidence"] <= 1):
                raise ValueError()
        except ValueError as error:
            messagebox.showerror("Invalid settings", str(error) or "Enter valid numbers within the settings ranges.")
            return
        if settings["source_type"] == "Video file" and not Path(settings["video_path"]).is_file():
            messagebox.showerror("Select video", "Choose an existing video file before starting.")
            return
        self.stop_event.clear()
        self.camera_controls = CameraControls() if settings['source_type'] == 'Camera' else None
        self.phase = 'opening_camera' if self.camera_controls else 'video_analysis'
        self.report_saved = False
        self.recalibrate_event.clear()
        self.progress["value"] = 0
        for key, value in (("SESSION", "00:00"), ("FACES", "—"), ("EPISODES", "0")):
            self.metrics[key].set(value)
        self.status.set("Starting session...")
        self.quality_text.set("Checking lighting, sharpness, and face position...")
        self.set_running(True)
        def work():
            try:
                run_monitoring(settings, self.emit, self.stop_event, self.recalibrate_event, self.camera_controls)
            except Exception as error:
                self.emit({"error": str(error)})
            finally:
                self.emit({"done": True})
        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()
        return True

    def set_running(self, running):
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.calibrate_button.configure(state="disabled")
        self.exam_button.configure(state='disabled')
        for control in self.inputs:
            control.configure(state="disabled" if running else "normal")
        self.source_choice.configure(state="disabled" if running else "readonly")
        self.home.start_button.configure(text='Return to monitoring' if running else '+  New session')
        self.new_session.start_button.configure(state='disabled' if running else 'normal')
        if running:
            self.update_phase_controls()
        else:
            self.monitor_page.update_phase('idle')

    def stop(self):
        self.stop_event.set()
        self.status.set("Ending exam and saving reports..." if self.phase in ('exam', 'video_analysis') else 'Closing camera...')
        self.gaze_target.place_forget()
        self.calibrate_button.configure(state='disabled')
        self.exam_button.configure(state='disabled')
        self.stop_button.configure(state="disabled")

    def poll(self):
        try:
            while True:
                msg = self.messages.get_nowait()
                if 'phase' in msg:
                    self.phase = msg['phase']
                    self.update_phase_controls()
                if 'report_path' in msg:
                    self.report_saved = True
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
                    self.details.set(msg.get('instruction') or f"Head: {msg['head']}  •  Pitch: {msg['pitch']}  •  Gaze: {msg['gaze']}\nReasons: {reasons}")
                    quality = msg.get('quality', {})
                    warnings = quality.get('warnings', [])
                    self.quality_text.set(('Quality: ' + '; '.join(warnings)) if warnings else
                                          'No alerts or evidence recording before Start exam.' if self.phase in ('preview', 'calibrating', 'ready') else
                                          ('Quality OK | ' + f"Processing: {msg.get('processing_fps', 0):.1f} FPS"))
                    self.update_gaze_target(msg)
                if "message" in msg:
                    self.status.set(msg["message"])
                if "error" in msg:
                    self.status.set("Session could not continue")
                    if not self.closing:
                        messagebox.showerror("Monitoring error", msg["error"] +
                            "\n\nUse your configured Python environment, install requirements.txt, and check the model files and camera.")
                if msg.get("done"):
                    self.phase = 'idle'
                    self.gaze_target.place_forget()
                    self.set_running(False)
                    if self.stop_event.is_set():
                        self.status.set('Session ended. Reports saved.' if self.report_saved else 'Camera closed. No exam was recorded.')
                    self.refresh_reports()
                    self.evaluation_panel.refresh()
        except queue.Empty:
            pass
        if self.closing and (self.worker is None or not self.worker.is_alive()):
            self.root.destroy()
            return
        self.root.after(80, self.poll)

    def refresh_reports(self):
        current_report = self.loaded_report
        directory = ROOT / "outputs/session_reports"
        if hasattr(self, 'home'):
            self.home.refresh()
        if hasattr(self, 'library_page'):
            self.library_page.refresh()
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
            if current_report in self.reports:
                self.report_choice.current(self.reports.index(current_report))
                if self.review_page.has_unsaved():
                    return
            else:
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
            self.review_page.refresh_report({})

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
        previous_report = self.loaded_report
        if not self.review_page.can_leave():
            if previous_report in self.reports:
                self.report_choice.current(self.reports.index(previous_report))
            return
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
            self.review_page.refresh_report(data)
        except (OSError, ValueError, TypeError) as error:
            self.loaded_report = None
            self.summary.set(f"Could not read this report: {error}")

    def show_evidence(self, _event=None):
        selection = self.table.selection()
        if not selection:
            self.reset_review_editor()
            return
        index = int(selection[0])
        if self.review_page.current_event == index:
            return
        if not self.review_page.can_leave():
            if self.review_page.current_event is not None:
                self.table.selection_set(str(self.review_page.current_event))
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
        self.review_page.show_event(index)

    def close(self):
        if not self.review_page.can_leave():
            return
        self.review_page.hide()
        self.closing = True
        self.exit_button.configure(state="disabled", text="Closing...")
        self.home.exit_button.configure(state="disabled", text="Closing...")
        self.new_session.exit_button.configure(state='disabled', text='Closing...')
        self.monitor_page.exit_button.configure(state='disabled', text='Closing...')
        self.library_page.exit_button.configure(state='disabled', text='Closing...')
        self.review_page.exit_button.configure(state='disabled', text='Closing...')
        self.settings_page.exit_button.configure(state='disabled', text='Closing...')
        self.evaluation_panel.exit_button.configure(state='disabled', text='Closing...')
        if self.worker is not None and self.worker.is_alive():
            self.stop()
        else:
            self.root.destroy()
