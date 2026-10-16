/*
 * Q-SAT Adaptive Ground Station - ESP32 Hardware Node Configuration Template
 * 
 * Copy this file to config.h if using separate configuration header,
 * or update WIFI_SSID / WIFI_PASSWORD / MQTT_BROKER in qsat_sensor_node.ino.
 */

#ifndef QSAT_CONFIG_H
#define QSAT_CONFIG_H

// WiFi Credentials
#define QSAT_WIFI_SSID       "YOUR_WIFI_SSID"
#define QSAT_WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"

// MQTT Broker Settings
#define QSAT_MQTT_BROKER     "192.168.1.100"
#define QSAT_MQTT_PORT       1883
#define QSAT_MQTT_CLIENT_ID  "ESP32_QGS_NODE_01"
#define QSAT_MQTT_TOPIC      "qsat/environment"

#endif // QSAT_CONFIG_H
