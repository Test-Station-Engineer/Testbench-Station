import time

from context import TestContext

from services import controller

from resources import actuators

from write import write

# NOTE Fun fact: The old name for this was testPDLine
def run(ctx: TestContext) -> bool:
    print(f"\033[94mRunning Wall Switch Test\033[0m")
    Device = ctx.Device

    def push_btn_then_check_dim_loop(btn_state: bool, expected_dim: int, attempts: int = 10) -> bool:
        attempts_made: int = 0
        passed: bool = False
        while attempts_made < attempts:
            time.sleep(0.25)
            if btn_state:
                controller.setPush4BTNOn()
            else:
                controller.setPush4BTNOff()
            verbose = True if attempts == 9 else False
            if not actuators.check_actuators_dim(ctx, Device.all_actuators_integer(), expected_dim,verbose=verbose):
                attempts_made += 1
            else: 
                passed = True
                break
        print('Attempts taken for dim 100:', attempts_made)
        return passed

    # Core Node Procedure was here, deleted

    Device.procedure().before_pdline_test(ctx)
    
    # if safe mode thingy: NOTE TRANSFER THIS LATER
    #     write.send_test_prompt(write.key,f'Connect control port of {ctx.device_name} to test station and press {write.key}','')
    
    controller.setPush4BTNOff() # press off button, but ignore event
    actuators.set_dim(ctx, Device.all_actuators_integer(),0) # clear dim, in case off button did not work
    
    time.sleep(1.0) # TODO CHECK TO SEE IF THIS IS NECESSARY
    
    write.updateLog('Starting PDLine Testing')
    
    if not push_btn_then_check_dim_loop(True, 100):
        write.updateLog('testPDLine','On','fail set dim')
        return False

    if not push_btn_then_check_dim_loop(False, 0):
        write.updateLog('testPDLine','Off','fail set dim')
        return False
    return True