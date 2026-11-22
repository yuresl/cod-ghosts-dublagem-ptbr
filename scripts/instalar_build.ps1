# Instala o build de VO PT-BR (gerado a partir do PS4) no jogo.
#   build\portuguese\*  -> <jogo>\portuguese\   (zonas por_*.ff + por_soundfile*.pak)
#   build\raiz\*.bik    -> <jogo>\              (vídeos de carregamento com a faixa PT-BR do PS4)
# Desfazer: scripts\restaurar_backup.ps1
param(
    [string]$Jogo  = "C:\Games\Call of Duty Ghosts",
    [string]$Build = (Join-Path (Split-Path -Parent $PSScriptRoot) "build")
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path "$Jogo\iw6sp64_ship.exe")) { throw "Jogo nao encontrado em $Jogo" }
if (Get-Process iw6sp64_ship -ErrorAction SilentlyContinue) { throw "Feche o jogo antes de instalar." }
$bk = Join-Path (Split-Path -Parent $PSScriptRoot) "backup_pc_original"
if (-not (Test-Path "$bk\portuguese") -or -not (Test-Path "$bk\prologue_load.bik")) { throw "Backup ausente; nao vou instalar sem backup." }

$n = 0
foreach ($par in @(@("$Build\portuguese", "$Jogo\portuguese"), @("$Build\raiz", $Jogo))) {
    if (-not (Test-Path $par[0])) { continue }
    Get-ChildItem $par[0] -File | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $par[1] $_.Name) -Force
        $n++
    }
}
Write-Host "instalados: $n arquivos"
