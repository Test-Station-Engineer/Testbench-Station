// mht_node_test_controller

#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <SoftwareSerial.h>

#define V24V_1 A6 // Unsure if used for anything ngl, check this on the wiring diagram
#define ENABLE_CONT 2 // Enable Continuous Output (HIGH is default actuator, LOW is pwm channels of core node)
#define ENABLE_IN 3 // Changed, check original
#define ADDR0 4 // TODO Close to implemented, just replace legacy MUX and mux funcs with this
#define ADDR1 5 // TODO Close to implemented, just replace legacy MUX and mux funcs with this
#define ADDR2 6 // TODO Close to implemented, just replace legacy MUX and mux funcs with this
#define AUX1 7 // For sensor testing things that aren't Supernode
#define ENABLE_OUTPUT1 8 // Probably doesn't need any changes, obviously verify though. For Ch1 and Ch2 of Node90
#define ENABLE_24V 9 // Probably done? Test and verify
#define PUSH_4BTN_OFF 10
#define PUSH_4BTN_ON 11
#define LED_LOAD_ON 12 // TODO Write (not as urgent)

// SoftwareSerial RS485_Serial(RX, TX); // RX, TX
// #define RS485_RE_DISABLE HIGH
// #define RS485_RE_ENABLE LOW
// #define RS485_DE_DISABLE LOW
// #define RS485_DE_ENABLE HIGH

enum{RELAYS_OUTPUT1,RELAYS_OUTPUT2};

bool serial_command_ready = false;
char serial_command_str[64];
uint8_t serial_command_index = 0;

// uint16_t value_v010v_mV = 0;   // Used in measuring the 0-10V port, unsure if needed anymore

bool addr_inputs[3] = {false,false,false};
uint8_t mux_channel = 0;

void setup(){
  initOutputs();
  // initRS485();
  // initADC();      // Used in measuring the 0-10V port, unsure if needed anymore
  Serial.begin(115200);
  Serial.println("Starting mht_node_test_controller");

  setRelays(RELAYS_OUTPUT2);
}

void loop() {

  if(serial_command_ready){
    serial_command_ready = false; // clear flag
    processSerialCommand(); // process command
    serial_command_str[0] = 0; // clear command
  }
  // if(RS485_Serial.available()){
  //   RS485SerialEvent();
  // }

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

// void RS485SerialEvent(void){
//   while(RS485_Serial.available()){
//     char c = RS485_Serial.read();
//     if(c=='\r'){
//       Serial.print("\r\n"); // echo
//     }
//     else if (c>10 and c<127){
//       Serial.print(c); // echo
//     }
//   }
// }

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
  // TODO REIMPLEMENT PERHAPS:
  // There were other methods that were used in the very first version of this.
  // Things such as blink and oneBlink, of which were used in methods "demoRelays" and "demoAux"
  // Consider investigating further if you want to bring them back, not urgent atm.
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

  // Added for my own testing purposes on serial monitor, not needed rn
  // else if(strcmp(tok,"set_red_led")==0){
  //   tok = strtok(NULL,delim);
  //   if(tok==NULL){
  //   }
  //   else if(strcmp(tok,"on")==0){
  //     setEnable24V(true);
  //   }
  //   else if(strcmp(tok,"off")==0){
  //     setEnable24V(false);
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
  // else if(strcmp(tok,"get_0-10V")==0){
  //   measureV010V();
  //   printV010V();
  // }
  // else if(strcmp(tok,"write_console")==0){
  //   for(i=14; i<strlen(serial_command_str); i++){
  //     str_msg[i-14] = serial_command_str[i];
  //   }
  //   str_msg[i-14] = 0; // null terminate string
  //   writeConsole(str_msg);
  // }
  // else if(strcmp(tok,"write_console_read_com")==0){
  //   for(i=23; i<strlen(serial_command_str); i++){
  //     str_msg[i-23] = serial_command_str[i];
  //   }
  //   str_msg[i-23] = 0; // null terminate string
  //   writeConsoleReadCOM(str_msg);
  // }
  // else if(strcmp(tok,"write_com_read_console")==0){ // zzcom
  //   for(i=23; i<strlen(serial_command_str); i++){
  //     str_msg[i-23] = serial_command_str[i];
  //   }
  //   str_msg[i-23] = 0; // null terminate string
  //   writeCOMReadConsole(str_msg);
  // }
  // else if(strcmp(tok,"read_console")==0){
  //   setRS485TERMRead();
  // }

  // else if (strcmp(tok, "set_mux") == 0) { // Objectively better than the below system, not sure if it works though
  //   tok = strtok(NULL, delim);
  //   if (tok != NULL) {
  //       int channel = atoi(tok);  // Convert string to integer
  //       if (channel > -1 && channel <= 7) {  // Ensure the channel is within the valid range
  //           setMuxChannel(channel);
  //       }
  //   }
  // }

  else if (strcmp(tok, "get_mux_channel") == 0) {
    getMuxChannel();
  }
  // set_cont_output [true/false]
  // true  = continuous output test (ENABLE_CONT HIGH, ADDR2 HIGH keeps PWM lines off LOAD-)
  // false = PWM test (ENABLE_CONT LOW, ADDR2 LOW), then pick channel with set_pwm
  else if(strcmp(tok,"set_cont_output")==0){
    tok = strtok(NULL,delim);
    if(tok==NULL){
    }
    else if(strcmp(tok,"true")==0){
      setContOutput(true);
    }
    else if(strcmp(tok,"false")==0){
      setContOutput(false);
    }
  }
  // set_pwm [0/1/2/3] -> sets ADDR1:ADDR0 to 00..11 (PWM1..PWM4)
  else if(strcmp(tok,"set_pwm")==0){
    tok = strtok(NULL,delim);
    if(tok==NULL){
    }
    else if(strcmp(tok,"0")==0 || strcmp(tok,"1")==0 || strcmp(tok,"2")==0 || strcmp(tok,"3")==0){
      setPwmChannel(atoi(tok));
    }
  }
  else if(strcmp(tok,"set_enable_in")==0){
    tok = strtok(NULL,delim);
    if(tok==NULL){
    }
    else if(strcmp(tok,"true")==0){
      setEnableIn(true);
    }
    else if(strcmp(tok,"false")==0){
      setEnableIn(false);
    }
  }

  else if(strcmp(tok,"set_mux")==0){
    setAux1(true);
    tok = strtok(NULL,delim);
    if(tok==NULL){
    }
    else if(strcmp(tok,"0")==0){
      setAddr0(false);
      setAddr1(false);
      setAddr2(false);
    }
    else if(strcmp(tok,"1")==0){
      setAddr0(true);
      setAddr1(false);
      setAddr2(false);    }
    else if(strcmp(tok,"2")==0){
      setAddr0(false);
      setAddr1(true);
      setAddr2(false);    }
    else if(strcmp(tok,"3")==0){
      setAddr0(true);
      setAddr1(true);
      setAddr2(false);    }
    else if(strcmp(tok,"4")==0){
      setAddr0(false);
      setAddr1(false);
      setAddr2(true);    }
    else if(strcmp(tok,"5")==0){
      setAddr0(true);
      setAddr1(false);
      setAddr2(true);    }
    else if(strcmp(tok,"6")==0){
      setAddr0(false);
      setAddr1(true);
      setAddr2(true);    }
    else if(strcmp(tok,"7")==0){
      setAddr0(true);
      setAddr1(true);
      setAddr2(true);    }
  }

  else{
    Serial.print("Unknown command: ");
    Serial.println(serial_command_str);
  }
}

// Measuring 0-10V Port. Obsolete, using a power meter instead now
// void measureV010V(void){
//   analogReference(INTERNAL); // 1.1V
//   value_v010v_mV = analogRead(V010V) / 10 * 118;
// }
// void printV010V(void){
//   char msg[64];
//   sprintf(msg,"%u.%03u",value_v010v_mV/1000,value_v010v_mV-value_v010v_mV/1000*1000);
//   Serial.println(msg);
// }

// void initADC(void){
//   analogReference(INTERNAL); // 1.1V
// }

void initOutputs(void){

  pinMode(ADDR0,OUTPUT);
  setAddr0(false);
  
  pinMode(ADDR1,OUTPUT);
  setAddr1(false);
  
  pinMode(ADDR2,OUTPUT);
  setAddr2(false);

  pinMode(ENABLE_CONT,OUTPUT);
  setEnableCont(false);

  pinMode(ENABLE_IN,OUTPUT);
  setEnableIn(false);

  pinMode(LED_LOAD_ON,OUTPUT);
  setLEDLoadOn(false); 
  pinMode(PUSH_4BTN_ON,OUTPUT);
  setPush4BTNOn(false);
  pinMode(PUSH_4BTN_OFF,OUTPUT);
  setPush4BTNOff(false);
  pinMode(ENABLE_24V,OUTPUT);
  setEnable24V(false);
  setEnable24V(true);
  pinMode(ENABLE_OUTPUT1,OUTPUT);
  setEnableOutput1(true);
  pinMode(AUX1,OUTPUT);
  setAux1(false);
}

// Addr state setters
void setAddr0(bool enable){
  digitalWrite(ADDR0,(enable)?(HIGH):(LOW));
}

void setAddr1(bool enable){
  digitalWrite(ADDR1,(enable)?(HIGH):(LOW));
}

void setAddr2(bool enable){
  digitalWrite(ADDR2,(enable)?(HIGH):(LOW));
}

void setEnableCont(bool enable){
  digitalWrite(ENABLE_CONT,(enable)?(HIGH):(LOW));
}
void setEnableIn(bool enable){
  digitalWrite(ENABLE_IN,(enable)?(HIGH):(LOW));
}

// Continuous output vs PWM test on Core Node.
// Drives ENABLE_CONT and ADDR2 together (both HIGH or both LOW).
void setContOutput(bool enable){
  setEnableCont(enable);
  addr_inputs[2] = enable;
  setAddr2(enable);
}

// Selects 1 of 4 Core Node PWM channels via ADDR1:ADDR0 (0 = 00 ... 3 = 11).
// Use with setContOutput(false). Does not touch ADDR2.
void setPwmChannel(uint8_t channel){
  if(channel > 3){
    return;
  }
  addr_inputs[0] = channel & 0x01;
  addr_inputs[1] = (channel >> 1) & 0x01;
  setAddr0(addr_inputs[0]);
  setAddr1(addr_inputs[1]);
}

void setLEDLoadOn(bool enable){
  digitalWrite(LED_LOAD_ON,(enable)?(HIGH):(LOW));
}

void setPush4BTNOn(bool enable){
  digitalWrite(PUSH_4BTN_ON,(enable)?(HIGH):(LOW));
}

void setPush4BTNOff(bool enable){
  digitalWrite(PUSH_4BTN_OFF,(enable)?(HIGH):(LOW));
}

void setEnable24V(bool enable){
  digitalWrite(ENABLE_24V,(enable)?(HIGH):(LOW));
}

void setEnableOutput1(bool enable){
  digitalWrite(ENABLE_OUTPUT1,(enable)?(HIGH):(LOW));
}

void setAux1(bool enable){
  digitalWrite(AUX1,(enable)?(HIGH):(LOW));
}

void setRelays(uint8_t mode){
  switch(mode){
    case RELAYS_OUTPUT1:
      setEnable24V(false);
      setEnableOutput1(true);
      break;
    case RELAYS_OUTPUT2:
      setEnable24V(false);
      setEnableOutput1(false);
      break;
    default:
      setEnable24V(true);
      setEnableOutput1(true);
      break;
  }
}

// void initRS485(void){
//   pinMode(RE_TERM,OUTPUT);
//   pinMode(DE_TERM,OUTPUT);
//   pinMode(RE_COM,OUTPUT);
//   pinMode(DE_COM,OUTPUT); 
//   setRS485TERMOff();
//   setRS485COMOff(); 
//   RS485_Serial.begin(115200);
//   RS485_Serial.setTimeout(250);
//   setRS485TERMRead();
// }

// void setRS485TERMOff(void){
//   digitalWrite(RE_TERM,RS485_RE_DISABLE);
//   digitalWrite(DE_TERM,RS485_DE_DISABLE);
// }
// void setRS485TERMRead(void){
//   setRS485COMOff();
//   digitalWrite(RE_TERM,RS485_RE_ENABLE);
//   digitalWrite(DE_TERM,RS485_DE_DISABLE);
// }
// void setRS485TERMWrite(void){
//   setRS485COMOff(); 
//   digitalWrite(RE_TERM,RS485_RE_DISABLE);
//   digitalWrite(DE_TERM,RS485_DE_ENABLE);
// }
// void setRS485TERMWriteAndRead(void){
//   setRS485COMOff();
//   digitalWrite(RE_TERM,RS485_RE_ENABLE);
//   digitalWrite(DE_TERM,RS485_DE_ENABLE);
// }
// void setRS485TERMWriteAndCOMRead(void){
//   setRS485COMOff(); 
//   setRS485TERMOff();
//   digitalWrite(RE_COM,RS485_RE_ENABLE); 
//   digitalWrite(DE_TERM,RS485_DE_ENABLE);
// }

// void setRS485COMOff(void){ 
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

// void readLineConsole(char * msg){
//   uint8_t i = 0;
//   uint8_t timeout = 0;
//   char c;
//   while(c!='\r'){
//     c = RS485_Serial.read();
//     if(c==-1){
//       delay(1);
//       if(timeout++>250){
//         break;
//       }
//     }
//     else if(c>10 && c<127){
//       msg[i++] = c;
//     }
//   }
//   msg[i] = 0; // null terminate
// }

// void sendCommandConsole(char * msg){
//   char read_str[64];
//   RS485_Serial.print('\x03'); // ctrl+c
//   //readLineConsole(read_str);
//   //Serial.println(read_str);
//   //readLineConsole(read_str);
//   //Serial.println(read_str);
//   delay(100);
//   uint8_t i;
//   for(i=0; i<strlen(msg); i++){
//     delay(50);
//     RS485_Serial.print(msg[i]);
//     Serial.print(msg[i]);
//   }
//   delay(100);
//   RS485_Serial.print('\r');
//   Serial.print('\r');
//   //delay(100);
//   RS485_Serial.print('\n');
//   Serial.print('\n');
// }

// void sendCommandCOM(char * msg){
//   uint8_t i;
//   for(i=0; i<strlen(msg); i++){
//     delay(50);
//     RS485_Serial.print(msg[i]);
//     Serial.print(msg[i]);
//   }
//   delay(100);
//   RS485_Serial.print('\r');
//   Serial.print('\r');
//   //delay(100);
//   RS485_Serial.print('\n');
//   Serial.print('\n');
// }

// void writeConsole(char * msg){
//   setRS485TERMWriteAndRead();
//   delay(10);
//   sendCommandConsole(msg);
//   setRS485TERMRead();
// }

// void writeConsoleReadCOM(char * msg){
//   setRS485TERMWriteAndCOMRead();
//   delay(10);
//   sendCommandConsole(msg);
//   // setRS485COMRead(); zzcom
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
  mux_channel = digitalRead(ADDR0) + digitalRead(ADDR1)*2 + digitalRead(ADDR2)*4;
  //Serial.println("Mux channel is set to " + String(mux_channel));
  printMuxChannel();
}

void setMuxChannel(uint8_t channel){
  // Look into masking
  // Loop through each bit (3 bits for values from 0 to 7)
  for (int i = 2; i >= 0; i--) {
    // Check if the bit at position i is 1 or 0
    bool bit = (channel >> i) & 1;
    addr_inputs[i] = bit;
  setAddr0(addr_inputs[0]);
  setAddr1(addr_inputs[1]);
  setAddr2(addr_inputs[2]);
  }
}

