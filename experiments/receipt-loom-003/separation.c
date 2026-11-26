/* Finite pair separation screen, same known family and exact sample alignment.
 * If observations agree within 2 units at gains a,b in [1/8,5/4],
 * necessarily |x - (b/a)z| <=32 with b/a in [1/10,10].
 * Infeasibility certifies separation; feasibility is inconclusive. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
enum { S=4096, TAGGED=2560, LEGACY=10 };
static int16_t atlas[TAGGED+LEGACY][S];
typedef struct {int32_t ln,ld,hn,hd;} interval;
static int constrain(interval *g,int32_t x,int32_t z){
    if(!z) return x>=-32&&x<=32;
    if(z<0){x=-x;z=-z;}
    int32_t lo=x-32,hi=x+32;
    if((int64_t)lo*g->ld>(int64_t)g->ln*z){g->ln=lo;g->ld=z;}
    if((int64_t)hi*g->hd<(int64_t)g->hn*z){g->hn=hi;g->hd=z;}
    return (int64_t)g->ln*g->hd<=(int64_t)g->hn*g->ld;
}
static int compatible(const int16_t *x,const int16_t *z){
    static const unsigned probes[]={128,257,397,521,719,911,1023,1103,1259,1427,1601,1801};
    interval g={1,10,10,1};
    for(unsigned j=0;j<sizeof probes/sizeof *probes;j++)for(unsigned c=0;c<2;c++){
        unsigned i=2*probes[j]+c;if(!constrain(&g,x[i],z[i]))return 0;
    }
    for(unsigned i=0;i<S;i++)if(!constrain(&g,x[i],z[i]))return 0;
    return 1;
}
int main(int argc,char **argv){
    assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);
    for(unsigned k=0;k<TAGGED+LEGACY;k++)for(unsigned i=0;i<S;i++){
        int lo=fgetc(f),hi=fgetc(f);assert(lo!=EOF&&hi!=EOF);
        int v=lo+256*hi; if(v>=32768)v-=65536;
        assert(v>=-2048&&v<=2048);atlas[k][i]=(int16_t)v;
    }
    assert(fgetc(f)==EOF&&!ferror(f));assert(!fclose(f));
    for(unsigned family=0;family<2;family++){
        unsigned begin=family?LEGACY:0,end=family?LEGACY+TAGGED:LEGACY;
        unsigned pairs=0,inconclusive=0;
        for(unsigned i=begin;i<end;i++)for(unsigned j=i+1;j<end;j++){
            ++pairs;
            if(compatible(atlas[i],atlas[j])&&compatible(atlas[j],atlas[i])){
                ++inconclusive;
                if(inconclusive<=10)printf("inconclusive family=%u atlas_indices=%u,%u\n",family,i,j);
            }
        }
        printf("family=%u pairs=%u certified=%u inconclusive=%u\n",family,pairs,pairs-inconclusive,inconclusive);
    }
    /* Deliberate identical-template negative control cannot be certified. */
    assert(compatible(atlas[10],atlas[10]));puts("identical template control PASS");
}
