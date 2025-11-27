#include <SoftwareSerial.h>
#include <Keyboard.h>
#include <Mouse.h>

// ======================================================
//                   UART SETUP
// ======================================================
#define RX_PIN 16   // Pico RX from Pi Zero
#define TX_PIN 17   // Pico TX to Pi Zero

SoftwareSerial mySerial(RX_PIN, TX_PIN);

// ======================================================
//                     SETUP
// ======================================================
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);

  Keyboard.begin();
  Mouse.begin();

  mySerial.begin(19200);
  Serial.begin(9600);

  delay(2000);
  Serial.println("Pi Pico HID Bridge Ready");
}

// ======================================================
//         MAP STRING (e.g. "CTRL") TO HID KEYCODE
// ======================================================
uint8_t getKeycode(String keyStr) {

  // Single character keys
  if (keyStr.length() == 1) {
    char c = keyStr.charAt(0);

    // Letters
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'))
      return c;

    // Numbers
    if (c >= '0' && c <= '9')
      return c;

    // Symbols
    switch (c) {
      case ' ': return ' ';
      case '-': return '-';
      case '=': return '=';
      case '[': return '[';
      case ']': return ']';
      case '\\': return '\\';
      case ';': return ';';
      case '\'': return '\'';
      case ',': return ',';
      case '.': return '.';
      case '/': return '/';
      case '`': return '`';
    }
  }

  // Named keys
  if (keyStr == "SPACE")     return ' ';
  if (keyStr == "ENTER")     return KEY_RETURN;
  if (keyStr == "BACKSPACE") return KEY_BACKSPACE;
  if (keyStr == "TAB")       return KEY_TAB;
  if (keyStr == "ESC")       return KEY_ESC;

  // Arrow keys
  if (keyStr == "UP")        return KEY_UP_ARROW;
  if (keyStr == "DOWN")      return KEY_DOWN_ARROW;
  if (keyStr == "LEFT")      return KEY_LEFT_ARROW;
  if (keyStr == "RIGHT")     return KEY_RIGHT_ARROW;

  // Navigation
  if (keyStr == "DELETE")    return KEY_DELETE;
  if (keyStr == "HOME")      return KEY_HOME;
  if (keyStr == "END")       return KEY_END;
  if (keyStr == "PAGEUP")    return KEY_PAGE_UP;
  if (keyStr == "PAGEDOWN")  return KEY_PAGE_DOWN;

  // Function keys
  if (keyStr == "F1") return KEY_F1;
  if (keyStr == "F2") return KEY_F2;
  if (keyStr == "F3") return KEY_F3;
  if (keyStr == "F4") return KEY_F4;
  if (keyStr == "F5") return KEY_F5;
  if (keyStr == "F6") return KEY_F6;
  if (keyStr == "F7") return KEY_F7;
  if (keyStr == "F8") return KEY_F8;
  if (keyStr == "F9") return KEY_F9;
  if (keyStr == "F10") return KEY_F10;
  if (keyStr == "F11") return KEY_F11;
  if (keyStr == "F12") return KEY_F12;

  // Modifiers
  if (keyStr == "CTRL")  return KEY_LEFT_CTRL;
  if (keyStr == "SHIFT") return KEY_LEFT_SHIFT;
  if (keyStr == "ALT")   return KEY_LEFT_ALT;
  if (keyStr == "WIN")   return KEY_LEFT_GUI;
  if (keyStr == "RWIN")  return KEY_RIGHT_GUI;

  return 0;
}

// ======================================================
//                       LED BLINK
// ======================================================
void blinkLED() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(50);
  digitalWrite(LED_BUILTIN, LOW);
}

// ======================================================
//         HANDLE "KEY:..." COMMAND (PRESS KEYS)
// ======================================================
void handleKey(String params) {
  params.trim();
  if (params.length() == 0) return;

  int plusIndex = params.indexOf('+');

  // ------------------ SINGLE KEY ------------------
  if (plusIndex == -1) {

    // SPACE special case
    if (params == "SPACE" || (params.length() == 1 && params.charAt(0) == ' ')) {
      Keyboard.write(' ');
      blinkLED();
      return;
    }

    // Printable char
    if (params.length() == 1) {
      char c = params.charAt(0);
      if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
          (c >= '0' && c <= '9') ||
          c == '-' || c == '=' || c == '[' || c == ']' ||
          c == '\\' || c == ';' || c == '\'' || c == ',' ||
          c == '.' || c == '/' || c == '`') {

        Keyboard.write(c);
        blinkLED();
        return;
      }
    }

    // Special named keys
    uint8_t k = getKeycode(params);
    if (k != 0) {
      Keyboard.press(k);
      delay(50);
      Keyboard.release(k);
      blinkLED();
    }
  }

  // ------------------ KEY COMBO (CTRL+C) ------------------
  else {
    uint8_t keys[10];
    int keyCount = 0;

    int start = 0;

    // Extract parts
    while ((plusIndex = params.indexOf('+', start)) != -1) {
      String part = params.substring(start, plusIndex);
      uint8_t k = getKeycode(part);
      if (k != 0) keys[keyCount++] = k;
      start = plusIndex + 1;
    }

    // Last part
    uint8_t k = getKeycode(params.substring(start));
    if (k != 0) keys[keyCount++] = k;

    // Press all
    for (int i = 0; i < keyCount; i++)
      Keyboard.press(keys[i]);

    delay(50);
    Keyboard.releaseAll();
    blinkLED();
  }
}

// ======================================================
//           HANDLE "KEYUP:..." (RELEASE KEY)
// ======================================================
void handleKeyRelease(String keyStr) {
  keyStr.trim();
  uint8_t k = getKeycode(keyStr);
  if (k != 0) Keyboard.release(k);
}

// ======================================================
//                       MAIN LOOP
// ======================================================
void loop() {

  if (!mySerial.available()) return;

  String line = mySerial.readStringUntil('\n');
  line.trim();

  Serial.print("UART: ");
  Serial.println(line);

  int firstColon = line.indexOf(':');
  if (firstColon == -1) return;

  String cmd    = line.substring(0, firstColon);
  String params = line.substring(firstColon + 1);

  // ---------------------- KEYBOARD ----------------------
  if (cmd == "KEY") {
    handleKey(params);
  }
  else if (cmd == "KEYUP") {
    handleKeyRelease(params);
  }

  // ---------------------- MOUSE -------------------------
  else if (cmd == "MOUSE") {

    int secondColon = params.indexOf(':');
    String action, args;

    if (secondColon == -1) {
      action = params;
      args = "";
    } else {
      action = params.substring(0, secondColon);
      args   = params.substring(secondColon + 1);
    }

    if (action == "MOVE") {
      int sep = args.indexOf(':');
      if (sep == -1) return;

      int dx = args.substring(0, sep).toInt();
      int dy = args.substring(sep + 1).toInt();
      Mouse.move(dx, dy, 0);
    }

    else if (action == "CLICK") {
      Mouse.click(MOUSE_LEFT);
      blinkLED();
    }

    else if (action == "RCLICK") {
      Mouse.click(MOUSE_RIGHT);
      blinkLED();
    }

    else if (action == "SCROLL") {
      int amount = args.toInt();
      Mouse.move(0, 0, amount);
      blinkLED();
    }
  }
}
