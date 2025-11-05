import load
import controller
import coap_client
import time

from devices import functions_misc as misc

input_port_safe_mode: bool = False
defacto_load_off_state = {"CC": 0.015}

key = misc.key
ip: str = ''
test_yaml = ''
serial_number = ''

mot = '100'
vac = '0'
remote_driver_exists = True
drivers = [0]
http_server: str = ""

# Advice Brad gave me: Keep in mind this test can technically be done using the MAC address and communicating that way 
# rather than using coap w/ ip address. This would require writing a new test file, which I may do someday

# Reminders:
# Incorporate functions written here in test.py
# Make sure serial number is retrieved from driver in getIP
# Set serial number of gateway using serial number typed into test
# Look into how sensor / wall switch tests work (coap commands)

def init(ip_address,test_configuration, serialnum):
    global ip, test_yaml, serial_number, remote_driver_exists, drivers, http_server

    ip = ip_address
    set_dim(ip,0,0)
    setMux(2,True)    

    if not coap_client.secure_setting(ip,f'/drivers/0/actuator','cluster','test_cluster'): misc.send_test_prompt(misc.key,f'Type "set_cluster all group1" and press {misc.key} to continue.','')
    if not coap_client.secure_setting(ip,f'/drivers/0/sensor','cluster','test_cluster'): misc.send_test_prompt(misc.key,f'Type "set_cluster all group1" and press {misc.key} to continue.','')
    if not coap_client.secure_setting(ip,f'/drivers/0/wallswitch','cluster','test_cluster'): misc.send_test_prompt(misc.key,f'Type "set_cluster all group1" and press {misc.key} to continue.','')
    
    if not coap_client.secure_setting(ip,f'/drivers/0/sensor','enable','true'): misc.send_test_prompt(misc.key,f'Type "set_sensor_enable true" in driver 0 console and press {misc.key} when it has been set.','')
    #if not coap_client.secure_setting(ip,f'/drivers/0/wallswitch','enable','true'): misc.send_test_prompt(misc.key,f'Type "set_wallswitch_enable true" in driver 0 console and press {misc.key} when it has been set.','')

    serial_number = serialnum
    test_yaml = test_configuration
    print("Mini Node Variables Initialized!")
    if 'firmware_upgrade' in test_yaml and test_yaml['firmware_upgrade']:
        if "http_server" in test_yaml: 
            http_server = test_yaml["http_server"]
            if "http_port" in test_yaml: http_server = f"http://192.168.2.47:{test_yaml["http_port"]}/firmware"
        print("http-server is:",http_server)
    if 'remote_drivers' in test_yaml:
        if test_yaml['remote_drivers'] == False or test_yaml['remote_drivers'] == 0: remote_driver_exists = False
        else: 
            remote_driver_exists = True
            remote_drivers = test_yaml['remote_drivers']
            drivers = list(range(0,remote_drivers+1))
        print(f"Remote Driver is set to {remote_driver_exists}, with there being {drivers} drivers.")
    if 'mini_cp' in test_yaml: 
        if not set_power_test(test_yaml['mini_cp']): misc.updateLog('set_power_test','fail')
        else: misc.updateLog('set_power_test','pass')
    if 'mini_cv' in test_yaml: 
        if not set_voltage_test(test_yaml['mini_cv']): misc.updateLog('set_voltage_test','fail')
        else: misc.updateLog('set_voltage_test','pass')
    if 'mini_cc' in test_yaml: 
        if not set_current_test(test_yaml['mini_cc']): misc.updateLog('set_current_test','fail')
        else: misc.updateLog('set_current_test','pass')

    input_configuration()

def get_dim(ip_address,channel):
    return coap_client.getValue(ip_address,f'/drivers/{channel}/actuator','pp')

def set_dim(ip_address: str,channel: int,dim: int,verbose: bool = False):
    coap_client.secure_setting(ip_address,f'/drivers/{channel}/actuator','pp',dim,verbose)

def get_power(ip_address: str,channel):
    return coap_client.getValue(ip_address,f'/drivers/{channel}/actuator','power')

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

def setMux(channel: int, verbose: bool = True, delay:float = 0.25):
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
            print("Attempting to retrive mux")
            count = 0
        #print("MUX WAS NOT SET PROPERLY FOR CHANNEL",channel,"- CURRENT MUX IS",current_mux)
        count+=1
        time.sleep(delay)

def get_board_version(ip_address):
    version_match = True

    if not 'gateway_version' in test_yaml:
        print("No gateway version specified in config file. Please resolve.")
        return False
    else: 
        gateway_version = str(test_yaml['gateway_version'])
        print("Gateway version should be: ", gateway_version)

    if not 'driver_version' in test_yaml:
        print("No driver version specified in config file. Please resolve.")
        return False
    else: 
        driver_version = str(test_yaml['driver_version'])
        print("Driver version should be: ", driver_version)

    gateway_found = coap_client.getValue(ip_address,'/version','version')
    if not gateway_found == gateway_version: 
        print("Gateway version",gateway_found,"does not match version",gateway_version,"specified in config file.")
        version_match = False
    driver_found = coap_client.getValue(ip_address,'/drivers/0/version','version')
    if not driver_found == driver_version:
        print("Driver version",driver_found,"does not match version",driver_version,"specified in config file.")
        version_match = False
    
    if version_match is False: return False
    else: return True
    #return coap_client.getValue(ip_address,'/version','hw_rev')
    

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
            # if "defacto_load_off_state" in test_yaml:
            #     defacto_load_off_state = test_yaml["defacto_load_off_state"]
            #     if "CC" in test_yaml["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CC"])
            #     if "CV" in test_yaml["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CV"])
            #     if "CR" in test_yaml["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CR"])
            # else: load.setOutputOn(False)
            if "defacto_load_off_state" not in test_yaml: load.setOutputOn(False)

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
            if "defacto_load_off_state" in test_yaml:
                defacto_load_off_state = test_yaml["defacto_load_off_state"]
                if "CC" in test_yaml["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CC"])
                if "CV" in test_yaml["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CV"])
                if "CR" in test_yaml["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CR"]) 
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
    set_dim(ip,0,dim,True)
    if remote_driver_exists: set_dim(ip,1,dim,True)


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
            if 'time_before_load_on' in test_yaml: 
                time.sleep(test_yaml['time_before_load_on'])
            
            load.setOutputOn(True)
            if 'hold_load_time' in test_yaml: 
                time.sleep(test_yaml['hold_load_time'])
            time.sleep(1.0)

            # power_check function, check above
            if not power_check(True): return False

    return True

def loads_test(test_loads):
    test_pass = True
    for index,test_load in enumerate(test_loads):
        if not load_test(test_load): test_pass = False

    # Sets load output off
    if "defacto_load_off_state" in test_yaml:
        if "CC" in test_yaml["defacto_load_off_state"]: load.setCurrent(defacto_load_off_state["CC"])
        if "CV" in test_yaml["defacto_load_off_state"]: load.setVoltage(defacto_load_off_state["CV"])
        if "CR" in test_yaml["defacto_load_off_state"]: load.setResistance(defacto_load_off_state["CR"])
    else: load.setOutputOn(False)
    if test_pass:
        misc.updateLog('testLoads','pass')
        return True
    misc.updateLog('testLoads','fail')

    return False

def serial_number_test(serialnum):
    get_sn = coap_client.getSN(ip)
    print("Gateway serial number is",get_sn)
    if serialnum != get_sn: 
        misc.updateLog('testSerialNumber','fail get',get_sn)
        return False
    else:
        print(serial_number)
        coap_client.putValue(ip,'/drivers/0','serial_number',serial_number)
        print("Driver serial number is",coap_client.getValue(ip,'/drivers/0','serial_number'))

def remote_driver_test():
    "This is where we test the mini node's ability to generate and power a remote driver"
    misc.send_test_prompt(key,f'This is the remote driver test. Press {key} to continue','Continuing test')
    coap_client.getValue(ip,'/network','serial_number')
    coap_client.putValue(ip,'/driver','serial_number',serial_number)

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

def return_sensor_test(ret):
    #coap_client.putValue(ip,'/sensors/sensor1','eventrisefall','mot,vac') # reset sensor 1 events
    coap_client.putValue(ip,'/actuators/actuator1','motdsbl','3') # disable motion
    return ret

def sensor_test():
    seconds: int = 0


    if input_port_safe_mode: misc.send_test_prompt(misc.key,f'Make sure sensor is plugged in and wallswitch is unplugged. Press {misc.key} to continue','Starting sensor test...')
    for driver in drivers:
        if not coap_client.secure_setting(ip,f'/drivers/{driver}/sensor','enable','true'): misc.send_test_prompt(misc.key,f'Type "set_sensor_enable true" in driver {driver} console and press {misc.key} when it has been set.','')
        if not set_power_test(900): misc.send_test_prompt(misc.key,f'Set power manually on driver {driver} and then press {key} to continue','Continuing...')
        # if not set_current_test(3000): misc.send_test_prompt(misc.key,f'Set current manually on driver {driver} and then press {key} to continue','Continuing...')

    # coap_client.putValue(ip,'/actuators/actuator1','motdsbl','33') # enable motion, CHECK MINI NODE EQUIVALENT

    # set Aux1 low, then set dim to 0 just in case aux didn't work this one time.
    controller.setAux(1,False,'') 
    for driver in drivers: 
        set_dim(ip,driver,0)
        
        # Get the dim setting on the mini node's policy.
        dim_setting = coap_client.getValue(ip,'/drivers/0/sensor','eventlh')
        if dim_setting == 'mot': dim_setting = int(mot)
        else:
            dim_setting = dim_setting.split(',')[-1].strip(';')
            dim_setting = int(dim_setting)
        print(f"Testing dim for driver {driver} with dim {dim_setting}")

    time.sleep(5.0) # wait for event, try to shorten this @ some point
    controller.setAux(1,True,'') # set Aux1 high, test rising edge of sensor1
    # time.sleep(5.0) # wait for event

    dim1 = get_dim(ip,0)
    while dim1 != 100:
        dim1 = get_dim(ip,0)
        # print("Dim of Driver 0 is",dim1)
        seconds += 1
        if seconds >= 10: break
    print("Driver 1: Dim 100 took ",seconds, " seconds.")
    if dim1 != dim_setting and dim1 == 0:
        misc.updateLog('testSensor1','high',1,'fail set dim',dim1)
        return return_sensor_test(False) # DREW note turn aux 1 off if fail
    else: misc.updateLog('testSensor1','high','pass set dim', dim1)
    if remote_driver_exists:
        dim2 = get_dim(ip,1)
        print("Dim of Driver 1 is",dim2)
        if dim2 != dim_setting and dim2 == 0:
            misc.updateLog('testSensor1','high',2,'fail set dim',dim2)
            return return_sensor_test(False)
        else: misc.updateLog('testSensor1','high','pass set dim', dim2)
    controller.setAux(1,False,'') # set Aux1 low, test falling edge of sensor1
    time.sleep(1.0) # wait for  event
    dim1 = get_dim(ip,0) # dim1 should be 0%
    while dim1 != 0:
        dim1 = get_dim(ip,0)
        # print("Dim of Driver 0 is",dim1)
        seconds += 1
        if seconds >= 10: break
    print("Driver 1: Dim 0 took ",seconds, " seconds.")
    if remote_driver_exists:
        seconds = 0
        dim2 = get_dim(ip,1) # dim2 should be 0%
        while dim2 != 0:
            dim2 = get_dim(ip,0)
            # print("Dim of Driver 0 is",dim1)
            seconds += 1
            if seconds >= 10: break
        print("Driver 2: Dim 0 took ",seconds, " seconds.")
    
    if dim1 != 0:
        misc.updateLog('testSensor1','low',1,'fail set dim',dim1)
        return return_sensor_test(False)
    elif remote_driver_exists:
        if dim2 != 0:
            misc.updateLog('testSensor1','low',2,'fail set dim',dim2)
            return return_sensor_test(False)
        else: misc.updateLog('testSensor1','low','pass set dim', dim2)
    return return_sensor_test(True)

def wallswitch_test(drivers):
    if input_port_safe_mode: misc.send_test_prompt(misc.key,f'Make sure wallswitch is plugged in and sensor is unplugged. Press {misc.key} to continue','Starting wallswitch test...')
    #drivers: list = list(range(0,drivers+1))

    print("Drivers:",drivers)
    for driver in drivers: 
        if not coap_client.secure_setting(ip,f'/drivers/{driver}/wallswitch','enable','true'): misc.send_test_prompt(misc.key,f'Type "set_wallswitch_enable true" in driver console and press {misc.key} when it has been set.','')
    
    time.sleep(3.0) # 2.9.4+ has a slight delay before enabling

    setMux(2,True)

    controller.setPush4BTNOff() # press off button, but ignore event
    for driver in drivers: set_dim(ip,driver,0)

    time.sleep(1.0) # CHECK TO SEE IF THIS IS NECESSARY
    misc.updateLog('Starting PDLine Testing')

    for driver in drivers:
        attempts = 0
        while attempts != 10:
            time.sleep(0.25)
            controller.setPush4BTNOn()
            dim = get_dim(ip,driver) # dim1 should be 0%
            attempts += 1
            if dim == 100: break
        misc.updateLog(f'Attempts taken for dim 100 on Driver {driver}:', attempts)
        if dim != 100:
            misc.updateLog('testPDLine','On Driver',driver,'fail set dim',dim)
            return False
        
        attempts = 0
        while attempts != 10:
            time.sleep(0.25)
            controller.setPush4BTNOff()
            dim = get_dim(ip,driver) # dim1 should be 0%
            attempts += 1
            if dim == 0: break
        misc.updateLog(f'Attempts taken for dim 0 on Driver {driver}:', attempts)
        if dim != 0:
            misc.updateLog('testPDLine','Off Driver',driver,'fail set dim',dim)
            return False

    return True

def firmware_upgrade_test():
    """This is where we test the mini node's ability to download a firmware update from a URL,
    \nsimulating its ability to do so in the field. Note that http server should be active beforehand"""
    
    if http_server == '':
        print('The http-server link is not set. Check the yaml file in',test_yaml)
        return False
    version_json_link: str = f"{http_server}/version.json"

    wait_time = 7.0
    # Updates the gateway
    coap_client.putValue(ip,'/ota','version_url',version_json_link)
    time.sleep(wait_time)
    print("Setting fetch_version to true on Gateway...")
    coap_client.putValue(ip,'/ota','fetch_version',"true")
    time.sleep(wait_time)
    coap_client.putValue(ip,'/ota','start',"true")
    
    time.sleep(25.0)

    # Updates the driver(s)
    coap_client.putValue(ip,'/drivers/0/ota','version_url',version_json_link)
    time.sleep(wait_time)
    print("Setting fetch_version to true on Driver...")
    coap_client.putValue(ip,'/drivers/0/ota','fetch_version',"true")
    time.sleep(wait_time)
    coap_client.putValue(ip,'/drivers/0/ota','start',"true")
    if remote_driver_exists: 
        coap_client.putValue(ip,'/drivers/1/ota','version_url',version_json_link)
        time.sleep(wait_time)
        coap_client.putValue(ip,'/drivers/1/ota','fetch_version',"true")
        time.sleep(wait_time)
        coap_client.putValue(ip,'/drivers/1/ota','start',"true")
    misc.send_test_prompt()

def autotune_test():
    "This is where we test the mini node's ability to change the color of a light fixture"
    misc.send_test_prompt(key,f'This is the remote driver test. Press {key} to continue','Continuing test')
    coap_client.secure_setting(ip,'/drivers/0/actuator','pwm_mode','AT')

    coap_client.secure_setting(ip,'/drivers/0/actuator','at','3000')
    misc.send_test_prompt(key,f'Check lights for AT 3000. Then press {key} to continue','Continuing test')

    coap_client.secure_setting(ip,'/drivers/0/actuator','at','4000')
    misc.send_test_prompt(key,f'Check lights for AT 4000. Then press {key} to continue','Continuing test')

    coap_client.secure_setting(ip,'/drivers/0/actuator','at','5000')
    misc.send_test_prompt(key,f'Check lights for AT 5000. Then press {key} to continue','')

    misc.updateLog('autotune_test','pass')

def rgbw_test(rgbw_sets: list = ["4278190080","16711680","65280","255","4294967295"]):
    pause_to_check = False

    if pause_to_check: misc.send_test_prompt(key,f'This is the RGBW test. Press {key} to continue','Continuing test')
    coap_client.secure_setting(ip,'/drivers/0/actuator','pwm_mode','RGBW_CC')

    set_current_test(2100)
    set_voltage_test(40000)
    set_power_test(900)
    set_dim(ip,0,0)

    setMux(1,True)
    set_dim(ip,0,100)

    
    for rgbw_set in rgbw_sets:
        time.sleep(2.0)
        coap_client.secure_setting(ip,f'/drivers/0/actuator','rgbw',rgbw_set)
        # time.sleep(0.5)
        # set_dim(ip,0,100,True)
        power = get_power(ip,0)
        if power < 700: 
            misc.send_test_prompt(key,f'Power ({power}) is too low. Either fix and press {key} or press Esc and send to troubleshooting.','')
        else:
            if pause_to_check: misc.send_test_prompt(key,f'Confirm the fixture(s) match the RGBW setting: {hex(rgbw_set)}. If so, press {key} to continue.','Continuing test')
            else: 
                print("Fixture set to",hex(rgbw_set))
                time.sleep(3.0)
# def commission(commission_settings_list):
#     for setting in commission_settings_list:
#         if 'resource' in setting: resource = setting['resource']
#         else: print("No resource set for this setting")
#         if 'key' in setting: key = setting['key']
#         else: print("No key set for this setting")
#         if 'value' in setting: value = setting['value']
#         else: print("No value set for this setting")

#         if not coap_client.secure_setting(ip,resource,key,value,True): return False
#     return True
