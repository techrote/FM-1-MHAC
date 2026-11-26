/* Freestanding object-only probe. No start-up, linker, bootloader or hardware. */
#include "phase_debt.h"
static pd_state state;
void phase_debt_probe_reset(unsigned mode) { pd_reset(&state,mode); }
void phase_debt_probe_render(int32_t *out,uint32_t n,unsigned density,unsigned mode,unsigned run) {
    pd_render(&state,out,n,density,mode,run);
}
unsigned phase_debt_probe_state_size(void) { return sizeof state; }
