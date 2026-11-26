/* Original FM1-003 contextual panel, fixed 4800-frame slots at 44100 Hz.
 * One aligned 32-bit command snapshot per callback, as in legacy app.c.
 * No context is committed implicitly. No audio input or flash writes. */
#include "scope_context.c"
typedef struct { uint8_t depth,index,leaf,context,witness,run; } cp_edit;
static unsigned cp_limit(unsigned d){unsigned n=1;while(d--)n*=3;return n;}
static void cp_key(cp_edit *e,unsigned k){
    if(k<3){if(e->depth<SC_DEPTH){e->index=(uint8_t)(3u*e->index+k);++e->depth;}}
    else if(k<7)e->leaf=(uint8_t)(k-3);
    else if(k<11)e->context=(uint8_t)(k-7);
    else if(k==11){if(e->depth){--e->depth;e->index/=3;}}
    else if(k==12){e->depth=0;e->index=0;}
    else if(k<27){e->depth=3;e->index=(uint8_t)(k-13);}
}
static void cp_knob(cp_edit *e,int32_t d){
    if(d>80)d=80;
    if(d< -80)d= -80;
    int32_t x=(int32_t)e->index+d,top=(int32_t)cp_limit(e->depth)-1;
    e->index=(uint8_t)(x<0?0:x>top?top:x);
}
static uint32_t cp_pack(const cp_edit *e){
    unsigned w=e->witness&&e->leaf==3&&e->context<3;
    return e->index|((uint32_t)e->depth<<7)|((uint32_t)e->leaf<<10)|((uint32_t)e->context<<12)|(w<<14)|((uint32_t)e->run<<15);
}
static int cp_phrase(uint32_t c,sc_phrase *p){
    if(c>>16)return SC_BAD;
    return sc_make(p,(c>>7)&7,c&127,(c>>10)&3,(c>>12)&3,(c>>14)&1);
}
typedef struct {sc_state s;sc_phrase next;uint32_t last;uint8_t valid,run;} cp_audio;
/* Edits restart at a phrase boundary after the current motif's tail;
 * no note overlap. Chunked rendering avoids per-frame wrapper calls. */
static void cp_render(cp_audio *a,int32_t *out,uint32_t n,uint32_t cmd){
    if(!a->valid||cmd!=a->last){
        sc_phrase p={0};a->valid=1;a->last=cmd;
        a->run=(uint8_t)(cp_phrase(cmd,&p)==0&&((cmd>>15)&1));
        if(a->run)a->next=p;
        sc_stop(&a->s);
    }
    while(n){
        sc_state *s=&a->s;
        if(s->active&&!s->until&&s->slot==s->phrase.n)s->active=0;
        if(!s->active&&!s->tone.env){
            if(!a->run)return;
            if(sc_begin(s,&a->next)!=0){a->run=0;return;}
        }
        uint32_t k=s->active?(s->until?s->until:SC_SLOT):s->tone.env;
        if(k>n)k=n;
        sc_render(s,out,k);out+=2*k;n-=k;
    }
}
#ifdef CP_TEST
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static int32_t a[2*SC_MAX*SC_SLOT*2],b[2*SC_MAX*SC_SLOT*2];
static void blocks(cp_audio *s,int32_t *o,unsigned n,uint32_t c,unsigned step){
    while(n){unsigned k=n<step?n:step;cp_render(s,o,k,c);o+=2*k;n-=k;}
}
int main(int argc,char **argv){
    assert(argc==2);unsigned count=0,peak=0;
    for(unsigned d=0;d<=4;d++)for(unsigned i=0;i<cp_limit(d);i++)for(unsigned l=0;l<4;l++)for(unsigned c=0;c<4;c++)for(unsigned w=0;w<2;w++){
        cp_edit e={(uint8_t)d,(uint8_t)i,(uint8_t)l,(uint8_t)c,(uint8_t)w,1};sc_phrase p={0};
        uint32_t cmd=cp_pack(&e);assert(!cp_phrase(cmd,&p));sc_expr x={0};assert(sc_parse(&p,c,&x)>=0&&x.depth==d&&x.leaf==l);
        unsigned z=0;for(unsigned j=0;j<d;j++)z=3*z+x.ops[j];assert(z==i);
        assert(p.n==2*d+2+(w&&l==3&&c<3));count++;
    }
    cp_edit e={0,0,0,3,0,0};cp_key(&e,0);cp_key(&e,1);cp_key(&e,2);cp_key(&e,2);cp_key(&e,1);assert(e.depth==4&&e.index==17);cp_key(&e,11);assert(e.depth==3&&e.index==5);cp_knob(&e,INT32_MAX);assert(e.index==26);cp_knob(&e,INT32_MIN);assert(!e.index);cp_key(&e,12);assert(!e.depth&&!e.index);cp_key(&e,26);assert(e.depth==3&&e.index==13);
    FILE *f=fopen(argv[1],"wb");assert(f);unsigned replays=0;
    for(unsigned w=0;w<2;w++)for(unsigned c=0;c<4;c++){
        e=(cp_edit){4,17,3,(uint8_t)c,(uint8_t)w,1};sc_phrase p={0};uint32_t cmd=cp_pack(&e);assert(!cp_phrase(cmd,&p));unsigned n=p.n*SC_SLOT;
        cp_audio x={0},y={0};memset(a,0,sizeof a);memset(b,0,sizeof b);blocks(&x,a,2*n,cmd,1);blocks(&y,b,2*n,cmd,257);
        assert(!memcmp(a,b,4*n*sizeof *a));assert(!memcmp(a,a+2*n,2*n*sizeof *a));sc_state direct={0};memset(b,0,sizeof b);assert(!sc_begin(&direct,&p));sc_render(&direct,b,n);assert(!memcmp(a,b,2*n*sizeof *a));
        for(unsigned j=0;j<2*n;j++){unsigned v=(unsigned)abs(a[j]);assert(v<=2048);if(v>peak)peak=v;uint16_t q=(uint16_t)a[j];assert(fputc(q&255,f)!=EOF&&fputc(q>>8,f)!=EOF);}replays++;
    }
    /* Edits and stop at a non-aligned point: old tail drains, then restart. */
    cp_audio x={0},y={0};memset(a,0,sizeof a);memset(b,0,sizeof b);e=(cp_edit){2,1,0,0,0,1};uint32_t c=cp_pack(&e);blocks(&x,a,333,c,1);blocks(&y,b,333,c,97);e.leaf=3;e.witness=1;c=cp_pack(&e);blocks(&x,a+666,8000,c,1);blocks(&y,b+666,8000,c,311);e.run=0;c=cp_pack(&e);blocks(&x,a+16666,4096,c,1);blocks(&y,b+16666,4096,c,61);assert(!memcmp(a,b,2*12429*sizeof *a));for(unsigned j=2*(8333+2048);j<2*12429;j++)assert(a[j]==0);
    memset(a,0,sizeof a);cp_render(&x,a,4096,0xffffffffu);for(unsigned j=0;j<8192;j++)assert(!a[j]);assert(!fclose(f));
    printf("legal_editor_commands=%u repeated_phrase_replays=%u direct_core_matches=%u peak=%u state_bytes=%zu edit_mute_invalid=PASS\n",count,replays,replays,peak,sizeof(cp_audio));return 0;
}
#else
#include "platform.c"
#if BOARD_SMK37
#error FM-1 only
#endif
#if FS != 44100u
#error Scope Context requires 44100 Hz
#endif
static cp_audio synth;
static volatile uint32_t command=3u<<12;
static void app_audio(int32_t *out,uint32_t n){uint32_t c=command;cp_render(&synth,out,n,c);}
static void app_main(void){
    cp_edit e={0,0,0,3,0,0};uint32_t prev=0,shown=~0u;
    static const char *const labels[]={"BEACON","RETURN","WAIT","REF"};
    static const char *const ctx[]={"CTX BEACON","CTX RETURN","CTX WAIT","CTX UNKNOWN"};
    for(;;){
        platform_poll();uint32_t released,b=fm1_input_edges(&released);
        uint32_t keys=fm1_in.notes,down=(keys&~prev)|fm1_input_note_edges();prev=keys;
        for(unsigned k=0;k<27;k++)if(down&(1u<<k))cp_key(&e,k);
        cp_knob(&e,fm1_enc_take(ENC_KNOB1));
        if(b&(1u<<BTN_SEL))e.witness^=1;
        if(b&(1u<<BTN_PLAY))e.run^=1;
        if(b&(1u<<BTN_HOME))e.run=0;
        uint32_t c=cp_pack(&e);command=c;uint32_t ui=c|((uint32_t)e.witness<<16);
        if(ui!=shown){
            char ops[5]={'-','-','-','-',0};unsigned idx=e.index;
            for(unsigned j=e.depth;j;j--){ops[j-1]="QNR"[idx%3];idx/=3;}
            draw_text_box(0,10,240,&FONT_L,"SCOPE CONTEXT",C_WHITE,1);
            draw_text_box(0,47,240,&FONT_S,ops,C_WHITE,1);
            draw_text_box(0,74,240,&FONT_S,labels[e.leaf],C_WHITE,1);
            draw_text_box(0,101,240,&FONT_S,ctx[e.context],C_WHITE,1);
            draw_text_box(0,128,240,&FONT_S,(c&(1u<<14))?"WITNESS ACTIVE":e.witness?"WITNESS ARMED":"WITNESS OFF",C_WHITE,1);
            draw_text_box(0,155,240,&FONT_S,e.run?"PLAYING":"STOPPED",C_WHITE,1);
            draw_text_box(0,180,240,&FONT_S,"KEY 0-2 Q N R / 3-6 LEAF",C_WHITE,1);
            draw_text_box(0,204,240,&FONT_S,"7-10 CTX / 11 POP / 12 CLR",C_WHITE,1);shown=ui;
        }
    }
}
#endif
