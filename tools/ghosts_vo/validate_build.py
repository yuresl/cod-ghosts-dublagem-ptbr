"""Valida um build de VO PT-BR contra o backup original.

Para cada zona por_*.ff do build:
  * a zona descomprime e tem o mesmo tamanho de corpo do original;
  * os sons estão nas mesmas posições e nada mudou fora dos campos de som;
  * cada ref streamed aponta para a região PT-BR acrescentada (ou é uma das exceções conhecidas
    do mapeamento: sem par no PS4);
  * todos os FLAC acrescentados passam no `flac -t`.
Para cada pak do build: o prefixo (conteúdo original) é idêntico ao backup.

Uso: python -I validate_build.py <build/portuguese> <backup_pc_original> <work/catalog>
"""
import json, os, subprocess, sys, glob, hashlib, struct
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
import ff_unpack, zone_sounds, catalog


def main(build, backup, cat):
    bport = os.path.join(backup, 'portuguese')
    mapping = json.load(open(os.path.join(cat, 'mapping.json')))
    sem_par = {(x['zone'], x['alias'], x['n']) for x in mapping if x['how'] == 'sem_par'}
    ok = True
    orig = {}
    for p in sorted(glob.glob(os.path.join(build, 'por_soundfile*.pak'))):
        n = int(os.path.basename(p)[len('por_soundfile'):-4])
        o = os.path.join(bport, os.path.basename(p)); orig[n] = os.path.getsize(o)
        h1 = hashlib.md5(); h2 = hashlib.md5()
        with open(o, 'rb') as a, open(p, 'rb') as b:
            left = orig[n]
            while left:
                k = min(left, 1 << 24); h1.update(a.read(k)); h2.update(b.read(k)); left -= k
        same = h1.digest() == h2.digest()
        ok &= same
        print(f'pak {n:2d}: prefixo original {"OK" if same else "DIFERENTE!"}  +{(os.path.getsize(p) - orig[n]) / 1e6:.1f} MB')

    def pak_for(n):
        return build if n in orig else bport

    flac_jobs = []
    tot = Counter()
    for f in sorted(glob.glob(os.path.join(build, 'por_*.ff'))):
        zone = os.path.basename(f)[4:-3]
        _, _, ob, _ = ff_unpack.unpack(os.path.join(bport, os.path.basename(f)))
        _, _, nb, _ = ff_unpack.unpack(f)
        if len(ob) != len(nb):
            print(zone, 'TAMANHO DO CORPO MUDOU'); ok = False; continue
        ro = zone_sounds.scan(ob)          # sem validação: a por_ original pode ter offsets inválidos
        rn = zone_sounds.scan(nb, lambda r: catalog.stream_ok(pak_for(r['pak']), 'por_', r))
        pos_ok = [r['pos'] for r in ro] == [r['pos'] for r in rn]
        allowed = bytearray(len(ob))
        for r in ro:
            if r['kind'] == 'stream':
                allowed[r['pos'] + 16:r['pos'] + 36] = b'\x01' * 20
            elif r['kind'] == 'primed':
                allowed[r['pos'] + 16:r['pos'] + 32] = b'\x01' * 16        # offset, len
                allowed[r['pos'] + 40:r['pos'] + 52] = b'\x01' * 12        # hdr, total, hash(=0)
                allowed[r['ls'] + 24:r['ls'] + 36] = b'\x01' * 12          # rate, fsiz, samples
                allowed[r['data']:r['data'] + r['prime']] = b'\x01' * r['prime']
            else:
                for k in (24, 25, 26, 27, 36, 37, 38, 39):
                    allowed[r['pos'] + k] = 1
                allowed[r['data']:r['data'] + r['size']] = b'\x01' * r['size']
        fora = sum(1 for i in range(len(ob)) if ob[i] != nb[i] and not allowed[i])
        c = Counter()
        for r in rn:
            if r['kind'] == 'loaded':
                c['loaded'] += 1; continue
            if r['pak'] in orig and r['off'] >= orig[r['pak']]:
                c['pt' if r['kind'] == 'stream' else 'pt_primed'] += 1
                flac_jobs.append((r['pak'], r['off'], r['len']))
                if r['kind'] == 'primed':
                    # o trecho na zona tem de ser exatamente o começo dos frames do FLAC no pak
                    with open(os.path.join(build, f"por_soundfile{r['pak']}.pak"), 'rb') as f:
                        f.seek(r['off'] + r['hdr']); head = f.read(r['prime'])
                    if (head != nb[r['data']:r['data'] + r['prime']] or r['fsiz'] != r['len'] - r['hdr']
                            or struct.unpack_from('<I', nb, r['pos'] + 48)[0] != 0):
                        c['PRIMED_INCONSISTENTE'] += 1
            elif (zone, r['alias'], r['n']) in sem_par:
                c['sem_par'] += 1
            elif r['kind'] == 'primed' and r['ch'] != 1:
                c['primed_estereo_ingles'] += 1
            else:
                c['INGLES_INESPERADO'] += 1
        good = pos_ok and fora == 0 and not c['INGLES_INESPERADO'] and not c['PRIMED_INCONSISTENTE']
        ok &= good
        tot += c
        print(f'{zone:22s} {"OK " if good else "ERRO"} sons={len(rn)} {dict(c)} fora_dos_campos={fora}')

    uniq = sorted(set(flac_jobs))

    def test(j):
        n, off, ln = j
        with open(os.path.join(build, f'por_soundfile{n}.pak'), 'rb') as f:
            f.seek(off); d = f.read(ln)
        return subprocess.run(['flac', '-t', '-s', '-'], input=d, capture_output=True).returncode == 0
    with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4) - 2)) as ex:
        res = list(ex.map(test, uniq))
    bad = res.count(False)
    ok &= bad == 0
    print('TOTAL', dict(tot), f'| FLAC únicos testados: {len(uniq)}, com erro: {bad}')
    print('RESULTADO:', 'APROVADO' if ok else 'REPROVADO')
    return ok


if __name__ == '__main__':
    sys.exit(0 if main(*sys.argv[1:4]) else 1)
