#include "line_reader.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static LineResult feed(LineReader *r, const char *s) {
    LineResult result = LINE_MORE;
    while (*s) { LineResult q = line_reader_feed(r, (unsigned char)*s++); if (q != LINE_MORE) result = q; }
    return result;
}
int main(void) {
    LineReader r; line_reader_init(&r);
    assert(feed(&r, "01|HB\r\n") == LINE_READY && !strcmp(r.text,"01|HB"));
    assert(feed(&r, "\n") == LINE_MORE);
    for (unsigned i=0; i<512u; ++i) assert(line_reader_feed(&r,'X')==LINE_MORE);
    assert(line_reader_feed(&r,'\n')==LINE_READY && strlen(r.text)==512u);
    for (unsigned i=0; i<513u; ++i) line_reader_feed(&r,'X');
    assert(feed(&r,"00|HB\n")==LINE_DROPPED);
    assert(feed(&r,"00|HB\n")==LINE_READY);
    assert(feed(&r,"00|H\rB\n")==LINE_DROPPED);
    line_reader_feed(&r,0); assert(feed(&r,"00|HB\n")==LINE_DROPPED);
    line_reader_discard(&r); assert(feed(&r,"suffix\n")==LINE_DROPPED);
    assert(feed(&r,"02|HB\n")==LINE_READY);
    puts("PASS line reader: CRLF, 512-character limit, overlength/binary/partial suffix discard");
    return 0;
}
