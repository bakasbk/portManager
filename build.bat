@echo off
cd /d %~dp0
call env\Scripts\activate.bat
pip install PySide6 pyinstaller
pyinstaller --onefile --windowed --noconfirm --name PortManager --collect-all PySide6 port_manager.py
if exist dist\PortManager.exe (
    echo ============================================
    echo  BUILD OK: dist\PortManager.exe created
    echo ============================================
) else (
    echo ============================================
    echo  BUILD FAILED, see errors above
    echo ============================================
)
pause
