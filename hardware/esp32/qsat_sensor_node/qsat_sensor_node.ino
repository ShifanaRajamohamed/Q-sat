/*
 * ============================================================================
 * Q-SAT Adaptive Ground Station - Hardware Sensor Node Firmware
 * Target Microcontroller: ESP32 DevKit v1 / ESP32-WROOM-32
 * ============================================================================
 * 
 * Hardware-in-the-Loop (HIL) Environment Telemetry Transmitter
 * 
 * Connected Physical Sensors:
 * 1. DHT22 (AM2302) on GPIO 4:
 *    - Ambient temperature (-40 to +80 deg C)
 *    - Relative humidity (0 to 100% RH)
 * 
 * 2. Optical LDR (Photoresistor) on GPIO 34 (ADC1_CH6):
 *    - Ambient optical background noise measurement (0 to 100,000 lux)
 *    - Calibrated via voltage divider (10k pull-down)
 * 
 * 3. MPU6050 (6-DOF IMU) via I2C (SDA: GPIO 21, SCL: GPIO 22):
 *    - Ground station telescope mount vibration & mechanical jitter
 *    - High-frequency sampling with dynamic RMS acceleration computation
 * 
 * Communication Protocol:
 * - IEEE 802.11 b/g/n WiFi client
 * - MQTT 3.1.1 JSON serialization to topic: "qsat/environment"
 * - Sampling / transmission frequency: 1.0 Hz
 * ============================================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <ArduinoJson.h>

// ----------------------------------------------------------------------------
// Network & MQTT Configuration
// ----------------------------------------------------------------------------
const char* WIFI_SSID     = "QSAT_LAB_NETWORK";
const char* WIFI_PASSWORD = "QuantumGroundStation2026";

const char* MQTT_BROKER   = "192.168.1.100";  // Ground station control server IP
const int   MQTT_PORT     = 1883;
const char* MQTT_CLIENT_ID= "ESP32_QGS_NODE_01";
const char* MQTT_TOPIC    = "qsat/environment";

// ----------------------------------------------------------------------------
// Pin Definitions
// ----------------------------------------------------------------------------
#define PIN_DHT           4    // GPIO 4 for DHT22
#define DHT_TYPE          DHT22
#define PIN_LDR           34   // ADC1 Channel 6 (Input only, low noise)
#define I2C_SDA           21   // I2C Data
#define I2C_SCL           22   // I2C Clock
#define PIN_STATUS_LED    2    // Onboard LED indicator

// ----------------------------------------------------------------------------
// Global Sensor Objects & State
// ----------------------------------------------------------------------------
DHT dht(PIN_DHT, DHT_TYPE);
Adafruit_MPU6050 mpu;
WiFiClient espClient;
PubSubClient mqttClient(espClient);

unsigned long lastTelemetryMillis = 0;
const unsigned long TELEMETRY_INTERVAL_MS = 1000; // 1 Hz publish rate
bool mpuAvailable = false;

// ----------------------------------------------------------------------------
// Sensor Reading Functions
// ----------------------------------------------------------------------------

/**
 * Read DHT22 temperature and humidity with sanity bounds check.
 */
void readDHT(float &temperature, float &humidity) {
  float t = dht.readTemperature();
  float h = dht.readHumidity();

  if (isnan(t) || isnan(h)) {
    Serial.println("[WARN] DHT22 read failed. Using nominal fallback.");
    temperature = 25.0f;
    humidity = 55.0f;
  } else {
    temperature = t;
    humidity = constrain(h, 0.0f, 100.0f);
  }
}

/**
 * Read analog LDR and convert ADC voltage to calibrated illuminance (Lux).
 * ESP32 ADC: 12-bit (0 - 4095), 3.3V reference.
 * Voltage divider: 3.3V -> LDR (GL5528) -> Node (GPIO34) -> 10k Resistor -> GND
 */
float readLDRLux() {
  int rawADC = analogRead(PIN_LDR);
  if (rawADC <= 0) return 0.1f;
  if (rawADC >= 4095) return 80000.0f;

  float vOut = (rawADC / 4095.0f) * 3.3f;
  // Calculate LDR resistance: R_ldr = R_ref * ((V_cc / V_out) - 1)
  const float R_ref = 10000.0f; // 10k fixed resistor
  float rLdr = R_ref * ((3.3f / vOut) - 1.0f);
  if (rLdr < 1.0f) rLdr = 1.0f;

  // Empirical lux conversion for standard CdS cell: Lux = 500 / (R_ldr in kOhm)^1.4
  float rKohm = rLdr / 1000.0f;
  float lux = 500.0f / pow(rKohm, 1.4f);

  return constrain(lux, 0.0f, 100000.0f);
}

/**
 * Sample MPU6050 accelerometer and compute RMS vibration metric (m/s^2).
 * High-pass filter removes static 1.0g gravity vector.
 */
float readVibrationRMS() {
  if (!mpuAvailable) {
    return 0.005f; // Nominal ambient mechanical noise
  }

  const int SAMPLES = 20;
  float sumSq = 0.0f;

  for (int i = 0; i < SAMPLES; i++) {
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);

    // Compute total acceleration magnitude
    float mag = sqrt(a.acceleration.x * a.acceleration.x +
                     a.acceleration.y * a.acceleration.y +
                     a.acceleration.z * a.acceleration.z);

    // Dynamic deviation from standard gravity (9.80665 m/s^2)
    float dynamicDev = abs(mag - 9.80665f);
    sumSq += dynamicDev * dynamicDev;
    delayMicroseconds(500); // 2 kHz sampling interval
  }

  float rms = sqrt(sumSq / SAMPLES);
  // Scale to vibration metric (0.0 to 1.0 arbitrary severity units)
  float vibrationLevel = rms / 10.0f;
  return constrain(vibrationLevel, 0.0f, 1.0f);
}

// ----------------------------------------------------------------------------
// Networking: WiFi & MQTT Connection Handlers
// ----------------------------------------------------------------------------

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("[INFO] Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[INFO] WiFi connected!");
    Serial.print("[INFO] IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WARN] WiFi connection timed out. Will retry in loop.");
  }
}

void connectMQTT() {
  if (mqttClient.connected()) return;
  if (WiFi.status() != WL_CONNECTED) return;

  Serial.print("[INFO] Connecting to MQTT Broker at ");
  Serial.print(MQTT_BROKER);
  Serial.print(":");
  Serial.println(MQTT_PORT);

  if (mqttClient.connect(MQTT_CLIENT_ID)) {
    Serial.println("[INFO] MQTT Connected successfully.");
    digitalWrite(PIN_STATUS_LED, HIGH);
  } else {
    Serial.print("[WARN] MQTT connect failed, rc=");
    Serial.print(mqttClient.state());
    Serial.println(". Will retry in next cycle.");
    digitalWrite(PIN_STATUS_LED, LOW);
  }
}

// ----------------------------------------------------------------------------
// Setup & Main Loop
// ----------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("==================================================");
  Serial.println("  Q-SAT ADAPTIVE GROUND STATION - SENSOR NODE     ");
  Serial.println("  Hardware-in-the-Loop Telemetry Firmware v1.0   ");
  Serial.println("==================================================");

  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LOW);
  analogReadResolution(12);

  // Initialize DHT22
  dht.begin();
  Serial.println("[INIT] DHT22 Temperature & Humidity Sensor initialized.");

  // Initialize I2C and MPU6050
  Wire.begin(I2C_SDA, I2C_SCL);
  if (mpu.begin(0x68, &Wire)) {
    mpuAvailable = true;
    mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    Serial.println("[INIT] MPU6050 6-DOF IMU initialized (2G, 21Hz filter).");
  } else {
    Serial.println("[WARN] MPU6050 not detected at 0x68. Vibration will use fallback model.");
    mpuAvailable = false;
  }

  // Configure MQTT
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);

  // Connect WiFi
  connectWiFi();
}

void loop() {
  // Maintain WiFi and MQTT links
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();

  // Periodic Telemetry Transmission at 1 Hz
  unsigned long currentMillis = millis();
  if (currentMillis - lastTelemetryMillis >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryMillis = currentMillis;

    float temperature = 0.0f;
    float humidity = 0.0f;
    readDHT(temperature, humidity);

    float ambientLux = readLDRLux();
    float vibration = readVibrationRMS();

    // Create JSON Telemetry Payload
    StaticJsonDocument<256> doc;
    doc["temperature"] = round(temperature * 10.0f) / 10.0f;
    doc["relative_humidity"] = round(humidity * 10.0f) / 10.0f;
    doc["ambient_light_lux"] = round(ambientLux * 10.0f) / 10.0f;
    doc["vibration_level"] = round(vibration * 10000.0f) / 10000.0f;
    doc["optical_background_noise"] = round(ambientLux * 10.0f) / 10.0f;
    doc["source"] = "HARDWARE";
    doc["device_id"] = MQTT_CLIENT_ID;
    doc["uptime_ms"] = currentMillis;

    char buffer[256];
    size_t len = serializeJson(doc, buffer, sizeof(buffer));

    // Publish to MQTT
    if (mqttClient.connected()) {
      bool success = mqttClient.publish(MQTT_TOPIC, buffer, false);
      if (success) {
        Serial.print("[PUB] -> ");
        Serial.println(buffer);
      } else {
        Serial.println("[ERR] MQTT publish failed.");
      }
    } else {
      Serial.print("[LOCAL_READ] -> ");
      Serial.println(buffer);
    }
  }
}
