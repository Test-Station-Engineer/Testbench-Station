import time

from context import TestContext

# from services import coap_client
from services import controller

from resources import actuators

from write import write

def run(ctx: TestContext) -> bool:
    print(f"\033[94mRunning Sensor Test\033[0m")

    Device = ctx.Device
    passed: bool = True

    Device.procedure().before_sensor_test(ctx)
    
    # if ctx.mini_node_test:
    #     if mnode.sensor_test(): return True
    #     else: return False

    # TODO Replace send_test_prompt with a popup prompt instead
    if ctx.input_safety_mode: 
        write.send_test_prompt(write.key,f'Connect control port of {Device.name} to test station and press {write.key}','')
        ctx.input_safety_mode = False
    
    controller.setAux(1,False,'') # set Aux1 low

    actuators.set_dim(ctx, Device.all_actuators_integer(),0) # Clear dim, in case Aux1 was left high for some reason

    time.sleep(5.0) # wait for event

    controller.setAux(1,True,'') # set Aux1 high, test rising edge of sensor1
    time.sleep(5.0) # wait for event

    if not actuators.check_actuators_dim(ctx, Device.all_actuators_integer(), 100, verbose=True):
        write.updateLog('testSensor1','high','fail set dim')
        passed = False

    time.sleep(2.0)

    controller.setAux(1,False,'') # set Aux1 low, test falling edge of sensor1
    time.sleep(1.0) # wait for  event

    if not actuators.check_actuators_dim(ctx, Device.all_actuators_integer(), 0, verbose=True):
        write.updateLog('testSensor1','low','fail set dim')
        passed = False

    Device.procedure().after_sensor_test(ctx)
    return passed