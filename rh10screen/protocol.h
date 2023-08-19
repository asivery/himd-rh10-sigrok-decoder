#pragma once
#include "screen.h"

namespace Protocol{
  void begin(Screen *screen);
  void handleIncomingMessage(uint8_t *data);
};
