"""Lê zonas IW6 (.ff).

Cabeçalho:
  0x00 'IWffu100' | 0x08 u32 versão (PC 0x235, PS4 0x231) | 0x0C flags | 0x10 8 bytes
  0x18 u32 N (entradas de streaming de imagem) | N * 24 bytes | u64 tamanho | u64 tamanho | corpo
Corpo: PC = zlib; PS4 = cru.
"""
import sys, zlib, struct, os

ZLIB = (b'\x78\xda', b'\x78\x9c', b'\x78\x01')


def header_len(d):
    n = struct.unpack_from('<I', d, 0x18)[0]
    return 0x1C + n * 24 + 16


def unpack(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'IWffu100', d[:8]
    ver = struct.unpack('<I', d[8:12])[0]
    hl = header_len(d)
    body = d[hl:]
    if body[:2] in ZLIB:
        out = bytearray(); dec = zlib.decompressobj()
        out += dec.decompress(body); rest = dec.unused_data
        while rest[:2] in ZLIB:
            dec = zlib.decompressobj(); out += dec.decompress(rest); rest = dec.unused_data
        return ver, 'zlib', bytes(out), len(rest)
    return ver, 'raw', body, 0


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    ver, kind, data, left = unpack(src)
    open(dst, 'wb').write(data)
    print(os.path.basename(src), hex(ver), kind, len(data), 'sobra', left)
