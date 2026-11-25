/* Original native fixture for four density-seven modes; no platform assets. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <assert.h>
#include "phase_debt.h"
static void write16(FILE *f,int32_t x){
    assert(x>=-6400 && x<=6400);
    unsigned u=(uint16_t)x;
    assert(fputc(u&255u,f)!=EOF); assert(fputc(u>>8,f)!=EOF);
}
int main(void){
    const char *names[]={"aligned","staggered","fixed","moving"};
    const unsigned a=4608,b=a+90624,c=b+8192,d=c+6656;
    for(unsigned m=0;m<4;m++){
        char path[64]; snprintf(path,sizeof path,"%s.pcm",names[m]);
        FILE *f=fopen(path,"wb"); assert(f);
        pd_state s; pd_reset(&s,m);
        for(unsigned i=0;i<d;i+=256){
            int32_t out[512]={0};
            pd_render(&s,out,256,7,m,i>=a&&i<b);
            for(unsigned j=0;j<512;j++) write16(f,out[j]);
        }
        assert(fclose(f)==0);
        snprintf(path,sizeof path,"%s.bounds",names[m]);
        f=fopen(path,"w"); assert(f);
        fprintf(f,"%u %u %u %u\n",2*a,2*b,2*c,2*d); assert(fclose(f)==0);
    }
    printf("native frames per mode=%u state_bytes=%zu\n",d,sizeof(pd_state));
}
