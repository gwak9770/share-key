#ifndef VEHICLE_LINE_READER_H
#define VEHICLE_LINE_READER_H
#include <stdbool.h>
#include <stddef.h>
#define VC_LINE_MAX 512u
typedef struct {
    char text[VC_LINE_MAX + 1u];
    size_t used;
    bool discard, saw_cr;
} LineReader;
typedef enum { LINE_MORE, LINE_READY, LINE_DROPPED } LineResult;
void line_reader_init(LineReader *r);
void line_reader_discard(LineReader *r);
LineResult line_reader_feed(LineReader *r, unsigned char c);
#endif
