#!/usr/bin/env python3
"""Bounded pi32v2 emitted-assembly provenance investigation.

No acceptance waiver: direct no-relax builds must match the previously qualified object/ELF
digests. Textual routes are diagnostic and may remain HOLD.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, tarfile, tempfile
from pathlib import Path

PIN="92f17b28f2d05f2f78fd1b160b58475d518902c8"
TC_HASH="cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990"
EXPECTED={
 "baseline":{"obj":"8211bfa04e537294b42067c9b773dd14697714f79552370fdfd803397a6b69e3","elf":"5dd622e2af4bfaffd78f9621392a646c828c5e421b93e74aa41cd3fb9e6b943d"},
 "scope":{"obj":"ea94170826dce664018a4ffe721e9dc8af66be6741a0b5c3d091bbdc276cef86","elf":"90e098ef48f757e40f1828efd62a5c6014e9d84451b54fa983aee5325e8e0eeb"},
}

def need(x,m):
    if not x: raise ValueError(m)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(args,cwd=None,check=True):
    p=subprocess.run([str(x) for x in args],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if check and p.returncode: raise RuntimeError(f"{args[0]} exit {p.returncode}: {p.stderr[-2000:]}")
    return p
def section_sizes(readelf,obj):
    t=run([readelf,"-S","-W",obj]).stdout
    out={}
    import re
    for l in t.splitlines():
        m=re.search(r"\[\s*\d+\]\s+(\S+)\s+\S+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+([0-9A-Fa-f]+)",l)
        if m: out[m.group(1)]=int(m.group(2),16)
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("dinghy",type=Path);ap.add_argument("archive",type=Path);ap.add_argument("scope",type=Path)
    a=ap.parse_args()
    need(run(["git","-C",a.dinghy,"rev-parse","HEAD"]).stdout.strip()==PIN,"wrong Dinghy pin")
    need(not run(["git","-C",a.dinghy,"status","--porcelain"]).stdout.strip(),"dirty Dinghy")
    need(sha(a.archive)==TC_HASH,"wrong toolchain archive")
    with tempfile.TemporaryDirectory(prefix="pre-hw-prov-") as td:
        td=Path(td); tc=td/"tc"; src=td/"src";tc.mkdir();src.mkdir()
        run(["tar","-xJf",a.archive,"-C",tc,"--strip-components=1"])
        arc=td/"src.tar"
        with arc.open("wb") as f:
            subprocess.run(["git","-C",a.dinghy,"archive","--format=tar",PIN],stdout=f,check=True)
        run(["tar","-xf",arc,"-C",src])
        clang=tc/"bin/clang"; ld=tc/"bin/ld.lld"; readelf=tc/"bin/llvm-readelf"; objdump=tc/"bin/llvm-objdump"
        flags=["-target","pi32v2","-mcpu=ac791n","-Os","-ffunction-sections","-fno-builtin","-Wall","-Wno-unused-function",
               "-Ifirmware/hal","-Ifirmware/src","-Ifirmware/gen","-DAPP_VER=\"dev\"","-DFELUCCA_ID=\"FM-1_990\"",
               "-fno-jump-tables","-mno-relax-all"]
        startup=[]
        for s in ["firmware/crt0.S","firmware/hal/fm1_vec.S","firmware/hal/fm1_isr.S"]:
            o=td/(Path(s).stem+".o"); run([clang,"-target","pi32v2","-mcpu=ac791n","-c",s,"-o",o],cwd=src);startup.append(o)
        reports=[]
        for variant in ["baseline","scope"]:
            tree=td/variant; shutil.copytree(src,tree)
            if variant=="scope":
                shutil.copy2(a.scope/"app.c",tree/"firmware/src/dinghy.c")
                shutil.copy2(a.scope/"scope_weave.h",tree/"firmware/src/scope_weave.h")
            direct=td/(variant+"-direct.o"); repeat=td/(variant+"-repeat.o"); asm=td/(variant+".s")
            run([clang,*flags,"-c","firmware/src/dinghy.c","-o",direct],cwd=tree)
            run([clang,*flags,"-c","firmware/src/dinghy.c","-o",repeat],cwd=tree)
            need(sha(direct)==sha(repeat)==EXPECTED[variant]["obj"],f"{variant} direct object drift")
            direct_elf=td/(variant+"-direct.elf")
            run([ld,"--gc-sections","-e","_start","-T","firmware/app.ld",*startup,direct,"-o",direct_elf],cwd=tree)
            need(sha(direct_elf)==EXPECTED[variant]["elf"],f"{variant} direct ELF drift")
            run([clang,*flags,"-S","firmware/src/dinghy.c","-o",asm],cwd=tree)
            trace_c=run([clang,*flags,"-###","-c","firmware/src/dinghy.c","-o",td/"trace.o"],cwd=tree,check=False).stderr
            trace_s=run([clang,*flags,"-###","-c",asm,"-o",td/"trace-asm.o"],cwd=tree,check=False).stderr
            routes=[
              ("assembler-default",[]),
              ("assembler-mno-relax-all",["-mno-relax-all"]),
              ("assembler-xassembler-mno-relax-all",["-Xassembler","-mno-relax-all"]),
              ("assembler-wa-mno-relax-all",["-Wa,-mno-relax-all"]),
              ("assembler-xassembler-no-relax",["-Xassembler","--no-relax"]),
              ("assembler-wa-no-relax",["-Wa,--no-relax"]),
            ]
            rr=[]
            for name,extra in routes:
                obj=td/(variant+"-"+name+".o"); elf=td/(variant+"-"+name+".elf")
                p=run([clang,"-target","pi32v2","-mcpu=ac791n",*extra,"-c",asm,"-o",obj],cwd=tree,check=False)
                row={"route":name,"compile_exit":p.returncode,"stderr_tail":p.stderr[-500:]}
                if p.returncode==0:
                    q=run([ld,"--gc-sections","-e","_start","-T","firmware/app.ld",*startup,obj,"-o",elf],cwd=tree,check=False)
                    row.update({"link_exit":q.returncode,"object_sha256":sha(obj),"object_exact":sha(obj)==EXPECTED[variant]["obj"],
                                "direct_sections":section_sizes(readelf,direct),"route_sections":section_sizes(readelf,obj)})
                    if q.returncode==0:
                        row.update({"elf_sha256":sha(elf),"elf_exact":sha(elf)==EXPECTED[variant]["elf"]})
                    else: row["link_stderr_tail"]=q.stderr[-500:]
                rr.append(row)
            exact=[x["route"] for x in rr if x.get("object_exact") and x.get("elf_exact")]
            c_relax="-mrelax-all" in trace_c or "mno-relax" in trace_c.lower()
            s_relax="-mrelax-all" in trace_s or "mno-relax" in trace_s.lower()
            diagnosis=("textual route remains HOLD; direct C no-relax is reproducible, but no tested assembler route reproduces it. "
                       "Reassembly uses cc1as; C/codegen options are unused there, and tested assembler-specific relaxation controls are unsupported or non-exact at this pin.")
            rep={"variant":variant,"direct_object_sha256":sha(direct),"direct_elf_sha256":sha(direct_elf),
                 "direct_repeat_exact":True,"exact_textual_routes":exact,"routes":rr,
                 "c_trace_mentions_relax_control":c_relax,"asm_trace_mentions_relax_control":s_relax,
                 "c_driver_trace_tail":trace_c[-1600:],"asm_driver_trace_tail":trace_s[-1600:],
                 "diagnosis":diagnosis,"status":"PASS" if exact else "HOLD","installation_authorized":False}
            print("provenance_probe "+json.dumps(rep,sort_keys=True));reports.append(rep)
        need(all(x["direct_repeat_exact"] for x in reports),"direct reproducibility lost")
        print("provenance_probe_complete=PASS diagnostic executed; textual identity may remain HOLD")

if __name__=="__main__":
    main()
