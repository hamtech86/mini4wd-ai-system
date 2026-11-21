/*
 * PWM micro-current diagnostic firmware, standalone candidate.
 * Uno pin mapping matches MotoreRev.ino (PWM5, IN3=7, IN4=8).
 * Output is OFF on boot; ARM token + START required.
 * A serial command/heartbeat gap over 2 seconds aborts to output OFF.
 * Raw ADC and timestamps only; no calibrated winding-current result yet.
 */
#include <Arduino.h>
#include <string.h>
#include "PwmDetectSequence.h"
#include "MicrocurrentCapture.h"

static const char FW_VERSION[] = "3.04-MICROCURRENT-DEV";
static const char FW_BUILD_ID[] = "PWM0-30-10S-AUX2-20261031";
static const uint8_t PIN_PWM = 5;
static const uint8_t PIN_IN3 = 7;
static const uint8_t PIN_IN4 = 8;
static const uint8_t CHANNELS[4] = {A0, A1, A4, A5};
static const uint32_t SERIAL_BAUD = 115200UL;
static const uint32_t LINK_TIMEOUT_MS = 2000UL;
static const uint32_t CAPTURE_INTERVAL_MS = 50UL;

PwmDetectSequence::Sequence sequence;
MicrocurrentCapture::Frame frame;
char rx[48];
uint8_t rxIndex = 0;
bool armed = false;
bool running = false;
bool directionForward = true;
char token[9] = {0};
uint32_t lastCommandMs = 0;
uint32_t sessionId = 0;
uint32_t sequenceNo = 0;
uint32_t lastCaptureMs = 0;

static void outputOff() {
  analogWrite(PIN_PWM, 0);
  digitalWrite(PIN_IN3, LOW);
  digitalWrite(PIN_IN4, LOW);
}

static void driveStage(uint8_t pwm) {
  if (pwm == 0) {
    outputOff();
    return;
  }
  digitalWrite(PIN_IN3, directionForward ? HIGH : LOW);
  digitalWrite(PIN_IN4, directionForward ? LOW : HIGH);
  analogWrite(PIN_PWM, pwm);
}

static bool tokenMatches(const char *value) {
  return token[0] != '\0' && strcmp(token, value) == 0;
}

static void emitAux(uint8_t pwm, uint8_t channel, uint16_t raw,
                    uint32_t timestampUs) {
  Serial.print(F("AUX,2,"));
  Serial.print(sessionId);
  Serial.print(',');
  Serial.print(sequenceNo++);
  Serial.print(F(",PWM_DETECT,"));
  Serial.print(directionForward ? F("FWD") : F("REV"));
  Serial.print(',');
  Serial.print(pwm);
  Serial.print(F(",RUNNING,"));
  Serial.print(channel);
  Serial.print(',');
  Serial.print(raw);
  Serial.print(',');
  Serial.println(timestampUs);
}

static void captureAndLog(uint8_t pwm) {
  if (!MicrocurrentCapture::capture(frame, CHANNELS)) return;
  for (uint8_t i = 0; i < frame.count; ++i) {
    const MicrocurrentCapture::Reading &reading = frame.reading[i];
    emitAux(pwm, reading.channel, reading.raw, reading.timestampUs);
  }
}

static void stopRun(const __FlashStringHelper *reason) {
  outputOff();
  running = false;
  armed = false;
  sequence.stop();
  Serial.print(F("STOPPED,"));
  Serial.println(reason);
}

static void handleLine(char *line) {
  lastCommandMs = millis();
  if (strcmp(line, "PING") == 0) {
    Serial.println(F("PONG"));
    return;
  }
  if (strcmp(line, "INFO") == 0) {
    Serial.print(F("INFO,"));
    Serial.print(FW_VERSION);
    Serial.print(',');
    Serial.println(FW_BUILD_ID);
    return;
  }
  if (strncmp(line, "ARM,", 4) == 0) {
    outputOff();
    strncpy(token, line + 4, sizeof(token) - 1);
    token[sizeof(token) - 1] = '\0';
    armed = token[0] != '\0';
    Serial.println(armed ? F("ARMED") : F("ERROR,EMPTY_TOKEN"));
    return;
  }
  if (strncmp(line, "DIR,", 4) == 0 && !running) {
    directionForward = strcmp(line + 4, "REV") != 0;
    Serial.println(directionForward ? F("DIR,FWD") : F("DIR,REV"));
    return;
  }
  if (strncmp(line, "START,", 6) == 0) {
    if (!armed || !tokenMatches(line + 6) || running) {
      outputOff();
      Serial.println(F("ERROR,NOT_ARMED_OR_TOKEN"));
      return;
    }
    if (!sequence.begin(millis())) {
      Serial.println(F("ERROR,SEQUENCE_STATE"));
      return;
    }
    running = true;
    sessionId = millis();
    sequenceNo = 0;
    lastCaptureMs = 0;
    Serial.print(F("STARTED,"));
    Serial.println(sessionId);
    return;
  }
  if (strcmp(line, "STOP") == 0) {
    stopRun(F("USER"));
    return;
  }
  Serial.println(F("ERROR,UNKNOWN_COMMAND"));
}

static void pollSerial() {
  while (Serial.available() > 0) {
    const char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      rx[rxIndex] = '\0';
      if (rxIndex > 0) handleLine(rx);
      rxIndex = 0;
    } else if (rxIndex < sizeof(rx) - 1) {
      rx[rxIndex++] = c;
    } else {
      rxIndex = 0;
      outputOff();
      armed = false;
      running = false;
      sequence.stop();
      Serial.println(F("ERROR,RX_OVERFLOW"));
    }
  }
}

void setup() {
  pinMode(PIN_PWM, OUTPUT);
  pinMode(PIN_IN3, OUTPUT);
  pinMode(PIN_IN4, OUTPUT);
  outputOff();
  Serial.begin(SERIAL_BAUD);
  lastCommandMs = millis();
  Serial.println(F("BOOT,OUTPUT_OFF"));
}

void loop() {
  pollSerial();
  if (running && (uint32_t)(millis() - lastCommandMs) > LINK_TIMEOUT_MS) {
    stopRun(F("SERIAL_TIMEOUT"));
    return;
  }
  if (!running) return;

  const uint32_t now = millis();
  if (sequence.update(now)) {
    outputOff();
    running = false;
    armed = false;
    Serial.println(F("COMPLETE"));
    return;
  }

  const PwmDetectSequence::Snapshot snapshot = sequence.snapshot(now);
  driveStage(snapshot.pwm);
  if (lastCaptureMs == 0 ||
      (uint32_t)(now - lastCaptureMs) >= CAPTURE_INTERVAL_MS) {
    captureAndLog(snapshot.pwm);
    lastCaptureMs = now;
  }
}
