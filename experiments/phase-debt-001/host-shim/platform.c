/* Original minimal API-contract shim, NOT Dinghy code or device emulation. */
#define BOARD_SMK37 0
#define FS 44100u
#define BTN_SEL 3u
#define BTN_HOME 8u
#define BTN_PLAY 12u
#define ENC_KNOB1 2u
#define C_WHITE 0xffffu
static const unsigned FONT_L=32, FONT_S=16;
static struct { uint32_t notes; } fm1_in;
static uint32_t edges, note_edges;
static int32_t detents;
static void platform_poll(void);
static uint32_t fm1_input_edges(uint32_t *released) {
    uint32_t v=edges; edges=0; *released=0; return v;
}
static uint32_t fm1_input_note_edges(void) {
    uint32_t v=note_edges; note_edges=0; return v;
}
static int32_t fm1_enc_take(unsigned id) {
    assert(id==ENC_KNOB1); int32_t v=detents; detents=0; return v;
}
static void draw_text_box(int x,int y,int w,const unsigned *font,
                          const char *s,unsigned color,int align);
