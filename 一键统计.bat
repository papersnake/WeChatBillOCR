@echo off
title 微信账单统计 -
setlocal enabledelayedexpansion

set "ADB=E:\rou\scrcpy\scrcpy-win64-v3.2\adb.exe"
set "UMI=E:\rou\Umi-OCR\Umi-OCR_Rapid_v2.1.5\Umi-OCR.exe"
set "DEVFILE=E:\rou\last_device.txt"
set "DEV="

:menu
cls
echo ================================================
echo    微信账单统计 - 一键启动
echo ================================================
if exist "%DEVFILE%" (
    set /p LASTDEV=<"%DEVFILE%"
) else (
    set "LASTDEV=未设置"
)
echo  上次设备: !LASTDEV!
echo ------------------------------------------------
echo   [1] 一键运行（连接手机 + 启动OCR + 统计）
echo   [2] 只连接手机
echo   [3] 只启动 Umi-OCR
echo   [4] 退出
echo.
set "CHOICE="
set /p CHOICE=请输入选项后回车:
if "%CHOICE%"=="1" goto runall
if "%CHOICE%"=="2" goto onlyconnect
if "%CHOICE%"=="3" goto onlyocr
if "%CHOICE%"=="4" exit /b 0
goto menu

:runall
call :connect
call :ocr
call :stats
pause
goto menu

:onlyconnect
call :connect
pause
goto menu

:onlyocr
call :ocr
pause
goto menu

rem ==== subroutines ====

:connect
set "DEV="
set /p DEV=手机IP:端口（直接回车用上次的 !LASTDEV!）:
if "!DEV!"=="" set "DEV=!LASTDEV!"
if "!DEV!"=="" (
    echo [错误] 未输入设备地址
    exit /b 1
)
"%ADB%" connect !DEV!
echo,!DEV!>"%DEVFILE%"
echo.
echo 当前设备列表:
"%ADB%" devices
exit /b 0

:ocr
curl -s -m 2 -o nul http://127.0.0.1:1224/ 2>nul
if not errorlevel 1 (
    echo [OK] Umi-OCR 正在运行
    exit /b 0
)
echo 正在启动 Umi-OCR（无窗口模式）...
start "" "%UMI%" --no_win
set /a N=0
:waitloop
timeout /t 1 /nobreak >nul
curl -s -m 2 -o nul http://127.0.0.1:1224/ 2>nul
if not errorlevel 1 (
    echo [OK] Umi-OCR 已启动
    exit /b 0
)
set /a N+=1
if !N! lss 20 goto waitloop
echo [错误] Umi-OCR 启动超时，请手动检查
exit /b 1

:stats
set "MONTHS="
set /p MONTHS=统计最近几个月（直接回车默认2）:
if "!MONTHS!"=="" set "MONTHS=2"
echo.
if not "!DEV!"=="" (
    python E:\rou\wechat_bill_ocr.py --device !DEV! --months !MONTHS!
) else (
    python E:\rou\wechat_bill_ocr.py --months !MONTHS!
)
exit /b 0
