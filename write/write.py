# Miscellaneous Functions for the test station, related to logging or sending messages
#import database
from pynput import keyboard
import sys

key = keyboard.Key.down 
#key = 'down'

key_string = "nothing"

process_ended: bool = False

def updateLog(*args):
    desc = ''
    for arg in args:
        if desc == '':
            desc = str(arg)
        else:
            desc += ' '+str(arg)
    if desc != '':
        print(desc)
        # Removed for now, might reimplement if I bring database back
        #database.updateTestLog(test_id,serial_number,board_version,desc)

def updateState(method,msg,state,description):
    print(method,msg)
    data = {
        "CurrentState":state,
        "Description":description
    }
    # Removed for now, might reimplement if I bring database back
    # database.updateTestTable(data, test_id)

def send_test_prompt(keyboard_key = key, prompt: str = f'Press {key_string} to continue', response: str = 'This is the response when the key is pressed'):

    json_key_mapping = { # This is used in send_test_prompt
        "enter": keyboard.Key.enter,
        "space": keyboard.Key.space,
        "down": keyboard.Key.down,
        "right": keyboard.Key.right,
        "esc": keyboard.Key.esc
        # Add other keys as needed
    }

    if len(str(keyboard_key)) > 1:
        if keyboard_key not in keyboard.Key:
            json_key_match = json_key_mapping.get(keyboard_key.lower())
            if json_key_match is None:
                print(f"\nKey '{keyboard_key}' does not exist in keyboard.Key.")
                print('\nKeyboard key is set to',keyboard_key)
                print('\nWARNING: Test prompt step key not set properly: Invalid key')
                sys.exit()
            else:
                keyboard_key = json_key_match


        key_string = str(keyboard_key)
        key_string = key_string.split('.')[-1]

    if str(keyboard_key) in prompt: prompt = prompt.replace(str(keyboard_key), key_string)
    if key_string.lower() in prompt: prompt = prompt.replace(str(key_string.lower()),key_string.upper())

    print(prompt)

    def on_press(key_input):
        global process_ended
        try:
            if key_input == keyboard.Key.esc:
                process_ended = True
                return False
            if key_input == keyboard_key:
                print("Key pressed:", key_string)
                return False  # Stop listener
        except AttributeError:
            pass  # Handle special keys (like Shift, Ctrl, etc.)

    # Set up the listener
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()  # Wait until the key is pressed

    if not process_ended: print(response)
    else:
        print("\nEscape was pressed. Process ended.")
        sys.exit()

def check_toggle(test_settings: dict):
    if 'toggle' not in test_settings: 
        return True
    elif test_settings['toggle'] in [0, False]: 
        return False
    return True