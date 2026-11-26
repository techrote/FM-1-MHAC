#include "receipt_loom.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void le(FILE *f,uint32_t v,unsigned n){while(n--){fputc((int)(v&255u),f);v>>=8;}}
int main(void){
    static const uint8_t expected[RL_MODES][5]={{1,2},{1,0,4,2},{1,3,4,2},{1,2},{1,0,4,0,5}};
    static const unsigned length[RL_MODES]={2,4,4,2,5};
    unsigned transactions=0, stale_accept=0, peak=0;
    for(unsigned m=0;m<RL_MODES;m++){
        rl_world w={0};
        for(unsigned t=0;t<512;t++){
            unsigned actor=w.actor,token=w.token;
            for(unsigned j=0;j<length[m];j++){
                rl_event e=rl_tick(&w,m);
                assert(e.kind==expected[m][j]);
                assert(w.age<=4&&w.attempt<=1);
                if(e.kind==RL_ACK){
                    assert(e.actor==(actor^1u));
                    if(e.token!=token){assert(m==RL_STALE_LATEST);++stale_accept;}
                    else assert(m!=RL_STALE_LATEST);
                }
            }
            assert(w.stage==0&&w.actor==(actor^1u)&&w.token==(uint8_t)(token+1u));
            ++transactions;
        }
    }
    FILE *f=fopen("receipt-loom.wav","wb");assert(f);
    enum { N=44100*3, TOTAL=N*RL_MODES };
    fwrite("RIFF",1,4,f);le(f,36+TOTAL*4,4);fwrite("WAVEfmt ",1,8,f);
    le(f,16,4);le(f,1,2);le(f,2,2);le(f,RL_FS,4);le(f,RL_FS*4,4);le(f,4,2);le(f,16,2);
    fwrite("data",1,4,f);le(f,TOTAL*4,4);
    for(unsigned m=0;m<RL_MODES;m++){
        rl_state a={0},b={0};
        for(unsigned i=0;i<N;){
            int32_t x[512]={0},y[512]={0};
            unsigned n=N-i<256?N-i:256;
            unsigned run=i<N-4096;
            rl_render(&a,x,n,12,m,run);
            for(unsigned j=0;j<n;j++)rl_render(&b,y+2*j,1,12,m,run);
            assert(!memcmp(x,y,2*n*sizeof *x));
            for(unsigned j=0;j<2*n;j++){
                unsigned p=(unsigned)(x[j]<0?-x[j]:x[j]);
                assert(p<=2048);if(p>peak)peak=p;
                if(i>=N-2048)assert(!p);
                le(f,(uint16_t)x[j],2);
            }
            i+=n;
        }
        assert(!a.env&&!b.env);
    }
    assert(!fclose(f));
    printf("transactions=%u wrong_token_accepts=%u frames=%u peak=%u state_bytes=%zu block_partition=PASS mute=PASS\n",transactions,stale_accept,TOTAL,peak,sizeof(rl_state));
}
