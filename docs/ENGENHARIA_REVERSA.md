# Engenharia reversa: VO do CoD Ghosts (PS4 → PC)

Notas técnicas do que foi descoberto para portar a dublagem in-game da versão de PS4 (CUSA00018, v1.00)
para a versão de PC (build 702660). Tudo foi obtido analisando os arquivos; nenhum executável foi
modificado.

## Por que o PC não tinha a dublagem in-game

A tradução da Tribo Gamer cria a pasta `portuguese\` do jogo, mas os 32 arquivos
`portuguese\por_soundfile*.pak` são **cópias byte a byte** de `english\eng_soundfile*.pak`. O jogo
carrega o idioma português (textos e legendas), mas o áudio localizado continua em inglês.

## Extração do PS4

- O PKG é um fpkg; o `PkgTool` do [LibOrbisPkg](https://github.com/maxton/LibOrbisPkg) extrai.
- **Bug com .NET 6+:** em `PFSCReader.cs`, `DeflateStream.Read` é chamado uma vez por bloco de 64 KB.
  No .NET 6+ essa leitura pode devolver menos bytes que o pedido, o que deixa **zeros no meio dos
  arquivos** extraídos. Correção em `patches/liborbispkg-net8.patch`: ler em loop até completar o bloco.

## Zonas (`.ff`)

```
0x00 'IWffu100' | 0x08 u32 versão (PC 0x235, PS4 0x231) | 0x0C flags | 0x10 8 bytes
0x18 u32 N | N × 24 bytes (streaming de imagens) | u64 tamanho | u64 tamanho | corpo
Corpo: PC = zlib; PS4 = sem compressão.
```
A tradução preenche as zonas `por_*` com zeros até o tamanho original; o instalador faz o mesmo.

## Sons

| | PC | PS4 |
|---|---|---|
| Streams (`<lang>_soundfileN.pak`) | FLAC 32/36 kHz, offsets **não** alinhados | MP3 48 kHz (LAME 3.98), ID3v2 + `PRIV` |
| Loaded (dentro da zona) | PCM16, WAVEFORMAT (geralmente 36 kHz) | MP3 |

FLAC do PC: blocos de 1024 amostras; metadados `STREAMINFO`, `VORBIS_COMMENT`
("reference libFLAC 1.2.1 20070917"), `APPLICATION 'fsiz'` (u32 = bytes de frames) e `SEEKTABLE`
(um ponto a cada 16384 amostras).

### Estruturas

```
snd_alias_list_t:   ptr(-1) | ptr(-1) | u32 count | pad | nome\0     (seguido de `count` entradas)

SoundFile tipo 2 (streamed), 40 bytes:
  02 01 00*6 | u8 isLocalized, pad | u16 fileIndex | u32 flags | u64 offset | u64 tamanho | u32 ms

SoundFile tipo 3 (primed: stream no .pak + início pré-carregado na zona):
  03 01 00*6 | u8 loc, pad | u16 fileIndex | u32 flags | u64 offset | u64 tamanho |
  ptr(-1) | u32 hdr | u32 fsiz | u32 VERIFICAÇÃO | pad | LoadedSound com os primeiros N bytes de frames

LoadedSound PC:  ptr(-1) | ptr(-2) | u64 0 | u32 rate | u32 size | u32 frames | u32 bytes/s |
                 u16 ch | u16 bits | u16 blockAlign | u16 ? | u32 size | pad | nome\0 | PCM
LoadedSound PS4: ptr(-1) | u64 size | ptr(-1) | u32 rate | u32 size | u32 samples | u32 0 |
                 u16 ch | u16 bits | u16 fmt(2=MP3) | u16 ? | u32 frames | pad | ptr(-1) | nome\0 | MP3
```

### Pontos que custaram caro (e a solução)

1. **Offsets não alinhados:** filtrar refs por alinhamento descartava 2/3 dos sons do PC. Agora cada
   candidato é validado pelo conteúdo do `.pak` (`fLaC`/`ID3` no offset).
2. **Atribuição de alias:** usar "o último nome antes do som" pegava nomes de grupo de mixer; o certo
   é o cabeçalho `snd_alias_list_t` com `count`.
3. **Primed (tipo 3):** o motor toca os N bytes de frames embutidos na zona e continua lendo o pak em
   `offset + hdr + N`. O campo **VERIFICAÇÃO** (u32 em +48) é checado contra o conteúdo; se não bate,
   o som é **descartado (fica mudo)**. **Zerado, o jogo não verifica** (confirmado em teste). O
   algoritmo não é CRC32, CRC32C, Adler, FNV, djb2, sdbm, xxHash nem MurmurHash3.
4. **Zonas `por_` alteradas pela tradução** (`por_common`, `por_code_post_gfx`): têm outro tamanho;
   os sons são localizados por (alias, ordem) e não por posição.

### Mapeamento PS4 → PC

Os nomes de alias são idênticos. PC e PS4 têm **46.932** sons de singleplayer cada; 46.892 casam
pela ordem exata dentro do alias. Validação da ordem: 7.153/7.153 sons de 5 zonas têm a mesma duração
(±120 ms) no PC em inglês e no PS4 em inglês.

## Build

- Os paks `por_soundfileN.pak` **só crescem**: o PT-BR é anexado no fim (alinhado em 2048), então o
  conteúdo original e as outras zonas ficam intactos.
- Zonas: campos fixos alterados in-place (o corpo mantém o tamanho); loaded mantém o tamanho do buffer
  e ajusta a taxa no WAVEFORMAT para a fala PT caber.
- `validate_build.py`: prefixo dos paks idêntico, 0 bytes alterados fora dos campos de som, nenhuma
  ref apontando para o inglês (exceto exceções conhecidas), `flac -t` em todos os FLAC, trecho primed
  igual aos frames do pak e verificação = 0.

## Vídeos (`*_load.bik`)

Bink 2 com 11 grupos × 4 faixas de áudio (um grupo por idioma). No PC o grupo 9 é cópia do inglês; no
PS4 os grupos 6 e 9 têm áudio próprio. Os 18 vídeos compatíveis (mesmos quadros, resolução, fps e
faixas) são substituídos via patch HDiffPatch (~3,5% do tamanho). `satfarm_b_load` e
`satfarm_transition_ghost` têm outra organização de faixas no PS4 e não são trocados.

## Limites da fonte

- O PT-BR do PS4 deixou ~16% das falas de diálogo em inglês (inimigos e figurantes) e ~27% do battle
  chatter: os arquivos são idênticos aos do inglês do PS4.
- `youngblood_hsh_letscheckthekill` não existe no PS4 v1.00 (foi adicionada num patch do PC).

## Testes no jogo

- `gravador.py` grava o áudio de saída do Windows (loopback WASAPI).
- `analisa_gravacao.py` procura cada som da missão na gravação (GCC-PHAT na banda de voz) nas versões
  PT-BR e inglês. Teste sintético: 6/6 falas no instante e idioma certos, 0 falsos positivos.
- Prologue: 43 diálogos detectados, todos em PT-BR. Satfarm: 356 sons PT-BR, 0 em inglês.
- Esta versão do jogo ignora `+map` na linha de comando e comandos no `config.cfg`; para chegar a uma
  missão, use `scripts/desbloquear_missoes.py`.
