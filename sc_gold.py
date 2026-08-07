#!/usr/bin/env python3
"""
Sol Cesto gold editor (2026 save format).

Gold lives in the IndexedDB object store named 'or' inside the LevelDB
write-ahead log, encoded as a V8 zigzag varint. Because the varint's
length changes with the value, this tool rebuilds the whole log file with
correct block framing and CRC32C checksums instead of patching in place,
so any amount works.

  python sc_gold.py show <leveldb_dir>
  python sc_gold.py set  <leveldb_dir> <amount>

<leveldb_dir> is the folder ending in .indexeddb.leveldb
Quit Sol Cesto completely first.
"""
import sys, os, re, glob, struct, shutil

BLOCK = 32768
STORE = b'\x00\x01\x01\x01\x01\x02\x00o\x00r'      # IndexedDB key for store 'or'

_T = []
for i in range(256):
    c = i
    for _ in range(8):
        c = (c >> 1) ^ (0x82F63B78 if c & 1 else 0)
    _T.append(c)


def crc32c(data):
    crc = 0xFFFFFFFF
    for b in data:
        crc = (crc >> 8) ^ _T[(crc ^ b) & 0xFF]
    return crc ^ 0xFFFFFFFF


def mask(c):
    return (((c >> 15) | (c << 17)) + 0xA282EAD8) & 0xFFFFFFFF


def gv(b, i):
    r = s = 0
    while True:
        x = b[i]; i += 1
        r |= (x & 0x7F) << s
        if not x & 0x80:
            return r, i
        s += 7


def pv(n):
    out = b''
    while True:
        c = n & 0x7F
        n >>= 7
        out += bytes([c | 0x80]) if n else bytes([c])
        if not n:
            return out


def read_batches(buf):
    out = []
    cur = b''
    off = 0
    n = len(buf)
    while off + 7 <= n:
        b = off % BLOCK
        if BLOCK - b < 7:
            off += BLOCK - b
            continue
        ln, ty = struct.unpack_from('<HB', buf, off + 4)
        if ln == 0 and ty == 0:
            off += BLOCK - b
            continue
        p = buf[off + 7:off + 7 + ln]
        off += 7 + ln
        if ty == 1:
            out.append(p)
        elif ty == 2:
            cur = p
        elif ty == 3:
            cur += p
        elif ty == 4:
            out.append(cur + p); cur = b''
        else:
            break
    return out


def write_batches(batches):
    out = bytearray()
    for rec in batches:
        i, left = 0, len(rec)
        first = True
        while True:
            avail = BLOCK - (len(out) % BLOCK)
            if avail < 7:
                out += b'\x00' * avail
                avail = BLOCK
            room = avail - 7
            take = min(room, left)
            last = take == left
            ty = (1 if last else 2) if first else (4 if last else 3)
            chunk = rec[i:i + take]
            out += struct.pack('<IHB', mask(crc32c(bytes([ty]) + chunk)), take, ty) + chunk
            i += take; left -= take; first = False
            if last:
                break
    return bytes(out)


def each_entry(rec):
    """Yield (entry_start, key, value_span) for a write batch."""
    if len(rec) < 12:
        return
    _, cnt = struct.unpack_from('<QI', rec, 0)
    i = 12
    for _ in range(cnt):
        st = i
        t = rec[i]; i += 1
        kl, i = gv(rec, i)
        k = rec[i:i + kl]; i += kl
        if t == 1:
            vl, j = gv(rec, i)
            yield st, k, (j, j + vl)
            i = j + vl
        else:
            yield st, k, None


def current(d):
    hits = []
    for f in sorted(glob.glob(os.path.join(d, '*'))):
        if not re.fullmatch(r'\d+\.log', os.path.basename(f)):
            continue
        for bi, rec in enumerate(read_batches(open(f, 'rb').read())):
            seq = struct.unpack_from('<Q', rec, 0)[0]
            for st, k, sp in each_entry(rec):
                if k == STORE and sp:
                    v = rec[sp[0]:sp[1]]
                    j = v.find(b'\xff\x10')
                    if j < 0:
                        continue
                    tag = v[j + 2]
                    if tag == 0x49:
                        z, _ = gv(v, j + 3)
                        val = (z >> 1) ^ (-(z & 1))
                    elif tag == 0x4E:
                        val = struct.unpack_from('<d', v, j + 3)[0]
                    else:
                        continue
                    hits.append((seq, f, bi, st, sp, v[:j], val))
    hits.sort(key=lambda h: h[0])
    return hits


def main():
    if len(sys.argv) < 3:
        print(__doc__); return
    cmd, d = sys.argv[1], sys.argv[2]
    hits = current(d)
    if not hits:
        raise SystemExit("no 'or' record found in the log - play a bit and quit "
                         "via Save and Quit so the game writes one")

    if cmd == 'show':
        seq, f, bi, st, sp, pre, val = hits[-1]
        print(f'  current gold: {val}   (seq {seq} in {os.path.basename(f)})')
        if len(hits) > 1:
            print(f'  ({len(hits)} historical writes; newest wins)')
        return

    if cmd != 'set':
        print(__doc__); return

    amount = int(sys.argv[3])
    if amount < 0:
        raise SystemExit('amount must be >= 0')
    seq, f, bi, st, sp, pre, val = hits[-1]

    bak = d.rstrip('\\/') + '.goldbak'
    if not os.path.exists(bak):
        shutil.copytree(d, bak)
        print(f'backup: {bak}')

    batches = read_batches(open(f, 'rb').read())
    rec = bytearray(batches[bi])
    newv = pre + b'\xff\x10\x49' + pv((amount << 1) ^ (amount >> 63))
    s, e = sp
    head = rec[:s]
    # rewrite the value-length varint that precedes the value
    kend = s
    while True:
        kend -= 1
        try:
            l, j = gv(rec, kend)
        except Exception:
            continue
        if j == s and l == e - s:
            break
    rec = bytes(rec[:kend]) + pv(len(newv)) + newv + bytes(rec[e:])
    batches[bi] = rec
    open(f, 'wb').write(write_batches(batches))
    print(f'  {val} -> {amount}   ({os.path.basename(f)})')
    after = current(d)
    print(f'  verified: {after[-1][6]}')


if __name__ == '__main__':
    main()
