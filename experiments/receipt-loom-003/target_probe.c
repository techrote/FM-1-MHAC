/* Freestanding object-only probe. No startup or device I/O. */
#include "receipt_loom.h"
static rl_state state;
void receipt_loom_probe_render(int32_t *out,uint32_t n,unsigned rate,unsigned mode,unsigned run) {
    rl_render(&state,out,n,rate,mode,run);
}
unsigned receipt_loom_probe_state_size(void) { return sizeof state; }
