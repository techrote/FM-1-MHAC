/* Candidate FM-1 app for pinned Dinghy API, not an installable image. */
#include <stdint.h>
#include "redundant_core.h"
#include "platform.c"
#if BOARD_SMK37
#error FM-1 only
#endif
#if FS != 44100u
#error Receipt Loom requires 44100 Hz
#endif
static rr_state synth;
static volatile uint32_t command=12u;
static void app_audio(int32_t *out,uint32_t n){
    uint32_t c=command;
    rr_render(&synth,out,n,c&31u,(c>>8)&15u,(c>>16)&1u);
}
static void app_main(void){
    unsigned rate=12,mode=0,run=0;
    uint32_t prev=0,shown=~0u;
    static const char *const names[]={"CLEAN","FIRST LOSS","STALE BOUND","STALE LATEST","BLACKOUT"};
    for(;;){
        platform_poll();
        uint32_t released,b=fm1_input_edges(&released);
        uint32_t keys=fm1_in.notes,down=(keys&~prev)|fm1_input_note_edges();
        prev=keys;
        for(unsigned k=0;k<27;k++) if(down&(1u<<k)) rate=k;
        int32_t d=fm1_enc_take(ENC_KNOB1);
        if(d>26) d=26;
        if(d< -26) d= -26;
        int32_t v=(int32_t)rate+d;
        rate=v<0?0u:v>26?26u:(unsigned)v;
        if(b&(1u<<BTN_SEL)) mode=(mode+1u)%RL_MODES;
        if(b&(1u<<BTN_PLAY)) run^=1u;
        if(b&(1u<<BTN_HOME)) run=0;
        uint32_t c=rate|(mode<<8)|(run<<16);
        command=c;
        if(c!=shown){
            char num[3]={(char)('0'+rate/10u),(char)('0'+rate%10u),0};
            draw_text_box(0,20,240,&FONT_L,"RECEIPT LOOM",C_WHITE,1);
            draw_text_box(0,70,240,&FONT_S,names[mode%RL_MODES],C_WHITE,1);
            draw_text_box(0,100,240,&FONT_L,num,C_WHITE,1);
            draw_text_box(0,166,240,&FONT_S,"REPEATED TOKEN",C_WHITE,1);
            draw_text_box(0,145,240,&FONT_S,run?"PLAYING":"STOPPED",C_WHITE,1);
            draw_text_box(0,190,240,&FONT_S,"SEL MODE / HOME MUTE",C_WHITE,1);
            shown=c;
        }
    }
}
