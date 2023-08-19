#include "screen.h"
#include "convtable.h"

static boolean barsEqual(AnyBar *barA, AnyBar *barB){
  return barA->start == barB->start && barA->end == barB->end && barA->enable == barB->enable;
}

static void barsCopy(AnyBar *dest, AnyBar *src){
  memcpy((void*) dest, (void*) src, sizeof(AnyBar));
}

std::string sj2utf8(const std::string &input)
{
  std::string output(40, ' '); //ShiftJis won't give 4byte UTF8, so max. 3 byte per input char are needed
  size_t indexInput = 0, indexOutput = 0;

  while(indexInput < input.length())
  {
    uint8_t value = (uint8_t)input[indexInput];
    if(value == 0xFA){
      indexInput++;
      value = (uint8_t)input[indexInput++];
      switch(value){
        case 0x55:
          output[indexOutput++] = ':';
          break;
      }
      continue;
    }else if(value == 0xFD){
      indexInput++;
      value = (uint8_t)input[indexInput++];
      if(value >= 0x65 && value < (0x65 + 10)){
        output[indexOutput++] = (value - 0x65) + '0';
      }
      switch(value){
        case 0x70:
          output[indexOutput++] = 'V';
          break;
        case 0x86:
          output[indexOutput++] = 'M';
          break;
        case 0x93:
          output[indexOutput++] = 'F';
          break;
        case 0x6f:
          output[indexOutput++] = 'D';
          break;
      }
      continue;
    }
    char arraySection = ((uint8_t)input[indexInput]) >> 4;

    size_t arrayOffset;
    if(arraySection == 0x8) arrayOffset = 0x100; //these are two-byte shiftjis
    else if(arraySection == 0x9) arrayOffset = 0x1100;
    else if(arraySection == 0xE) arrayOffset = 0x2100;
    else arrayOffset = 0; //this is one byte shiftjis

    //determining real array offset
    if(arrayOffset)
    {
      arrayOffset += (((uint8_t)input[indexInput]) & 0xf) << 8;
      indexInput++;
      if(indexInput >= input.length()) break;
    }
    arrayOffset += (uint8_t)input[indexInput++];
    arrayOffset <<= 1;

    //unicode number is...
    uint16_t unicodeValue = (convTable[arrayOffset] << 8) | convTable[arrayOffset + 1];

    //converting to UTF8
    if(unicodeValue < 0x80)
    {
      output[indexOutput++] = unicodeValue;
    }
    else if(unicodeValue < 0x800)
    {
      output[indexOutput++] = 0xC0 | (unicodeValue >> 6);
      output[indexOutput++] = 0x80 | (unicodeValue & 0x3f);
    }
    else
    {
      output[indexOutput++] = 0xE0 | (unicodeValue >> 12);
      output[indexOutput++] = 0x80 | ((unicodeValue & 0xfff) >> 6);
      output[indexOutput++] = 0x80 | (unicodeValue & 0x3f);
    }
  }
  output.resize(indexOutput); //remove the unnecessary bytes
  return output;
}

uint32_t calcChksum(const std::string &str, bool inv){
  uint32_t chk = 0;
  for(int i = 0; i<str.length(); i++){
    chk += str[i] * (1 << i);
  }
  chk = (chk & ~1) | inv;
  return chk;
}

Screen::Screen(){
  for(int i = 0; i<6; i++){
    this->clearRow(i);
  }
}

void Screen::setRowsInvertedBitfield(uint8_t bf){
  this->invertedBitfield = bf;
}

void Screen::setRow(unsigned int rowNum, bool statusOnly, const char* data, int length){
  int col = statusOnly ? 4 : 0;
  if(rowNum > 5){
      rowNum = 5;
  }

  std::string utf8 = sj2utf8(std::string(data, length));
  this->textBuffer[rowNum].replace(col, utf8.length(), utf8);
}

void Screen::clearRow(unsigned int rowNum){
  this->textBuffer[rowNum] = "                    "; // 20 spaces
}


void Screen::processScrollBar(unsigned int start, unsigned int end, unsigned int enable){
  this->scrollBar.start = start;
  this->scrollBar.end = end;
  this->scrollBar.enable = enable;
}

void Screen::processTrackBar(unsigned int start, unsigned int end, unsigned int row, unsigned int enable){
  this->trackBar.start = start;
  this->trackBar.end = end;
  this->trackBar.enable = enable;
  this->trackBarRow = row;
}

I2CSSD1327Screen::I2CSSD1327Screen(): disp(U8G2_R0, U8X8_PIN_NONE){}

void I2CSSD1327Screen::begin(){
  Wire.begin();
  this->disp.begin();
  this->disp.enableUTF8Print();
  this->disp.setFont(u8g2_font_b16_t_japanese1);
  this->disp.setFontDirection(0);
  this->disp.setBusClock(400000);
  for(int i = 0; i<6; i++){
    this->rowCache[i] = calcChksum(this->textBuffer[i], 0);
  }
}

#define SCROLL_BAR_WIDTH 6
#define TOP_RESERVED_PX 16
#define TRACK_BAR_WIDTH 65
#define TRACK_BAR_HMARGIN 5
#define TRACK_BAR_STARTX 60

void I2CSSD1327Screen::render(){
  for(int i = 0; i<6; i++){
    uint32_t chk = calcChksum(this->textBuffer[i], this->invertedBitfield & (1 << i));
    if(chk != this->rowCache[i]){
      this->renderRow(i);
      this->rowCache[i] = chk;
    }
  }
  // render the scrollbar and trackbar

  if(!barsEqual(&this->trackBar, &this->trackBarCache) || this->trackBarRow != this->trackBarRowCache){
    barsCopy(&this->trackBarCache, &this->trackBar);
    trackBarRowCache = trackBarRow;
    // Render trackbar
    this->disp.setDrawColor(0);
    this->disp.drawBox(TRACK_BAR_STARTX+1, 16 * trackBarRow + TRACK_BAR_HMARGIN+1, TRACK_BAR_WIDTH-1, 16 - TRACK_BAR_HMARGIN-1);
    this->disp.setDrawColor(1);
    this->disp.drawFrame(TRACK_BAR_STARTX, 16 * trackBarRow + TRACK_BAR_HMARGIN, TRACK_BAR_WIDTH, 16 - TRACK_BAR_HMARGIN);
    this->disp.drawBox(TRACK_BAR_STARTX+1, 16 * trackBarRow + TRACK_BAR_HMARGIN + this->trackBar.start, this->trackBar.end - this->trackBar.start, 16 - TRACK_BAR_HMARGIN - 1);
    this->disp.updateDisplayArea(0, trackBarRow * 2, (this->scrollBar.enable ? 15 : 16), 2);
  }

  if(this->scrollBar.enable){
    barsCopy(&this->scrollBarCache, &this->scrollBar);
    // Render scrollbar
    if(this->scrollBar.enable){
      this->disp.setDrawColor(0);
      this->disp.drawBox(128 - SCROLL_BAR_WIDTH, TOP_RESERVED_PX, SCROLL_BAR_WIDTH, 96 - TOP_RESERVED_PX);
      this->disp.setDrawColor(1);
      this->disp.drawBox(128 - SCROLL_BAR_WIDTH, TOP_RESERVED_PX, 1, 96 - TOP_RESERVED_PX);
      this->disp.drawBox(128 - SCROLL_BAR_WIDTH, this->scrollBar.start + TOP_RESERVED_PX, SCROLL_BAR_WIDTH, this->scrollBar.end - this->scrollBar.start);
      this->disp.updateDisplayArea(15, 1, 1, 12);
    }
  }
}

void I2CSSD1327Screen::renderRow(unsigned int row){
  this->disp.setDrawColor(0);
  this->disp.drawBox(0, row * 16, 128, 16);
  if(this->invertedBitfield & (1 << row)){
    this->disp.setDrawColor(1);
    if(row == 0 || row == 1){
      this->disp.drawLine(0, 16, 128, 16);
    }
    this->disp.drawBox(0, row * 16, 128, 16);
    this->disp.setDrawColor(0);
  }else{
    this->disp.setDrawColor(1);
    if(row == 0 || row == 1){
      this->disp.drawLine(0, 16, 128, 16);
    }
  }
  this->disp.setCursor(0, 16 * (row + 1) - 1);
  this->disp.print(this->textBuffer[row].c_str());
  this->disp.updateDisplayArea(0, row * 2, (this->scrollBar.enable ? 15 : 16), 2);
}
