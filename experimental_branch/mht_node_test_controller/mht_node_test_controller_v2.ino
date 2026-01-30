// mht_node_test_controller
// 2023/07/20 - Add ENABLE_24V_1 load switch control signal
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <SoftwareSerial.h>

#define V24V_1 A6
#define V24V_2 A5
#define OUT1_PDLINE A4
#define CON_PIN1 A3
#define RE_TERM A2
#define DE_TERM A1
#define V010V A0
#define MUX1 2 // Changed, check original
#define MUX2 3 // Changed, check original
#define TX 4
#define RX 5
#define AUX1 6
#define MUX3 7 // Changed from AUX2
#define ENABLE_OUTPUT1 8
#define ENABLE_24V 9
#define PUSH_4BTN_OFF 10
#define PUSH_4BTN_ON 11
#define EXTRA 12 // Changed, check original
#define ENABLE_24V_1 13 // 24V_1 load switch control signal

SoftwareSerial RS485_Serial(RX, TX); // RX, TX
#define RS485_RE_DISABLE HIGH
#define RS485_RE_ENABLE LOW
#define RS485_DE_DISABLE LOW
#define RS485_DE_ENABLE HIGH

enum{RELAYS_24V_1,RELAYS_OUTPUT1,RELAYS_OUTPUT2,RELAYS_24V_2};

uint8_t board_version_index;
uint8_t last_board_version_index;
enum{
  BOARD_DETECTED_NONE,
  BOARD_DETECTED_ND60,BOARD_DETECTED_REV3,BOARD_DETECTED_ELS3,
  BOARD_DETECTED_REV6,BOARD_DETECTED_REV7,BOARD_DETECTED_REV8
};
char * board_version_names[] = {
  "none",
  "nd60","rev3","els3",
  "rev6","rev7","rev8"
};
char board_version[8];

bool serial_command_ready = false;
char serial_command_str[64];
uint8_t serial_command_index = 0;

uint16_t value_v010v_mV = 0;

// uint16_t blink_counter; zzblink_counter def

bool mux_inputs[3] = {false,false,false};
uint8_t mux_channel = 0;

void setup(){
  initOutputs();
  initRS485();
  initADC();
  Serial.begin(115200);
  Serial.println("Starting mht_node_test_controller");
  last_board_version_index = 0xFF; // initialize to force state change and print after first detectBoardVersion()
  //demoRelays();
  //demoAux();
  setRelays(RELAYS_OUTPUT2);
}

void loop() {
  // detectBoardVersion();
  
  // if(board_version_index == BOARD_DETECTED_NONE){ //zzdetectBoardVersion condition 
  //   blink();
  // }
  if(serial_command_ready){
    serial_command_ready = false; // clear flag
    processSerialCommand(); // process command
    serial_command_str[0] = 0; // clear command
  }
  if(RS485_Serial.available()){
    RS485SerialEvent();
  }

}

void serialEvent(){
  while(!serial_command_ready && Serial.available()){
    char c = Serial.read();
    //Serial.print(c); // echo
    if(c=='\r'){
      serial_command_ready = true;
      serial_command_str[serial_command_index] = 0; // null terminate string
      serial_command_index = 0; // reset index
      Serial.print("\r\n"); // echo
    }
    else if (c>10 and c<127){
      serial_command_str[serial_command_index++] = c;
      Serial.print(c); // echo
    }
  }
}

void RS485SerialEvent(void){
  while(RS485_Serial.available()){
    char c = RS485_Serial.read();
    if(c=='\r'){
      Serial.print("\r\n"); // echo
    }
    else if (c>10 and c<127){
      Serial.print(c); // echo
    }
  }
}

void processSerialCommand(void){
  uint8_t i = 0;
  char * tok;
  char delim[] = " ";
  char str_cpy[64];
  char str_msg[64];
  strcpy(str_cpy,serial_command_str); // make a copy to parse
  //Serial.print("processSerialCommand: ");
  //Serial.println(str_cpy);
  tok = strtok(str_cpy,delim);
  if(tok==NULL){
    return;
  }
  if(strcmp(tok,"set_relays")==0){
    tok = strtok(NULL,delim);
    if(tok==NULL){
    }
    else if(strcmp(tok,"output1")==0){
      setRelays(RELAYS_OUTPUT1);
    }
    else if(strcmp(tok,"output2")==0){
      setRelays(RELAYS_OUTPUT2);
    }
    // vvv NO LONGER BEING USED vvv
    // else if(strcmp(tok,"24V")==0){
    //   setRelays(RELAYS_24V_1);
    // }
    // else if(strcmp(tok,"24V_1")==0){
    //   setRelays(RELAYS_24V_1);
    // }
    // else if(strcmp(tok,"24V_2")==0){
    //   setRelays(RELAYS_24V_2);
    // }
  }
  else if(strcmp(tok,"set_aux1")==0){
    tok = strtok(NULL,delim);
    if(tok==NULL){
    }
    else if(strcmp(tok,"true")==0){
      setAux1(true);
    }
    else if(strcmp(tok,"false")==0){
      setAux1(false);
    }
  }
  // else if(strcmp(tok,"set_aux2")==0){ // zzaux2
  //   tok = strtok(NULL,delim);
  //   if(tok==NULL){
  //   }
  //   else if(strcmp(tok,"true")==0){
  //     setAux2(true);
  //   }
  //   else if(strcmp(tok,"false")==0){
  //     setAux2(false);
  //   }
  // }
  // else if(strcmp(tok,"set_load_led")==0){ zzled
  //   tok = strtok(NULL,delim);
  //   if(tok==NULL){
  //   }
  //   else if(strcmp(tok,"on")==0){
  //     setLEDLoadOn(true);
  //   }
  //   else if(strcmp(tok,"off")==0){
  //     setLEDLoadOn(false);
  //   }
  // }
  else if(strcmp(tok,"set_push_4BTN_On")==0){
    setPush4BTNOn(true);
    delay(300);
    setPush4BTNOn(false);
  }
  else if(strcmp(tok,"set_push_4BTN_Off")==0){
    setPush4BTNOff(true);
    delay(300);
    setPush4BTNOff(false);
  }
  else if(strcmp(tok,"get_board_version")==0){
    printBoardVersion();
  }
  else if(strcmp(tok,"get_0-10V")==0){
    measureV010V();
    printV010V();
  }
  else if(strcmp(tok,"write_console")==0){
    for(i=14; i<strlen(serial_command_str); i++){
      str_msg[i-14] = serial_command_str[i];
    }
    str_msg[i-14] = 0; // null terminate string
    writeConsole(str_msg);
  }
  else if(strcmp(tok,"write_console_read_com")==0){
    for(i=23; i<strlen(serial_command_str); i++){
      str_msg[i-23] = serial_command_str[i];
    }
    str_msg[i-23] = 0; // null terminate string
    writeConsoleReadCOM(str_msg);
  }
  // else if(strcmp(tok,"write_com_read_console")==0){ // zzcom
  //   for(i=23; i<strlen(serial_command_str); i++){
  //     str_msg[i-23] = serial_command_str[i];
  //   }
  //   str_msg[i-23] = 0; // null terminate string
  //   writeCOMReadConsole(str_msg);
  // }
  else if(strcmp(tok,"read_console")==0){
    setRS485TERMRead();
  }
  else if (strcmp(tok, "set_mux") == 0) {
    tok = strtok(NULL, delim);
    if (tok != NULL) {
        int channel = atoi(tok);  // Convert string to integer
        if (channel > -1 && channel <= 8) {  // Ensure the channel is within the valid range
            setMuxChannel(channel);
        }
    }
}

  else if (strcmp(tok, "get_mux_channel") == 0) {
    getMuxChannel();
  }
  else if(strcmp(tok,"set_mux")==0){
    tok = strtok(NULL,delim);
    if(tok==NULL){
    }
    else if(strcmp(tok,"0")==0){
      setMux1(false);
      setMux2(false);
      setMux3(false);
    }
    else if(strcmp(tok,"1")==0){
      setMux1(true);
      setMux2(false);
      setMux3(false);    }
    else if(strcmp(tok,"2")==0){
      setMux1(false);
      setMux2(true);
      setMux3(false);    }
    else if(strcmp(tok,"3")==0){
      setMux1(true);
      setMux2(true);
      setMux3(false);    }
    else if(strcmp(tok,"4")==0){
      setMux1(false);
      setMux2(false);
      setMux3(true);    }
    else if(strcmp(tok,"5")==0){
      setMux1(true);
      setMux2(false);
      setMux3(true);    }
    else if(strcmp(tok,"6")==0){
      setMux1(false);
      setMux2(true);
      setMux3(true);    }
    else if(strcmp(tok,"7")==0){
      setMux1(true);
      setMux2(true);
      setMux3(true);    }
  }
  else{
    Serial.print("Unknown command: ");
    Serial.println(serial_command_str);
  }
}

void measureV010V(void){
  analogReference(INTERNAL); // 1.1V
  value_v010v_mV = analogRead(V010V) / 10 * 118;
}

void printV010V(void){
  char msg[64];
  sprintf(msg,"%u.%03u",value_v010v_mV/1000,value_v010v_mV-value_v010v_mV/1000*1000);
  Serial.println(msg);
}

// void demoRelays(void){ //Might be zz
//   oneBlink();
//   setRelays(RELAYS_OUTPUT1);
//   oneBlink();
//   setRelays(RELAYS_OUTPUT2);
//   oneBlink();
//   setRelays(RELAYS_24V_1);
//   oneBlink();
//   setRelays(RELAYS_24V_2);
// }

// void demoAux(void){ // zzdemoaux
//   oneBlink();
//   setAux1(true);
//   setAux2(false); zzdemoaux
//   oneBlink();
//   setAux1(false);
//   setAux2(true);
//   oneBlink();
//   setAux1(false);
//   setAux2(false); // zzdemoaux
// }

// void oneBlink(void){ zzblink
//   uint16_t i = 0;
//   blink_counter = 0; // reset counter
//   while(i++<1001){
//     blink();
//   }
// }

// void blink(void){ // zzled zzblink
//   if(blink_counter++==500){
//     setLEDLoadOn(true);
//   }
//   else if(blink_counter>=1000){
//     setLEDLoadOn(false);
//     blink_counter = 0;
//   }
//   delay(1);
// }

void printBoardVersion(void){
  Serial.println(board_version);
}

void detectBoardVersion(void){
  if(analogRead(V24V_1)<10){ // None: V24V_1 low
    board_version_index = BOARD_DETECTED_NONE;
  }
  else if(analogRead(V24V_2)<50){ // nd60: V24V_2 low
    board_version_index = BOARD_DETECTED_ND60;
  }
  else if(analogRead(CON_PIN1)<50){ // rev6: Console Pin1 low, not 14V
    board_version_index = BOARD_DETECTED_REV6; // confirm if this is also true for rev7 and rev8
  }
  else if(detectOut1PDLINE()){ // rev3: Ouput1 Pin4 is PDLINE high, greater than 5V (ADC_VALUE 438)
    board_version_index = BOARD_DETECTED_REV3;
  }
  else{ // els: otherwise
    board_version_index = BOARD_DETECTED_ELS3;
  }
  sprintf(board_version,"%s",board_version_names[board_version_index]);
  if(last_board_version_index != board_version_index){
    printBoardVersion();
    // setLEDLoadOn(false); zzled
  }
  last_board_version_index = board_version_index;
}

bool detectOut1PDLINE(void){
  uint8_t i;
  for(i=0; i<20; i++){
    if(analogRead(OUT1_PDLINE)>500){
      return true;
    }
  }
  return false;
}

void initADC(void){
  analogReference(INTERNAL); // 1.1V
}

void initOutputs(void){

  pinMode(MUX1,OUTPUT);
  setMux1(false);
  
  pinMode(MUX2,OUTPUT);
  setMux2(false);
  
  pinMode(MUX3,OUTPUT);
  setMux3(false);

  // pinMode(LED_LOAD_ON,OUTPUT); // zzled
  // setLEDLoadOn(false); 
  pinMode(PUSH_4BTN_ON,OUTPUT);
  setPush4BTNOn(false);
  pinMode(PUSH_4BTN_OFF,OUTPUT);
  setPush4BTNOff(false);
  pinMode(ENABLE_24V,OUTPUT);
  setEnable24V(true);
  pinMode(ENABLE_OUTPUT1,OUTPUT);
  setEnableOutput1(true);
  pinMode(AUX1,OUTPUT);
  setAux1(false);
  // pinMode(AUX2,OUTPUT); zzaux2
  // setAux2(false);
  pinMode(ENABLE_24V_1,OUTPUT);
  setEnable24V_1(false);
}

// MUX state setters
void setMux1(bool enable){
  digitalWrite(MUX1,(enable)?(HIGH):(LOW));
}

void setMux2(bool enable){
  digitalWrite(MUX2,(enable)?(HIGH):(LOW));
}

void setMux3(bool enable){
  digitalWrite(MUX3,(enable)?(HIGH):(LOW));
}

// void setLEDLoadOn(bool enable){ //zzload
//   digitalWrite(LED_LOAD_ON,(enable)?(HIGH):(LOW));
// }

void setPush4BTNOn(bool enable){
  digitalWrite(PUSH_4BTN_ON,(enable)?(HIGH):(LOW));
}

void setPush4BTNOff(bool enable){
  digitalWrite(PUSH_4BTN_OFF,(enable)?(HIGH):(LOW));
}

void setEnable24V(bool enable){
  digitalWrite(ENABLE_24V,(enable)?(HIGH):(LOW));
}

void setEnable24V_1(bool enable){
  digitalWrite(ENABLE_24V_1,(enable)?(HIGH):(LOW));
}

void setEnableOutput1(bool enable){
  digitalWrite(ENABLE_OUTPUT1,(enable)?(HIGH):(LOW));
}

void setAux1(bool enable){
  digitalWrite(AUX1,(enable)?(HIGH):(LOW));
}

// void setAux2(bool enable){ zzaux2
//   digitalWrite(AUX2,(enable)?(HIGH):(LOW));
// }

void setRelays(uint8_t mode){
  switch(mode){
    case RELAYS_OUTPUT1:
      setEnable24V_1(false);
      setEnable24V(false);
      setEnableOutput1(true);
      break;
    case RELAYS_OUTPUT2:
      setEnable24V_1(false);
      setEnable24V(false);
      setEnableOutput1(false);
      break;
    case RELAYS_24V_2:
      setEnable24V_1(false);
      setEnable24V(true);
      setEnableOutput1(true);
      break;
    default:
      setEnable24V_1(true);
      setEnable24V(true);
      setEnableOutput1(true);
      break;
  }
}

void initRS485(void){
  pinMode(RE_TERM,OUTPUT);
  pinMode(DE_TERM,OUTPUT);
  // pinMode(RE_COM,OUTPUT); // zzcom
  // pinMode(DE_COM,OUTPUT); // zzcom
  setRS485TERMOff();
  // setRS485COMOff(); //zzcom
  RS485_Serial.begin(115200);
  RS485_Serial.setTimeout(250);
  setRS485TERMRead();
}

void setRS485TERMOff(void){
  digitalWrite(RE_TERM,RS485_RE_DISABLE);
  digitalWrite(DE_TERM,RS485_DE_DISABLE);
}
void setRS485TERMRead(void){
  // setRS485COMOff(); // zzcom
  digitalWrite(RE_TERM,RS485_RE_ENABLE);
  digitalWrite(DE_TERM,RS485_DE_DISABLE);
}
void setRS485TERMWrite(void){
  // setRS485COMOff(); // zzcom
  digitalWrite(RE_TERM,RS485_RE_DISABLE);
  digitalWrite(DE_TERM,RS485_DE_ENABLE);
}
void setRS485TERMWriteAndRead(void){
  // setRS485COMOff();
  digitalWrite(RE_TERM,RS485_RE_ENABLE);
  digitalWrite(DE_TERM,RS485_DE_ENABLE);
}
void setRS485TERMWriteAndCOMRead(void){
  // setRS485COMOff(); // zzcom
  setRS485TERMOff();
  // digitalWrite(RE_COM,RS485_RE_ENABLE); // zzcom
  digitalWrite(DE_TERM,RS485_DE_ENABLE);
}

// void setRS485COMOff(void){ // zzcom all
//   digitalWrite(RE_COM,RS485_RE_DISABLE);
//   digitalWrite(DE_COM,RS485_DE_DISABLE);
// }
// void setRS485COMRead(void){
//   setRS485TERMOff();
//   digitalWrite(RE_COM,RS485_RE_ENABLE);
//   digitalWrite(DE_COM,RS485_DE_DISABLE);
// }
// void setRS485COMWrite(void){
//   setRS485TERMOff();
//   digitalWrite(RE_COM,RS485_RE_DISABLE);
//   digitalWrite(DE_COM,RS485_DE_ENABLE);
// }
// void setRS485COMWriteAndTERMRead(void){
//   setRS485COMOff();
//   setRS485TERMOff();
//   digitalWrite(RE_TERM,RS485_RE_ENABLE);
//   digitalWrite(DE_COM,RS485_DE_ENABLE);
// }

void readLineConsole(char * msg){
  uint8_t i = 0;
  uint8_t timeout = 0;
  char c;
  while(c!='\r'){
    c = RS485_Serial.read();
    if(c==-1){
      delay(1);
      if(timeout++>250){
        break;
      }
    }
    else if(c>10 && c<127){
      msg[i++] = c;
    }
  }
  msg[i] = 0; // null terminate
}

void sendCommandConsole(char * msg){
  char read_str[64];
  RS485_Serial.print('\x03'); // ctrl+c
  //readLineConsole(read_str);
  //Serial.println(read_str);
  //readLineConsole(read_str);
  //Serial.println(read_str);
  delay(100);
  uint8_t i;
  for(i=0; i<strlen(msg); i++){
    delay(50);
    RS485_Serial.print(msg[i]);
    Serial.print(msg[i]);
  }
  delay(100);
  RS485_Serial.print('\r');
  Serial.print('\r');
  //delay(100);
  RS485_Serial.print('\n');
  Serial.print('\n');
}

void sendCommandCOM(char * msg){
  uint8_t i;
  for(i=0; i<strlen(msg); i++){
    delay(50);
    RS485_Serial.print(msg[i]);
    Serial.print(msg[i]);
  }
  delay(100);
  RS485_Serial.print('\r');
  Serial.print('\r');
  //delay(100);
  RS485_Serial.print('\n');
  Serial.print('\n');
}

void writeConsole(char * msg){
  setRS485TERMWriteAndRead();
  delay(10);
  sendCommandConsole(msg);
  setRS485TERMRead();
}

void writeConsoleReadCOM(char * msg){
  setRS485TERMWriteAndCOMRead();
  delay(10);
  sendCommandConsole(msg);
  // setRS485COMRead(); zzcom
}

// void writeCOMReadConsole(char * msg){ // zzcom
//   setRS485COMWriteAndTERMRead();
//   delay(10);
//   sendCommandCOM(msg);
//   setRS485TERMRead();
// }

void printMuxChannel(){
    Serial.println("Mux channel is set to " + String(mux_channel));
}

void getMuxChannel(){
  mux_channel = 0;
  uint8_t channel_inputs[] = {0,0,0};
  // for(int i = 0;i<=2;i++){
  //   if (mux_inputs[i] == true){
  //     channel_inputs[i] = 1;
  //   }
  //   mux_channel += channel_inputs[i]*(2^i);
  // }
  mux_channel = digitalRead(MUX1) + digitalRead(MUX2)*2 + digitalRead(MUX3)*4;
  //Serial.println("Mux channel is set to " + String(mux_channel));
  printMuxChannel();
}

void setMuxChannel(uint8_t channel){
  // Look into masking
  // Loop through each bit (3 bits for values from 0 to 7)
  for (int i = 2; i >= 0; i--) {
    // Check if the bit at position i is 1 or 0
    bool bit = (channel >> i) & 1;
    mux_inputs[i] = bit;
  setMux1(mux_inputs[0]);
  setMux2(mux_inputs[1]);
  setMux3(mux_inputs[2]);
  }
}

