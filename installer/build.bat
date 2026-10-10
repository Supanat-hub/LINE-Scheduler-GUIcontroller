@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo  LINE Scheduler - Automated Build Script (PyInstaller + Inno Setup)
echo =====================================================================

cd /d "%~dp0\.."

echo [*] 1. ตรวจสอบการติดตั้งแพ็กเกจที่จำเป็น...
python -m pip install -q pyinstaller customtkinter pywinauto pyautogui pyperclip apscheduler pystray pillow pywin32

echo [*] 2. เริ่มต้นคอมไพล์ด้วย PyInstaller...
python -m PyInstaller --noconfirm --clean installer\build.spec

if %ERRORLEVEL% NEQ 0 (
    echo [-] การคอมไพล์ด้วย PyInstaller ล้มเหลว!
    pause
    exit /b %ERRORLEVEL%
)

echo [OK] คอมไพล์ PyInstaller สำเร็จ! ผลลัพธ์อยู่ที่ dist\LineScheduler\

echo [*] 3. ตรวจสอบ Inno Setup Compiler (ISCC.exe)...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
)

where ISCC >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set ISCC=ISCC
)

if exist %ISCC% (
    echo [*] พบ Inno Setup Compiler: %ISCC%
    echo [*] กำลังสร้างตัวติดตั้ง LineScheduler-Setup.exe...
    %ISCC% installer\setup.iss
    if %ERRORLEVEL% EQU 0 (
        echo =====================================================================
        echo  [SUCCESS] สร้างตัวติดตั้งสำเร็จ: dist\installer\LineScheduler-Setup.exe
        echo =====================================================================
    ) else (
        echo [-] การสร้างตัวติดตั้งด้วย Inno Setup ล้มเหลว!
    )
) else (
    echo [!] ไม่พบ Inno Setup บนเครื่องนี้
    echo     คุณสามารถใช้โฟลเดอร์ dist\LineScheduler\ ได้ทันที
    echo     หรือติดตั้ง Inno Setup 6 จาก https://jrsoftware.org/isdl.php เพื่อสร้าง Setup.exe
)

echo.
pause
