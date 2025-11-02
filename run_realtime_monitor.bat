@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================================
echo 🔍 OMG 실시간 암호화폐 모니터링 시작
echo ========================================================
echo.
echo 모니터링 설정:
echo   - 대상: Top 100 코인 (debug 파일 기반)
echo   - 간격: 30분마다 체크
echo   - 알림 조건: 매수선 5%% 이내 접근
echo   - 중복 방지: 코인별/레벨별 하루 1회
echo.
echo 초기화:
echo   - 매일 00:10 자동 debug 파일 재생성
echo   - Analysis Excel 기반 모니터링 데이터 로드
echo.
echo 종료하려면 Ctrl+C를 누르세요.
echo ========================================================
echo.

python crypto_realtime_monitor.py

pause
