#include "receipt_loom.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint32_t rng=0x8a12e65bu;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static uint64_t digest(const int32_t *p,unsigned n){
    uint64_t h=UINT64_C(14695981039346656037);
    for(unsigned i=0;i<n;i++){h^=(uint32_t)p[i];h*=UINT64_C(1099511628211);}
    return h;
}
static void le(FILE *f,uint32_t v,unsigned n){while(n--){fputc((int)(v&255u),f);v>>=8;}}
int main(void){
    static uint64_t hashes[2560];unsigned count=0,peak=0;
    for(unsigned k=RL_ASK;k<=RL_EXPIRE;k++)for(unsigned a=0;a<2;a++)for(unsigned t=0;t<256;t++){
        rl_state s={0};int32_t x[RL_ENV*2]={0};
        rl_trigger(&s,(rl_event){k,a,t},1);
        rl_render(&s,x,RL_ENV,12,0,0);
        assert(!s.env);
        uint64_t h=digest(x,RL_ENV*2);
        for(unsigned j=0;j<count;j++)assert(h!=hashes[j]);
        hashes[count++]=h;
    }
    static int32_t x[2048],y[2048];rl_state a={0},b={0};unsigned frames=0,parts=0;
    for(unsigned i=0;i<12000;i++){
        unsigned n=1+next()%1024,rate=next()%40,mode=next()%12,run=next()%4!=0;
        memset(x,0,sizeof x);memset(y,0,sizeof y);
        rl_render(&a,x,n,rate,mode,run);
        for(unsigned j=0;j<n;){unsigned m=1+next()%73;if(m>n-j)m=n-j;rl_render(&b,y+2*j,m,rate,mode,run);j+=m;parts++;}
        assert(!memcmp(x,y,n*2*sizeof *x));
        assert(!memcmp(&a.world,&b.world,sizeof a.world));
        assert(!memcmp(a.phase,b.phase,sizeof a.phase)&&!memcmp(a.inc,b.inc,sizeof a.inc));
        assert(a.until==b.until&&a.tail_inc==b.tail_inc&&a.env==b.env&&a.actor==b.actor&&a.running==b.running&&a.mode==b.mode);
        for(unsigned j=0;j<n*2;j++){unsigned p=(unsigned)(x[j]<0?-x[j]:x[j]);assert(p<=2048);if(p>peak)peak=p;}
        frames+=n;
    }
    memset(x,0,sizeof x);rl_render(&a,x,1024,12,9,0);
    memset(x,0,sizeof x);rl_render(&a,x,1024,12,9,0);assert(!a.env);
    memset(x,0,sizeof x);rl_render(&a,x,1024,12,9,0);assert(!a.env);
    for(unsigned j=0;j<2048;j++)assert(!x[j]);
    enum { N=44100*3,TOTAL=N*RL_MODES };
    FILE *f=fopen("receipt-witness.wav","wb");assert(f);
    fwrite("RIFF",1,4,f);le(f,36+TOTAL*4,4);fwrite("WAVEfmt ",1,8,f);
    le(f,16,4);le(f,1,2);le(f,2,2);le(f,RL_FS,4);le(f,RL_FS*4,4);le(f,4,2);le(f,16,2);fwrite("data",1,4,f);le(f,TOTAL*4,4);
    for(unsigned m=0;m<RL_MODES;m++){
        rl_state s={0};
        for(unsigned i=0;i<N;){unsigned n=N-i<256?N-i:256;memset(x,0,sizeof x);rl_render(&s,x,n,12,m+RL_MODES,i<N-4096);
            for(unsigned j=0;j<n*2;j++)le(f,(uint16_t)x[j],2);
            i+=n;
        }
    }
    assert(!fclose(f));
    printf("tagged_templates=%u distinct_digests=PASS transitions=12000 frames=%u partitions=%u peak=%u state_bytes=%zu mute=PASS\n",count,frames,parts,peak,sizeof(rl_state));
}
