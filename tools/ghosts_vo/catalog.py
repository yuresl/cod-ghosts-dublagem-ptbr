"""Catálogo global de sons localizados (PC eng/por vs PS4 por) e mapeamento PS4 -> PC.

Uso: python -I catalog.py <pasta_zonas_pc> <prefixo_pc> <pasta_zonas_ps4> <saida_dir>
"""
import glob, json, os, sys, statistics
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import ff_unpack, zone_sounds


def mp3_ms(b):
    """Duração de um MP3 (ID3 + frames MPEG-1 Layer III) contando os frames."""
    BR = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
    SR = [44100, 48000, 32000]
    i = 0
    if b[:3] == b'ID3':
        i = 10 + ((b[6] << 21) | (b[7] << 14) | (b[8] << 7) | b[9])
    n = 0; sr = 48000
    while i + 4 <= len(b) and b[i] == 0xff and b[i + 1] & 0xe0 == 0xe0:
        br = BR[b[i + 2] >> 4]; sr = SR[(b[i + 2] >> 2) & 3]
        if not br:
            break
        i += 144 * br * 1000 // sr + ((b[i + 2] >> 1) & 1); n += 1
    return n * 1152 / sr * 1000


def dur_ms(r):
    if r['kind'] == 'stream':
        return r['ms']
    if r['kind'] == 'primed' and r.get('side') == 'ps4':
        return r.get('mp3_ms', r['ms'])
    # PC: WAVEFORMAT real (PCM16, ex. 36 kHz; validado contra a mesma gravação em inglês do PS4)
    # PS4: MP3, 'samples' inclui o padding do encoder (~0,03 s)
    return r['samples'] / r['rate'] * 1000


_maps = {}
def stream_ok(folder, prefix, r):
    """Confere se a ref aponta para o início de um stream real (fLaC no PC, ID3/frame MP3 no PS4)."""
    import mmap
    p = os.path.join(folder, f"{prefix}soundfile{r['pak']}.pak")
    if p not in _maps:
        if not os.path.exists(p):
            _maps[p] = None
        else:
            f = open(p, 'rb'); _maps[p] = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    m = _maps[p]
    if m is None or r['off'] + r['len'] > len(m):
        return False
    h = m[r['off']:r['off'] + 4]
    return h == b'fLaC' or h[:3] == b'ID3' or (h[0] == 0xff and h[1] & 0xe0 == 0xe0)


def load_dir(folder, prefix):
    recs = []
    bad = Counter()
    for f in sorted(glob.glob(os.path.join(folder, prefix + '*.ff'))):
        zname = os.path.basename(f)[len(prefix):-3]
        if '_mp' in zname or zname.startswith('mp_'):
            continue                                    # só singleplayer por enquanto
        ver, kind, data, _ = ff_unpack.unpack(f)
        def valid(r):
            ok = stream_ok(folder, prefix, r)
            if not ok:
                bad[zname] += 1
            return ok
        for r in zone_sounds.scan(data, valid):
            if r['kind'] == 'primed' and r['side'] == 'ps4':
                m = _maps[os.path.join(folder, f"{prefix}soundfile{r['pak']}.pak")]
                r['mp3_ms'] = mp3_ms(m[r['off']:r['off'] + r['len']])
            r['zone'] = zname; r['ver'] = ver; r['dur'] = round(dur_ms(r))
            recs.append(r)
    print(prefix, 'candidatos descartados (nao apontam p/ stream valido):', sum(bad.values()))
    return recs


def match(pc, ps4):
    by_alias = defaultdict(list)
    seen_zone = {}
    for r in ps4:                                       # cada alias: entradas da 1ª zona em que aparece
        z = seen_zone.setdefault(r['alias'], r['zone'])
        if z == r['zone']:
            by_alias[r['alias']].append(r)
    pc_groups = defaultdict(list)
    for r in pc:
        pc_groups[(r['zone'], r['alias'])].append(r)
    out = []
    for (zone, alias), lst in pc_groups.items():
        cand = by_alias.get(alias, [])
        for i, r in enumerate(lst):
            m, how = None, 'sem_par'
            if cand and len(cand) == len(lst):
                m, how = cand[i], 'ordem'
            elif cand:
                m = min(cand, key=lambda c: abs(c['dur'] - r['dur'])); how = 'duracao'
            ratio = (m['dur'] / r['dur']) if m and r['dur'] else None
            out.append(dict(zone=zone, alias=alias, n=i, pc_kind=r['kind'], pc_pos=r['pos'],
                            pc_pak=r.get('pak'), pc_off=r.get('off'), pc_len=r.get('len') or r.get('size'),
                            pc_dur=r['dur'], how=how,
                            ps4_zone=m and m['zone'], ps4_kind=m and m['kind'], ps4_pos=m and m['pos'],
                            ps4_pak=m and m.get('pak'), ps4_off=m and m.get('off'),
                            ps4_len=m and (m.get('len') or m.get('size')), ps4_data=m and m.get('data'),
                            ps4_dur=m and m['dur'], ratio=ratio and round(ratio, 3)))
    return out


if __name__ == '__main__':
    pcdir, pcpref, psdir, outdir = sys.argv[1:5]
    os.makedirs(outdir, exist_ok=True)
    pc = load_dir(pcdir, pcpref); ps4 = load_dir(psdir, 'por_')
    json.dump(pc, open(os.path.join(outdir, 'pc_sounds.json'), 'w'))
    json.dump(ps4, open(os.path.join(outdir, 'ps4_sounds.json'), 'w'))
    m = match(pc, ps4)
    import re
    GEN = re.compile(r'generic|breath|cough|death|pain|grunt|scream|effort|yell|exert|plr_|ply_|_ply|_plr|shout|gasp|jump|land|hurt|vox|chatter|laugh|cry|walla|crowd|_dist_|dog|riley|bark|whimper|growl', re.I)
    BC = re.compile(r'^(gl|gm|gs|sp|us|ru|fd|stealth|so|ve)_[a-z0-9]+_', re.I)
    for x in m:
        a = x['alias'] or ''
        x['cat'] = 'battlechatter' if BC.match(a) else ('esforco' if GEN.search(a) else 'dialogo')
        x['revisar'] = x['cat'] == 'dialogo' and (x['how'] != 'ordem' or not x['ratio'] or not .6 <= x['ratio'] <= 1.8)
    print('categorias', Counter(x['cat'] for x in m), '| revisar', sum(x['revisar'] for x in m))
    json.dump(m, open(os.path.join(outdir, 'mapping.json'), 'w'), indent=0)
    import csv
    with open(os.path.join(outdir, 'mapping_report.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(m[0].keys())); w.writeheader(); w.writerows(m)
    c = Counter(x['how'] for x in m)
    print('PC sons', len(pc), Counter(r['kind'] for r in pc), '| PS4 sons', len(ps4), Counter(r['kind'] for r in ps4))
    print('mapeamento', dict(c), 'cobertura %.1f%%' % (100 * (len(m) - c['sem_par']) / len(m)))
    rat = [x['ratio'] for x in m if x['ratio']]
    print('razao dur PS4/PC: mediana %.2f | fora de 0.6..1.8: %d' % (statistics.median(rat), sum(1 for r in rat if not .6 <= r <= 1.8)))
    for z, k in sorted(Counter((x['zone'], x['how']) for x in m).items()):
        pass
    per = defaultdict(Counter)
    for x in m: per[x['zone']][x['how']] += 1
    for z in sorted(per): print('  %-34s %s' % (z, dict(per[z])))
