#!/usr/bin/env python3
"""Aligned contextual motif inverse; receiver context is an explicit input.
No synchronization, analogue or physical-hardware claim."""
import array
import hashlib
import pathlib
import subprocess
import sys
import tempfile
from fractions import Fraction as F
from scope_inverse import feasible, ENV, GAIN

SLOT, REST, REF = 4800, 9, 10
FIXTURE = r'''
#include "scope_context.c"
#include <stdio.h>
#include <assert.h>
int main(void){
 for(unsigned t=0;t<=SC_REF;t++){
  int32_t b[2*SW_ENV]={0};sc_state s={0};s.active=1;s.phrase.n=1;s.phrase.t[0]=(uint8_t)t;
  sc_render(&s,b,SW_ENV);
  for(unsigned j=0;j<2*SW_ENV;j++){unsigned q=(uint16_t)b[j];assert(putchar(q&255)!=EOF&&putchar(q>>8)!=EOF);}
 }
 return 0;
}
'''


def pcm(raw):
    a=array.array('h');a.frombytes(raw)
    if sys.byteorder!='little':a.byteswap()
    return a


def atlas(cc):
    with tempfile.TemporaryDirectory() as tmp:
        c=pathlib.Path(tmp)/'atlas.c';exe=c.with_suffix('');c.write_text(FIXTURE)
        subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(pathlib.Path(__file__).resolve().parent),str(c),'-o',str(exe)],check=True)
        raw=subprocess.check_output([str(exe)])
    a=pcm(raw);assert len(a)==11*2*ENV
    return [a[i*2*ENV:(i+1)*2*ENV] for i in range(11)]


def parse(seq, context):
    if context not in range(4):raise ValueError('context')
    i=0;ops=[]
    while i<len(seq) and seq[i]<3:
        ops.append(seq[i]);i+=1
    if len(ops)>4 or i>=len(seq):return None
    leaf=seq[i];i+=1;witness=None
    if leaf==REF and i<len(seq) and 6<=seq[i]<=8:
        witness=seq[i]-6;i+=1
    if leaf!=REF and not 6<=leaf<=8:return None
    if list(seq[i:])!=[3+o for o in reversed(ops)]+[REST]:return None
    if leaf!=REF:status,resolved='literal',leaf-6
    elif witness is not None and context!=3 and context!=witness:status,resolved='mismatch',None
    elif context!=3:status,resolved='context',context
    elif witness is not None:status,resolved='witness-only',witness
    else:status,resolved='unknown',None
    return tuple(ops),leaf,witness,status,resolved


def decode(a, templates, context):
    if len(a)%(2*SLOT) or not 2<=len(a)//(2*SLOT)<=12:return None
    seq=[];lo,hi=GAIN
    for start in range(0,len(a),2*SLOT):
        if any(a[start+2*ENV:start+2*SLOT]):return None
        y=a[start:start+2*ENV];matches=[]
        for t,x in enumerate(templates):
            g=feasible(x,y,(lo,hi))
            if g is not None:matches.append((t,g))
        if len(matches)!=1:return None
        t,(lo,hi)=matches[0];seq.append(t)
    result=parse(seq,context)
    return (result,(lo,hi)) if result is not None else None


def synth(seq, templates):
    a=array.array('h')
    for t in seq:a.extend(templates[t]);a.extend([0]*(2*(SLOT-ENV)))
    return a


def main(cc, path):
    templates=atlas(cc)
    assert all(feasible(a,b,(F(1,10),F(10)),32) is None for i,a in enumerate(templates) for b in templates[:i])
    raw=pathlib.Path(path).read_bytes();a=pcm(raw);offset=0;cases=0
    for w in range(2):
        for c in range(4):
            witness=c if w and c<3 else None
            seq=[0,1,2,2,REF]+([] if witness is None else [6+witness])+[5,5,4,3,REST]
            n=len(seq)*2*SLOT;x=a[offset:offset+n];offset+=n;assert x==synth(seq,templates)
            g=(F(1,8),F(77,200),F(5,4))[cases%3]
            y=array.array('h',(round(g*v)+(j%3-1) if j%(2*SLOT)<2*ENV and seq[j//(2*SLOT)]!=REST else 0 for j,v in enumerate(x)))
            for rc in range(4):
                result,interval=decode(y,templates,rc);assert result==parse(seq,rc) and interval[0]<=g<=interval[1]
                if witness is not None and rc<3 and rc!=witness:assert result[3]=='mismatch'
            cases+=1
    assert offset==len(a)
    seq=[0,REF,6,3,REST];x=synth(seq,templates)
    assert decode(x,templates,2)[0][3]=='mismatch'
    assert decode(x,templates,3)[0][3]=='witness-only'
    assert decode(synth([0,REF,6,4,REST],templates),templates,0) is None
    x[2*ENV]=1;assert decode(x,templates,0) is None
    x=synth(seq,templates);x[:2*ENV]=array.array('h',(round(F(1,2)*v) for v in x[:2*ENV]));assert decode(x,templates,0) is None
    print(f'template_pairs=55/55 panel_captures={cases}/8 receiver_cases={cases*4}/32 closure_gap_gain_falsifiers=PASS pcm_sha256={hashlib.sha256(raw).hexdigest()}')

if __name__=='__main__':main(*sys.argv[1:])
