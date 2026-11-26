#ifndef MHAC_RL_REDUNDANT_H
#define MHAC_RL_REDUNDANT_H
#include "receipt_loom.h"
/* Alternative sound mapping, independent of the legacy/tagged renderer.
 * Each 1024-frame half repeats the complete event and token. Mild stereo
 * placement preserves actor distinction while leaving both channels usable.
 * No decoder or input hardware is required on the device. */
enum { RR_HALF=1024, RR_ATTACK=64 };
typedef struct {
    rl_world world;
    uint32_t phase[2], inc_event, inc_lo, inc_hi, until;
    uint16_t env;
    uint8_t actor, running, mode;
} rr_state;
static inline void rr_trigger(rr_state *s, rl_event e){
    if(e.kind<RL_ASK || e.kind>RL_EXPIRE || e.actor>1u)return;
    s->actor=e.actor; s->env=RL_ENV;
    s->phase[0]=s->phase[1]=0;
    s->inc_event=20000000u+5000000u*(e.kind-1u+5u*e.actor);
    s->inc_lo=90000000u+10000000u*(e.token&15u);
    s->inc_hi=90000000u+10000000u*(e.token>>4);
}
/* Caller supplies a zeroed stereo accumulation buffer, as in rl_render.
 * Rate, reset, bounded tail and world semantics follow Receipt Loom. */
static inline void rr_render(rr_state *s,int32_t *out,uint32_t n,unsigned rate,unsigned mode,unsigned run){
    if(rate>26u)rate=26u;
    if(mode>=RL_MODES)mode=RL_CLEAN;
    run=!!run;
    if((run&&!s->running)||mode!=s->mode){
        s->world=(rl_world){0};s->until=s->env;s->mode=(uint8_t)mode;
    }
    s->running=(uint8_t)run;
    for(uint32_t i=0;i<n;i++){
        if(run&&!s->until){
            rl_event e=rl_tick(&s->world,mode);
            if(e.kind)rr_trigger(s,e);
            s->until=12000u-rate*200u;
        }
        if(run)--s->until;
        if(s->env){
            unsigned t=(RL_ENV-s->env)%RR_HALF;
            if(!t)s->phase[0]=s->phase[1]=0;
            unsigned gain=t<RR_ATTACK?t*16u:(RR_HALF-1u-t)*1024u/(RR_HALF-RR_ATTACK-1u);
            int32_t x=rl_tri(s->phase[0])*(int32_t)gain/32768;
            x+=rl_tri(s->phase[1])*(int32_t)gain/32768;
            s->phase[0]+=s->inc_event;
            s->phase[1]+=t<RR_HALF/2u?s->inc_lo:s->inc_hi;
            out[2u*i+s->actor]+=x;
            out[2u*i+(s->actor^1u)]+=x*3/4;
            --s->env;
        }
    }
}
#endif
