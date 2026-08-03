@echo off
cd /d "%~dp0"
call env\Scripts\activate.bat
python port_manager.py
