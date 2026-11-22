"""Libera todas as missões da campanha na tela "Selec. Missão" do CoD Ghosts (PC).

O perfil players2\\settings_s.zip.iw6 (formato "SEMV", sem checksum) guarda, no campo 0x29, uma string
com um dígito por missão ('0' = não concluída; '1'..'4' = concluída na dificuldade). Este script marca
as N primeiras missões como concluídas e guarda uma cópia do original em *.antes_desbloqueio.

Uso:  python desbloquear_missoes.py ["C:\\Games\\Call of Duty Ghosts"] [--restaurar]
"""
import os, shutil, sys

N_MISSOES = 20
DIFICULDADE = b'2'


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    jogo = args[0] if args else r'C:\Games\Call of Duty Ghosts'
    perfil = os.path.join(jogo, 'players2', 'settings_s.zip.iw6')
    bak = perfil + '.antes_desbloqueio'
    if '--restaurar' in sys.argv:
        shutil.copyfile(bak, perfil); print('perfil restaurado'); return
    d = bytearray(open(perfil, 'rb').read())
    assert d[:4] == b'SEMV', 'formato de perfil inesperado'
    i = d.find(b'\x29\x06')
    s = next(k for k in range(i + 2, i + 16) if d[k:k + 1] in b'01234')
    e = d.index(b'\x00', s)
    print('antes :', d[s:e].decode())
    if not os.path.exists(bak):
        shutil.copyfile(perfil, bak)
    for k in range(min(N_MISSOES, e - s)):
        if d[s + k:s + k + 1] == b'0':
            d[s + k] = DIFICULDADE[0]
    open(perfil, 'wb').write(d)
    print('depois:', d[s:e].decode())


if __name__ == '__main__':
    main()
