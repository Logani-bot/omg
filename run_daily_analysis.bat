@echo off
chcp 65001 > nul
REM ========================================
REM OMG Daily Analysis (00:10 Auto Run)
REM ========================================
REM Top 100 코인 Phase 1.5 시뮬레이션
REM Debug 파일 + Analysis Excel 생성
REM ========================================

cd /d "%~dp0"

REM 로그 파일 설정
set LOG_FILE=logs\omg_daily_%date:~0,4%%date:~5,2%%date:~8,2%.log
if not exist "logs" mkdir "logs"

echo ======================================== >> "%LOG_FILE%"
echo OMG Daily Analysis - %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

echo ========================================
echo OMG Daily Analysis - %date% %time%
echo ========================================
echo.

REM ===== Step 1: Top 100 코인 Debug 파일 생성 =====
echo [1/2] Generating debug files for Top 100 coins...
echo ========================================
echo [1/2] auto_debug_builder.py 실행 중... >> "%LOG_FILE%"

python auto_debug_builder.py --limit-days 1200 >> "%LOG_FILE%" 2>&1

if %ERRORLEVEL% neq 0 (
    echo ERROR: auto_debug_builder.py failed! >> "%LOG_FILE%"
    echo ERROR: Debug 파일 생성 실패!
    goto :error_exit
)

echo Step 1 completed successfully >> "%LOG_FILE%"
echo.

REM ===== Step 2: Analysis Excel 생성 =====
echo [2/2] Generating analysis Excel...
echo ========================================
echo [2/2] coin_analysis_excel.py 실행 중... >> "%LOG_FILE%"

python coin_analysis_excel.py >> "%LOG_FILE%" 2>&1

if %ERRORLEVEL% neq 0 (
    echo ERROR: coin_analysis_excel.py failed! >> "%LOG_FILE%"
    echo ERROR: Analysis Excel 생성 실패!
    goto :error_exit
)

echo Step 2 completed successfully >> "%LOG_FILE%"

echo.
echo ========================================
echo 완료: %date% %time%
echo ========================================
echo 완료: %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

echo SUCCESS: Daily analysis completed >> "%LOG_FILE%"
echo.
echo 생성된 파일:
echo   - debug/*.csv (Top 100 coins)
echo   - output/coin_analysis_*.xlsx
echo.
exit /b 0

:error_exit
echo ========================================
echo ERROR: 작업 실패 at %date% %time%
echo ========================================
echo ERROR: 작업 실패 at %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
exit /b 1
