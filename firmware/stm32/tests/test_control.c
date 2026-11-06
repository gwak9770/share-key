#include "control.h"
#include "config.h"

#include <assert.h>
#include <stdio.h>

static Inputs closed = { true, false, false, false };
static Inputs sensed_locked = { true, true, false, false };
#if CONTROL_USE_ENDPOINTS
static Inputs sensed_unlocked = { true, false, true, false };
#endif

static void settle(Controller *c, Inputs in, uint32_t start) {
    control_init(c, start);
    control_tick(c, in, start);
    control_tick(c, in, start + DEBOUNCE_MS);
    assert(c->ready);
}

static uint32_t prepare_locked(Controller *c, uint32_t start) {
#if CONTROL_USE_ENDPOINTS
    settle(c, sensed_locked, start);
    uint32_t now = start + DEBOUNCE_MS;
    control_heartbeat(c, now);
    assert(control_arm(c, now) == RES_OK);
#else
    settle(c, closed, start);
    uint32_t now = start + DEBOUNCE_MS;
    control_heartbeat(c, now);
    assert(control_arm(c, now) == RES_OK);
    assert(control_request(c, ACT_LOCK, 0, now) == RES_OK);
    now += SERVO_TRAVEL_MS;
    control_tick(c, closed, now);
#endif
    assert(control_is_locked(c));
    return now;
}

static Inputs locked_input(void) {
    return CONTROL_USE_ENDPOINTS ? sensed_locked : closed;
}

static void test_boot_and_liveness(void) {
    Controller c;
    control_init(&c, 0);
    assert(!c.armed && !c.heartbeat_seen && !control_lock_known(&c));
    assert(c.output.motor == 0 && c.output.servo_us == 0);
    assert(control_arm(&c, 0) == RES_NOT_READY);
    settle(&c, closed, 0);
    assert(control_arm(&c, DEBOUNCE_MS) == RES_LINK_STALE);
    assert(!c.heartbeat_seen);
    control_heartbeat(&c, DEBOUNCE_MS);
    assert(!c.armed);
    assert(control_arm(&c, DEBOUNCE_MS + 1) == RES_OK);
    assert(c.last_heartbeat == DEBOUNCE_MS);
    control_tick(&c, closed, DEBOUNCE_MS + LINK_TIMEOUT_MS);
    assert(c.fault == FAULT_LINK && !c.armed);
    control_heartbeat(&c, DEBOUNCE_MS + LINK_TIMEOUT_MS + 1);
    assert(c.fault == FAULT_LINK && !c.armed);
    assert(control_arm(&c, DEBOUNCE_MS + LINK_TIMEOUT_MS + 1) == RES_FAULT);
    assert(control_clear(&c) == RES_OK);
    assert(!c.armed && c.output.motor == 0 && c.output.servo_us == 0);
    assert(control_arm(&c, DEBOUNCE_MS + LINK_TIMEOUT_MS + 1) == RES_OK);
}

static void test_unknown_and_servo(void) {
    Controller c;
    settle(&c, closed, 0);
    uint32_t now = DEBOUNCE_MS;
    control_heartbeat(&c, now);
    assert(control_arm(&c, now) == RES_OK);
    assert(control_request(&c, ACT_MOTOR, 100, now) == RES_NOT_LOCKED);
    assert(control_request(&c, ACT_UNLOCK, 0, now) == RES_OK);
    assert(c.output.servo_us == SERVO_UNLOCK_US && c.moving);
    assert(!control_lock_known(&c));
#if CONTROL_USE_ENDPOINTS
    control_tick(&c, closed, now + SERVO_MIN_SETTLE_MS);
    assert(c.moving);
    control_heartbeat(&c, now + SERVO_TIMEOUT_MS);
    control_tick(&c, closed, now + SERVO_TIMEOUT_MS);
    assert(c.fault == FAULT_SERVO && c.output.servo_us == 0);
    settle(&c, sensed_locked, 0);
    now = DEBOUNCE_MS;
    control_heartbeat(&c, now);
    assert(control_arm(&c, now) == RES_OK);
    assert(control_request(&c, ACT_UNLOCK, 0, now) == RES_OK);
    control_tick(&c, sensed_unlocked, now + 1);
    control_tick(&c, sensed_unlocked, now + 1 + DEBOUNCE_MS);
    assert(c.moving); /* Endpoints do not bypass minimum travel/settle time. */
    control_tick(&c, sensed_unlocked, now + SERVO_MIN_SETTLE_MS);
    assert(!c.moving && control_is_unlocked(&c));
    assert(!control_position_estimated(&c));
#else
    Inputs floating = { true, true, true, false };
    control_tick(&c, floating, now + SERVO_TRAVEL_MS - 1);
    assert(c.moving && !control_lock_known(&c) && c.fault == FAULT_NONE);
    control_tick(&c, floating, now + SERVO_TRAVEL_MS);
    assert(!c.moving && control_is_unlocked(&c));
    assert(control_position_estimated(&c));
    assert(!c.stable.locked && !c.stable.unlocked);
    assert(c.fault == FAULT_NONE && c.output.servo_us == SERVO_UNLOCK_US);
    control_tick(&c, closed, now + SERVO_TIMEOUT_MS);
    assert(c.fault == FAULT_NONE); /* No missing-endpoint timeout in this mode. */
#endif
    control_stop(&c, now + SERVO_TIMEOUT_MS + 1);
    assert(!control_lock_known(&c) && !c.armed && c.output.servo_us == 0);
}

static void test_motor_interlocks(void) {
    Controller c;
    uint32_t now = prepare_locked(&c, 0);
    Inputs in = locked_input();
    assert(control_request(&c, ACT_MOTOR, MOTOR_MAX_PERMILLE + 1, now) == RES_RANGE);
    assert(control_request(&c, ACT_MOTOR, 100, now) == RES_OK);
    control_tick(&c, in, now + MOTOR_RAMP_MS);
    assert(c.output.motor > 0 && c.output.motor <= 100);
    assert(control_request(&c, ACT_UNLOCK, 0, now + MOTOR_RAMP_MS) == RES_BUSY);
    Inputs opened = in;
    opened.door_closed = false;
    control_tick(&c, opened, now + MOTOR_RAMP_MS + 1);
    assert(c.fault == FAULT_DOOR && !c.armed && c.output.motor == 0);
    control_heartbeat(&c, now + MOTOR_RAMP_MS + 2);
    assert(c.fault == FAULT_DOOR && !c.armed);

    now = prepare_locked(&c, 0);
    Inputs stopped = in;
    stopped.estop = true;
    control_tick(&c, stopped, now + 1);
    assert(c.fault == FAULT_ESTOP && c.output.servo_us == 0 && !c.armed);
    assert(control_clear(&c) == RES_FAULT);

#if CONTROL_USE_ENDPOINTS
    now = prepare_locked(&c, 0);
    assert(control_request(&c, ACT_MOTOR, 100, now) == RES_OK);
    Inputs lost = in;
    lost.locked = false;
    control_tick(&c, lost, now + 1);
    assert(c.fault == FAULT_LOCK && c.output.motor == 0);
    settle(&c, sensed_locked, 0);
    Inputs conflict = sensed_locked;
    conflict.unlocked = true;
    control_tick(&c, conflict, DEBOUNCE_MS + 1);
    control_tick(&c, conflict, 2 * DEBOUNCE_MS + 1);
    assert(c.fault == FAULT_SENSOR && control_clear(&c) == RES_FAULT);
#else
    now = prepare_locked(&c, 0);
    control_stop(&c, now + 1);
    control_heartbeat(&c, now + 2);
    assert(control_arm(&c, now + 2) == RES_OK);
    assert(control_request(&c, ACT_MOTOR, 100, now + 2) == RES_NOT_LOCKED);
    assert(control_request(&c, ACT_LOCK, 0, now + 3) == RES_OK);
    control_stop(&c, now + 4);
    control_tick(&c, closed, now + 4 + SERVO_TRAVEL_MS);
    assert(!control_lock_known(&c)); /* Cancelled motion cannot finish in the background. */
#endif
}

#if CONTROL_USE_ENDPOINTS
static void test_endpoint_completion_deadline(void) {
    Controller c;
    uint32_t start = DEBOUNCE_MS;

    /* Even an already qualified target does not prove when motion completed
       if the first post-request tick arrives after the deadline. */
    settle(&c, sensed_unlocked, 0);
    control_heartbeat(&c, start);
    assert(control_arm(&c, start) == RES_OK);
    assert(control_request(&c, ACT_UNLOCK, 0, start) == RES_OK);
    control_tick(&c, sensed_unlocked, start + SERVO_TIMEOUT_MS + 1u);
    assert(c.fault == FAULT_SERVO && !c.moving && !c.armed);
    assert(c.output.servo_us == 0);

    /* The first qualified target sample at the exact deadline is too late. */
    settle(&c, sensed_locked, 0);
    control_heartbeat(&c, start);
    assert(control_arm(&c, start) == RES_OK);
    assert(control_request(&c, ACT_UNLOCK, 0, start) == RES_OK);
    control_tick(&c, sensed_unlocked, start + SERVO_TIMEOUT_MS - DEBOUNCE_MS);
    assert(c.moving && c.fault == FAULT_NONE);
    control_tick(&c, sensed_unlocked, start + SERVO_TIMEOUT_MS);
    assert(c.fault == FAULT_SERVO && !c.moving && c.output.servo_us == 0);

    /* A qualified sample one tick before the deadline completes normally. */
    settle(&c, sensed_locked, 0);
    control_heartbeat(&c, start);
    assert(control_arm(&c, start) == RES_OK);
    assert(control_request(&c, ACT_UNLOCK, 0, start) == RES_OK);
    control_tick(&c, sensed_unlocked, start + SERVO_TIMEOUT_MS - DEBOUNCE_MS - 1u);
    assert(c.moving && c.fault == FAULT_NONE);
    control_tick(&c, sensed_unlocked, start + SERVO_TIMEOUT_MS - 1u);
    assert(!c.moving && c.fault == FAULT_NONE && control_is_unlocked(&c));
    assert(c.output.servo_us == SERVO_UNLOCK_US);
    control_tick(&c, sensed_unlocked, start + SERVO_TIMEOUT_MS + 1u);
    assert(c.fault == FAULT_NONE && c.output.servo_us == SERVO_UNLOCK_US);
}
#endif

static void test_reversal_and_wrap(void) {
    Controller c;
    uint32_t now = prepare_locked(&c, 0);
    Inputs in = locked_input();
    assert(control_request(&c, ACT_MOTOR, 100, now) == RES_OK);
    while (c.output.motor < 100) {
        now += MOTOR_RAMP_MS;
        control_heartbeat(&c, now);
        control_tick(&c, in, now);
    }
    assert(control_request(&c, ACT_MOTOR, -100, now) == RES_OK);
    while (c.output.motor > 0) {
        now += MOTOR_RAMP_MS;
        control_heartbeat(&c, now);
        control_tick(&c, in, now);
    }
    uint32_t zero = now;
    control_tick(&c, in, zero + MOTOR_REVERSE_DEAD_MS - 1);
    assert(c.output.motor == 0);
    control_tick(&c, in, zero + MOTOR_REVERSE_DEAD_MS + MOTOR_RAMP_MS);
    assert(c.output.motor < 0);
    assert(control_request(&c, ACT_MOTOR, 0, zero + MOTOR_REVERSE_DEAD_MS + MOTOR_RAMP_MS) == RES_OK);
    assert(c.output.motor == 0);

    uint32_t start = UINT32_MAX - 100u;
    settle(&c, closed, start);
    uint32_t hb = start + DEBOUNCE_MS;
    control_heartbeat(&c, hb);
    assert(control_arm(&c, hb) == RES_OK);
    control_tick(&c, closed, hb + LINK_TIMEOUT_MS - 1);
    assert(c.armed && c.fault == FAULT_NONE);
    control_tick(&c, closed, hb + LINK_TIMEOUT_MS);
    assert(!c.armed && c.fault == FAULT_LINK);
}

int main(void) {
    test_boot_and_liveness();
    test_unknown_and_servo();
    test_motor_interlocks();
#if CONTROL_USE_ENDPOINTS
    test_endpoint_completion_deadline();
#endif
    test_reversal_and_wrap();
    printf("PASS control: endpoints=%d, boot unknown, real heartbeat, servo completion, interlocks, stop, reversal, rollover\n",
           CONTROL_USE_ENDPOINTS);
    return 0;
}
