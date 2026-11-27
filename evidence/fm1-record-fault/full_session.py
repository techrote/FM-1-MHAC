#!/usr/bin/env python3
"""Run the pinned upstream loader and transport against synthetic NOR and host data.
No flashable outputs, upstream redistribution or physical-device access.
HOLD witnesses are expected falsifiers, not installation acceptance.
"""
import hashlib
from pathlib import Path
import subprocess as sp
import sys
import tempfile

PIN = "92f17b28f2d05f2f78fd1b160b58475d518902c8"
BLOBS = {
    "tests/ldr_test.c": "3bce220ae0a856f63a327a3890291266ecda54a4",
    "firmware/src/ota.c": "70996a9c15560ce8fa318d335e3a057791aa2e63",
    "firmware/loader/ldr_core.c": "8ed638bef7945756adbbbffa5b82ff99cb98adfd",
}
PATCHES = [
    ('static uint32_t corrupt_at, corrupt_once, no_finish;',
     'static uint32_t fault_off, fault_kind, fault_fired, bad_finish;\nstatic uint32_t corrupt_at, corrupt_once, no_finish;'),
    ('memcpy(m + 14, "success", 8);',
     'memcpy(m + 14, bad_finish ? "failure" : "success", 8);'),
    ('static int ldr_fread(uint32_t off, void *p, uint32_t n) { memcpy(p, nor + off, n); return 0; }',
     """static int ldr_fread(uint32_t off, void *p, uint32_t n) {
         if (off > sizeof nor || n > sizeof nor - off) abort();
         if (fault_kind == 1 && off == fault_off && n == 4096 && !fault_fired++) return -1;
         memcpy(p, nor + off, n); return 0;
     }"""),
    ('erases++;\n    memset(nor + off, 0xFF, 0x1000);',
     """erases++;
    if (off >= sizeof nor || (off & 4095)) abort();
    if (fault_kind == 2 && off == fault_off && !fault_fired++) return -1;
    if (fault_kind == 3 && off == fault_off && !fault_fired++) {
        memset(nor + off, 0xFF, 64); return -1;
    }
    memset(nor + off, 0xFF, 0x1000);"""),
    ('for (i = 0; i < n; i++) nor[off + i] &= s[i];',
     """if (off > sizeof nor || n > sizeof nor - off) abort();
    if (fault_kind == 4 && off == fault_off && !fault_fired++) {
        for (i = 0; i < n / 2; i++) nor[off + i] &= s[i];
        return -1;
    }
    for (i = 0; i < n; i++) nor[off + i] &= s[i];"""),
    ('int main(int argc, char **argv)', 'int upstream_main(int argc, char **argv)'),
]

EXTENSION = r"""
/* Synthetic host-only image. Does not invoke SPL or physical flash controller. */
#define F_OFF 0x400u
#define CHANGE 0x5000u
#define STORE 0x97000u
static uint8_t image[F_OFF + T_APP_HI], before[sizeof nor];
static unsigned assertions;
static void need(int ok, const char *why) {
    if (!ok) { fprintf(stderr, "FAIL %s\n", why); exit(1); }
    assertions++;
}
static void reset_case(void) {
    uint8_t *f = image + F_OFF, *e = f + 32, *b = f + 0x200;
    uint32_t key = 0;
    memset(image, 0, sizeof image);
    ota_wr32(e + 4, 0x200u);
    memcpy(e + 16, "isd_config.ini", 15);
    ota_wr16(e, ota_crc16(e + 2, 30, 0));
    ota_jl_enc(e, 32);
    ota_wr16(b + 32, ota_crc16(b, 32, 0));
    memset(nor, 0xFF, sizeof nor);
    memcpy(nor, f, 0x4000);
    need(ldr_chip_key(&key) == 0, "synthetic head parsed");
    ota_wr16(f + 0x4000, ota_crc16(f + 0x4002, 30, 0));
    ldr_sfc(f + 0x4000, 32, 0, key);
    memset(f + CHANGE, 0x39, 4096);
    memcpy(nor + 0x4000, f + 0x4000, T_APP_HI - 0x4000);
    memset(nor + CHANGE, 0xA5, 4096);
    memset(nor + STORE, 0xC3, 4096);
    put_record();
    memcpy(before, nor, sizeof nor);
    e = image + 0x40;
    ota_wr16(e + 4, ota_crc16(f, T_APP_HI, 0));
    ota_wr32(e + 8, F_OFF);
    ota_wr32(e + 12, T_APP_HI);
    ota_jl_enc(e, 0x50);
    ota_wr16(image + 2, ota_crc16(e, 0x50, 0));
    ota_wr16(image + 8, 1);
    ota_wr16(image, ota_crc16(image + 2, 0x3E, 0));
    ota_jl_enc(image, 0x40);
    logical = image; logical_len = sizeof image;
    rx_full = now_ms = requests = erases = bad_range = record_cleared = f0_asked = 0;
    corrupt_at = corrupt_once = no_finish = flash_unknown = 0;
    fault_kind = fault_off = fault_fired = bad_finish = 0;
}
static int app_equal(void) {
    return !memcmp(nor + 0x4000, image + F_OFF + 0x4000, T_APP_HI - 0x4000);
}
static int staging_record(void) {
    const uint8_t *p = nor + T_REC;
    return ota_rd16(p + 6) == 0x5441 && ota_rd16(p) &&
           ota_rd16(p) == ota_crc16(p + 2, 78, 0);
}
static void protected_equal(void) {
    need(!memcmp(nor, before, 0x4000), "head intact");
    need(!memcmp(nor + STORE, before + STORE, 4096), "store intact");
    need(!memcmp(nor + T_ERASE_HI, before + T_ERASE_HI,
                sizeof nor - T_ERASE_HI), "tail intact");
    need(bad_range == 0, "no out-of-window access");
}
static void completed(void) {
    need(app_equal(), "new app bytes match");
    need(!staging_record() && record_cleared, "record cleared");
    protected_equal();
}
static void retry_fault(unsigned kind, uint32_t off, int expect) {
    reset_case(); fault_kind = kind; fault_off = off;
    need(ldr_session() == expect, "fault propagated");
    need(fault_fired > 0, "fault reached");
    need(staging_record() && !record_cleared, "recovery marker retained");
    need(!app_equal(), "old or partial app, not complete");
    protected_equal();
    fault_kind = 0;
    need(ldr_session() == 0, "explicit host retry succeeded");
    completed();
    printf("fault kind=%u offset=%#x: marker retained; explicit retry PASS\n", kind, off);
}
int main(void) {
    reset_case();
    need(ldr_session() == 0, "baseline full session");
    completed();
    retry_fault(1, CHANGE, -8);
    retry_fault(2, CHANGE, -9);
    retry_fault(3, CHANGE, -9);
    retry_fault(4, CHANGE, -10);
    retry_fault(4, CHANGE + 15 * 256, -10);
    reset_case(); no_finish = 1;
    need(ldr_session() == LDR_ENOFIN, "missing finish rejected");
    need(app_equal() && staging_record() && !record_cleared, "app written; marker retained");
    protected_equal();
    no_finish = 0;
    need(ldr_session() == 0, "explicit finish retry"); completed();
    puts("missing finish: app already written; marker retained");
    reset_case(); corrupt_at = F_OFF + CHANGE + 123; corrupt_once = 0;
    need(ldr_session() == LDR_EBADPKG, "persistent transport CRC failure");
    need(!app_equal() && staging_record() && !record_cleared, "corrupt app written; marker retained");
    protected_equal();
    corrupt_at = 0;
    need(ldr_session() == 0, "explicit clean retry"); completed();
    puts("persistent CRC failure: marker retained, corrupted app bytes observed");
    reset_case(); bad_finish = 1;
    need(ldr_session() == 0, "non-success payload accepted by pinned loader");
    completed();
    puts("HOLD: matching transport reply containing failure accepted as finish");
    reset_case(); fault_kind = 2; fault_off = T_REC & ~4095u;
    need(ldr_session() == 0, "cleanup erase failure hidden");
    need(app_equal() && staging_record() && record_cleared, "success with persistent record");
    protected_equal();
    puts("HOLD: successful return with valid flash recovery marker still present");
    reset_case(); put_record_at(STORE + 0xF00);
    need(ldr_session() == 0, "record collision full session");
    need(nor[STORE] == 0xFF && nor[STORE + 0xF00] == 0xFF, "store sector erased");
    need(app_equal() && !staging_record(), "app complete despite store loss");
    need(!memcmp(nor, before, 0x4000) && bad_range == 0, "head and range checks");
    puts("HOLD: synthetic record collision erased user-store sector during full session");
    printf("PASS %u host assertions; HOLD physical boot, installation, recovery\n", assertions);
    return 0;
}
"""

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def instrument(source):
    for old, new in PATCHES:
        if source.count(old) != 1:
            raise ValueError("unexpected anchor count: " + old[:80])
        source = source.replace(old, new, 1)
    return source + "\n" + EXTENSION

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: full_session.py PINNED_DINGHY_CHECKOUT")
    root = Path(sys.argv[1]).resolve()
    got = sp.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if got != PIN:
        raise SystemExit("wrong checkout revision: " + got)
    with tempfile.TemporaryDirectory(prefix="fm1-session-") as tmp:
        work = Path(tmp)
        for name, expected in BLOBS.items():
            data = (root / name).read_bytes()
            if blob(data) != expected:
                raise SystemExit("wrong source identity: " + name)
            target = work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data if name != "tests/ldr_test.c" else instrument(data.decode()).encode())
            print("verified", name, expected, flush=True)
        outputs = []
        for cc in ("gcc", "clang"):
            exe = work / cc
            sp.run([cc, "--version"], check=True)
            sp.run([cc, "-std=c11", "-O2", "-DBOARD_SMK37=0", "-fsanitize=undefined",
                    "-fno-sanitize-recover=all", str(work / "tests/ldr_test.c"), "-o", str(exe)], check=True)
            output = sp.check_output([str(exe)], text=True, timeout=90)
            print(cc, output, sep="\n", flush=True)
            outputs.append(output)
        if outputs[0] != outputs[1]:
            raise SystemExit("compiler transcript mismatch")
        print("identical native transcripts; no physical installation authorization")
if __name__ == "__main__":
    main()
