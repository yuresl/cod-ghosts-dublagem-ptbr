"""Monta o payload do instalador único (installer/payload) a partir de:
  - work/trad/portuguese      : arquivos da tradução (sem os por_soundfile*.pak, que são cópias do inglês)
  - build/portuguese          : zonas por_*.ff dubladas + por_soundfile*.pak (original + trecho PT acrescentado)
  - build/raiz                : vídeos *_load.bik do PS4
  - backup_pc_original        : jogo original (base para medir/verificar)

Saída:
  payload/portuguese/   arquivos copiados direto para <jogo>\\portuguese
  payload/paks/por_soundfileN.ptbr   trecho PT de cada pak (anexado à cópia do eng_soundfileN.pak)
  payload/bik/<nome>.hdiff           patch HDiffPatch (vídeo PC original -> vídeo PS4)
  payload/manifest.txt               uma linha por arquivo gerado (ver formato abaixo)
  payload/tools/hpatchz.exe          aplicador de patch (MIT)

manifest.txt:
  PAK|N|eng_size|eng_md5|final_size|final_md5|tem_trecho(0/1)
  BIK|nome|orig_size|orig_md5|novo_size|novo_md5
"""
import glob, hashlib, os, shutil, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TRAD = os.path.join(ROOT, 'work', 'trad', 'portuguese')
BUILD = os.path.join(ROOT, 'build')
BK = os.path.join(ROOT, 'backup_pc_original')
OUT = os.path.join(ROOT, 'installer', 'payload')


def md5(p, limit=None):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        left = limit
        while True:
            n = 1 << 24 if left is None else min(1 << 24, left)
            if n == 0:
                break
            b = f.read(n)
            if not b:
                break
            h.update(b)
            if left is not None:
                left -= len(b)
    return h.hexdigest()


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    for d in ('portuguese', 'paks', 'bik', 'tools'):
        os.makedirs(os.path.join(OUT, d))
    man = []

    # 1) arquivos da tradução (menos paks), sobrescritos pelas zonas dubladas
    for p in glob.glob(os.path.join(TRAD, '*')):
        if 'soundfile' in os.path.basename(p):
            continue
        shutil.copy2(p, os.path.join(OUT, 'portuguese'))
    for p in glob.glob(os.path.join(BUILD, 'portuguese', 'por_*.ff')):
        shutil.copy2(p, os.path.join(OUT, 'portuguese'))
    print('portuguese/:', len(os.listdir(os.path.join(OUT, 'portuguese'))), 'arquivos')

    # 2) paks: todos os por_soundfile da tradução (= cópias do inglês) + trecho PT
    for p in sorted(glob.glob(os.path.join(TRAD, 'por_soundfile*.pak')),
                    key=lambda s: int(os.path.basename(s)[13:-4])):
        n = int(os.path.basename(p)[13:-4])
        eng = os.path.join(BK, 'english', f'eng_soundfile{n}.pak')
        es, em = os.path.getsize(eng), md5(eng)
        if es != os.path.getsize(p) or em != md5(p):
            raise SystemExit(f'por_soundfile{n} da tradução não é cópia do inglês')
        built = os.path.join(BUILD, 'portuguese', f'por_soundfile{n}.pak')
        if os.path.exists(built):
            if md5(built, es) != em:
                raise SystemExit(f'pak {n}: prefixo do build difere do inglês')
            with open(built, 'rb') as f, open(os.path.join(OUT, 'paks', f'por_soundfile{n}.ptbr'), 'wb') as o:
                f.seek(es); shutil.copyfileobj(f, o, 1 << 24)
            fs, fm, tail = os.path.getsize(built), md5(built), 1
        else:
            fs, fm, tail = es, em, 0
        man.append(f'PAK|{n}|{es}|{em}|{fs}|{fm}|{tail}')
    print('paks:', len([m for m in man if m.startswith('PAK')]), '| com trecho PT:', sum(m.endswith('|1') for m in man))

    # 3) vídeos: patch HDiffPatch do original do PC para o do PS4
    for p in sorted(glob.glob(os.path.join(BUILD, 'raiz', '*.bik'))):
        nm = os.path.basename(p)
        orig = os.path.join(BK, nm)
        diff = os.path.join(OUT, 'bik', nm[:-4] + '.hdiff')
        subprocess.run(['hdiffz', '-s', '-c-zstd-21-24', '-f', orig, p, diff], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        man.append(f'BIK|{nm}|{os.path.getsize(orig)}|{md5(orig)}|{os.path.getsize(p)}|{md5(p)}')
    print('vídeos:', len([m for m in man if m.startswith('BIK')]))

    hp = shutil.which('hpatchz')
    # o shim do scoop aponta para o exe real
    real = os.path.join(os.path.dirname(os.path.dirname(hp)), 'apps', 'hdiffpatch', 'current', 'hpatchz.exe')
    if not os.path.exists(real):
        real = glob.glob(os.path.expanduser('~/scoop/apps/hdiffpatch/current/**/hpatchz.exe'), recursive=True)[0]
    shutil.copy2(real, os.path.join(OUT, 'tools', 'hpatchz.exe'))
    lic = glob.glob(os.path.expanduser('~/scoop/apps/hdiffpatch/current/**/LICENSE*'), recursive=True)
    if lic:
        shutil.copy2(lic[0], os.path.join(OUT, 'tools', 'HDiffPatch-LICENSE.txt'))

    with open(os.path.join(OUT, 'manifest.txt'), 'w', newline='\r\n') as f:
        f.write('\n'.join(man) + '\n')
    tot = sum(os.path.getsize(os.path.join(dp, fn)) for dp, _, fs in os.walk(OUT) for fn in fs)
    print(f'payload total: {tot / 1e6:.0f} MB')


if __name__ == '__main__':
    main()
