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

    def test_home_routes_to_workspace_without_starting_camera(self):
        self.assertEqual(self.dashboard.home.winfo_manager(), 'place')
        with patch.object(app, 'run_monitoring') as runner:
            self.dashboard.home.start_button.invoke()
        runner.assert_not_called()
        self.assertEqual(self.dashboard.tabs.select(), str(self.dashboard.workspace_pages['live']))
        self.assertEqual(self.dashboard.home.winfo_manager(), '')
        self.dashboard.show_home()
        self.assertEqual(self.dashboard.home.winfo_manager(), 'place')

    def test_home_uses_real_counts_and_opens_selected_report(self):
        directory = app.ROOT / 'outputs/session_reports'
        directory.mkdir(parents=True)
        report = directory / 'session_report_home.json'
        report.write_text(json.dumps({'session_name': 'Home test', 'events': [
            {'start_seconds': 1, 'review': {'status': 'Needs follow-up'}},
            {'start_seconds': 3, 'review': {'status': 'False alarm'}}]}), encoding='utf-8')
        (directory / 'invalid.json').write_text('not json')
        self.dashboard.home.refresh()
        self.assertEqual(self.dashboard.home.metrics['sessions'].get(), '1')
        self.assertEqual(self.dashboard.home.metrics['pending'].get(), '1')
        self.assertEqual(self.dashboard.home.metrics['events'].get(), '2')
        self.dashboard.home.table.selection_set('0')
        self.dashboard.home.open_button.invoke()
        self.assertEqual(self.dashboard.loaded_report, report)

    def test_home_actions_fit_smaller_window(self):
        self.dashboard.set_fullscreen(False)
        self.root.deiconify()
        self.root.geometry('1000x740')
        self.root.update()
        home = self.dashboard.home
        for widget in (home.start_button, home.open_button, home.exit_button):
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                 self.root.winfo_rooty() + self.root.winfo_height())
            self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                 self.root.winfo_rootx() + self.root.winfo_width())

    def test_home_exit_is_in_sidebar_and_closes_app(self):
        home = self.dashboard.home
        self.assertFalse(hasattr(home, 'fullscreen_button'))
        self.assertEqual(home.exit_button.master.master.grid_info()['column'], 0)
        with patch.object(self.root, 'destroy') as destroy:
            home.exit_button.invoke()
        destroy.assert_called_once()

    def test_new_session_rules_add_remove_and_custom_clip_settings(self):
        self.dashboard.open_workspace('live')
        page = self.dashboard.new_session
        self.assertEqual(page.winfo_manager(), 'place')
        page.object_choice.set('Laptop')
        page.add_object()
        page.add_object()
        self.assertEqual(self.dashboard.forbidden_objects.count('LAPTOP'), 1)
        page.objects.selection_set(self.dashboard.forbidden_objects.index('BOOK'))
        page.remove_object()
        self.assertNotIn('BOOK', self.dashboard.forbidden_objects)
        self.dashboard.clip_duration.set('15')
        with patch.object(app, 'run_monitoring') as runner:
            self.dashboard.start_configured_session()
            self.dashboard.worker.join(timeout=3)
        settings = runner.call_args[0][0]
        self.assertEqual(settings['clip_duration_seconds'], 15)
        self.assertIn('LAPTOP', settings['forbidden_objects'])
        self.assertNotIn('BOOK', settings['forbidden_objects'])
        self.assertEqual(page.winfo_manager(), '')

    def test_new_session_rejects_invalid_duration_and_empty_rules_are_allowed(self):
        self.dashboard.forbidden_objects.clear()
        self.dashboard.clip_duration.set('16')
        with patch.object(app.messagebox, 'showerror') as error:
            self.dashboard.start()
        error.assert_called_once()
        self.assertIsNone(self.dashboard.worker)
        self.dashboard.save_clips.set(False)
        self.dashboard.new_session.update_clip_controls()
        self.assertEqual(str(self.dashboard.new_session.duration['state']), 'disabled')
        with patch.object(app, 'run_monitoring') as runner:
            self.dashboard.start()
            self.dashboard.worker.join(timeout=3)
        self.assertEqual(runner.call_args[0][0]['forbidden_objects'], [])

    def test_new_session_footer_fits_smaller_window(self):
        self.dashboard.set_fullscreen(False)
        self.dashboard.open_workspace('live')
        self.root.geometry('1000x740')
        self.root.deiconify()
        self.root.update()
        button = self.dashboard.new_session.start_button
        self.assertTrue(button.winfo_ismapped())
        self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                             self.root.winfo_rooty() + self.root.winfo_height())
        self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                             self.root.winfo_rootx() + self.root.winfo_width())
        canvas = self.dashboard.new_session.form_canvas
        before = canvas.yview()[0]
        canvas.event_generate('<MouseWheel>', delta=-360)
        self.root.update()
        self.assertGreater(canvas.yview()[0], before)

    def test_camera_phase_buttons_gate_exam_and_show_center_target(self):
        from examwatch.screen_calibration import CameraControls
        self.dashboard.camera_controls = CameraControls()
        self.dashboard.open_workspace('monitor')
        self.dashboard.phase = 'preview'
        self.dashboard.update_phase_controls()
        self.assertEqual(str(self.dashboard.exam_button['state']), 'disabled')
        self.dashboard.begin_exam()
        self.assertFalse(self.dashboard.camera_controls.begin_exam.is_set())
        self.dashboard.update_gaze_target({'target': (.5, .5), 'target_index': -1})
        self.assertEqual(float(self.dashboard.gaze_target.place_info()['relx']), .5)
        self.assertEqual(float(self.dashboard.gaze_target.place_info()['rely']), .5)
        self.dashboard.begin_calibration()
        self.assertTrue(self.dashboard.camera_controls.calibrate.is_set())
        self.dashboard.phase = 'ready'
        self.dashboard.update_phase_controls()
        self.assertEqual(str(self.dashboard.exam_button['state']), 'normal')
        self.dashboard.begin_exam()
        self.assertTrue(self.dashboard.camera_controls.begin_exam.is_set())
        self.assertEqual(self.dashboard.gaze_target.winfo_manager(), '')

    def test_monitor_page_matches_new_pages_and_navigation_preserves_phase(self):
        from examwatch.home_page import BG
        self.dashboard.open_workspace('monitor')
        page = self.dashboard.monitor_page
        self.assertEqual(page.winfo_manager(), 'place')
        self.assertEqual(page['bg'], BG)
        self.dashboard.phase = 'preview'
        self.dashboard.update_phase_controls()
        self.assertEqual(page.phase_badge['text'], 'PREVIEW ONLY')
        self.assertEqual(str(self.dashboard.exam_button['state']), 'disabled')
        self.dashboard.show_home()
        self.assertEqual(page.winfo_manager(), '')
        self.dashboard.open_workspace('monitor')
        self.assertEqual(page.phase_badge['text'], 'PREVIEW ONLY')
        self.assertIn('live', page.nav_buttons)

    def test_monitor_controls_fit_at_minimum_window_size(self):
        self.dashboard.open_workspace('monitor')
        self.dashboard.set_fullscreen(False)
        self.root.geometry('1000x740')
        self.root.deiconify()
        self.root.update()
        for button in (self.dashboard.start_button, self.dashboard.calibrate_button,
                       self.dashboard.exam_button, self.dashboard.stop_button,
                       self.dashboard.monitor_page.exit_button):
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 self.root.winfo_rooty() + self.root.winfo_height())
            self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                 self.root.winfo_rootx() + self.root.winfo_width())

    def test_library_filters_and_actions_use_selected_path_with_duplicate_names(self):
        directory = app.ROOT / 'outputs/session_reports'
        directory.mkdir(parents=True)
        first = directory / 'session_report_1.json'
        second = directory / 'session_report_2.json'
        first.write_text(json.dumps({'session_name': 'Same name', 'duration_seconds': 65,
            'events': [{'start_seconds': 1, 'review': {'status': 'Reviewed'}}]}), encoding='utf-8')
        second.write_text(json.dumps({'session_name': 'Same name', 'duration_seconds': 90,
            'events': [{'start_seconds': 2}]}), encoding='utf-8')
        self.dashboard.open_workspace('review')
        library = self.dashboard.library_page
        self.assertEqual(library.winfo_manager(), 'place')
        self.assertEqual(library.metrics['total'].get(), '2')
        library.query.set('SAME NAME')
        library.status_filter.set('Needs review')
        self.assertEqual(len(library.visible_rows), 1)
        self.assertEqual(library.visible_rows[0]['path'], second)
        library.table.selection_set('0')
        library.selection_changed()
        with patch.object(self.dashboard, 'export_pdf') as exporter:
            library.export_selected()
        exporter.assert_called_once()
        self.assertEqual(self.dashboard.loaded_report, second)
        library.open_selected()
        self.assertEqual(library.winfo_manager(), '')
        self.assertEqual(self.dashboard.loaded_report, second)
        self.dashboard.open_workspace('review')
        self.assertEqual(library.status_filter.get(), 'Needs review')
        library.table.selection_set('0')
        with patch.object(app.messagebox, 'askyesno', return_value=True):
            library.delete_selected()
        self.assertFalse(second.exists())
        self.assertTrue(first.exists())
        self.assertEqual(len(library.visible_rows), 0)
        self.assertEqual(str(library.open_button['state']), 'disabled')

    def test_library_empty_filter_and_minimum_layout(self):
        self.dashboard.open_workspace('review')
        self.dashboard.set_fullscreen(False)
        self.root.geometry('1000x740')
        self.root.deiconify()
        self.root.update()
        library = self.dashboard.library_page
        library.query.set('no match')
        self.assertEqual(library.visible_rows, [])
        self.assertEqual(str(library.delete_button['state']), 'disabled')
        for button in (library.open_button, library.pdf_button, library.delete_button, library.exit_button):
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 self.root.winfo_rooty() + self.root.winfo_height())
            self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                 self.root.winfo_rootx() + self.root.winfo_width())

    def review_fixture(self, events):
        directory = app.ROOT / 'outputs/session_reports'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / 'session_report_review_page.json'
        path.write_text(json.dumps({'session_name': 'Review page test', 'duration_seconds': 30,
            'events': events}), encoding='utf-8')
        self.dashboard.open_home_session(path)
        return path

    def test_review_page_unsaved_changes_can_cancel_event_and_page_navigation(self):
        self.review_fixture([{'start_seconds': 1, 'end_seconds': 3, 'reasons': ['BOOK']},
                             {'start_seconds': 6, 'end_seconds': 8, 'reasons': ['CELL PHONE']}])
        page = self.dashboard.review_page
        self.assertEqual(page.current_event, 0)
        self.dashboard.review_notes.insert('1.0', 'ملاحظة لم تحفظ بعد')
        with patch('examwatch.session_review.messagebox.askyesno', return_value=False):
            page.move(1)
            self.assertEqual(page.current_event, 0)
            self.assertEqual(self.dashboard.table.selection(), ('0',))
            self.dashboard.open_workspace('review')
        self.assertEqual(page.winfo_manager(), 'place')
        self.assertEqual(self.dashboard.review_notes.get('1.0', 'end-1c'), 'ملاحظة لم تحفظ بعد')
        self.dashboard.review_status.set('False alarm')
        self.dashboard.save_review()
        self.assertFalse(page.has_unsaved())
        self.assertIn('1 of 2', page.completion.get())
        page.move(1)
        self.assertEqual(page.current_event, 1)
        self.assertEqual(self.dashboard.review_notes.get('1.0', 'end-1c'), '')
        self.dashboard.open_workspace('review')
        self.assertEqual(page.winfo_manager(), '')
        self.assertEqual(self.dashboard.library_page.metrics['pending'].get(), '1')

    def test_review_page_empty_session_and_fixed_actions(self):
        self.review_fixture([])
        page = self.dashboard.review_page
        self.assertEqual(str(self.dashboard.save_review_button['state']), 'disabled')
        self.assertEqual(str(self.dashboard.clip_button['state']), 'disabled')
        self.dashboard.set_fullscreen(False)
        self.root.geometry('1000x740')
        self.root.deiconify()
        self.root.update()
        for widget in (self.dashboard.save_review_button, page.pdf_button, page.exit_button,
                       page.previous_button, page.next_button):
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                 self.root.winfo_rooty() + self.root.winfo_height())
            self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                 self.root.winfo_rootx() + self.root.winfo_width())

    def test_review_clip_plays_inline_and_releases_decoder_on_navigation(self):
        import importlib.util
        if not importlib.util.find_spec('cv2') or not importlib.util.find_spec('numpy'):
            self.skipTest('Video dependencies unavailable')
        import cv2
        import numpy as np
        directory = app.ROOT / 'outputs/clips'
        directory.mkdir(parents=True)
        path = directory / 'test.avi'
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 10, (160, 90))
        if not writer.isOpened():
            self.skipTest('MJPG codec unavailable')
        try:
            for value in range(12):
                writer.write(np.full((90, 160, 3), value * 10, dtype=np.uint8))
        finally:
            writer.release()
        self.review_fixture([{'start_seconds': 1, 'end_seconds': 3, 'reasons': ['BOOK'], 'clip': str(path)}])
        self.dashboard.play_clip()
        viewer = self.dashboard.review_page.viewer
        self.assertIsNotNone(viewer.cap)
        self.assertIsNotNone(viewer.timer)
        viewer.toggle()
        self.assertFalse(viewer.playing)
        viewer.restart()
        self.assertTrue(viewer.playing)
        self.dashboard.open_workspace('review')
        self.assertIsNone(viewer.cap)
        self.assertIsNone(viewer.timer)

    def test_settings_save_is_persistent_and_does_not_change_active_session(self):
        from unittest.mock import Mock
        from examwatch.preferences import load_preferences
        worker = Mock()
        worker.is_alive.return_value = True
        self.dashboard.worker = worker
        page = self.dashboard.settings_page
        page.variables['fullscreen'].set(False)
        page.variables['camera'].set('2')
        page.variables['minimum_duration'].set('2.5')
        page.variables['clip_duration_seconds'].set('15')
        for name, variable in page.object_variables.items():
            variable.set(name == 'LAPTOP')
        page.save()
        self.assertEqual(self.dashboard.minimum.get(), '1.0')
        self.assertTrue(self.dashboard.fullscreen)
        loaded, _ = load_preferences(app.ROOT)
        self.assertEqual(loaded['clip_duration_seconds'], 15)
        self.assertEqual(loaded['forbidden_objects'], ['LAPTOP'])
        self.assertTrue(self.dashboard.pending_defaults)
        worker.is_alive.return_value = False
        self.dashboard.open_workspace('live')
        self.assertEqual(self.dashboard.minimum.get(), '2.5')
        self.assertEqual(self.dashboard.camera.get(), '2')
        self.assertFalse(self.dashboard.fullscreen)
        self.assertEqual(self.dashboard.forbidden_objects, ['LAPTOP'])
        self.assertFalse(self.dashboard.pending_defaults)
        self.dashboard.worker = None

    def test_settings_invalid_values_and_restore_are_not_silently_saved(self):
        page = self.dashboard.settings_page
        page.variables['confidence'].set('bad')
        with patch('examwatch.settings_page.messagebox.showerror') as error:
            page.save()
        error.assert_called_once()
        self.assertFalse((app.ROOT / 'outputs/preferences.json').exists())
        page.restore()
        self.assertEqual(float(page.variables['confidence'].get()), .4)
        self.assertFalse((app.ROOT / 'outputs/preferences.json').exists())

    def test_remaining_pages_share_dark_layout_and_fit_minimum_window(self):
        from examwatch.home_page import BG
        self.dashboard.set_fullscreen(False)
        self.root.geometry('1000x740')
        self.root.deiconify()
        for page_name, widgets in (
                ('evaluation', (self.dashboard.evaluation_panel.export_button,
                                self.dashboard.evaluation_panel.import_button,
                                self.dashboard.evaluation_panel.exit_button)),
                ('settings', (self.dashboard.settings_page.save_button,
                              self.dashboard.settings_page.reset_button,
                              self.dashboard.settings_page.exit_button))):
            self.dashboard.open_workspace(page_name)
            self.root.update()
            page = self.dashboard.evaluation_panel if page_name == 'evaluation' else self.dashboard.settings_page
            self.assertEqual(page['bg'], BG)
            self.assertEqual(page.winfo_manager(), 'place')
            for widget in widgets:
                self.assertTrue(widget.winfo_ismapped())
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                     self.root.winfo_rooty() + self.root.winfo_height())
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                     self.root.winfo_rootx() + self.root.winfo_width())
        self.dashboard.show_home()
        self.assertEqual(self.dashboard.settings_page.winfo_manager(), '')

    def test_invalid_saved_evaluation_does_not_leave_broken_metric_cards(self):
        reports = app.ROOT / 'outputs/session_reports'
        reports.mkdir(parents=True)
        (reports / 'session_report_invalid.json').write_text(json.dumps({
            'session_id': 'test', 'duration_seconds': 10, 'events': []}), encoding='utf-8')
        results = app.ROOT / 'outputs/evaluations'
        results.mkdir(parents=True)
        (results / 'session_report_invalid_evaluation.json').write_text(json.dumps({
            'session_id': 'test', 'precision': 'broken'}), encoding='utf-8')
        panel = self.dashboard.evaluation_panel
        panel.refresh()
        self.assertIsNone(panel.metric_result)
        panel.draw_metrics()
        texts = [panel.chart.itemcget(item, 'text') for item in panel.chart.find_all()
                 if panel.chart.type(item) == 'text']
        self.assertEqual(texts.count('N/A'), 3)

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
        from examwatch.evaluation import REASONS
        self.assertEqual(len(panel.table.get_children()), len(REASONS))
        self.assertIn('Matched: 0', panel.result_text.get())
        self.assertTrue((app.ROOT / 'outputs/evaluations/session_report_test_evaluation.json').is_file())

    def test_preview_does_not_grow_or_push_controls_out_of_window(self):
        self.dashboard.open_workspace('monitor')
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
