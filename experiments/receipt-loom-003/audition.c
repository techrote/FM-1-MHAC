/* Offline Receipt Loom renderer. Original core PCM, no hardware I/O or normalization. */
#include "redundant_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

enum { MAX_SEG=128, MAX_BLOCK=1024, MAX_FRAMES=120*RL_FS };
typedef struct { unsigned frames, mode, rate, play; } segment;
static int number(const char **p,unsigned max,unsigned *v){
    unsigned n=0; const char *s=*p;
    if(*s<'0'||*s>'9')return 0;
    do { unsigned d=(unsigned)(*s-'0');
        if(d>max || n>(max-d)/10u)return 0;
        n=n*10u+d; ++s;
    }while(*s>='0'&&*s<='9');
    *p=s; *v=n; return 1;
}
static int parse(const char *p,segment *s){
    return number(&p,MAX_FRAMES,&s->frames)&&s->frames>0&&*p++==':'&&
        number(&p,4,&s->mode)&&*p++==':'&&number(&p,26,&s->rate)&&*p++==':'&&
        number(&p,1,&s->play)&&!*p;
}
static int put(FILE *f,uint32_t x,unsigned bytes){
    for(unsigned i=0;i<bytes;i++)if(fputc((int)((x>>(8u*i))&255u),f)==EOF)return 0;
    return 1;
}
static int header(FILE *f,unsigned n){
    return fwrite("RIFF",1,4,f)==4&&put(f,36u+4u*n,4)&&fwrite("WAVEfmt ",1,8,f)==8&&
        put(f,16,4)&&put(f,1,2)&&put(f,2,2)&&put(f,RL_FS,4)&&put(f,4u*RL_FS,4)&&
        put(f,4,2)&&put(f,16,2)&&fwrite("data",1,4,f)==4&&put(f,4u*n,4);
}
static int render(FILE *f, int family, unsigned block,rl_state *a,rr_state *b,segment s){
    while(s.frames){
        unsigned n=s.frames<block?s.frames:block;
        int32_t x[2*MAX_BLOCK]={0};
        if(family==2)rr_render(b,x,n,s.rate,s.mode,s.play);
        else rl_render(a,x,n,s.rate,s.mode+(family==1?RL_MODES:0),s.play);
        for(unsigned i=0;i<2*n;i++){
            if(x[i]<-2048||x[i]>2048||!put(f,(uint16_t)x[i],2))return 0;
        }
        s.frames-=n;
    }
    return 1;
}
int main(int argc,char **argv){
    if(argc<5||argc>4+MAX_SEG)goto usage;
    int family=!strcmp(argv[1],"legacy")?0:!strcmp(argv[1],"tagged")?1:!strcmp(argv[1],"redundant")?2:-1;
    const char *p=argv[2]; unsigned block;
    if(family<0||!number(&p,MAX_BLOCK,&block)||*p||!block)goto usage;
    segment seg[MAX_SEG]; unsigned count=(unsigned)(argc-4), total=RL_ENV;
    for(unsigned i=0;i<count;i++){
        if(!parse(argv[4+i],&seg[i])||seg[i].frames>MAX_FRAMES-total)goto usage;
        total+=seg[i].frames;
    }
    FILE *f=fopen(argv[3],"wb");if(!f){perror("output");return 1;}
    rl_state a={0};rr_state b={0};int ok=header(f,total);
    for(unsigned i=0;ok&&i<count;i++)ok=render(f,family,block,&a,&b,seg[i]);
    segment tail={RL_ENV,seg[count-1].mode,seg[count-1].rate,0};
    if(ok)ok=render(f,family,block,&a,&b,tail);
    if(fclose(f)!=0)ok=0;
    if(!ok){fprintf(stderr,"render/write failed; output incomplete\n");return 1;}
    fprintf(stderr,"frames=%u rl_state=%zu rr_state=%zu\n",total,sizeof(a),sizeof(b));return 0;
usage:
    fprintf(stderr,"usage: audition legacy|tagged|redundant BLOCK OUT.wav FRAMES:MODE:RATE:PLAY [...]\n");return 2;
}
