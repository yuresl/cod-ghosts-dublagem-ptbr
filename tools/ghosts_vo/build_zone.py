"""Gera a versão PT-BR (VO do PS4) de uma zona do PC e acrescenta o áudio nos por_soundfileN.pak.

Uso:
  python -I build_zone.py <zona> [<zona> ...] --game <pasta_jogo> --backup <backup_pc_original>
                          --ps4 <ps4_extract/uroot> --catalog <work/catalog> --out <build> --tmp <work/tmp>

Estratégia (não destrutiva para as outras missões):
  * por_soundfileN.pak: parte da cópia original (backup) e só ACRESCENTA streams novos no fim
    (alinhados em 2048). Os offsets antigos continuam válidos para as outras zonas.
  * zona por_<zona>.ff: mesmas estruturas, campos fixos alterados in-place (offset/len/ms dos
    streams; PCM e taxa dos loaded sem mudar o tamanho), recomprimida com zlib.
"""
import argparse, json, os, shutil, struct, subprocess, sys, zlib, hashlib
sys.path.insert(0, os.path.dirname(__file__))
import ff_unpack, zone_sounds

FFMPEG = 'ffmpeg'
FLAC = 'flac'
ALIGN = 2048
VENDOR = b'reference libFLAC 1.2.1 20070917'


# ---------------------------------------------------------------- áudio
def decode_to_pcm(src_bytes, rate, tmp, tag, ch=1):
    """MP3 (bytes) -> PCM s16le (mono ou estéreo, intercalado) na taxa pedida."""
    src = os.path.join(tmp, tag + '.mp3')
    open(src, 'wb').write(src_bytes)
    out = subprocess.run([FFMPEG, '-hide_banner', '-v', 'error', '-i', src, '-ac', str(ch), '-ar', str(rate),
                          '-af', 'aresample=resampler=soxr', '-f', 's16le', '-'],
                         capture_output=True, check=True).stdout
    os.remove(src)
    return out


def flac_blocks(data):
    assert data[:4] == b'fLaC'
    i, blocks = 4, []
    while True:
        h = data[i]; t = h & 0x7f; L = int.from_bytes(data[i + 1:i + 4], 'big')
        blocks.append((t, data[i + 4:i + 4 + L]))
        i += 4 + L
        if h >> 7:
            return blocks, data[i:]


def blk(t, body, last):
    return bytes([(0x80 if last else 0) | t]) + len(body).to_bytes(3, 'big') + body


def flac_header_len(fl):
    return len(fl) - len(flac_blocks(fl)[1])


def encode_flac_pc(pcm, rate, tmp, tag, level='-8', ch=1):
    """PCM -> FLAC no layout do PC: STREAMINFO, VORBIS_COMMENT(libFLAC 1.2.1), APPLICATION fsiz, SEEKTABLE."""
    raw = os.path.join(tmp, tag + '.raw'); out = os.path.join(tmp, tag + '.flac')
    open(raw, 'wb').write(pcm)
    subprocess.run([FLAC, '-s', '-f', level, '--blocksize=1024', '--no-padding', '-S', '16384s',
                    '--force-raw-format', '--endian=little', '--sign=signed', f'--channels={ch}',
                    '--bps=16', f'--sample-rate={rate}', '-o', out, raw], check=True)
    data = open(out, 'rb').read()
    os.remove(raw); os.remove(out)
    blocks, frames = flac_blocks(data)
    d = dict(blocks)
    streaminfo, seek = d[0], d.get(3, b'')
    # remove placeholders vazios da seektable (sample number 0xFFFFFFFFFFFFFFFF)
    pts = [seek[k:k + 18] for k in range(0, len(seek), 18)]
    pts = b''.join(p for p in pts if p[:8] != b'\xff' * 8)
    vorbis = struct.pack('<I', len(VENDOR)) + VENDOR + struct.pack('<I', 0)
    app = b'fsiz' + struct.pack('<I', len(frames))
    hdr = b'fLaC' + blk(0, streaminfo, False) + blk(4, vorbis, False) + blk(2, app, not pts)
    if pts:
        hdr += blk(3, pts, True)
    return hdr + frames


def flac_rate(pak_bytes_at_off):
    b = pak_bytes_at_off[8:42]
    return (b[10] << 12) | (b[11] << 4) | (b[12] >> 4)


# ---------------------------------------------------------------- zona
def pack_zone(raw, body):
    """Recomprime o corpo mantendo o cabeçalho original (tamanho variável) e atualiza os campos
    de tamanho. Completa com zeros até o tamanho original, como a tradução fez."""
    hl = ff_unpack.header_len(raw)
    f1, f2 = struct.unpack_from('<QQ', raw, hl - 16)
    comp = zlib.compress(body, 9)
    data = bytearray(raw[:hl]) + comp
    size = max(len(data), len(raw))
    struct.pack_into('<Q', data, hl - 16, size if f1 == len(raw) else f1)
    struct.pack_into('<Q', data, hl - 8, size if f2 == len(raw) else f2)
    data += bytes(size - len(data))
    return bytes(data)


def _dither(pcm, seconds_pad, rate):
    """Soma ruído de ±1 LSB (inaudível, ~-90 dBFS) e acrescenta silêncio com o mesmo ruído:
    usado só para o FLAC ficar com pelo menos o tamanho do trecho primed da zona."""
    import array, random
    a = array.array('h'); a.frombytes(pcm)
    a.extend([0] * int(seconds_pad * rate))
    rnd = random.Random(1234)
    for k in range(len(a)):
        a[k] = max(-32768, min(32767, a[k] + rnd.choice((-1, 0, 1))))
    return a.tobytes()


def _encode_job(args):
    src, rate, tmp, tag, min_frames, ch = args
    pcm = decode_to_pcm(src, rate, tmp, tag, ch)
    fl = encode_flac_pc(pcm, rate, tmp, tag, ch=ch)
    pad, extra = 0.0, None
    # primed: os frames precisam ter pelo menos `min_frames` bytes (tamanho fixo do buffer na zona)
    if min_frames and len(fl) - flac_header_len(fl) < min_frames:
        fl = encode_flac_pc(pcm, rate, tmp, tag, '-0', ch); extra = '-0'
        while len(fl) - flac_header_len(fl) < min_frames:
            p2 = _dither(pcm, pad, rate * ch)
            fl = encode_flac_pc(p2, rate, tmp, tag, '-0', ch)
            extra = f'-0+dither+{pad:.1f}s'
            pad += 0.5
            if len(fl) - flac_header_len(fl) >= min_frames:
                pcm = p2
    return fl, round(len(pcm) / 2 / ch / rate * 1000), len(pcm) // (2 * ch), extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('zones', nargs='*')
    ap.add_argument('--game', required=True); ap.add_argument('--backup', required=True)
    ap.add_argument('--ps4', required=True); ap.add_argument('--catalog', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--tmp', required=True)
    ap.add_argument('--jobs', type=int, default=max(2, (os.cpu_count() or 4) - 2))
    ap.add_argument('--all', action='store_true', help='todas as zonas presentes no mapeamento')
    a = ap.parse_args()
    if a.all:
        a.zones = sorted({x['zone'] for x in json.load(open(os.path.join(a.catalog, 'mapping.json')))})
    os.makedirs(os.path.join(a.out, 'portuguese'), exist_ok=True); os.makedirs(a.tmp, exist_ok=True)

    mapping = json.load(open(os.path.join(a.catalog, 'mapping.json')))
    ps4_zone_cache = {}
    paks = {}                                     # n -> caminho no build (aberto para append)
    report = []

    def out_pak(n):
        if n not in paks:
            dst = os.path.join(a.out, 'portuguese', f'por_soundfile{n}.pak')
            if not os.path.exists(dst):
                shutil.copyfile(os.path.join(a.backup, 'portuguese', f'por_soundfile{n}.pak'), dst)
            paks[n] = dst
        return paks[n]

    def ps4_source(x):
        if x['ps4_kind'] in ('stream', 'primed'):         # primed: o pak tem o MP3 completo
            with open(os.path.join(a.ps4, 'portuguese', f"por_soundfile{x['ps4_pak']}.pak"), 'rb') as f:
                f.seek(x['ps4_off']); return f.read(x['ps4_len'])
        z = x['ps4_zone']
        if z not in ps4_zone_cache:
            ps4_zone_cache[z] = ff_unpack.unpack(os.path.join(a.ps4, 'portuguese', f'por_{z}.ff'))[2]
        return ps4_zone_cache[z][x['ps4_data']:x['ps4_data'] + x['ps4_len']]

    done_streams = {}          # (fonte PS4, pak, taxa) -> (offset, len, ms): reaproveitado entre zonas
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(max_workers=a.jobs)

    def src_key(x):
        return (x['ps4_kind'], x['ps4_zone'], x['ps4_pak'], x['ps4_off'], x['ps4_pos'])

    for zone in a.zones:
        src_ff = os.path.join(a.backup, 'portuguese', f'por_{zone}.ff')
        raw = open(src_ff, 'rb').read()
        ver, kind, body, _ = ff_unpack.unpack(src_ff)
        body = bytearray(body)
        # O mapeamento foi feito sobre eng_<zona>.ff; a por_<zona>.ff da tradução pode ter outro
        # tamanho/posições (e até offsets inválidos, ex.: code_post_gfx). Localiza cada som por (alias, ordem).
        por_recs = zone_sounds.scan(bytes(body))
        by_key = {(r['alias'], r['n']): r for r in por_recs}
        items = [x for x in mapping if x['zone'] == zone]
        miss = [(x['alias'], x['n']) for x in items if (x['alias'], x['n']) not in by_key]
        if miss or len(por_recs) != len(items):
            raise SystemExit(f'{zone}: estrutura da por_ difere da eng_ ({len(por_recs)} x {len(items)} sons, faltando {miss[:5]})')
        recs = {x['pc_pos']: by_key[(x['alias'], x['n'])] for x in items}
        stats = dict(stream=0, primed=0, loaded=0, mantido_ingles=0, reaproveitado=0, primed_engordado=0)

        # 1) streams/primed que ainda não foram convertidos: taxa original e conversão em paralelo
        rate_of = {}
        key_of = {}
        jobs = {}
        for k, x in enumerate(items):
            r = recs.get(x['pc_pos'])
            if r is None or x['how'] == 'sem_par' or r['kind'] not in ('stream', 'primed'):
                continue
            # taxa lida do stream inglês original (pela posição na eng_, sempre válida)
            with open(os.path.join(a.backup, 'english', f"eng_soundfile{x['pc_pak']}.pak"), 'rb') as f:
                f.seek(x['pc_off']); rate = flac_rate(f.read(64))
            if r['pak'] != x['pc_pak']:
                raise SystemExit(f"{zone}: pak divergente para {x['alias']}")
            rate_of[k] = rate
            min_frames = r['prime'] if r['kind'] == 'primed' else 0
            ch = r.get('ch', 1) if r['kind'] == 'primed' else 1
            key = src_key(x) + (ch, r['pak'], rate, min_frames)
            key_of[k] = key
            if key not in done_streams and key not in jobs:
                jobs[key] = (x, rate, f'{zone}_{k}', min_frames, ch)
        keys = list(jobs)
        results = pool.map(lambda key: _encode_job((ps4_source(jobs[key][0]), jobs[key][1], a.tmp,
                                                    jobs[key][2], jobs[key][3], jobs[key][4])), keys)
        for key, (fl, ms, nsamp, extra) in zip(keys, results):          # grava em ordem
            p = out_pak(key[-3])
            with open(p, 'r+b') as f:
                f.seek(0, 2); end = f.tell()
                start = (end + ALIGN - 1) // ALIGN * ALIGN
                f.write(bytes(start - end)); f.write(fl)
            hl = flac_header_len(fl)
            done_streams[key] = dict(off=start, len=len(fl), ms=ms, samples=nsamp, hdr=hl,
                                     fsiz=len(fl) - hl, head=fl[hl:hl + key[-1]] if key[-1] else b'',
                                     extra=extra)

        # 2) aplica na zona
        for k, x in enumerate(items):
            r = recs.get(x['pc_pos'])
            if r is None or x['how'] == 'sem_par':
                stats['mantido_ingles'] += 1; continue
            if r['kind'] in ('stream', 'primed'):
                if k not in key_of:
                    stats['mantido_ingles'] += 1; continue
                rate = rate_of[k]
                key = key_of[k]
                if key not in jobs:
                    stats['reaproveitado'] += 1
                s = done_streams[key]
                i = r['pos']
                if r['kind'] == 'stream':
                    struct.pack_into('<QQI', body, i + 16, s['off'], s['len'], s['ms'])
                else:
                    # primed: stream no pak + cópia dos primeiros `prime` bytes de frames na zona
                    struct.pack_into('<QQ', body, i + 16, s['off'], s['len'])
                    struct.pack_into('<II', body, i + 40, s['hdr'], s['fsiz'])
                    # +48: verificação do conteúdo (hash de algoritmo desconhecido). Se não bater, o jogo
                    # descarta o som (fica mudo); zerado, o jogo não verifica (confirmado em teste no jogo).
                    struct.pack_into('<I', body, i + 48, 0)
                    L = r['ls']
                    struct.pack_into('<III', body, L + 24, rate, s['fsiz'], s['samples'])
                    assert len(s['head']) == r['prime']
                    body[r['data']:r['data'] + r['prime']] = s['head']
                    if s['extra']:
                        stats['primed_engordado'] += 1
                stats[r['kind']] += 1
                report.append(dict(zone=zone, alias=x['alias'], n=x['n'], kind=r['kind'], pak=r['pak'],
                                   off=s['off'], len=s['len'], ms_old=r['ms'], ms_new=s['ms'], rate=rate,
                                   extra=s['extra']))
            else:
                # loaded PCM16: mesmo tamanho de buffer; ajusta a taxa para a fala PT-BR caber
                i, size, ch, ba = r['pos'], r['size'], r['ch'], r.get('fmt') or 2
                if ch not in (1, 2):
                    stats['mantido_ingles'] += 1; continue
                n_frames = size // ba
                pcm = decode_to_pcm(ps4_source(x), 48000, a.tmp, f'{zone}_{k}', ch)
                dur = len(pcm) / 2 / ch / 48000
                rate = r['rate']
                if dur * rate > n_frames:
                    rate = max(16000, int(n_frames / dur))
                pcm = decode_to_pcm(ps4_source(x), rate, a.tmp, f'{zone}_{k}', ch)[:size]
                pcm = pcm + bytes(size - len(pcm))
                body[r['data']:r['data'] + size] = pcm
                struct.pack_into('<I', body, i + 24, rate)
                struct.pack_into('<I', body, i + 36, rate * ba)
                stats['loaded'] += 1
                report.append(dict(zone=zone, alias=x['alias'], n=x['n'], kind='loaded',
                                   rate_old=r['rate'], rate_new=rate, dur_ptbr=round(dur, 3)))
        out_ff = os.path.join(a.out, 'portuguese', f'por_{zone}.ff')
        packed = pack_zone(raw, bytes(body))
        open(out_ff, 'wb').write(packed)
        print(zone, stats, 'zona', len(packed), 'bytes (original', len(raw), ')', flush=True)
    json.dump(report, open(os.path.join(a.out, 'build_report.json'), 'w'), indent=0)
    for n, p in sorted(paks.items()):
        print(f'por_soundfile{n}.pak', os.path.getsize(p), 'bytes')


if __name__ == '__main__':
    main()
