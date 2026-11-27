/* FM-1 candidate for the existing Dinghy panel API; target not yet qualified. */
#include <stdint.h>
#include "scope_weave.h"
#include "platform.c"
#if BOARD_SMK37
#error FM-1 only
#endif
#if FS != 44100u
#error Scope Weave requires 44100 Hz
#endif
static sw_state synth;
static volatile uint32_t command=12u<<8;
static void app_audio(int32_t *out,uint32_t n){
    uint32_t c=command;
    sw_render(&synth,out,n,c&31u,(c>>5)&3u,(c>>8)&31u,(c>>16)&1u);
}
static void app_main(void){
    unsigned preset=0,rate=12,mode=0,run=0;
    uint32_t prev=0,shown=~0u;
    static const char *const modes[]={"ORDERED SCOPE","SORTED CONTROL","LEAF ONLY"};
    static const char *const ops[]={"QUOTE","NEGATE","REQUEST"};
    static const char *const leaves[]={"BEACON","RETURN","WAIT"};
    for(;;){
        platform_poll();
        uint32_t released,b=fm1_input_edges(&released);
        uint32_t keys=fm1_in.notes,down=(keys&~prev)|fm1_input_note_edges();
        prev=keys;
        for(unsigned k=0;k<27;k++) if(down&(1u<<k)) preset=k;
        int32_t d=fm1_enc_take(ENC_KNOB1);
        if(d>26) d=26;
        if(d< -26) d= -26;
        int32_t v=(int32_t)rate+d;
        rate=v<0?0u:v>26?26u:(unsigned)v;
        if(b&(1u<<BTN_SEL)) mode=(mode+1u)%SW_MODES;
        if(b&(1u<<BTN_PLAY)) run^=1u;
        if(b&(1u<<BTN_HOME)) run=0;
        uint32_t c=preset|(mode<<5)|(rate<<8)|(run<<16);
        command=c;
        if(c!=shown){
            char num[3]={(char)('0'+rate/10u),(char)('0'+rate%10u),0};
            draw_text_box(0,10,240,&FONT_L,"SCOPE WEAVE",C_WHITE,1);
            draw_text_box(0,48,240,&FONT_S,modes[mode],C_WHITE,1);
            draw_text_box(0,77,240,&FONT_S,ops[preset/9u],C_WHITE,1);
            draw_text_box(0,102,240,&FONT_S,ops[(preset/3u)%3u],C_WHITE,1);
            draw_text_box(0,127,240,&FONT_S,leaves[preset%3u],C_WHITE,1);
            draw_text_box(0,154,240,&FONT_S,num,C_WHITE,1);
            draw_text_box(0,180,240,&FONT_S,run?"PLAYING":"STOPPED",C_WHITE,1);
            draw_text_box(0,208,240,&FONT_S,"SEL MODE / HOME MUTE",C_WHITE,1);
            shown=c;
        }
    }
}
