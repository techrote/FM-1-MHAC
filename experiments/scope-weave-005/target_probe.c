/* Freestanding object-only probe; no startup or device I/O. */
#include "scope_weave.h"
static sw_state state;
void scope_weave_probe_render(int32_t *out,uint32_t n,unsigned preset,unsigned mode,unsigned rate,unsigned run){
    sw_render(&state,out,n,preset,mode,rate,run);
}
unsigned scope_weave_probe_state_size(void){return sizeof state;}
