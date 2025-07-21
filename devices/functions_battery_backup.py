import load
import controller
import coap_client
import time

from devices import functions_misc as misc

defacto_load_off_state = {"CC": 0.015}

key = misc.key
ip: str = ''
test_json = ''
serial_number = ''

mot = '100'
vac = '0'
remote_driver_exists = True
http_server: str = ""

def init(ip_address,test_configuration, serialnum):
    global ip, test_json, serial_number, remote_driver_exists, http_server

    ip = ip_address
    serial_number = serialnum
    test_json = test_configuration
    print("Mini Node Variables Initialized!")
    if "http_port" in test_json: http_server = f"http://192.168.3.13:{test_json["http_port"]}/firmware"
    elif "http_server" in test_json: http_server = test_json["http_server"]
    print("http-server is:",http_server)
    if 'remote_driver' in test_json:
        if test_json['remote_driver'] == False: remote_driver_exists = False
        print("Remote Driver is set to",remote_driver_exists)
    if 'mini_cp' in test_json: 
        if not set_power_test(test_json['mini_cp']): misc.updateLog('set_power_test','fail')
        else: misc.updateLog('set_power_test','pass')
    if 'mini_cv' in test_json: 
        if not set_voltage_test(test_json['mini_cv']): misc.updateLog('set_voltage_test','fail')
        else: misc.updateLog('set_voltage_test','pass')
    if 'mini_cc' in test_json: 
        if not set_current_test(test_json['mini_cc']): misc.updateLog('set_current_test','fail')
        else: misc.updateLog('set_current_test','pass')

    input_configuration()

def get_dim(ip_address,channel):
    return coap_client.getValue(ip_address,f'/drivers/{channel}/actuator','dim')

def set_power_test(power: int):
    if coap_client.secure_setting(ip,f'/drivers/0/actuator','cp',power,True):
        if remote_driver_exists: 
            if coap_client.secure_setting(ip,f'/drivers/1/actuator','cp',power,True): return True
            else: return False
        else: return True
    else: return False

def set_voltage_test(voltage: int):
    if coap_client.secure_setting(ip,f'/drivers/0/actuator','cv',voltage,True):
        if remote_driver_exists: 
            if coap_client.secure_setting(ip,f'/drivers/1/actuator','cv',voltage,True): return True
            else: return False
        else: return True
    else: return False

def set_current_test(current: int):
    if coap_client.secure_setting(ip,f'/drivers/0/actuator','cc',current,True):
        if remote_driver_exists: 
            if coap_client.secure_setting(ip,f'/drivers/1/actuator','cc',current,True): return True
            else: return False
        else: return True
    else: return False

def load_test(test_load):
    "This is the load test procedure for the mini node"

    def power_check(turn_off_load_after: bool = True):
        global defacto_load_off_state
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

            # Sets load output to a low or off state, depending on your test configuration
            # if "defacto_load_off_state" in test_json:
            #     defacto_load_off_state = test_json["defacto_load_off_state"]
            #     if "CC" in test_json["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CC"])
            #     if "CV" in test_json["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CV"])
            #     if "CR" in test_json["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CR"])
            # else: load.setOutputOn(False)
            if "defacto_load_off_state" not in test_json: load.setOutputOn(False)

            # if power is less than required, fail it. Else, pass it
            if power < test_load['power']:
                misc.updateLog('testLoad',relay,'fail power',power)
                return False
            else: 
                misc.updateLog('testLoad',relay,'pass power',power)
                return True
        misc.updateLog('testLoad',relay,'pass power',power)

        # Sets load output to a low or off state, depending on your test configuration
        if turn_off_load_after:
            if "defacto_load_off_state" in test_json:
                defacto_load_off_state = test_json["defacto_load_off_state"]
                if "CC" in test_json["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CC"])
                if "CV" in test_json["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CV"])
                if "CR" in test_json["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CR"]) 
            else: load.setOutputOn(False)
        return True

    dim: int = 100
    if 'mini_cp' in test_load: set_power_test(test_load['mini_cp'])
    if 'mini_cv' in test_load: set_voltage_test(test_load['mini_cv'])
    if 'mini_cc' in test_load: set_current_test(test_load['mini_cc'])
    if 'dim' in test_load: dim = test_load['dim']

    # print("Current dim is:",coap_client.getValue(ip,'/drivers/0/actuator','dim'))
    #coap_client.secure_setting(ip,'/drivers/0/actuator','dim',dim/2,True)
    #if remote_driver_exists: coap_client.secure_setting(ip,'/drivers/1/actuator','dim',dim/2)
    time.sleep(1.0)
    coap_client.secure_setting(ip,'/drivers/0/actuator','dim',dim,True)
    if remote_driver_exists: coap_client.secure_setting(ip,'/drivers/1/actuator','dim',dim)


    time.sleep(0.5)
                
    if ('CR' in test_load or 'CC' in test_load or 'CV' in test_load) and 'power' in test_load:

        relays = ['output2']

        #print(relays)

        for relay in relays:

            # Set load to channel
            controller.setRelays(relay) 

            # Set load on load machine
            if 'CR' in test_load: load.setResistance(test_load['CR'])
            if 'CV' in test_load: load.setVoltage(test_load['CV'])
            if 'CC' in test_load: load.setCurrent(test_load['CC'])
            
            # Set output on and measure power
            time.sleep(1.0)
            if 'time_before_load_on' in test_json: 
                time.sleep(test_json['time_before_load_on'])
            
            load.setOutputOn(True)
            if 'hold_load_time' in test_json: 
                time.sleep(test_json['hold_load_time'])
            time.sleep(1.0)

            # power_check function, check above
            if not power_check(True): return False

    return True

def loads_test(test_loads):
    pass

def input_configuration():
    "This is where we set the input sensor configuration for the mini node"
    global remote_driver_exists

    coap_client.secure_setting(ip,'/drivers/0/sensor','type','INPUT_LH')
    coap_client.secure_setting(ip,'/drivers/0/policy','mot',f'F1,0,{mot},-1,101;')
    coap_client.secure_setting(ip,'/drivers/0/policy','vac','F1,0,101,1,0;')
    # coap_client.secure_setting(ip,'/drivers/0/sensor','eventlh','mot')
    # coap_client.secure_setting(ip,'/drivers/0/sensor','eventhl','vac')
    coap_client.secure_setting(ip,'/drivers/0/sensor','eventlh',f'F0,0,{mot};')
    coap_client.secure_setting(ip,'/drivers/0/sensor','eventhl',f'F0,0,{vac};')

    if remote_driver_exists:
        remote_test_fail = False
        if not coap_client.secure_setting(ip,'/drivers/1/sensor','type','INPUT_LH'): remote_test_fail = True
        # if not coap_client.secure_setting(ip,'/drivers/1/policy','mot',f'F1,0,{mot},-1,101;'): remote_test_fail = True
        if not coap_client.secure_setting(ip,'/drivers/1/policy','mot',f'F1,0,{mot},-1,101;'): remote_test_fail = True
        if not coap_client.secure_setting(ip,'/drivers/1/policy','vac','F1,0,101,1,0;'): remote_test_fail = True
        if not coap_client.secure_setting(ip,'/drivers/1/sensor','eventlh',f'F0,0,{mot};'): remote_test_fail = True
        if not coap_client.secure_setting(ip,'/drivers/1/sensor','eventhl',f'F0,0,{vac};'): remote_test_fail = True
        if remote_test_fail: print("Remote driver configuration failed")
