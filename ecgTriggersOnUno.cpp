#include <FastLED.h>

#define NUM_LEDS 28
#define DATA_PIN 3

CRGB leds[NUM_LEDS];

// Flow parameters
int wavePos = 0;
int waveWidth = 12;
bool beatTriggered = false;
unsigned long lastBeatTime = 0;
const unsigned long beatInterval = 1000;
const unsigned long frameDelayMs = 15;

struct Event {
  char type;
  unsigned int startMs;
  unsigned int endMs;
};

Event events[5];
const char eventTypes[5] = {'P', 'Q', 'R', 'S', 'T'};
const uint8_t eventLed[5] = {4, 9, 14, 19, 24};
const CRGB eventColor[5] = {
  CRGB(0, 80, 255),
  CRGB(180, 0, 255),
  CRGB(255, 30, 0),
  CRGB(255, 150, 0),
  CRGB(0, 220, 120)
};

void setup() {
  Serial.begin(115200);

  pinMode(DATA_PIN, OUTPUT);
  digitalWrite(DATA_PIN, HIGH);

  delay(1000);

  FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(60);
  FastLED.clear();
  FastLED.show();
  lastBeatTime = millis();
  Serial.println("UNO_READY");
}
// input to circ representation
// essentially a mutable 5x2 matrix
// {Pin, Pout},{Qin, Qout},{Rin, Rout},{Sin, Sout},{Tin, Tout}

// trigger
void triggerBeat() {
  beatTriggered = true;
  wavePos = 0;
  lastBeatTime = millis();
}

int eventIndex(char type) {
  for (int i = 0; i < 5; i++) {
    if (eventTypes[i] == type) {
      return i;
    }
  }
  return -1;
}

int parseEvents(String line) {
  int count = 0;
  line.trim();
  line.toUpperCase();

  while (line.length() > 0 && count < 5) {
    int colon = line.indexOf(':');
    int comma = line.indexOf(',');

    if (colon <= 0) {
      break;
    }
    if (comma == -1) {
      comma = line.length();
    }

    char type = line.charAt(0);
    if (eventIndex(type) >= 0) {
      events[count].type = type;
      events[count].startMs = (unsigned int)line.substring(colon + 1, comma).toInt();
      events[count].endMs = events[count].startMs + 40;
      count++;
    }

    line = (comma < line.length()) ? line.substring(comma + 1) : "";
    line.trim();
  }

  return count;
}

// JSON packet format:
// {"type":"ecg_pqrst","unit":"ms","labels":["P","Q","R","S","T"],"matrix":[[Pin,Pout],[Qin,Qout],[Rin,Rout],[Sin,Sout],[Tin,Tout]]}
int parseJsonMatrix(String line) {
  int matrixStart = line.indexOf("[[");
  int count = 0;

  if (matrixStart < 0) {
    return 0;
  }

  int cursor = matrixStart + 2;
  while (count < 5 && cursor < line.length()) {
    int comma = line.indexOf(',', cursor);
    int close = line.indexOf(']', comma + 1);

    if (comma < 0 || close < 0) {
      break;
    }

    events[count].type = eventTypes[count];
    events[count].startMs = (unsigned int)line.substring(cursor, comma).toInt();
    events[count].endMs = (unsigned int)line.substring(comma + 1, close).toInt();
    if (events[count].endMs <= events[count].startMs) {
      events[count].endMs = events[count].startMs + 1;
    }

    count++;
    cursor = close + 1;
    int nextOpen = line.indexOf('[', cursor);
    if (nextOpen < 0) {
      break;
    }
    cursor = nextOpen + 1;
  }

  return count;
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

void paintEvent(char type) {
  int idx = eventIndex(type);
  if (idx < 0) {
    return;
  }

  uint8_t center = eventLed[idx];
  CRGB color = eventColor[idx];

  for (int radius = 0; radius <= 2; radius++) {
    int left = center - radius;
    int right = center + radius;

    if (left >= 0) {
      leds[left] = color;
    }
    if (right < NUM_LEDS) {
      leds[right] = color;
    }
  }

  FastLED.show();
}

void clearEvent(char type) {
  int idx = eventIndex(type);
  if (idx < 0) {
    return;
  }

  uint8_t center = eventLed[idx];

  for (int radius = 0; radius <= 2; radius++) {
    int left = center - radius;
    int right = center + radius;

    if (left >= 0) {
      leds[left] = CRGB::Black;
    }
    if (right < NUM_LEDS) {
      leds[right] = CRGB::Black;
    }
  }

  FastLED.show();
}

void executeEvents(int count) {
  unsigned long start = millis();

  for (int i = 0; i < count; i++) {
    while (millis() - start < events[i].startMs) {
      if (beatTriggered) {
        renderFlow();
      } else {
        fadeToBlackBy(leds, NUM_LEDS, 24);
        FastLED.show();
      }
      delay(frameDelayMs);
    }

    if (events[i].type == 'R') {
      triggerBeat();
    }

    while (millis() - start < events[i].endMs) {
      paintEvent(events[i].type);
      delay(frameDelayMs);
    }

    clearEvent(events[i].type);
  }

  lastBeatTime = millis();
}

// lub-dub, two pulses with short gap
void lubDubEffect() {
  // lub
  triggerBeat();
  while (beatTriggered) {
    renderFlow();
    delay(frameDelayMs);
  }

  delay(120);

  // dub
  triggerBeat();
  while (beatTriggered) {
    renderFlow();
    delay(frameDelayMs);
  }
}

void loop() {

  // serial input with baud rate 115200
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.equalsIgnoreCase("beat")) {
      triggerBeat();
    } else {
      int count = input.startsWith("{") ? parseJsonMatrix(input) : parseEvents(input);
      if (count > 0) {
        executeEvents(count);
      }
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
    delay(frameDelayMs);
  }
}
