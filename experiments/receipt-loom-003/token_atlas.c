/* Original host-only measurement fixture for Receipt Loom. No hardware I/O. */
#include "receipt_loom.h"
#include <stdio.h>
#include <assert.h>
static void write16(int32_t v){
    assert(v>=-2048 && v<=2048);
    uint16_t u=(uint16_t)v;
    assert(fputc(u&255,stdout)!=EOF); assert(fputc(u>>8,stdout)!=EOF);
}
int main(void){
    for(unsigned tagged=0;tagged<2;tagged++)
        for(unsigned k=RL_ASK;k<=RL_EXPIRE;k++)
            for(unsigned a=0;a<2;a++)
                for(unsigned t=0;t<(tagged?256u:1u);t++){
                    rl_state s={0}; int32_t x[RL_ENV*2]={0};
                    rl_trigger(&s,(rl_event){k,a,t},tagged);
                    rl_render(&s,x,RL_ENV,12,0,0);
                    for(unsigned i=0;i<RL_ENV*2;i++) write16(x[i]);
                }
    assert(!fflush(stdout));
}
