#include "vehicle_app.h"
#include "config.h"
#include "line_reader.h"
#include "sharekey.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

static Controller controller;
static VehicleDisplay display;
static LineReader reader;
static bool initialized, server_online, allow_led, deny_led;
static uint32_t allow_started, deny_started;
static bool last_moving, return_candidate, return_stable, return_released;
static uint32_t return_changed;
static Fault reported_fault;
#if VC_ENABLE_SERVO && VC_RELOCK_ON_DOOR_CLOSE
static bool door_observed, previous_door_closed;
#endif

static bool hex_digit(char c) {
    return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F') || (c >= 'a' && c <= 'f');
}
static bool has_rid(const char *s) {
    return strlen(s) >= 3u && hex_digit(s[0]) && hex_digit(s[1]) && s[2] == '|';
}
static const char *position_name(void) {
    if (!control_lock_known(&controller)) return "UNKNOWN";
    return control_is_locked(&controller) ? "LOCKED" : "UNLOCKED";
}
static void update_control(uint32_t now) {
    control_tick(&controller, vc_platform_inputs(), now);
    vc_platform_apply(controller.output);
    if (controller.fault != reported_fault) {
        reported_fault = controller.fault;
        char msg[96];
        snprintf(msg, sizeof(msg), "CONTROL FAULT=%s", control_fault(controller.fault));
        vc_platform_log(msg);
    }
    if (last_moving && !controller.moving && controller.fault == FAULT_NONE) {
        char msg[96];
        snprintf(msg, sizeof(msg), "ACT DONE POSITION=%s SOURCE=%s", position_name(),
                 control_position_estimated(&controller) ? "ESTIMATED" : "ENDPOINT");
        vc_platform_log(msg);
    }
    last_moving = controller.moving;
}
static Result request(Action action, int value, uint32_t now) {
    update_control(now);
    Result result = control_arm(&controller, now);
    if (result == RES_OK) result = control_request(&controller, action, value, now);
    vc_platform_apply(controller.output);
    last_moving = controller.moving;
    return result;
}

/* 1106 (권기백): report the debounced door switch as a '#' debug log line
 * ("# DOOR STATE OPEN" / "# DOOR STATE CLOSED") so the Pi relay can show the
 * real door on the demo web page. Log only — not a protocol message (00 §5:
 * '#' lines are debug logs), no effect on policy, actuation or relock. */
static int door_logged = -1;
static void log_door_state(void) {
    if (!controller.qualified[0]) return;
    int closed = controller.stable.door_closed ? 1 : 0;
    if (closed == door_logged) return;
    door_logged = closed;
    vc_platform_log(closed ? "DOOR STATE CLOSED" : "DOOR STATE OPEN");
}

static void relock_on_door_close(void) {
#if VC_ENABLE_SERVO && VC_RELOCK_ON_DOOR_CLOSE
    /* The first debounced observation is a baseline, never a closing edge.
     * Retain the last qualified value across switch bounce. */
    if (!controller.qualified[0]) return;
    bool closed = controller.stable.door_closed;
    bool closing = door_observed && !previous_door_closed && closed;
    previous_door_closed = closed;
    door_observed = true;
    /* Consume the edge even when blocked; never defer motion until a later
     * heartbeat, fault clear, or end of another movement. UNKNOWN-at-close
     * is still a proposal, so this release only relocks from UNLOCKED. */
    if (!closing || !controller.armed || controller.fault != FAULT_NONE ||
        !control_is_unlocked(&controller)) return;
    Result result = vehicle_app_request_lock();
    char msg[80];
    snprintf(msg, sizeof(msg), "DOOR CLOSED -> LOCK ACT=%s", control_result(result));
    vc_platform_log(msg);
#endif
}

static char active_mode;
char vehicle_app_mode(void) { return active_mode; }

/* 1104 (곽동규 검토 R1): bytes received while the boot selection waits are
 * never dispatched later. A buffered HB would otherwise be stamped with the
 * time it is processed, not when it arrived, and look fresh for ~2s. Drop the
 * queue; only if the drop stopped inside a line, discard up to the next '\n'
 * so its tail cannot run as a valid suffix. Lines that arrive complete after
 * selection are kept. */
#if VC_DEMO_MODE_SELECT
static bool select_cut_line;  /* last dropped byte was inside a line */
static void drop_rx_during_select(void) {
    int b;
    while ((b = vc_platform_rx_get()) >= 0) select_cut_line = b != '\n';
}
#endif

/* 1103: demo-only boot selection (config.h VC_DEMO_MODE_SELECT). Runs before
 * sk_init(), so the policy core still gets a single mode for this boot.
 * Release USER to confirm; after VC_MODE_SELECT_MAX_MS the mode on screen at
 * that moment is confirmed even if USER is still held. */
static char select_mode(void) {
    char mode = APP_POLICY_MODE;
#if VC_DEMO_MODE_SELECT
    static const char list[] = VC_DEMO_MODES;
    char valid[sizeof(list)];
    size_t n = 0;
    for (size_t i = 0; list[i]; ++i)
        if ((list[i] == 'A' || list[i] == 'C') && !memchr(valid, list[i], n)) valid[n++] = list[i];
    if (n < 2u || !vc_platform_mode_button()) return mode;
    select_cut_line = false;
    size_t at = 0;
    while (at < n && valid[at] != mode) ++at;
    at = at < n ? (at + 1u) % n : 0u;        /* held: start at the mode after the default */
    uint32_t start = vc_platform_millis(), step = start;
    char msg[48];
    for (;;) {
        display.mode = valid[at];
        snprintf(msg, sizeof(msg), "MODE SELECT %c (release USER to confirm)", valid[at]);
        vc_platform_log(msg);
        for (;;) {
            vc_platform_service(&controller, &display);
            drop_rx_during_select();
            uint32_t now = vc_platform_millis();
            if (!vc_platform_mode_button() || (uint32_t)(now - start) >= VC_MODE_SELECT_MAX_MS) {
                drop_rx_during_select();
                if (select_cut_line) line_reader_discard(&reader);
                return valid[at];
            }
            if ((uint32_t)(now - step) >= VC_MODE_STEP_MS) { step = now; break; }
        }
        at = (at + 1u) % n;
    }
#else
    return mode;
#endif
}

bool vehicle_app_init(void) {
    initialized = false;
    if (!vc_platform_init()) return false;
    uint32_t now = vc_platform_millis();
    control_init(&controller, now);
    line_reader_init(&reader);
    memset(&display, 0, sizeof(display));
    display.policy = '-'; display.remaining = -1; display.actuation = RES_NOT_READY;
    memcpy(display.reason, "--", 3u);
    allow_led = deny_led = server_online = last_moving = false;
    return_candidate = return_stable = return_released = false;
    return_changed = now; reported_fault = FAULT_NONE;
#if VC_ENABLE_SERVO && VC_RELOCK_ON_DOOR_CLOSE
    door_observed = previous_door_closed = false;
#endif
    door_logged = -1;
    sk_set_sync_period(2000u);
    active_mode = select_mode();
    display.mode = active_mode;
    sk_init(active_mode);
    vc_platform_apply(controller.output);
    vc_platform_log("boot F429 vehicle control v2");
    char msg[100];
    snprintf(msg, sizeof(msg), "MODE=%c ENDPOINTS=%u SERVO=%u MOTOR=%u TEST=%u",
             active_mode, (unsigned)CONTROL_USE_ENDPOINTS, (unsigned)VC_ENABLE_SERVO,
             (unsigned)VC_ENABLE_MOTORS, (unsigned)TEST_BUILD);
    vc_platform_log(msg);
    initialized = true;
    return true;
}

#if TEST_BUILD
static void test_command(const char *s, uint32_t now) {
    Result r = RES_RANGE;
    if (!strcmp(s, "STATUS")) {
        char msg[180];
        snprintf(msg, sizeof(msg), "TEST STATUS ARM=%u READY=%u LINK=%u DOOR=%u POS=%s EST=%u MOTOR=%d FAULT=%s",
                 controller.armed, controller.ready, control_link_fresh(&controller, now),
                 controller.stable.door_closed, position_name(), control_position_estimated(&controller),
                 controller.output.motor, control_fault(controller.fault));
        vc_platform_log(msg); return;
    }
    if (!strcmp(s, "STOP")) { vehicle_app_stop(); r = RES_OK; }
    else if (!strcmp(s, "CLEAR")) r = vehicle_app_clear_fault();
    else if (!strcmp(s, "LOCK") && VC_ENABLE_SERVO) r = request(ACT_LOCK, 0, now);
    else if (!strcmp(s, "UNLOCK") && VC_ENABLE_SERVO) r = request(ACT_UNLOCK, 0, now);
    else if (!strncmp(s, "MOTOR ", 6) && VC_ENABLE_MOTORS) {
        char *end; errno = 0;
        const char *v = s + 6;
        bool numeric = (*v >= '0' && *v <= '9') || (*v == '-' && v[1] >= '0' && v[1] <= '9');
        long n = strtol(v, &end, 10);
        if (numeric && !errno && end != v && !*end && n >= -MOTOR_MAX_PERMILLE && n <= MOTOR_MAX_PERMILLE)
            r = request(ACT_MOTOR, (int)n, now);
    }
    char msg[80]; snprintf(msg, sizeof(msg), "TEST RESULT=%s", control_result(r));
    vc_platform_log(msg);
}
#endif

static void dispatch(char *line, uint32_t now) {
#if TEST_BUILD
    if (!strncmp(line, "TEST ", 5u)) { test_command(line + 5, now); return; }
#endif
    if (!has_rid(line)) return;
    if (!strcmp(line + 3, "HB")) {
        control_heartbeat(&controller, now);  /* no reply, no arm, no fault clear */
        return;
    }
    /* Original shared policy source owns every official KEY/REQ/RESP/SYNC field. */
    sk_handle_line(line);
}

/* Read the selected KID from the real policy state, never from incoming SYNC
 * text or a second shadow counter. Called after core processing has finished. */
static void refresh_key_display(bool synced) {
    sk_key_view_t view;
    if (!display.kid[0] || display.policy == 'N') return;
    uint32_t kid = (uint32_t)strtoul(display.kid, NULL, 16);
    if (!sk_get_key_view(kid, &view)) return;
    display.remaining = strcmp(view.blocked_reason, "00") ? 0 : view.remaining;
    if (strcmp(view.blocked_reason, "00")) {
        /* Effective usable count is zero; the raw core counter stays intact.
         * Keep a newer failed request's 01/02 etc. reason for diagnostics. */
        if (synced || display.policy != 'D' || !strcmp(display.reason, "05")) {
            display.policy = 'D';
            memcpy(display.reason, view.blocked_reason, 3u);
        }
        display.actuation_attempted = false;
    } else if (display.policy == 'D' && !strcmp(display.reason, "05") &&
               display.remaining != 0) {
        /* A refill clears stale count exhaustion, but is not an auth grant. */
        display.policy = 'W'; memcpy(display.reason, "--", 3u);
        display.actuation_attempted = false;
    }
}

void vehicle_app_step(void) {
    if (!initialized) return;
    uint32_t now = vc_platform_millis();
    if (vc_platform_take_io_fault()) {
        control_trip(&controller, FAULT_IO, now);
        line_reader_discard(&reader); /* never execute a valid suffix after loss */
    }
    update_control(now);
    for (unsigned count = 0; count < VC_RX_BUDGET; ++count) {
        int b = vc_platform_rx_get();
        if (b < 0) break;
        LineResult state = line_reader_feed(&reader, (unsigned char)b);
        if (state == LINE_READY) {
            now = vc_platform_millis();
            update_control(now);
            dispatch(reader.text, now);
        } else if (state == LINE_DROPPED) {
            vc_platform_log("RX DROP invalid/overlength line");
        }
    }
    sk_poll();
    refresh_key_display(false);
    now = vc_platform_millis();
    update_control(now);
    log_door_state();
    relock_on_door_close();
    if (VC_ENABLE_RETURN_BUTTON) {
        bool raw = vc_platform_return_pressed();
        if (raw != return_candidate) { return_candidate = raw; return_changed = now; }
        if ((uint32_t)(now - return_changed) >= DEBOUNCE_MS) {
            if (!raw) return_released = true;
            if (raw && !return_stable && return_released) vehicle_on_return_button();
            return_stable = raw;
        }
    }
    if (allow_led && (uint32_t)(now - allow_started) >= VC_LED_PULSE_MS) allow_led = false;
    if (deny_led && (uint32_t)(now - deny_started) >= VC_LED_PULSE_MS) deny_led = false;
    vc_platform_indicators(allow_led, server_online, deny_led || controller.fault != FAULT_NONE);
    vc_platform_service(&controller, &display);
}

const Controller *vehicle_app_controller(void) { return &controller; }
const VehicleDisplay *vehicle_app_display(void) { return &display; }
Result vehicle_app_request_lock(void) {
    if (!initialized || !VC_ENABLE_SERVO) return RES_NOT_READY;
    return request(ACT_LOCK, 0, vc_platform_millis());
}
void vehicle_app_stop(void) {
    control_stop(&controller, vc_platform_millis());
    vc_platform_apply(controller.output);
    last_moving = false;
}
Result vehicle_app_clear_fault(void) {
    update_control(vc_platform_millis());
    return control_clear(&controller); /* does not arm or move */
}
#if defined(__GNUC__)
__attribute__((weak))
#endif
void vehicle_on_return_button(void) {
    vc_platform_log("RETURN BUTTON: select target KID in application; no key state changed");
}

/* The unchanged sharekey.c calls these hooks AFTER the original decision path. */
void sk_port_actuate(int cmd, int remaining) {
    uint32_t now = vc_platform_millis();
    display.policy = 'A'; memcpy(display.reason, "00", 3u);
    display.command = cmd; display.remaining = remaining;
    display.actuation_attempted = false; display.actuation = RES_NOT_READY;
    allow_led = true; deny_led = false; allow_started = now;
    if (cmd == 3) {
        vc_platform_log("AUTH ALLOW RETURN: key marked returned; no physical command assigned");
        return;
    }
    if ((cmd == 1 && !VC_ENABLE_SERVO) || (cmd == 2 && !VC_ENABLE_MOTORS)) {
        vc_platform_log("AUTH ALLOW ACT DISABLED: output feature disabled in config.h");
        return;
    }
    Result r = RES_RANGE;
    if (cmd == 1) r = request(ACT_UNLOCK, 0, now);
    else if (cmd == 2) r = request(ACT_MOTOR, MOTOR_START_PERMILLE, now);
    display.actuation = r; display.actuation_attempted = true;
    char msg[128];
    snprintf(msg, sizeof(msg), "AUTH ALLOW CMD=%02X LEFT=%d ACT=%s", cmd, remaining, control_result(r));
    vc_platform_log(msg);
    /* Policy RES=A remains policy permission. Failure never refunds a count. */
}
void sk_port_deny(int cmd, const char *reason) {
    display.policy = 'D'; display.command = cmd;
    display.reason[0] = reason && reason[0] ? reason[0] : '-';
    display.reason[1] = reason && reason[0] && reason[1] ? reason[1] : '-';
    display.reason[2] = '\0';
    display.remaining = -1; display.actuation_attempted = false;
    deny_led = true; allow_led = false; deny_started = vc_platform_millis();
    /* A rejected credential never becomes a movement command or global stop. */
}
void sk_port_send_line(const char *line) {
    /* Mirror only the policy core's OUTGOING fixed-format RES to the display.
     * Denial hooks have no remaining-count argument; the official response
     * supplies it, including early REQ rejection. Never change the wire or
     * use display parsing to grant an action. */
    bool result_line = strlen(line) == 23u && has_rid(line) &&
        !strncmp(line + 3, "RES|", 4u) && line[15] == '|' &&
        line[17] == '|' && line[20] == '|' &&
        (line[16] == 'A' || line[16] == 'D' || line[16] == 'H');
    if (result_line) {
        for (unsigned i = 7; i < 15; ++i)
            if (!hex_digit(line[i])) result_line = false;
        for (unsigned i = 18; i < 23; ++i)
            if (i != 20u && !hex_digit(line[i])) result_line = false;
    }
    if (result_line) {
        char remaining_hex[3] = {line[21], line[22], '\0'};
        unsigned remaining = (unsigned)strtoul(remaining_hex, NULL, 16);
        memcpy(display.kid, line + 7, 8u); display.kid[8] = '\0';
        display.policy = line[16];
        display.reason[0] = line[18]; display.reason[1] = line[19];
        display.reason[2] = '\0';
        display.remaining = remaining == 255u ? -1 : (int)remaining;
        if (display.policy != 'A') display.actuation_attempted = false;
    }
    /* 1103 (권기백): mirror the policy core's KEY registration answer to the
     * display only. "RR|KEYOK|KKKKKKKK" (17) / "RR|KEYNG|KKKKKKKK|CC" (20). */
    size_t key_len = strlen(line);
    bool key_ok = key_len == 17u && has_rid(line) && !strncmp(line + 3, "KEYOK|", 6u);
    bool key_ng = key_len == 20u && has_rid(line) && !strncmp(line + 3, "KEYNG|", 6u) &&
        line[17] == '|' && hex_digit(line[18]) && hex_digit(line[19]);
    if (key_ok || key_ng) {
        for (unsigned i = 9; i < 17; ++i)
            if (!hex_digit(line[i])) key_ok = key_ng = false;
    }
    if (key_ok || key_ng) {
        display.policy = key_ok ? 'K' : 'N';
        display.reason[0] = key_ok ? '0' : line[18];
        display.reason[1] = key_ok ? '0' : line[19];
        display.reason[2] = '\0';
        memcpy(display.kid, line + 9, 8u); display.kid[8] = '\0';
        display.remaining = -1; display.actuation_attempted = false;
    }
    if (has_rid(line) && !strncmp(line + 3, "SYNCACK|", 8u))
        refresh_key_display(true); /* Core emits ACK only after authenticated apply. */
    vc_platform_send_line(line);
}
void sk_port_log(const char *line) {
    if (!strcmp(line, "server sync ok -> ONLINE")) server_online = true;
    if (!strcmp(line, "no server response -> OFFLINE")) server_online = false;
    vc_platform_log(line);
}
uint32_t sk_port_millis(void) { return vc_platform_millis(); }
uint32_t sk_port_unix_time(void) { return 0u; } /* A/C release; B/D compile-time blocked. */
void sk_port_random(uint8_t *out, size_t n) { vc_platform_random(out, n); }
void sk_app_run(void) {
    if (!vehicle_app_init()) vc_platform_panic();
    for (;;) vehicle_app_step();
}
