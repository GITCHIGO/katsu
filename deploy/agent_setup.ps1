# KATSU Agent installeren op de VPS (docs/live_installatie.md §11). Gebruik in PowerShell:
#   irm https://raw.githubusercontent.com/GITCHIGO/katsu/main/deploy/agent_setup.ps1 | iex
# Leest/schrijft alleen in C:\katsu; plaatst geen orders; KATSU zelf moet je daarna herstarten.
Set-Location C:\katsu\code
Write-Host "1/5 code bijwerken (git pull)" -ForegroundColor Cyan
git pull
Write-Host "2/5 privé-repo katsu-data ophalen" -ForegroundColor Cyan
if (-not (Test-Path C:\katsu\katsu-data\.git)) {
    git clone https://github.com/GITCHIGO/katsu-data.git C:\katsu\katsu-data
}
if (-not (Test-Path C:\katsu\katsu-data\.git)) { Write-Host "FOUT: katsu-data niet gekloond (bestaat de repo? ingelogd bij GitHub?)" -ForegroundColor Red; return }
Write-Host "3/5 config aanvullen met [agent]" -ForegroundColor Cyan
$cfg = "C:\katsu\config.toml"
if (-not (Select-String -Path $cfg -Pattern '^\[agent\]' -Quiet)) {
    Add-Content -Path $cfg -Value "`r`n[agent]`r`nrepo_dir = 'C:\katsu\katsu-data'`r`n"
}
Write-Host "4/5 eerste verzameling en waakhond" -ForegroundColor Cyan
& C:\katsu\code\.venv\Scripts\python.exe -m katsu.agent.collect $cfg verzamel
& C:\katsu\code\.venv\Scripts\python.exe -m katsu.agent.collect $cfg waakhond
Write-Host "5/5 taken in de Taakplanner" -ForegroundColor Cyan
schtasks /Create /TN "KATSU waakhond" /SC MINUTE /MO 15 /TR "C:\katsu\code\deploy\waakhond.bat" /F
schtasks /Create /TN "KATSU verzamel" /SC HOURLY /TR "C:\katsu\code\deploy\verzamel.bat" /F
Write-Host "KLAAR. Herstart nu KATSU: Ctrl+C in het KATSU-venster, dan opnieuw starten." -ForegroundColor Green
