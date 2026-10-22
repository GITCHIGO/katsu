# KATSU bijwerken op de VPS: nieuwe code ophalen en KATSU Live herstarten.
#   irm https://raw.githubusercontent.com/GITCHIGO/katsu/main/deploy/update.ps1 | iex
Set-Location C:\katsu\code
Write-Host "1/2 code bijwerken (git pull)" -ForegroundColor Cyan
git pull
Write-Host "2/2 KATSU Live herstarten" -ForegroundColor Cyan
irm https://raw.githubusercontent.com/GITCHIGO/katsu/main/deploy/restart.ps1 | iex
