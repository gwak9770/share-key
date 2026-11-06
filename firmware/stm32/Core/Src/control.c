#include "control.h"
#include "config.h"

#include <string.h>

_Static_assert(CONTROL_USE_ENDPOINTS == 0 || CONTROL_USE_ENDPOINTS == 1,
               "CONTROL_USE_ENDPOINTS must be 0 or 1");
_Static_assert(SERVO_TRAVEL_MS >= SERVO_MIN_SETTLE_MS &&
               SERVO_TRAVEL_MS < SERVO_TIMEOUT_MS,
               "Timed travel must be at least settle time and below timeout");
_Static_assert(MOTOR_MAX_PERMILLE > 0 && MOTOR_MAX_PERMILLE <= 1000,
               "Motor output bound must be 1..1000 permille");
_Static_assert(MOTOR_RAMP_STEP > 0 && MOTOR_RAMP_MS > 0,
               "Motor ramp interval and step must be positive");

static uint32_t age(uint32_t now, uint32_t before) { return now - before; }
static int sign(int n) { return (n > 0) - (n < 0); }

bool control_link_fresh(const Controller *c, uint32_t now) {
    return c->heartbeat_seen && age(now, c->last_heartbeat) < LINK_TIMEOUT_MS;
}

bool control_lock_known(const Controller *c) {
    return !c->moving && c->position != LOCK_UNKNOWN;
}
bool control_is_locked(const Controller *c) {
    return control_lock_known(c) && c->position == LOCK_LOCKED;
}
bool control_is_unlocked(const Controller *c) {
    return control_lock_known(c) && c->position == LOCK_UNLOCKED;
}
bool control_position_estimated(const Controller *c) {
    return !CONTROL_USE_ENDPOINTS && control_lock_known(c);
}

void control_init(Controller *c, uint32_t now) {
    memset(c, 0, sizeof(*c));
    c->last_heartbeat = c->last_ramp = c->zero_at = now;
    for (unsigned i = 0; i < 3; ++i) c->changed_at[i] = now;
    /* No synthetic heartbeat, known latch position, or boot movement. */
    c->position = LOCK_UNKNOWN;
}

void control_stop(Controller *c, uint32_t now) {
    if (c->output.motor) c->last_direction = sign(c->output.motor);
    c->armed = false;
    c->moving = false;
    c->motor_target = 0;
    c->output.motor = 0;
    c->output.servo_us = 0;
    c->zero_at = now;
    /* Released PWM no longer supports a software position estimate.
       In endpoint mode, a later tick may establish a measured position. */
    c->position = LOCK_UNKNOWN;
}

void control_trip(Controller *c, Fault fault, uint32_t now) {
    if (c->fault == FAULT_NONE) c->fault = fault;
    control_stop(c, now);
}

void control_heartbeat(Controller *c, uint32_t now) {
    c->heartbeat_seen = true;
    c->last_heartbeat = now;
}

static bool filter(Controller *c, unsigned i, bool raw, bool *candidate,
                   bool *stable, uint32_t now) {
    if (raw != *candidate) {
        *candidate = raw;
        c->changed_at[i] = now;
        c->qualified[i] = false;
    }
    if (age(now, c->changed_at[i]) >= DEBOUNCE_MS) {
        *stable = *candidate;
        c->qualified[i] = true;
    }
    return c->qualified[i];
}

void control_tick(Controller *c, Inputs raw, uint32_t now) {
    bool door_ready = filter(c, 0, raw.door_closed, &c->candidate.door_closed,
                             &c->stable.door_closed, now);
#if CONTROL_USE_ENDPOINTS
    bool lock_ready = filter(c, 1, raw.locked, &c->candidate.locked,
                             &c->stable.locked, now);
    bool unlock_ready = filter(c, 2, raw.unlocked, &c->candidate.unlocked,
                               &c->stable.unlocked, now);
    c->ready = door_ready && lock_ready && unlock_ready;
    c->position = LOCK_UNKNOWN;
    if (lock_ready && unlock_ready) {
        if (c->stable.locked && !c->stable.unlocked) c->position = LOCK_LOCKED;
        if (!c->stable.locked && c->stable.unlocked) c->position = LOCK_UNLOCKED;
    }
#else
    c->ready = door_ready;
    /* Floating or absent endpoint inputs cannot grant a lock estimate. */
    c->stable.locked = c->stable.unlocked = false;
    c->candidate.locked = c->candidate.unlocked = false;
    if (!raw.door_closed && c->position == LOCK_LOCKED) c->position = LOCK_UNKNOWN;
#endif
    c->stable.estop = raw.estop;
    if (raw.estop) control_trip(c, FAULT_ESTOP, now);
#if CONTROL_USE_ENDPOINTS
    if (lock_ready && unlock_ready && c->stable.locked && c->stable.unlocked)
        control_trip(c, FAULT_SENSOR, now);
#endif
    if (c->armed && !control_link_fresh(c, now)) control_trip(c, FAULT_LINK, now);

    /* Immediate raw stop, debounced permission. A bounce can stop the rig,
       but cannot grant motion. The estimated-mode claim remains an estimate. */
    if (c->output.motor || c->motor_target) {
        if (!raw.door_closed) control_trip(c, FAULT_DOOR, now);
#if CONTROL_USE_ENDPOINTS
        else if (!raw.locked || raw.unlocked) control_trip(c, FAULT_LOCK, now);
#else
        else if (!control_is_locked(c)) control_trip(c, FAULT_LOCK, now);
#endif
    }

    if (c->moving) {
        uint32_t elapsed = age(now, c->move_started);
        if (c->want_lock && !raw.door_closed) {
            control_trip(c, FAULT_DOOR, now);
        }
#if CONTROL_USE_ENDPOINTS
        else if (elapsed >= SERVO_TIMEOUT_MS) {
            /* A delayed sample cannot prove completion before the deadline. */
            control_trip(c, FAULT_SERVO, now);
        }
        else if (c->ready && elapsed >= SERVO_MIN_SETTLE_MS &&
                 (c->want_lock ? c->stable.locked : c->stable.unlocked)) {
            c->moving = false;
            /* Keep PWM to hold the calibrated position; position is measured. */
        }
#else
        else if (elapsed >= SERVO_TRAVEL_MS) {
            c->position = c->want_lock ? LOCK_LOCKED : LOCK_UNLOCKED;
            c->moving = false;
            /* Timed completion is never reported as measured feedback. */
        }
#endif
    }

    if (c->armed && c->fault == FAULT_NONE &&
        age(now, c->last_ramp) >= MOTOR_RAMP_MS) {
        c->last_ramp = now;
        int target = c->motor_target;
        int current = c->output.motor;
        if (current && sign(current) != sign(target)) target = 0;
        if (!current && target && c->last_direction &&
            sign(target) != c->last_direction &&
            age(now, c->zero_at) < MOTOR_REVERSE_DEAD_MS) target = 0;
        if (current < target) {
            current += MOTOR_RAMP_STEP;
            if (current > target) current = target;
        } else if (current > target) {
            current -= MOTOR_RAMP_STEP;
            if (current < target) current = target;
        }
        if (c->output.motor && !current) c->zero_at = now;
        if (current) c->last_direction = sign(current);
        c->output.motor = current;
    }
}

Result control_arm(Controller *c, uint32_t now) {
    if (c->fault != FAULT_NONE) return RES_FAULT;
    if (!c->ready) return RES_NOT_READY;
    if (c->stable.estop) return RES_FAULT;
    if (!control_link_fresh(c, now)) {
        if (c->armed) control_trip(c, FAULT_LINK, now);
        return RES_LINK_STALE;
    }
    c->armed = true;
    return RES_OK;
}

Result control_request(Controller *c, Action action, int value, uint32_t now) {
    if (c->fault != FAULT_NONE) return RES_FAULT;
    if (!c->ready) return RES_NOT_READY;
    if (!c->armed) return RES_NOT_ARMED;
    if (!control_link_fresh(c, now)) {
        control_trip(c, FAULT_LINK, now);
        return RES_LINK_STALE;
    }
    if (c->moving) return RES_BUSY;
    switch (action) {
    case ACT_LOCK:
    case ACT_UNLOCK:
        if (c->output.motor || c->motor_target) return RES_BUSY;
        if (action == ACT_LOCK && !c->stable.door_closed) return RES_DOOR_OPEN;
        c->want_lock = action == ACT_LOCK;
        c->output.servo_us = c->want_lock ? SERVO_LOCK_US : SERVO_UNLOCK_US;
        c->position = LOCK_UNKNOWN;
        c->moving = true;
        c->move_started = now;
        return RES_OK;
    case ACT_MOTOR:
        if (value < -MOTOR_MAX_PERMILLE || value > MOTOR_MAX_PERMILLE) return RES_RANGE;
        if (value && !c->stable.door_closed) return RES_DOOR_OPEN;
        if (value && !control_is_locked(c)) return RES_NOT_LOCKED;
        c->motor_target = value;
        if (!value) {
            if (c->output.motor) c->last_direction = sign(c->output.motor);
            c->output.motor = 0;
            c->zero_at = now;
        }
        return RES_OK;
    default:
        return RES_RANGE;
    }
}

Result control_clear(Controller *c) {
    if (c->armed || !c->ready) return RES_NOT_READY;
    if (c->stable.estop) return RES_FAULT;
#if CONTROL_USE_ENDPOINTS
    if (c->stable.locked && c->stable.unlocked) return RES_FAULT;
#endif
    c->fault = FAULT_NONE;
    return RES_OK; /* An explicit local clear does not arm or move. */
}

const char *control_result(Result r) {
    static const char *const names[] = {
        "OK", "NOT_READY", "NOT_ARMED", "FAULT", "BUSY",
        "DOOR_OPEN", "NOT_LOCKED", "RANGE", "LINK_STALE"
    };
    return (unsigned)r < sizeof(names) / sizeof(names[0]) ? names[r] : "UNKNOWN";
}

const char *control_fault(Fault f) {
    static const char *const names[] = {
        "NONE", "SENSOR_CONFLICT", "LINK_TIMEOUT", "ESTOP",
        "DOOR_OPEN", "LOCK_LOST", "SERVO_TIMEOUT", "IO"
    };
    return (unsigned)f < sizeof(names) / sizeof(names[0]) ? names[f] : "UNKNOWN";
}
