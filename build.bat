@echo off
chcp 65001 >nul
	echo ============================================
	echo   BUILD MINECRAFT LAUNCHER - PyInstaller
	echo ============================================
	echo.

set THONNY_PY=C:\Users\%USERNAME%\AppData\Local\Programs\Thonny\python.exe

if not exist "%THONNY_PY%" (
    echo [LOI] Khong tim thay Python Thonny tai: %THONNY_PY%
    echo.
    echo Hay mo Thonny, vao Tools ^> Open system shell, gõ lenh:
    echo     where python
    echo Sau do copy duong dan va sua bien THONNY_PY trong file bat nay.
    pause
    exit /b 1
)

echo [OK] Python Thonny: %THONNY_PY%
echo.

"%THONNY_PY%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Chua co PyInstaller, dang cai vao Thonny...
    "%THONNY_PY%" -m pip install pyinstaller
)

echo Bat dau build...
echo.

"%THONNY_PY%" -m PyInstaller --onefile --windowed --name "MinecraftLauncher" --icon "icon.ico" --add-data "components;components" --hidden-import "minecraft_launcher_lib" --hidden-import "minecraft_launcher_lib.utils" --hidden-import "minecraft_launcher_lib.install" --hidden-import "minecraft_launcher_lib.command" --hidden-import "minecraft_launcher_lib.fabric" --hidden-import "minecraft_launcher_lib.quilt" --hidden-import "minecraft_launcher_lib.forge" --hidden-import "minecraft_launcher_lib.neoforge" --hidden-import "tkinter" --hidden-import "tkinter.ttk" --hidden-import "tkinter.messagebox" --hidden-import "tkinter.filedialog" --collect-all "minecraft_launcher_lib" --hidden-import "psutil" --collect-all "psutil" main.py

echo.
if exist "dist\MinecraftLauncher.exe" (
    echo [OK] Build thanh cong! File: dist\MinecraftLauncher.exe
    explorer dist
) else (
    echo [THAT BAI] Xem log o tren de debug.
)

pause