#!/usr/bin/env python3
"""Small deterministic WAV receipt for emulator qualification."""
from __future__ import annotations
import argparse, hashlib, json, math, wave
from array import array
from pathlib import Path

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("wav",type=Path)
    ap.add_argument("--silent-tail-ms",type=int,default=0)
    ap.add_argument("--require-audio",action="store_true")
    ns=ap.parse_args()
    blob=ns.wav.read_bytes()
    with wave.open(str(ns.wav),"rb") as w:
        ch,sw,rate,n=w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes()
        if (ch,sw,rate)!=(2,2,44100):
            raise SystemExit(f"unexpected WAV format channels={ch} width={sw} rate={rate}")
        pcm=w.readframes(n)
    a=array("h"); a.frombytes(pcm)
    peak=max((abs(x) for x in a),default=0)
    nz=[i//2 for i,x in enumerate(a) if x]
    first=min(nz) if nz else None
    last=max(nz) if nz else None
    if ns.require_audio and not nz:
        raise SystemExit("no non-zero audio")
    tail_frames=(rate*ns.silent_tail_ms)//1000
    if tail_frames:
        start=max(0,n-tail_frames)
        if any(a[2*start:]):
            raise SystemExit(f"last {ns.silent_tail_ms} ms are not silent")
    rms=math.sqrt(sum(float(x)*x for x in a)/len(a)) if a else 0.0
    print(json.dumps({
        "path":str(ns.wav),"sha256":hashlib.sha256(blob).hexdigest(),"frames":n,
        "seconds":n/rate,"peak":peak,"rms":round(rms,6),
        "nonzero_frames":len(set(nz)),"first_nonzero_frame":first,"last_nonzero_frame":last,
        "silent_tail_ms":ns.silent_tail_ms
    },sort_keys=True))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
