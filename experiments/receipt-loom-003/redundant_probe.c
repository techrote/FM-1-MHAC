/* Native exhaustive atlas and transition test; no device I/O. */
#include "redundant_core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static uint32_t rng=42;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void wr(int32_t v){uint16_t u=(uint16_t)v;assert(fputc(u&255,stdout)!=EOF);assert(fputc(u>>8,stdout)!=EOF);}
static void bound(const int32_t *x,unsigned n){for(unsigned i=0;i<2*n;i++)assert(x[i]>=-2048&&x[i]<=2048);}
int main(int argc,char **argv){
    if(argc==2&&!strcmp(argv[1],"atlas")){
        for(unsigned k=RL_ASK;k<=RL_EXPIRE;k++)for(unsigned a=0;a<2;a++)for(unsigned t=0;t<256;t++){
            rr_state s={0};int32_t x[2*RL_ENV]={0};
            rr_trigger(&s,(rl_event){k,a,t});rr_render(&s,x,RL_ENV,12,0,0);
            bound(x,RL_ENV);assert(!memcmp(x,x+2*RR_HALF,2*RR_HALF*sizeof *x));
            for(unsigned i=0;i<2*RL_ENV;i++)wr(x[i]);
        }
        assert(!fflush(stdout));return 0;
    }
    if(argc==2&&!strcmp(argv[1],"demo")){
        for(unsigned m=0;m<RL_MODES;m++){
            rr_state s={0};
            for(unsigned i=0;i<3u*RL_FS;i++){int32_t x[2]={0};rr_render(&s,x,1,26,m,1);bound(x,1);wr(x[0]);wr(x[1]);}
        }
        assert(!fflush(stdout));return 0;
    }
    rr_state a={0},b={0};unsigned long frames=0,parts=0,mutes=0;
    for(unsigned k=0;k<12000;k++){
        unsigned n=1+next()%1100,rate=next()%27,mode=next()%5,run=next()%2;
        int32_t x[2200]={0},y[2200]={0};rr_render(&a,x,n,rate,mode,run);
        for(unsigned p=0;p<n;){unsigned len=1+next()%97;if(len>n-p)len=n-p;rr_render(&b,y+2*p,len,rate,mode,run);p+=len;++parts;}
        assert(!memcmp(x,y,2*n*sizeof *x));
        assert(a.world.actor==b.world.actor&&a.world.token==b.world.token&&a.world.stage==b.world.stage&&a.world.attempt==b.world.attempt&&a.world.age==b.world.age);
        assert(a.phase[0]==b.phase[0]&&a.phase[1]==b.phase[1]&&a.inc_event==b.inc_event&&a.inc_lo==b.inc_lo&&a.inc_hi==b.inc_hi&&a.until==b.until&&a.env==b.env&&a.actor==b.actor&&a.running==b.running&&a.mode==b.mode);
        bound(x,n);frames+=n;
        if(k%17==0){int32_t z[2*(RL_ENV+1)]={0},w[2*(RL_ENV+1)]={0};rr_render(&a,z,RL_ENV+1,rate,mode,0);rr_render(&b,w,RL_ENV+1,rate,mode,0);assert(!memcmp(z,w,sizeof z));assert(!a.env&&!b.env&&z[2*RL_ENV]==0&&z[2*RL_ENV+1]==0);bound(z,RL_ENV+1);++mutes;}
    }
    printf("transitions=12000 frames=%lu partitions=%lu mute_checks=%lu state_bytes=%zu PASS\n",frames,parts,mutes,sizeof a);
}
