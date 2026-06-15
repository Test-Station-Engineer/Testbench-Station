from services import controller
from time import sleep

def set(channel: int, verbose: bool = True, delay: float = 0.25):
    # If you want to improve the odds of it finding the mux, give it more time to read it in controller.py

    controller.setMux(channel - 1)

    if verbose: 
        print("Setting Mux to output on channel", channel)
    if delay: sleep(delay)
    #print("Mux channel",relay,"is",controller.getMux())
    current_mux = controller.getMux()
    count: int = 0
    while current_mux != channel - 1:
        current_mux = controller.getMux()
        if count == -1 or count % 50 == 0:
            print("Attempting to retrieve mux")
            count = 1
        #print("MUX WAS NOT SET PROPERLY FOR CHANNEL",channel,"- CURRENT MUX IS",current_mux)
        count += 1
        if delay: 
            sleep(delay)
        
        if count > 200:
            print("MUX failed to set after 200 polls; continuing anyway")
            break