# coap_client.py
import asyncio
from aiocoap import *
from cbor2 import loads, dumps
import socket

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
        except:
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

def getSN(ip_address):
    return getValue(ip_address,'/network','serialnum')

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

def setCCCV(ip_address,channel,stage):
    #putValue(ip_address,'/actuators/actuator'+str(channel),'cccv',str(stage))
    putValue(ip_address,'/network','cmd','set_cccv '+str(channel)+' '+str(stage))

def getMaxWatt(ip_address,channel):
    value = getValue(ip_address,'/actuators/actuator'+str(channel),'maxw')
    try:
        return round(float(value)/10,1)
    except:
        return 0

def setMaxWatt(ip_address,channel,maxwatt):
    putValue(ip_address,'/network','cmd','set_max_watt '+str(channel)+' '+str(int(maxwatt*10)))

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

    
