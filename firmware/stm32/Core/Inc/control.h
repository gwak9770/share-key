#ifndef VEHICLE_CONTROL_H
#define VEHICLE_CONTROL_H

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    FAULT_NONE, FAULT_SENSOR, FAULT_LINK, FAULT_ESTOP,
    FAULT_DOOR, FAULT_LOCK, FAULT_SERVO, FAULT_IO
} Fault;
typedef enum { ACT_LOCK, ACT_UNLOCK, ACT_MOTOR } Action;
typedef enum {
    RES_OK, RES_NOT_READY, RES_NOT_ARMED, RES_FAULT,
    RES_BUSY, RES_DOOR_OPEN, RES_NOT_LOCKED, RES_RANGE, RES_LINK_STALE
} Result;
typedef enum { LOCK_UNKNOWN, LOCK_LOCKED, LOCK_UNLOCKED } LockPosition;

/* Inputs are logical values, not electrical pin levels. */
typedef struct { bool door_closed, locked, unlocked, estop; } Inputs;
typedef struct { int motor; uint16_t servo_us; } Outputs;
typedef struct {
    Inputs stable, candidate;
    Outputs output;
    uint32_t changed_at[3], last_heartbeat, move_started, last_ramp, zero_at;
    bool qualified[3], ready, armed, moving, want_lock, heartbeat_seen;
    int motor_target, last_direction;
    Fault fault;
    LockPosition position;
} Controller;

void control_init(Controller *c, uint32_t now);
void control_tick(Controller *c, Inputs raw, uint32_t now);
/* A received heartbeat only updates liveness. It never arms or clears faults. */
void control_heartbeat(Controller *c, uint32_t now);
Result control_arm(Controller *c, uint32_t now);
Result control_request(Controller *c, Action action, int value, uint32_t now);
Result control_clear(Controller *c);
/* Unconditional local stop; use this for stop/error paths, not a motor command. */
void control_stop(Controller *c, uint32_t now);
void control_trip(Controller *c, Fault fault, uint32_t now);
bool control_link_fresh(const Controller *c, uint32_t now);
bool control_lock_known(const Controller *c);
bool control_is_locked(const Controller *c);
bool control_is_unlocked(const Controller *c);
/* True only for a known position inferred from a completed timed command. */
bool control_position_estimated(const Controller *c);
const char *control_result(Result r);
const char *control_fault(Fault f);

#endif
