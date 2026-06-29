import time

from context import TestContext

from services import coap_client
from services import controller

def run(ctx: TestContext, number_of_times_to_restart: int = 1, seconds_to_wait_for_restart: float = 8.0) -> bool:
    # TODO Replace this with a simpler timeout check, also ip check should be different

    times_restarted = 0
    while(times_restarted < number_of_times_to_restart):
        coap_client.putValue(ctx.ip,'/network','cmd','trigger 1')
        count = 0
        while(count < seconds_to_wait_for_restart):
            try:
                print("Attempt",times_restarted+1,
                      "IP Address rediscovered:",
                      coap_client.getValue(ctx.ip,'/network','madr'))
                break
            except Exception:
                print("Awaiting ip...")
                time.sleep(1.0) # TODO THIS WAS ORIGINALLY OUTSIDE OF THIS EXCEPTION, CHECK IF NEEDED
                print(count)    # TODO THIS WAS ORIGINALLY OUTSIDE OF THIS EXCEPTION, CHECK IF NEEDED
                count += 1      # TODO THIS WAS ORIGINALLY OUTSIDE OF THIS EXCEPTION, CHECK IF NEEDED
        if coap_client.getValue(ctx.ip,'/network','madr') != ctx.ip: # TODO THIS WILL NEVER BE THE CASE!
            return False
        times_restarted += 1
    return True