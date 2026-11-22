"""Retrato MD5 de uma pasta de jogo (portuguese/*, *.bik, english/*) para comparar antes/depois."""
import hashlib, json, os, sys


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest()


def snap(root):
    out = {}
    for sub in ('', 'portuguese', 'english'):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            p = os.path.join(d, n)
            if os.path.isfile(p) and (sub or n.endswith('.bik')):
                out[os.path.join(sub, n).replace('\\', '/')] = md5(p)
    return out


if __name__ == '__main__':
    root, dst = sys.argv[1], sys.argv[2]
    s = snap(root)
    json.dump(s, open(dst, 'w'), indent=0, sort_keys=True)
    print(len(s), 'arquivos ->', dst)
