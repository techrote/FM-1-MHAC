#ifndef MHAC_PHASE_DEBT_H
#define MHAC_PHASE_DEBT_H
#include <stdint.h>
enum { PD_LANES=8, PD_MOD=64, PD_FS=44100, PD_STEP=2205 };
enum { PD_ALIGNED, PD_STAGGERED, PD_FIXED_LOSS, PD_MOVING_LOSS };
typedef struct {
    uint32_t phase[PD_LANES];
    uint16_t envelope[PD_LANES], until;
    uint8_t residue[PD_LANES], mode, running;
} pd_state;
static inline void pd_reset(pd_state *s, unsigned mode) {
    *s=(pd_state){0};
    s->mode=(uint8_t)(mode&3u);
    for(unsigned j=0;j<PD_LANES;j++)
        s->residue[j]=(uint8_t)(s->mode==PD_ALIGNED?0:j*8u);
}
/* Return full carry mask and optionally erase one observation, not state. */
static inline unsigned pd_tick(pd_state *s, unsigned a, unsigned *full) {
    unsigned mask=0;
    if(a>64u) a=64u;
    for(unsigned j=0;j<PD_LANES;j++){
        unsigned x=s->residue[j]+a;
        if(x>=64u){mask|=1u<<j;x-=64u;}
        s->residue[j]=(uint8_t)x;
    }
    if(full) *full=mask;
    if(s->mode==PD_FIXED_LOSS) mask&=~1u;
    if(s->mode==PD_MOVING_LOSS) mask&=mask-1u;
    return mask;
}
/* Original integer triangle; no floats, division, heap or external I/O. */
static inline int32_t pd_triangle(uint32_t phase) {
    unsigned u=phase>>16;
    return u<32768u?(int32_t)u*2-32768:98303-(int32_t)u*2;
}
/* One audio-thread owner; mode changes/mute fade existing pulses instead of
   discontinuous reset. New mode starts fresh at a block boundary. */
static inline void pd_render(pd_state *s, int32_t *out, uint32_t n,
                             unsigned a, unsigned mode, unsigned run) {
    static const uint32_t inc[8]={21426141u,26995255u,32139211u,42852281u,
                                 53990510u,64278422u,85704563u,107981019u};
    mode&=3u;
    if(mode!=s->mode){
        s->mode=(uint8_t)mode;
        for(unsigned j=0;j<8;j++) s->residue[j]=(uint8_t)(mode?j*8u:0);
        s->until=0;
    }
    if(run&&!s->running) s->until=0;
    s->running=(uint8_t)!!run;
    for(uint32_t i=0;i<n;i++){
        if(run&&s->until==0){
            unsigned mask=pd_tick(s,a,0);
            for(unsigned j=0;j<8;j++) if(mask&(1u<<j)){
                /* Fixed-length pulses never overlap themselves at this rate. */
                if(!s->envelope[j]) {s->phase[j]=0;s->envelope[j]=800;}
            }
            s->until=PD_STEP;
        }
        if(run) --s->until;
        for(unsigned j=0;j<8;j++) if(s->envelope[j]){
            unsigned e=s->envelope[j];
            /* 64-frame attack, then release. Mute stops new events. */
            unsigned gain=e>736u?(800u-e)*25u:(e*1600u)/736u;
            int32_t sample=pd_triangle(s->phase[j])*(int32_t)gain/32768;
            out[2u*i+(j&1u)]+=sample;
            s->phase[j]+=inc[j]; --s->envelope[j];
        }
    }
}
#endif
