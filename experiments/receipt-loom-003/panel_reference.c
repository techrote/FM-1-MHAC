/* Native synthetic capture fixture; not emulation or physical device evidence. */
#include "receipt_loom.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv){
    assert(argc==2); unsigned mode=(unsigned)atoi(argv[1]); assert(mode<10);
    rl_state s={0}; int32_t x[2]={0};
    /* 100 ms stopped, 2.5 s play, 300 ms mute; shift by 97 frames. */
    unsigned start=4410,stop=start+110250,tail=stop+7938,end=tail+6615;
    fprintf(stderr,"%u %u %u %u\n",2*start,2*stop,2*tail,2*end);
    for(unsigned i=0;i<end;i++){
        x[0]=x[1]=0; rl_render(&s,x,1,26,mode,i>=start+97 && i<stop);
        for(unsigned c=0;c<2;c++){
            uint16_t u=(uint16_t)(x[c]*385/1000);
            assert(fputc(u&255,stdout)!=EOF);assert(fputc(u>>8,stdout)!=EOF);
        }
    }
    assert(!fflush(stdout));
}
