"""Procura, numa gravação do áudio do jogo, cada fala de uma missão nas versões PT-BR e inglês.

Uso:
  python -I analisa_gravacao.py <gravacao.flac> [--zona prologue] [--jogo "C:/Games/Call of Duty Ghosts"]
                                [--backup backup_pc_original] [--catalog work/catalog] [--saida relatorio.csv]

Referências:
  PT-BR  = o que está INSTALADO no jogo (portuguese/por_<zona>.ff + por_soundfile*.pak)
  inglês = backup original (english/eng_<zona>.ff + eng_soundfile*.pak)
Detecção: correlação cruzada GCC-PHAT (banda de voz) em segmentos da gravação; o escore é o pico
normalizado (z-score). Para cada fala informa o melhor instante e o idioma que bateu.
"""
import argparse, csv, hashlib, io, json, os, sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
sys.path.insert(0, os.path.dirname(__file__))
import ff_unpack, zone_sounds, catalog

SR = 4000                 # análise em 4 kHz (voz até 2 kHz)
SEG = 32 * SR             # segmento da gravação
HOP = 24 * SR             # sobreposição de 8 s (= REF_MAX)
REF_MAX = 8 * SR          # usa no máximo os 8 s iniciais de cada fala
LIMIAR = 18.0             # z-score mínimo para considerar "tocou" (ruído de fundo fica em 9-12)
MARGEM = 1.5              # o idioma vencedor precisa de z >= MARGEM x o do outro


def to_sr(x, sr):
    if x.ndim > 1:
        x = x.mean(axis=1)
    x = x.astype(np.float64)
    from math import gcd
    g = gcd(int(sr), SR)
    return resample_poly(x, SR // g, int(sr) // g)


def flac_bytes_to(x):
    d, sr = sf.read(io.BytesIO(x), dtype='float32')
    return to_sr(d, sr)


def pcm_to(raw, rate, ch):
    a = np.frombuffer(raw[:len(raw) // (2 * ch) * 2 * ch], dtype='<i2').astype(np.float32) / 32768
    return to_sr(a.reshape(-1, ch) if ch > 1 else a, rate)


def ler_pak(path, off, ln):
    with open(path, 'rb') as f:
        f.seek(off); return f.read(ln)


def refs_da_zona(zone_ff, pak_dir, pak_pref, zone_name):
    """{(alias, n): sinal 4 kHz} para todos os sons da zona (stream/primed/loaded)."""
    body = ff_unpack.unpack(zone_ff)[2]
    out = {}
    for r in zone_sounds.scan(body, lambda r: catalog.stream_ok(pak_dir, pak_pref, r)):
        try:
            if r['kind'] in ('stream', 'primed'):
                sig = flac_bytes_to(ler_pak(os.path.join(pak_dir, f"{pak_pref}soundfile{r['pak']}.pak"), r['off'], r['len']))
            else:
                ba = r.get('fmt') or 2
                sig = pcm_to(body[r['data']:r['data'] + r['size']], r['rate'], max(1, ba // 2))
        except Exception as e:
            continue
        if len(sig) >= SR // 4:
            out[(r['alias'], r['n'])] = sig
    return out


def preparar(sig):
    s = sig[:REF_MAX]
    s = s - s.mean()
    return s / (np.sqrt((s ** 2).sum()) + 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('gravacao')
    ap.add_argument('--zona', default='prologue')
    ap.add_argument('--jogo', default='C:/Games/Call of Duty Ghosts')
    ap.add_argument('--backup', default='backup_pc_original')
    ap.add_argument('--catalog', default='work/catalog')
    ap.add_argument('--saida', default=None)
    a = ap.parse_args()

    print('carregando gravação...', flush=True)
    rec, sr = sf.read(a.gravacao, dtype='float32')
    rec = to_sr(rec, sr)
    dur = len(rec) / SR
    print(f'  {dur / 60:.1f} min', flush=True)

    print('montando referências PT (instalado) e EN (backup)...', flush=True)
    pt = refs_da_zona(os.path.join(a.jogo, 'portuguese', f'por_{a.zona}.ff'),
                      os.path.join(a.jogo, 'portuguese'), 'por_', a.zona)
    en = refs_da_zona(os.path.join(a.backup, 'english', f'eng_{a.zona}.ff'),
                      os.path.join(a.backup, 'english'), 'eng_', a.zona)
    mapping = {(x['alias'], x['n']): x for x in json.load(open(os.path.join(a.catalog, 'mapping.json'))) if x['zone'] == a.zona}
    # referências únicas (muitos sons compartilham o mesmo áudio)
    uniq = {}
    chaves = sorted(set(pt) | set(en), key=lambda k: (str(k[0]), k[1]))
    for k in chaves:
        for lang, d in (('PT', pt), ('EN', en)):
            if k in d:
                s = preparar(d[k]); h = hashlib.md5(np.round(s, 4).tobytes()).hexdigest()
                uniq.setdefault(h, [s, []])[1].append((lang, k))
    print(f'  {len(chaves)} sons, {len(uniq)} referências únicas', flush=True)

    # banda de voz e ponderação PHAT
    N = SEG + REF_MAX
    N = 1 << (N - 1).bit_length()
    freqs = np.fft.rfftfreq(N, 1 / SR)
    banda = ((freqs > 150) & (freqs < 1900)).astype(np.float64)
    ref_fft = {h: np.conj(np.fft.rfft(v[0], N)).astype(np.complex64) for h, v in uniq.items()}
    melhor = {h: (0.0, 0.0) for h in uniq}

    starts = list(range(0, max(1, len(rec) - REF_MAX // 2), HOP))
    for si, s0 in enumerate(starts):
        seg = rec[s0:s0 + SEG]
        if len(seg) < SR:
            continue
        X = np.fft.rfft(seg - seg.mean(), N).astype(np.complex64)
        for h, Yc in ref_fft.items():
            G = X * Yc
            G = G / (np.abs(G) + 1e-12) * banda
            c = np.fft.irfft(G, N)[:len(seg)]
            p = int(np.argmax(c)); pk = c[p]
            z = (pk - np.median(c)) / (c.std() + 1e-12)
            if z > melhor[h][0]:
                melhor[h] = (z, (s0 + p) / SR)
        print(f'  segmento {si + 1}/{len(starts)}', flush=True)

    # resultado por som
    linhas = []
    for k in chaves:
        res = {}
        for h, (s, lst) in uniq.items():
            for lang, kk in lst:
                if kk == k:
                    res[lang] = melhor[h]
        zpt, tpt = res.get('PT', (0, 0)); zen, ten = res.get('EN', (0, 0))
        mesmo = any(len({l for l, kk in lst if kk == k}) == 2 for h, (s, lst) in uniq.items())
        if mesmo:
            veredito = 'TOCOU (PT=EN, som sem idioma)' if zpt >= LIMIAR else '-'
        elif zpt >= LIMIAR and zpt >= MARGEM * zen:
            veredito = 'PT-BR'
        elif zen >= LIMIAR and zen >= MARGEM * zpt:
            veredito = 'INGLES'
        elif max(zpt, zen) >= LIMIAR:
            veredito = 'TOCOU (idioma incerto)'
        else:
            veredito = '-'
        x = mapping.get(k, {})
        t = tpt if (veredito.startswith('PT') or (veredito.startswith('TOCOU') and zpt >= zen)) else ten
        linhas.append(dict(alias=k[0], n=k[1], tipo=x.get('pc_kind'), categoria=x.get('cat'), veredito=veredito,
                           tempo=f'{int(t // 60):02d}:{t % 60:05.2f}' if veredito != '-' else '',
                           t=t if veredito != '-' else None, z_pt=round(zpt, 1), z_en=round(zen, 1)))
    det = sorted([l for l in linhas if l['t'] is not None], key=lambda l: l['t'])
    saida = a.saida or os.path.splitext(a.gravacao)[0] + '_relatorio.csv'
    with open(saida, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=[k for k in linhas[0] if k != 't']); w.writeheader()
        for l in det + [l for l in linhas if l['t'] is None]:
            w.writerow({k: v for k, v in l.items() if k != 't'})
    from collections import Counter
    print('\nRESUMO:', dict(Counter(l['veredito'] for l in linhas)))
    print('\nLINHA DO TEMPO (o que tocou):')
    for l in det:
        print(f"  {l['tempo']}  {l['veredito']:30s} {l['alias']}#{l['n']} ({l['tipo']}, {l['categoria']})  zPT={l['z_pt']} zEN={l['z_en']}")
    print('\nrelatório:', saida)


if __name__ == '__main__':
    main()
