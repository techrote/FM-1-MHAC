/* Original Scope Weave extension. Compile with -DSC_TEST for host tests.
 * Context is the last explicitly committed leaf; 3 means unknown.
 * No implicit context mutation, allocation, I/O or floating point in core. */
#include "scope_weave.h"
enum { SC_DEPTH=4, SC_REF=10, SC_MAX=12, SC_SLOT=4800 };
enum { SC_BAD=-1, SC_MISMATCH=-2, SC_RESOLVED=0, SC_UNKNOWN=1, SC_WITNESS_ONLY=2 };
typedef struct { uint8_t n,t[SC_MAX]; } sc_phrase;
typedef struct { uint8_t depth,ops[SC_DEPTH],leaf,resolved; } sc_expr;
/* base-3 index, outermost digit first. leaf=3 means contextual REF. */
int sc_make(sc_phrase *p,unsigned depth,unsigned index,unsigned leaf,unsigned context,unsigned witness){
    unsigned limit=1;
    if(depth>SC_DEPTH||leaf>3||context>3||witness>1||(witness&&(leaf!=3||context==3))) return SC_BAD;
    for(unsigned i=0;i<depth;i++) limit*=3;
    if(index>=limit) return SC_BAD;
    p->n=0;
    for(unsigned i=0;i<depth;i++){limit/=3;p->t[p->n++]=(uint8_t)(index/limit%3);}
    p->t[p->n++]=(uint8_t)(leaf==3?SC_REF:6+leaf);
    if(witness) p->t[p->n++]=(uint8_t)(6+context);
    for(unsigned i=depth;i;i--) p->t[p->n++]=(uint8_t)(3+p->t[i-1]);
    p->t[p->n++]=SW_REST;
    return 0;
}
int sc_parse(const sc_phrase *p,unsigned context,sc_expr *e){
    if(context>3||p->n<2||p->n>SC_MAX) return SC_BAD;
    unsigned i=0,d=0,leaf,resolved,witness=3;
    while(i<p->n&&p->t[i]<3){if(d==SC_DEPTH)return SC_BAD;e->ops[d++]=p->t[i++];}
    if(i>=p->n)return SC_BAD;
    unsigned t=p->t[i++];
    if(t==SC_REF){leaf=3;if(i<p->n&&p->t[i]>=6&&p->t[i]<=8)witness=p->t[i++]-6;}
    else if(t>=6&&t<=8)leaf=t-6;else return SC_BAD;
    for(unsigned j=d;j;j--)if(i>=p->n||p->t[i++]!=3+e->ops[j-1])return SC_BAD;
    if(i+1!=p->n||p->t[i]!=SW_REST)return SC_BAD;
    resolved=leaf!=3?leaf:context!=3?context:witness;
    e->depth=(uint8_t)d;e->leaf=(uint8_t)leaf;e->resolved=(uint8_t)resolved;
    if(leaf==3&&witness!=3&&context!=3&&witness!=context)return SC_MISMATCH;
    if(resolved==3)return SC_UNKNOWN;
    return leaf==3&&context==3?SC_WITNESS_ONLY:SC_RESOLVED;
}
typedef struct { sw_state tone; sc_phrase phrase; uint16_t until; uint8_t slot,active; } sc_state;
/* One phrase per start. Reject busy/invalid commands without changing state. */
int sc_begin(sc_state *s,const sc_phrase *p){
    sc_expr e;
    if(s->active||s->tone.env||sc_parse(p,3,&e)<0)return SC_BAD;
    s->phrase=*p;s->slot=0;s->until=0;s->active=1;return 0;
}
void sc_stop(sc_state *s){s->active=0;s->until=0;}
/* Additive 44100-Hz stereo. Caller must provide headroom. Stop completes
 * current envelope (at most 2048 frames), but starts no further notes. */
void sc_render(sc_state *s,int32_t *out,uint32_t n){
    for(uint32_t i=0;i<n;i++){
        if(s->active&&!s->until){
            if(s->slot==s->phrase.n)s->active=0;
            else{
                unsigned t=s->phrase.t[s->slot++];
                if(t==SC_REF){s->tone.token=SC_REF;s->tone.env=SW_ENV;s->tone.phase[0]=s->tone.phase[1]=0;s->tone.inc[0]=28600000u;s->tone.inc[1]=60500000u;}
                else sw_trigger(&s->tone,t);
                s->until=SC_SLOT;
            }
        }
        if(s->active)--s->until;
        if(s->tone.env){
            uint32_t elapsed=SW_ENV-s->tone.env;
            uint32_t gain=elapsed<128u?elapsed*8u:(uint32_t)(s->tone.env-1u)*1024u/1920u;
            int32_t x=0;
            for(unsigned j=0;j<2;j++){x+=sw_tri(s->tone.phase[j])*(int32_t)gain/32768;s->tone.phase[j]+=s->tone.inc[j];}
            unsigned t=s->tone.token,ch=t<3?0:t<6?1:t&1u;
            out[2*i+ch]+=x;out[2*i+(ch^1u)]+=x/2;--s->tone.env;
        }
    }
}
#ifdef SC_TEST
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static int32_t a[2*SC_MAX*SC_SLOT+2],b[2*SC_MAX*SC_SLOT+2];
static unsigned render(sc_phrase *p,int32_t *out,unsigned part){
    sc_state s={0};unsigned n=p->n*SC_SLOT+1;memset(out,0,2*n*sizeof *out);assert(sc_begin(&s,p)==0);
    assert(sc_begin(&s,p)==SC_BAD);
    for(unsigned i=0;i<n;){unsigned k=n-i<part?n-i:part;sc_render(&s,out+2*i,k);i+=k;}
    assert(!s.active&&!s.tone.env);return n;
}
int main(int argc,char **argv){
    assert(argc==2);unsigned literal=0,ref=0,tag=0,mismatch=0,malformed=0,limit=1,peak=0;
    for(unsigned d=0;d<=SC_DEPTH;d++,limit*=3)for(unsigned i=0;i<limit;i++){
        sc_phrase p={0},q={0};sc_expr e={0};
        for(unsigned l=0;l<3;l++){
            assert(!sc_make(&p,d,i,l,3,0));assert(sc_parse(&p,3,&e)==SC_RESOLVED&&e.resolved==l&&e.depth==d);literal++;
            if(d){q=p;q.t[q.n-2]=(uint8_t)(3+(q.t[0]+1)%3);assert(sc_parse(&q,3,&e)==SC_BAD);malformed++;}
        }
        for(unsigned c=0;c<4;c++){
            assert(!sc_make(&p,d,i,3,c,0));assert(sc_parse(&p,c,&e)==(c==3?SC_UNKNOWN:SC_RESOLVED)&&e.resolved==c);ref++;
            if(c<3){assert(!sc_make(&q,d,i,3,c,1));assert(sc_parse(&q,3,&e)==SC_WITNESS_ONLY&&e.resolved==c);assert(sc_parse(&q,c,&e)==SC_RESOLVED);tag++;
                for(unsigned other=0;other<3;other++)if(other!=c){assert(sc_parse(&q,other,&e)==SC_MISMATCH);mismatch++;}}
        }
        assert(!sc_make(&p,d,i,3,0,0));assert(!sc_make(&q,d,i,3,2,0));assert(!memcmp(&p,&q,p.n+1));
        unsigned n=render(&p,a,1);assert(render(&q,b,257)==n&&!memcmp(a,b,2*n*sizeof *a));
        assert(!sc_make(&p,d,i,3,0,1));assert(!sc_make(&q,d,i,3,2,1));n=render(&p,a,257);assert(render(&p,b,31)==n&&!memcmp(a,b,2*n*sizeof *a));
        for(unsigned j=0;j<2*n;j++){unsigned z=(unsigned)abs(a[j]);assert(z<=2048);if(z>peak)peak=z;}
        assert(render(&q,b,113)==n&&memcmp(a,b,2*n*sizeof *a));
    }
    sc_phrase p={0};sc_expr e={0};assert(sc_make(&p,5,0,0,0,0)==SC_BAD);assert(sc_make(&p,0,1,0,0,0)==SC_BAD);assert(sc_make(&p,0,0,3,3,1)==SC_BAD);assert(sc_parse(&p,3,&e)==SC_BAD);
    assert(!sc_make(&p,4,7,3,0,1));sc_state s={0};assert(!sc_begin(&s,&p));memset(a,0,sizeof a);sc_render(&s,a,333);sc_stop(&s);sc_render(&s,a+666,2048);assert(!s.tone.env&&!s.active);memset(a,0,sizeof a);sc_render(&s,a,2048);for(unsigned i=0;i<4096;i++)assert(a[i]==0);
    FILE *f=fopen(argv[1],"wb");assert(f);for(unsigned witness=0;witness<2;witness++)for(unsigned c=0;c<3;c+=2){assert(!sc_make(&p,3,5,3,c,witness));unsigned n=render(&p,a,257);for(unsigned j=0;j<2*(n-1);j++){uint16_t x=(uint16_t)a[j];assert(fputc(x&255,f)!=EOF);assert(fputc(x>>8,f)!=EOF);}}assert(!fclose(f));
    printf("literal=%u ref=%u witnessed=%u context_mismatch=%u malformed=%u\n",literal,ref,tag,mismatch,malformed);printf("depth_shapes=121 context_alias_pcm=121 witness_distinction_pcm=121 partition_checks=242 peak=%u state_bytes=%zu mute=PASS\n",peak,sizeof(sc_state));return 0;
}
#endif
