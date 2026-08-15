/********************************************************************
 * Motor Voltage Diagnostic
 *
 * Purpose
 * --------------------------------------------------
 * Isolated A4/A5 voltage-path verification against a multimeter.
 * This sketch does NOT modify MOTOR_BREAKIN_V3 behavior or CSV schema.
 *
 * Hardware
 * --------------------------------------------------
 * Arduino UNO
 * L298N
 * A4 = VM1
 * A5 = VM2
 * Motor voltage divider = 47k / 10k
 *
 * Serial
 * --------------------------------------------------
 * 57600 baud
 *
 * Commands
 * --------------------------------------------------
 * RUN       start motor at current PWM
 * STOP      stop motor
 * PWM=0..255 set PWM
 * SENSOR    immediately print one measurement
 *
 ********************************************************************/

#include <Arduino.h>

constexpr uint8_t PIN_PWM = 5;
constexpr uint8_t PIN_IN3 = 7;
constexpr uint8_t PIN_IN4 = 8;
constexpr uint8_t PIN_VM1 = A4;
constexpr uint8_t PIN_VM2 = A5;

constexpr float ADC_REFERENCE_VOLTAGE = 5.0f;
constexpr float ADC_MAX_COUNT = 1023.0f;
constexpr float DIVIDER_GAIN = (47000.0f + 10000.0f) / 10000.0f;
constexpr uint32_t LOG_INTERVAL_MS = 100;

uint8_t pwmValue = 64;
bool running = false;
uint32_t lastLog = 0;
String commandBuffer;

static float adcToMotorVoltage(uint16_t raw)
{
    return (static_cast<float>(raw) * ADC_REFERENCE_VOLTAGE / ADC_MAX_COUNT) * DIVIDER_GAIN;
}

static void printSensor()
{
    // Read both channels consecutively so the diagnostic pair is time-local.
    const uint16_t raw1 = analogRead(PIN_VM1);
    const uint16_t raw2 = analogRead(PIN_VM2);

    const float v1 = adcToMotorVoltage(raw1);
    const float v2 = adcToMotorVoltage(raw2);
    const float motorV = v1 - v2;

    Serial.print(F("SENSOR,VM1_RAW="));
    Serial.print(raw1);
    Serial.print(F(",VM2_RAW="));
    Serial.print(raw2);
    Serial.print(F(",VM1_V="));
    Serial.print(v1, 3);
    Serial.print(F(",VM2_V="));
    Serial.print(v2, 3);
    Serial.print(F(",MOTOR_V="));
    Serial.print(motorV, 3);
    Serial.print(F(",PWM="));
    Serial.println(pwmValue);
}

static void startMotor()
{
    digitalWrite(PIN_IN3, HIGH);
    digitalWrite(PIN_IN4, LOW);
    analogWrite(PIN_PWM, pwmValue);
    running = true;
    Serial.println(F("RUN,FWD"));
}

static void stopMotor()
{
    analogWrite(PIN_PWM, 0);
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, LOW);
    running = false;
    Serial.println(F("STOP"));
}

static void processCommand(String cmd)
{
    cmd.trim();
    cmd.toUpperCase();

    if (cmd == F("RUN"))
    {
        startMotor();
        return;
    }

    if (cmd == F("STOP"))
    {
        stopMotor();
        return;
    }

    if (cmd == F("SENSOR"))
    {
        printSensor();
        return;
    }

    if (cmd.startsWith(F("PWM=")))
    {
        const int value = cmd.substring(4).toInt();
        pwmValue = static_cast<uint8_t>(constrain(value, 0, 255));
        if (running)
        {
            analogWrite(PIN_PWM, pwmValue);
        }
        Serial.print(F("PWM="));
        Serial.println(pwmValue);
        return;
    }

    Serial.println(F("ERROR,UNKNOWN_COMMAND"));
}

void setup()
{
    pinMode(PIN_PWM, OUTPUT);
    pinMode(PIN_IN3, OUTPUT);
    pinMode(PIN_IN4, OUTPUT);
    pinMode(PIN_VM1, INPUT);
    pinMode(PIN_VM2, INPUT);

    analogWrite(PIN_PWM, 0);
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, LOW);

    Serial.begin(57600UL);
    Serial.println(F("MOTOR_VOLTAGE_DIAGNOSTIC_V1"));
    Serial.println(F("A4=VM1,A5=VM2,DIVIDER=47K/10K"));
    Serial.println(F("Commands: RUN STOP PWM=0..255 SENSOR"));
}

void loop()
{
    while (Serial.available() > 0)
    {
        const char c = static_cast<char>(Serial.read());
        if (c == '\n' || c == '\r')
        {
            if (commandBuffer.length() > 0)
            {
                processCommand(commandBuffer);
                commandBuffer = "";
            }
        }
        else if (commandBuffer.length() < 40)
        {
            commandBuffer += c;
        }
    }

    const uint32_t now = millis();
    if (now - lastLog >= LOG_INTERVAL_MS)
    {
        lastLog = now;
        printSensor();
    }
}
