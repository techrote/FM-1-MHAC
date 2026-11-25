/* Execute the actual app_main/app_audio against an original API contract shim.
   No upstream code, device I/O, timing simulation or target qualification. */
#include <assert.h>
#include <limits.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "app.c"

enum { FRAMES=256, SEGMENT=88, NROWS=5 };
#define B(x) (1u<<(x))
typedef struct {
    uint32_t keys, taps, buttons;
    int32_t delta;
    unsigned density, mode, run;
    int audible; /* -1: transition, 0: settled silence, 1: nonzero */
} event;
static const event score[]={
    {0,0,0,0,24,1,0,0},                         /* boot stopped */
    {B(26),0,0,0,64,1,0,0},                     /* highest key */
    {B(26),0,0,-40,24,1,0,0},                   /* held key doesn't retrigger */
    {0,0,0,0,24,1,0,0},                         /* release */
    {0,B(0),0,0,0,1,0,0},                      /* short tap, not held */
    {0,0,0,INT32_MAX,64,1,0,0},                 /* clamp huge detent */
    {0,0,0,INT32_MIN,0,1,0,0},
    {B(0)|B(26),0,0,-40,24,1,0,0},              /* highest pressed wins */
    {0,0,B(BTN_PLAY),0,24,1,1,1},               /* staggered */
    {0,0,B(BTN_SEL),0,24,2,1,1},                /* fixed */
    {0,0,B(BTN_SEL),0,24,3,1,1},                /* moving */
    {0,0,B(BTN_SEL),0,24,0,1,1},                /* aligned */
    {0,0,B(BTN_SEL),0,24,1,1,1},                /* staggered again */
    {0,0,B(BTN_HOME)|B(BTN_PLAY),0,24,1,0,-1},   /* HOME wins */
    {0,0,0,0,24,1,0,0},                         /* no repeated redraw */
    {0,0,B(BTN_SEL),-16,8,2,0,0},               /* fixed, density 8 */
    {0,0,B(BTN_PLAY),0,8,2,1,1},
    {0,0,B(BTN_SEL),0,8,3,1,-1},                /* may finish old pulse */
    {0,0,0,0,8,3,1,0},                         /* complete moving loss */
    {0,0,B(BTN_HOME),0,8,3,0,0}
};
static unsigned step, draws, peak, total_blocks, nonzero_blocks;
static char rows[NROWS][64];
static jmp_buf done;
static FILE *wav;
static void le(unsigned x,unsigned n) { while(n--){assert(fputc(x&255,wav)!=EOF); x>>=8;} }
static void draw_text_box(int x,int y,int w,const unsigned *font,
                          const char *s,unsigned color,int align) {
    static const int ys[]={20,70,100,145,190};
    assert(x==0&&w==240&&color==C_WHITE&&align==1);
    unsigned k=0;while(k<NROWS&&ys[k]!=y)k++;
    assert(k<NROWS&&strlen(s)<sizeof rows[k]);
    assert(*font==((k==0||k==2)?32u:16u));
    strcpy(rows[k],s); draws++;
}
static void render_segment(int audible) {
    unsigned nonzero=0;
    for(unsigned b=0;b<SEGMENT;b++) {
        int32_t guard[2*FRAMES+2]={0}; guard[0]=111;guard[2*FRAMES+1]=-111;
        app_audio(guard+1,FRAMES);
        assert(guard[0]==111&&guard[2*FRAMES+1]==-111);
        unsigned active=0;
        for(unsigned j=1;j<=2*FRAMES;j++) {
            int32_t v=guard[j];assert(v>=-6400&&v<=6400);
            unsigned a=(unsigned)(v<0?-v:v);if(a>peak)peak=a;
            active|=a!=0;le((uint16_t)v,2);
        }
        nonzero+=active;total_blocks++;nonzero_blocks+=active;
        /* HOME and the selective erasure transition may retain an old pulse,
           but no old pulse can survive four 256-frame blocks. */
        if(audible==-1&&b>=4)assert(!active);
    }
    if(audible==0)assert(!nonzero);
    if(audible==1)assert(nonzero);
}
static void platform_poll(void) {
    static const char *names[]={"ALIGNED","STAGGER","FIXED LOSS","MOVING LOSS"};
    if(step) {
        const event *e=&score[step-1];
        unsigned expected=e->density|(e->mode<<8)|(e->run<<16);
        assert(command==expected);
        char num[3]={(char)('0'+e->density/10),(char)('0'+e->density%10),0};
        assert(!strcmp(rows[0],"PHASE DEBT")&&!strcmp(rows[1],names[e->mode]));
        assert(!strcmp(rows[2],num)&&!strcmp(rows[3],e->run?"PLAYING":"STOPPED"));
        assert(!strcmp(rows[4],"SEL MODE / HOME MUTE"));
        unsigned changed=step==1;
        if(step>1){const event *p=&score[step-2];changed=(e->density!=p->density||e->mode!=p->mode||e->run!=p->run);}
        assert(draws==NROWS*changed);draws=0;
        render_segment(e->audible);
    }
    if(step==sizeof score/sizeof *score)longjmp(done,1);
    const event *e=&score[step++];
    fm1_in.notes=e->keys;note_edges=e->taps;edges=e->buttons;detents=e->delta;
}
int main(void) {
    unsigned bytes=(unsigned)(sizeof score/sizeof *score)*SEGMENT*FRAMES*4;
    wav=fopen("panel-replay.wav","wb");assert(wav);
    assert(fwrite("RIFF",1,4,wav)==4);le(bytes+36,4);
    assert(fwrite("WAVEfmt ",1,8,wav)==8);le(16,4);le(1,2);le(2,2);
    le(FS,4);le(FS*4,4);le(4,2);le(16,2);
    assert(fwrite("data",1,4,wav)==4);le(bytes,4);
    if(!setjmp(done))app_main();
    assert(!fclose(wav));
    printf("panel_steps=%u blocks=%u audible_blocks=%u peak=%u guard=PASS panel=PASS\n",step,total_blocks,nonzero_blocks,peak);
    return 0;
}
