/* Host-only certificate for known sample erasures in Receipt Loom tagged motifs.
 * An erased sample is absent, not a measured zero. For any common observation
 * with independent gains a,b in [1/8,5/4] and errors <=2, each surviving sample
 * must satisfy |x-(b/a)z|<=32, 1/10<=b/a<=10, and the reverse constraint.
 * Infeasible => separated. Feasible => inconclusive, not necessarily a collision.
 * Identical surviving vectors are exact collisions (choose gain 1, error 0).
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
enum { N=2048, S=2*N, K=2560, LEGACY=10 };
static int16_t atlas[K][S], projected[K][S];
typedef struct {int32_t ln,ld,hn,hd;} interval;
static int constrain(interval *g,int32_t x,int32_t z){
    if(!z) return x>=-32&&x<=32;
    if(z<0){x=-x;z=-z;}
    int32_t lo=x-32,hi=x+32;
    if((int64_t)lo*g->ld>(int64_t)g->ln*z){g->ln=lo;g->ld=z;}
    if((int64_t)hi*g->hd<(int64_t)g->hn*z){g->hn=hi;g->hd=z;}
    return (int64_t)g->ln*g->hd<=(int64_t)g->hn*g->ld;
}
static int compatible(const int16_t *x,const int16_t *z,unsigned n){
    interval g={1,10,10,1};
    for(unsigned j=1;j<=24;j++){
        unsigned i=j*n/25;
        if(!constrain(&g,x[i],z[i]))return 0;
    }
    for(unsigned i=0;i<n;i++)if(!constrain(&g,x[i],z[i]))return 0;
    return 1;
}
/* Half-open frame range, bit mask for channels, stride relative to range start. */
static void screen(const char *name,unsigned start,unsigned end,unsigned channels,unsigned stride){
    unsigned n=0,degree[K]={0},exact_degree[K]={0};
    for(unsigned t=start;t<end;t+=stride)for(unsigned c=0;c<2;c++)if(channels&(1u<<c)){
        for(unsigned k=0;k<K;k++)projected[k][n]=atlas[k][2*t+c];
        ++n;
    }
    assert(n>0&&n<=S);
    unsigned pairs=0,uncertain=0,exact=0,max_candidates=1,max_exact=1,cross_event_actor=0;
    unsigned first_i=K,first_j=K,nonexact_i=K,nonexact_j=K;
    for(unsigned i=0;i<K;i++)for(unsigned j=i+1;j<K;j++){
        ++pairs;
        const int16_t *x=projected[i],*z=projected[j];
        if(!compatible(x,z,n)||!compatible(z,x,n))continue;
        ++uncertain; ++degree[i]; ++degree[j];
        if(i/256!=j/256)++cross_event_actor;
        if(!memcmp(x,z,n*sizeof *x)){
            ++exact; ++exact_degree[i]; ++exact_degree[j];
            if(first_i==K){first_i=i;first_j=j;}
        } else {
            if(nonexact_i==K){nonexact_i=i;nonexact_j=j;}
            if(!strcmp(name,"right")||!strcmp(name,"second_half"))
                printf("refine %s %u %u\n",name,i,j);
        }
    }
    unsigned unique=0;
    for(unsigned i=0;i<K;i++){
        if(!degree[i])++unique;
        if(degree[i]+1>max_candidates)max_candidates=degree[i]+1;
        if(exact_degree[i]+1>max_exact)max_exact=exact_degree[i]+1;
    }
    printf("%s samples=%u pairs=%u separated=%u inconclusive=%u exact=%u unique=%u max_candidates=%u max_exact=%u cross_event_actor=%u first_exact=%u,%u first_nonexact=%u,%u\n",
           name,n,pairs,pairs-uncertain,uncertain,exact,unique,max_candidates,max_exact,cross_event_actor,first_i,first_j,nonexact_i,nonexact_j);
    assert(compatible(projected[0],projected[0],n));
    if(!strcmp(name,"full")||!strcmp(name,"left"))assert(!uncertain);
    if(!strcmp(name,"first_half"))assert(exact==19200&&uncertain==exact&&max_exact==16);
}
int main(int argc,char **argv){
    if(argc!=2){fprintf(stderr,"usage: %s atlas.pcm\n",argv[0]);return 2;}
    FILE *f=fopen(argv[1],"rb");assert(f);
    for(unsigned k=0;k<K+LEGACY;k++)for(unsigned i=0;i<S;i++){
        int lo=fgetc(f),hi=fgetc(f);assert(lo!=EOF&&hi!=EOF);
        int v=lo+256*hi;if(v>=32768)v-=65536;assert(v>=-2048&&v<=2048);
        if(k>=LEGACY)atlas[k-LEGACY][i]=(int16_t)v;
    }
    assert(fgetc(f)==EOF&&!ferror(f));assert(!fclose(f));
    screen("full",0,N,3,1);
    screen("left",0,N,1,1);
    screen("right",0,N,2,1);
    screen("stride4",0,N,3,4);
    screen("first_half",0,N/2,3,1);
    screen("second_half",N/2,N,3,1);
    screen("first_half_left",0,N/2,1,1);
    screen("second_half_left",N/2,N,1,1);
    screen("last_quarter",3*N/4,N,3,1);
    puts("identical-vector controls and declared profile assertions PASS");
    return 0;
}
