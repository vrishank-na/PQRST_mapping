#include <FastLED.h>

// ---------------- CONFIG ----------------
#define NUM_LEDS 144
#define DATA_PIN 6
#define RELAY_PIN 7

CRGB leds[NUM_LEDS];

// Flow parameters
int wavePos = 0;
int waveWidth = 12;
bool beatTriggered = false;

unsigned long lastBeatTime = 0;
int beatInterval = 800; // ms between beats

// ---------------- SETUP ----------------
void setup() {
  Serial.begin(115200);

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH); // power ON

  delay(1000); // stabilize power

  FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(60);
  FastLED.clear();
  FastLED.show();
}

// ---------------- HEARTBEAT TRIGGER ----------------
void triggerBeat() {
  beatTriggered = true;
  wavePos = 0;
  lastBeatTime = millis();
}

// ---------------- FLOW ANIMATION ----------------
void renderFlow() {
  fadeToBlackBy(leds, NUM_LEDS, 40);

  for (int i = 0; i < waveWidth; i++) {
    int index = wavePos - i;

    if (index >= 0 && index < NUM_LEDS) {
      int intensity = 255 - (i * 20);
      leds[index] = CRGB(intensity, intensity * 0.1, 0);
    }
  }

  FastLED.show();
  wavePos++;

  if (wavePos > NUM_LEDS) {
    beatTriggered = false;
  }
}

// ---------------- LUB-DUB EFFECT ----------------
void lubDubEffect() {
  // First pulse (LUB)
  triggerBeat();
  while (beatTriggered) {
    renderFlow();
    delay(15);
  }

  delay(120);

  // Second pulse (DUB)
  triggerBeat();
  while (beatTriggered) {
    renderFlow();
    delay(15);
  }
}

// ---------------- LOOP ----------------
void loop() {

  // ---- SERIAL INPUT ----
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');

    if (input.indexOf("beat") >= 0) {
      triggerBeat();
    }
  }

  // ---- AUTO HEARTBEAT (fallback) ----
  if (millis() - lastBeatTime > beatInterval) {
    lubDubEffect();
    lastBeatTime = millis();
  }

  // ---- NORMAL FLOW ----
  if (beatTriggered) {
    renderFlow();
    delay(15);
  }
}