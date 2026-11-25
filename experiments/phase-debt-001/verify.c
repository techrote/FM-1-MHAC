#include "phase_debt.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned pop(unsigned m){unsigned n=0;while(m){n++;m&=m-1;}return n;}
static void le(FILE *f,unsigned x,unsigned n){while(n--){fputc(x&255,f);x>>=8;}}
int main(void){
    unsigned cases=0; long fixed=0,moving=0;
    for(unsigned a=0;a<=64;a++) for(unsigned b=0;b<=64;b++){
        pd_state s;pd_reset(&s,PD_STAGGERED);unsigned total=0,C=0;
        for(unsigned i=0;i<64;i++){unsigned x=i%2?a:b;C+=x;total+=pop(pd_tick(&s,x,0));assert(total==8*C/64);cases++;}
    }
    for(unsigned mode=2;mode<=3;mode++){
        pd_state s;pd_reset(&s,mode);long sum=0;
        for(unsigned i=0;i<64;i++)sum+=pop(pd_tick(&s,8,0));
        if(mode==2)fixed=sum;else moving=sum;
    }
    assert(fixed==56&&moving==0);
    /* Exact block-partition invariance for constant commands. */
    int32_t a[2048]={0},b[2048]={0};pd_state s,t;pd_reset(&s,1);pd_reset(&t,1);
    pd_render(&s,a,1024,64,1,1);for(unsigned i=0;i<1024;i++)pd_render(&t,b+2*i,1,64,1,1);
    assert(!memcmp(a,b,sizeof a));
    FILE *f=fopen("phase-debt.wav","wb");assert(f);unsigned frames=PD_FS*8;
    fwrite("RIFF",1,4,f);le(f,36+frames*4,4);fwrite("WAVEfmt ",1,8,f);le(f,16,4);le(f,1,2);le(f,2,2);le(f,PD_FS,4);le(f,PD_FS*4,4);le(f,4,2);le(f,16,2);fwrite("data",1,4,f);le(f,frames*4,4);
    pd_reset(&s,0);int peak=0;
    for(unsigned i=0;i<frames;i++){
        int32_t out[2]={0};unsigned mode=i/(PD_FS*2);pd_render(&s,out,1,24,mode,1);
        for(unsigned j=0;j<2;j++){assert(abs(out[j])<=6400);if(abs(out[j])>peak)peak=abs(out[j]);le(f,(uint16_t)out[j],2);}
    }
    assert(!fclose(f));
    for(unsigned i=0;i<1000;i++){int32_t out[2]={0};pd_render(&s,out,1,64,3,0);if(i>=800)assert(!out[0]&&!out[1]);}
    printf("carry_checks=%u fixed=%ld moving=%ld block_invariance=PASS mute=PASS peak=%d state_bytes=%zu\n",cases,fixed,moving,peak,sizeof(pd_state));
    return 0;
}
