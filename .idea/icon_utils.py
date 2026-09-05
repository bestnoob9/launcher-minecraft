import os
import sys
import tkinter as tk

def gan_icon_app(window):
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        duong_dan_ico = os.path.join(base_dir, "assets", "icon.ico")
        duong_dan_png = os.path.join(base_dir, "assets", "icon.png")

        if sys.platform == "win32" and os.path.exists(duong_dan_ico):
            window.iconbitmap(duong_dan_ico)
        elif os.path.exists(duong_dan_png):
            icon_img = tk.PhotoImage(file=duong_dan_png)
            window.iconphoto(True, icon_img)
            window._icon_img_ref = icon_img
    except Exception as e:
        print(f"ko thể gắn icon: {e}")
