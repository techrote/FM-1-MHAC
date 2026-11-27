#!/usr/bin/env python3
"""Table/data-aware replacement for the final linear LLVM unknown-instruction screen.

It does not replace the existing ELF/MMIO/rebuild audit.  It classifies only rows that the
legacy llvm-objdump text screen reports as "unknown", and still fails on unclassified rows,
RAM calls or ROM-address matches.
"""
from __future__ import annotations
import argparse, json, re, struct, subprocess
from pathlib import Path

BASE = 0x02000120
LIMIT = BASE + 0x8DFBC

def need(ok, msg):
    if not ok:
        raise ValueError(msg)

def out(*args):
    return subprocess.check_output([str(x) for x in args], text=True)

def elf_text(path: Path):
    b = path.read_bytes()
    need(len(b) >= 52 and b[:7] == b"\x7fELF\x01\x01\x01", "ELF32 little-endian required")
    h = struct.unpack_from("<16sHHIIIIIHHHHHH", b)
    need(h[1] == 2 and h[2] == 241 and h[4] == BASE, "unexpected ELF type/machine/entry")
    shoff, entsz, n, shstr = h[6], h[11], h[12], h[13]
    need(entsz == 40 and 0 < shstr < n and shoff + entsz*n <= len(b), "bad section table")
    ss = [struct.unpack_from("<10I", b, shoff+i*entsz) for i in range(n)]
    st = ss[shstr]
    names = b[st[4]:st[4]+st[5]]
    found = {}
    for s in ss:
        name = names[s[0]:].split(b"\0",1)[0].decode("ascii","strict")
        if name in (".text",".ram_text"):
            found[name] = (s[3], b[s[4]:s[4]+s[5]])
    need(".text" in found and ".ram_text" in found, "missing text sections")
    return found

ROW = re.compile(r"^\s*([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{2}(?:\s+|$))+?)(?:\s{2,}|\t)(.*)$")
LABEL = re.compile(r"^([0-9a-fA-F]+) <([^>]+)>:$")

def parse_dis(text):
    rows=[]; labels=[]
    for line in text.splitlines():
        lm=LABEL.match(line)
        if lm:
            labels.append((int(lm.group(1),16),lm.group(2)))
            continue
        m=ROW.match(line)
        if m:
            raw=bytes.fromhex(" ".join(re.findall(r"[0-9a-fA-F]{2}",m.group(2))))
            rows.append({"addr":int(m.group(1),16),"raw":raw,"payload":m.group(3).strip(),"line":line})
    return rows, sorted(labels)

def tbb_ranges(rows):
    ranges=[]
    for i,row in enumerate(rows):
        m=re.search(r"\btbb\s*\[r(\d+)\]",row["payload"],re.I)
        if not m: continue
        reg=m.group(1); bound=None; guard=None
        for p in reversed(rows[max(0,i-8):i]):
            g=re.search(rf"if\s*\(r{reg}\s*>\s*(\d+)\)\s*goto",p["payload"],re.I)
            if g:
                bound=int(g.group(1)); guard=p; break
        if bound is None or bound > 255: continue
        start=row["addr"]+len(row["raw"])
        end=(start+bound+1+1)&~1  # byte table plus normal halfword padding
        ranges.append({"start":start,"end":end,"kind":"bounded-tbb-byte-table",
                       "evidence":{"tbb":row["line"],"guard":guard["line"],"entries":bound+1}})
    return ranges

def label_ranges(labels, text_addr, text_bytes, rows):
    ranges=[]
    for addr,name in labels:
        if not name.startswith(".Ljta"): continue
        off=addr-text_addr
        if off < 0 or off+12 > len(text_bytes): continue
        words=[]
        pos=off
        while pos+4 <= len(text_bytes) and len(words) < 256:
            w=struct.unpack_from("<I",text_bytes,pos)[0]
            if not (text_addr <= w < text_addr+len(text_bytes) and w % 2 == 0):
                break
            words.append(w)
            pos += 4
        if len(words) < 3: continue
        prior=[r for r in rows if r["addr"] < addr][-10:]
        joined=" | ".join(r["payload"] for r in prior)
        # The compiler-specific .Ljta label plus a contiguous run of in-.text targets is
        # the classification gate. The independent direct_object.mjs closure check binds
        # each word to its local relocation symbol; the nearby dispatch is retained here
        # as diagnostic context only because llvm-objdump formatting is not stable enough
        # to make a regex over that syntax an acceptance condition.
        end=addr+4*len(words)
        ranges.append({"start":addr,"end":end,"kind":"computed-address-jump-table",
                       "evidence":{"label":name,"targets":[hex(w) for w in words],"dispatch":joined}})
    return ranges

def string_range(addr, text_addr, text_bytes):
    o=addr-text_addr
    if o < 0 or o >= len(text_bytes): return None
    printable=lambda x: 32 <= x <= 126
    if not printable(text_bytes[o]): return None
    a=o
    while a>0 and printable(text_bytes[a-1]): a-=1
    z=o
    while z<len(text_bytes) and printable(text_bytes[z]): z+=1
    if z-a < 6 or z >= len(text_bytes) or text_bytes[z] != 0:
        return None
    return {"start":text_addr+a,"end":text_addr+z+1,"kind":"nul-terminated-printable-literal",
            "evidence":{"text":text_bytes[a:z].decode("ascii")}}

def classify(row, ranges, text_addr, text_bytes):
    a=row["addr"]
    for r in ranges:
        if r["start"] <= a < r["end"]:
            return r
    return string_range(a,text_addr,text_bytes)

def screen(path: Path, tc: Path):
    sections=elf_text(path)
    dis=out(tc/"llvm-objdump","-d",path)
    rows,labels=parse_dis(dis)
    rt=out(tc/"llvm-objdump","-d","-j",".ram_text",path)
    rtrows,_=parse_dis(rt)
    unknown=[r for r in rows if re.search(r"<unknown>|\bunknown\b",r["payload"],re.I)]
    ranges=tbb_ranges(rows)+label_ranges(labels,*sections[".text"],rows)
    classified=[]; unresolved=[]
    for row in unknown:
        c=classify(row,ranges,*sections[".text"])
        rec={"address":hex(row["addr"]),"row":row["line"]}
        if c:
            rec.update({"classification":c["kind"],"range":[hex(c["start"]),hex(c["end"])],
                        "evidence":c["evidence"]})
            classified.append(rec)
        else:
            unresolved.append(rec)
    calls=[r["line"] for r in rtrows if re.search(r"\bcall\w*\b",r["payload"],re.I)]
    rom=[]
    for r in rows:
        if re.search(r"\b(?:0x)?ffc[0-9a-f]{5}\b",r["line"],re.I): rom.append(r["line"])
        for val in re.findall(r"=\s*(-?\d+)\s*(?:<|$)",r["line"]):
            if 0xFFC00000 <= (int(val)&0xffffffff) < 0xFFD00000 and r["line"] not in rom: rom.append(r["line"])
    receipt={"elf":path.name,"legacy_unknown_rows":len(unknown),"recognized_ranges":[
                 {"kind":r["kind"],"start":hex(r["start"]),"end":hex(r["end"])} for r in ranges],
             "classified_data_rows":len(classified),
             "unresolved_unknown_rows":len(unresolved),"classified":classified,"unresolved":unresolved,
             "ram_calls":calls,"rom_hits":rom,
             "status":"PASS" if not unresolved and not calls and not rom else "HOLD"}
    print("table_aware_screen "+json.dumps(receipt,sort_keys=True))
    need(receipt["status"]=="PASS",f"table-aware screen HOLD for {path.name}")
    return receipt

def selftest():
    dis=""" 2002254: 00 fc ea 08    if (r0 > 4) goto 468
 2002258: 00 01          tbb [r0]
 200225a: 03 9d          <unknown>
 200225c: 32 46          if (r2 == 0) goto 204
 200225e: 2d 00          <unknown>
"""
    rows,_=parse_dis(dis); rr=tbb_ranges(rows)
    need(len(rr)==1 and rr[0]["start"]==0x200225a and rr[0]["end"]==0x2002260,"TBB range")
    need(classify(rows[2],rr,0x2000000,b"\0"*0x3000)["kind"]=="bounded-tbb-byte-table","TBB classify")
    need(classify(rows[4],rr,0x2000000,b"\0"*0x3000)["kind"]=="bounded-tbb-byte-table","TBB pad classify")
    bad=""" 2002258: 00 01          tbb [r0]
 200225a: 03 9d          <unknown>
"""
    need(not tbb_ranges(parse_dis(bad)[0]),"unguarded TBB must not classify")
    data=bytearray(b"\0"*64); data[8:22]=b"UNKNOWN FLASH\0"
    c=string_range(8,0,data); need(c and c["kind"]=="nul-terminated-printable-literal","string")
    data[8:14]=b"ABCDEF"; data[14]=1; need(string_range(8,0,data) is None,"unterminated/nonliteral")
    print("table_aware_screen_selftest=PASS")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--toolchain",type=Path)
    ap.add_argument("elf",nargs="*",type=Path)
    a=ap.parse_args()
    if a.selftest: selftest()
    if a.elf:
        need(a.toolchain is not None,"--toolchain required")
        for p in a.elf: screen(p,a.toolchain)

if __name__=="__main__":
    main()
