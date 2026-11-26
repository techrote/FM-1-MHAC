/* Deterministic metamorphic audio stress, original FM1-001 source. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "phase_debt.h"
#define MAX_FRAMES 1024u
static uint32_t rng=0x91adf145u;
static uint32_t draw(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void equal_state(const pd_state *a,const pd_state *b){
    assert(a->mode==b->mode && a->running==b->running && a->until==b->until);
    for(unsigned j=0;j<8;j++){
        assert(a->phase[j]==b->phase[j] && a->envelope[j]==b->envelope[j]);
        assert(a->residue[j]==b->residue[j] && a->residue[j]<64u);
        assert(a->envelope[j]<=800u);
    }
}
int main(void){
    pd_state a,b; pd_reset(&a,1); pd_reset(&b,1);
    int32_t whole[2*MAX_FRAMES+2],split[2*MAX_FRAMES+2];
    uint64_t frames=0,parts=0; unsigned peak=0, mute_checks=0;
    for(unsigned trial=0;trial<12000;trial++){
        unsigned n=1u+draw()%MAX_FRAMES, density=draw()%128u;
        unsigned mode=draw()%4u, run=draw()%2u;
        if(trial%17u==0){n=MAX_FRAMES;run=0;mute_checks++;}
        memset(whole,0,sizeof whole);memset(split,0,sizeof split);
        whole[0]=split[0]=0x12345678;whole[2*n+1]=split[2*n+1]=0x23456789;
        pd_render(&a,whole+1,n,density,mode,run);
        for(unsigned pos=0;pos<n;){
            unsigned k=1u+draw()%127u;if(k>n-pos)k=n-pos;
            pd_render(&b,split+1+2*pos,k,density,mode,run);pos+=k;parts++;
        }
        assert(whole[0]==0x12345678 && whole[2*n+1]==0x23456789);
        assert(split[0]==0x12345678 && split[2*n+1]==0x23456789);
        assert(!memcmp(whole+1,split+1,2*n*sizeof(int32_t)));
        equal_state(&a,&b);
        for(unsigned j=0;j<2*n;j++){
            int32_t v=whole[j+1];assert(v>=-6400 && v<=6400);
            unsigned mag=(unsigned)(v<0?-v:v);if(mag>peak)peak=mag;
            if(!run && j>=1600u)assert(v==0);
        }
        frames+=n;
    }
    printf("transitions=12000 frames=%llu split_calls=%llu full_mute_checks=%u peak=%u state_bytes=%zu\n",
        (unsigned long long)frames,(unsigned long long)parts,mute_checks,peak,sizeof a);
    return 0;
}
