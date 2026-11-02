@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 若系统已在运行，直接打开浏览器，不重复启动
powershell -NoProfile -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',8899); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 (
  echo 万界大合体已在运行，正在打开浏览器...
  start "" http://127.0.0.1:8899/
  exit /b 0
)

echo ============================================
echo    万界大合体 . 五术合一推演系统
echo ============================================
echo.
python server.py --open
if errorlevel 1 (
  echo.
  echo [提示] 启动失败。请确认：
  echo   1. 已安装 Python 3.10 或更高版本；
  echo   2. 已执行  pip install -r requirements.txt
  echo.
  pause
)
