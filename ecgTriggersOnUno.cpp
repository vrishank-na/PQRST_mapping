#include <FastLED.h>
#define NUM_LEDS 28
#define DATA_PIN 3
CRGB leds[NUM_LEDS];

// Flow parameters
int wavePos = 0;
int waveWidth = 12;
bool beatTriggered = false;

void setup() {
  Serial.begin(115200);

  pinMode(DATA_PIN, OUTPUT);
  digitalWrite(DATA_PIN, HIGH);

  delay(1000);

  FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(60);
  FastLED.clear();
  FastLED.show();
}
// input to circ representation
// [P:in, P:out; Q:in, Q:out; R:in, R:out; S:in, S:out; T:in, T:out]
// array within an array
//  essentially a mutable 5x2 matrix
// {Pin, Pout},{Qin, Qout},{Rin, Rout},{Sin, Sout},{Tin, Tout}

// trigger
void triggerBeat() {
  beatTriggered = true;
  wavePos = 0;
  lastBeatTime = millis();
}

// render flow, default state black
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
// lub-dub, two pulses with short gap
void lubDubEffect() {
  // lub
  triggerBeat();
  while (beatTriggered) {
    renderFlow();
    delay(15);
  }

  delay(120);

  // dub
  triggerBeat();
  while (beatTriggered) {
    renderFlow();
    delay(15);
  }
}

void loop() {

  // serial input with baud rate 115200
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');

    if (input.indexOf("beat") >= 0) {
      triggerBeat();
    }
  }

  // fallback
  if (millis() - lastBeatTime > beatInterval) {
    lubDubEffect();
    lastBeatTime = millis();
  }

  // normal flow
  if (beatTriggered) {
    renderFlow();
    delay(15);
  }
}