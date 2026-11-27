#!/usr/bin/env python3
"""Scope Weave aligned, known-erasure inverse; host measurement, not target DSP."""
import argparse
import array
import itertools
import pathlib
import subprocess
import tempfile
import wave
from fractions import Fraction as F

ENV, REST = 2048, 9
GAIN = (F(1, 8), F(5, 4))
C_FIXTURE = r'''
#include "scope_weave.h"
#include <stdio.h>
#include <assert.h>
static int32_t buf[2*6*4800];
static void emit(unsigned n){
 for(unsigned j=0;j<2*n;j++){
  unsigned x=(uint16_t)buf[j];
  assert(putchar(x&255u)!=EOF);assert(putchar(x>>8)!=EOF);buf[j]=0;
 }
}
int main(void){
 for(unsigned t=0;t<9;t++){sw_state s={0};sw_trigger(&s,t);sw_render(&s,buf,SW_ENV,0,0,26,0);emit(SW_ENV);}
 for(unsigned m=0;m<3;m++)for(unsigned p=0;p<27;p++){
  sw_state s={0};sw_render(&s,buf,6*4800,p,m,26,1);emit(6*4800);
 }
 return 0;
}
'''

def tokens(p, mode):
    a, b, c = p//9, p//3%3, p%3
    if mode == 1:
        a, b = sorted((a,b))
    if mode == 2:
        return (REST,REST,6+c,REST,REST,REST)
    return (a,b,6+c,3+b,3+a,REST)


def feasible(x, y, prior=GAIN, eps=2):
    """Exact interval for common positive gain; no floating-point acceptance."""
    ln, ld = prior[0].numerator, prior[0].denominator
    hn, hd = prior[1].numerator, prior[1].denominator
    # Early probes only reject; every sample is checked before acceptance.
    for indices in (range(0,len(x),127), range(len(x))):
        for i in indices:
            a,b = x[i],y[i]
            if a == 0:
                if abs(b)>eps:
                    return None
                continue
            if a < 0:
                a,b = -a,-b
            l,h = b-eps,b+eps
            if l*ld>ln*a:
                ln,ld=l,a
            if h*hd<hn*a:
                hn,hd=h,a
            if ln*hd>hn*ld:
                return None
    return F(ln,ld),F(hn,hd)


def inverse(pcm, atlas, rate=26, observed=range(6), modes=range(3)):
    """Return (mode,preset,gain interval) for EVERY compatible history.

    Requires externally aligned six-slot PCM at 44.1 kHz, fixed rate, no overlap.
    Entire missing slots are ignored, including their gaps. Retained gaps exact zero.
    """
    if not 0<=rate<=26:
        raise ValueError('rate')
    tick=10000-200*rate
    if len(pcm)!=12*tick or len(atlas)!=10:
        raise ValueError('shape')
    observed=tuple(sorted(set(observed)))
    if any(not 0<=j<6 for j in observed):
        raise ValueError('slot')
    evidence={}
    for j in observed:
        start=2*j*tick
        if any(pcm[start+2*ENV:start+2*tick]):
            return []
        y=pcm[start:start+2*ENV]
        evidence[j]={}
        for t,x in enumerate(atlas):
            g=feasible(x,y)
            if g is not None:
                evidence[j][t]=g
    matches=[]
    for mode,p in itertools.product(modes,range(27)):
        lo,hi=GAIN
        for j in observed:
            g=evidence[j].get(tokens(p,mode)[j])
            if g is None:
                break
            lo,hi=max(lo,g[0]),min(hi,g[1])
            if lo>hi:
                break
        else:
            matches.append((mode,p,(lo,hi)))
    return matches


def native(cc):
    with tempfile.TemporaryDirectory() as tmp:
        c=pathlib.Path(tmp)/'atlas.c'; exe=pathlib.Path(tmp)/'atlas'
        c.write_text(C_FIXTURE)
        subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror',
                        '-fsanitize=undefined','-fno-sanitize-recover=all','-I',
                        str(pathlib.Path(__file__).resolve().parent),str(c),'-o',str(exe)],check=True)
        raw=subprocess.check_output([str(exe)])
    data=array.array('h');data.frombytes(raw)
    import sys
    if sys.byteorder!='little': data.byteswap()
    assert len(data)==9*2*ENV+81*12*4800
    atlas=[data[i*2*ENV:(i+1)*2*ENV] for i in range(9)]
    atlas.append(array.array('h',[0])*(2*ENV))
    base=9*2*ENV
    phrases=[data[base+i*57600:base+(i+1)*57600] for i in range(81)]
    return atlas,phrases,raw


def synth(seq, atlas):
    out=array.array('h')
    for t in seq:
        out.extend(atlas[t]);out.extend([0]*(2*(4800-ENV)))
    return out


def selftest(cc):
    import hashlib
    atlas,phrases,raw=native(cc)
    # Necessary condition for overlap under GAIN and eps=2: |x-r*z| <=32.
    # Includes silence: do not conflate absent data with retained zero samples.
    assert all(feasible(a,b,(F(1,10),F(10)),32) is None
               for i,a in enumerate(atlas) for b in atlas[:i])
    print('pairwise template separation: 45/45')
    for mode in range(3):
        for p in range(27):
            seq=tokens(p,mode); x=phrases[27*mode+p]
            assert x==synth(seq,atlas)
            g=(F(1,8),F(77,200),F(5,4))[p%3]
            y=array.array('h', (round(g*v)+((i%3)-1) if i%9600<4096 and seq[i//9600]!=REST else 0
                               for i,v in enumerate(x)))
            got=inverse(y,atlas,modes=(mode,))
            expected=[q for q in range(27) if tokens(q,mode)==seq]
            assert [q for _,q,_ in got]==expected
            assert all(lo<=g<=hi for _,_,(lo,hi) in got)
        print(f'mode {mode}: 27/27 noisy gain-varied native phrases')
    original=tokens(3,0)
    malformed=list(original);malformed[3]=3
    assert not inverse(synth(malformed,atlas),atlas,modes=(0,))
    alternate=list(original);alternate[1]=2;alternate[3]=5
    assert [p for _,p,_ in inverse(synth(alternate,atlas),atlas,modes=(0,))]==[6]
    # Each isolated pulse valid; inconsistent gain across slots must fail.
    y=phrases[3][:];y[:4096]=array.array('h',(round(F(1,2)*v) for v in y[:4096]))
    assert not inverse(y,atlas,modes=(0,))
    y=phrases[3][:];y[4096]=1
    assert not inverse(y,atlas,modes=(0,))
    print('falsifiers: malformed close, shared-gain violation, gap activity rejected; valid paired substitution accepted')
    # Exhaust all slot-retention masks symbolically; pairwise certificate makes
    # this a statement about identifiability under the aligned contract.
    for mode in range(3):
        full=[]
        for mask in range(64):
            obs=[j for j in range(6) if mask>>j&1]
            classes={tuple(tokens(p,mode)[j] for j in obs) for p in range(27)}
            if len(classes)==27: full.append(mask)
        minimum=min((m.bit_count() for m in full),default=None)
        print(f'mode {mode}: fully identifying masks {len(full)}/64, minimum slots {minimum}')
    for obs in ((0,1,2),(2,3,4),(0,4),(2,),()):
        got=inverse(phrases[3],atlas,observed=obs,modes=(0,))
        expected=[p for p in range(27) if all(tokens(p,0)[j]==original[j] for j in obs)]
        assert [p for _,p,_ in got]==expected
        print(f'observed={obs}: compatible presets={expected}')
    print('native atlas+phrases sha256',hashlib.sha256(raw).hexdigest())
    print('PASS')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cc',default='gcc');ap.add_argument('--wav',type=pathlib.Path)
    ap.add_argument('--frame',type=int,default=0);ap.add_argument('--rate',type=int,default=26)
    ap.add_argument('--slots',default='0,1,2,3,4,5')
    args=ap.parse_args()
    if args.wav is None:
        selftest(args.cc)
    else:
        atlas,_,_=native(args.cc)
        with wave.open(str(args.wav),'rb') as w:
            if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(2,2,44100):
                raise ValueError('requires stereo PCM16 44100 Hz')
            w.setpos(args.frame); raw=w.readframes(6*(10000-200*args.rate))
        pcm=array.array('h');pcm.frombytes(raw)
        import sys
        if sys.byteorder!='little': pcm.byteswap()
        for match in inverse(pcm,atlas,args.rate,[int(j) for j in args.slots.split(',') if j]):
            print(match)
