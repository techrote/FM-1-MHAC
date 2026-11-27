#!/usr/bin/env python3
"""Contextual panel PCM witness, with bounded integer onset search."""
import array
import pathlib
import subprocess
import sys
import tempfile
from fractions import Fraction as F
from context_inverse import atlas, decode, parse, pcm, SLOT

# Keys are actual modeled panel names, not MIDI commands. 10 means clear context.
CASES = {
    'literal': ('N5', [8,9]),
    'witness': ('N0 N1 N2 N2 N6 N7 SCL', [0,1,2,2,10,6,5,5,4,3,9]),
    'unwitnessed': ('N0 N1 N2 N2 N6 N7', [0,1,2,2,10,5,5,4,3,9]),
    'unknown': ('N0 N6 N10 SCL', [0,10,3,9]),
    'edited': ('N0 N2 N11 N1 N6 N9 SCL', [0,1,10,8,4,3,9]),
}


def verify(a, bounds, templates, case):
    if len(bounds)!=4 or not 0<=bounds[0]<bounds[1]<=bounds[2]<bounds[3]==len(a) or any(b%2 for b in bounds):
        raise ValueError('invalid capture bounds')
    start,end,mute,stop=bounds
    if any(a[:start]) or any(a[mute:stop]):
        raise ValueError('boot or mute not silent')
    first=next((i for i in range(start,end,2) if max(abs(a[i]),abs(a[i+1]))>2),None)
    if first is None: raise ValueError('no positive witness')
    seq=CASES[case][1]; span=2*SLOT*len(seq); matches=[]
    # All expressions start with a non-rest motif; constrain onset to 64 frames.
    for shift in range(65):
        origin=first-2*shift
        if origin<start or origin+2*span>end or any(a[start:origin]): continue
        # Decode every receiver context, and both loops under a common gain.
        g=(F(1,8),F(5,4))
        for j in range(2):
            block=a[origin+j*span:origin+(j+1)*span]
            for rc in range(4):
                result=decode(block,templates,rc)
                if result is None or result[0]!=parse(seq,rc): break
                lo,hi=result[1];g=max(g[0],lo),min(g[1],hi)
                if g[0]>g[1]: break
            else: continue
            break
        else: matches.append((origin//2,g))
    if len(matches)!=1: raise ValueError(f'expected unique onset, got {matches}')
    print(f'case={case} origin={matches[0][0]} gain={matches[0][1]} two_loops=PASS receiver_contexts=4/4')
    return matches[0]


def selftest(templates):
    # Exercise the actual portable editor and callback, not a Python-only renderer.
    code='''#define CP_TEST\n#define main original_main\n#include "context_panel.c"\n#undef main\nint main(int argc,char **argv){\n cp_edit e={0,0,0,3,0,0};\n for(int j=1;j<argc;j++){if(!strcmp(argv[j],"SCL"))e.witness^=1;else cp_key(&e,(unsigned)atoi(argv[j]+1));}\n e.run=1;cp_audio s={0};sc_phrase p={0};uint32_t c=cp_pack(&e);assert(!cp_phrase(c,&p));\n unsigned n=2*p.n*SC_SLOT;memset(a,0,sizeof a);blocks(&s,a,n,c,257);\n for(unsigned j=0;j<2*n;j++){unsigned q=(uint16_t)a[j];assert(putchar(q&255)!=EOF&&putchar(q>>8)!=EOF);}return 0;}\n'''
    with tempfile.TemporaryDirectory() as tmp:
        src=pathlib.Path(tmp)/'fixture.c';exe=src.with_suffix('');src.write_text(code)
        for cc in ('gcc','clang'):
            subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(pathlib.Path(__file__).resolve().parent),str(src),'-o',str(exe)],check=True)
            for case,(keys,seq) in CASES.items():
                raw=pcm(subprocess.check_output([str(exe),*keys.split()]))
                assert len(raw)==4*SLOT*len(seq)
                for gain in (F(1,8),F(77,200),F(5,4)):
                    a=array.array('h',[0])*400+array.array('h',(round(gain*v) for v in raw))+array.array('h',[0])*1000
                    bounds=(200,len(a)-800,len(a)-400,len(a))
                    origin,g=verify(a,bounds,templates,case);assert origin==200 and g[0]<=gain<=g[1]
                # Wrong expected grammar must fail even when waveform is valid.
                try:verify(a,bounds,templates,'literal' if case!='literal' else 'unknown')
                except ValueError:pass
                else:raise AssertionError('wrong expected grammar accepted')
                # Post-mute nonzero sample must fail.
                a[-1]=1
                try:verify(a,bounds,templates,case)
                except ValueError:pass
                else:raise AssertionError('mute violation accepted')
    print('native contextual capture fixtures PASS; 30 positive / 20 negative controls, not emulation')


if __name__=='__main__':
    templates=atlas('gcc')
    if len(sys.argv)==1:selftest(templates)
    else:
        prefix=pathlib.Path(sys.argv[1]);case=sys.argv[2]
        verify(pcm(prefix.with_suffix('.pcm').read_bytes()),tuple(map(int,prefix.with_suffix('.bounds').read_text().split())),templates,case)
