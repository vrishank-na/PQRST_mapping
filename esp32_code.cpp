// ======================
// GPIO DEFINITIONS
// ======================
#define RA1 2
#define RA2 4
#define LA1 5
#define LA2 18

#define RV1 13
#define RV2 14
#define LV1 27
#define LV2 26

#define TRICUSPID 23
#define MITRAL    22
#define PULMONARY 25
#define AORTIC    33

int atria[] = {RA1, RA2, LA1, LA2};
int ventricles[] = {RV1, RV2, LV1, LV2};

struct Event {
  char type;
  int time_ms;
};

Event events[5];

// ======================
// SETUP
// ======================
void setup() {
  Serial.begin(115200);

  int pins[] = {
    RA1, RA2, LA1, LA2,
    RV1, RV2, LV1, LV2,
    TRICUSPID, MITRAL, PULMONARY, AORTIC
  };

  for (int p : pins) {
    pinMode(p, OUTPUT);
    digitalWrite(p, LOW);
  }

  Serial.println("[ESP32] Ready for PQRST events");
}

// ======================
// PARSE PQRST LINE
// ======================
int parseEvents(String line) {
  int count = 0;

  while (line.length() && count < 5) {
    int colon = line.indexOf(':');
    int comma = line.indexOf(',');

    if (colon == -1) break;
    if (comma == -1) comma = line.length();

    events[count].type = line.charAt(0);
    events[count].time_ms =
      line.substring(colon + 1, comma).toInt();

    line = (comma < line.length()) ? line.substring(comma + 1) : "";
    count++;
  }

  return count;
}

// ======================
// EXECUTE EVENTS
// ======================
void executeEvents(int n) {
  unsigned long t0 = millis();

  for (int i = 0; i < n; i++) {

    while (millis() < t0 + events[i].time_ms);

    switch (events[i].type) {

      case 'P':   // P-wave: right and left atria.
        for (int p : atria) digitalWrite(p, HIGH);
        delay(60);
        for (int p : atria) digitalWrite(p, LOW);
        break;

      case 'Q':   // Q-wave: tricuspid and mitral valves.
        digitalWrite(TRICUSPID, HIGH);
        digitalWrite(MITRAL, HIGH);
        delay(30);
        digitalWrite(TRICUSPID, LOW);
        digitalWrite(MITRAL, LOW);
        break;

      case 'R':   // R-wave: right and left ventricles.
        for (int v : ventricles) digitalWrite(v, HIGH);
        break;

      case 'S':   // S-wave: pulmonary and aortic valves.
        digitalWrite(PULMONARY, HIGH);
        digitalWrite(AORTIC, HIGH);
        delay(50);
        digitalWrite(PULMONARY, LOW);
        digitalWrite(AORTIC, LOW);

        for (int v : ventricles) digitalWrite(v, LOW);
        break;

      case 'T':   // T-wave: ventricular repolarization (optional glow).
        // intentionally subtle / no action
        break;
    }
  }
}

// ======================
// MAIN LOOP
// ======================
void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    if (line.length() > 0) {
      int n = parseEvents(line);
      executeEvents(n);
    }
  }
}