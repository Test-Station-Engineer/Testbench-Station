# network.py
import subprocess

from context import TestContext
from services import coap_client_scan

from write import write

def _derive_subnet_from_host() -> str:
    host_ip = subprocess.run(['hostname', '-I'], stdout=subprocess.PIPE) \
                        .stdout.decode('utf-8').split(' ')[0]
    print("USING HOST IP. HOST IP IS:", host_ip)
    parts = host_ip.split('.')
    if len(parts) == 4:
        parts[3] = '255'
        return '.'.join(parts)
    return '192.168.1.255'

def get_ip(ctx: TestContext) -> bool:
    """
    Discover device IP, using ctx.general_settings_config for subnet/scan parameters.
    Populates ctx.ip on success. Returns True/False.
    """

    write.updateLog('getIP','start')
    #if mini_node_test: coap_client_scan.is_mini_node = True

    # Mini-node flag still toggles a scan behavior flag
    if ctx.mini_node_test:
        coap_client_scan.is_mini_node = True

    # --- Configure scan parameters from general_settings.yaml (if present)
    gs = ctx.general_settings_config or {}
    
    if 'subnet' in gs and gs['subnet']:
        coap_client_scan.subnet = gs['subnet']
    else:
        # Derive subnet from host IP (legacy logic)
        try:
            coap_client_scan.subnet = gs.get('subnet') or _derive_subnet_from_host()
            # host_ip = subprocess.run(['hostname', '-I'], stdout=subprocess.PIPE) \
            #                     .stdout.decode('utf-8').split(' ')[0]
            # print("USING HOST IP. HOST IP IS: ",host_ip)
            # parts = host_ip.split('.')
            # if len(parts) == 4:
            #     parts[3] = '255'
            #     coap_client_scan.subnet = '.'.join(parts)
            # else:
            #     print("Unexpected host IP format; defaulting subnet to 255 broadcast on 192.168.2.x")
            #     coap_client_scan.subnet = '192.168.2.255'
        except Exception as e:
            print("Failed to derive subnet from host IP:", e)
            coap_client_scan.subnet = '192.168.2.255'

    # Scan tuning  
    ctx.scan_timeout = gs.get('scan_timeout', ctx.scan_timeout)
    ctx.scan_range_start = gs.get('scan_start', ctx.scan_range_start)
    ctx.scan_range_end = gs.get('scan_end', ctx.scan_range_end)

    # --- Decide scanning mode
    if ctx.scan_sn:
        # Set the scan matching mode (by SN exact or leading digits for set_sn)
        
        if ctx.set_sn and ctx.sn_leading_digits_to_set_sn:
            print('scan subnet', coap_client_scan.subnet,
                  'for device with leading sn digit(s):', ctx.sn_leading_digits_to_set_sn)
            coap_client_scan.serial_number = ctx.sn_leading_digits_to_set_sn
            coap_client_scan.scan_for_leading_digits = True
        else:
            print('scan subnet', coap_client_scan.subnet, 'for sn', ctx.serial_number)
            coap_client_scan.serial_number = ctx.serial_number
            coap_client_scan.scan_for_leading_digits = False

        # Perform the scan
        coap_client_scan.scan(ctx.scan_range_start, ctx.scan_range_end, ctx.scan_timeout)

        # Evaluate scan results
        for node in getattr(coap_client_scan, 'nodes', []):
            try:
                node_sn = node['network']['serialnum']
                node_ip = node['ip']
            except Exception:
                continue

            # Normal mode: exact match
            if not ctx.set_sn and node_sn == ctx.serial_number:
                ctx.ip = node_ip
                print('scan found sn', ctx.serial_number, 'at', ctx.ip)
                write.updateLog('getIP', ctx.ip)
                return True

            # Set-SN mode: leading digits match
            if ctx.set_sn and ctx.sn_leading_digits_to_set_sn \
               and node_sn.startswith(ctx.sn_leading_digits_to_set_sn):
                ctx.ip = node_ip
                print('scan found sn leading digits', ctx.sn_leading_digits_to_set_sn, 'at', ctx.ip)
                write.updateLog('getIP', ctx.ip)
                return True

        # No match found via scan
        write.updateLog('getIP', 'failed')
        return False
    
def testSubnet(ctx, subnet) -> bool:
    # ip_split = ctx.ip.split('.')
    ip_split = (ctx.ip or '').split('.')
    subnet_split = subnet.split('.')
    if len(ip_split) != 4:
        write.updateLog('testSubnet','fail ip length')
        return False
    if len(subnet_split) != 4:
        write.updateLog('testSubnet','fail subnet length')
        return False
    for i in range(0,4):
        if subnet_split[i] == '255':
            return True
        if ip_split[i] != subnet_split[i]:
            write.updateLog('testSubnet','fail subnet mismatch')
            print("IP Split:",ip_split)
            print("Subnet Split:",subnet_split)
            return False
    write.updateLog('testSubnet','ip == subnet')
    return True