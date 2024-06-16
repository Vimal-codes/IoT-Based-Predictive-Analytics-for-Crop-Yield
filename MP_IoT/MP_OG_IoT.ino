#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <time.h>

#define DHTPIN 14
#define DHTTYPE DHT22

const char* ssid = "S22";
const char* password = "97453426";
const char* serverName = "http://192.168.3.121:8181/add_reading"; // Change to your server IP

DHT dht(DHTPIN, DHTTYPE);

// Calibration constants
const int analogMax = 4095; // Maximum analog value (12-bit ADC)
const float rainMaxMM = 1000.0; // Maximum rainfall in mm corresponding to analogMax
const int rainSensorBaseline = 0; // Adjust this baseline value based on dry sensor reading

const unsigned long SECONDS_PER_HOUR = 3600;
unsigned long previousHourMillis = 0;

float analogToMM(int analogValue) {
  // Ensure the analog value does not go below the baseline
  int adjustedValue = analogValue - rainSensorBaseline;
  if (adjustedValue < 0) {
    adjustedValue = 0;
  }
  // Convert adjusted analog reading to mm based on calibration
  return (adjustedValue * rainMaxMM) / (analogMax - rainSensorBaseline);
}

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("WiFi connected");
  dht.begin();

  configTime(0, 0, "pool.ntp.org"); // Synchronize time with NTP server
  while (!time(nullptr)) {
    Serial.print(".");
    delay(1000);
  }

  previousHourMillis = millis();
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    float h = dht.readHumidity();
    float t = dht.readTemperature();

    // Read the raw analog value from the rain sensor
    int rainAnalog = analogRead(34); // Replace with actual rain sensor reading logic
    float rainMM = analogToMM(rainAnalog);

    if (isnan(h) || isnan(t)) {
      Serial.println("Failed to read from DHT sensor!");
      return;
    }

    // Send current readings to the server
    sendSensorDataToServer(t, h, rainMM);

    // Check if an hour has passed
    unsigned long currentMillis = millis();
    if (currentMillis - previousHourMillis >= SECONDS_PER_HOUR * 1000) {
      // Send the reading to the server
      sendHourlySensorDataToServer(t, h, rainMM);

      // Reset previous hour millis
      previousHourMillis = currentMillis;
    }
  } else {
    Serial.println("WiFi Disconnected");
  }

  delay(1000); // Take a reading every second
}

void sendSensorDataToServer(float temperature, float humidity, float rain) {
  HTTPClient http;
  http.begin(serverName);
  http.addHeader("Content-Type", "application/json");

  String httpRequestData = "{\"temperature\":\"" + String(temperature) + "\",\"humidity\":\"" + String(humidity) + "\",\"rain\":\"" + String(rain) + "\"}";
  Serial.print("HTTP Request data: ");
  Serial.println(httpRequestData);

  int httpResponseCode = http.POST(httpRequestData);

  if (httpResponseCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);

    String response = http.getString();
    Serial.println(response);
  } else {
    Serial.print("Error on sending POST: ");
    Serial.println(httpResponseCode);
    Serial.println(http.errorToString(httpResponseCode));
  }

  http.end();
}

void sendHourlySensorDataToServer(float temperature, float humidity, float rain) {
  HTTPClient http;
  http.begin(serverName);
  http.addHeader("Content-Type", "application/json");

  String httpRequestData = "{\"temperature\":\"" + String(temperature) + "\",\"humidity\":\"" + String(humidity) + "\",\"rain\":\"" + String(rain) + "\",\"hourly\":\"true\"}";
  Serial.print("HTTP Request data: ");
  Serial.println(httpRequestData);

  int httpResponseCode = http.POST(httpRequestData);

  if (httpResponseCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);

    String response = http.getString();
    Serial.println(response);
  } else {
    Serial.print("Error on sending POST: ");
    Serial.println(httpResponseCode);
    Serial.println(http.errorToString(httpResponseCode));
  }

  http.end();
}


