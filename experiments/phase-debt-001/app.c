/* Original app-layer candidate for Dinghy's documented single-TU API.
   Not a standalone flashable image. See README for integration hold. */
#include <stdint.h>
#include "phase_debt.h"
#include "platform.c"
#if BOARD_SMK37
#error This experiment is FM-1 only.
#endif
#if FS != 44100u
#error Phase Debt requires 44100 internal frames per second.
#endif
static pd_state synth;
/* Main loop is sole writer, ISR snapshots one aligned 32-bit word. */
static volatile uint32_t command=24u|(1u<<8);
static void app_audio(int32_t *out, uint32_t n) {
    uint32_t c=command;
    pd_render(&synth,out,n,c&127u,(c>>8)&3u,(c>>16)&1u);
}
static void app_main(void) {
    unsigned a=24, mode=1, run=0;
    uint32_t shown=~0u, prev=0;
    static const char *const names[]={"ALIGNED","STAGGER","FIXED LOSS","MOVING LOSS"};
    for(;;){
        platform_poll();
        uint32_t released, b=fm1_input_edges(&released);
        uint32_t keys=fm1_in.notes, down=(keys&~prev)|fm1_input_note_edges();
        prev=keys;
        for(unsigned k=0;k<27;k++) if(down&(1u<<k)) a=(k*64u+13u)/26u;
        int32_t delta=fm1_enc_take(ENC_KNOB1);
        if(delta>64) delta=64;
        if(delta< -64) delta= -64;
        int32_t v=(int32_t)a+delta;
        a=v<0?0u:v>64?64u:(unsigned)v;
        if(b&(1u<<BTN_SEL)) mode=(mode+1u)&3u;
        if(b&(1u<<BTN_PLAY)) run^=1u;
        if(b&(1u<<BTN_HOME)) run=0;
        uint32_t c=a|(mode<<8)|(run<<16);
        command=c;
        if(c!=shown){
            char num[3]={(char)('0'+a/10u),(char)('0'+a%10u),0};
            draw_text_box(0,20,240,&FONT_L,"PHASE DEBT",C_WHITE,1);
            draw_text_box(0,70,240,&FONT_S,names[mode],C_WHITE,1);
            draw_text_box(0,100,240,&FONT_L,num,C_WHITE,1);
            draw_text_box(0,145,240,&FONT_S,run?"PLAYING":"STOPPED",C_WHITE,1);
            draw_text_box(0,190,240,&FONT_S,"SEL MODE / HOME MUTE",C_WHITE,1);
            shown=c;
        }
    }
}
