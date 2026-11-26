/* FM1-003 host audition for the existing portable Scope Weave core.
 * Not a target image, physical panel simulation, DAC capture or human study.
 * Build: cc -std=c11 -O2 -Wall -Wextra -Werror audition.c -o audition
 * Usage: audition OUT.wav FRAMES:PRESET:MODE:RATE:RUN [...]
 * Preset 0..26, mode 0 ordered / 1 sorted / 2 leaf, rate 0..26, run 0/1.
 * Frame unit 1/44100 s. Segments are continuous; an automatic stop/tail
 * is appended. PCM is unchanged core amplitude, no normalization.
 * Example: audition scope.wav 57600:3:0:26:1 57600:9:0:26:1
 * Output must not already exist. Limits: 128 segments, 120 s plus tail.
 */
#include "scope_weave.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { BLOCK=257, MAX_SEG=128, MAX_FRAMES=120*SW_FS, TAIL=SW_ENV+256 };
typedef struct { unsigned frames,preset,mode,rate,run; } segment;
static int number(const char **s,unsigned limit,unsigned *v){
    unsigned n=0;const char *p=*s;
    if(*p<'0'||*p>'9')return 0;
    do { unsigned d=(unsigned)(*p-'0');
        if(d>limit||n>(limit-d)/10u)return 0;
        n=10u*n+d;++p;
    } while(*p>='0'&&*p<='9');
    *s=p;*v=n;return 1;
}
static int parse(const char *p,segment *s){
    unsigned *fields[]={&s->frames,&s->preset,&s->mode,&s->rate,&s->run};
    const unsigned limits[]={MAX_FRAMES,SW_PRESETS-1,SW_MODES-1,26,1};
    for(unsigned i=0;i<5;i++){
        if(!number(&p,limits[i],fields[i]))return 0;
        if(i!=4){if(*p!=':')return 0;++p;}
    }
    return !*p&&s->frames!=0;
}
static int le(FILE *f,uint32_t x,unsigned n){
    for(unsigned i=0;i<n;i++){if(fputc((int)(x&255u),f)==EOF)return 0;x>>=8;}
    return 1;
}
static int header(FILE *f,unsigned frames){
    return fwrite("RIFF",1,4,f)==4&&le(f,36u+4u*frames,4)&&
        fwrite("WAVEfmt ",1,8,f)==8&&le(f,16,4)&&le(f,1,2)&&le(f,2,2)&&
        le(f,SW_FS,4)&&le(f,SW_FS*4u,4)&&le(f,4,2)&&le(f,16,2)&&
        fwrite("data",1,4,f)==4&&le(f,4u*frames,4);
}
static int render(FILE *f,sw_state *state,segment s,unsigned *peak,int tail){
    int32_t out[2*BLOCK];unsigned done=0;
    while(done<s.frames){
        unsigned n=s.frames-done;if(n>BLOCK)n=BLOCK;
        memset(out,0,sizeof out);
        sw_render(state,out,n,s.preset,s.mode,s.rate,s.run);
        for(unsigned j=0;j<2*n;j++){
            int32_t x=out[j];
            if(x < -2048||x > 2048||(tail&&done+j/2>=SW_ENV&&x))return 0;
            unsigned a=(unsigned)(x<0?-x:x);if(a>*peak)*peak=a;
            if(!le(f,(uint16_t)x,2))return 0;
        }
        done+=n;
    }
    return 1;
}
int main(int argc,char **argv){
    segment s[MAX_SEG];unsigned frames=0,peak=0;
    if(argc<3||argc>MAX_SEG+2){fputs("usage: audition OUT.wav FRAMES:PRESET:MODE:RATE:RUN [...]\n",stderr);return 2;}
    for(int i=2;i<argc;i++){
        if(!parse(argv[i],&s[i-2])||s[i-2].frames>MAX_FRAMES-frames){
            fprintf(stderr,"invalid segment %d or duration limit\n",i-1);return 2;
        }
        frames+=s[i-2].frames;
    }
    FILE *f=fopen(argv[1],"wbx");if(!f){perror("output (must be new)");return 1;}
    sw_state state={0};int ok=header(f,frames+TAIL);
    for(int i=2;i<argc&&ok;i++)ok=render(f,&state,s[i-2],&peak,0);
    segment tail=s[argc-3];tail.frames=TAIL;tail.run=0;
    if(ok)ok=render(f,&state,tail,&peak,1)&&!state.env;
    if(fclose(f))ok=0;
    if(!ok){remove(argv[1]);fputs("render or output failure; incomplete output removed if possible\n",stderr);return 1;}
    fprintf(stderr,"host PCM frames=%u tail=%u peak=%u state_bytes=%zu\n",frames+TAIL,TAIL,peak,sizeof state);
    return 0;
}
