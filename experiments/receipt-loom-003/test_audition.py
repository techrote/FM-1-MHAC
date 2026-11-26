#!/usr/bin/env python3
"""Compile pinned cores locally; generate original PCM fixtures and exact tests."""
import hashlib
import pathlib
import struct
import subprocess
import tempfile
import wave
import sys

HERE = pathlib.Path(__file__).resolve().parent
FAMILIES = ('legacy', 'tagged', 'redundant')
MODES = ('clean', 'first-loss', 'stale-bound', 'stale-latest', 'blackout')
ENV = 2048

def pcm(path):
    with wave.open(str(path), 'rb') as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (2, 2, 44100)
        b = w.readframes(w.getnframes())
        assert len(b) == 4*w.getnframes()
    assert path.stat().st_size == 44+len(b)
    return b

def run(exe, path, family, block, *segments):
    p = subprocess.run([str(exe), family, str(block), str(path), *segments], capture_output=True, text=True, check=True)
    data = pcm(path)
    frames = sum(int(s.split(':')[0]) for s in segments)+ENV
    assert len(data) == 4*frames
    peak = max(abs(x[0]) for x in struct.iter_unpack('<h', data))
    assert peak <= 2048
    return data, peak, p.stderr.strip()

def main(out):
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td)
        exes=[]
        for cc in ('gcc','clang'):
            exe=t/cc
            subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all',str(HERE/'audition.c'),'-o',str(exe)],check=True)
            print(subprocess.check_output([cc,'--version'],text=True).splitlines()[0])
            exes.append(exe)
        data={}
        for family in FAMILIES:
            for mode,name in enumerate(MODES):
                path=out/f'{family}-{name}.wav'
                args=('4410:0:12:0',f'176400:{mode}:26:1',f'4410:{mode}:26:0')
                raw,peak,info=run(exes[0],path,family,257,*args)
                assert not any(raw[:4410*4]) and not any(raw[-ENV*4:]) and peak>0
                for exe,block in [(exes[0],1),(exes[0],1024),(exes[1],257)]:
                    assert run(exe,t/'tmp.wav',family,block,*args)[0]==raw
                data[family,mode]=raw
                print(f'{path.name}: {info} peak={peak} sha256={hashlib.sha256(path.read_bytes()).hexdigest()}')
            assert (data[family,0]==data[family,3]) == (family=='legacy')
            assert len({data[family,m] for m in range(5)}) == (4 if family=='legacy' else 5)
            # Interrupt an active pulse, wait through mute, restart at a new tempo,
            # change mode while running, and stop again. No hidden gain or fades.
            args=('777:0:26:1','4096:0:26:0','120000:0:12:1','80000:2:0:1','60000:4:26:1','4096:4:26:0')
            raw,peak,info=run(exes[0],out/f'{family}-performance.wav',family,257,*args)
            assert not any(raw[(777+ENV)*4:(777+4096)*4])
            assert not any(raw[-ENV*4:])
            for exe,block in [(exes[0],1),(exes[0],1024),(exes[1],257)]:
                assert run(exe,t/'tmp.wav',family,block,*args)[0]==raw
            print(f'{family}-performance.wav: {info} peak={peak} transition/mute PASS')
        invalid=[('bad','257','1:0:0:1'),('legacy','0','1:0:0:1'),('legacy','1025','1:0:0:1'),('legacy','+1','1:0:0:1'),('legacy','1','0:0:0:1'),('legacy','1','1:5:0:1'),('legacy','1','1:0:27:1'),('legacy','1','1:0:0:2'),('legacy','1','1:0:0:'),('legacy','1','1:0:0:1x'),('legacy','1','1:0:0'),('legacy','1','-1:0:0:1'),('legacy','1','5292000:0:0:1'),('legacy','1','999999999999999999:0:0:1')]
        for family,block,seg in invalid:
            p=t/'bad.wav'
            assert subprocess.run([str(exes[0]),family,block,str(p),seg],capture_output=True).returncode==2 and not p.exists()
        print('PASS: 15 fixed-mode and 3 transition fixtures; 54 exact alternate block/compiler comparisons; 14 malformed inputs; 3 alias/class checks.')
    
if __name__=='__main__':
    main(pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'wav')
