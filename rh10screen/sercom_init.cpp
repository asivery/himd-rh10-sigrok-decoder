#include "sercom_init.h"

void initSercom(){
  PORT->Group[PORTA].PINCFG[8].bit.PMUXEN = 0x1; // Enable Peripheral Multiplexing for SERCOM0 SPI PA08
  PORT->Group[PORTA].PMUX[4].bit.PMUXE = 0x2; // SERCOM0 is selected for peripheral use of this pad (0x2 selects peripheral function C: SERCOM)
  PORT->Group[PORTA].PINCFG[9].bit.PMUXEN = 0x1; // Enable Peripheral Multiplexing for SERCOM0 SPI PA09
  PORT->Group[PORTA].PMUX[4].bit.PMUXO = 0x2; // SERCOM0 is selected for peripheral use of this pad (0x2 selects peripheral function C: SERCOM)
  PORT->Group[PORTA].PINCFG[10].bit.PMUXEN = 0x1; // Enable Peripheral Multiplexing for SERCOM0 SPI PA10
  PORT->Group[PORTA].PMUX[5].bit.PMUXE = 0x2; // SERCOM0 is selected for peripheral use of this pad (0x2 selects peripheral function C: SERCOM)
  PORT->Group[PORTA].PINCFG[11].bit.PMUXEN = 0x1; // Enable Peripheral Multiplexing for SERCOM0 SPI PA11
  PORT->Group[PORTA].PMUX[5].bit.PMUXO = 0x2; // SERCOM0 is selected for peripheral use of this pad (0x2 selects peripheral function C: SERCOM)

  SERCOM0->SPI.CTRLA.bit.ENABLE = 0; // page 481
  while (SERCOM0->SPI.SYNCBUSY.bit.ENABLE); // Wait until bit is enabled.

  SERCOM0->SPI.CTRLA.bit.SWRST = 1; // page 481
  while (SERCOM0->SPI.CTRLA.bit.SWRST || SERCOM0->SPI.SYNCBUSY.bit.SWRST); // Wait until software reset is complete.

  NVIC_EnableIRQ(SERCOM0_IRQn);
  NVIC_SetPriority(SERCOM0_IRQn, 2);
  GCLK->CLKCTRL.reg = GCLK_CLKCTRL_ID(GCM_SERCOM0_CORE) | // Generic Clock 0
                          GCLK_CLKCTRL_GEN_GCLK0 | // Generic Clock Generator 0 is the source
                          GCLK_CLKCTRL_CLKEN; // Enable Generic Clock Generator
  while (GCLK->STATUS.reg & GCLK_STATUS_SYNCBUSY); // Wait for synchronisation

  // Set up SPI control A register
  SERCOM0->SPI.CTRLA.bit.DORD = 1; // LSB is transferred first. // page 492
  SERCOM0->SPI.CTRLA.bit.CPOL = 1; // SCK is high when idle. The leading edge of a clock cycle is a falling edge, while the trailing edge is a rising edge. // page 492
  SERCOM0->SPI.CTRLA.bit.CPHA = 1; // Data is sampled on a trailing SCK edge and changed on a leading SCK edge. // page 492
  SERCOM0->SPI.CTRLA.bit.FORM = 0x0; // SPI frame // page 493
  SERCOM0->SPI.CTRLA.bit.DIPO = 0x0; // DATA PAD0 is used as slave input: MOSI // (slave mode) page 493
  SERCOM0->SPI.CTRLA.bit.DOPO = 0x2; // DATA PAD2 is used as slave output: MISO // (slave mode) page 493
  SERCOM0->SPI.CTRLA.bit.MODE = 0x2; // SPI slave operation. // page 494
  SERCOM0->SPI.CTRLA.bit.IBON = 0x0; // Immediate Buffer Overflow Notification. STATUS.BUFOVF is asserted immediately upon buffer overflow. // page 494
  SERCOM0->SPI.CTRLA.bit.RUNSTDBY = 1; // Wake on Receive Complete interrupt. // page 494

  // Set up SPI control B register
  SERCOM0->SPI.CTRLB.bit.SSDE = 0x0; // Enable Slave Select Low Detect // page 497
  SERCOM0->SPI.CTRLB.bit.CHSIZE = 0; // Character Size 8 bits // page 497

  // Set up SPI interrupts
  SERCOM0->SPI.INTENSET.bit.SSL = 0x1; // Enable Slave Select Low interrupt. // page 501
  SERCOM0->SPI.INTENSET.bit.RXC = 0x1; // Enable Receive Complete interrupt. // page 501
  SERCOM0->SPI.INTENSET.bit.TXC = 0x1; // Disable Transmit Complete interrupt. // page 501
  SERCOM0->SPI.INTENSET.bit.ERROR = 0x1; // Enable Error interrupt. // page 501
  SERCOM0->SPI.INTENSET.bit.DRE = 0x1; // Disable Data Register Empty interrupt. // page 501

  SERCOM0->SPI.CTRLA.bit.ENABLE = 1; // page 481
  while (SERCOM0->SPI.SYNCBUSY.bit.ENABLE); // Wait until bit is enabled.
  SERCOM0->SPI.CTRLB.bit.RXEN = 0x1; // Enable Receiver // page 496. This is done here rather than in section "Set up SPI control B register" due to an errate issue.
  while (SERCOM0->SPI.SYNCBUSY.bit.CTRLB); // Wait until receiver is enabled.
}
