@echo off
cd /d C:\katsu\code
.venv\Scripts\python.exe -m katsu.agent.collect C:\katsu\config.toml verzamel >> C:\katsu\data\verzamel.txt 2>&1
