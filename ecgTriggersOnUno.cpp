#include <FastLED.h>
#include <ArduinoJson.h>

#define NUM_LEDS 28
#define DATA_PIN 3

CRGB leds[NUM_LEDS];

unsigned long lastBeatTime = 0;
const unsigned long frameDelayMs = 15;
const uint8_t EVENT_FADE = 36;
const uint8_t MAX_PENDING_PACKETS = 4;
const uint8_t MAX_PACKET_CHARS = 96;

struct Event {
  char type;
  unsigned int startMs;
  unsigned int endMs;
};

Event events[5];
Event playbackEvents[5];
const char eventTypes[5] = {'P', 'Q', 'R', 'S', 'T'};
char pendingPackets[MAX_PENDING_PACKETS][MAX_PACKET_CHARS];
uint8_t pendingPacketCount = 0;
uint8_t pendingPacketHead = 0;
uint8_t playbackCount = 0;
uint8_t playbackIndex = 0;
unsigned long playbackStartMs = 0;
bool playbackActive = false;

struct Segment {
  uint8_t start;
  uint8_t count;
  CRGB color;
};

enum SegmentId {
  RIGHT_ATRIUM,
  TRICUSPID_VALVE,
  RIGHT_VENTRICLE,
  PULMONARY_VALVE,
  LEFT_ATRIUM,
  MITRAL_VALVE,
  LEFT_VENTRICLE,
  AORTIC_VALVE
};

// LEDSCHEMATIC.md serial order, zero-indexed ranges:
// 0-2 RA, 3-5 tricuspid, 6-9 RV, 10-12 pulmonary,
// 13-16 LA, 17-19 mitral, 20-24 LV, 25-27 aortic.
const Segment segments[8] = {
  {0, 3, CRGB(0, 80, 255)},
  {3, 3, CRGB(0, 220, 80)},
  {6, 4, CRGB(0, 80, 255)},
  {10, 3, CRGB(0, 220, 80)},
  {13, 4, CRGB(255, 30, 0)},
  {17, 3, CRGB(0, 220, 80)},
  {20, 5, CRGB(255, 30, 0)},
  {25, 3, CRGB(0, 220, 80)}
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
int parseJsonMatrix(const char* line) {
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, line);
  if (error) {
    Serial.print("JSON_ERR");
    Serial.println(error.c_str());
    Serial.flush();
    return 0;
  }

  JsonArray matrix = doc["m"];
  if (matrix.isNull()) {
    Serial.println("JSON_MATRIX_NULL");
    Serial.flush();
    return 0;
  }
  if (!matrix.isNull() && matrix.size() > 0) {
    int count = 0;
    for (JsonVariant row : matrix) {
      if (count >= 5) {
        break;
      }

      if (row.is<JsonArray>() && row.size() >= 2) {
        JsonArray values = row.as<JsonArray>();
        events[count].type = eventTypes[count];
        events[count].startMs = values[0].as<unsigned int>();
        events[count].endMs = values[1].as<unsigned int>();
        if (events[count].endMs <= events[count].startMs) {
          events[count].endMs = events[count].startMs + 1;
        }
        count++;
      }
    }
    return count;
  }

  return 0;
}

void paintSegment(SegmentId segmentId, uint8_t brightness = 255) {
  Segment segment = segments[segmentId];
  CRGB color = segment.color;
  color.nscale8_video(brightness);

  for (uint8_t i = 0; i < segment.count; i++) {
    uint8_t ledIndex = segment.start + i;
    if (ledIndex < NUM_LEDS) {
      leds[ledIndex] = color;
    }
  }
}

void paintHeartPhase(char type) {
  fadeToBlackBy(leds, NUM_LEDS, EVENT_FADE);

  switch (type) {
    case 'P':
      // P-wave: atrial depolarization -> right and left atria.
      paintSegment(RIGHT_ATRIUM);
      paintSegment(LEFT_ATRIUM);
      break;

    case 'Q':
      // Q-wave: AV valves -> tricuspid and mitral valves.
      paintSegment(TRICUSPID_VALVE);
      paintSegment(MITRAL_VALVE);
      break;

    case 'R':
      // R-wave: ventricular depolarization -> right and left ventricles.
      paintSegment(RIGHT_VENTRICLE);
      paintSegment(LEFT_VENTRICLE);
      break;

    case 'S':
      // S-wave: semilunar valves -> pulmonary and aortic valves.
      paintSegment(PULMONARY_VALVE);
      paintSegment(AORTIC_VALVE);
      break;

    case 'T':
      // T-wave: ventricular repolarization, intentionally softer than R.
      paintSegment(RIGHT_VENTRICLE, 110);
      paintSegment(LEFT_VENTRICLE, 110);
      break;
  }

  FastLED.show();
}

void clearEvent(char type) {
  fadeToBlackBy(leds, NUM_LEDS, 160);
  FastLED.show();
}

void startPlayback(int count) {
  if (count <= 0) {
    return;
  }

  Serial.print("START");
  Serial.println(count);
  Serial.flush();

  for (int i = 0; i < count; i++) {
    playbackEvents[i] = events[i];
  }

  playbackCount = count;
  playbackIndex = 0;
  playbackStartMs = millis();
  playbackActive = true;
}

void updatePlayback() {
  if (!playbackActive || playbackIndex >= playbackCount) {
    if (playbackActive) {
      playbackActive = false;
      lastBeatTime = millis();
    }
    return;
  }

  unsigned long elapsed = millis() - playbackStartMs;
  Event& current = playbackEvents[playbackIndex];

  if (elapsed < current.startMs) {
    fadeToBlackBy(leds, NUM_LEDS, 18);
    FastLED.show();
    return;
  }

  if (elapsed < current.endMs) {
    paintHeartPhase(current.type);
    return;
  }

  clearEvent(current.type);
  playbackIndex++;
  if (playbackIndex >= playbackCount) {
    Serial.println("DONE");
    Serial.flush();
    playbackActive = false;
    lastBeatTime = millis();
  }
}

void enqueuePacket(const char* packet) {
  if (pendingPacketCount >= MAX_PENDING_PACKETS) {
    return;
  }

  uint8_t slot = (pendingPacketHead + pendingPacketCount) % MAX_PENDING_PACKETS;
  strncpy(pendingPackets[slot], packet, MAX_PACKET_CHARS - 1);
  pendingPackets[slot][MAX_PACKET_CHARS - 1] = '\0';
  pendingPacketCount++;
}

void loop() {
  static char serialBuffer[MAX_PACKET_CHARS];
  static uint8_t serialLen = 0;

  while (Serial.available()) {
    int incoming = Serial.read();
    if (incoming <= 0) {
      break;
    }

    char ch = (char)incoming;
    if (ch == '\n') {
      if (serialLen > 0) {
        serialBuffer[serialLen] = '\0';
        char trimmed[MAX_PACKET_CHARS];
        uint8_t trimmedLen = 0;
        for (uint8_t i = 0; i < serialLen; i++) {
          if (serialBuffer[i] != '\r' && serialBuffer[i] != '\n') {
            trimmed[trimmedLen++] = serialBuffer[i];
          }
        }
        trimmed[trimmedLen] = '\0';

        if (trimmedLen > 0) {
          String input = String(trimmed);
          input.trim();

          if (input.equalsIgnoreCase("beat")) {
            FastLED.clear();
            FastLED.show();
          } else {
            if (input.startsWith("{")) {
              Serial.println("JSON_RCVD");
              Serial.flush();
            }
            int count = input.startsWith("{") ? parseJsonMatrix(trimmed) : parseEvents(input);
            Serial.print("EVENT_COUNT");
            Serial.println(count);
            Serial.flush();
            if (count > 0) {
              enqueuePacket(trimmed);
            }
          }
        }
      }
      serialLen = 0;
    } else if (serialLen < MAX_PACKET_CHARS - 1) {
      serialBuffer[serialLen++] = ch;
    }
  }

  if (!playbackActive && pendingPacketCount > 0) {
    char* nextPacket = pendingPackets[pendingPacketHead];
    startPlayback(parseJsonMatrix(nextPacket));
    pendingPacketHead = (pendingPacketHead + 1) % MAX_PENDING_PACKETS;
    pendingPacketCount--;
  }

  updatePlayback();

  if (!playbackActive) {
    fadeToBlackBy(leds, NUM_LEDS, 8);
    FastLED.show();
  }
}
