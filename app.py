"""Launch the ExamWatch desktop application."""

import tkinter as tk

from examwatch.dashboard import Dashboard


if __name__ == "__main__":
    Dashboard(tk.Tk()).root.mainloop()
