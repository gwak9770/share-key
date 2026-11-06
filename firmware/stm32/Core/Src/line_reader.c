#include "line_reader.h"
#include <string.h>
void line_reader_init(LineReader *r) { memset(r, 0, sizeof(*r)); }
void line_reader_discard(LineReader *r) {
    r->used = 0; r->discard = true; r->saw_cr = false;
}
LineResult line_reader_feed(LineReader *r, unsigned char c) {
    if (c == '\n') {
        bool bad = r->discard;
        size_t length = r->used;
        r->text[length] = '\0';
        r->used = 0; r->discard = false; r->saw_cr = false;
        if (bad) return LINE_DROPPED;
        return length ? LINE_READY : LINE_MORE;
    }
    if (r->discard) return LINE_MORE;
    if (r->saw_cr) { line_reader_discard(r); return LINE_MORE; }
    if (c == '\r') { r->saw_cr = true; return LINE_MORE; }
    if (c < 0x20u || c > 0x7eu || r->used >= VC_LINE_MAX) {
        line_reader_discard(r); return LINE_MORE;
    }
    r->text[r->used++] = (char)c;
    return LINE_MORE;
}
