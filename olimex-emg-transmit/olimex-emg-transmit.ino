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
#define HEADER 0xcc
//#define SAMP_FREQ 512
#define SAMP_FREQ 256
#define LED_PIN  13
#define CAL_SIG_PIN 9
#define PACKET_SIZE 9
#define BAUDRATE 115200

#if ( SAMP_FREQ < 488 ) // Sets a flag if prescaler needs changing
#define SLOW 1
#endif

#define DUMMY // if defined, will output dummy data

// Gloval constants and variables
unsigned int OCRval = 0;          // OCR value for sampling freq
volatile byte TXData[PACKET_SIZE]; // bytes to be transmitted
volatile int ADC_val;     // current ADC val
volatile byte state = HIGH;
volatile byte state2 = HIGH;
volatile byte count = 3;

#ifdef DUMMY
volatile byte dummy_counter = 1;
volatile byte dummy_index = 0;
volatile int dummy_offset = 0;
volatile bool send_dummy = false;
volatile char dir = 1;
#endif


//~~~~~~~~~~
// Functions
//~~~~~~~~~~

/****************************************************/
/*  Function name: dummyRead                        */
/*  Parameters                                      */
/*    Input   :  byte i: ADC index value            */
/*    Output  :  int: dummy ADC result              */
/*    Action: Outputs a fake ADC reading simulating */
/*            an EMG pulse every 4 sec.             */
/****************************************************/
#ifdef DUMMY
int dummyRead(byte i){
  int result = 512;
  if (!dummy_counter) {
    send_dummy = true;
  }
  if (send_dummy){
    if (i == dummy_index) { result += dummy_offset; }
    dummy_offset += dir;
    if (dummy_offset == 255){
      dir = -1;
    } else if (dummy_offset == 0) {
      dir = 1;
      send_dummy = false;
      dummy_index = (++dummy_index) % 4;
    }
  }
  return result;
}
#endif

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
  OCRval = (F_CPU) / 2 / 64 / (SAMP_FREQ) - 1;
  #ifdef SLOW
  OCRval >>= 1;
  #endif
  OCRval = constrain(OCRval, 0, 255);
  

  // clear all timer2 registers
  TCCR2A = 0;
  TCCR2B = 0;
  TIMSK2 = 0;

  //set timer2 control register values
  TCCR2A |= (1<<WGM21);
  TCCR2B |= (1<<CS22);

//  TCCR2A |= (1<<COM2A1);
//  TCCR2B |= (1<<FOC2A);
//  
//  DDRB |= (1<<3);
#ifdef SLOW
  // change prescaler to 128, halve calculated OCR val
  TCCR2B |= (1<<CS20);
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
/*            every [[count+1]] samples.              */
/****************************************************/
void togglePins(){
  count--;
  if (!count){
    digitalWrite(LED_PIN, state);
    digitalWrite(CAL_SIG_PIN, state);
    digitalWrite(11, state);
    count = 15;
    state = !state;
  }
#ifdef DUMMY
  if (!(count % 4)){ ++dummy_counter; }
#endif
//  digitalWrite(11, state2);
//  state2 = !state2;
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

  Serial.begin(BAUDRATE);
  setSampleFreq(SAMP_FREQ);
  pinMode(LED_PIN, OUTPUT);
  pinMode(CAL_SIG_PIN, OUTPUT);
  pinMode(11, OUTPUT);
  analogReference(EXTERNAL);

  TXData[0] = HEADER;
  TXData[1] = HEADER;
  TXData[2] = OCRval;
  byte j = 0;
  for (j=3; j<PACKET_SIZE; j++){
    TXData[j] = 0;
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
  // Disable Timer2 interrupt
//  TIMSK2 &= ~(1<<OCIE2A);
  Serial.write(TXData[0]);
  Serial.write(TXData[1]);
  Serial.write(TXData[2]);
  Serial.write(TXData[3]);
  // Read 4 ADC channels
  byte i = 0;
  TXData[8] = 0;
  for(i=0;i<4;i++){
#ifdef DUMMY
    ADC_val = dummyRead(i);
#else
    ADC_val = analogRead(i);
#endif
    byte hiBits = (byte)(ADC_val >> 8);
    TXData[8] |= (hiBits << (2 * i));
    TXData[4 + i] = (byte)ADC_val;
    Serial.write(TXData[4 + i]);
  }
  // send high bits
  Serial.write(TXData[8]);
  // increment packet counter
  TXData[3]++;

  // Toggle LED and CAL_SIG_PIN at SAMPFREQ/8
  togglePins();
  // Enable Timer2 interrupt
//  TIMSK2 |= (1<<OCIE2A);
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



