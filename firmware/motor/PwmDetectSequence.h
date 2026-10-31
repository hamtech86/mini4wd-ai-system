#ifndef MINI4WD_PWM_DETECT_SEQUENCE_H
#define MINI4WD_PWM_DETECT_SEQUENCE_H

#include <stdint.h>

namespace PwmDetectSequence {

static const uint8_t FIRST_PWM = 0;
static const uint8_t LAST_PWM = 30;
static const uint32_t STAGE_DURATION_MS = 10000UL;

enum State : uint8_t {
    IDLE = 0,
    RUNNING,
    COMPLETE,
    ABORTED
};

struct Snapshot {
    State state;
    uint8_t stage_index;
    uint8_t pwm;
    uint32_t stage_elapsed_ms;
};

class Sequence {
public:
    Sequence()
        : state_(IDLE), stage_(FIRST_PWM), stage_started_ms_(0) {}

    bool begin(uint32_t now_ms) {
        if (state_ == RUNNING) {
            return false;
        }
        state_ = RUNNING;
        stage_ = FIRST_PWM;
        stage_started_ms_ = now_ms;
        return true;
    }

    // Advances at most one stage per call. A delayed loop therefore never
    // skips a PWM value or shortens the next stage; its actual duration may
    // exceed 10 seconds and must be recorded by the caller.
    bool update(uint32_t now_ms) {
        if (state_ != RUNNING) {
            return false;
        }
        const uint32_t elapsed = now_ms - stage_started_ms_;
        if (elapsed < STAGE_DURATION_MS) {
            return false;
        }
        if (stage_ == LAST_PWM) {
            state_ = COMPLETE;
            return true;
        }
        ++stage_;
        stage_started_ms_ = now_ms;
        return true;
    }

    // STOP is terminal for this run. Caller must independently command
    // hardware PWM=0 immediately; this class does not control any GPIO.
    bool stop() {
        if (state_ != RUNNING) {
            return false;
        }
        state_ = ABORTED;
        return true;
    }

    Snapshot snapshot(uint32_t now_ms) const {
        Snapshot result;
        result.state = state_;
        result.stage_index = stage_;
        result.pwm = (state_ == RUNNING) ? stage_ : 0;
        result.stage_elapsed_ms =
            (state_ == RUNNING) ? (now_ms - stage_started_ms_) : 0;
        return result;
    }

    State state() const { return state_; }

private:
    State state_;
    uint8_t stage_;
    uint32_t stage_started_ms_;
};

} // namespace PwmDetectSequence

#endif
