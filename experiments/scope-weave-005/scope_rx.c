/* FM1-003: bounded streaming inverse of Scope Weave's aligned PCM contract.
 * Host/portable measurement apparatus; not wired to unverified audio input.
 * Stereo PCM16 at SW_FS; exact slot alignment and rate supplied externally.
 * Retained pulse samples: common positive gain [1/8,5/4], error <=2.
 * Retained gaps: exact zero. Erased slots: ignored, NOT silence.
 * No heap, floats, retained PCM, device I/O or forced unique answer. */
#include "scope_weave.h"
#include <string.h>
typedef struct { int32_t ln,ld,hn,hd; } rx_gain;
typedef struct {
    rx_gain slot[6][10];
    sw_state tone[9];
    uint32_t tick;
    uint16_t offset;
    uint8_t slot_index,observed,failed;
} scope_rx;
static rx_gain rx_prior(void){return (rx_gain){1,8,5,4};}
/* Bounds: a/c in [-32770,32770], b/d in [1,2048].
 * sw_render produces at most 2048 in absolute value in a zeroed frame.
 * Thus every signed cross-product fits in int32_t (<= 67112960). */
static int rx_gt(int32_t a,int32_t b,int32_t c,int32_t d){return a*d>c*b;}
static void rx_advance(scope_rx *s){
    if(++s->offset==s->tick){s->offset=0;s->slot_index++;}
}
static int rx_live(rx_gain g){return !rx_gt(g.ln,g.ld,g.hn,g.hd);}
static void rx_dead(rx_gain *g){*g=(rx_gain){1,1,0,1};}
static void rx_limit(rx_gain *g,int32_t a,int32_t b){
    if(!a){if(b>2||b< -2)rx_dead(g);return;}
    if(a<0){a=-a;b=-b;}
    if(rx_gt(b-2,a,g->ln,g->ld)){g->ln=b-2;g->ld=a;}
    if(rx_gt(g->hn,g->hd,b+2,a)){g->hn=b+2;g->hd=a;}
}
static void rx_meet(rx_gain *a,rx_gain b){
    if(!rx_live(b)){rx_dead(a);return;}
    if(rx_gt(b.ln,b.ld,a->ln,a->ld)){a->ln=b.ln;a->ld=b.ld;}
    if(rx_gt(a->hn,a->hd,b.hn,b.hd)){a->hn=b.hn;a->hd=b.hd;}
}
int scope_rx_init(scope_rx *s,unsigned rate,unsigned observed){
    memset(s,0,sizeof *s);
    if(rate>26||observed>63){s->failed=1;return -1;}
    s->tick=10000u-200u*rate;s->observed=(uint8_t)observed;
    for(unsigned j=0;j<6;j++)for(unsigned t=0;t<10;t++)s->slot[j][t]=rx_prior();
    return 0;
}
/* A block may cross slot boundaries. On malformed length, latch failure.
 * Caller supplies 2*n samples; NULL is valid only when n==0. */
int scope_rx_feed(scope_rx *s,const int16_t *pcm,uint32_t n){
    if(s->failed||!s->tick||n>(6u-s->slot_index)*s->tick-s->offset||(!pcm&&n)){s->failed=1;return -1;}
    for(uint32_t i=0;i<n;i++,rx_advance(s)){
        unsigned j=s->slot_index,k=s->offset;
        if(!(s->observed&(1u<<j)))continue;
        if(k>=SW_ENV){if(pcm[2*i]||pcm[2*i+1]){s->failed=1;return -1;}continue;}
        if(!k){memset(s->tone,0,sizeof s->tone);for(unsigned t=0;t<9;t++)sw_trigger(&s->tone[t],t);}
        for(unsigned t=0;t<10;t++){
            rx_gain *g=&s->slot[j][t];if(!rx_live(*g))continue;
            int32_t x[2]={0};if(t<9)sw_render(&s->tone[t],x,1,0,0,26,0);
            rx_limit(g,x[0],pcm[2*i]);if(rx_live(*g))rx_limit(g,x[1],pcm[2*i+1]);
        }
    }
    return 0;
}
/* Output bit p in masks[m] iff the entire retained PCM is compatible with
 * preset p, mode m, and ONE common gain. Return count (0 is abstention),
 * or -1 for invalid/incomplete input; masks cleared on all error paths. */
int scope_rx_finish(const scope_rx *s,unsigned modes,uint32_t masks[3]){
    masks[0]=masks[1]=masks[2]=0;
    if(s->failed||!s->tick||s->slot_index!=6||s->offset||!modes||modes>7)return -1;
    int count=0;
    for(unsigned m=0;m<3;m++)if(modes&(1u<<m))for(unsigned p=0;p<27;p++){
        rx_gain g=rx_prior();
        for(unsigned j=0;j<6&&rx_live(g);j++)if(s->observed&(1u<<j))rx_meet(&g,s->slot[j][sw_token(p,m,j)]);
        if(rx_live(g)){masks[m]|=UINT32_C(1)<<p;count++;}
    }
    return count;
}
#ifdef SCOPE_RX_TEST
#include <assert.h>
#include <stdio.h>
static int32_t source[120000];static int16_t input[120000];
static unsigned expected_token(unsigned p,unsigned m,unsigned j){
    unsigned a=p/9,b=p/3%3,c=p%3;
    if(m==1&&a>b){unsigned q=a;a=b;b=q;}
    unsigned seq[]={a,b,6+c,3+b,3+a,9};return m==2&&j!=2?9:seq[j];
}
static void generate(unsigned p,unsigned m,unsigned rate,unsigned gain){
    unsigned tick=10000-200*rate,n=6*tick;sw_state s={0};memset(source,0,2*n*sizeof *source);
    sw_render(&s,source,n,p,m,rate,1);
    const int num[]={1,77,5},den[]={8,200,4};
    for(unsigned i=0;i<2*n;i++)input[i]=(int16_t)(source[i]*num[gain]/den[gain]+(i%(2*tick)<2*SW_ENV&&expected_token(p,m,i/(2*tick))!=9?(int)(i%3)-1:0));
}
static unsigned feed(scope_rx *s,unsigned n,unsigned part){
    for(unsigned i=0;i<n;){unsigned k=n-i<part?n-i:part;if(scope_rx_feed(s,input+2*i,k))return 0;i+=k;}return 1;
}
static void check(unsigned p,unsigned m,unsigned rate,unsigned obs,unsigned gain,unsigned part){
    scope_rx s;uint32_t got[3],want[3]={0};int count=0;unsigned n=6*(10000-200*rate);
    generate(p,m,rate,gain);assert(!scope_rx_init(&s,rate,obs));assert(feed(&s,n,part));
    for(unsigned u=0;u<3;u++)for(unsigned q=0;q<27;q++){
        unsigned same=1;for(unsigned j=0;j<6;j++)if((obs&(1u<<j))&&expected_token(p,m,j)!=expected_token(q,u,j))same=0;
        if(same){want[u]|=UINT32_C(1)<<q;count++;}
    }
    assert(scope_rx_finish(&s,7,got)==count&&!memcmp(got,want,sizeof got));
    assert(scope_rx_finish(&s,1u<<m,got)>0&&got[m]==want[m]&&got[(m+1)%3]==0&&got[(m+2)%3]==0);
}
int main(void){
    unsigned full=0,erasure=0;scope_rx s;uint32_t got[3];
    for(unsigned m=0;m<3;m++)for(unsigned p=0;p<27;p++){check(p,m,p%3==0?0:p%3==1?13:26,63,p%3,p%2?257:1);full++;}
    for(unsigned m=0;m<3;m++)for(unsigned mask=0;mask<64;mask++){check(3,m,26,mask,mask%3,1024);erasure++;}
    for(unsigned r=0;r<=26;r++)for(unsigned m=0;m<3;m++){
        check((r*7+m)%27,m,r,63,r%3,1+r*31);
        check((r*7+m)%27,m,r,(r*13+m)%64,r%3,10000-r*200+1);
    }
    const int32_t num[]={-32770,-32769,-1,0,1,32769,32770},den[]={1,2,8,2047,2048};
    unsigned products=0;
    for(unsigned a=0;a<7;a++)for(unsigned b=0;b<5;b++)for(unsigned c=0;c<7;c++)for(unsigned d=0;d<5;d++){
        assert(rx_gt(num[a],den[b],num[c],den[d])==((int64_t)num[a]*den[d]>(int64_t)num[c]*den[b]));products++;
    }
    assert(!scope_rx_init(&s,0,0));assert(!scope_rx_feed(&s,0,0));
    assert(!scope_rx_feed(&s,input,60000));assert(s.slot_index==6&&!s.offset);
    assert(!scope_rx_feed(&s,0,0));assert(scope_rx_finish(&s,7,got)==81);
    assert(scope_rx_feed(&s,input,1)==-1);
    printf("all_rate_cases=162 boundary_products=%u end_cursor=PASS\n",products);
    generate(3,0,26,2);assert(!scope_rx_init(&s,26,63));assert(!scope_rx_feed(&s,input,1));assert(scope_rx_finish(&s,7,got)==-1&&!got[0]);
    assert(scope_rx_feed(&s,input,28800)==-1);assert(scope_rx_finish(&s,7,got)==-1);
    assert(scope_rx_init(&s,27,63)==-1);assert(scope_rx_init(&s,26,64)==-1);
    assert(!scope_rx_init(&s,26,63));assert(scope_rx_feed(&s,0,1)==-1);
    generate(3,0,26,2);input[2*SW_ENV]=1;assert(!scope_rx_init(&s,26,63));assert(!feed(&s,28800,257));
    assert(!scope_rx_init(&s,26,62));assert(feed(&s,28800,257));assert(scope_rx_finish(&s,7,got)>0);
    generate(3,0,26,2);for(unsigned i=0;i<2*SW_ENV;i++)input[i]/=4;assert(!scope_rx_init(&s,26,63));assert(feed(&s,28800,257));assert(scope_rx_finish(&s,7,got)==0);
    generate(3,0,26,2);input[0]=32767;assert(!scope_rx_init(&s,26,63));assert(feed(&s,28800,257));assert(scope_rx_finish(&s,7,got)==0);
    assert(scope_rx_finish(&s,0,got)==-1&&!got[0]&&!got[1]&&!got[2]);
    printf("full_phrases=%u erasure_cases=%u exact_candidate_sets=PASS malformed_gap_gain_outlier_controls=PASS state_bytes=%zu\n",full,erasure,sizeof(scope_rx));return 0;
}
#endif
