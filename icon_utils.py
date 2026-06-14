import os
import sys
import tkinter as tk


def gan_icon_app(window):
    """
    Gan icon cho cua so (titlebar + taskbar).

    Cach dung:
      - Tao thu muc "assets" nam cung cap voi main.py.
      - Bo file icon vao do:
          assets/icon.ico   (uu tien dung tren Windows - taskbar/titlebar)
          assets/icon.png   (du phong, dung cho moi he dieu hanh)
      - Goi gan_icon_app(window) cho moi cua so (Tk hoac Toplevel) can hien icon.
    """
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        duong_dan_ico = os.path.join(base_dir, "assets", "icon.ico")
        duong_dan_png = os.path.join(base_dir, "assets", "icon.png")

        if sys.platform == "win32" and os.path.exists(duong_dan_ico):
            window.iconbitmap(duong_dan_ico)
        elif os.path.exists(duong_dan_png):
            icon_img = tk.PhotoImage(file=duong_dan_png)
            window.iconphoto(True, icon_img)
            # Giu tham chieu de Python khong don rac (garbage-collect) anh icon
            window._icon_img_ref = icon_img
    except Exception as e:
        print(f"[Icon] Khong the gan icon: {e}")