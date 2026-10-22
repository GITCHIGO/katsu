@echo off
cd /d C:\katsu\code
.venv\Scripts\python.exe -m katsu.agent.collect C:\katsu\config.toml waakhond >> C:\katsu\data\waakhond.txt 2>&1
