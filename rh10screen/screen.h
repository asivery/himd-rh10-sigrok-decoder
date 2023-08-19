#pragma once
#include <stdint.h>
#include <string>
#include <U8g2lib.h>
#include <Wire.h>

struct AnyBar{
  unsigned int start, end, enable;
};

class Screen{
public:
    Screen();
    void setRowsInvertedBitfield(uint8_t inv);
    void setRow(unsigned int row, bool statusOnly, const char* data, int length);
    void clearRow(unsigned int row);
    void processScrollBar(unsigned int start, unsigned int end, unsigned int enable);
    void processTrackBar(unsigned int start, unsigned int end, unsigned int row, unsigned int enable);
    
    virtual void render() = 0;
protected:
    std::string textBuffer[6];
    AnyBar scrollBar;
    AnyBar trackBar;
    uint8_t trackBarRow;
    uint8_t invertedBitfield;
};

class I2CSSD1327Screen : public Screen {
public:
    I2CSSD1327Screen();
    void begin();
    void render() override;
private:
    void renderRow(unsigned int row);
    uint32_t rowCache[6];
    AnyBar scrollBarCache;
    AnyBar trackBarCache;
    uint8_t trackBarRowCache;
    
    U8G2_SSD1327_MIDAS_128X128_F_HW_I2C disp;
};
