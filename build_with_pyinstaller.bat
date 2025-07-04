@echo off
REM Build the Kiwoom Trader app with PyInstaller

REM Clean previous build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist main.spec del main.spec

REM Set icon path if available
set ICON=resource\icon\activity-feed-64.ico
if not exist %ICON% set ICON=

REM Run PyInstaller
pyinstaller --noconfirm --onefile --windowed ^
  --add-data "ui;ui" ^
  --add-data "resource;resource" ^
  --icon "%ICON%" ^
  main.py

REM Show result
if exist dist\main.exe (
    echo Build succeeded! See dist\main.exe
) else (
    echo Build failed.
)
pause 