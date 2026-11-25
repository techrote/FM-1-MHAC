/* Host panel-equivalent fixture: no device I/O. */
#include "redundant_core.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static void render(rr_state *s,unsigned n,unsigned mode,unsigned run){
    while(n--){int32_t x[2]={0};rr_render(s,x,1,26,mode,run);
        for(unsigned j=0;j<2;j++){uint16_t v=(uint16_t)(x[j]*385/1000);assert(fputc(v&255,stdout)!=EOF);assert(fputc(v>>8,stdout)!=EOF);}}
}
int main(int argc,char **argv){assert(argc==2);unsigned mode=(unsigned)atoi(argv[1]);assert(mode<5);rr_state s={0};
    render(&s,4410+97,mode,0);render(&s,110250,mode,1);render(&s,8820,mode,0);render(&s,4410,mode,0);
    fprintf(stderr,"%u %u %u %u\n",8820u,2u*(4507+110250),2u*(4507+110250+8820),2u*(4507+110250+8820+4410));return fflush(stdout)!=0;}
