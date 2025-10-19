@echo off
echo 업비트 모니터링 시스템 시작
echo ================================

cd /d "%~dp0"

python run_monitor.py

pause

