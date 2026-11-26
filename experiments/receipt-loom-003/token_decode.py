"""Host-only exact bounded-error template inversion. Python 3 stdlib only.
No physical audio-channel model, timing recovery beyond integer onset offsets,
or authentication claim. A nonunique answer is not silently resolved.
"""
import array
import hashlib
import pathlib
import sys
from fractions import Fraction

N = 2048
RATE = 44100
EPS = 2
GAIN = (1, 8, 5, 4)  # rational endpoints: 1/8 .. 5/4
# Several interior samples, both channels; final acceptance checks ALL samples.
PROBES = tuple(2*i+c for i in (128,257,397,521,719,911,1023,1103,1259,1427,1601,1801) for c in (0,1))


def pcm16(data):
    a = array.array('h'); a.frombytes(data)
    if sys.byteorder != 'little': a.byteswap()
    return a


def read_atlas(path):
    a = pcm16(pathlib.Path(path).read_bytes())
    labels = [(tag,k,actor,t) for tag in (0,1) for k in range(1,6)
              for actor in (0,1) for t in range(256 if tag else 1)]
    if len(a) != len(labels)*N*2: raise ValueError('wrong atlas length')
    return [(label, a[i*N*2:(i+1)*N*2]) for i,label in enumerate(labels)]


def intersect(x,y,bound,indices):
    """Exact integer cross-products; no floating-point acceptance decision."""
    ln,ld,hn,hd = bound
    for i in indices:
        v,w = x[i],y[i]
        if v == 0:
            if abs(w)>EPS: return None
            continue
        if v<0: v,w=-v,-w
        a,b=w-EPS,w+EPS
        if a*ld>ln*v: ln,ld=a,v
        if b*hd<hn*v: hn,hd=b,v
        if ln*hd>hn*ld: return None
    return ln,ld,hn,hd


def decode(atlas, obs, tagged=None, gain=GAIN):
    if len(obs)!=N*2: raise ValueError('wrong pulse length')
    matches=[]
    for label,x in atlas:
        if tagged is not None and label[0]!=tagged: continue
        b=intersect(x,obs,gain,PROBES)
        if b is not None:
            b=intersect(x,obs,b,range(N*2))
            if b is not None: matches.append((label,b))
    return matches


def event_cycle(mode, count):
    """Independent symbolic oracle. Token starts at zero, actor alternates."""
    for token in range(count):
        a=token%2; t=token%256
        yield (1,a,t)
        if mode==0: yield (2,a^1,t)
        elif mode==1:
            yield None; yield (4,a,t); yield (2,a^1,t)
        elif mode==2:
            yield (3,a^1,t^1); yield (4,a,t); yield (2,a^1,t)
        elif mode==3: yield (2,a^1,t^1)
        elif mode==4:
            yield None; yield (4,a,t); yield None; yield (5,a,t)
        else: raise ValueError('invalid mode')


def groups(pcm,start,stop):
    # Split pulse groups on long exact-zero gaps, not short zero crossings.
    first=last=None
    for i in range(start,stop):
        if pcm[2*i] or pcm[2*i+1]:
            if last is not None and i-last>128:
                yield first,last; first=None
            if first is None: first=i
            last=i
    if first is not None: yield first,last


def capture(atlas,prefix,mode,rate=26):
    """Strict test of modeled PCM from a fresh boot, selected panel mode, PLAY/HOME.
    No skipped prefix events; only an incomplete final pulse may be excluded.
    """
    p=pathlib.Path(prefix)
    raw=p.with_suffix('.pcm').read_bytes(); pcm=pcm16(raw)
    b=list(map(int,p.with_suffix('.bounds').read_text().split()))
    if len(b)!=4 or any(v%2 for v in b) or not 0<=b[0]<b[1]<=b[2]<b[3]==len(pcm):
        raise ValueError('bad stereo boundaries')
    start,stop,tail,end=[v//2 for v in b]
    if any(pcm[:2*start]) or any(pcm[2*tail:]): raise ValueError('boot or mute is nonzero')
    gs=list(groups(pcm,start,stop)); period=12000-rate*200
    tagged=int(mode>=5)
    # Last group can be truncated by capture cutoff; require all prior pulses.
    if gs and gs[-1][0]+N>stop: gs.pop()
    if not gs: raise ValueError('no complete pulses')
    # Decode all feasible integer offsets near first nonzero (attack starts at zero).
    # Enforce shared gain and absolute timing; report ambiguity rather than guessing.
    possibilities=[]
    for offset in range(1,5):
        base=gs[0][0]-offset
        if not start<=base<=start+RATE//5: continue
        gain=GAIN; labels=[]; ok=True
        for first,last in gs:
            tick=(first-base+period//2)//period
            onset=base+tick*period
            if not (onset<=first<=onset+4 and last<onset+N and onset+N<=stop): ok=False; break
            m=decode(atlas,pcm[2*onset:2*(onset+N)],tagged,gain)
            if len(m)!=1: ok=False; break
            label,gain=m[0]; labels.append((tick,label))
        if ok:
            # Require exact silence outside pulse windows (including unobserved complete ticks).
            oracle=list(event_cycle(mode%5,128))
            observed=dict(labels)
            for tick in range((stop-base-N)//period+1):
                e=oracle[tick]; expected=None if e is None else (tagged,e[0],e[1],e[2] if tagged else 0)
                if observed.get(tick)!=expected: ok=False; break
            if ok and len(labels)>=8 and len(observed)==len(labels) and all(0<=tick<=(stop-base-N)//period for tick,_ in labels): possibilities.append((base,gain,labels))
    if len(possibilities)!=1: raise ValueError(f'mode {mode} compatible sequences={len(possibilities)}')
    base,g,labels=possibilities[0]
    print(f'mode={mode} pulses={len(labels)} onset={base} gain={Fraction(g[0],g[1])}..{Fraction(g[2],g[3])} sha256={hashlib.sha256(raw).hexdigest()} PASS')
    return labels


def selftest(atlas):
    # All 2560 tagged labels under two gains; full exact template check and search.
    for i,(label,x) in enumerate(atlas[10:]):
        num,den=((385,1000) if i%2 else (1,1))
        y=array.array('h',(int(v*num/den) for v in x))
        m=decode(atlas,y,1)
        assert len(m)==1 and m[0][0]==label,(label,m)
    # Token omitted in legacy: only ten labels in atlas, no claim of token recovery.
    for label,x in atlas[:10]:
        m=decode(atlas,x,0); assert len(m)==1 and m[0][0]==label
    # Strong arbitrary defect and out-of-contract gain; no nearest-codeword forcing.
    label,x=atlas[10+123]
    y=array.array('h',x); y[999]=30000
    assert not decode(atlas,y,1)
    assert not decode(atlas,array.array('h',(int(v/32) for v in x)),1)
    print('native labels=2560 tagged + 10 legacy; alternate gains; 2 negative controls PASS')


if __name__=='__main__':
    atlas=read_atlas(sys.argv[1])
    if sys.argv[2]=='--selftest': selftest(atlas)
    else: capture(atlas,sys.argv[2],int(sys.argv[3]),int(sys.argv[4]) if len(sys.argv)>4 else 26)
