#pragma once
#include <math.h>
#include <stdint.h>

class HeatingPid {
public:
    void reset() { integral = 0; initialized = false; output = 0; }
    float update(float target, float temperature, uint32_t now, float kp, float ki, float kd) {
        const float error = target - temperature;
        const float seconds = initialized ? (now - previousAt) / 1000.0f : 0;
        // Derivative on measurement avoids a derivative kick on target changes.
        const float derivative = seconds > 0 ? -kd * (temperature - previousTemperature) / seconds : 0;
        const float candidate = fminf(100, fmaxf(0, integral + ki * error * seconds));
        const float unconstrained = kp * error + candidate + derivative;
        // Anti-windup: integrate only inside the range or out of saturation.
        if ((unconstrained >= 0 && unconstrained <= 100) ||
            (unconstrained > 100 && error < 0) || (unconstrained < 0 && error > 0)) integral = candidate;
        output = fminf(100, fmaxf(0, kp * error + integral + derivative));
        previousTemperature = temperature;
        previousAt = now;
        initialized = true;
        return output;
    }
    float value() const { return output; }
private:
    float integral = 0, previousTemperature = 0, output = 0;
    uint32_t previousAt = 0;
    bool initialized = false;
};
