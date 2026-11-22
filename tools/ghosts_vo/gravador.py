"""Grava o áudio de SAÍDA do Windows (loopback WASAPI do dispositivo padrão) em FLAC.

Uso:  python gravador.py [pasta_saida]
Para parar: Ctrl+C nesta janela (ou crie um arquivo chamado PARAR na pasta de saída).
"""
import datetime, os, sys, time, warnings
import numpy as np
import soundcard as sc
import soundfile as sf

RATE = 48000
BLOCO = RATE // 2                      # 0,5 s por leitura

warnings.filterwarnings('ignore', category=sc.SoundcardRuntimeWarning)  # "data discontinuity" em silêncio


def main():
    pasta = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', '..', 'gravacoes')
    pasta = os.path.abspath(pasta); os.makedirs(pasta, exist_ok=True)
    parar = os.path.join(pasta, 'PARAR')
    if os.path.exists(parar):
        os.remove(parar)
    sp = sc.default_speaker()
    mic = sc.get_microphone(sp.id, include_loopback=True)
    nome = os.path.join(pasta, 'sessao_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '.flac')
    print(f'Gravando a saída: {sp.name}')
    print(f'Arquivo: {nome}')
    print('Pare com Ctrl+C (ou criando o arquivo PARAR nessa pasta).\n')
    t0 = time.time(); ultimo = 0; picos = []
    with sf.SoundFile(nome, 'w', samplerate=RATE, channels=2, subtype='PCM_16', format='FLAC') as out, \
            mic.recorder(samplerate=RATE, channels=2, blocksize=1024) as rec:
        try:
            while not os.path.exists(parar):
                d = rec.record(numframes=BLOCO)
                if d.ndim == 1:
                    d = np.stack([d, d], axis=1)
                out.write(np.clip(d[:, :2], -1, 1))
                picos.append(float(np.abs(d).max()) if d.size else 0.0)
                el = time.time() - t0
                if el - ultimo >= 5:
                    p = max(picos) if picos else 0; picos = []
                    db = 20 * np.log10(p) if p > 0 else -99
                    barra = '#' * max(0, int((db + 60) / 2))
                    print(f'{int(el // 60):02d}:{int(el % 60):02d}  nível {db:6.1f} dBFS  {barra}', flush=True)
                    ultimo = el
        except KeyboardInterrupt:
            pass
    print(f'\nGravação encerrada ({(time.time() - t0) / 60:.1f} min): {nome}')


if __name__ == '__main__':
    main()
