/* Minimal standalone-harness newlib support. There is no filesystem/stdio UART
 * retarget here: protocol output uses the application's UART queue. Unsupported
 * system calls return an explicit error. CubeIDE users keep generated syscalls.
 */
#include "main.h"
#include <errno.h>
#include <stddef.h>
#include <sys/stat.h>

extern char _heap_start;
extern char _heap_end;

void *_sbrk(ptrdiff_t increment) {
    static char *next;
    if (next == NULL) next = &_heap_start;
    ptrdiff_t used = next - &_heap_start;
    ptrdiff_t capacity = &_heap_end - &_heap_start;
    if ((increment > 0 && increment > capacity - used) ||
        (increment < 0 && increment < -used)) {
        errno = ENOMEM;
        return (void *)-1;
    }
    char *previous = next;
    next += increment;
    return previous;
}

int _close(int fd) { (void)fd; errno = EBADF; return -1; }
int _fstat(int fd, struct stat *status) { (void)fd; (void)status; errno = EBADF; return -1; }
int _isatty(int fd) { (void)fd; return 0; }
int _lseek(int fd, int offset, int whence) {
    (void)fd; (void)offset; (void)whence; errno = ESPIPE; return -1;
}
int _read(int fd, char *buffer, int length) {
    (void)fd; (void)buffer; (void)length; errno = ENOSYS; return -1;
}
int _write(int fd, const char *buffer, int length) {
    (void)fd; (void)buffer; (void)length; errno = ENOSYS; return -1;
}
int _getpid(void) { return 1; }
int _kill(int pid, int signal) { (void)pid; (void)signal; errno = EINVAL; return -1; }
void _exit(int status) {
    (void)status;
    __disable_irq();
    for (;;) { }
}
