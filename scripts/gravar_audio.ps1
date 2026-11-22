# Grava o áudio que sai do PC (o que você ouve no fone/caixa) enquanto joga.
# Abra ANTES de iniciar o jogo e feche com Ctrl+C quando terminar o trecho.
# A gravação vai para <repositório>\gravacoes\sessao_<data>.flac
$py = (Get-Command python -ErrorAction Stop).Source
$raiz = Split-Path -Parent $PSScriptRoot
& $py -I (Join-Path $raiz "tools\ghosts_vo\gravador.py") (Join-Path $raiz "gravacoes")
