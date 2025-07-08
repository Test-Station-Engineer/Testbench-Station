# coap_client_scan.py
import coap_client
import socket
import time
import sys

import keyboard

nodes = []
scan_for_leading_digits: bool = False

is_mini_node = False

def getIP():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

ip_address=str(getIP())
#print('ip_address',ip_address)

ip_address_split = ip_address.split('.')
ip_address_split[3] = '255'
broadcast_ip_address = '.'.join(ip_address_split)
#print('broadcast_ip_address',broadcast_ip_address)

def putBcastINXIP(new_ip):
    coap_client.putValueBcast(broadcast_ip_address,'/network','inxip',new_ip)

subnet = ip_address
serial_number = ''
def scan(range_start=2,range_end=255):
    global ip_address_split, ip_address, nodes
    ip_address_split = subnet.split('.')
    ip_address_split[3] = str(range_start)
    ip_start = '.'.join(ip_address_split)
    ip_address_split[3] = str(range_end)
    ip_end = '.'.join(ip_address_split)
    print('Scan range',ip_start,'to',ip_end)
    if range_start < 2 or range_end > 255 or range_end <= range_start:
        print('Scan range error')
        return []
    print('Start scan...')
    nodes = []
    start = time.time()
    for i in range(range_start,range_end):
    #for i in range(20,30):

        if keyboard.is_pressed('esc'):
            print("\nScan terminated by user.")
            return nodes
        
        progress = '\r'+str(int(100*(i+1)/(range_end-range_start)))+'%'
        print(progress,end='')
        ip_address_split = subnet.split('.')
        ip_address_split[3] = str(i)
        test_ip_address = '.'.join(ip_address_split)
        if test_ip_address != ip_address:
            #print('scan',test_ip_address,end='')
            data = coap_client.getUcast(test_ip_address,'/network',0.1)
            if data:
                #print(' SN',data['serialnum'],test_ip_address)
                node = {'ip':test_ip_address,'network':data}
                if not is_mini_node:
                    node['dfd']=coap_client.getUcast(test_ip_address,'/dfd',0.1)
                    node['dfu']=coap_client.getUcast(test_ip_address,'/dfu',0.1)
                    context = coap_client.getUcast(test_ip_address,'/actuators/actuator1/context',0.1)
                    try:
                        if "keyw" in context:
                            node['cluster']=context["keyw"][0]
                        else:
                            node['cluster']=''
                    except:
                        print("\nCONTEXT ERROR - UPDATING NODE DB")
                        coap_client.putValue(test_ip_address,'/network','cmd','update_db')
                nodes.append(node)
                if scan_for_leading_digits:
                    if node['network']['serialnum'][:len(serial_number)] == serial_number:
                        break
                if serial_number != '' and node['network']['serialnum'] == serial_number:
                    break
            else:
                #print(' not a node')
                pass
    print('\r100% ')
    print('Scan found',len(nodes),'nodes')
    elapsed = round(time.time() - start,1)
    print('Scan complete in',elapsed,'s')
    return nodes

resource_keys = [
    ["SN","network","serialnum"],
    ["emac","network","emac"],
    ["","dfd","bver"],
    ["","ip",""],
    ["dfd_ver","dfd","frev"],
    ["dfu_ver","dfu","frev"]
]

def printNodes():
    global nodes
    print('Print nodes...')
    for node in nodes:
        for key in resource_keys:
            print(' ',end='')
            if key[2] == '':
                if key[0] != '':
                    print(key[0],node[key[1]],end='')
                else:
                    print(node[key[1]],end='')
            elif key[2] in node[key[1]]:
                if key[0] != '':
                    print(key[0],node[key[1]][key[2]],end='')
                else:
                    print(node[key[1]][key[2]],end='')
        print('')
    print('Print nodes complete')

def start():
    #putBcastINXIP(ip_address) # set our ip_address as inxip
    scan()
    printNodes()

def stop():
    return

def main(argv, arc):
    global subnet
    if arc > 1:
        subnet = argv[1]
        print('subnet',subnet)
    start()

if __name__ == '__main__':
    main(sys.argv, len(sys.argv))

