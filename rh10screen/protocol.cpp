#include "protocol.h"

static Screen *screen;

static uint8_t rowBitfieldToFirst(uint8_t rowBitfield){
  for(int i = 0; i<6; i++){
    if(rowBitfield  & (1 << i)){
      return i;
    }
  }
  return 0;
}

void serialPrintHex(byte b){
  const char *data = "0123456789ABCDEF";
  SerialUSB.print(data[b >> 4]);
  SerialUSB.print(data[b & 0xF]);
}

#define CARGS (uint8_t *data, int &crs)
#define COMMAND(x) void x CARGS
#define NEXT (data[crs++])
typedef void (*command_handler) CARGS;

COMMAND(handleSetInvertedRows){
  uint8_t rows = NEXT;
  screen->setRowsInvertedBitfield(~rows);
}

COMMAND(handleClear){
  uint8_t clearMap = NEXT;
  for(int i = 0; i<6; i++){
    if((clearMap & (1 << i)) != 0){
      screen->clearRow(i);
    }
  }
}

COMMAND(handleScrollbarManage){
  byte pixelStart = NEXT;
  byte pixelEnd = NEXT;
  byte unk = NEXT;
  byte enable = NEXT;
  
  screen->processScrollBar(pixelStart, pixelEnd, enable);
}

COMMAND(handleTrackbarManage){
  byte rows = rowBitfieldToFirst(NEXT);
  byte pixelStart = NEXT;
  byte pixelEnd = NEXT;
  byte enable = NEXT;

  screen->processTrackBar(pixelStart, pixelEnd, rows, enable);
}

COMMAND(handleText){
  uint8_t opcode = NEXT;  
  uint8_t rowBitfield = NEXT;
  uint8_t length = NEXT & 0b01111111;
  uint8_t enc = NEXT;
  char text[40] = {0x20};
  for(int i = 0; i<length; i++) text[i] = NEXT;

  uint8_t row = rowBitfieldToFirst(rowBitfield);

  screen->setRow(row, opcode == 0xE3, text, 30);
}

COMMAND(handleTextE2){
  uint8_t rowBitfield = NEXT;
  uint8_t what = NEXT;
  uint8_t length = NEXT & 0b01111111;
  uint8_t enc = NEXT;

  uint8_t row = rowBitfieldToFirst(rowBitfield);
  char text[40] = {0};
  for(int i = 0; i<length; i++) text[i] = NEXT;
  screen->setRow(row, false, text, length);
}

void Protocol::begin(Screen *_screen){
  screen = _screen;
}

#define IGNORE(opcode, len) case opcode: i += len; break
#define BIND(opcode, handler) case opcode: handler(data, ++i); break
#define BIND_WITHOPCODE(opcode, handler) case opcode: handler(data, i); break
void Protocol::handleIncomingMessage(uint8_t *data){
  int i = 0;
  
  while(i < 43 && data[i] != 0){
    uint8_t opcode = data[i];
    command_handler ch;
    
    switch(opcode){
      // Prologues
      IGNORE(0x3D, 3);
      IGNORE(0x3F, 3);
      IGNORE(0x3B, 3);
      IGNORE(0xFF, 3);
      IGNORE(0x37, 3);
      IGNORE(0x1F, 3);
      IGNORE(0x2F, 3);
      
      // Commands
      IGNORE(0x02, 2);
      BIND(0x03, handleClear);
      IGNORE(0x04, 2);
      BIND(0x05, handleSetInvertedRows);
      IGNORE(0x13, 2);
      IGNORE(0x1B, 2);
      IGNORE(0x20, 2);
      IGNORE(0x23, 2);
      IGNORE(0x24, 2);
      IGNORE(0x30, 2);
      IGNORE(0x50, 5);
      IGNORE(0x53, 5);
      IGNORE(0x54, 5);
      IGNORE(0x56, 5);

      BIND(0x68, handleScrollbarManage);
      BIND(0x69, handleTrackbarManage);
      
      IGNORE(0x6a, 5);
      IGNORE(0x6b, 5);
      IGNORE(0x75, 7);
      IGNORE(0x91, 10);

      BIND(0xE2, handleTextE2);
      BIND_WITHOPCODE(0xE0, handleText);
      BIND_WITHOPCODE(0xE3, handleText);
      

      default:
        SerialUSB.print("Unknown command: ");
        SerialUSB.print(opcode);
        SerialUSB.print(" at index ");
        SerialUSB.print(i);
        SerialUSB.println();
        for(int i = 0; i<43; i++){
          serialPrintHex(data[i]);
          SerialUSB.print(" ");
        }
        SerialUSB.println();
        return;
    }
  }
}
#undef CARGS
#undef COMMAND
#undef END_COMMAND
#undef NEXT
#undef IGNORE
#undef BIND
