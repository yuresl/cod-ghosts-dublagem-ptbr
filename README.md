# Call of Duty: Ghosts (PC) - Dublagem PT-BR completa

Ferramentas para levar a **dublagem oficial em português do Brasil** da versão de PS4 de
*Call of Duty: Ghosts* para a versão de PC, que foi lançada sem ela.

Com a tradução da Tribo Gamer, o PC fica com textos e legendas em português, mas o áudio dos diálogos
de gameplay, do rádio, das chamadas de combate e das cutscenes em tempo real continua em inglês. Este
projeto converte o áudio PT-BR do PS4 para o formato do PC e gera um instalador único com tradução +
dublagem.

> **Este repositório não contém nenhum arquivo do jogo** (áudio, vídeo, zonas ou executáveis) nem os
> arquivos da tradução. Para usar, você precisa das **suas próprias cópias**: o jogo de PC e um dump da
> versão de PS4 (CUSA00018).

## Resultado

| | Antes | Depois |
|---|---|---|
| Textos, menus e legendas | PT-BR (Tribo Gamer) | PT-BR (Tribo Gamer) |
| Diálogos de gameplay, rádio, chamadas de combate | inglês | **PT-BR** |
| Cutscenes em tempo real | inglês | **PT-BR** |
| Vídeos de carregamento das missões | PT-BR / inglês (varia) | **PT-BR** (faixas do PS4) |

- 46.932 sons de singleplayer mapeados entre PC e PS4 (46.892 casados pela ordem exata dentro do alias).
- Validado no jogo nas missões Prologue e "Sem Laços" (Satfarm), com gravação do áudio e análise
  automática: nenhuma fala em inglês fora das que o próprio PS4 não dublou.

### Limitações conhecidas

- Algumas falas de **inimigos e figurantes** continuam em inglês: a própria versão brasileira do PS4
  não as dublou (os arquivos são idênticos aos do inglês).
- Uma fala do Hesh no Prólogo ("Let's check the kill") foi adicionada num patch do PC e não existe no PS4.
- Os vídeos `satfarm_b_load` e `satfarm_transition_ghost` continuam os do PC (organização de faixas diferente).

## Requisitos

- *Call of Duty: Ghosts* para PC, **build 702660**, com a tradução da Tribo Gamer instalada.
- Dump **próprio** da versão de PS4, `CUSA00018` v1.00 (fpkg).
- Windows, ~60 GB livres para os arquivos de trabalho.
- [Python 3.10+](https://www.python.org/) com `numpy scipy soundfile` (e `soundcard` para o gravador).
- [FFmpeg](https://ffmpeg.org/), [FLAC](https://xiph.org/flac/) (`flac`), [HDiffPatch](https://github.com/sisong/HDiffPatch) (`hdiffz`/`hpatchz`).
- [.NET SDK 8](https://dotnet.microsoft.com/) e o [LibOrbisPkg](https://github.com/maxton/LibOrbisPkg) com o patch deste repositório.
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) e [7-Zip](https://www.7-zip.org/) para gerar o instalador.

## Passo a passo

Todos os comandos rodam na raiz do repositório. Pastas de trabalho (`backup_pc_original`,
`ps4_extract`, `work`, `build`) ficam fora do Git (ver `.gitignore`).

### 1. Backup do jogo de PC

```powershell
$jogo = "C:\Games\Call of Duty Ghosts"
robocopy $jogo backup_pc_original soundfile*.pak *.ff *.bik /COPY:DAT
robocopy "$jogo\english"    backup_pc_original\english    /E /COPY:DAT
robocopy "$jogo\portuguese" backup_pc_original\portuguese /E /COPY:DAT
robocopy "$jogo\players2"   backup_pc_original\players2   /E /COPY:DAT
```

Para voltar ao original a qualquer momento: `scripts\restaurar_backup.ps1`.

### 2. Extrair o PKG do PS4

```powershell
git clone https://github.com/maxton/LibOrbisPkg tools\LibOrbisPkg
git -C tools\LibOrbisPkg apply ..\..\patches\liborbispkg-net8.patch
dotnet build tools\LibOrbisPkg\PkgTool.Core\PkgTool.Core.csproj -c Release -o tools\bin\pkgtool
tools\bin\pkgtool\PkgTool.Core.exe pkg_extract "<seu dump>.pkg" ps4_extract
```

O patch corrige um bug que deixa **zeros no meio dos arquivos** quando o LibOrbisPkg é compilado em .NET 6+.

### 3. Catalogar e casar os sons PC ↔ PS4

```powershell
python -I tools\ghosts_vo\catalog.py backup_pc_original\english eng_ ps4_extract\uroot\portuguese work\catalog
```

Gera `work\catalog\mapping.json` e `mapping_report.csv` (com a coluna `revisar`).

### 4. Gerar e validar

```powershell
python -I tools\ghosts_vo\build_zone.py --all --game x --backup backup_pc_original --ps4 ps4_extract\uroot --catalog work\catalog --out work\build_full --tmp work\tmp
python -I tools\ghosts_vo\validate_build.py work\build_full\portuguese backup_pc_original work\catalog
```

O validador deve terminar com `RESULTADO: APROVADO`.

### 5. Montar a pasta `build`

```powershell
New-Item -ItemType Directory build\raiz -Force
Move-Item work\build_full\portuguese build\portuguese
Get-ChildItem ps4_extract\uroot\*_load.bik | Where-Object { $_.Name -notin 'satfarm_b_load.bik','filler_load.bik' } | Copy-Item -Destination build\raiz
```

Para testar direto no jogo, sem instalador: `scripts\instalar_build.ps1`.

### 6. Gerar o instalador único

```powershell
7z x "<instalador da tradução Tribo Gamer>.exe" -owork\trad
python -I tools\ghosts_vo\make_payload.py
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer\CoD_Ghosts_PTBR.iss
```

O instalador (`installer\output\`) faz backup do que substitui, gera os paks PT-BR a partir dos
`eng_soundfile*.pak` do próprio jogo (conferindo o MD5 antes e depois), aplica os patches dos vídeos e
inclui um desinstalador que devolve os arquivos originais.

## Testar no jogo

- `scripts\desbloquear_missoes.py`: libera todas as missões na tela "Selec. Missão" (com backup do perfil).
- `scripts\gravar_audio.ps1`: grava o áudio que sai do PC enquanto você joga (jogo em janela sem bordas).
- `python -I tools\ghosts_vo\analisa_gravacao.py gravacoes\<sessao>.flac --zona prologue`: mostra a
  linha do tempo do que tocou, em PT-BR ou em inglês.

## Como funciona

Detalhes dos formatos e de cada problema resolvido: [docs/ENGENHARIA_REVERSA.md](docs/ENGENHARIA_REVERSA.md).

| Arquivo | Função |
|---|---|
| `tools/ghosts_vo/ff_unpack.py` | lê zonas `.ff` do PC (zlib) e do PS4 |
| `tools/ghosts_vo/zone_sounds.py` | lista os sons (streamed, primed e loaded) de uma zona |
| `tools/ghosts_vo/catalog.py` | catálogo global e mapeamento PS4 → PC |
| `tools/ghosts_vo/build_zone.py` | converte o áudio e gera as zonas e os paks PT-BR |
| `tools/ghosts_vo/validate_build.py` | validação automática do build |
| `tools/ghosts_vo/make_payload.py` | payload mínimo do instalador (trechos PT + patches) |
| `tools/ghosts_vo/gravador.py`, `analisa_gravacao.py` | gravação e análise do áudio do jogo |
| `installer/CoD_Ghosts_PTBR.iss` | script do instalador (Inno Setup) |

## Créditos

- **Tradução** (textos, menus e legendas): Tribo Gamer. Administrador: H3rdell; tradução: H3rdell,
  killerking6261053 e Metralha; revisão e testes: H3rdell e killerking6261053.
- **Pacote de 2022**: Mente Bizarra (zonas de texto usadas como base).
- **Dublagem**: oficial (Activision / Infinity Ward), da versão de PS4.
- **Porte da dublagem para o PC e ferramentas deste repositório**: [yuresl](https://github.com/yuresl).
- [LibOrbisPkg](https://github.com/maxton/LibOrbisPkg) (LGPL-3.0), [HDiffPatch](https://github.com/sisong/HDiffPatch) (MIT).

## Aviso legal

Projeto de fãs, sem afiliação com a Activision ou a Infinity Ward. *Call of Duty* é marca registrada
da Activision Publishing, Inc. Este repositório contém apenas código e documentação: nenhum arquivo do
jogo, da dublagem ou da tradução é distribuído aqui. Use somente com cópias que você possui.

## Licença

O código deste repositório está sob a licença [MIT](LICENSE). Isso não se aplica ao conteúdo do jogo
nem à tradução, que pertencem aos seus autores.
