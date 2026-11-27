/* Native qualification of optional acoustic-equivalence and retrigger policies. */
#define CP_TEST
#define main cp_old_test_main
#include "context_panel.c"
#undef main
#include "context_policy.h"
static uint32_t rnd=0x1a49c875u;
static unsigned random32(void){rnd^=rnd<<13;rnd^=rnd>>17;rnd^=rnd<<5;return rnd;}
static uint32_t command(unsigned d,unsigned i,unsigned l,unsigned c,unsigned w,unsigned run){
    cp_edit e={(uint8_t)d,(uint8_t)i,(uint8_t)l,(uint8_t)c,(uint8_t)w,(uint8_t)run};return cp_pack(&e);
}
static int32_t x[2*8192],y[2*8192];
static void clear(void){memset(x,0,sizeof x);memset(y,0,sizeof y);}
static void sample(cp_policy_audio *a,cp_policy_audio *b,uint32_t ca,uint32_t cb,unsigned n){
    clear();cp_policy_render(a,x,n,ca);cp_policy_render(b,y,n,cb);assert(!memcmp(x,y,2*n*sizeof *x));
}
static void output(FILE *f,const int32_t *v,unsigned n){
    for(unsigned j=0;j<2*n;j++){assert(v[j]>=-2048&&v[j]<=2048);uint16_t q=(uint16_t)v[j];assert(fputc(q&255,f)!=EOF&&fputc(q>>8,f)!=EOF);}
}
int main(int argc,char **argv){
    assert(argc==2);unsigned keys=0,hidden=0,exposed=0;
    for(unsigned d=0;d<=4;d++)for(unsigned i=0;i<cp_limit(d);i++)for(unsigned l=0;l<4;l++)for(unsigned c=0;c<4;c++)for(unsigned w=0;w<2;w++)for(unsigned run=0;run<2;run++){
        uint32_t q=command(d,i,l,c,w,run),k=cp_policy_key(cp_policy_pack(q,1,123));sc_phrase p={0},r={0};
        assert(!cp_phrase(q,&p)&&!cp_phrase(k,&r));assert(p.n==r.n&&!memcmp(p.t,r.t,p.n));assert((q&32768u)==(k&32768u));assert(cp_policy_key(cp_policy_pack(q,0,123))==q);keys++;
    }
    /* Vary private context at every callback versus a fixed-context control,
     * through all operator sequences and leaf values; compare additive PCM. */
    unsigned long long frames=0;
    for(unsigned d=0;d<=4;d++)for(unsigned i=0;i<cp_limit(d);i++)for(unsigned l=0;l<4;l++){
        cp_policy_audio a={0},b={0};unsigned remaining=(2*d+2)*SC_SLOT+13;
        while(remaining){unsigned n=1+random32()%257;if(n>remaining)n=remaining;
            uint32_t ca=cp_policy_pack(command(d,i,l,random32()%4,0,1),1,0),cb=cp_policy_pack(command(d,i,l,0,0,1),1,0);
            for(unsigned j=0;j<2*n;j++)x[j]=y[j]=j%2?-73:91;
            cp_policy_render(&a,x,n,ca);cp_policy_render(&b,y,n,cb);assert(!memcmp(x,y,2*n*sizeof *x));remaining-=n;frames+=n;
        }hidden++;
    }
    /* Every witnessed context pair remains distinguishable after an edit. */
    for(unsigned c=0;c<3;c++)for(unsigned d=0;d<3;d++)if(c!=d){
        cp_policy_audio a={0},b={0};uint32_t ca=cp_policy_pack(command(0,0,3,c,1,1),1,0),cb=cp_policy_pack(command(0,0,3,d,1,1),1,0);
        sample(&a,&b,ca,ca,701);clear();cp_policy_render(&a,x,8192,ca);cp_policy_render(&b,y,8192,cb);assert(memcmp(x,y,sizeof x));exposed++;
    }
    /* Explicit retrigger reproduces legacy context-edit timing, including epoch wrap. */
    uint32_t q=command(2,1,3,1,0,1),r=command(2,1,3,2,0,1);
    const unsigned offsets[]={1,127,701,2047,2048,4799,4800,4801,8192};
    unsigned retriggers=0;
    for(unsigned j=0;j<sizeof offsets/sizeof *offsets;j++){
        cp_policy_audio a={0},b={0};sample(&a,&b,cp_policy_pack(q,1,32767),cp_policy_pack(q,0,0),offsets[j]);
        sample(&a,&b,cp_policy_pack(r,1,0),cp_policy_pack(r,0,0),8192);retriggers++;
        sample(&a,&b,cp_policy_pack(r&~32768u,1,1),cp_policy_pack(r&~32768u,0,0),8192);assert(!a.core.s.active&&!a.core.s.tone.env);
    }
    /* Three clips: hidden edit, explicit retrigger, legacy edit. */
    FILE *f=fopen(argv[1],"wb");assert(f);
    for(unsigned m=0;m<3;m++){
        cp_policy_audio a={0};unsigned eq=m!=2;clear();cp_policy_render(&a,x,701,cp_policy_pack(q,eq,0));output(f,x,701);
        for(unsigned j=0;j<5;j++){clear();cp_policy_render(&a,x,8192,cp_policy_pack(r,eq,m==1));output(f,x,8192);}
        clear();cp_policy_render(&a,x,8192,cp_policy_pack(r&~32768u,eq,m==1));output(f,x,8192);
    }
    assert(!fclose(f));printf("key_contracts=%u hidden_sequences=%u hidden_frames=%llu witnessed_edits=%u retrigger_boundaries=%u state_bytes=%zu PASS\n",keys,hidden,frames,exposed,retriggers,sizeof(cp_policy_audio));return 0;
}
