"""UI smoke tests; require Tk support but never open the camera."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tkinter as tk

from examwatch import dashboard as app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch = patch.object(app, "ROOT", Path(self.temp.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.dashboard = app.Dashboard(self.root)
        self.addCleanup(self.cancel_callbacks)

    def cancel_callbacks(self):
        for callback in self.root.tk.call('after', 'info'):
            self.root.after_cancel(callback)

    def test_empty_report_list_and_settings_lock(self):
        self.assertEqual(self.dashboard.reports, [])
        self.dashboard.set_running(True)
        self.assertEqual(str(self.dashboard.start_button['state']), 'disabled')
        self.dashboard.set_running(False)
        self.assertEqual(str(self.dashboard.start_button['state']), 'normal')

    def test_starts_fullscreen_and_button_can_toggle(self):
        self.assertTrue(self.dashboard.fullscreen)
        self.assertIn('Exit fullscreen', self.dashboard.fullscreen_button['text'])
        self.dashboard.fullscreen_button.invoke()
        self.assertFalse(self.dashboard.fullscreen)
        self.assertIn('Fullscreen', self.dashboard.fullscreen_button['text'])
        self.dashboard.fullscreen_button.invoke()
        self.assertTrue(self.dashboard.fullscreen)

    def test_exit_button_closes_idle_application(self):
        with patch.object(self.root, 'destroy') as destroy:
            self.dashboard.exit_button.invoke()
        destroy.assert_called_once()
        self.assertTrue(self.dashboard.closing)

    def test_exit_button_requests_cleanup_for_running_session(self):
        from unittest.mock import Mock
        self.dashboard.worker = Mock()
        self.dashboard.worker.is_alive.return_value = True
        with patch.object(self.root, 'destroy') as destroy:
            self.dashboard.exit_button.invoke()
        destroy.assert_not_called()
        self.assertTrue(self.dashboard.stop_event.is_set())
        self.assertTrue(self.dashboard.closing)

    def test_report_loads_timeline(self):
        directory = app.ROOT / 'outputs/session_reports'
        directory.mkdir(parents=True)
        (directory / 'session_report_test.json').write_text(json.dumps({
            'session_id': 'test', 'duration_seconds': 12,
            'confirmed_episodes': 1,
            'events': [{'start_seconds': 2, 'end_seconds': 5,
                        'reasons': ['CELL PHONE'], 'screenshot': None}],
        }), encoding='utf-8')
        self.dashboard.refresh_reports()
        self.assertEqual(len(self.dashboard.table.get_children()), 1)
        self.assertIn('CELL PHONE', str(self.dashboard.table.item('0', 'values')))

    def test_named_report_is_visible_in_list_and_summary(self):
        directory = app.ROOT / 'outputs/session_reports'
        directory.mkdir(parents=True)
        (directory / 'session_report_named.json').write_text(json.dumps({
            'session_id': 'named', 'session_name': 'امتحان الذكاء الاصطناعي',
            'duration_seconds': 10, 'events': [],
        }), encoding='utf-8')
        self.dashboard.refresh_reports()
        self.assertIn('امتحان الذكاء الاصطناعي', self.dashboard.report_choice.get())
        self.assertIn('امتحان الذكاء الاصطناعي', self.dashboard.summary.get())

    def test_event_review_can_be_saved_and_reopened_without_screenshot(self):
        directory = app.ROOT / 'outputs/session_reports'
        directory.mkdir(parents=True)
        report = directory / 'session_report_review.json'
        report.write_text(json.dumps({'events': [{'start_seconds': 1, 'screenshot': None}]}),
                          encoding='utf-8')
        self.dashboard.refresh_reports()
        self.assertEqual(self.dashboard.table.set('0', 'review'), 'Unreviewed')
        self.dashboard.table.selection_set('0')
        self.dashboard.show_evidence()
        self.dashboard.review_status.set('Needs follow-up')
        self.dashboard.review_notes.insert('1.0', 'يحتاج مراجعة من المشرف')
        self.dashboard.save_review()
        self.dashboard.refresh_reports()
        self.dashboard.table.selection_set('0')
        self.dashboard.show_evidence()
        self.assertEqual(self.dashboard.review_status.get(), 'Needs follow-up')
        self.assertEqual(self.dashboard.review_notes.get('1.0', 'end-1c'), 'يحتاج مراجعة من المشرف')
        self.assertEqual(self.dashboard.table.set('0', 'review'), 'Needs follow-up')

    def test_session_name_is_trimmed_and_passed_to_worker(self):
        self.dashboard.session_name.set('  امتحان الشبكات  ')
        with patch.object(app, 'run_monitoring') as runner:
            self.dashboard.start()
            self.dashboard.worker.join(timeout=3)
        self.assertEqual(runner.call_args[0][0]['session_name'], 'امتحان الشبكات')

    def test_delete_cancel_and_confirm_clear_last_session(self):
        directory = app.ROOT / 'outputs/session_reports'
        directory.mkdir(parents=True)
        report = directory / 'session_report_delete.json'
        report.write_text(json.dumps({'session_name': 'Test', 'events': []}), encoding='utf-8')
        self.dashboard.refresh_reports()
        with patch.object(app.messagebox, 'askyesno', return_value=False):
            self.dashboard.delete_selected_session()
        self.assertTrue(report.exists())
        with patch.object(app.messagebox, 'askyesno', return_value=True):
            self.dashboard.delete_selected_session()
        self.assertFalse(report.exists())
        self.assertEqual(self.dashboard.report_choice.get(), '')
        self.assertEqual(str(self.dashboard.delete_button['state']), 'disabled')

    def test_missing_dependencies_surface_error_and_restore_controls(self):
        with patch.object(app, 'run_monitoring', side_effect=ImportError('Missing mediapipe')):
            self.dashboard.start()
            self.dashboard.worker.join(timeout=3)
        self.assertFalse(self.dashboard.worker.is_alive())
        with patch.object(app.messagebox, 'showerror') as error:
            self.dashboard.poll()
        error.assert_called_once()
        self.assertIn('Missing mediapipe', error.call_args[0][1])
        self.assertEqual(str(self.dashboard.start_button['state']), 'normal')

    def test_bad_settings_do_not_start_camera(self):
        self.dashboard.confidence.set('nan')
        with patch.object(app.messagebox, 'showerror') as error:
            self.dashboard.start()
        error.assert_called_once()
        self.assertIsNone(self.dashboard.worker)

    def test_video_source_requires_file_and_passes_selected_path(self):
        self.dashboard.source_type.set('Video file')
        with patch.object(app.messagebox, 'showerror') as error:
            self.dashboard.start()
        error.assert_called_once()
        self.assertIsNone(self.dashboard.worker)
        video = app.ROOT / 'test.mp4'
        video.touch()
        self.dashboard.video_path.set(str(video))
        with patch.object(app, 'run_monitoring') as runner:
            self.dashboard.start()
            self.dashboard.worker.join(timeout=3)
        self.assertEqual(runner.call_args[0][0]['source_type'], 'Video file')
        self.assertEqual(runner.call_args[0][0]['video_path'], str(video))

    def test_evaluation_template_is_independent_and_metrics_render(self):
        directory = app.ROOT / 'outputs/session_reports'
        directory.mkdir(parents=True)
        report = {'session_id': 'test', 'duration_seconds': 10, 'events': []}
        (directory / 'session_report_test.json').write_text(json.dumps(report), encoding='utf-8')
        panel = self.dashboard.evaluation_panel
        panel.refresh()
        target = app.ROOT / 'labels.json'
        with patch('examwatch.evaluation_panel.filedialog.asksaveasfilename', return_value=str(target)), patch(
                'examwatch.evaluation_panel.messagebox.showinfo'):
            panel.export_template()
        labels = json.loads(target.read_text(encoding='utf-8'))
        self.assertFalse(labels['complete'])
        self.assertEqual(labels['events'], [])
        labels.update(complete=True)
        target.write_text(json.dumps(labels), encoding='utf-8')
        with patch('examwatch.evaluation_panel.filedialog.askopenfilename', return_value=str(target)):
            panel.run()
        self.assertEqual(len(panel.table.get_children()), 8)
        self.assertIn('Matched: 0', panel.result_text.get())
        self.assertTrue((app.ROOT / 'outputs/evaluations/session_report_test_evaluation.json').is_file())

    def test_preview_does_not_grow_or_push_controls_out_of_window(self):
        self.dashboard.set_fullscreen(False)
        self.root.deiconify()
        self.root.update()
        for geometry in ('1260x850', '1000x740'):
            self.root.geometry(geometry)
            self.root.update()
            viewport = self.dashboard.preview_viewport
            original = (viewport.winfo_width(), viewport.winfo_height())
            for _ in range(40):
                # Simulate repeated rendered frames without camera dependencies.
                self.dashboard.photo = tk.PhotoImage(
                    width=viewport.winfo_width(), height=viewport.winfo_height())
                self.dashboard.preview.configure(image=self.dashboard.photo, text='')
                self.root.update_idletasks()
                self.assertEqual((viewport.winfo_width(), viewport.winfo_height()), original)
            button = self.dashboard.stop_button
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 self.root.winfo_rooty() + self.root.winfo_height())


if __name__ == '__main__':
    unittest.main()
