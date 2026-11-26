/* FM1-003: native active-playback transition witness, not target emulation. */
#define CP_TEST
#define main cp_previous_test_main
#include "context_panel.c"
#undef main

enum { BANK=6, CHUNK=1024 };
static const cp_edit edits[BANK]={
    {2,1,3,0,1,1}, {4,17,3,2,1,1}, {0,0,2,3,0,1},
    {2,1,3,2,0,1}, {0,0,0,3,0,0}, {2,1,3,1,0,1}
};
static int32_t pcm[BANK][2*SC_MAX*SC_SLOT];
static sc_phrase phrase[BANK];
static uint32_t command_bank[BANK];
static unsigned period[BANK];
static unsigned long long frames, callbacks;
static unsigned peak;
static uint32_t rng=0x35c71a9bu;
static uint32_t random32(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
/* Independent scheduling oracle: pre-rendered whole phrases, no cp_render
 * or sc_stop in the oracle. A changed command truncates to the current
 * motif envelope; newer commands supersede pending ones during that tail. */
typedef struct { unsigned playing,pos,tail,last; } oracle;
static void want(oracle *o,unsigned id,int32_t *dst){
    if(id!=o->last){
        if(!o->tail&&o->playing<BANK&&period[o->playing]){
            unsigned k=o->pos%SC_SLOT;
            if(k&&k<SW_ENV&&phrase[o->playing].t[o->pos/SC_SLOT]!=SW_REST)o->tail=SW_ENV-k;
        }
        if(!o->tail)o->playing=BANK;
        o->last=id;
    }
    if(o->playing==BANK&&id<BANK&&period[id]){o->playing=id;o->pos=0;}
    if(o->playing<BANK){
        dst[0]+=pcm[o->playing][2*o->pos];dst[1]+=pcm[o->playing][2*o->pos+1];
        o->pos=(o->pos+1)%period[o->playing];
        if(o->tail&&!--o->tail)o->playing=BANK;
    }
}
static void segment(cp_audio *a,oracle *o,unsigned id,unsigned n,unsigned step,FILE *f){
    int32_t got[2*CHUNK],expected[2*CHUNK];
    uint32_t cmd=id==BANK?0xffffffffu:command_bank[id];
    while(n){
        unsigned k=n<step?n:step;
        for(unsigned j=0;j<2*k;j++)got[j]=expected[j]=j%2? -73:91;
        for(unsigned j=0;j<k;j++)want(o,id,expected+2*j);
        cp_render(a,got,k,cmd);assert(!memcmp(got,expected,2*k*sizeof *got));
        for(unsigned j=0;j<2*k;j++){
            int32_t v=got[j]-(j%2? -73:91);unsigned mag=(unsigned)abs(v);
            assert(mag<=2048);if(mag>peak)peak=mag;
            if(f){uint16_t q=(uint16_t)v;assert(fputc(q&255,f)!=EOF&&fputc(q>>8,f)!=EOF);}
        }
        frames+=k;callbacks++;n-=k;
    }
}
int main(int argc,char **argv){
    assert(argc==2);
    for(unsigned j=0;j<BANK;j++){
        command_bank[j]=cp_pack(&edits[j]);assert(!cp_phrase(command_bank[j],&phrase[j]));
        if(edits[j].run){sc_state s={0};period[j]=phrase[j].n*SC_SLOT;assert(!sc_begin(&s,&phrase[j]));sc_render(&s,pcm[j],period[j]);}
    }
    const unsigned offsets[]={0,1,127,128,2047,2048,2049,4799,4800,4801,9600,9601,14399,14400,28799,28800,33599,33600};
    unsigned pairs=0;
    for(unsigned old=0;old<BANK;old++)for(unsigned next=0;next<=BANK;next++)for(unsigned i=0;i<sizeof offsets/sizeof *offsets;i++){
        cp_audio a={0};oracle o={BANK,0,0,BANK+1};
        segment(&a,&o,old,offsets[i],257,NULL);
        segment(&a,&o,next,SC_SLOT+SW_ENV+1,113,NULL);
        segment(&a,&o,4,SW_ENV+1,31,NULL);assert(!a.s.tone.env&&!a.s.active);pairs++;
    }
    cp_audio a={0};oracle o={BANK,0,0,BANK+1};
    for(unsigned i=0;i<12000;i++){
        unsigned id=random32()%(BANK+1),n=1+random32()%700,step=1+random32()%CHUNK;
        segment(&a,&o,id,n,step,NULL);
    }
    segment(&a,&o,4,SW_ENV+1,19,NULL);assert(!a.s.tone.env&&!a.s.active);
    /* Falsifier: equal phrase PCM does not imply equal live edit behaviour.
     * Commands 3 and 5 differ only in unwitnessed context. */
    assert(period[3]==period[5]&&!memcmp(pcm[3],pcm[5],2*period[3]*sizeof(int32_t)));
    cp_audio x={0},y={0};int32_t pre[2*701]={0},q[2*701]={0},u[2*4096]={0},v[2*4096]={0};
    cp_render(&x,pre,701,command_bank[3]);cp_render(&y,q,701,command_bank[3]);assert(!memcmp(pre,q,sizeof pre));
    cp_render(&x,u,4096,command_bank[5]);cp_render(&y,v,4096,command_bank[3]);assert(memcmp(u,v,sizeof u));
    FILE *f=fopen(argv[1],"wb");assert(f);a=(cp_audio){0};o=(oracle){BANK,0,0,BANK+1};
    segment(&a,&o,0,35000,127,f);segment(&a,&o,1,63001,257,f);segment(&a,&o,2,12001,31,f);
    segment(&a,&o,3,35000,113,f);segment(&a,&o,5,35000,113,f);segment(&a,&o,4,4410,257,f);assert(!fclose(f));
    printf("boundary_cases=%u randomized_commands=12000 frames=%llu callbacks=%llu peak=%u oracle=PASS additive=PASS stop=PASS\n",pairs,frames,callbacks,peak);
    puts("unwitnessed_context_edit: equal standalone phrase PCM, different live transition PCM (expected current restart policy)");
    return 0;
}
