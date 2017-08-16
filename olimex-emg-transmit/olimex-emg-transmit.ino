/* Code for sampling 4 channels of EMG signals using the
 * Olimex 'EMG EKG' Arduino shield on an Arduino Uno.
 * 
 * This is part of Christian D'Abrera's engineering final
 * year project titled "EMG Bio-feedback for rehabilitation".
 * 
 * Christian D'Abrera
 * Curtin University 2017
 * christian.dabrera@student.curtin.edu.au
 * chrisdabrera@gmail.com
 * 
 * ================================
 * Based on code shipped with OLIMEX SHIELD-EKG/EMG
 * Contributors:
 * * Penko Todorov Bozhkov (2012)
 * * Joerg Hansmann (2003)
 * * Jim Peters (2003)
 * * Andreas Robinson (2003)
 * ================================
 * Notes:
 * * Header should be 0xFC twice, as this combination cannot
 *   occur when transmitting a 10-bit value as two bytes.
 * * Other info to be transmitted is actual OCR value, to 
 *   allow proper timestamp calculation, and a 'packet counter'
 *   which lets us know if we missed a packet.
 */


// All definitions
#define HEADER 0xfc
#define SAMP_FREQ 512
#define LED_PIN  13
#define CAL_SIG_PIN 9

#if ( SAMP_FREQ < 488 ) // Sets a flag if prescaler needs changing
#define SLOW 1
#endif


// Gloval constants and variables
byte OCRval = 0;          // OCR value for sampling freq
volatile byte TXData[12]; // bytes to be transmitted
volatile byte i;          // counter variable
volatile int ADC_val;     // current ADC val


//~~~~~~~~~~
// Functions
//~~~~~~~~~~

/****************************************************/
/*  Function name: setSampleFreq                    */
/*  Parameters                                      */
/*    Input   :  int (frequency)                    */
/*    Output  :  No                                 */
/*    Action: Determines OCR value for given sample */
/*     frequency, configures TIMER2 and enables ISR */
/****************************************************/
void setSampleFreq(int freq) {
/* ATMega328P datasheet s18.7.2 (pp 147-148)
 * f_OCnx = f_clkIO / (2*N*(1+OCRnx))
 *   where:
 *     f_OCnx  = timer output frequency
 *     f_clkIO = CPU frequency
 *     OCRnx   = output compare register x (set value)
 *     N       = Prescaler value
 * 
 * N should be 64 for a minimum frequency of 488Hz
*/
  OCRval = constrain((F_CPU) / 2 / 64 / (SAMP_FREQ) - 1, 0, 255);

  // clear all timer2 registers
  TCCR2A = 0;
  TCCR2B = 0;
  TIMSK2 = 0;

  //set timer2 control register values
  TCCR2A |= (1<<WGM21);
  TCCR2B |= (1<<CS22);
#ifdef SLOW
  // change prescaler to 128, halve calculated OCR val
  TCCR2B |= (1<<CS20);
  OCRval >>= 1;
#endif
  TIMSK2 |= (1<<OCIE2A);
  OCR2A = OCRval;
}


/****************************************************/
/*  Function name: togglePins                       */
/*  Parameters                                      */
/*    Input   :  No                                 */
/*    Output  :  No                                 */
/*    Action: Toggles state of an LED and 'CAL' pin */
/****************************************************/
void togglePins(){
  static byte state = HIGH;
  digitalWrite(LED_PIN, state);
  digitalWrite(CAL_SIG_PIN, state);
  state = !state;
}


/****************************************************/
/*  Function name: setup                            */
/*  Parameters                                      */
/*    Input   :  No                                 */
/*    Output  :  No                                 */
/*    Action: Initializes peripherals & variables   */
/****************************************************/
void setup() {
  noInterrupts();

  Serial.begin(115200);
  setSampleFreq(SAMP_FREQ);
  pinMode(LED_PIN, OUTPUT);
  pinMode(CAL_SIG_PIN, OUTPUT);
  analogReference(EXTERNAL);

  TXData[0] = HEADER;
  TXData[1] = HEADER;
  TXData[2] = OCRval;
  for (i=3; i<12; i++){
    TXData[i] = 0;
  }

  interrupts();
}


/****************************************************/
/*  Function name: ISR(TIMER2_COMPA_vect)           */
/*  - is an interrupt service routine (TIMER2       */
/*    compare match)                                */
/*  Parameters                                      */
/*    Input   :  No                                 */
/*    Output  :  No                                 */
/*    Action: Samples ADC at a fixed frequency.     */
/****************************************************/
ISR(TIMER2_COMPA_vect){
  // Read 4 ADC channels
  for(i=0;i<4;i++){
    ADC_val = analogRead(i);
    TXData[4 + 2*i] = (byte)(ADC_val >> 8);
    TXData[5 + 2*i] = (byte)ADC_val;
  }

  // transmit data
  for(i=0;i<12;i++){
    Serial.write(TXData[i]);
  }
  // increment packet counter
  TXData[3]++;

  // Toggle LED and CAL_SIG_PIN at SAMPFREQ/2
  togglePins();
}


/****************************************************/
/*  Function name: loop                             */
/*  Parameters                                      */
/*    Input   :  No                                 */
/*    Output  :  No                                 */
/*    Action: Puts MCU into sleep mode.             */
/****************************************************/
void loop() {
  __asm__ __volatile__ ("sleep");
}



