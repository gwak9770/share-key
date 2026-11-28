/* Integration tests use the production policy, parser and control code.
 * Deterministic RNG and fake I/O below are for the host tests only. */
#include "vehicle_app.h"
#include "config.h"
#include "sharekey.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TEST_KID 0x00000007u
#define CAPTURE_COUNT 512u
#define CAPTURE_LENGTH 600u

static uint32_t now_ms, random_state;
static Inputs input_state;
static Outputs applied;
static bool io_fault, return_pressed;
static bool led_allow, led_online, led_deny;
static unsigned service_count;
static unsigned char rx_bytes[8192];
static size_t rx_read, rx_write;
static char wire[CAPTURE_COUNT][CAPTURE_LENGTH];
static char logs[CAPTURE_COUNT][CAPTURE_LENGTH];
static size_t wire_count, log_count;
static unsigned next_rid;

bool vc_platform_init(void) { return true; }
uint32_t vc_platform_millis(void) { return now_ms; }
Inputs vc_platform_inputs(void) { return input_state; }
void vc_platform_apply(Outputs out) { applied = out; }
int vc_platform_rx_get(void) {
    return rx_read < rx_write ? rx_bytes[rx_read++] : -1;
}
bool vc_platform_take_io_fault(void) {
    bool result = io_fault;
    io_fault = false;
    return result;
}
void vc_platform_send_line(const char *line) {
    assert(wire_count < CAPTURE_COUNT && strlen(line) < CAPTURE_LENGTH);
    strcpy(wire[wire_count++], line);
}
void vc_platform_log(const char *line) {
    assert(log_count < CAPTURE_COUNT && strlen(line) < CAPTURE_LENGTH);
    strcpy(logs[log_count++], line);
}
void vc_platform_random(uint8_t *out, size_t n) {
    while (n--) {
        random_state = random_state * 1664525u + 1013904223u;
        *out++ = (uint8_t)(random_state >> 24);
    }
}
void vc_platform_indicators(bool allow, bool online, bool deny) {
    led_allow = allow;
    led_online = online;
    led_deny = deny;
}
bool vc_platform_return_pressed(void) { return return_pressed; }
static uint16_t tone_hz;                      /* last pitch sent to the buzzer */
static uint16_t tone_seen[16];                /* distinct non-zero pitches heard */
static size_t tone_seen_count;
void vc_platform_tone(uint16_t hz) {
    tone_hz = hz;
    if (!hz) return;
    for (size_t i = 0; i < tone_seen_count; ++i) if (tone_seen[i] == hz) return;
    assert(tone_seen_count < sizeof(tone_seen) / sizeof(tone_seen[0]));
    tone_seen[tone_seen_count++] = hz;
}
static bool tone_heard(uint16_t hz) {
    for (size_t i = 0; i < tone_seen_count; ++i) if (tone_seen[i] == hz) return true;
    return false;
}
#if VC_ENABLE_RTC
#include "rtc_time.h"
static bool stub_rtc_ok;
static RtcTime stub_rtc;
uint32_t vc_platform_unix_time(void) { return stub_rtc_ok ? rtc_to_unix(&stub_rtc, VC_RTC_UTC_OFFSET_S) : 0u; }
bool vc_platform_rtc_text(char *out, size_t n) { return stub_rtc_ok && rtc_format(&stub_rtc, out, n); }
bool vc_platform_rtc_set_text(const char *local) {
    RtcTime t;
    if (!rtc_parse(local, &t)) return false;
    stub_rtc = t; stub_rtc_ok = true; return true;
}
#endif
static uint32_t mode_hold_ms;                 /* USER held for this long from boot */
static bool local_user_pressed;
bool vc_platform_mode_button(void) {
    if (!mode_hold_ms) return local_user_pressed;
    uint32_t step = mode_hold_ms < 100u ? mode_hold_ms : 100u;
    mode_hold_ms -= step; now_ms += step;     /* holding the button takes time */
    return true;
}
static const char *inject_during_select;      /* bytes that arrive while USER is held */
void vc_platform_service(const Controller *c, const VehicleDisplay *display) {
    assert(c && display);
    ++service_count;
    if (inject_during_select && mode_hold_ms) {
        size_t n = strlen(inject_during_select);
        memcpy(rx_bytes, inject_during_select, n);
        rx_read = 0; rx_write = n;
        inject_during_select = NULL;
    }
}
void vc_platform_panic(void) {
    fputs("unexpected platform panic\n", stderr);
    abort();
}

static unsigned rid(void) { return next_rid++ & 0xffu; }

static const char *last_wire_prefix(const char *prefix) {
    size_t n = strlen(prefix);
    for (size_t i = wire_count; i > 0; --i)
        if (!strncmp(wire[i - 1], prefix, n)) return wire[i - 1];
    fprintf(stderr, "missing wire prefix: %s\n", prefix);
    abort();
}

static bool has_log(const char *fragment) {
    for (size_t i = 0; i < log_count; ++i)
        if (strstr(logs[i], fragment)) return true;
    return false;
}

static void feed_bytes(const void *data, size_t n) {
    assert(rx_read == rx_write && n <= sizeof(rx_bytes));
    memcpy(rx_bytes, data, n);
    rx_read = 0;
    rx_write = n;
    unsigned loops = 0;
    do {
        vehicle_app_step();
        assert(++loops < 100u);
    } while (rx_read < rx_write);
}

static void feed_line(const char *line) {
    char framed[2048];
    size_t n = strlen(line);
    assert(n + 1 < sizeof(framed));
    memcpy(framed, line, n);
    framed[n] = '\n';
    feed_bytes(framed, n + 1u);
}

static void heartbeat(void) {
    size_t before = wire_count;
    feed_line("F0|HB");
    /* sk_poll may independently emit a SYNCREQ, but never an HB response. */
    for (size_t i = before; i < wire_count; ++i) assert(strstr(wire[i], "|HB") == NULL);
}

static void advance(uint32_t elapsed) {
    now_ms += elapsed;
    vehicle_app_step();
}

static void keepalive_for(uint32_t elapsed) {
    heartbeat();
    while (elapsed) {
        uint32_t step = elapsed > 250u ? 250u : elapsed;
        now_ms += step;
        heartbeat();
        elapsed -= step;
    }
}

static void reset_app_with_door(bool closed) {
    local_user_pressed=false;
    now_ms = 0;
    random_state = 0x12345678u;
    input_state = (Inputs){ closed, false, false, false };
    applied = (Outputs){ 0, 0 };
    io_fault = return_pressed = false;
    led_allow = led_online = led_deny = false;
    service_count = 0;
    tone_hz = 0; tone_seen_count = 0;
    rx_read = rx_write = wire_count = log_count = 0;
    next_rid = 1;
    assert(vehicle_app_init());
    assert(applied.motor == 0 && applied.servo_us == 0);
    assert(!vehicle_app_controller()->armed);
    assert(!vehicle_app_controller()->heartbeat_seen);
    assert(!control_lock_known(vehicle_app_controller()));
    vehicle_app_step();
    advance(DEBOUNCE_MS);
    assert(vehicle_app_controller()->ready);
    assert(service_count >= 2);
}

static void reset_app(void) { reset_app_with_door(true); }

static void hex_encode(const uint8_t *bytes, size_t n, char *hex) {
    static const char alphabet[] = "0123456789ABCDEF";
    for (size_t i = 0; i < n; ++i) {
        hex[2 * i] = alphabet[bytes[i] >> 4];
        hex[2 * i + 1] = alphabet[bytes[i] & 15u];
    }
    hex[2 * n] = '\0';
}

static unsigned hex_digit(char c) {
    if (c >= '0' && c <= '9') return (unsigned)(c - '0');
    assert(c >= 'A' && c <= 'F');
    return (unsigned)(c - 'A') + 10u;
}

static void hex_decode(const char *hex, size_t n, uint8_t *bytes) {
    assert(strlen(hex) == n * 2);
    for (size_t i = 0; i < n; ++i)
        bytes[i] = (uint8_t)((hex_digit(hex[2 * i]) << 4) | hex_digit(hex[2 * i + 1]));
}

static unsigned make_key(char *line, size_t capacity) {
    uint8_t tag[32];
    char tag_hex[65];
    unsigned id = rid();
    sk_key_tag(TEST_KID, UINT32_MAX, 4, 0, 3, tag);
    hex_encode(tag, sizeof(tag), tag_hex);
    snprintf(line, capacity, "%02X|KEY|%08X|FFFFFFFF|04|00|03|%s", id, TEST_KID, tag_hex);
    assert(strlen(line) == 98u);
    return id;
}

static void register_key(void) {
    char line[160], prefix[40], expected[40];
    unsigned id = make_key(line, sizeof(line));
    snprintf(prefix, sizeof(prefix), "%02X|KEY", id);
    snprintf(expected, sizeof(expected), "%02X|KEYOK|%08X", id, TEST_KID);
    feed_line(line);
    assert(!strcmp(last_wire_prefix(prefix), expected));
}

static unsigned make_response(unsigned command, char *line, size_t capacity) {
    uint8_t nonce[16], individual_key[32], tag[32];
    char request[64], prefix[64], nonce_hex[33], tag_hex[65];
    unsigned id = rid();
    snprintf(request, sizeof(request), "%02X|REQ|%08X|%02X", id, TEST_KID, command);
    snprintf(prefix, sizeof(prefix), "%02X|CHAL|%08X|", id, TEST_KID);
    feed_line(request);
    const char *challenge = last_wire_prefix(prefix) + strlen(prefix);
    assert(strlen(challenge) == 32u);
    strcpy(nonce_hex, challenge);
    hex_decode(nonce_hex, 16, nonce);
    sk_derive(TEST_KID, individual_key);
    sk_auth_tag(individual_key, TEST_KID, (uint8_t)command, nonce, tag);
    hex_encode(tag, sizeof(tag), tag_hex);
    snprintf(line, capacity, "%02X|RESP|%08X|%02X|%s|%s", id, TEST_KID, command, nonce_hex, tag_hex);
    assert(strlen(line) == 117u);
    return id;
}

static void expect_result(unsigned id, char result, const char *reason, unsigned remaining) {
    char expected[64], prefix[16];
    snprintf(prefix, sizeof(prefix), "%02X|RES|", id);
    snprintf(expected, sizeof(expected), "%02X|RES|%08X|%c|%s|%02X",
             id, TEST_KID, result, reason, remaining);
    const char *actual = last_wire_prefix(prefix);
    if (strcmp(actual, expected)) {
        fprintf(stderr, "expected %s\nactual   %s\n", expected, actual);
        abort();
    }
    assert(vehicle_app_display()->policy == result);
    assert(!strcmp(vehicle_app_display()->reason, reason));
    sk_key_view_t view;
    bool blocked = sk_get_key_view(TEST_KID, &view) && strcmp(view.blocked_reason, "00");
    int shown = blocked ? 0 : (remaining == 255u ? -1 : (int)remaining);
    assert(vehicle_app_display()->remaining == shown);
}

static unsigned policy_remaining(unsigned remaining_c) {
    return APP_POLICY_MODE == 'C' ? remaining_c : 0xffu;
}

static unsigned authenticate(unsigned command, char result, const char *reason, unsigned remaining_c) {
    char response[160];
    unsigned id = make_response(command, response, sizeof(response));
    feed_line(response);
    expect_result(id, result, reason, policy_remaining(remaining_c));
    return id;
}

static void complete_servo(bool locked) {
#if CONTROL_USE_ENDPOINTS
    input_state.locked = locked;
    input_state.unlocked = !locked;
    advance(1);
    advance(DEBOUNCE_MS);
    advance(SERVO_MIN_SETTLE_MS);
#else
    (void)locked;
    advance(SERVO_TRAVEL_MS);
#endif
    assert(!vehicle_app_controller()->moving);
    assert(vehicle_app_controller()->fault == FAULT_NONE);
}

static void make_sync(uint32_t version, uint8_t state, char *line, size_t capacity) {
    const char *request = NULL;
    for (size_t i = wire_count; i > 0; --i) {
        if (strstr(wire[i - 1], "|SYNCREQ|")) { request = wire[i - 1]; break; }
    }
    assert(request);
    char request_copy[CAPTURE_LENGTH];
    strcpy(request_copy, request);
    char *id = strtok(request_copy, "|");
    char *type = strtok(NULL, "|");
    char *vid = strtok(NULL, "|");
    char *nonce_text = strtok(NULL, "|");
    assert(id && type && vid && nonce_text && !strcmp(type, "SYNCREQ"));
    uint8_t nonce[16], tag[32];
    char tag_hex[65];
    uint32_t kid = TEST_KID;
    hex_decode(nonce_text, 16, nonce);
    sk_sync_tag(version, nonce, &kid, &state, 1, tag);
    hex_encode(tag, sizeof(tag), tag_hex);
    snprintf(line, capacity, "%s|SYNC|%s|%08X|%s|01|%08X:%02X|%s",
             id, vid, version, nonce_text, TEST_KID, state, tag_hex);
}

static void test_heartbeat_and_servo_bridge(void) {
    reset_app();
    register_key();
    feed_line("GG|HB");
    feed_line("00|HB|extra");
    feed_line("0|HB");
    assert(!vehicle_app_controller()->heartbeat_seen);
    authenticate(1, 'A', "00", 3);
    assert(vehicle_app_display()->policy == 'A');
    assert(vehicle_app_display()->actuation_attempted);
    assert(vehicle_app_display()->actuation == RES_LINK_STALE);
    assert(applied.servo_us == 0 && !vehicle_app_controller()->armed);

    heartbeat();
    assert(vehicle_app_controller()->heartbeat_seen && !vehicle_app_controller()->armed);
    authenticate(1, 'A', "00", 2);
    assert(vehicle_app_display()->actuation == RES_OK);
    assert(applied.servo_us == SERVO_UNLOCK_US && vehicle_app_controller()->moving);
    assert(led_allow && !led_deny);
    complete_servo(false);
    assert(control_is_unlocked(vehicle_app_controller()));
    assert(control_position_estimated(vehicle_app_controller()) == !CONTROL_USE_ENDPOINTS);
    assert(has_log("ACT DONE POSITION=UNLOCKED"));

    now_ms = vehicle_app_controller()->last_heartbeat + LINK_TIMEOUT_MS;
    heartbeat(); /* The overdue heartbeat arrives after the mandatory control tick. */
    assert(vehicle_app_controller()->fault == FAULT_LINK);
    assert(!vehicle_app_controller()->armed && applied.servo_us == 0 && applied.motor == 0);
    assert(led_deny);
    heartbeat();
    assert(vehicle_app_controller()->fault == FAULT_LINK);
    authenticate(1, 'A', "00", 1);
    assert(vehicle_app_display()->actuation == RES_FAULT);
    assert(applied.servo_us == 0);
}

static void test_policy_count_duplicate_and_sync(void) {
    reset_app();
    register_key();
    for (unsigned attempt = 1; attempt <= 6; ++attempt) {
        bool allowed = APP_POLICY_MODE == 'A' || attempt <= 4;
        unsigned left = attempt <= 4 ? 4u - attempt : 0u;
        heartbeat();
        authenticate(1, allowed ? 'A' : 'D', allowed ? "00" : "05", left);
        if (allowed) {
            assert(vehicle_app_display()->actuation == RES_OK);
            complete_servo(false);
        }
        if (attempt == 1) register_key(); /* Re-registering must not replenish C. */
    }

    char valid_sync[256];
    make_sync(1, 0, valid_sync, sizeof(valid_sync));
    feed_line(valid_sync);
    assert(led_online);
    heartbeat();
    authenticate(1, 'A', "00", 3);
    complete_servo(false);
    feed_line(valid_sync); /* Consumed sync response cannot replenish again. */
    heartbeat();
    authenticate(1, 'A', "00", 2);
    complete_servo(false);

    keepalive_for(2000);
    char revoke_sync[256];
    make_sync(2, 1, revoke_sync, sizeof(revoke_sync));
    feed_line(revoke_sync);
    authenticate(1, 'D', "03", 2);
    register_key();
    authenticate(1, 'D', "03", 2);

    keepalive_for(2000);
    make_sync(3, 0, valid_sync, sizeof(valid_sync));
    feed_line(valid_sync);
    authenticate(1, 'D', "03", 2); /* Valid sync cannot resurrect a revoked key. */
}

static void test_three_misses_online_indicator(void) {
    reset_app(); register_key();
    char sync[256];
    make_sync(1,0,sync,sizeof sync); feed_line(sync);
    assert(led_online && sk_online_state()==1);
    keepalive_for(2000); /* First new request, not a missed response yet. */
    assert(sk_sync_misses()==0 && led_online);
    for (unsigned miss=1;miss<=3;++miss) {
        keepalive_for(2000); /* Pi HB remains healthy while server is absent. */
        assert(sk_sync_misses()==miss);
        assert(led_online==(miss<3));
        assert(control_link_fresh(vehicle_app_controller(),now_ms));
        assert(vehicle_app_controller()->fault==FAULT_NONE);
    }
    make_sync(1,0,sync,sizeof sync); feed_line(sync);
    assert(led_online && sk_online_state()==1 && sk_sync_misses()==0);
    puts("PASS offline indicator: 3 server misses, Pi HB independent, signed recovery online");
}

static void test_tamper_and_replay(void) {
    reset_app();
    register_key();
    heartbeat();
    char correct[160], tampered[160];
    unsigned id = make_response(1, correct, sizeof(correct));
    strcpy(tampered, correct);
    size_t last = strlen(tampered) - 1;
    tampered[last] = tampered[last] == '0' ? '1' : '0';
    feed_line(tampered);
    expect_result(id, 'D', "01", policy_remaining(4));
    assert(applied.servo_us == 0 && !vehicle_app_controller()->armed);
    feed_line(correct);
    expect_result(id, 'D', "02", policy_remaining(4));
    assert(applied.servo_us == 0);

    id = make_response(1, correct, sizeof(correct));
    feed_line(correct);
    expect_result(id, 'A', "00", policy_remaining(3));
    assert(applied.servo_us == SERVO_UNLOCK_US);
    feed_line(correct);
    expect_result(id, 'D', "02", policy_remaining(3));
    /* A denied credential does not stop a previously authorized motion. */
    assert(applied.servo_us == SERVO_UNLOCK_US);
    complete_servo(false);
}

static void test_frames_and_test_build_boundary(void) {
    reset_app();
    char key[160], damaged[1024];
    (void)make_key(key, sizeof(key));
    memset(damaged, 'x', 513u);
    strcpy(damaged + 513u, key);
    feed_line(damaged);
    assert(has_log("RX DROP"));
    for (size_t i = 0; i < wire_count; ++i) assert(strstr(wire[i], "|KEYOK|") == NULL);

    unsigned id = rid();
    char request[64];
    snprintf(request, sizeof(request), "%02X|REQ|%08X|01", id, TEST_KID);
    feed_line(request);
    expect_result(id, 'D', "08", 0);
    feed_line(key); /* The next complete valid frame is accepted. */
    assert(strstr(last_wire_prefix("01|KEY"), "|KEYOK|"));

    memset(damaged, 'x', 513u);
    strcpy(damaged + 513u, "00|HB");
    feed_line(damaged);
    assert(!vehicle_app_controller()->heartbeat_seen);
    feed_line("00|H\rB");
    assert(!vehicle_app_controller()->heartbeat_seen);
    heartbeat();
    assert(vehicle_app_controller()->heartbeat_seen);
#if !TEST_BUILD
    feed_line("TEST UNLOCK");
    feed_line("1 ARM");
    feed_line("2 UNLOCK");
    assert(!vehicle_app_controller()->armed && applied.servo_us == 0);
#endif

    io_fault = true;
    feed_line("00|HB");
    assert(vehicle_app_controller()->fault == FAULT_IO);
    assert(applied.motor == 0 && applied.servo_us == 0);
}

static void test_motor_failure_does_not_refund(void) {
    reset_app();
    register_key();
    heartbeat();
    authenticate(2, 'A', "00", 3);
#if VC_ENABLE_MOTORS
    assert(vehicle_app_display()->actuation_attempted);
    assert(vehicle_app_display()->actuation == RES_NOT_LOCKED);
#else
    assert(!vehicle_app_display()->actuation_attempted);
    assert(has_log("ACT DISABLED"));
#endif
    assert(applied.motor == 0);
    authenticate(2, 'D', "07", 3); /* Repeated START must not refresh the session. */
    authenticate(5, 'A', "00", 3); /* A new START needs an authenticated stop first. */
    authenticate(1, 'A', "00", 2);
    complete_servo(false);
    heartbeat();
    assert(vehicle_app_request_lock() == RES_OK);
    complete_servo(true);
    assert(control_is_locked(vehicle_app_controller()));
    authenticate(2, 'A', "00", 1);
#if VC_ENABLE_MOTORS
    assert(vehicle_app_display()->actuation == RES_OK);
    advance(MOTOR_RAMP_MS);
    assert(applied.motor > 0 && applied.motor <= MOTOR_START_PERMILLE);
    input_state.door_closed = false;
    advance(1);
    assert(applied.motor == 0 && vehicle_app_controller()->fault == FAULT_DOOR);
#else
    assert(applied.motor == 0 && !vehicle_app_display()->actuation_attempted);
#endif
}

static void test_reauth_local_stop_cutoff(void) {
    reset_app(); register_key(); heartbeat();
    assert(vehicle_app_request_lock()==RES_OK);
    complete_servo(true);
    assert(sk_configure_reauth(100,50,100));
    authenticate(2,'A',"00",3);
    advance(MOTOR_RAMP_MS);
#if VC_ENABLE_MOTORS
    assert(applied.motor>0);
#endif
    keepalive_for(150);
    assert(vehicle_app_display()->engine_running && vehicle_app_display()->reauth_warning);
    assert(!vehicle_app_display()->stopped);
#if VC_ENABLE_MOTORS
    assert(applied.motor>0); /* Reauth expiry must not cut a driving motor. */
#endif
#if VC_DEMO_DRIVE_INPUT
    local_user_pressed=true; advance(1); advance(DEBOUNCE_MS/2);
    local_user_pressed=false; advance(1); advance(DEBOUNCE_MS);
    assert(!vehicle_app_display()->stopped); /* Bounce cannot report STOP. */
    local_user_pressed=true; advance(1); advance(DEBOUNCE_MS);
    assert(vehicle_app_display()->stopped);
    advance(99); assert(vehicle_app_display()->engine_running);
    advance(1); assert(!vehicle_app_display()->engine_running && applied.motor==0);
    assert(has_log("REAUTH STOP CUTOFF"));
    authenticate(2,'D',"07",3);
#else
    assert(vehicle_app_display()->engine_running);
    authenticate(5,'A',"00",3);
#endif
    assert(vehicle_app_controller()->fault==FAULT_NONE);
}

/* 1128: passive buzzer mirrors allow / deny / engine off and the reauth warning. */
static void test_buzzer_sounds(void) {
    reset_app(); register_key(); heartbeat();
    assert(tone_hz == 0 && tone_seen_count == 0);          /* silent at boot */
    authenticate(1, 'A', "00", 3);
    assert(tone_hz == BUZZER_ALLOW_HZ);
    advance(120); assert(tone_hz == 0);
    complete_servo(false);

    char response[160];
    make_response(1, response, sizeof(response));
    response[strlen(response) - 1] = response[strlen(response) - 1] == '0' ? '1' : '0';
    feed_line(response);                                     /* tampered tag -> 01 */
    assert(tone_hz == BUZZER_DENY_HZ);
    advance(150); assert(tone_hz == 0);                      /* gap */
    advance(100); assert(tone_hz == BUZZER_DENY_HZ);
    advance(150); assert(tone_hz == 0);
    assert(vehicle_app_controller()->fault == FAULT_NONE);   /* sound never changes control */

    reset_app(); register_key(); heartbeat();
    assert(vehicle_app_request_lock() == RES_OK);
    complete_servo(true);
    assert(sk_configure_reauth(100, 50, VC_STOP_CUTOFF_S * 1000u));
    authenticate(2, 'A', "00", 3);
    keepalive_for(1500);
    assert(vehicle_app_display()->reauth_warning && tone_heard(BUZZER_WARN_DRIVE_HZ));
    assert(!tone_heard(BUZZER_WARN_STOP_HZ));
#if VC_DEMO_DRIVE_INPUT
    local_user_pressed = true; advance(1); advance(DEBOUNCE_MS);
    assert(vehicle_app_display()->stopped);
    keepalive_for(1000);
    assert(tone_heard(BUZZER_WARN_STOP_HZ) && !tone_heard(BUZZER_WARN_CUTOFF_HZ));
    const uint32_t cutoff = VC_STOP_CUTOFF_S * 1000u;
    keepalive_for(cutoff - cutoff / 3u);
    assert(vehicle_app_display()->engine_running && tone_heard(BUZZER_WARN_CUTOFF_HZ));
    while (vehicle_app_display()->engine_running) { now_ms += 250u; heartbeat(); }
    assert(has_log("REAUTH STOP CUTOFF") && tone_hz == BUZZER_OFF1_HZ);
    advance(150); assert(tone_hz == BUZZER_OFF2_HZ);
    advance(150); assert(tone_hz == BUZZER_OFF3_HZ);
    advance(250); assert(tone_hz == 0);                      /* engine off: warning ends */
    authenticate(2, 'D', "07", 3);
    assert(tone_hz == BUZZER_DENY_HZ);
#else
    authenticate(5, 'A', "00", 3);
    assert(tone_hz == BUZZER_OFF1_HZ);
#endif
    assert(tone_seen_count >= 3u);                           /* 기술요건 1: 3가지 이상 주파수 */
    printf("PASS buzzer: allow/deny/engine-off sounds, reauth warning rises, %u pitches, control unchanged\n",
           (unsigned)tone_seen_count);
}

static size_t lock_request_logs(void) {
    size_t count = 0;
    for (size_t i = 0; i < log_count; ++i)
        if (strstr(logs[i], "DOOR CLOSED -> LOCK ACT=")) ++count;
    return count;
}

static void set_door(bool closed) {
    input_state.door_closed = closed;
    advance(1);
    advance(DEBOUNCE_MS);
    assert(vehicle_app_controller()->stable.door_closed == closed);
}

static void prepare_unlocked(void) {
    reset_app();
    register_key();
    heartbeat();
    authenticate(1, 'A', "00", 3);
    complete_servo(false);
    assert(control_is_unlocked(vehicle_app_controller()));
    assert(lock_request_logs() == 0); /* Already closed is not a close edge. */
}

static void test_relock_boot_and_unknown(void) {
    reset_app(); /* Boot closed, with and without heartbeat, must stay still. */
    heartbeat();
    keepalive_for(1000);
    assert(applied.servo_us == 0 && !vehicle_app_controller()->armed);
    assert(lock_request_logs() == 0);
    reset_app_with_door(false);
    heartbeat();
    set_door(true); /* UNKNOWN-at-close is not enabled by this release. */
    assert(applied.servo_us == 0 && !vehicle_app_controller()->armed);
    assert(lock_request_logs() == 0);
}

static void test_relock_debounce_and_one_shot(void) {
    prepare_unlocked();
    set_door(false);
    input_state.door_closed = true;
    advance(1);
    advance(DEBOUNCE_MS - 1u);
    assert(!vehicle_app_controller()->moving && lock_request_logs() == 0);
    input_state.door_closed = false; /* Bounce cancels the incomplete close. */
    advance(1);
    input_state.door_closed = true;
    advance(1);
    advance(DEBOUNCE_MS - 1u);
    assert(!vehicle_app_controller()->moving && lock_request_logs() == 0);
    advance(1);
#if VC_RELOCK_ON_DOOR_CLOSE
    assert(vehicle_app_controller()->moving && applied.servo_us == SERVO_LOCK_US);
    assert(lock_request_logs() == 1 && has_log("DOOR CLOSED -> LOCK ACT=OK"));
    complete_servo(true);
    assert(control_is_locked(vehicle_app_controller()));
    assert(has_log("ACT DONE POSITION=LOCKED"));
    heartbeat();
    advance(100);
    assert(lock_request_logs() == 1 && !vehicle_app_controller()->moving);
#else
    assert(control_is_unlocked(vehicle_app_controller()) && lock_request_logs() == 0);
    assert(applied.servo_us == SERVO_UNLOCK_US);
#endif
    /* Local lock must neither consume nor replenish the authentication budget. */
    heartbeat();
    authenticate(1, 'A', "00", 2);
    complete_servo(false);
}

static void test_relock_busy_edge_not_deferred(void) {
    reset_app(); register_key(); heartbeat();
    authenticate(1, 'A', "00", 3);
    set_door(false);
    set_door(true); /* Closing during unlock is consumed, not queued. */
    assert(vehicle_app_controller()->moving && applied.servo_us == SERVO_UNLOCK_US);
    assert(lock_request_logs() == 0);
    complete_servo(false);
    advance(100);
    assert(control_is_unlocked(vehicle_app_controller()) && lock_request_logs() == 0);
    set_door(false);
    set_door(true); /* A new real edge is required. */
#if VC_RELOCK_ON_DOOR_CLOSE
    assert(lock_request_logs() == 1 && applied.servo_us == SERVO_LOCK_US);
#else
    assert(lock_request_logs() == 0 && applied.servo_us == SERVO_UNLOCK_US);
#endif
}

static void test_relock_faults_and_stop(void) {
    prepare_unlocked(); set_door(false); set_door(true);
#if VC_RELOCK_ON_DOOR_CLOSE
    assert(vehicle_app_controller()->moving);
    input_state.door_closed = false;
    advance(1); /* Raw opening stops locking before debounce completes. */
    assert(vehicle_app_controller()->fault == FAULT_DOOR);
    assert(applied.servo_us == 0 && applied.motor == 0);
    set_door(false); heartbeat(); set_door(true);
    assert(vehicle_app_controller()->fault == FAULT_DOOR && lock_request_logs() == 1);
    assert(vehicle_app_clear_fault() == RES_OK);
    advance(100);
    assert(applied.servo_us == 0); /* Fault clear is not an automatic retry. */
#endif
    prepare_unlocked(); set_door(false);
    now_ms = vehicle_app_controller()->last_heartbeat + LINK_TIMEOUT_MS;
    vehicle_app_step();
    assert(vehicle_app_controller()->fault == FAULT_LINK);
    heartbeat(); set_door(true);
    assert(applied.servo_us == 0 && lock_request_logs() == 0);
    assert(vehicle_app_controller()->fault == FAULT_LINK);

    prepare_unlocked(); set_door(false);
    vehicle_app_stop(); heartbeat(); set_door(true);
    assert(applied.servo_us == 0 && lock_request_logs() == 0);
    assert(!vehicle_app_controller()->armed);

#if VC_RELOCK_ON_DOOR_CLOSE
    prepare_unlocked(); set_door(false); set_door(true);
    now_ms = vehicle_app_controller()->last_heartbeat + LINK_TIMEOUT_MS;
    vehicle_app_step(); /* Timeout during auto-lock keeps the original fault latch. */
    assert(vehicle_app_controller()->fault == FAULT_LINK && applied.servo_us == 0);
#endif
}

static void test_relock_physical_cycles_keep_policy(void) {
    reset_app(); register_key();
    for (unsigned attempt = 1; attempt <= 6; ++attempt) {
        bool allowed = APP_POLICY_MODE == 'A' || attempt <= 4;
        heartbeat();
        authenticate(1, allowed ? 'A' : 'D', allowed ? "00" : "05",
                     attempt <= 4 ? 4u - attempt : 0u);
        if (allowed) {
            complete_servo(false);
            set_door(false);
            heartbeat();
            set_door(true);
#if VC_RELOCK_ON_DOOR_CLOSE
            assert(vehicle_app_controller()->moving && applied.servo_us == SERVO_LOCK_US);
            complete_servo(true);
            assert(control_is_locked(vehicle_app_controller()));
#endif
        } else {
            assert(!vehicle_app_controller()->moving);
#if VC_RELOCK_ON_DOOR_CLOSE
            assert(control_is_locked(vehicle_app_controller()));
#endif
        }
    }
#if VC_RELOCK_ON_DOOR_CLOSE
    assert(lock_request_logs() == (APP_POLICY_MODE == 'A' ? 6u : 4u));
#else
    assert(lock_request_logs() == 0);
#endif
}

/* 1103: KEYOK/KEYNG are mirrored to the display; the wire line is unchanged. */
static void test_key_registration_display(void) {
    char line[160], prefix[40], expected[40], kid[9];
    reset_app();
    register_key();
    snprintf(kid, sizeof(kid), "%08X", TEST_KID);
    assert(vehicle_app_display()->policy == 'K');
    assert(!strcmp(vehicle_app_display()->kid, kid));
    assert(!strcmp(vehicle_app_display()->reason, "00"));
    unsigned id = make_key(line, sizeof(line));
    line[strlen(line) - 1] = line[strlen(line) - 1] == '0' ? '1' : '0';   /* tamper KEY tag */
    snprintf(prefix, sizeof(prefix), "%02X|KEY", id);
    snprintf(expected, sizeof(expected), "%02X|KEYNG|%08X|01", id, TEST_KID);
    feed_line(line);
    assert(!strcmp(last_wire_prefix(prefix), expected));
    assert(vehicle_app_display()->policy == 'N');
    assert(!strcmp(vehicle_app_display()->reason, "01"));
    heartbeat();
    authenticate(1, 'A', "00", 3u);
    assert(vehicle_app_display()->policy == 'A');                       /* next RES overrides */
}

#if VC_DEMO_MODE_SELECT
/* 1103: hold USER at RESET -> other mode, hold past one step -> wraps back. */
static void test_demo_mode_select(void) {
    char other = APP_POLICY_MODE == 'C' ? 'A' : 'C';
    char response[160];
    mode_hold_ms = 0; reset_app();
    assert(vehicle_app_mode() == APP_POLICY_MODE && vehicle_app_display()->mode == APP_POLICY_MODE);
    mode_hold_ms = 300; reset_app();
    assert(vehicle_app_mode() == other && vehicle_app_display()->mode == other);
    assert(has_log("MODE SELECT") && has_log(other == 'A' ? "MODE=A" : "MODE=C"));
    register_key(); heartbeat();
    unsigned id = make_response(1, response, sizeof(response));
    feed_line(response);
    expect_result(id, 'A', "00", other == 'A' ? 0xffu : 3u);   /* policy really switched */
    mode_hold_ms = VC_MODE_STEP_MS + 300u; reset_app();
    assert(vehicle_app_mode() == APP_POLICY_MODE);             /* stepped once more, wrapped */
    mode_hold_ms = 0;
}

/* 1104 (곽동규 검토 R1): an HB received while USER is held must not count after
 * selection. reset_app() itself asserts heartbeat_seen == false after the
 * first app steps, so a buffered HB would already fail there. */
static void test_mode_select_drops_buffered_rx(void) {
    char response[160];
    inject_during_select = "F0|HB\n";
    mode_hold_ms = 4000u; reset_app();
    assert(!inject_during_select && rx_read == rx_write);
    assert(!control_link_fresh(vehicle_app_controller(), now_ms));
    register_key();
    unsigned id = make_response(1, response, sizeof(response));
    feed_line(response);                                       /* policy may allow ... */
    assert(vehicle_app_display()->actuation != RES_OK);        /* ... but no movement */
    assert(!vehicle_app_controller()->moving && applied.servo_us == 0);
    (void)id;
    heartbeat();                                               /* a new HB after selection */
    id = make_response(1, response, sizeof(response));
    feed_line(response);
    assert(vehicle_app_display()->actuation == RES_OK && vehicle_app_controller()->moving);

    /* A line split by the drop: its tail after selection is discarded, never run. */
    inject_during_select = "F0|H";
    mode_hold_ms = 300u; reset_app();
    feed_bytes("B\n", 2u);
    assert(has_log("RX DROP"));
    heartbeat();
    assert(control_link_fresh(vehicle_app_controller(), now_ms));

    /* Held past VC_MODE_SELECT_MAX_MS: the mode on screen is confirmed while held. */
    mode_hold_ms = VC_MODE_SELECT_MAX_MS + 5000u; reset_app();
    assert(mode_hold_ms > 0u);
    assert(has_log("MODE SELECT") && vehicle_app_mode() == vehicle_app_display()->mode);
    mode_hold_ms = 0;
}
#endif

/* Regression: no open request after SYNC; real signed packets drive UI. */
/* 1106: debounced door switch is reported once per change as a debug log for
 * the demo page; bounce shorter than DEBOUNCE_MS is never reported. */
static size_t door_state_logs(const char *which) {
    size_t n = 0;
    for (size_t i = 0; i < log_count; ++i) if (strstr(logs[i], which)) ++n;
    return n;
}
static void test_door_state_log(void) {
    reset_app();
    assert(door_state_logs("DOOR STATE CLOSED") == 1 && door_state_logs("DOOR STATE OPEN") == 0);
    input_state.door_closed = false; advance(5);
    input_state.door_closed = true; advance(DEBOUNCE_MS + 5);       /* bounce */
    assert(door_state_logs("DOOR STATE OPEN") == 0);
    set_door(false);
    assert(door_state_logs("DOOR STATE OPEN") == 1);
    advance(100); assert(door_state_logs("DOOR STATE OPEN") == 1);  /* once per change */
    set_door(true);
    assert(door_state_logs("DOOR STATE CLOSED") == 2);
    assert(!vehicle_app_controller()->moving);                      /* log only, no actuation */
}

static void test_live_key_display(void) {
    char sync[256], replay[256], response[160];
    reset_app(); register_key(); heartbeat();
    authenticate(1, 'A', "00", 3); complete_servo(false);
    make_sync(1, 0, sync, sizeof(sync)); feed_line(sync);
    assert(vehicle_app_display()->remaining == (APP_POLICY_MODE == 'C' ? 4 : -1));
    assert(!vehicle_app_controller()->moving);
    strcpy(replay, sync);
    authenticate(1, 'A', "00", 3); complete_servo(false);
    feed_line(replay); /* Same nonce must not refresh either state or screen. */
    assert(vehicle_app_display()->remaining == (APP_POLICY_MODE == 'C' ? 3 : -1));
    keepalive_for(2000);
    make_sync(2, 1, sync, sizeof(sync));
    sync[strlen(sync)-1] = sync[strlen(sync)-1] == '0' ? '1' : '0';
    feed_line(sync);
    assert(vehicle_app_display()->policy == 'A');
    assert(vehicle_app_display()->remaining == (APP_POLICY_MODE == 'C' ? 3 : -1));
    keepalive_for(2000);
    make_sync(2, 1, sync, sizeof(sync)); feed_line(sync);
    assert(vehicle_app_display()->policy == 'D');
    assert(!strcmp(vehicle_app_display()->reason,"03"));
    assert(vehicle_app_display()->remaining == 0);
    assert(!vehicle_app_controller()->moving); /* Display update does not move servo. */
    sk_key_view_t view;
    assert(sk_get_key_view(TEST_KID,&view));
    assert(view.remaining == (APP_POLICY_MODE == 'C' ? 3 : -1)); /* No policy mutation. */
    authenticate(1,'D',"03",3); /* Wire keeps original raw counter. */
    register_key();
    assert(vehicle_app_display()->policy == 'D' && vehicle_app_display()->remaining == 0);

    /* Another key's registration/RES selects that key, not the last sync entry. */
    uint8_t tag[32]; char th[65], key[160];
    sk_key_tag(8,UINT32_MAX,4,0,3,tag); hex_encode(tag,32,th);
    snprintf(key,sizeof(key),"01|KEY|00000008|FFFFFFFF|04|00|03|%s",th);
    feed_line(key);
    assert(!strcmp(vehicle_app_display()->kid,"00000008"));
    assert(vehicle_app_display()->policy == 'K');
    keepalive_for(2000); make_sync(3,1,sync,sizeof(sync)); feed_line(sync);
    assert(vehicle_app_display()->policy == 'K');
    assert(vehicle_app_display()->remaining == (APP_POLICY_MODE == 'C' ? 4 : -1));
    authenticate(1,'D',"03",3);
    assert(!strcmp(vehicle_app_display()->kid,"00000007"));

    if (APP_POLICY_MODE == 'C') {
        reset_app(); register_key(); heartbeat();
        for (unsigned i=0;i<4;++i) { authenticate(1,'A',"00",3-i); complete_servo(false); heartbeat(); }
        authenticate(1,'D',"05",0);
        make_sync(1,0,sync,sizeof(sync)); feed_line(sync);
        assert(vehicle_app_display()->policy == 'W' && vehicle_app_display()->remaining == 4);
        assert(!vehicle_app_controller()->moving);
    }
    reset_app(); register_key();
    (void)make_response(3,response,sizeof(response)); feed_line(response);
    assert(vehicle_app_display()->policy == 'D');
    assert(!strcmp(vehicle_app_display()->reason,"09") && vehicle_app_display()->remaining == 0);
    puts("PASS live OLED state: refill, revoke, replay/tamper rejected, multi-key, refill clears 05, return; wire/core unchanged");
}

static void test_servo_calibration_command(void) {
#if TEST_BUILD && VC_ENABLE_SERVO
    reset_app();
    feed_line("TEST SERVO 1500");                 /* bench heartbeat required */
    assert(has_log("TEST RESULT=LINK_STALE") && applied.servo_us == 0);
    heartbeat();
    feed_line("TEST SERVO 1500");
    assert(has_log("TEST SERVO_US=1500") && applied.servo_us == 1500);
    advance(50); heartbeat();
    assert(applied.servo_us == 1500);             /* held across control ticks */
    feed_line("TEST STATUS");
    assert(applied.servo_us == 1500);             /* STATUS keeps calibration */
    feed_line("TEST SERVO 400");
    assert(has_log("TEST RESULT=RANGE") && applied.servo_us == 1500);
    feed_line("TEST SERVO 15x0");
    assert(applied.servo_us == 1500);
    feed_line("TEST SERVO 2500");
    assert(has_log("TEST SERVO_US=2500") && applied.servo_us == 2500);
    feed_line("TEST SERVO 0");
    assert(applied.servo_us == vehicle_app_controller()->output.servo_us);
    feed_line("TEST SERVO 1800");
    assert(applied.servo_us == 1800);
    feed_line("TEST UNLOCK");                     /* a real actuation ends calibration */
    complete_servo(false);
    assert(applied.servo_us == SERVO_UNLOCK_US);
    heartbeat();
    feed_line("TEST SERVO 1800");
    assert(applied.servo_us == 1800);
    feed_line("TEST STOP");                       /* other commands end calibration */
    assert(applied.servo_us == vehicle_app_controller()->output.servo_us);
    heartbeat();
    feed_line("TEST SERVO 1600");
    assert(applied.servo_us == 1600);
    io_fault = true;
    feed_line("00|HB");
    assert(vehicle_app_controller()->fault == FAULT_IO && applied.servo_us == 0);
    feed_line("TEST SERVO 1600");
    assert(has_log("TEST RESULT=FAULT") && applied.servo_us == 0);
    puts("PASS TEST SERVO: heartbeat required, 0/500..2500 only, held, STATUS keeps, other command/fault clears");
#endif
}

static void test_rtc_boot_log_and_bench_commands(void) {
#if VC_ENABLE_RTC
    stub_rtc_ok = false;
    reset_app();
    assert(has_log("RTC NG: B/D period keys denied (04)"));
    assert(!vehicle_app_display()->rtc_bad);       /* C mode needs no clock */
    assert(rtc_parse("2026-11-28 15:00:00", &stub_rtc)); stub_rtc_ok = true;
    reset_app();
    assert(has_log("RTC 2026-11-28 15:00:00 KST UNIX=1795845600"));
#if TEST_BUILD
    feed_line("TEST RTC");
    assert(has_log("TEST RTC=2026-11-28 15:00:00 KST UNIX=1795845600"));
    feed_line("TEST RTC SET 2026-11-28 16:30:05");
    assert(has_log("TEST RTC SET=2026-11-28 16:30:05 KST UNIX=1795851005") && has_log("TEST RESULT=OK"));
    log_count = 0;
    feed_line("TEST RTC SET 2026-13-01 00:00:00");
    assert(has_log("TEST RTC SET FAILED") && has_log("TEST RESULT=RANGE"));
    feed_line("TEST RTC");
    assert(has_log("TEST RTC=2026-11-28 16:30:05 KST UNIX=1795851005"));
#endif
    puts("PASS RTC: boot log valid/NG, KST->UTC unix, TEST RTC / RTC SET (bad date rejected)");
#endif
}

int main(void) {
    test_live_key_display();
    test_door_state_log();
    test_heartbeat_and_servo_bridge();
    test_policy_count_duplicate_and_sync();
    test_three_misses_online_indicator();
    test_tamper_and_replay();
    test_frames_and_test_build_boundary();
    test_motor_failure_does_not_refund();
    test_reauth_local_stop_cutoff();
    test_buzzer_sounds();
    test_relock_boot_and_unknown();
    test_relock_debounce_and_one_shot();
    test_relock_busy_edge_not_deferred();
    test_relock_faults_and_stop();
    test_relock_physical_cycles_keep_policy();
    test_key_registration_display();
    test_servo_calibration_command();
    test_rtc_boot_log_and_bench_commands();
#if VC_DEMO_MODE_SELECT
    test_demo_mode_select();
    test_mode_select_drops_buffered_rx();
    puts("PASS demo mode select: default, hold -> other mode (policy switched), hold longer -> wrap, RX during select dropped (R1), 15s timeout");
#endif
    printf("PASS app integration: policy=%c, endpoints=%d, motors=%d; real KEY/REQ/RESP/SYNC, HB, servo, count, tamper, replay, revoke, framing\n",
           APP_POLICY_MODE, CONTROL_USE_ENDPOINTS, VC_ENABLE_MOTORS);
    printf("PASS relock=%d: boot/UNKNOWN idle, debounce, one-shot, busy edge, faults/stop, A/C physical cycles; KEYOK/KEYNG display\n",
           VC_RELOCK_ON_DOOR_CLOSE);
    return 0;
}
