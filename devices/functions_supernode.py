import load
import controller
import coap_client
import time

import random # only used once

from devices import functions_misc as misc

key = misc.key
ip: str = ''
test_json = ''

dc_in_mode: bool = False

def init(ip_address, test_configuration):
    global ip, test_json
    ip = ip_address
    test_json = test_configuration

    for i in range(1,9): coap_client.secure_setting(ip,f'/actuators/actuator{i}','fadetime',0)


def test_cccv(cccv,channel = 0):
    
    print("Setting cccv to",cccv,"on channel",channel)
    coap_client.setCCCV(ip,channel,cccv)
    time.sleep(8.0)

    if channel == 0:
        for i in range(1,8):
            setting = int(coap_client.getValue(ip,f'/actuators/actuator{i}','cccv'))
            if setting != cccv:
                misc.updateLog('testCCCV',f'fail actuator{i}',setting)
                return False
    else:
        setting = int(coap_client.getValue(ip,f'/actuators/actuator{channel}','cccv'))
        if setting != cccv:
            misc.updateLog('testCCCV',f'fail actuator{channel}',setting)
            return False
    return True

def test_max_watt(maxw, channel = 0):
    
    print("Setting cccv to",maxw,"on channel",channel)
    coap_client.setMaxWatt(ip,channel,maxw)

    time.sleep(3.0)
    
    for i in range(1,8):
        setting = coap_client.getMaxWatt(ip,i)
        if setting != maxw: 
            print("Max Watt failed to assign on channel:",i)
            return False
        
    return True

def set_mux(channel: int, verbose: bool = True, delay:float = 0.25):
    # If you want to improve the odds of it finding the mux, give it more time to read it in controller.py

    controller.setMux(channel-1)

    if verbose: print("Setting Mux to output on channel", channel)
    if delay: time.sleep(delay)
    #print("Mux channel",relay,"is",controller.getMux())
    current_mux = controller.getMux
    count: int = -1
    while current_mux != channel-1:
        current_mux = controller.getMux()
        if count == 50 or -1:
            if verbose: print("Attempting to retrieve mux")
            count = 0
        #print("MUX WAS NOT SET PROPERLY FOR CHANNEL",channel,"- CURRENT MUX IS",current_mux)
        count+=1
        time.sleep(delay)

def load_test(test_load):
    "This is the load test procedure for the mini node"

    def power_check(turn_off_load_after: bool = True):
        """Measures power once, then if it is below expected, it will wait and measure again.
        \nIf it's still inadequate, it will pause and await user input.
        \nIf still inadequate, it will fail and turn load machine off, if input var is true."""

        power = load.measurePower()

        # If power measured is less than required, wait, then measure again. Then await the user to measure a third time
        if power < test_load['power']: 
            print("Failed initial power test at",power,"watts. Awaiting new measurement.")
            time.sleep(3.0)
            power = load.measurePower()
            if power < test_load['power']:
                misc.send_test_prompt(key,f"TEST STATION PAUSED. PRESS {key} TO CONTINUE.","CONTINUING TEST.")
                power = load.measurePower()

            # Sets load output off
            if turn_off_load_after: load.setOutputOn(False)

            # if power is less than required, fail it. Else, pass it
            if power < test_load['power']:
                misc.updateLog('testLoad',relay,'fail power',power)
                return False
            else: 
                misc.updateLog('testLoad',relay,'pass power',power)
                return True
        misc.updateLog('testLoad',relay,'pass power',power)
        if turn_off_load_after: load.setOutputOn(False)
        return True
    ################################################################

    dim: int = 100
    if 'dim' in test_load: dim = test_load['dim']

    time.sleep(0.5)
                
    if ('CR' in test_load or 'CC' in test_load or 'CV' in test_load) and 'power' in test_load:

        relays = [1,2,3,4,5,6,7,8]

        #print(relays)

        for relay in relays:

            # This is exclusively for checking the change in the 0-10V port.
            coap_client.setDim(ip,9,10*relay)

            dc_in_load_multiplier = 1.0 
            if dc_in_mode: 
                dc_in_load_multiplier = 0.9
                relay = random.randint(1,8) # If DC in test, we only test 1 random relay, so disregard for loop in this case.
                # cccv = random.randint(0,4)
                if "cccv" in test_load: test_cccv(test_load['cccv'],relay)
                if "maxw" in test_load: test_max_watt(test_load['maxw'])

            if 'CR' in test_load: load.setResistance(test_load['CR'] * dc_in_load_multiplier)
            if 'CV' in test_load: load.setVoltage(test_load['CV'] * dc_in_load_multiplier)
            if 'CC' in test_load: load.setCurrent(test_load['CC'] * dc_in_load_multiplier)

            coap_client.secure_setting(ip,f'/sensors/input{relay}','sentype','INPUT_LH_OR_HL') # Change sensor 1 events supernode version
            coap_client.secure_setting(ip,'/sensors/input'+str(relay),'eventlh',f"F0,{relay},{dim}")
            coap_client.secure_setting(ip,'/sensors/input'+str(relay),'eventhl',f"F0,{relay},0") # Change sensor 1 events supernode version                    

            if coap_client.getDim(ip,relay) != 0 and relay != 1: # Current channel should be 0 dim since it hasn't been set yet
                print("Policy eventhl is not working properly for channel",relay)

            # These 2 if statements are meant to invoke a change in dim from switching inputs on either end of the inputs 
            if relay == 1:
                set_mux(8,False)
                time.sleep(0.5)
            elif relay == 8 and dc_in_mode:
                set_mux(1,False)
                time.sleep(0.5)

            set_mux(relay)
            time.sleep(0.5)

            # Check to see that eventhl policy is working
            current_channel_dim = coap_client.getDim(ip,relay)
            if relay != 1: 
                previous_channel_dim = coap_client.getDim(ip,relay-1)
                if previous_channel_dim != 0:
                    print("Policy eventhl is not working properly for channel",relay-1,", previous:",previous_channel_dim)
            if current_channel_dim != test_load['dim']:
                print("Policy eventlh is not working properly for channel",relay,", current:",current_channel_dim)
                for i in range(1,9):
                    print("Dim of channel",i,"is",coap_client.getDim(ip,i))
            
            # SET OUTPUT ON AND MEASURE POWER
            # time.sleep(1.0)
            if 'time_before_load_on' in test_json: time.sleep(test_json['time_before_load_on'])

            load.setOutputOn(True)

            if 'hold_load_time' in test_json: time.sleep(test_json['hold_load_time'])
            time.sleep(1.0)

            power_check(True)
            
            if dc_in_mode: 
                print("DCin Tested")
                break

        return True
    
    #if supernode_test: load.setOutputOn(False)
    return True

def dc_in_test():
    global dc_in_mode

    dc_in_mode = True

    misc.send_test_prompt(misc.key,f"Replace SuperNode PoE cable with data cable. Then connect the DCin cable. Press {misc.key} when ready","Starting DCin test")

    time.sleep(3.0)

    # coap_client.setCCCV(ip,0,1)
    # voltage = coap_client.getValue(ip,'/actuators/actuator1','voltage')
    #print(str(voltage))
    
    if 'loads' in test_json: 
        valid_loads = [load for load in test_json['loads'] if load.get('cccv') not in (1,2)]
        test_load = random.choice(valid_loads)
    elif 'load' in test_json: test_load = test_json['load']
    else: 
        print("'Load' nor 'Loads' found in test json file. Using local default value.")
        local_default_loads = [
        { "cccv": 0, "CV": 40, "dim": 100, "power": 45.0 },
        { "cccv": 1, "CC": 5.0, "dim": 100, "power": 45.0 },
        { "cccv": 2, "CC": 2.5, "dim": 100, "power": 45.0 },
        { "cccv": 3, "CC": 2, "dim": 100, "power": 45.0 },
        { "cccv": 4, "CC": 1.5, "dim": 100, "power": 45.0 }
        ]
        valid_loads = [load for load in local_default_loads if load.get('cccv') not in [1,2]]
        test_load = random.choice(local_default_loads)
    print(test_load)
    load_test(test_load)

    coap_client.setCCCV(ip,0,255)
    
    # time.sleep(5.0)
    # if int(voltage) < 9000: 
    #     print("Voltage is inadequate:", voltage)
    #     return False

    return True

def commission(configuration):
    test_pass: bool = True
    print("configuring supernode")

    for index,setting in enumerate(configuration):

        if 'sentype' in setting:
            sentype_config = str(setting['sentype'])
            print("Sentype:",sentype_config)
            coap_client.setSentype(ip,0,sentype_config)
            time.sleep(1.0)
            for i in range(1,9):
                # time.sleep(0.25)
                coap_client.secure_setting(ip,'/sensors/input'+str(i),'sentype',str(sentype_config))
                print(coap_client.getEventLH(ip,i))

                # sentype = coap_client.getSentype(ip,i)
                # if sentype != sentype_config: 
                #     print("Failed to set sentype setting.")
                #     return False
        # if 'sentype' in setting: 
        #     sentype_config = str(setting['sentype'])
        #     print("Sentype:",sentype_config)
        #     coap_client.setSentype(ip,0,sentype_config)
        #     time.sleep(1.0)
        #     for i in range(1,9):
        #         sentype = coap_client.getSentype(ip,i)
        #         #time.sleep(0.25) 
        #         if sentype != sentype_config: 
        #             #print("Sentype commission failed on input",i)
        #             #print("Retrying...")
        #             count: int = 0
        #             while str(sentype) != sentype_config:
        #                 coap_client.setSentype(ip,i,str(setting['sentype']))
        #                 sentype = coap_client.getSentype(ip,i)
        #                 # time.sleep(0.15)
        #                 count += 1
        #                 if count >= 10: break
        #             # print("Count is:",count)
        #             if sentype != sentype_config: 
        #                 print("Failed to commission sentype on channel",i)
        #                 test_pass = False
        #             else: print("Sentype",i,'successfully set to',sentype)
        #         else: print("Sentype",i,'successfully set to',sentype)
        #############################################################################################

        if 'eventlh' in setting:
            event_lh_config = str(setting['eventlh'])
            print("EventLH:",event_lh_config)
            coap_client.setEventLH(ip,0,event_lh_config)
            time.sleep(1.0)
            for i in range(1,9):
                coap_client.secure_setting(ip,'/sensors/input'+str(i),'eventlh',str(event_lh_config))
                print(coap_client.getEventLH(ip,i))

        if 'eventhl' in setting:
            event_hl_config = str(setting['eventhl'])
            print("EventHL:",event_hl_config)
            #coap_client.setSentype(ip,0,sentype_config)
            coap_client.setEventHL(ip,0,event_hl_config)
            time.sleep(1.0)
            for i in range(1,9):
                coap_client.secure_setting(ip,'/sensors/input'+str(i),'eventhl',str(event_hl_config))
                print(coap_client.getEventLH(ip,i))

        ##############################################################################################
        if test_pass == False: return False   
    return True



"""
            # SUPERNODE RELATED SUPERNODE RELATED SUPERNODE RELATED SUPERNODE RELATED SUPERNODE RELATED 

            if supernode_test:

                # We do relay+1 because the supernode reads input channels as 1-8, not 0-7 (+1)
                coap_client.putValue(ip,'/sensors/input'+str(relay),'sentype','INPUT_LH_OR_HL') # change sensor 1 events supernode version
                coap_client.putValue(ip,'/sensors/input'+str(relay),'eventlh',f"F0,{relay},{dim}")
                coap_client.putValue(ip,'/sensors/input'+str(relay),'eventhl',f"F0,{relay},0") # change sensor 1 events supernode version                    

                # CHECK TO SEE THAT INPUT POLICY WAS SET PROPERLY
                sentype: str = coap_client.getValue(ip,'/sensors/input'+str(relay),'sentype')
                event_low_high: str = coap_client.getValue(ip,'/sensors/input'+str(relay),'eventlh')
                event_high_low: str = coap_client.getValue(ip,'/sensors/input'+str(relay),'eventhl')

                if sentype != "INPUT_LH_OR_HL": 
                    updateLog('testLoad',relay,'failed to set input sentype:',sentype)
                    return False
                else: pass #print("Channel",relay,"sentype check passed:",sentype)

                if event_low_high != f"F0,{relay},{test_load['dim']}": 
                    updateLog('testLoad',relay,'failed to set input eventlh:',event_low_high)
                    return False
                else: pass #print("Channel",relay,"eventlh check passed:",event_low_high)

                if event_high_low != f"F0,{relay},0": 
                    updateLog('testLoad',relay,'failed to set input eventhl:',event_high_low)
                    return False 
                else: pass #print("Channel",relay,"eventhl check passed:",event_high_low)

                if coap_client.getDim(ip,relay) != 0 and relay != 1: # Current channel should be 0 dim since it hasn't been set yet
                    print("Policy eventhl is not working properly for channel",relay)

                if relay == 1:
                    setMux(8,False)
                    time.sleep(0.5)

                setMux(relay)
                time.sleep(0.5)

                # Check to see that eventhl policy is working
                current_channel_dim = coap_client.getDim(ip,relay)
                if relay != 1: 
                    previous_channel_dim = coap_client.getDim(ip,relay-1)
                    if previous_channel_dim != 0:
                        print("Policy eventhl is not working properly for channel",relay-1,", previous:",previous_channel_dim)
                if current_channel_dim != test_load['dim']:
                    print("Policy eventlh is not working properly for channel",relay,", current:",current_channel_dim)
                    for i in range(1,9):
                        print("Dim of channel",i,"is",coap_client.getDim(ip,i))
            
            # SUPERNODE RELATED SUPERNODE RELATED SUPERNODE RELATED SUPERNODE RELATED SUPERNODE RELATED 
"""