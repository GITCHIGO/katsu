# KATSU Live herstarten op de VPS (stopt de lopende runner, start een nieuwe in een eigen venster).
#   irm https://raw.githubusercontent.com/GITCHIGO/katsu/main/deploy/restart.ps1 | iex
$p = Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like '*katsu.live.runner*' }
foreach ($x in $p) { Write-Host "stop KATSU (pid $($x.ProcessId))"; Stop-Process -Id $x.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 3
Start-Process -FilePath "C:\katsu\code\.venv\Scripts\python.exe" -ArgumentList "-m", "katsu.live.runner", "C:\katsu\config.toml" -WorkingDirectory "C:\katsu\code"
Write-Host "KATSU Live opnieuw gestart in een nieuw venster." -ForegroundColor Green
