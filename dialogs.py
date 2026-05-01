# dialogs.py - Cross-platform file dialogs using tkinter
import os
import tkinter as tk
from tkinter import filedialog

_root = None
_app_dir = os.path.dirname(os.path.abspath(__file__))

def _get_root():
    global _root
    if _root is None:
        _root = tk.Tk()
        _root.withdraw()
    return _root

def get_save_scene_file(default_name="scene.bfxr"):
    """Show save dialog for .bfxr scene files. Returns path or None."""
    try:
        root = _get_root()
        path = filedialog.asksaveasfilename(
            defaultextension=".bfxr",
            filetypes=[("BFXR Scene", "*.bfxr"), ("All Files", "*.*")],
            initialdir=_app_dir,
            initialfile=default_name,
            title="Save BFXR Scene"
        )
        return path if path else None
    except Exception:
        return None

def get_load_scene_file():
    """Show open dialog for .bfxr scene files. Returns path or None."""
    try:
        root = _get_root()
        path = filedialog.askopenfilename(
            defaultextension=".bfxr",
            filetypes=[("BFXR Scene", "*.bfxr"), ("All Files", "*.*")],
            initialdir=_app_dir,
            title="Load BFXR Scene"
        )
        return path if path else None
    except Exception:
        return None

def get_save_wav_file(default_name="sound.wav"):
    """Show save dialog for WAV files. Returns path or None."""
    try:
        root = _get_root()
        path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("WAV Audio", "*.wav"), ("All Files", "*.*")],
            initialdir=_app_dir,
            initialfile=default_name,
            title="Export WAV File"
        )
        return path if path else None
    except Exception:
        return None

def get_load_any_file(title="Open File", filetypes=None):
    """Show open dialog for any file. Returns path or None."""
    if filetypes is None:
        filetypes = [("All Files", "*.*")]
    try:
        root = _get_root()
        path = filedialog.askopenfilename(
            filetypes=filetypes,
            initialdir=_app_dir,
            title=title
        )
        return path if path else None
    except Exception:
        return None

def get_text_input(title, prompt, default_text=""):
    """Show dialog to edit text. Returns edited text or None."""
    try:
        root = _get_root()
        dialog = tk.Toplevel(root)
        dialog.title(title)
        dialog.transient(root)
        dialog.grab_set()
        dialog.geometry("450x180")

        tk.Label(dialog, text=prompt, anchor="w").pack(fill="x", padx=10, pady=(10, 5))

        entry = tk.Entry(dialog, width=60)
        entry.insert(0, default_text)
        entry.pack(padx=10, pady=5, fill="x")
        entry.select_range(0, tk.END)
        entry.focus_set()

        result = [None]

        def on_ok():
            result[0] = entry.get()
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="OK", width=10, command=on_ok, default=tk.ACTIVE).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", width=10, command=dialog.destroy).pack(side="left", padx=5)

        dialog.wait_window()
        return result[0]
    except Exception:
        return None


def destroy_root():
    """Clean up tkinter root window."""
    global _root
    if _root is not None:
        _root.destroy()
        _root = None

def copy_to_clipboard(text):
    """Copy text to clipboard."""
    try:
        root = _get_root()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    except Exception:
        pass

def paste_from_clipboard():
    """Paste text from clipboard. Returns text or None."""
    try:
        root = _get_root()
        return root.clipboard_get()
    except Exception:
        return None
