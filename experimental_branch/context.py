
# context.py
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class TestContext:
    # Identifiers
    test_id: str = '1'          # I should remove this @ some point, it's useless

    serial_number: str = ''     # Serial number of device under test
    mac_address: str = ''       # MAC address of device under test
    custom_sn: str = ''         # Custom serial number for certain devices (TODO Unsure if still used)
    board_version: str = ''     # Board version of device under test
    device: str = ''            # Device type (e.g., Mini-Node, ELS-Node, etc.) Used for CSV logging

    # Final results
    status: str = "Pass"
    notes: List[str] = field(default_factory=list)

    # Environment
    ip: str = ""
    node_channels: int = 2      # How many channels for a node. 2 by default

    # Device Flags (formerly globals)
    mini_node: bool = False
    els_node: bool = False
    usbc_node: bool = False
    supernode: bool = False
    battery_backup: bool = False

    # YAML configs
    general_settings_config: Dict = field(default_factory=dict)
    test_config: Dict = field(default_factory=dict)

    # Settings
    microcontroller_port: str = 'COM3'                  # The COM port for the microcontroller connection, MAKE SURE THIS IS SET IN GENERAL SETTINGS YAML
    # microcontroller_port: str = '/dev/ttyUSB0'         # Linux version
    baud: int = 115200                                  # Baud rate for microcontroller connection
    microcontroller_timeout: int = 0                    # timeout for connecting to microcontroller COM port (in seconds); 0 = no timeout

    # CSV batch info
    csv_file_name: str = ""
    batch_csv_file: str = "test_batch.csv"

    ########################################### Go through things below this line later #####################################################

    stop_on_failure: bool = False       # Whether or not to stop the test on first failure
    update_golden: bool = False         # Whether or not to update the golden firmware on code version mismatch (NO LONGER USED)
    require_golden_match: bool = False  # Whether or not to require the golden firmware to match the code version (NO LONGER USED)
    debug_print: bool = False           # Unsure if used
    dfd_match_required: bool = False    # Whether or not to require the DFD firmware to match the code version


    scan_sn: bool = True        # Set to false by default if we implement COM-based discovery again (cut feature unfortunately)
    # database.skip_db = True   # Database functions are defunct (NO LONGER USED) 

    maxw_save = None            # TODO CHECK IF THIS IS NECESSARY LATER
    cccv_save = None            # TODO CHECK IF THIS IS NECESSARY LATER

    CC_yaml: bool = False   # Generalize all devices to use the same name convention for bools and standardize the logic between them
    CV_yaml: bool = False   # Instead of having a set of yaml bools that are used differently 
    CCUV_yaml: bool = False # than the already differently named [device]_test bools

    # DEVICE IDENTIFICATION (All 'test' bools are used to handle special quirks involved with an otherwise standardized test procedure)
    mini_node_test: bool = False        
    els_node_test: bool = False
    usbc_node_test: bool = False
    usbc_current_channel = ''           # NEED TO GENERALIZE USBC LOAD TEST FUNCTION TO WORK WITHIN STANDARD TEST LOAD FUNCTION USING YAML
    supernode_test: bool = False
    battery_backup_test: bool = False   # STILL NEED TO GIVE THIS ITS OWN .PY FILE FOR DEVICE-SPECIFIC FUNCTIONS

    # Allows testbench to look for a device with leading digits provided in an argument and 
    # sets the serial number of that device to the serial number argument
    # NOT BEING USED CURRENTLY, CAN REMOVE
    set_sn: bool = False
    sn_leading_digits_to_set_sn: str = ''

    scan_timeout = 0.1
    scan_range_start = 2
    scan_range_end = 255

    prompt_continue_key: str = 'DOWN'
    prompt_end_test_key: str = 'Esc'

    test_status: str = 'Pass'  # Overall test status, Pass by default
    test_notes: list = []
    csv_arg_file_name: str = ''

    
    # ─────────────────────────────────────────────
    # Result Tracking
    # ─────────────────────────────────────────────
    test_status: str = "Pass"       # Overall test status
    test_notes: List[str] = field(default_factory=list)

    def add_notes(self, *notes):
        """Convenience helper to record notes."""
        for n in notes:
            self.test_notes.append(str(n))

    # ─────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────
    def mark_fail(self, reason: str = ""):
        """Convenience method to mark the test as failed."""
        self.test_status = "Fail"
        if reason:
            self.add_notes(reason)
