@echo off
rem Daily Trend E1 run (YouTube): builds the view snapshots that "measured growth" needs.
rem Scheduled with Windows Task Scheduler ("FYP Trend Daily"). Log: pipeline\cache\daily_run.log
rem The embedding model is already downloaded; offline mode stops a hang on the HF Hub check.
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
cd /d "%~dp0..\.."
echo ===== %date% %time% ===== >> pipeline\cache\daily_run.log
py -3.10 -X utf8 experiments\trend_e1\run_e1.py --versions youtube >> pipeline\cache\daily_run.log 2>&1
echo exit=%errorlevel% >> pipeline\cache\daily_run.log
