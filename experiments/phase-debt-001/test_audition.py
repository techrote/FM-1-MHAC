"""Native fixture generation and deterministic comparison; no hardware claims."""
import array, hashlib, pathlib, subprocess, sys, tempfile, wave
ROOT = pathlib.Path(__file__).resolve().parent
FS = 44100
CASES = {f'{name}-{density}': [f'{FS*2}:{density}:{mode}:1']
         for mode,name in enumerate(('aligned','staggered','fixed','moving'))
         for density in (8,24)}
CASES['performance'] = ['4410:0:0:0','88200:24:0:1','88200:24:1:1',
                        '88200:8:2:1','88200:8:3:1','44100:64:1:1',
                        '113:64:1:0','137:32:2:1','4410:32:2:0']
BAD = [[], ['0:1:1:1'], ['1:65:0:1'], ['1:1:4:1'], ['1:1:1:2'],
       ['1:1:1:1x'], ['-1:1:1:1'], ['1: 1:1:1'], ['1:1:1'],
       ['99999999999999999999:1:1:1'], ['5292000:1:1:1','1:1:1:1'],
       ['1:1:1:1']*129]
def inspect(p,commands):
    with wave.open(str(p),'rb') as w:
        assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(2,2,FS)
        assert w.getnframes()==sum(int(c.split(':')[0]) for c in commands)+800
        a=array.array('h',w.readframes(w.getnframes()))
    if sys.byteorder!='little':a.byteswap()
    peak=max(map(abs,a)); assert peak<=6400
    assert not any(a[-2:])
    return peak,hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=pathlib.Path(sys.argv[1]);out.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory() as tmp:
        t=pathlib.Path(tmp); baseline={}; comparisons=0; bad=0
        for cc in ('gcc','clang'):
            print(subprocess.check_output([cc,'--version'],text=True).splitlines()[0])
            exe=t/cc
            subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror',
                            '-fsanitize=undefined','-fno-sanitize-recover=all',
                            str(ROOT/'audition.c'),'-o',str(exe)],check=True)
            for name,commands in CASES.items():
                for block in (1,257,1024):
                    p=t/f'{cc}-{name}-{block}.wav'
                    subprocess.run([str(exe),str(block),str(p),*commands],check=True)
                    peak,digest=inspect(p,commands)
                    if name not in baseline:
                        baseline[name]=digest
                        (out/f'{name}.wav').write_bytes(p.read_bytes())
                        print(name,peak,digest)
                    assert digest==baseline[name]; comparisons+=1
            for block,commands in [('257',c) for c in BAD]+[(b,['1:1:1:1']) for b in ('0','1025','+1','1x')]:
                p=t/'invalid.wav'
                r=subprocess.run([str(exe),block,str(p),*commands],capture_output=True)
                assert r.returncode==2 and not p.exists();bad+=1
            p=t/'existing.wav';p.write_bytes(b'keep')
            r=subprocess.run([str(exe),'257',str(p),'1:1:1:1'],capture_output=True)
            assert r.returncode==1 and p.read_bytes()==b'keep';bad+=1
        assert inspect(out/'moving-8.wav',CASES['moving-8'])[0]==0
        assert all(inspect(out/f'{n}.wav',CASES[n])[0]>0 for n in CASES if n!='moving-8')
        assert len(set(baseline.values()))==len(CASES)
        print(f'PASS fixtures={len(CASES)} executions={comparisons} invalid_or_overwrite={bad}')
if __name__=='__main__':main()
