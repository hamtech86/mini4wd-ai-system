/********************************************************************
 * MOTOR_BREAKIN_V3.00
 * Mini4WD Motor Break-In Device
 *
 * FILE : Part1-A
 *
 * Hardware
 * --------------------------------------------------
 * Arduino UNO
 * L298N
 * ACS712 x2
 *
 * Design Policy
 * --------------------------------------------------
 * ・Long-term maintainable architecture
 * ・SECTION based management
 * ・FUNC based management
 * ・CSV communication
 * ・Python UI compatible
 *
 ********************************************************************/

/********************************************************************
 * SECTION 01 : Revision History
 ********************************************************************
 * Rev 3.00
 * --------------------------------------------------
 * Initial Architecture
 * Common Communication Specification
 * Common CSV Logger
 * Stable Runtime Framework
 *
 * Reserved Functions
 * --------------------------------------------------
 * Brush Index
 * Peak Detection
 * Estimated RPM
 * Estimated Torque
 * Automatic Break-In
 *
 ********************************************************************/

/********************************************************************
 * SECTION 02 : Include Files
 ********************************************************************/

#include <Arduino.h>
#include <string.h>

/********************************************************************
 * SECTION 03 : System Configuration
 ********************************************************************/

constexpr char FW_VERSION[]   = "3.00";
constexpr char DEVICE_TYPE[]  = "MOTOR";
constexpr char DEVICE_MODEL[] = "MOTOR_BREAKIN_V3";

constexpr uint32_t SERIAL_BAUD = 57600UL;

constexpr float TARGET_VOLTAGE_DEFAULT = 1.50f;
constexpr uint16_t VOLTAGE_CONTROL_INTERVAL_MS = 100;
/*
PIDではなく簡易制御
誤差
 ↓
PWM補正
*/
constexpr float VOLTAGE_GAIN = 5.0f;


#define RIPPLE_WINDOW 10


float currentBuffer[RIPPLE_WINDOW];
float voltageBuffer[RIPPLE_WINDOW];

int rippleIndex = 0;
int rippleCount = 0;
bool rippleFilled = false;


/********************************************************************
 * SECTION 04 : Timing Configuration
 ********************************************************************/

constexpr uint16_t SENSOR_INTERVAL_MS = 20;
constexpr uint16_t LOG_INTERVAL_MS    = 100;

//Reserved
//STATUS command only
constexpr uint16_t STATUS_INTERVAL_MS = 500;

/********************************************************************
 * SECTION 05 : Pin Assignment
 ********************************************************************/

constexpr uint8_t PIN_PWM = 5;

constexpr uint8_t PIN_IN3 = 7;
constexpr uint8_t PIN_IN4 = 8;

constexpr uint8_t PIN_ACS1 = A0;
constexpr uint8_t PIN_ACS2 = A1;

constexpr uint8_t PIN_VM1 = A4;
constexpr uint8_t PIN_VM2 = A5;

/********************************************************************
 * SECTION 06 : ADC Configuration
 ********************************************************************/

constexpr float ADC_REFERENCE_VOLTAGE = 5.0f;
constexpr float ADC_MAX_COUNT = 1023.0f;

/* Voltage Divider

Motor ----47k----+----10k----GND
                 |
                ADC

Gain = (47k+10k)/10k = 5.7

*/

constexpr float DIVIDER_R1 = 47000.0f;
constexpr float DIVIDER_R2 = 10000.0f;

constexpr float DIVIDER_GAIN =
    (DIVIDER_R1 + DIVIDER_R2) / DIVIDER_R2;

/* ACS712 Calibration */

float ACS1_ZERO = 512.0f;
float ACS2_ZERO = 512.0f;

/* 5A版 ACS712 */
constexpr float ACS_SENSITIVITY = 0.185f; //5A版0.185V/A,30A版0.066V/A



/********************************************************************
 * SECTION 07 : Communication Configuration
 ********************************************************************/

constexpr uint8_t RX_BUFFER_SIZE = 64;

constexpr uint8_t INSTANCE_ID_SIZE = 12;

constexpr bool DEBUG_SERIAL = false;
constexpr bool DEBUG_SENSOR = false;
constexpr bool DEBUG_LOG = false;
constexpr bool DEBUG_PWM = false;
/********************************************************************
 * SECTION 08 : Device State
 ********************************************************************/

enum DeviceState
{
    STATE_INIT = 0,

    STATE_READY,

    STATE_RUN,

    STATE_PAUSE,

    STATE_STOP,

    STATE_COMPLETE,

    STATE_ERROR
};

/********************************************************************
 * SECTION 09 : Motor Direction
 ********************************************************************/

enum MotorDirection
{
    DIR_FORWARD = 0,

    DIR_REVERSE
};

/********************************************************************
 * SECTION 10 : Runtime Structure
 ********************************************************************/

struct RuntimeData
{
    DeviceState state;

    MotorDirection direction;

    bool running;

    bool paused;

    uint8_t pwm;

    uint32_t startTime;

    uint32_t elapsedTime;
};

/********************************************************************
 * SECTION 11 : Sensor Structure
 ********************************************************************/

struct SensorData
{
    uint16_t rawACS1;
    uint16_t rawACS2;

    uint16_t rawVM1;
    uint16_t rawVM2;

    float current1;
    float current2;

    float voltage1;
    float voltage2;

    float motorVoltage;

    /*
     * Evaluation Data
     */

    float currentAvg;
    float voltageAverage;
    float power;
    float peakPower;
    float peakCurrent;
    float peakVoltage;
    unsigned long peakTime;
    int peakPWM;

    float finalPower;
    float finalCurrent;
    float finalVoltage;
    float finalRipple;


    /*
     * Brush Evaluation
     */

    float currentMin;
    float currentMax;

    float voltageMin;
    float voltageMax;

    float currentRipple;
    float voltageRipple;

    /*
     * Brush Peak Evaluation
    */

    float brushPeakCurrent;
    unsigned long brushPeakTime;
    float brushPeakRipple;
    bool brushPeakDetected;

    uint16_t rawMagnetic;
    float magneticLevel;
    bool magneticSensorValid;

    uint16_t rawThermistor;
    float motorTemperature;
    bool thermistorValid;

};

    






/********************************************************************
 * SECTION 12 : Timer Structure
 ********************************************************************/

struct TimerData
{
    uint32_t sensorTimer;

    uint32_t logTimer;

    uint32_t statusTimer;
};

/********************************************************************
 * SECTION 12-B : Voltage Control Structure
 ********************************************************************/

struct VoltageControlData
{
    bool enabled;

    float targetVoltage;

    uint32_t controlTimer;
};


VoltageControlData voltageControl;




/********************************************************************
 * SECTION 13 : Communication Structure
 ********************************************************************/

struct CommunicationData
{
    char rxBuffer[RX_BUFFER_SIZE];

    uint8_t rxIndex;

    char instanceID[INSTANCE_ID_SIZE];
};

/********************************************************************
 * SECTION 14 : Global Variables
 ********************************************************************/

RuntimeData runtime;

SensorData sensor;

float peakPower = 0.0;
unsigned long peakTime = 0;


TimerData timerData;

CommunicationData comm;

/********************************************************************
 * SECTION 15 : Function Prototype
 ********************************************************************/

/* Initialization */

// FUNC-101
void initializeSystem();

// FUNC-102
void initializePins();

// FUNC-103
void initializeVariables();

// FUNC_104
void calibrateACS712();

// FUNC-151
void setState(DeviceState newState);



/* Communication */

// FUNC-201
void processSerial();

// FUNC-202
void processCommand(const char *cmd);

// FUNC-203
void sendInfo();

// FUNC-204
void sendStatus();

// FUNC-205
void sendOK();

// FUNC-206
void sendError(const char *message);

/* Sensor */

// FUNC-300
void updateSensors();

// FUNC-301
uint16_t readACS1();

// FUNC-302
uint16_t readACS2();

// FUNC-303
float readMotorVoltage();




/* Logger */

// FUNC-401
void sendLog();

/* Utility */

// FUNC-501
void startForward();

// FUNC-502
void startReverse();

// FUNC-503
void stopMotor();

// FUNC-551
void setPWM(uint8_t pwm);

 /********************************************************************
 * SECTION 16 : setup()
 ********************************************************************/

void setup()
{
    Serial.begin(SERIAL_BAUD);

   
    initializeSystem();

    Serial.println();
    Serial.println(F("========================================"));
    Serial.println(F(" Mini4WD MOTOR BREAK-IN DEVICE"));
    Serial.println(F(" MOTOR_BREAKIN_V3"));
    Serial.print(F(" Firmware : "));
    Serial.println(FW_VERSION);
    Serial.println(F("========================================"));

    sendInfo();
}

/********************************************************************
 * SECTION 17 : loop()
 ********************************************************************/

void loop()
{
    uint32_t now = millis();

    /* ---------- Communication ---------- */

    processSerial();

    /* ---------- Sensor Update ---------- */

    if ((now - timerData.sensorTimer) >= SENSOR_INTERVAL_MS)
    {
        timerData.sensorTimer = now;

        updateSensors();
    }

    /* ---------- CSV Logger ---------- */

    if ((now - timerData.logTimer) >= LOG_INTERVAL_MS)
{
    timerData.logTimer = now;

    if (runtime.state != STATE_STOP)
    {
        sendLog();
    }
}


    /* ---------- Status ---------- */
    /*
    if ((now - timerData.statusTimer) >= STATUS_INTERVAL_MS)
    {
        timerData.statusTimer = now;

        sendStatus();
    }
    */
    /* ---------- Runtime ---------- */

    if (runtime.running)
    {
        runtime.elapsedTime = now - runtime.startTime;
    }
    if(
    (now - voltageControl.controlTimer)
    >= VOLTAGE_CONTROL_INTERVAL_MS
    )
    {
        voltageControl.controlTimer = now;
            
        voltageControlUpdate();
    }

}

/********************************************************************
* FUNC-151 : setState()
********************************************************************/

void setState(DeviceState newState)
{

    runtime.state = newState;


    /*
     * State Change Action
     */


    switch(newState)
    {


        case STATE_INIT:

            Serial.print(F("INIT"));

            break;




        case STATE_READY:

            Serial.print(F("READY"));

            break;




        case STATE_RUN:


            Serial.print(F("RUN"));


            /*
             * Reset Peak Data
             */

            sensor.peakPower   = 0.0f;
            sensor.peakCurrent = 0.0f;
            sensor.peakVoltage = 0.0f;
            sensor.peakTime    = 0;
            sensor.peakPWM     = 0;


            break;





        case STATE_PAUSE:

            Serial.print(F("PAUSE"));

            break;




        case STATE_STOP:


            Serial.print(F("STOP"));


            /*
             * Final Evaluation Save
             */


            sensor.finalPower =
                sensor.peakPower;


            sensor.finalCurrent =
                sensor.peakCurrent;


            sensor.finalVoltage =
                sensor.peakVoltage;


            sensor.finalRipple =
                sensor.currentRipple;


            break;






        case STATE_COMPLETE:


            Serial.print(F("COMPLETE"));

            break;




        case STATE_ERROR:


            Serial.print(F("ERROR"));

            break;




        default:

            Serial.print(F("UNKNOWN"));

            break;


    }



    Serial.print(F(","));



    if(runtime.direction == DIR_FORWARD)
    {
        Serial.println(F("FWD"));
    }
    else
    {
        Serial.println(F("REV"));
    }


}


/********************************************************************
 * FUNC-101 : initializeSystem()
 ********************************************************************/

void initializeSystem()
{
    initializeVariables();    

    initializePins();

    calibrateACS712();

    stopMotor();

    setState(STATE_READY);
}

/********************************************************************
 * FUNC-102 : initializePins()
 ********************************************************************/

void initializePins()
{
    pinMode(PIN_PWM, OUTPUT);

    pinMode(PIN_IN3, OUTPUT);

    pinMode(PIN_IN4, OUTPUT);

    pinMode(PIN_ACS1, INPUT);

    pinMode(PIN_ACS2, INPUT);

    pinMode(PIN_VM1, INPUT);

    pinMode(PIN_VM2, INPUT);

    analogWrite(PIN_PWM, 0);

    digitalWrite(PIN_IN3, LOW);

    digitalWrite(PIN_IN4, LOW);
}

/********************************************************************
 * FUNC-103 : initializeVariables()
 ********************************************************************/

void initializeVariables()
{
    runtime.state = STATE_INIT;

    runtime.direction = DIR_FORWARD;

    runtime.running = false;

    runtime.paused = false;

    runtime.pwm = 0;

    runtime.startTime = 0;

    runtime.elapsedTime = 0;
    voltageControl.enabled = false;

    voltageControl.targetVoltage = TARGET_VOLTAGE_DEFAULT;

    voltageControl.controlTimer = 0;


    memset(&sensor, 0, sizeof(sensor));

    memset(&timerData, 0, sizeof(timerData));

    memset(&comm, 0, sizeof(comm));
    
    sensor.currentMin = 999.0f;
    sensor.currentMax = 0.0f;

    sensor.voltageMin = 999.0f;
    sensor.voltageMax = 0.0f;

    sensor.currentRipple = 0.0f;
    sensor.voltageRipple = 0.0f;

    sensor.peakPower = 0.0f;
    sensor.peakCurrent = 0.0f;
    sensor.peakVoltage = 0.0f;

    sensor.brushPeakCurrent = 0.0f;
    sensor.brushPeakTime = 0;
    sensor.brushPeakRipple = 0.0f;
    sensor.brushPeakDetected = false;




    sensor.peakTime = 0;
    sensor.peakPWM = 0;


    strncpy(comm.instanceID,
            "000001",
            INSTANCE_ID_SIZE - 1);

            /* ---------- ACS712 Auto Zero ---------- */

    delay(300);

        long sum1 = 0;
        long sum2 = 0;

        for (int i = 0; i < 200; i++)
        {
            sum1 += analogRead(PIN_ACS1);
            sum2 += analogRead(PIN_ACS2);
            delay(2);
        }

        ACS1_ZERO = (float)sum1 / 200.0f;
        ACS2_ZERO = (float)sum2 / 200.0f;

        Serial.print(F("ACS1_ZERO="));
        Serial.println(ACS1_ZERO);

        Serial.print(F("ACS2_ZERO="));
        Serial.println(ACS2_ZERO);

   
}

/********************************************************************
calibrateACS712()
********************************************************************/

void calibrateACS712()
{
    delay(300);

    long sum1 = 0;
    long sum2 = 0;

    for (int i = 0; i < 200; i++)
    {
        sum1 += analogRead(PIN_ACS1);
        sum2 += analogRead(PIN_ACS2);
        delay(2);
    }

    ACS1_ZERO = (float)sum1 / 200.0f;
    ACS2_ZERO = (float)sum2 / 200.0f;
}




/********************************************************************
 * FUNC-104 : stopMotor()
 ********************************************************************/

void stopMotor()
{
    analogWrite(PIN_PWM, 0);

    digitalWrite(PIN_IN3, LOW);

    digitalWrite(PIN_IN4, LOW);

    runtime.running = false;

    runtime.paused = false;
}

/********************************************************************
 * Temporary Stub Functions
 * (Implemented in Part2 and later)
 ********************************************************************/

/********************************************************************
 * SECTION 18 : Serial Communication
 ********************************************************************/

/********************************************************************
 * BLOCK 18-01 : Serial Receive
 ********************************************************************/

/********************************************************************
 * FUNC-201 : processSerial()
 *
 * Receive one line command from Serial
 *
 ********************************************************************/

void processSerial()
{
    while (Serial.available())
    {
        char c = Serial.read();

        /* Ignore CR */

        if (c == '\r')
        {
            continue;
        }

        /* End of Line */

        if (c == '\n')
        {
            comm.rxBuffer[comm.rxIndex] = '\0';

            if (comm.rxIndex > 0)
            {
                processCommand(comm.rxBuffer);
            }

            comm.rxIndex = 0;

            return;
        }

        /* Store */

        if (comm.rxIndex < (RX_BUFFER_SIZE - 1))
        {
            comm.rxBuffer[comm.rxIndex++] = c;
        }
    }
}

/********************************************************************
 * BLOCK 18-02 : Command Parser
 ********************************************************************/

/********************************************************************
 * FUNC-202 : processCommand()
 *
 ********************************************************************/

void processCommand(const char *cmd)
{
    if (strcmp(cmd, "INFO") == 0)
    {
        sendInfo();
        return;
    }

    if (strcmp(cmd, "STATUS") == 0)
    {
        sendStatus();
        return;
    }

    if (strcmp(cmd, "PING") == 0)
    {
        Serial.println(F("PONG"));
        return;
    }

    if (strcmp(cmd, "START") == 0)
    {
        runtime.paused = false;

       if (runtime.direction == DIR_FORWARD)
        {
          startForward();
        }
       else
        {
          startReverse();
        }

    sendOK();

    return;
}

   if (strcmp(cmd, "STOP") == 0)
{
    stopMotor();

    setState(STATE_STOP);

    // 停止時の最終評価を1回だけ送信
    sendLog();

    sendOK();

    return;
}


    

    if (strcmp(cmd, "PAUSE") == 0)
    {
     runtime.paused = true;

     analogWrite(PIN_PWM, 0);

     setState(STATE_PAUSE);

     sendOK();

     return;
    }


    

    if (strcmp(cmd, "RESUME") == 0)
    {
        runtime.paused = false;

        setState(STATE_RUN);

        sendOK();

        return;
    }

    if (strcmp(cmd, "FWD") == 0)
    {
        startForward();

        sendOK();

        return;
    }

    if (strcmp(cmd, "REV") == 0)
    {
        startReverse();

        sendOK();

        return;
    }

    /* PWM=128 */

    if (strncmp(cmd, "PWM=", 4) == 0)
    {
        int value = atoi(cmd + 4);

        if (value < 0)
        {
            value = 0;
        }

        if (value > 255)
        {
            value = 255;
        }

        setPWM((uint8_t)value);

        sendOK();

        return;
    }

    

    if(strncmp(cmd,"TARGET=",7)==0)
    {
        voltageControl.targetVoltage =
            atof(cmd + 7);

        sendOK();

        return;
    }

    if(strcmp(cmd,"VCTRL=ON")==0)
    {
        voltageControl.enabled = true;

        sendOK();

        return;
    }

    if(strcmp(cmd,"VCTRL=OFF")==0)
    {
        voltageControl.enabled = false;

        sendOK();

        return;
    }




    sendError("UNKNOWN_COMMAND");
}

/********************************************************************
 * SECTION 19 : Response Functions
 ********************************************************************/

/********************************************************************
 * BLOCK 19-01 : Device Information
 ********************************************************************/

/********************************************************************
 * FUNC-203 : sendInfo()
 ********************************************************************/

void sendInfo()
{
    Serial.print(F("INFO,TYPE="));
    Serial.print(DEVICE_TYPE);

    Serial.print(F(",MODEL="));
    Serial.print(DEVICE_MODEL);

    Serial.print(F(",FW="));
    Serial.print(FW_VERSION);

    Serial.print(F(",ID="));
    Serial.println(comm.instanceID);
}

/********************************************************************
 * BLOCK 19-02 : Device Status
 ********************************************************************/

/********************************************************************
 * FUNC-204 : sendStatus()
 ********************************************************************/

void sendStatus()
{
    Serial.print(F("STATUS,"));

    switch (runtime.state)
    {
        case STATE_INIT:
            Serial.print(F("INIT"));
            break;

        case STATE_READY:
            Serial.print(F("READY"));
            break;

        case STATE_RUN:
            Serial.print(F("RUN"));
            break;

        case STATE_PAUSE:
            Serial.print(F("PAUSE"));
            break;

        case STATE_STOP:
            Serial.print(F("STOP"));
            break;

        case STATE_COMPLETE:
            Serial.print(F("COMPLETE"));
            break;

        case STATE_ERROR:
            Serial.print(F("ERROR"));
            break;

        default:
            Serial.print(F("UNKNOWN"));
            break;
    }


    Serial.print(F(",DIR="));

     if (runtime.direction == DIR_FORWARD)
     {
      Serial.print(F("FWD"));
     }
     else
     {
      Serial.print(F("REV"));
     }

    Serial.print(F(",PWM="));

Serial.print(runtime.pwm);


/* Target Voltage */

    Serial.print(F(",TARGET="));

    Serial.print(
        voltageControl.targetVoltage,
        2
    );


/* Voltage Control */

    Serial.print(F(",VCTRL="));

    if(voltageControl.enabled)
    {
        Serial.print(F("ON"));
    }
    else
    {
        Serial.print(F("OFF"));
    }


    /* Current Motor Voltage */

    Serial.print(F(",V="));

    Serial.print(
        sensor.motorVoltage,
        2
    );


    /* Time */

    Serial.print(F(",TIME="));

    Serial.println(
        runtime.elapsedTime
    );

}

/********************************************************************
 * BLOCK 19-03 : Common Response
 ********************************************************************/

/********************************************************************
 * FUNC-205 : sendOK()
 ********************************************************************/

void sendOK()
{
    Serial.println(F("OK"));
}

/********************************************************************
 * FUNC-206 : sendError()
 ********************************************************************/

void sendError(const char *message)
{
    Serial.print(F("ERROR,"));
    Serial.println(message);
}

/********************************************************************
 * SECTION 20 : Sensor Functions
 ********************************************************************/

/********************************************************************
 * FUNC-301 : readACS1()
 ********************************************************************/

uint16_t readACS1()
{
    return analogRead(PIN_ACS1);
}

/********************************************************************
 * FUNC-302 : readACS2()
 ********************************************************************/

uint16_t readACS2()
{
    return analogRead(PIN_ACS2);
}






/********************************************************************
 * FUNC-303 : readMotorVoltage()
 *
 * Returns:
 *     Vmotor = V1 - V2
 ********************************************************************/

float readMotorVoltage()
{
    float adc1 = analogRead(PIN_VM1);
    float adc2 = analogRead(PIN_VM2);

    sensor.rawVM1 = (uint16_t)adc1;
    sensor.rawVM2 = (uint16_t)adc2;

    sensor.voltage1 =
        (adc1 * ADC_REFERENCE_VOLTAGE / ADC_MAX_COUNT)
        * DIVIDER_GAIN;

    sensor.voltage2 =
        (adc2 * ADC_REFERENCE_VOLTAGE / ADC_MAX_COUNT)
        * DIVIDER_GAIN;

    sensor.motorVoltage =
        sensor.voltage1 - sensor.voltage2;

    return sensor.motorVoltage;
   

}

/********************************************************************
* FUNC-300 : updateSensors()
********************************************************************/

void updateSensors()
{


 /*
  * ADC Read
  */
 sensor.rawMagnetic = analogRead(A2);
 sensor.magneticLevel =
 (sensor.rawMagnetic * 5.0f) / 1023.0f;
 
 sensor.magneticSensorValid =
 (sensor.rawMagnetic > 5 &&
  sensor.rawMagnetic < 1018);


 sensor.rawThermistor =
 analogRead(A3);

 sensor.thermistorValid =
 (sensor.rawThermistor > 5 &&
  sensor.rawThermistor < 1018);

 if(sensor.thermistorValid)
 {
     float resistance =
     10000.0f *
     ((1023.0f /
     sensor.rawThermistor) - 1.0f);

     float steinhart;

     steinhart =
     resistance / 10000.0f;

     steinhart =
     log(steinhart);

     steinhart /= 3950.0f;

     steinhart +=
     1.0f /
     (25.0f + 273.15f);

     steinhart =
     1.0f / steinhart;

     sensor.motorTemperature =
     steinhart - 273.15f;
 }



 sensor.rawACS1 = readACS1();

 sensor.rawACS2 = readACS2();

//======================================================
// AUTO ZERO
// READY状態のみオフセット更新
//======================================================
    if(runtime.state == STATE_READY &&
     runtime.pwm == 0)
    {
        ACS1_ZERO =
            ACS1_ZERO * 0.999f +
            sensor.rawACS1 * 0.001f;

        ACS2_ZERO =
            ACS2_ZERO * 0.999f +
            sensor.rawACS2 * 0.001f;
    }


 readMotorVoltage();



 /*
  * Current conversion
  * ACS712 5A
  */


 float sensorVoltage1 =
 -(sensor.rawACS1 - ACS1_ZERO)
 * ADC_REFERENCE_VOLTAGE
 / ADC_MAX_COUNT;


 sensor.current1 =
 sensorVoltage1
 / ACS_SENSITIVITY;




 float sensorVoltage2 =
 -(sensor.rawACS2 - ACS2_ZERO)
 * ADC_REFERENCE_VOLTAGE
 / ADC_MAX_COUNT;


 sensor.current2 =
 sensorVoltage2
 / ACS_SENSITIVITY;

//======================================================
// DEAD BAND
//======================================================
    if(fabs(sensor.current1) < 0.05f)
    {
     sensor.current1 = 0.0f;
    }

    if(fabs(sensor.current2) < 0.05f)
    {
    sensor.current2 = 0.0f;
}


 /*
  * Average
  */


 sensor.currentAvg =
 (
    sensor.current1
    +
    sensor.current2
 )
 /
 2.0f;

/*
 * Brush Peak Detection
 */

   if(runtime.elapsedTime > 300)
{
    if(sensor.currentAvg > sensor.brushPeakCurrent)
    {
        sensor.brushPeakCurrent = sensor.currentAvg;
        sensor.brushPeakTime = runtime.elapsedTime;
    }
}





 sensor.voltageAverage =
 (
    sensor.voltage1
    +
    sensor.voltage2
 )
 /
 2.0f;



 /*
  * Power
  */


 sensor.power =
    sensor.motorVoltage
    *
    sensor.currentAvg;



 /*
  * Moving Window Ripple
  */


 currentBuffer[rippleIndex] =
     sensor.currentAvg;


 voltageBuffer[rippleIndex] =
     sensor.motorVoltage;



 rippleIndex++;



 if(rippleIndex >= RIPPLE_WINDOW)
 {
    rippleIndex = 0;
    rippleFilled = true;
 }



 int count;


 if(rippleFilled)
 {
    count = RIPPLE_WINDOW;
 }
 else
 {
    count = rippleIndex;
 }



 if(count > 0)
 {

    float cMin = currentBuffer[0];
    float cMax = currentBuffer[0];

    float vMin = voltageBuffer[0];
    float vMax = voltageBuffer[0];



    for(int i=1;i<count;i++)
    {

       if(currentBuffer[i] < cMin)
          cMin = currentBuffer[i];


       if(currentBuffer[i] > cMax)
          cMax = currentBuffer[i];


       if(voltageBuffer[i] < vMin)
          vMin = voltageBuffer[i];


       if(voltageBuffer[i] > vMax)
          vMax = voltageBuffer[i];

    }



    sensor.currentRipple =
        cMax - cMin;


    sensor.voltageRipple =
        vMax - vMin;

 }


 /*
  * Peak Power Detection
  *
  * Start after motor stabilization
  */


 if(runtime.elapsedTime > 3000 &&
    sensor.currentAvg > 0.05f &&
    sensor.power > sensor.peakPower)
 {


    sensor.peakPower =
       sensor.power;


    sensor.peakCurrent =
       sensor.currentAvg;


    sensor.peakVoltage =
       sensor.motorVoltage;


    sensor.peakTime =
       runtime.elapsedTime;


    sensor.peakPWM =
       runtime.pwm;

 }


}


/********************************************************************
 * SECTION 21 : CSV Logger
 ********************************************************************/
/********************************************************************
* FUNC-401 : sendLog()
********************************************************************/

void sendLog()
{

  Serial.print(F("DATA,"));
  Serial.print(DEVICE_MODEL);
  Serial.print(',');



  Serial.print(comm.instanceID);
  Serial.print(',');



  Serial.print(runtime.elapsedTime);
  Serial.print(',');



  Serial.print(sensor.rawACS1);
  Serial.print(',');



  Serial.print(sensor.rawACS2);
  Serial.print(',');



  Serial.print(sensor.current1, 3);
  Serial.print(',');



  Serial.print(sensor.current2, 3);
  Serial.print(',');



  Serial.print(sensor.voltage1, 3);
  Serial.print(',');



  Serial.print(sensor.voltage2, 3);
  Serial.print(',');



  Serial.print(sensor.motorVoltage, 3);
  Serial.print(',');



  Serial.print(runtime.pwm);
  Serial.print(',');



  if(runtime.direction == DIR_FORWARD)
  {
      Serial.print(F("FWD"));
  }
  else
  {
      Serial.print(F("REV"));
  }



  Serial.print(',');



  switch(runtime.state)
  {


      case STATE_INIT:
          Serial.print(F("INIT"));
          break;


      case STATE_READY:
          Serial.print(F("READY"));
          break;


      case STATE_RUN:
          Serial.print(F("RUN"));
          break;


      case STATE_PAUSE:
          Serial.print(F("PAUSE"));
          break;


      case STATE_STOP:
          Serial.print(F("STOP"));
          break;


      case STATE_COMPLETE:
          Serial.print(F("COMPLETE"));
          break;


      case STATE_ERROR:
          Serial.print(F("ERROR"));
          break;


      default:
          Serial.print(F("UNKNOWN"));
          break;

  }



  Serial.print(',');



  /*
   * Evaluation Data
   */


  // CURRENT_AVG(A)
  Serial.print(sensor.currentAvg, 3);
  Serial.print(',');



  // POWER(W)
  Serial.print(sensor.power, 3);
  Serial.print(',');



  // CURRENT_RIPPLE(A)
  Serial.print(sensor.currentRipple, 3);
  Serial.print(',');



  // VOLTAGE_RIPPLE(V)
  Serial.print(sensor.voltageRipple, 3);
  Serial.print(',');



  // PEAK POWER
  Serial.print(sensor.peakPower, 3);
  Serial.print(',');



  // PEAK CURRENT
  Serial.print(sensor.peakCurrent, 3);
  Serial.print(',');



  // PEAK VOLTAGE
  Serial.print(sensor.peakVoltage, 3);
  Serial.print(',');



  // PEAK PWM
  Serial.print(sensor.peakPWM);
  Serial.print(',');



  /*
   * Brush Evaluation
   */


  // BRUSH PEAK CURRENT(A)
  Serial.print(sensor.brushPeakCurrent, 3);

 Serial.print(',');

 Serial.print(sensor.rawMagnetic);

 Serial.print(',');

 Serial.print(sensor.magneticLevel,3);

 Serial.print(',');

 Serial.print(sensor.motorTemperature,1);


  Serial.println();





}



/********************************************************************
 * SECTION 22 : Motor Control
 ********************************************************************/

/********************************************************************
 * FUNC-501 : startForward()
 ********************************************************************/

void startForward()
{
    runtime.direction = DIR_FORWARD;

    digitalWrite(PIN_IN3, HIGH);
    digitalWrite(PIN_IN4, LOW);

    analogWrite(PIN_PWM, runtime.pwm);

    runtime.running = true;

    if (!runtime.paused)
    {
        runtime.startTime = millis();
    }

    setState(STATE_RUN);
}

/********************************************************************
 * FUNC-502 : startReverse()
 ********************************************************************/

void startReverse()
{
    runtime.direction = DIR_REVERSE;

    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, HIGH);

    analogWrite(PIN_PWM, runtime.pwm);

    runtime.running = true;

    if (!runtime.paused)
    {
        runtime.startTime = millis();
    }

    setState(STATE_RUN);
}

/********************************************************************
 * FUNC-551 : setPWM()
 ********************************************************************/

void setPWM(uint8_t pwm)
{
    runtime.pwm = pwm;

    if (runtime.running)
    {
        analogWrite(PIN_PWM, runtime.pwm);
    }
}

/********************************************************************
 * SECTION 23 : Voltage Control
 ********************************************************************/

constexpr float VOLTAGE_DEADBAND = 0.03f; //±30mV

/********************************************************************
 * FUNC-601 : voltageControlUpdate()
 ********************************************************************/

void voltageControlUpdate()
{

    if (!voltageControl.enabled)
    {
        return;
    }


    float error =
        voltageControl.targetVoltage
        -
        sensor.motorVoltage;

    /* Deadband */

    if (fabs(error) <= VOLTAGE_DEADBAND)
    {
        return;
    }

    int16_t correction =
        error * VOLTAGE_GAIN;


    int16_t limitedCorrection;
        
    if(correction > 1 )
    {
        limitedCorrection = 1;
    }
    else if(correction < -1)
    {
         limitedCorrection = -1;
    }
    else 
    {
         limitedCorrection = correction;
    }

    int16_t newPWM =
        runtime.pwm + limitedCorrection;

    if(newPWM < 0)
    {
        newPWM = 0;
    }


    if(newPWM > 255)
    {
        newPWM = 255;
    }


    runtime.pwm =
        (uint8_t)newPWM;


    analogWrite(
        PIN_PWM,
        runtime.pwm
    );
}