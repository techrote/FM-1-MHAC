#!/usr/bin/env python3
"""Host-only corrective candidate; never builds a flashable image.

Apply original experimental finalization logic to the separately obtained,
identity-checked pinned GPL upstream in a disposable directory. No upstream
files are redistributed. First-stage OTA, SPL, flash hardware, and physical
recovery are explicitly outside this witness. No installation authorization.
"""
from pathlib import Path
import subprocess as sp
import sys
import tempfile
import full_session as base

def one(source, old, new):
    if source.count(old) != 1:
        raise ValueError("anchor count: " + old[:100])
    return source.replace(old, new, 1)

CORE = r"""
#define LDR_EOWNED (-15)
#define LDR_ECLEAN (-16)
/* Only a byte-exact first-stage FM-1 record in its dedicated staging
 * location can be consumed. Any other CRC-valid candidate in the old scan
 * window blocks before app writes. This is not a model of SPL selection. */
static int ldr_owned_record(void)
{
    uint8_t expected[112] = {0}, actual[112];
    uint32_t i, s;
    ota_wr16(expected + 2, 0x5A0Du);
    ota_wr16(expected + 4, 0x5A01u);
    ota_wr16(expected + 6, 0x5441u);
    for (i = 0; i < sizeof OTA_PARM_ID - 1u; ++i)
        expected[8 + i] = (uint8_t)OTA_PARM_ID[i];
    ota_wr32(expected + 72, OTA_AREA);
    ota_wr16(expected, ota_crc16(expected + 2, 78, 0));
    if (ldr_fread(OTA_RES, actual, sizeof actual) ||
        !ota_memeq(expected, actual, sizeof actual))
        return LDR_EOWNED;
    for (s = LDR_REC_HI; s > LDR_REC_LO; s -= 0x1000u) {
        uint32_t at = s - 0x100u;
        if (at == OTA_RES)
            continue;
        if (ldr_fread(at, actual, 80))
            return LDR_EOWNED;
        if (ota_rd16(actual + 6) == 0x5441u && ota_rd16(actual) &&
            ota_rd16(actual) == ota_crc16(actual + 2, 78, 0))
            return LDR_EOWNED;
    }
    return 0;
}
/* Failure after an erase starts can destroy persistent recovery state.
 * Never treat an error or unreadable/partial sector as success. Do not
 * infer that a failed cleanup is automatically retryable after reboot. */
static int ldr_records_drop(void)
{
    uint8_t check[256];
    uint32_t sector = OTA_RES & ~0xFFFu, i, j;
    if (ldr_owned_record())
        return LDR_EOWNED;
    if (ldr_erase(sector))
        return LDR_ECLEAN;
    for (i = 0; i < 0x1000u; i += sizeof check) {
        if (ldr_fread(sector + i, check, sizeof check))
            return LDR_ECLEAN;
        for (j = 0; j < sizeof check; ++j)
            if (check[j] != 0xFFu)
                return LDR_ECLEAN;
    }
    ldr_record_clear();
    return 0;
}
"""

def patch_core(source):
    lo = source.index("static void ldr_records_drop(void)\n{")
    hi = source.index("\nstatic int ldr_pass(void)", lo)
    source = source[:lo] + CORE + source[hi:]
    lo = source.index("    if (!ldr_flash_known()) {")
    hi = source.index("    /* the head of flash.bin", lo)
    source = source[:lo] + """    if (!ldr_flash_known())
        return LDR_EOWNED; /* no writes; avoid existing EFLASH reset branch */
    if (ldr_owned_record())
        return LDR_EOWNED;
""" + source[hi:]
    source = one(source, "if (!ota_read(0xF0000000u, sec, 8))",
                 'if (!ota_read(0xF0000000u, sec, 8) &&\n'
                 '            ota_memeq(sec, (const uint8_t *)"success", 8))')
    return one(source, "    ldr_records_drop();\n    return 0;",
               "    return ldr_records_drop();")

TESTS = r"""
static void no_write(int result, const char *name) {
    memcpy(before, nor, sizeof nor);
    need(ldr_session() == result, name);
    need(!memcmp(nor, before, sizeof nor), "entire flash unchanged");
    need(erases == 0 && !record_cleared, "no erase or RAM clear");
}
static void clean_retry(unsigned kind, int marker_expected) {
    reset_case(); fault_kind = kind; fault_off = T_REC & ~4095u;
    need(ldr_session() == LDR_ECLEAN, "cleanup fault propagated");
    need(app_equal() && !record_cleared, "app complete, no RAM clear");
    need(staging_record() == marker_expected, "persistent record state");
    protected_equal();
    fault_kind = 0;
    if (marker_expected) {
        need(ldr_session() == 0, "explicit retry with valid owned record");
        completed();
    } else {
        need(ldr_session() == LDR_EOWNED, "missing record refuses retry");
        need(!record_cleared, "still no RAM clear");
    }
    printf("cleanup fault %u: marker=%d; explicit retry %s\n",
           kind, marker_expected, marker_expected ? "PASS" : "HOLD");
}
int main(void) {
    uint32_t at = T_REC & ~4095u;
    reset_case();
    need(ldr_session() == 0, "baseline");
    completed();
    for (uint32_t i = 0; i < 4096; ++i)
        need(nor[at + i] == 0xFF, "full staging sector erased");
    retry_fault(1, CHANGE, -8);
    retry_fault(2, CHANGE, -9);
    retry_fault(3, CHANGE, -9);
    retry_fault(4, CHANGE, -10);
    retry_fault(4, CHANGE + 15 * 256, -10);
    reset_case(); no_finish = 1;
    need(ldr_session() == LDR_ENOFIN, "missing completion refused");
    need(app_equal() && staging_record() && !record_cleared, "marker held");
    no_finish = 0; need(ldr_session() == 0, "completion retry"); completed();
    reset_case(); bad_finish = 1;
    need(ldr_session() == LDR_ENOFIN, "wrong completion refused");
    need(f0_asked == 4 && app_equal() && staging_record() && !record_cleared,
         "all wrong replies refused, marker held");
    bad_finish = 0; need(ldr_session() == 0, "correct completion retry"); completed();
    reset_case(); corrupt_at = F_OFF + CHANGE + 123;
    need(ldr_session() == LDR_EBADPKG, "persistent CRC fault");
    need(!app_equal() && staging_record() && !record_cleared, "marker retained");
    corrupt_at = 0; need(ldr_session() == 0, "CRC retry"); completed();
    reset_case(); flash_unknown = 1; no_write(LDR_EOWNED, "unknown flash");
    reset_case(); put_record_at(STORE + 0xF00); no_write(LDR_EOWNED, "store collision");
    reset_case(); put_record_at(T_REC - 4096); no_write(LDR_EOWNED, "second staging record");
    reset_case(); nor[T_REC + 8] ^= 1;
    ota_wr16(nor + T_REC, ota_crc16(nor + T_REC + 2, 78, 0));
    no_write(LDR_EOWNED, "valid CRC but foreign identity");
    reset_case(); nor[T_REC + 72] ^= 1;
    ota_wr16(nor + T_REC, ota_crc16(nor + T_REC + 2, 78, 0));
    no_write(LDR_EOWNED, "valid CRC but foreign stage pointer");
    reset_case(); nor[T_REC + 100] ^= 1;
    no_write(LDR_EOWNED, "noncanonical suffix outside CRC");
    reset_case(); memset(nor + T_REC, 0xFF, 112);
    no_write(LDR_EOWNED, "missing owned record");
    reset_case(); fault_kind = 7; fault_off = STORE + 0xF00;
    no_write(LDR_EOWNED, "scan read failure");
    need(fault_fired > 0, "scan fault reached");
    clean_retry(2, 1); /* erase fails without modification */
    clean_retry(3, 1); /* partial erase outside marker */
    clean_retry(6, 1); /* falsely successful partial erase */
    clean_retry(5, 0); /* partial erase destroys marker */
    clean_retry(8, 0); /* successful erase but readback fails */
    puts("HOLD: destructive finalization and unreadable readback are not reboot-safe");
    printf("PASS %u corrective host assertions; HOLD physical boot, installation, recovery\n",
           assertions);
    return 0;
}
"""

def patch_test(source):
    source = base.instrument(source)
    source = one(source, "    put_record();\n    memcpy(before, nor, sizeof nor);",
                 """    memset(nor + (T_REC & ~4095u), 0xA5, 4096);
    put_record();
    memcpy(nor + T_REC + 8, OTA_PARM_ID, sizeof OTA_PARM_ID - 1u);
    ota_wr32(nor + T_REC + 72, OTA_AREA);
    ota_wr16(nor + T_REC, ota_crc16(nor + T_REC + 2, 78, 0));
    memcpy(before, nor, sizeof nor);""")
    source = one(source,
        "if (fault_kind == 1 && off == fault_off && n == 4096 && !fault_fired++) return -1;",
        """if (fault_kind == 1 && off == fault_off && n == 4096 && !fault_fired++) return -1;
        if (fault_kind == 7 && off == fault_off && n == 80 && !fault_fired++) return -1;
        if (fault_kind == 8 && off == fault_off && n == 256 && !fault_fired++) return -1;""")
    source = one(source, "    memset(nor + off, 0xFF, 0x1000);",
        """    if (fault_kind == 5 && off == fault_off && !fault_fired++) {
        memset(nor + off + 0xF00, 0xFF, 256); return -1;
    }
    if (fault_kind == 6 && off == fault_off && !fault_fired++) {
        memset(nor + off, 0xFF, 64); return 0;
    }
    memset(nor + off, 0xFF, 0x1000);""")
    pos = source.index("\nint main(void) {")
    return source[:pos] + "\n" + TESTS

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: finalization_candidate.py PINNED_DINGHY_CHECKOUT")
    root = Path(sys.argv[1]).resolve()
    if sp.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                       text=True).strip() != base.PIN:
        raise SystemExit("wrong upstream checkout")
    with tempfile.TemporaryDirectory(prefix="fm1-finalization-") as tmp:
        work = Path(tmp)
        for name, expected in base.BLOBS.items():
            raw = (root / name).read_bytes()
            if base.blob(raw) != expected:
                raise SystemExit("wrong source identity: " + name)
            out = work / name
            out.parent.mkdir(parents=True, exist_ok=True)
            if name == "tests/ldr_test.c":
                raw = patch_test(raw.decode()).encode()
            if name == "firmware/loader/ldr_core.c":
                raw = patch_core(raw.decode()).encode()
            out.write_bytes(raw)
            print("verified upstream", name, expected, flush=True)
        results = []
        for cc in ("gcc", "clang"):
            exe = work / cc
            sp.run([cc, "--version"], check=True)
            sp.run([cc, "-std=c11", "-O2", "-DBOARD_SMK37=0",
                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    str(work / "tests/ldr_test.c"), "-o", str(exe)], check=True)
            result = sp.check_output([str(exe)], text=True, timeout=90)
            print(cc, result, sep="\n", flush=True)
            results.append(result)
        if results[0] != results[1]:
            raise SystemExit("candidate compiler transcript mismatch")
        print("identical corrective native transcripts; no physical authorization")

if __name__ == "__main__":
    main()
