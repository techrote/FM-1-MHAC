#ifndef MHAC_SCOPE_WEAVE_H
#define MHAC_SCOPE_WEAVE_H
#include <stdint.h>
enum { SW_PRESETS=27, SW_MODES=3, SW_FS=44100, SW_ENV=2048, SW_REST=9 };
/* Operator indices: quote, negate, request. Leaves: beacon, return, wait.
 * Modes: ordered scope, sorted scope (deliberately loses order), leaf only.
 * Five tokens per expression, then one silent slot; no semantic truth claim. */
static inline unsigned sw_token(unsigned preset,unsigned mode,unsigned slot){
    if(preset>=SW_PRESETS) preset=0;
    unsigned a=preset/9u,b=(preset/3u)%3u,c=preset%3u;
    if(mode==1u&&a>b){unsigned t=a;a=b;b=t;}
    if(slot==2u) return 6u+c;
    if(mode==2u) return SW_REST;
    switch(slot){case 0:return a;case 1:return b;case 3:return 3u+b;case 4:return 3u+a;default:return SW_REST;}
}
/* Strict inverse of the ordered five-token grammar; -1 means malformed. */
static inline int sw_parse(const uint8_t t[5]){
    if(t[0]>=3u||t[1]>=3u||t[2]<6u||t[2]>8u||t[3]!=3u+t[1]||t[4]!=3u+t[0]) return -1;
    return (int)(9u*t[0]+3u*t[1]+t[2]-6u);
}
typedef struct {
    uint32_t phase[2],inc[2],until;
    uint16_t env;
    uint8_t preset,mode,running,slot,token;
} sw_state;
static inline int32_t sw_tri(uint32_t p){
    uint32_t u=p>>16;
    return u<32768u?(int32_t)u*2-32768:98303-(int32_t)u*2;
}
static inline void sw_trigger(sw_state *s,unsigned t){
    /* Distinct openings, closings and leaves: original musical convention. */
    static const uint32_t hz[9][2]={
        {21426141u,32139211u},{24050000u,38300000u},{26995255u,40492883u},
        {16069605u,21426141u},{18037500u,24050000u},{20246441u,26995255u},
        {32139211u,42852281u},{36075000u,48100000u},{40492883u,53990510u}};
    if(t>=SW_REST) return;
    s->token=(uint8_t)t;s->env=SW_ENV;
    for(unsigned j=0;j<2;j++){s->phase[j]=0;s->inc[j]=hz[t][j];}
}
/* Additive stereo rendering; caller owns output buffer and headroom.
 * Controls are snapshotted per callback. Existing note tails are not cut. */
static inline void sw_render(sw_state *s,int32_t *out,uint32_t n,unsigned preset,unsigned mode,unsigned rate,unsigned run){
    if(preset>=SW_PRESETS) preset=0;
    if(mode>=SW_MODES) mode=0;
    if(rate>26u) rate=26u;
    run=!!run;
    if((run&&!s->running)||preset!=s->preset||mode!=s->mode){
        s->slot=0;s->until=s->env;s->preset=(uint8_t)preset;s->mode=(uint8_t)mode;
    }
    s->running=(uint8_t)run;
    for(uint32_t i=0;i<n;i++){
        if(run&&!s->until){
            sw_trigger(s,sw_token(preset,mode,s->slot));
            s->slot=(uint8_t)((s->slot+1u)%6u);
            s->until=10000u-200u*rate;
        }
        if(run) --s->until;
        if(s->env){
            uint32_t elapsed=SW_ENV-s->env;
            uint32_t gain=elapsed<128u?elapsed*8u:(uint32_t)(s->env-1u)*1024u/1920u;
            int32_t x=0;
            for(unsigned j=0;j<2;j++){
                x+=sw_tri(s->phase[j])*(int32_t)gain/32768;
                s->phase[j]+=s->inc[j];
            }
            unsigned ch=s->token<3u?0u:s->token<6u?1u:s->token&1u;
            out[2u*i+ch]+=x;out[2u*i+(ch^1u)]+=x/2;
            --s->env;
        }
    }
}
#endif
