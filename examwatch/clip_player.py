"""Local evidence player; closes its decoder and Tk timer on exit."""
import tkinter as tk
from tkinter import ttk


def open_clip(parent, path):
    import cv2
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise ValueError('Cannot open this evidence clip.')
    window = tk.Toplevel(parent)
    window.title('Event evidence - ' + path.name)
    window.geometry('720x500')
    viewport = tk.Frame(window, bg='#070d17')
    viewport.pack(fill='both', expand=True)
    preview = tk.Label(viewport, bg='#070d17')
    preview.place(relwidth=1, relheight=1)
    fps = cap.get(cv2.CAP_PROP_FPS)
    interval = max(15, int(1000 / fps)) if 0 < fps < 240 else 100
    state = {'playing': True, 'timer': None, 'photo': None, 'closed': False}
    controls = ttk.Frame(window)
    controls.pack(fill='x')

    def close():
        state['closed'] = True
        if state['timer'] is not None:
            window.after_cancel(state['timer'])
        cap.release()
        window.destroy()

    def tick():
        state['timer'] = None
        if state['closed']:
            return
        if state['playing']:
            ok, frame = cap.read()
            if ok:
                h, w = frame.shape[:2]
                scale = min(max(1, viewport.winfo_width()) / w, max(1, viewport.winfo_height()) / h)
                frame = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))))
                ok, data = cv2.imencode('.png', frame)
                if ok:
                    state['photo'] = tk.PhotoImage(data=data.tobytes())
                    preview.configure(image=state['photo'])
            else:
                state['playing'] = False
        state['timer'] = window.after(interval, tick)

    def restart():
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        state['playing'] = True

    ttk.Button(controls, text='Play / pause', command=lambda: state.update(playing=not state['playing'])).pack(side='left')
    ttk.Button(controls, text='Restart', command=restart).pack(side='left')
    ttk.Button(controls, text='Close', command=close).pack(side='right')
    window.protocol('WM_DELETE_WINDOW', close)
    parent.bind('<Destroy>', lambda event: close() if event.widget == parent and not state['closed'] else None, add='+')
    window.after_idle(tick)
