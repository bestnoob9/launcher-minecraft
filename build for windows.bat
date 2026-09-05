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

if not exist "assets\icon.ico" (
    echo [LOI] Khong tim thay assets\icon.ico
    echo.
    echo Hay tao thu muc "assets" cung cap voi main.py va dat file
    echo icon.ico ^(va icon.png neu co^) vao do truoc khi build.
    pause
    exit /b 1
)

echo [OK] Tim thay assets\icon.ico
echo.

if not exist "run_app.py" (
    echo [LOI] Khong tim thay run_app.py
    echo.
    echo File nay la diem khoi dong chinh de build ^(thay cho main.py^).
    echo Hay dam bao run_app.py nam cung thu muc voi main.py truoc khi build.
    pause
    exit /b 1
)

echo [OK] Tim thay run_app.py
echo.

"%THONNY_PY%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Chua co PyInstaller, dang cai vao Thonny...
    "%THONNY_PY%" -m pip install pyinstaller
)

if not exist "version_info.txt" (
    echo [CANH BAO] Khong tim thay version_info.txt - build van tiep tuc
    echo nhung file .exe se thieu thong tin Company/Product/Description.
    echo.
)

echo Bat dau build...
echo.

"%THONNY_PY%" -m PyInstaller --onefile --windowed --noupx --name "MinecraftLauncher" --icon "assets\icon.ico" --version-file "version_info.txt" --add-data "components;components" --add-data "assets;assets" --hidden-import "minecraft_launcher_lib" --hidden-import "minecraft_launcher_lib.utils" --hidden-import "minecraft_launcher_lib.install" --hidden-import "minecraft_launcher_lib.command" --hidden-import "minecraft_launcher_lib.fabric" --hidden-import "minecraft_launcher_lib.quilt" --hidden-import "minecraft_launcher_lib.forge" --hidden-import "minecraft_launcher_lib.neoforge" --hidden-import "tkinter" --hidden-import "tkinter.ttk" --hidden-import "tkinter.messagebox" --hidden-import "tkinter.filedialog" --collect-all "minecraft_launcher_lib" --hidden-import "psutil" --collect-all "psutil" --hidden-import "PIL" --collect-all "PIL" run_app.py

echo.
if exist "dist\MinecraftLauncher.exe" (
    echo [OK] Build thanh cong! File: dist\MinecraftLauncher.exe
    echo.
    echo ============================================
    echo   VE CANH BAO "Windows da bao ve PC cua ban"
    echo   ^(SmartScreen - ung dung khong ro nguon goc^)
    echo ============================================
    echo Day la canh bao cua Windows SmartScreen, KHONG phai loi cua file
    echo build. No xuat hien vi file .exe CHUA duoc ky so ^(code sign^) bang
    echo 1 chung chi ^(certificate^) duoc Windows tin tuong.
    echo.
    echo Cach duy nhat de HET HAN canh bao nay tren may nguoi khac:
    echo   1. Mua 1 chung chi ky so ^(code signing certificate^) tu 1 nha
    echo      cung cap duoc tin tuong ^(vd: SSL.com, Certum, DigiCert, Sectigo^).
    echo      - Chung chi loai EV ^(Extended Validation^) se HET canh bao
    echo        NGAY LAP TUC tren moi may.
    echo      - Chung chi loai OV thuong ^(re hon^) van con canh bao luc dau,
    echo        se tu het dan khi SmartScreen "tich luy uy tin" theo so luot
    echo        tai/chay ^(co the mat vai tuan - vai thang^).
    echo   2. Sau khi co file .pfx, ky file .exe bang signtool ^(co san trong
    echo      Windows SDK^), vi du:
    echo        signtool sign /f "duong_dan_toi_cert.pfx" /p "MAT_KHAU_PFX" ^^^^
    echo          /fd sha256 /tr http://timestamp.digicert.com /td sha256 ^^^^
    echo          "dist\MinecraftLauncher.exe"
    echo.
    echo Chung chi tu ky ^(self-signed^) KHONG loai bo duoc canh bao nay tren
    echo may nguoi khac - no chi bo canh bao tren chinh may da cai chung chi
    echo do vao "Trusted Root". Day la co che bao mat cua Windows, khong the
    echo "vuot qua" bang cach chinh sua file build.
    echo ============================================
    echo.
    explorer dist
) else (
    echo [THAT BAI] Xem log o tren de debug.
)

pause