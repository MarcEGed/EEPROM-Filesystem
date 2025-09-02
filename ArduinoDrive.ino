#include <EEPROM.h>

const int FILE_SIZE = 300;
const int FILE_COUNT = 3;
const int META_ADDR = FILE_SIZE * FILE_COUNT; // Metadata starts at 900 out of 1024

struct FileMeta {
  char name[10];     // Always null-terminated
  uint16_t length;
};

FileMeta files[FILE_COUNT];

void setup() {
  Serial.begin(9600);
  loadMetadata();
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    handleCommand(cmd);
  }
}

// --- Metadata Handling ---
void loadMetadata() {
  for (int i = 0; i < FILE_COUNT; i++) {
    int addr = META_ADDR + i * sizeof(FileMeta);
    for (int j = 0; j < 10; j++) {
      files[i].name[j] = EEPROM.read(addr + j);
    }
    files[i].name[9] = '\0';  // Ensure null-terminated
    files[i].length = EEPROM.read(addr + 10) | (EEPROM.read(addr + 11) << 8);
  }
}

void saveMetadata() {
  for (int i = 0; i < FILE_COUNT; i++) {
    int addr = META_ADDR + i * sizeof(FileMeta);
    for (int j = 0; j < 9; j++) {
      EEPROM.write(addr + j, files[i].name[j]);
    }
    EEPROM.write(addr + 9, '\0'); // Always terminate string
    EEPROM.write(addr + 10, files[i].length & 0xFF);
    EEPROM.write(addr + 11, files[i].length >> 8);
  }
}

// --- Command Handling ---
void handleCommand(String cmd) {
  cmd.trim();
  
  if (cmd.startsWith("WRITE ")) {
    int fileIndex = cmd.substring(6, 7).toInt() - 1;
    String data = cmd.substring(8);
    writeFile(fileIndex, data);

  } else if (cmd.startsWith("READ ")) {
    int fileIndex = cmd.substring(5).toInt() - 1;
    readFile(fileIndex);

  } else if (cmd.startsWith("LIST")) {
    for (int i = 0; i < FILE_COUNT; i++) {
      Serial.print(i + 1);
      Serial.print(": ");
      Serial.print(files[i].name[0] ? files[i].name : "(empty)");
      Serial.print(" (");
      Serial.print(files[i].length);
      Serial.println(" bytes)");
    }

  } else if (cmd.startsWith("WRITE_NAME ")) {
    int fileIndex = cmd.substring(11, 12).toInt() - 1;
    String newName = cmd.substring(13);
    newName.trim();
    if (newName.length() > 9) newName = newName.substring(0, 9); // max 9 chars, last for '\0'
    for (int i = 0; i < 9; i++) {
      files[fileIndex].name[i] = i < newName.length() ? newName[i] : 0;
    }
    files[fileIndex].name[9] = '\0';
    saveMetadata();

  } else if (cmd.startsWith("DELETE")) {
    int fileIndex = cmd.substring(7).toInt() - 1;
    deleteFile(fileIndex);

  } else if (cmd.startsWith("FORMAT")) {
    formatEEPROM();
    Serial.println("EEPROM formatted. All files cleared.");
  }
}

// --- File Operations ---
void writeFile(int index, String data) {
  if (index < 0 || index >= FILE_COUNT) return;
  if (data.length() > FILE_SIZE) data = data.substring(0, FILE_SIZE);

  int addr = index * FILE_SIZE;
  for (int i = 0; i < data.length(); i++) {
    EEPROM.write(addr + i, data[i]);
  }
  files[index].length = data.length();
  saveMetadata();
}

void readFile(int index) {
  if (index < 0 || index >= FILE_COUNT) return;

  int addr = index * FILE_SIZE;
  for (int i = 0; i < files[index].length; i++) {
    Serial.write(EEPROM.read(addr + i));
  }
}

void deleteFile(int index) {
  if (index < 0 || index >= FILE_COUNT) return;

  int addr = index * FILE_SIZE;
  for (int i = 0; i < FILE_SIZE; i++) {
    EEPROM.write(addr + i, 0);
  }
  files[index].length = 0;
  for (int i = 0; i < 10; i++) {
    files[index].name[i] = 0;
  }
  saveMetadata();
}

// --- Formatting EEPROM ---
void formatEEPROM() {
  for (int i = 0; i < FILE_COUNT; i++) {
    // Clear file data
    int addr = i * FILE_SIZE;
    for (int j = 0; j < FILE_SIZE; j++) {
      EEPROM.write(addr + j, 0);
    }
    // Clear metadata
    for (int j = 0; j < 10; j++) {
      files[i].name[j] = 0;
    }
    files[i].length = 0;
  }
  saveMetadata();
}
