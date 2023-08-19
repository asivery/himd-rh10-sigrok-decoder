#include "protocol.h"
#include "sercom_init.h"

#define Serial SerialUSB

#define DEBUG
#define MESSAGE_LENGTH 43
#define MESSAGE_BUFFER_LENGTH 300

static I2CSSD1327Screen screen;


void __attribute__((noreturn)) panic(const char* reason){
  SerialUSB.println(reason);
  detachInterrupt(digitalPinToInterrupt(SCK));
  for(;;){
    // TODO: SHOW ALL PREVIOUS BUFFERS
  }
}

void setup(){
  SerialUSB.begin(115200);
  delay(4000);
  SerialUSB.println("INIT!");
  initSercom();
  delay(1000);
  screen.begin();
  Protocol::begin(&screen);
}


static uint8_t incomingBytesBuffer[MESSAGE_LENGTH * MESSAGE_BUFFER_LENGTH];
static uint32_t writingPtr = 0, readingPtr = 0;

void loop(){
  int coercedWritingPtr = (writingPtr / MESSAGE_LENGTH) * MESSAGE_LENGTH;
  if(coercedWritingPtr == readingPtr) return;
  Protocol::handleIncomingMessage(&incomingBytesBuffer[readingPtr]);
  readingPtr += MESSAGE_LENGTH;
  readingPtr %= (MESSAGE_LENGTH * MESSAGE_BUFFER_LENGTH);
  
  screen.render();
}


typedef unsigned long long int micros_t;
micros_t lastByte = 0;

void SERCOM0_Handler(){
  uint8_t data = 0;
  uint8_t interrupts = SERCOM0->SPI.INTFLAG.reg; // Read SPI interrupt register

  if(interrupts & 0b10000000){
    Serial.println("ERRROR");
    SERCOM0->SPI.INTFLAG.bit.ERROR = 1;
  }
  
  // Slave Select Low interrupt
  if (interrupts & (1 << 3)) // 1000 = bit 3 = SSL // page 503
  {
    SERCOM0->SPI.INTFLAG.bit.SSL = 1; // Clear Slave Select Low interrupt
  }
  
  // Data Received Complete interrupt: this is where the data is received, which is used in the main loop
  if (interrupts & (1 << 2)) // 0100 = bit 2 = RXC // page 503
  {
    boolean hasOverflown = SERCOM0->SPI.STATUS.bit.BUFOVF;
    if(hasOverflown){
      Serial.println("OVERFLOW");
      SERCOM0->SPI.STATUS.bit.BUFOVF = 1;
    }
    
    micros_t currentByte = micros();
    micros_t reset = currentByte - lastByte;
    if(reset > 5000){
      writingPtr = (writingPtr / MESSAGE_LENGTH) * MESSAGE_LENGTH;
    }
    lastByte = currentByte;
    
    data = SERCOM0->SPI.DATA.reg; // Read data register
    incomingBytesBuffer[writingPtr++] = data;
    writingPtr %= (MESSAGE_LENGTH * MESSAGE_BUFFER_LENGTH);
    
    SERCOM0->SPI.INTFLAG.bit.RXC = 1; // Clear Receive Complete interrupt
  }
  
  if (interrupts & (1 << 1)) // 0010 = bit 1 = TXC // page 503
  {
    SERCOM0->SPI.INTFLAG.bit.TXC = 1; // Clear Transmit Complete interrupt
  }
  
  // Data Register Empty interrupt
  if (interrupts & (1 << 0)) // 0001 = bit 0 = DRE // page 503
  {
    SERCOM0->SPI.DATA.reg = 0xAA;
  }
}
