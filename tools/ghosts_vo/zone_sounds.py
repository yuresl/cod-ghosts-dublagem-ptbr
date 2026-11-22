"""Lista os sons (streamed e loaded) de uma zona IW6 descomprimida, na ordem da zona,
cada um associado ao alias que o precede.

Layouts descobertos empiricamente (validar com REA):
  SoundFile streamed (PC 0x235 / PS4 0x231):
    02 01 00*6 | u8 isLocalized, pad | u16 fileIndex | u32 flags | u64 offset | u64 length | u32 msec
  LoadedSound PS4 (MP3, fmt=2):
    ptr(-1) | u64 size | ptr(-1) | u32 rate | u32 size | u32 samples | u32 0 |
    u16 ch | u16 bits | u16 fmt | u16 ? | u32 frames | pad4 | ptr(-1) | name\0 | data[size]
  LoadedSound PC (PCM):
    ptr(-1) | ptr(-2) | u64 0 | u32 ? | u32 size | u32 samples | u32 ? |
    u16 ch | u16 bits | u16 fmt | u16 ? | u32 size | pad4 | name\0 | data[size]
  SoundFile primed (tipo 3): stream no .pak + início pré-carregado na zona
    03 01 00*6 | u8 loc, pad | u16 fileIndex | u32 flags | u64 offset | u64 length |
    ptr(-1) | u32 hdr | u32 total | u32 hash | pad4 | LoadedSound do início:
      PC : ptr(-1) | ptr(-2) | u64 0 | u32 rate | u32 fsiz | u32 samples | u32 0 |
           u16 ch | u16 bits | u16 blocksize | u16 ? | u32 prime | pad4 | nome\0 | prime bytes
           (prime = cópia dos primeiros bytes de frames do FLAC, a partir de offset+hdr)
      PS4: ptr(-1) | u64 prime | ptr(-1) | u32 rate | u32 size | u32 samples | u32 0 |
           u16 ch | u16 bits | u16 fmt | u16 ? | u32 frames | pad4 | ptr(-1) | nome\0 | prime bytes
"""
import re, struct, sys, json

INL = b'\xff\xff\xff\xff\xff\xfd\xfd\xfd'
STREAM = re.compile(rb'\x02\x01\x00\x00\x00\x00\x00\x00[\x00\x01]\x00', re.S)
PRIMED = re.compile(rb'\x03\x01\x00\x00\x00\x00\x00\x00[\x00\x01]\x00.{22}' + re.escape(INL), re.S)
NEG2 = b'\xfe\xff\xff\xff\xff\xfd\xfd\xfd'
PS4_LOADED = re.compile(re.escape(INL) + rb'(.{8})' + re.escape(INL) + rb'(.{4})(.{4})', re.S)
PC_LOADED = re.compile(re.escape(INL) + re.escape(b'\xfe\xff\xff\xff\xff\xfd\xfd\xfd') + rb'\x00{8}', re.S)
ALIAS = re.compile(rb'(?<=[\x00\xfd])([a-z][a-z0-9_]{4,})\x00')
ALIAS_LIST = re.compile(re.escape(INL) + re.escape(INL) + rb'(.{4})\x00\x00\x00\x00([A-Za-z0-9_][A-Za-z0-9_\-.]{1,})\x00', re.S)
RATES = {8000, 11025, 16000, 22050, 24000, 32000, 36000, 44100, 48000}


def cstr(z, i):
    j = z.index(b'\x00', i)
    return z[i:j].decode('latin-1'), j + 1


def scan(z, valid=None):
    """valid(rec) -> bool: confere se a ref streamed aponta para um stream real (os offsets
    NÃO são necessariamente alinhados; a validação é feita pelo conteúdo do .pak)."""
    recs = []
    for m in STREAM.finditer(z):
        i = m.start()
        loc, idx, flags, off, ln, ms = struct.unpack_from('<BxHIQQI', z, i + 8)
        if 0 < ln < 200_000_000 and 0 < idx < 100 and ms < 3_600_000:
            r = dict(pos=i, kind='stream', loc=loc, pak=idx, off=off, len=ln, ms=ms)
            if valid is None or valid(r):
                recs.append(r)
    for m in PRIMED.finditer(z):
        i = m.start()
        loc, idx, flags, off, ln = struct.unpack_from('<BxHIQQ', z, i + 8)
        hdr, total, hsh = struct.unpack_from('<III', z, i + 40)
        L = i + 56
        if not (0 < ln < 200_000_000 and 0 < idx < 100 and z[L:L + 8] == INL):
            continue
        if z[L + 8:L + 16] == NEG2:                         # PC
            rate, fsiz, samples, _, ch, bits, bs, x, prime = struct.unpack_from('<IIIIHHHHI', z, L + 24)
            name, d = cstr(z, L + 56)
            side = 'pc'
        else:                                               # PS4
            prime = struct.unpack_from('<Q', z, L + 8)[0]
            rate, fsiz, samples, _, ch, bits, bs, x, frames = struct.unpack_from('<IIIIHHHHI', z, L + 24)
            name, d = cstr(z, L + 64)
            side = 'ps4'
        if rate not in RATES or not 0 < prime < 50_000_000:
            continue
        r = dict(pos=i, kind='primed', side=side, loc=loc, pak=idx, off=off, len=ln, hdr=hdr,
                 total=total, ls=L, rate=rate, fsiz=fsiz, samples=samples, ch=ch, name=name,
                 data=d, prime=prime, ms=round(samples / rate * 1000))
        if valid is None or valid(r):
            recs.append(r)
    for m in PS4_LOADED.finditer(z):
        i = m.start()
        size = struct.unpack('<Q', m.group(1))[0]
        rate, size2 = struct.unpack('<II', m.group(2) + m.group(3))
        if rate not in RATES or size != size2 or not 0 < size < 50_000_000:
            continue
        samples, _, ch, bits, fmt, x, frames = struct.unpack_from('<IIHHHHI', z, i + 32)
        name, d = cstr(z, i + 64)
        recs.append(dict(pos=i, kind='loaded', fmt=fmt, rate=rate, ch=ch, bits=bits,
                         samples=samples, frames=frames, name=name, data=d, size=size))
    for m in PC_LOADED.finditer(z):
        i = m.start()
        a, size, samples, b, ch, bits, fmt, x, size2 = struct.unpack_from('<IIIIHHHHI', z, i + 24)
        if size != size2 or not 0 < size < 50_000_000:
            continue
        name, d = cstr(z, i + 56)
        recs.append(dict(pos=i, kind='loaded', fmt=fmt, rate=a, rate2=b, ch=ch, bits=bits,
                         samples=samples, name=name, data=d, size=size))
    recs.sort(key=lambda r: r['pos'])
    # alias = cabeçalho snd_alias_list_t mais recente: ptr(-1) | ptr(-1) | u32 count | pad | nome\0
    heads = [(m.start(), m.group(2).decode(), struct.unpack('<I', m.group(1))[0])
             for m in ALIAS_LIST.finditer(z)
             if 0 < struct.unpack('<I', m.group(1))[0] <= 512]
    hi = -1
    for r in recs:
        while hi + 1 < len(heads) and heads[hi + 1][0] < r['pos']:
            hi += 1
        r['alias'], r['list_pos'], r['list_count'] = (heads[hi][1], heads[hi][0], heads[hi][2]) if hi >= 0 else (None, None, None)
    seen = {}
    for r in recs:
        k = r['list_pos']
        seen[k] = seen.get(k, -1) + 1
        r['n'] = seen[k]
    return recs


def list_consistency(recs):
    """Quantas listas têm exatamente `count` sons (sanidade do parser)."""
    from collections import Counter
    per = Counter(r['list_pos'] for r in recs)
    cnt = {r['list_pos']: r['list_count'] for r in recs}
    return Counter('igual' if per[k] == cnt[k] else ('menos' if per[k] < cnt[k] else 'mais') for k in per)


if __name__ == '__main__':
    z = open(sys.argv[1], 'rb').read()
    recs = scan(z)
    if len(sys.argv) > 2:
        json.dump(recs, open(sys.argv[2], 'w'), indent=0)
    from collections import Counter
    print(sys.argv[1], 'total', len(recs), Counter((r['kind'], r.get('fmt')) for r in recs))
