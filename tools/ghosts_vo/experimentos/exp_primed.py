"""Build de EXPERIMENTO para descobrir por que os sons primed (tipo 3) ficam mudos.

Parte do build atual (build/portuguese) e altera só 3 falas do Prologue:
  E1 youngblood_els_odinitsodin    : FLAC inglês ORIGINAL (bytes intactos), apenas movido p/ o fim do pak;
                                     campos e trecho primed da zona = os originais em inglês.
  E2 youngblood_hsh_whatdiddadmean : áudio INGLÊS decodificado e reencodado pelo nosso encoder, movido.
  E3 youngblood_hsh_readypush      : PT-BR como no build atual, mas com o campo 'hash' (+48) zerado.
Saída: work/exp/portuguese (por_prologue.ff + paks alterados).
"""
import os, sys, struct, shutil, subprocess, json
sys.path.insert(0, os.path.dirname(__file__))
import ff_unpack, zone_sounds, build_zone as bz

BUILD = 'build/portuguese'; BK = 'backup_pc_original'; OUT = 'work/exp/portuguese'; TMP = 'work/tmp_exp'
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)

raw = open(f'{BUILD}/por_prologue.ff', 'rb').read()
body = bytearray(ff_unpack.unpack(f'{BUILD}/por_prologue.ff')[2])
orig = ff_unpack.unpack(f'{BK}/portuguese/por_prologue.ff')[2]
recs = {(r['alias'], r['n']): r for r in zone_sounds.scan(bytes(body)) if r['kind'] == 'primed'}
orecs = {(r['alias'], r['n']): r for r in zone_sounds.scan(orig) if r['kind'] == 'primed'}
paks = {}

def pak_out(n):
    if n not in paks:
        dst = f'{OUT}/por_soundfile{n}.pak'
        shutil.copyfile(f'{BUILD}/por_soundfile{n}.pak', dst); paks[n] = dst
    return paks[n]

def append(n, data):
    p = pak_out(n)
    with open(p, 'r+b') as f:
        f.seek(0, 2); end = f.tell(); start = (end + 2047) // 2048 * 2048
        f.write(bytes(start - end)); f.write(data)
    return start

def eng_flac(o):
    with open(f"{BK}/english/eng_soundfile{o['pak']}.pak", 'rb') as f:
        f.seek(o['off']); return f.read(o['len'])

def set_primed(r, off, fl, rate, samples, head):
    i, L = r['pos'], r['ls']
    hl = bz.flac_header_len(fl)
    struct.pack_into('<QQ', body, i + 16, off, len(fl))
    struct.pack_into('<II', body, i + 40, hl, len(fl) - hl)
    struct.pack_into('<III', body, L + 24, rate, len(fl) - hl, samples)
    assert len(head) == r['prime']
    body[r['data']:r['data'] + r['prime']] = head

log = []
# E1: original inglês, só movido
r = recs[('youngblood_els_odinitsodin', 0)]; o = orecs[('youngblood_els_odinitsodin', 0)]
fl = eng_flac(o); off = append(r['pak'], fl)
set_primed(r, off, fl, o['rate'], o['samples'], fl[o['hdr']:o['hdr'] + r['prime']])
assert body[r['data']:r['data'] + r['prime']] == orig[o['data']:o['data'] + o['prime']]
log.append(('E1 odinitsodin', 'ingles original movido', off))

# E2: inglês reencodado pelo nosso encoder
r = recs[('youngblood_hsh_whatdiddadmean', 0)]; o = orecs[('youngblood_hsh_whatdiddadmean', 0)]
src = f'{TMP}/e2.flac'; open(src, 'wb').write(eng_flac(o))
pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-f', 's16le', '-ac', str(o['ch']), '-'], capture_output=True, check=True).stdout
fl = bz.encode_flac_pc(pcm, o['rate'], TMP, 'e2b', ch=o['ch'])
hl = bz.flac_header_len(fl)
assert len(fl) - hl >= r['prime'], 'FLAC menor que o trecho primed'
off = append(r['pak'], fl)
set_primed(r, off, fl, o['rate'], len(pcm) // (2 * o['ch']), fl[hl:hl + r['prime']])
log.append(('E2 whatdiddadmean', 'ingles reencodado', off))

# E3: PT atual, hash zerado
r = recs[('youngblood_hsh_readypush', 0)]
struct.pack_into('<I', body, r['pos'] + 48, 0)
log.append(('E3 readypush', 'PT com hash=0', None))

open(f'{OUT}/por_prologue.ff', 'wb').write(bz.pack_zone(raw, bytes(body)))
for l in log: print(*l)
print('arquivos:', sorted(os.listdir(OUT)))
