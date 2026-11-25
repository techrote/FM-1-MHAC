/* Original host-only pulse atlas: all 256 masks through the actual DSP. */
#include <stdio.h>
#include "phase_debt.h"
int main(void) {
    for (unsigned mask=0;mask<256;mask++) {
        pd_state s; int32_t out[1600]={0};
        pd_reset(&s,PD_STAGGERED);
        for(unsigned j=0;j<8;j++) s.residue[j]=(mask&(1u<<j))?63:0;
        pd_render(&s,out,800,1,PD_STAGGERED,1);
        for(unsigned i=0;i<1600;i++) {
            if(out[i]<-6400||out[i]>6400) return 1;
            unsigned v=(uint16_t)out[i];
            if(putchar(v&255)==EOF||putchar(v>>8)==EOF) return 2;
        }
    }
    return fflush(stdout)!=0;
}
