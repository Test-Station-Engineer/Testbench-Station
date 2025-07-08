# coap_client.py
import asyncio
from aiocoap import *
from cbor2 import loads, dumps
import socket

import time

# resource = '/actuators/actuator1''
# data = {'maxw':'713'}
async def asyncPut(ip_address,resource,data):
    protocol = await Context.create_client_context()
    uri = 'coap://'+ip_address+'/inx'+resource
    payload = dumps({'e':data})
    #request = Message(code=PUT, mtype=CON, payload=payload, uri=uri)
    request = Message(code=PUT, mtype=CON, payload=payload, uri=uri, content_format=ContentFormat.CBOR)
    try:
        response = await protocol.request(request).response
    except Exception as e:
        print('Failed to fetch resource:')
        print(e)
    #else:
    #    print('Result: %s\n%r'%(response.code, response.payload))

def put(ip_address,resource,data):
    asyncio.run(asyncPut(ip_address,resource,data))

def putValue(ip_address,resource,key,value):
    put(ip_address,resource,{key:value})

def putValueBcast(ip_address,resource,key,value):
    port = 5683
    mtype = CON
    uri = 'coap://'+ip_address+'/inx'+resource
    payload = dumps({'e':{key:value}})
    #request = Message(code=PUT, mtype=mtype, payload=payload, uri=uri, mid=0)
    request = Message(code=PUT, mtype=mtype, payload=payload, uri=uri, mid=0, content_format=ContentFormat.CBOR)
    #print(request.encode())
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(request.encode(), (ip_address, port))
    sock.close()

def putValueMcast(ip_address,resource,key,value):
    port = 5683
    mtype = CON
    uri = 'coap://'+ip_address+'/inx'+resource
    payload = dumps({'e':{key:value}})
    #request = Message(code=PUT, mtype=mtype, payload=payload, uri=uri, mid=0)
    request = Message(code=PUT, mtype=mtype, payload=payload, uri=uri, mid=0, content_format=ContentFormat.CBOR)
    #print(request.encode())
    MULTICAST_TTL = 1
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
    sock.sendto(request.encode(), (ip_address, port))
    sock.close() 

async def asyncGet(ip_address,resource):
    protocol = await Context.create_client_context()
    uri = 'coap://'+ip_address+'/inx'+resource
    # both CON and NON work
    #request = Message(code=GET, mtype=NON, uri=uri, content_format=ContentFormat.CBOR)
    request = Message(code=GET, mtype=CON, uri=uri, content_format=ContentFormat.CBOR)
    data = {}
    try:
        response = await protocol.request(request).response
    except Exception as e:
        print('Failed to fetch resource:')
        print(e)
    else:
        #print('Result: %s\n%r'%(response.code, response.payload))
        #print('decoded payload',loads(response.payload, str_errors='replace'))
        data = loads(response.payload, str_errors='replace')['e']
    return data

def getUcast(ip_address,resource,timeout):
    port = 5683
    mtype = NON
    uri = 'coap://'+ip_address+'/inx'+resource
    request = Message(code=GET, mtype=mtype, uri=uri, mid=0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(timeout)
    sock.sendto(request.encode(), (ip_address, port))
    try:
        response = sock.recv(1024)
    except:
        response = b''
    sock.close()
    if len(response)>7:
        payload = response[7:]
        try:
            data = loads(payload, str_errors='replace')['e']
            return data
        except Exception:
            try:
                payload = response[12:]
                data = loads(payload, str_errors='replace')['e']
                return data
            except Exception:
                return None
    return None

def getBcast(ip_address,resource):
    port = 5683
    mtype = CON
    uri = 'coap://'+ip_address+'/inx'+resource
    request = Message(code=GET, mtype=mtype, uri=uri, mid=0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(request.encode(), (ip_address, port))
    sock.close()

def get(ip_address,resource):
    return asyncio.run(asyncGet(ip_address,resource))

def getValue(ip_address,resource,key):
    try:
        return get(ip_address,resource)[key]
    except:
        return ''
    
# Checks to see if connection was lost
async def check_ip(ip_address, resource='/network',key = 'cmd',value='set_cccv 3 3', timeout=3):
    """Check if the device with the given IP address is reachable within the specified timeout."""
    try:
        # Set a timeout for the GET request
        data = await asyncio.wait_for(putValue(ip_address,resource,key,value), timeout)
        if data:
            print("Data is",data)
            return True  # The device responded
    except asyncio.TimeoutError:
        print(f"Timeout: No response from {ip_address} after {timeout} seconds.")
    except Exception as e:
        print(f"Error while trying to reach {ip_address}: {e}")
    
    return False  # No response, IP is probably not reachable

def is_ip_reachable(ip_address, resource='/network',key = 'cmd',value='set_cccv 3 3', timeout=3):
    """Blocking call to check if the device IP is reachable."""
    return asyncio.run(check_ip(ip_address, resource, key, value, timeout))

def getSN(ip_address):
    return getValue(ip_address,'/network','serialnum')

def getMAC(ip_address):
    return getValue(ip_address,'/network','emac')

def setSN(ip_address,sn):
    putValue(ip_address,'/network','serialnum',sn)

def getINXIP(ip_address):
    return getValue(ip_address,'/network','inxip')

def setINXIP(ip_address,inx_ip):
    putValue(ip_address,'/network','inxip',inx_ip)

def getTFTPIP(ip_address):
    return getValue(ip_address,'/dfd','tsrv')

def setTFTPIP(ip_address,tftp_ip):
    putValue(ip_address,'/dfd','tsrv',tftp_ip)

def getExpectedVersion(ip_address):
    return getValue(ip_address,'/dfd','erev')

def setExpectedVersion(ip_address,expected_version):
    putValue(ip_address,'/dfd','erev',expected_version)

def getDFDVersion(ip_address):
    return getValue(ip_address,'/dfd','frev')

def getGoldenVersion(ip_address):
    return getValue(ip_address,'/dfd','grev')

def getDFUVersion(ip_address):
    return getValue(ip_address,'/dfu','frev')

def getBoardVersion(ip_address):
    return getValue(ip_address,'/dfd','bver')

def getCCCV(ip_address,channel):
    return getValue(ip_address,'/actuators/actuator'+str(channel),'cccv')

def setCCCV(ip_address,channel,stage): # Unused
    #putValue(ip_address,'/actuators/actuator'+str(channel),'cccv',str(stage))
    putValue(ip_address,'/network','cmd','set_cccv '+str(channel)+' '+str(stage))

def getMaxWatt(ip_address,channel):
    value = getValue(ip_address,'/actuators/actuator'+str(channel),'maxw')
    try:
        return round(float(value)/10,1)
    except:
        return 0

def setMaxWatt(ip_address,channel,maxwatt):
    putValue(ip_address,'/network','cmd','set_max_watt '+str(channel)+' '+str(int(maxwatt)))

def getPWMFrequency(ip_address):
    value = getValue(ip_address,'/actuators/actuator1','pwmfreq')
    try:
        return int(round(float(value),0))
    except:
        return 0

def setPWMFrequency(ip_address,frequency):
    putValue(ip_address,'/actuators/actuator1','pwmfreq',str(frequency))

def getDim(ip_address,channel):
    return getValue(ip_address,'/actuators/actuator'+str(channel),'pp')

def setDim(ip_address,channel,dim):
    putValue(ip_address,'/network','cmd','set_dim '+str(channel)+' '+str(dim))

def getSentype(ip_address,channel):
    if channel == 0: return putValue(ip_address,'/network','cmd','get_input_type sentype')
    else: return getValue(ip_address,'/sensors/input'+str(channel),'sentype')

def setSentype(ip_address,channel,sentype):
    if channel == 0: putValue(ip_address,'/network','cmd','set_input_type sentype'+str(sentype))
    else: putValue(ip_address,'/sensors/input'+str(channel),'sentype',str(sentype)) # change sensor 1 events supernode version

def getEventLH(ip_address,channel):
    return getValue(ip_address,'/sensors/input'+str(channel),'eventlh')

def setEventLH(ip_address,channel,eventlh):
    if channel == 0: putValue(ip_address,'/network','cmd','set_input_type eventlh'+str(eventlh))
    else: putValue(ip_address,'/sensors/input'+str(channel),'eventlh',str(eventlh))

def getEventHL(ip_address,channel):
    return getValue(ip_address,'/sensors/input'+str(channel),'eventhl')

def setEventHL(ip_address,channel,eventhl):
    if channel == 0: putValue(ip_address,'/network','cmd','set_input_type eventhl'+str(eventhl))
    else: putValue(ip_address,'/sensors/input'+str(channel),'eventhl',str(eventhl))

def secure_setting(ip_address: str,resource: str,key: str,value,verbose: bool = False):
    for i in range(1,10):    
        #print(power)
        putValue(ip_address,resource,key,value)
        get_setting = getValue(ip_address,resource,key)
        if value == get_setting:
            if verbose or i > 1: print(f"{resource,key} assigned as {get_setting}. It took {i} tries")
            return True
        time.sleep(0.25)
    if value is not get_setting:
        print("Failed to set",key,"of resource",resource,"to",value,"after",i,"retries.")
        return False

def set_lldp(ip_address,state: bool): 
    secure_setting(ip_address,'/network','lldp_enable',str(state).lower())