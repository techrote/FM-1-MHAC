#ifndef MHAC_RECEIPT_LOOM_H
#define MHAC_RECEIPT_LOOM_H
#include <stdint.h>
enum { RL_CLEAN, RL_LOSS, RL_STALE_BOUND, RL_STALE_LATEST, RL_BLACKOUT, RL_MODES };
enum { RL_NONE, RL_ASK, RL_ACK, RL_REJECT, RL_REPAIR, RL_EXPIRE };
typedef struct { uint8_t actor, token, stage, attempt, age; } rl_world;
typedef struct { uint8_t kind, actor, token; } rl_event;
/* One pending transaction, one retry, no external or delayed queue. */
static inline rl_event rl_tick(rl_world *w, unsigned mode) {
    rl_event e={RL_NONE,w->actor,w->token};
    if(mode>=RL_MODES) mode=RL_CLEAN;
    if(w->stage==0){
        w->age=0; w->attempt=0; w->stage=1; e.kind=RL_ASK;
    } else {
        ++w->age;
        if(w->stage==1){
            e.actor^=1u;
            unsigned drop=mode==RL_BLACKOUT||(mode==RL_LOSS&&!w->attempt);
            unsigned stale=(mode==RL_STALE_BOUND||mode==RL_STALE_LATEST)&&!w->attempt;
            if(stale) e.token^=1u;
            if(drop) w->stage=2;
            else if(stale&&mode==RL_STALE_BOUND){ e.kind=RL_REJECT; w->stage=2; }
            else { e.kind=RL_ACK; w->stage=0; }
        } else if(!w->attempt){
            w->attempt=1; w->stage=1; e.kind=RL_REPAIR;
        } else { e.kind=RL_EXPIRE; w->stage=0; }
        if(w->stage==0){ w->actor^=1u; w->token=(uint8_t)(w->token+1u); }
    }
    return e;
}
enum { RL_FS=44100, RL_ENV=2048 };
typedef struct {
    rl_world world;
    uint32_t phase[2], inc[2], until;
    uint16_t env;
    uint8_t actor, running, mode;
} rl_state;
static inline int32_t rl_tri(uint32_t p){
    uint32_t u=p>>16;
    return u<32768u?(int32_t)u*2-32768:98303-(int32_t)u*2;
}
/* Rate 0..26 => tick period 12000..6800 frames; fixed bounded two-tone motif. */
static inline void rl_render(rl_state *s,int32_t *out,uint32_t n,unsigned rate,unsigned mode,unsigned run){
    static const uint32_t motifs[6][2]={
        {0,0},{21426141u,32139211u},{26995255u,42852281u},
        {38300000u,39700000u},{21426141u,26995255u},{32139211u,16069605u}};
    if(rate>26u) rate=26u;
    if(mode>=RL_MODES) mode=RL_CLEAN;
    run=!!run;
    if((run&&!s->running)||mode!=s->mode){
        s->world=(rl_world){0}; s->until=s->env; s->mode=(uint8_t)mode;
    }
    s->running=(uint8_t)run;
    for(uint32_t i=0;i<n;i++){
        if(run&&!s->until){
            rl_event e=rl_tick(&s->world,mode);
            if(e.kind){
                s->actor=e.actor; s->env=RL_ENV;
                for(unsigned j=0;j<2;j++){
                    s->phase[j]=0; s->inc[j]=motifs[e.kind][j]*(1u+e.actor);
                }
            }
            s->until=12000u-rate*200u;
        }
        if(run) --s->until;
        if(s->env){
            uint32_t elapsed=RL_ENV-s->env;
            uint32_t gain=elapsed<128u?elapsed*8u:(uint32_t)s->env*1024u/1920u;
            int32_t x=0;
            for(unsigned j=0;j<2;j++){
                x+=rl_tri(s->phase[j])*(int32_t)gain/32768;
                s->phase[j]+=s->inc[j];
            }
            out[2u*i+s->actor]+=x;
            out[2u*i+(s->actor^1u)]+=x/4;
            --s->env;
        }
    }
}
#endif
