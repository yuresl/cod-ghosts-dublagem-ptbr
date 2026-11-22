"""Teste sintético do analisador: monta uma 'gravação' com música de fundo + falas PT e EN conhecidas
em instantes conhecidos, com volume baixo e ruído, e confere se o analisador acerta."""
import os, sys, subprocess, numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(__file__))
import analisa_gravacao as ag

JOGO = 'C:/Games/Call of Duty Ghosts'
pt = ag.refs_da_zona(f'{JOGO}/portuguese/por_prologue.ff', f'{JOGO}/portuguese', 'por_', 'prologue')
en = ag.refs_da_zona('backup_pc_original/english/eng_prologue.ff', 'backup_pc_original/english', 'eng_', 'prologue')
escolha = [('PT', ('youngblood_els_gethiminthe', 0)), ('PT', ('youngblood_hsh_whatthehellis', 0)),
           ('EN', ('youngblood_hsh_thenwhatthehell', 0)), ('PT', ('odin_kyr_houstonbudandi', 0)),
           ('EN', ('youngblood_els_heshlogan', 0)), ('PT', ('youngblood_hsh_comeondown', 0))]
# fundo: faixa de música do vídeo de abertura (estéreo) a 48 kHz
mus = subprocess.run(['ffmpeg', '-v', 'error', '-i', f'{JOGO}/prologue_load.bik', '-map', '0:1', '-t', '100',
                      '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'], capture_output=True).stdout
fundo = np.frombuffer(mus, dtype=np.float32).copy() * 0.6
fundo = np.concatenate([fundo, fundo])[:150 * 48000]
rng = np.random.default_rng(1); fundo += rng.normal(0, 0.01, len(fundo)).astype(np.float32)
esperado = []
for i, (lang, k) in enumerate(escolha):
    d = pt if lang == 'PT' else en
    if k not in d:
        print('sem ref', lang, k); continue
    sig4 = d[k]
    sig = np.interp(np.arange(len(sig4) * 12) / 12, np.arange(len(sig4)), sig4).astype(np.float32)
    t = 8 + i * 22.3
    s = int(t * 48000); fundo[s:s + len(sig)] += 0.35 * sig[:len(fundo) - s]
    esperado.append((t, lang, k))
os.makedirs('work/teste_analisador', exist_ok=True)
sf.write('work/teste_analisador/sintetico.flac', np.stack([fundo, fundo], 1), 48000)
for e in esperado: print('inserido', f'{e[0]:6.1f}s', e[1], e[2])
