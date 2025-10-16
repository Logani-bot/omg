@echo off
REM Envelope Alert 실행 배치 파일
REM Windows 작업 스케줄러에서 사용

cd /d C:\Coding\OMG
python envelope_alert.py

REM 에러 발생 시 로그 저장
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] %date% %time% - Exit Code: %ERRORLEVEL% >> envelope_alert_error.log
)

