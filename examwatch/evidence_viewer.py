"""Resizable evidence viewer with local inline video playback."""
import math
import tkinter as tk

from examwatch.home_page import SECONDARY


class EvidenceViewer(tk.Frame):
    def __init__(self, parent, on_state):
        super().__init__(parent, bg='#080f0c', width=320, height=180)
        self.label = tk.Label(self, bg='#080f0c', fg=SECONDARY,
                              text='Select an event to inspect its evidence.', font=('Segoe UI', 10), wraplength=280)
        self.label.place(relwidth=1, relheight=1)
        self.on_state = on_state
        self.cap = None
        self.timer = None
        self.playing = False
        self.ended = False
        self.image = None
        self.photo = None
        self.bind('<Configure>', lambda _event: self.draw())

    def stop(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.playing = False
        self.on_state(False, False)

    def clear(self, text='Select an event to inspect its evidence.'):
        self.stop()
        self.image, self.photo = None, None
        self.label.configure(image='', text=text)

    def load_image(self, path):
        from PIL import Image
        self.stop()
        with Image.open(path) as image:
            self.image = image.convert('RGB').copy()
        self.draw()

    def draw(self):
        if self.image is None:
            return
        from PIL import ImageTk
        image = self.image.copy()
        image.thumbnail((max(1, self.winfo_width() - 2), max(1, self.winfo_height() - 2)))
        self.photo = ImageTk.PhotoImage(image)
        self.label.configure(image=self.photo, text='')

    def play(self, path):
        import cv2
        self.stop()
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            self.stop()
            raise ValueError('This evidence clip is missing or cannot be decoded.')
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.interval = max(15, int(1000 / fps)) if math.isfinite(fps) and 0 < fps < 240 else 100
        self.ended, self.playing = False, True
        self.tick()

    def tick(self):
        self.timer = None
        if self.cap is None or not self.playing:
            return
        try:
            import cv2
            from PIL import Image
            ok, frame = self.cap.read()
            if not ok:
                self.playing, self.ended = False, True
                self.on_state(True, False)
                return
            self.image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            self.draw()
            self.on_state(True, True)
            self.timer = self.after(self.interval, self.tick)
        except Exception:
            self.clear('Evidence playback failed. Try the screenshot instead.')

    def toggle(self):
        if self.cap is None:
            return
        if self.playing:
            if self.timer is not None:
                self.after_cancel(self.timer)
                self.timer = None
            self.playing = False
            self.on_state(True, False)
        else:
            if self.ended:
                self.restart()
            else:
                self.playing = True
                self.tick()

    def restart(self):
        if self.cap is None:
            return
        import cv2
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.ended, self.playing = False, True
        self.tick()

    def destroy(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        super().destroy()
