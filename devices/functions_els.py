import load
import controller
import coap_client
import time

from devices import functions_misc as misc

key = misc.key

def load_test(ip: str,test_load, test_config):
    "This is the load test procedure for the ELS node"

    # print("testload",test_load)
    # print("testconfig",test_config)

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
            load.setOutputOn(False)

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

    dim: int = 100
    if 'dim' in test_load: dim = test_load['dim']

    coap_client.setDim(ip,3,10)
    time.sleep(0.5)
    coap_client.setDim(ip,3,dim)

    time.sleep(0.5)
                
    if ('CR' in test_load or 'CC' in test_load or 'CV' in test_load) and 'power' in test_load:

        relays = ['output1','output2']

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
            if 'time_before_load_on' in test_config: 
                time.sleep(test_config['time_before_load_on'])
            
            load.setOutputOn(True)
            if 'hold_load_time' in test_config: 
                time.sleep(test_config['hold_load_time'])
            time.sleep(1.0)

            # power_check function, check above
            if not power_check(True): return False

        misc.send_test_prompt(key,f'Press and hold EM-test button and press {key}', 'Keep holding EM-test button. Check green light, it should now blink quickly.')
        load.setOutputOn(True)
        time.sleep(1.0)
        if not power_check(False): return False
        misc.send_test_prompt(key,f'Release the EM-test button, then disconnect the PoE cable and press {key}','Keep PoE out. Check green light again. It should blink quickly.')
        if not power_check(True): return False
        misc.send_test_prompt(key,f'Plug PoE cable back in and press {key}','')
        time.sleep(2.0)
    return True