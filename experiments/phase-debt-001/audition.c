/* Offline Phase Debt audition renderer. No device or upstream dependencies. */
#include "phase_debt.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { MAX_SEG=128, MAX_BLOCK=1024, TAIL=800, LIMIT=120*PD_FS };
typedef struct { unsigned frames, density, mode, play; } segment;
static int number(const char **p, unsigned max, unsigned *out) {
    unsigned n=0;
    if (**p<'0'||**p>'9') return 0;
    while (**p>='0'&&**p<='9') {
        unsigned d=(unsigned)(**p-'0');
        if(d>max || n>(max-d)/10u) return 0;
        n=n*10u+d; ++*p;
    }
    *out=n; return 1;
}
static int parse(const char *p, segment *s) {
    return number(&p,LIMIT,&s->frames)&&s->frames&&*p++==':'&&
        number(&p,64,&s->density)&&*p++==':'&&number(&p,3,&s->mode)&&
        *p++==':'&&number(&p,1,&s->play)&&!*p;
}
static void le(FILE *f, uint32_t v, unsigned n) {
    while(n--){ fputc((int)(v&255u),f); v>>=8; }
}
static int render(FILE *f,pd_state *s,segment c,unsigned block) {
    int32_t pcm[2*MAX_BLOCK];
    while(c.frames){
        unsigned n=c.frames<block?c.frames:block;
        memset(pcm,0,n*2*sizeof *pcm);
        pd_render(s,pcm,n,c.density,c.mode,c.play);
        for(unsigned i=0;i<2*n;i++){
            if(pcm[i]< -6400||pcm[i]>6400) return 0;
            le(f,(uint16_t)pcm[i],2);
        }
        if(ferror(f))return 0;
        c.frames-=n;
    }
    return 1;
}
int main(int argc,char **argv) {
    segment seg[MAX_SEG]; unsigned total=0,block=0;
    if(argc<4||argc>3+MAX_SEG) goto usage;
    const char *p=argv[1];
    if(!number(&p,MAX_BLOCK,&block)||!block||*p) goto usage;
    for(int i=3;i<argc;i++){
        if(!parse(argv[i],&seg[i-3])||seg[i-3].frames>LIMIT-total)goto usage;
        total+=seg[i-3].frames;
    }
    /* Exclusive creation prevents accidental overwrite, including input files. */
    FILE *f=fopen(argv[2],"wbx");
    if(!f){perror(argv[2]);return 1;}
    uint32_t bytes=(total+TAIL)*4u;
    fwrite("RIFF",1,4,f);le(f,36u+bytes,4);fwrite("WAVEfmt ",1,8,f);
    le(f,16,4);le(f,1,2);le(f,2,2);le(f,PD_FS,4);le(f,PD_FS*4,4);
    le(f,4,2);le(f,16,2);fwrite("data",1,4,f);le(f,bytes,4);
    pd_state s;pd_reset(&s,seg[0].mode);
    int ok=!ferror(f);
    for(int i=3;i<argc&&ok;i++)ok=render(f,&s,seg[i-3],block);
    segment tail=seg[argc-4];tail.frames=TAIL;tail.play=0;
    if(ok)ok=render(f,&s,tail,block);
    if(fclose(f))ok=0;
    if(!ok){fprintf(stderr,"render failed; output incomplete\n");return 1;}
    return 0;
usage:
    fprintf(stderr,"usage: audition BLOCK NEW.wav FRAMES:DENSITY:MODE:PLAY [...]\n");return 2;
}
