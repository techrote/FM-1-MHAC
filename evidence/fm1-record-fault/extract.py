"""Extract exact pinned cleanup code from a separately obtained upstream checkout.
No network, device access or upstream redistribution. Run from harness directory.
"""
import hashlib
import pathlib
import re
import sys

PIN = '92f17b28f2d05f2f78fd1b160b58475d518902c8'

def read(root, name, expected):
    data = (root / name).read_bytes()
    blob = hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()
    if blob != expected:
        raise ValueError(f'{name}: unexpected git blob {blob}; require {PIN}')
    return data.decode('utf-8')

def select(src, pattern):
    matches = re.findall(pattern, src, re.M | re.S)
    if len(matches) != 1:
        raise ValueError(f'expected exactly one match: {pattern}')
    return matches[0]

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: python extract.py /path/to/pinned/dinghy')
    root = pathlib.Path(sys.argv[1])
    ota = read(root, 'firmware/src/ota.c', '70996a9c15560ce8fa318d335e3a057791aa2e63')
    core = read(root, 'firmware/loader/ldr_core.c', '8ed638bef7945756adbbbffa5b82ff99cb98adfd')
    parts = [select(ota, r'^static uint32_t ota_rd16\([^\n]+$'),
             select(ota, r'^static uint32_t ota_crc16\([^\n]+\n\{.*?^\}'),
             select(core, r'^#define LDR_REC_LO 0x93000u[^\n]+$'),
             select(core, r'^#define LDR_REC_HI 0xFC000u[^\n]+$'),
             select(core, r'^static void ldr_records_drop\(void\)\n\{.*?^\}')]
    data = ('\n'.join(parts) + '\n').encode()
    digest = hashlib.sha256(data).hexdigest()
    if digest != '821e353b5a5569aca96a4f74d4d42f4388f006c4f11e269eccd90bfef464eb21':
        raise ValueError(f'excerpt hash mismatch: {digest}')
    pathlib.Path('fm1_record_core.inc').write_bytes(data)
    print('Verified upstream blobs and extracted code:', digest)
