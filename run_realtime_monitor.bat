@echo off
chcp 65001 > nul
cd /d "%~dp0"

REM ========================================================
REM OMG 실시간 모니터링 시작 (중복 방지)
REM ========================================================

REM 기존 프로세스 확인 및 종료
echo 기존 프로세스 확인 중...
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV ^| findstr /C:"python.exe"') do (
    wmic process where "ProcessId=%%i AND CommandLine LIKE '%%crypto_realtime_monitor%%'" get ProcessId 2>nul | findstr /R "^[0-9]" >nul
    if not errorlevel 1 (
        echo 기존 프로세스 발견 (PID: %%i), 종료합니다...
        taskkill /PID %%i /F >nul 2>&1
    )
)

timeout /t 2 /nobreak >nul

echo ========================================================
echo 🔍 OMG 실시간 암호화폐 모니터링 시작
echo ========================================================
echo.
echo 모니터링 설정:
echo   - 대상: Top 100 코인 (debug 파일 기반)
echo   - 간격: 5분마다 체크
echo   - 알림 조건: 매수선 5%% 이내 접근
echo   - 중복 방지: 코인별/레벨별 하루 1회
echo.
echo 초기화:
echo   - 매일 00:00 자동 debug 파일 재생성
echo   - Analysis Excel 기반 모니터링 데이터 로드
echo.
echo 종료하려면 Ctrl+C를 누르세요.
echo ========================================================
echo.

python crypto_realtime_monitor.py

REM 프로세스 종료 시 Lock 파일 정리
if exist "crypto_monitor.lock" del "crypto_monitor.lock"

pause
