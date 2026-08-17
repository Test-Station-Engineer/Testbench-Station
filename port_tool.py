import pyvisa
from serial import Serial
from serial.tools import list_ports

from config import config

port_debug = False

# ---------------------------------------------------------------------------
# VISA
# ---------------------------------------------------------------------------

rm = pyvisa.ResourceManager('@py')

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def get_candidates(instrument):
    """
    Return the configured candidates for an instrument.
    """
    return config["instruments"][instrument]["candidates"]


def open_instrument(instrument):
    """
    Try each candidate in order and open the first matching device.

    A candidate matches only if every property specified in the candidate
    matches the discovered device.

    Raises:
        RuntimeError: If no candidate matches any connected device.
    """
    candidates = get_candidates(instrument)
    for index, candidate in enumerate(candidates, start=1):

        device_type = candidate.get("type")

        if not device_type:
            print(f"WARNING: Candidate {index} has no 'type'. Skipping.")
            continue

        if port_debug: print(f"\nChecking candidate {index}: {candidate}")

        if device_type in ("usbtmc", "visa"):
            inst = _open_visa(candidate)

        elif device_type == "serial":
            inst = _open_serial(candidate)

        else:
            print(
                f"WARNING: Unknown device type '{device_type}' "
                f"in candidate {index}. Skipping."
            )
            continue

        if inst is not None:
            print(f"Opened {instrument} with candidate {index}.")
            return inst

    raise RuntimeError("No matching instrument found.")


# ---------------------------------------------------------------------------
# VISA / USBTMC
# ---------------------------------------------------------------------------

def _open_visa(candidate):
    """
    Search VISA resources for an instrument matching the candidate.

    USB VID/PID are used to filter candidate serial interfaces before
    opening them with VISA. Once a likely resource is found, *IDN? is
    used to identify the actual instrument.
    """

    resources = rm.list_resources("?*USB?*INSTR")

    if not resources:
        print("  No USB VISA resources found.")
        return None

    for resource in resources:

        if port_debug: print(f"  Checking VISA resource: {resource}")

        # If this is an ASRL resource, identify the underlying USB device
        # before opening it.
        if resource.startswith("ASRL"):
            if candidate.get("type") == "usbtmc":
                continue

            # Stage 1: safely inspect USB information using pyserial.
            port = _get_serial_port_from_visa_resource(resource)

            if port is None:
                continue

            if not _usb_candidate_matches(candidate, port):
                continue

        # Stage 2: actually open the candidate VISA resource
        inst = None

        try:
            inst = rm.open_resource(resource)

            # Short timeout while probing.
            inst.timeout = 1000

            idn = inst.query("*IDN?").strip()

            print(f"    *IDN? -> {idn}")

            if _visa_candidate_matches(candidate, idn):

                # Restore normal operating timeout.
                inst.timeout = 10000

                print(f"    MATCH: {resource}")
                return inst

            print("    Not a match.")

            inst.close()

        except Exception as e:

            print(
                f"    Could not communicate with {resource}: {e}"
            )

            if inst is not None:
                try:
                    inst.close()
                except Exception:
                    pass

    return None

def _visa_candidate_matches(candidate, idn):
    """
    Determine whether an instrument's *IDN? response matches the candidate.

    Currently supported identifying fields:

        manufacturer
        model
        serial

    All fields specified in the candidate must match.

    Example:

        manufacturer: ARRAY
        model: 3721A

    requires both ARRAY and 3721A to appear in the identification.
    """

    parts = [part.strip() for part in idn.split(",")]

    # Standard *IDN? format is generally:
    #
    #   MANUFACTURER,MODEL,SERIAL_NUMBER,VERSION
    #
    # Your ARRAY currently reports:
    #
    #   ARRAY,3721A,0,1.43-0.0-0.0

    actual = {
        "manufacturer": parts[0] if len(parts) > 0 else None,
        "model": parts[1] if len(parts) > 1 else None,
        "serial": parts[2] if len(parts) > 2 else None,
    }

    for field in ("manufacturer", "model", "serial"):

        expected = candidate.get(field)

        # Field wasn't specified in YAML.
        if expected is None:
            continue

        actual_value = actual.get(field)

        if actual_value is None:
            print(
                f"    Mismatch: {field} "
                f"(expected {expected!r}, but IDN did not provide it)"
            )
            return False

        if str(expected).lower() != str(actual_value).lower():
            print(
                f"    Mismatch: {field} "
                f"(expected {expected!r}, found {actual_value!r})"
            )
            return False

    return True

# ---------------------------------------------------------------------------
# Serial
# ---------------------------------------------------------------------------

def _open_serial(candidate, baudrate: int = 115200, timeout = 1.0):
    """
    Search connected serial devices for a device matching candidate.

    Supported matching fields:
        serial
        vid
        pid
        manufacturer
        product

    Optional opening field:
        baudrate
    """

    ports = list_ports.comports()

    if not ports:
        print("  No serial devices found.")
        return None

    for port in ports:

        if port_debug: print(f"  Checking serial device: {port.device}")

        if not _serial_candidate_matches(candidate, port):
            continue

        try:
            baud = candidate.get("baudrate", baudrate)

            device = Serial(
                port.device,
                baudrate=baud,
                timeout=timeout
            )

            if port_debug: print(f"  Found matching serial device: {port.device}")

            return device

        except Exception as e:
            print(
                f"  WARNING: Found matching device but could not open "
                f"{port.device}: {e}"
            )

            return None

    return None

def _get_serial_port_from_visa_resource(resource):
    """
    Find the pyserial port corresponding to a VISA ASRL resource.
    """

    # Example:
    #
    # ASRL/dev/ttyUSB3::INSTR
    #
    # -> /dev/ttyUSB3

    if not resource.startswith("ASRL"):
        return None

    port_name = resource[4:]

    if "::" in port_name:
        port_name = port_name.split("::")[0]

    for port in list_ports.comports():

        if port.device == port_name:
            return port

    return None

def _usb_candidate_matches(candidate, port):
    """
    Check USB-level identifying information before opening a VISA
    serial resource.

    Any USB fields specified in the candidate must match.
    """

    expected_values = {
        "usb_vid": port.vid,
        "usb_pid": port.pid,
        "usb_serial": port.serial_number,
    }

    for field, actual in expected_values.items():

        expected = candidate.get(field)

        # Not specified in YAML -> ignore it
        if expected is None:
            continue

        if field in ("usb_vid", "usb_pid"):
            matches = _numeric_values_match(expected, actual)
        else:
            matches = str(expected).lower() == str(actual).lower()

        if not matches:
            if port_debug:
                print(
                    f"    USB mismatch: {field} "
                    f"(expected {expected!r}, found {actual!r})"
                )
            return False

    return True

def _serial_candidate_matches(candidate, port):
    """
    Check whether a serial port matches every property specified
    in the candidate.

    This uses AND logic:

        serial + VID + PID

    means ALL THREE must match.

    Fields not specified in the candidate are ignored.
    """

    actual_values = {
        "serial": port.serial_number,
        "vid": port.vid,
        "pid": port.pid,
        "manufacturer": port.manufacturer,
        "product": port.product,
    }

    fields_to_check = (
        "serial",
        "vid",
        "pid",
        "manufacturer",
        "product",
    )

    for field in fields_to_check:

        expected = candidate.get(field)

        # This field wasn't specified in YAML.
        if expected is None:
            continue

        actual = actual_values[field]

        if not _values_match(field, expected, actual):

            if port_debug: print(
                f"    Mismatch: {field} "
                f"(expected {expected!r}, found {actual!r})"
            )

            return False

    return True


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------

def _values_match(field, expected, actual):
    """
    Compare a configured candidate value against a discovered value.
    """

    if actual is None:
        return False

    if field in ("vid", "pid"):
        return _numeric_values_match(expected, actual)

    # Strings such as manufacturer/product/serial.
    return str(expected).lower() == str(actual).lower()


def _numeric_values_match(expected, actual):
    """
    Compare numeric values while allowing YAML values such as:

        0x067B
        1659

    to match the integer returned by pyserial.
    """

    try:
        if isinstance(expected, str):
            expected = int(expected, 0)
        else:
            expected = int(expected)

        actual = int(actual)

        return expected == actual

    except (TypeError, ValueError):
        return False


def _format_hex_or_decimal(value):
    """
    Format a numeric value for searching inside a VISA resource string.

    For example:

        0xF4EC -> 'f4ec'
        62188  -> 'f4ec'

    Both forms are useful when inspecting VISA resource strings.
    """

    try:
        value = int(value)

        return f"{value:x}"

    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    try:
        load_candidates = get_candidates("load")

        load = open_instrument("load")

        print("\nLoad machine opened successfully.")
        print(load)

    except RuntimeError as e:
        print(f"\nERROR: {e}")