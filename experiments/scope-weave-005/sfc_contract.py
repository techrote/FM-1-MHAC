#!/usr/bin/env python3
"""Host-only fault injection for pinned Dinghy fl_enter/fl_exit.
No device access, target compilation, or physical register model claim.
Input: firmware/hal/fm1_flash.h from Dinghy 92f17b28f2d05f2f78fd1b160b58475d518902c8.
Generated GPL-derived test translation unit stays in a disposable directory.
"""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile

REGION_SHA = 'a769d554468574a94fdc3245c6e85f3243581538786d384d09bea7535e504869'
BLOB_SHA = 'c5db7c2e6665d267623556177d2afbe939e8be99'

PRE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <setjmp.h>
#define RAMINL static inline
#define BUSY UINT32_C(0x80000000)
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
typedef struct { uint32_t sfc_con, spi_con; } fl_saved_t;
static uint32_t cfg, SPI0_CON, IOMAP_CON0, writes[2];
static unsigned reads, nw, busy_left, phase, budget, exit_busy;
static int stuck, cache_stuck;
static jmp_buf stop;
static void tick(void) { if (!budget) longjmp(stop,1); --budget; }
static void fl_cache_idle(void) { while (cache_stuck) tick(); }
static void fl_csync(void) { }
static uint32_t sfc_read(void) {
    tick(); ++reads;
    if (stuck || busy_left) { if (busy_left) --busy_left; return cfg | BUSY; }
    return cfg;
}
static void sfc_write(uint32_t v) {
    REQUIRE(nw < 2); writes[nw++] = v;
    cfg = v & ~BUSY; /* hypothesis: bit 31 is read-only status */
    if (nw == 1) busy_left = exit_busy;
}
'''
POST = r'''
static void init(uint32_t mode, unsigned first, unsigned last) {
    cfg=UINT32_C(0x00010025)|(mode<<8); SPI0_CON=0x55aa; IOMAP_CON0=0xa5;
    reads=nw=phase=0; busy_left=first; exit_busy=last; budget=64; stuck=cache_stuck=0;
}
static void normal(unsigned mode, unsigned first, unsigned last) {
    fl_saved_t s;
    init(mode,first,last); uint32_t original=cfg;
    REQUIRE(setjmp(stop)==0);
    int rc=fl_enter(&s);
    REQUIRE(s.sfc_con==(original|(first?BUSY:0)) && s.spi_con==0x55aa);
    if(mode==6 || mode==7) {
        REQUIRE(rc==-1 && reads==1 && nw==0 && cfg==original && SPI0_CON==0x55aa && IOMAP_CON0==0xa5);
        return;
    }
    REQUIRE(rc==0 && nw==1 && writes[0]==0 && cfg==0 && SPI0_CON==0x1029 && IOMAP_CON0==0x85);
    REQUIRE(reads==2+(first?first-1:0));
    fl_exit(&s);
    REQUIRE(reads==3+(first?first-1:0)+last && nw==2);
    REQUIRE(writes[1]==(original|(first?BUSY:0)) && cfg==original && SPI0_CON==0x55aa && IOMAP_CON0==0xa5);
}
static void fault(unsigned kind) {
    fl_saved_t s;
    init(3,0,0);
    if(setjmp(stop)==0) {
        if(kind==0) cache_stuck=1;
        if(kind==1) stuck=1;
        REQUIRE(fl_enter(&s)==0);
        phase=1;
        stuck=1;
        fl_exit(&s);
        REQUIRE(0);
    }
    REQUIRE(budget==0);
    if(kind==0) REQUIRE(phase==0 && reads==0 && nw==0 && cfg!=0 && SPI0_CON==0x55aa && IOMAP_CON0==0xa5);
    if(kind==1) REQUIRE(phase==0 && reads==64 && nw==0 && cfg!=0 && SPI0_CON==0x55aa && IOMAP_CON0==0xa5);
    if(kind==2) REQUIRE(phase==1 && reads==64 && nw==1 && cfg==0 && SPI0_CON==0x55aa && IOMAP_CON0==0xa5);
    printf("fault=%u budget_exhausted reads=%u writes=%u phase=%u\n",kind,reads,nw,phase);
}
int main(void) {
    unsigned n=0,rejected=0,busy_restore=0;
    for(unsigned mode=0;mode<16;++mode) for(unsigned a=0;a<5;++a) for(unsigned b=0;b<5;++b) {
        normal(mode,a,b); ++n;
        if(mode==6 || mode==7) ++rejected; else if(a) ++busy_restore;
    }
    printf("finite_cases=%u rejected_mode=%u saved_busy_written_back=%u\n",n,rejected,busy_restore);
    for(unsigned i=0;i<3;++i) fault(i);
    puts("PASS source-contract observation; hardware fidelity HOLD");
    return 0;
}
'''


def transform(raw, excerpt=False):
    if not excerpt and hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()!=BLOB_SHA:
        raise ValueError('source Git blob mismatch')
    s=raw.decode('utf-8')
    start=s.index('RAMINL int fl_enter(')
    end=s.index('\nRAMINL void fl_inval(',start) if not excerpt else len(s)
    region=s[start:end].rstrip()+'\n'
    if hashlib.sha256(region.encode()).hexdigest()!=REGION_SHA:
        raise ValueError('enter/exit source region mismatch')
    # Separate stores from loads; refuse anchor drift before compiling.
    region,n=re.subn(r'\bSFC_CON\s*=\s*([^;]+);',r'sfc_write(\1);',region)
    if n!=2 or len(re.findall(r'\bSFC_CON\b',region))!=3:
        raise ValueError('unexpected register access structure')
    region=re.sub(r'\bSFC_CON\b','sfc_read()',region)
    return PRE+region+POST


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--excerpt',action='store_true',help='region-only fixture, not full pinned source')
    a=p.parse_args()
    raw=a.source.read_bytes()
    c=transform(raw,a.excerpt)
    # Deterministic fail-closed negative control.
    try:
        transform(raw.replace(b'SFC_CON',b'SFC_BAD',1),a.excerpt)
    except ValueError:
        print('mutated source rejected',flush=True)
    else:
        raise RuntimeError('mutation accepted')
    print('source=region-only fixture' if a.excerpt else 'source=exact pinned Git blob',flush=True)
    with tempfile.TemporaryDirectory() as d:
        src=Path(d)/'contract.c'; src.write_text(c,encoding='utf-8')
        outputs=[]
        for cc in ('gcc','clang'):
            binary=Path(d)/cc
            subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all',str(src),'-o',str(binary)],check=True,timeout=30)
            result=subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=10)
            outputs.append(result.stdout)
            print(cc+'\n'+result.stdout,end='',flush=True)
        if outputs[0]!=outputs[1]:
            raise RuntimeError('compiler observation mismatch')
    print('No target execution or controller validation. HOLD.')


if __name__=='__main__':
    main()
