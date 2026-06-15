from dataclasses import dataclass
from typing import Optional

import time
from services import load_mach

from frontend import prompt
from write import write

# TODO Delete later
from devices import functions_mini as mnode
from devices import functions_els as els
#
from services import controller

from context import TestContext

GREEN = "\033[3;92m" # TODO Move this to a utilities file and expand to support more colors and formatting options
RED = "\033[3;91m" # TODO Move this to a utilities file and expand to support more colors and formatting options
YELLOW = "\033[3;93m" # TODO Move this to a utilities file and expand to support more colors and formatting options
RESET = "\033[3;0m" # TODO Move this to a utilities file and expand to support more colors and formatting options

# TODO Move this to a utilities file and expand to support more colors and formatting options
def color_val(value, ok):
    return f"{GREEN}{value}{RESET}" if ok else f"{RED}{value}{RESET}"

@dataclass
class LoadTestResult:
    status: bool
    average_power: float | None
    median_power: float | None
    minimum_power: float | None
    maximum_power: float | None

@dataclass
class GeneralLoadTestSettings:
    time_before_load_on: Optional[float] = None
    hold_load_time: Optional[float] = None
    measure_every_seconds: Optional[float] = None
    sweep_channel_first: bool = False
    turn_load_off_after: bool = True

@dataclass
class SingleLoadTestSettings:
    min_power_thresh: Optional[float] = None
    max_power_thresh: Optional[float] = None
    sweep_channel_first: bool = False
    load_cr: Optional[float] = None
    load_cv: Optional[float] = None
    load_cc: Optional[float] = None
    time_before_load_on: Optional[float] = None
    hold_load_time: Optional[float] = None
    measure_every_seconds: Optional[float] = None
    turn_load_off_after: bool = True

def parse_general_load_test_settings(ctx: TestContext, test_loads: dict) -> GeneralLoadTestSettings:
    return GeneralLoadTestSettings(
        time_before_load_on = (test_loads['time_before_load_on'] if 'time_before_load_on' in test_loads 
                               else ctx.test_config.get('time_before_load_on', 1.0)),
        hold_load_time = (test_loads['hold_load_time'] if 'hold_load_time' in test_loads
                          else ctx.test_config.get('hold_load_time', 3.0)),
        measure_every_seconds = (test_loads['measure_every_seconds'] if 'measure_every_seconds' in test_loads
                                 else ctx.test_config.get('measure_every_seconds', 0.25)),
        sweep_channel_first = (test_loads['sweep_channel_first'] if 'sweep_channel_first' in test_loads
                               else ctx.test_config.get('sweep_channel_first', False)),
        turn_load_off_after = (test_loads['turn_load_off_after'] if 'turn_load_off_after' in test_loads
                               else ctx.test_config.get('turn_load_off_after', True))
    )

def parse_single_load_test_settings(ctx: TestContext, test_load: dict) -> SingleLoadTestSettings:
    # ---- Get general defaults safely ----
    general = ctx.general_load_settings or GeneralLoadTestSettings()
    # print("SWEEP CHANNELS FIRST IS SET TO:", "test_load:",test_load.get('sweep_channel_first'), "general:",general.sweep_channel_first, "ctx.test_config:", ctx.test_config.get('sweep_channel_first', False))

    # ---- Validate required parameters ----
    has_power = ('power' in test_load) or ('below_power' in test_load)
    has_load = any(k in test_load for k in ('Load_CR', 'Load_CC', 'Load_CV'))

    if not has_power:
        print(f"WARNING: LOAD {test_load} HAS NO POWER THRESHOLD LISTED")
    if not has_load:
        print(f"WARNING: LOAD {test_load} HAS NO LOAD SETTING LISTED")

    if not (has_power and has_load):
        print("Skipping load test due to missing required parameters.")
        return None

    # ---- Parse power thresholds ONLY from test_load ----
    min_power = None
    max_power = None

    if 'power' in test_load:
        try:
            min_power = float(test_load['power'])
        except (TypeError, ValueError):
            print(f"Invalid power value: {test_load['power']}")

    if 'below_power' in test_load:
        try:
            max_power = float(test_load['below_power'])
        except (TypeError, ValueError):
            print(f"Invalid below_power value: {test_load['below_power']}")    

    # ---- hold_load_time (test_load > general > config > default) ----
    hold_load_time = (
        test_load.get('hold_load_time')
        or general.hold_load_time
        or ctx.test_config.get('hold_load_time')
    )

    if hold_load_time is None or hold_load_time <= 0:
        print(f"\033[3;93mInvalid hold_load_time value: {hold_load_time}. "
              f"Using default of 3.0 seconds.\033[0m")
        hold_load_time = 3.0

    # ---- Build settings object ----
    return SingleLoadTestSettings(
        min_power_thresh = min_power,
        max_power_thresh = max_power,
        sweep_channel_first = (test_load.get('sweep_channel_first') or general.sweep_channel_first or False),
        load_cr = test_load.get('Load_CR'),
        load_cv = test_load.get('Load_CV'),
        load_cc = test_load.get('Load_CC'),
        time_before_load_on = (test_load.get('time_before_load_on') or general.time_before_load_on or 1.0),
        hold_load_time=hold_load_time,
        measure_every_seconds = (test_load.get('measure_every_seconds') or general.measure_every_seconds or 0.25),
        turn_load_off_after = test_load.get('turn_load_off_after', general.turn_load_off_after)
    )
def moving_power_check(
    min_power_thresh: float = None,
    max_power_thresh: float = None,
    hold_time_seconds: float = 5.0,
    measure_every_seconds: float = 0.25,
    relay: int = 1
) -> LoadTestResult:

    # --- Color helpers ---
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"

    def color_val(value, ok):
        return f"{GREEN}{value}{RESET}" if ok else f"{RED}{value}{RESET}"

    def is_in_range(p):
        if min_power_thresh is not None and p < min_power_thresh:
            return False
        if max_power_thresh is not None and p > max_power_thresh:
            return False
        return True

    # --- Measurement window ---
    def measure_power_window():
        power_measurements = []
        spinner = ["|", "/", "-", "\\"]
        i = 0

        time.sleep(2.0)
        start_time = time.time()

        while time.time() - start_time < hold_time_seconds:
            try:
                power = load_mach.measurePower()
            except load_mach.visa.errors.VisaIOError as e:
                print(f"Load-01 Visa IO Timeout Error: {e}")
                return None
            except Exception as e:
                print(f"Unexpected error during power check: {e}")
                return None

            power_measurements.append(power)

            colored_power = color_val(power, is_in_range(power))
            print(f"Power: {colored_power} W {spinner[i % 4]}", end="\r")

            i += 1
            time.sleep(measure_every_seconds)

        # Print final list with color
        print("\nFinal Power Measurements:")
        colored_list = [color_val(p, is_in_range(p)) for p in power_measurements]
        print("[ " + ", ".join(colored_list) + " ]")

        return power_measurements

    # --- Stats ---
    def compute_stats(measurements):
        middle_value = lambda nums: sorted(nums)[len(nums)//2 - (1 if len(nums)%2==0 else 0)]

        avg_power = sum(measurements) / len(measurements)
        median_power = middle_value(measurements)
        min_power = min(measurements)
        max_power = max(measurements)

        return avg_power, median_power, min_power, max_power

    # --- Threshold evaluation ---
    def evaluate_thresholds(avg_power, median_power):
        failures = []

        # Min threshold
        if min_power_thresh is not None:
            if avg_power < min_power_thresh:
                failures.append(f"Average: {avg_power}")
            if median_power < min_power_thresh:
                failures.append(f"Median: {median_power}")

            if failures:
                return (
                    "min",
                    failures,
                    f"Expected at least {min_power_thresh} watts."
                )

        failures = []

        # Max threshold
        if max_power_thresh is not None:
            if avg_power > max_power_thresh:
                failures.append(f"Average: {avg_power}")
            if median_power > max_power_thresh:
                failures.append(f"Median: {median_power}")

            if failures:
                return (
                    "max",
                    failures,
                    f"Expected at most {max_power_thresh} watts."
                )

        return None

    # --- Main retry loop ---
    while True:
        measurements = measure_power_window()
        if measurements is None:
            return LoadTestResult(False, None, None, None, None)

        avg_power, median_power, min_power, max_power = compute_stats(measurements)

        print(f"\nSummary Channel {relay}:")
        print(f"{color_val(value = f'Average Power: {avg_power}', ok = is_in_range(avg_power))} W")
        print(f"{color_val(value = f'Median Power: {median_power}', ok = is_in_range(median_power))} W")
        print(f"{color_val(value = f'Minimum Power: {min_power}', ok = is_in_range(min_power))} W")
        print(f"{color_val(value = f'Maximum Power: {max_power}', ok = is_in_range(max_power))} W")

        result = evaluate_thresholds(avg_power, median_power)

        if result is None:
            write.updateLog('test_load', relay, 'pass power', avg_power)
            return LoadTestResult(True, avg_power, median_power, min_power, max_power)

        fail_type, failures, expectation = result
        fail_str = ", ".join(failures)

        load_mach.setOutputOn(False)
        print(f"Failed {fail_type} power test at {fail_str}. {expectation}")

        p = prompt.abort_retry_ignore_prompt(
            "Power Measure Fail",
            f"Power Measure Fail. Measured {fail_str}. {expectation}"
        )

        if p == "abort":
            print("\nAbort was selected. Process ended.")
            return LoadTestResult(False, avg_power, median_power, min_power, max_power)

        elif p == "retry":
            print("Retrying...")
            time.sleep(3.0)
            continue  # retry loop

        elif p == "ignore":
            print("Ignore was selected. Continuing test...")
            write.updateLog('test_load', relay, 'fail power', avg_power)
            return LoadTestResult(True, avg_power, median_power, min_power, max_power)

def test_single_load(ctx: TestContext, test_load: dict) -> bool:
    """Tests a load based on parameters defined in the test load argument."""
    Device = ctx.Device # TODO REMEMBER TO PUT THIS IN A DEVICE SELECTER AND REPLACE ctx LATER

    load_test_settings: SingleLoadTestSettings = parse_single_load_test_settings(ctx, test_load)
    
    Device.procedure().before_load_relays(ctx, test_load) 

    if load_test_settings is None: return True

    time.sleep(0.5)

    # Set Relays Bool allows testing first listed relay or all relays
    # TODO Scale to accept relay as an input perhaps, put in TestProcedure before_load_step/sequence???
    if load_test_settings.sweep_channel_first: all_relays = [ctx.current_relay]
    else: all_relays = Device.relays()
    # relays = all_relays[0] if getattr(load_test_settings, "sweep_channel_first", False) else all_relays
    
    # print("relays:", all_relays)
    ran_once = False
    for relay in all_relays:
        # vvv Relays are ['output1,'output2'] for node90, ['output1'] for supernode (uses mux instead), and
        step = relay if isinstance(relay, int) else relay[-1] # TODO This is a shitty bandaid for the fact that some devices have relays listed as integers and some as strings. 
        Device.procedure().set_relays(step)
        ctx.current_relay = step

        # Set load based on load test settings. NOTE We do this per relay in case the operator makes manual adjustments in between relays
        if load_test_settings.load_cr is not None: load_mach.setResistance(load_test_settings.load_cr)
        elif load_test_settings.load_cv is not None: load_mach.setVoltage(load_test_settings.load_cv)
        elif load_test_settings.load_cc is not None: load_mach.setCurrent(load_test_settings.load_cc) # Make it increase to ideal value over time if load mach sucks
                
        # SET OUTPUT ON AND MEASURE POWER
        time.sleep(1.0)
        time.sleep(load_test_settings.time_before_load_on)
        # ^ TODO MOVE THIS IN GENERAL PARSER

        Device.procedure().before_load_output_on(ctx, test_load, step)

        if load_test_settings.turn_load_off_after or not ran_once:
            load_mach.setOutputOn(True)

        if load_test_settings is None: return True

        result = moving_power_check(
            min_power_thresh=load_test_settings.min_power_thresh,
            max_power_thresh=load_test_settings.max_power_thresh,
            hold_time_seconds=load_test_settings.hold_load_time,
            measure_every_seconds=load_test_settings.measure_every_seconds,
            relay=relay
        )

        Device.procedure().before_load_output_off(ctx, test_load, step)
        if load_test_settings.turn_load_off_after: load_mach.setOutputOn(False)

        if not result.status:
            ctx.add_notes(round(result.average_power, 5))
            # updateTestNotes(round(result.average_power,5))
            return False

        # Successful measurement
        ctx.add_notes(round(result.average_power, 5))     
        # updateTestNotes(round(result.average_power,5)) 

        ran_once = True   
    
    # if ctx.supernode_test: load_mach.setOutputOn(False)
    return True

def test_loads(ctx: TestContext, test_loads: dict) -> bool:
    print(f"\033[94mRunning Loads Test\033[0m")
    Device = ctx.Device
    test_pass = True

    ctx.general_load_settings = parse_general_load_test_settings(ctx=ctx, test_loads=test_loads)

    # Gets the load list from test loads dictionary and validates it
    test_loads_list = test_loads.get('test_steps', [])
    if not isinstance(test_loads_list, list):
        print(f"Invalid test_loads format: 'loads' should be a list of load dictionaries.")
        return False
    if not test_loads_list:
        print(f"No loads found in test_loads. Please ensure 'loads' key contains a list of load configurations.")
        return False
    
    if Device.procedure().custom_loads_test(ctx=ctx, test_loads=test_loads_list): return True

    # # TODO DELETE LATER
    # if ctx.mini_node_test: 
    #     print("Testing Mini Node Loads")
    #     if not mnode.loads_test(test_loads): return False
    #     return True

    Device.procedure().before_load_sequence(ctx=ctx, test_loads=test_loads_list) # NOTE Used to be in for loop
    
    all_relays = Device.relays()
    if ctx.general_load_settings.sweep_channel_first:
        print(f"\n\033[3;94mSWEEPING CHANNELS FIRST: Testing relays in order {Device.relays()} with all load settings, then moving to next relay.\033[0m")
        relays = all_relays
    else: relays = [ctx.current_relay]

    for relay in relays:
        # step = relay if isinstance(relay, int) else relay[-1] # TODO This is a shitty bandaid for the fact that some devices have relays listed as integers and some as strings.
        Device.procedure().set_relays(relay)
        ctx.current_relay = relay
        for index,test_load in enumerate(test_loads_list):
            if not test_single_load(ctx, test_load): test_pass = False
        if not ctx.general_load_settings.sweep_channel_first: break

    load_mach.setOutputOn(False)

    if test_pass:
        write.updateLog('test_loads','pass')
        return True
    
    write.updateLog('test_loads','fail')
    return False