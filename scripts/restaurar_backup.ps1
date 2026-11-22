# Restaura os arquivos originais de audio/zonas do CoD Ghosts (PC) a partir do backup.
# Uso:  powershell -ExecutionPolicy Bypass -File restaurar_backup.ps1 [-Jogo "C:\Games\Call of Duty Ghosts"]
param(
    [string]$Jogo   = "C:\Games\Call of Duty Ghosts",
    [string]$Backup = (Join-Path (Split-Path -Parent $PSScriptRoot) "backup_pc_original")
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path "$Jogo\iw6sp64_ship.exe")) { throw "Jogo nao encontrado em $Jogo" }
if (-not (Test-Path "$Backup\english")) { throw "Backup nao encontrado em $Backup" }
if (Get-Process iw6sp64_ship -ErrorAction SilentlyContinue) { throw "Feche o jogo antes de restaurar." }

robocopy $Backup $Jogo soundfile*.pak *.ff *.bik /COPY:DAT /R:1 /W:1 /NP /NFL /NDL | Out-Null
robocopy "$Backup\english"    "$Jogo\english"    /E /COPY:DAT /R:1 /W:1 /NP /NFL /NDL | Out-Null
robocopy "$Backup\portuguese" "$Jogo\portuguese" /E /COPY:DAT /R:1 /W:1 /NP /NFL /NDL | Out-Null
robocopy "$Backup\players2"   "$Jogo\players2"   /E /COPY:DAT /R:1 /W:1 /NP /NFL /NDL | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy falhou (codigo $LASTEXITCODE)" }
Write-Host "Restauracao concluida."
