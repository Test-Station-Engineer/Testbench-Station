# database.py
import mysql.connector
from config import CONFIG
import time

cursor = None
cnx = None
connected = False
skip_db = False

def disconnect():
    global connected, cursor, cnx
    if connected:
        try:
            cnx.close()
            cursor.close()
            print("database - disconnected")
        except:
            print("database - error disconnecting")
        connected = False

def connect():
    global connected, cursor, cnx
    if skip_db:
        return True
    conn_counter = 0
    while not cnx:  
        try:
            print("checking for connection")
            conn_counter += 1
            cnx = mysql.connector.connect(
                host=CONFIG.DB_HOST,  # Replace with your MySQL server host
                user=CONFIG.DB_USER,  # Replace with your MySQL username
                password=CONFIG.DB_PASSWD,  # Replace with your MySQL password
                database=CONFIG.DB_NAME  # Replace with your MySQL database name
            )
            connected = True
        except Exception as e:
            if conn_counter > 5:
                print("database - No connection available in pool")
                connected = False
            time.sleep(0.5)
    if connected:
        print("database - connected")
        cursor = cnx.cursor()
    return connected

def updateTestLog(test_id,serial_number,board_version,desc):
    global connected, cursor, cnx
    if skip_db:
        return True
    elif not connected:
        return False
    try:
        
        # Insert/update into DB after detecting NodeID from DB using the IP. 
        # For each record in remote_programming_log, add a new column called 
        # status (varchar) and set it to what is printed above in each condition 
        sql = f"SELECT ID FROM pmi_node WHERE IPAddress = '{node['ip']}' AND Deleted=0"
        cursor.execute(sql)
        result = cursor.fetchone()
        print(result)
        if result:
            nid = result[0]
        #    sqlIU = f"INSERT INTO pmi_remote_programming_log (NodeID, IPAddress, ApplyVersion, Status, Description, RPId) VALUES ({nid}, '{node['ip']}', '{app_version}', '{node['match']}', '{desc}',{test_id})"
        #    cursor.execute(sqlIU)
        #    cnx.commit()
            sqlFetch = f"SELECT ID FROM pmi_remote_programming_log WHERE NodeID={nid} AND RPId={test_id}"
            cursor.execute(sqlFetch)
            row = cursor.fetchone()
            if row:
                sqlIU = f"UPDATE pmi_remote_programming_log SET ApplyVersion='{app_version}', Status='{node['match']}', Description='{desc}' WHERE ID={row[0]}"
            else:
                sqlIU = f"INSERT INTO pmi_remote_programming_log (NodeID, IPAddress, ApplyVersion, Status, Description, RPId) VALUES ({nid}, '{node['ip']}', '{app_version}', '{node['match']}', '{desc}',{test_id})"
            print("sqlIU: " + sqlIU) 
            cursor.execute(sqlIU)
            cnx.commit()
    except Exception as e:
        print("database - updateLog - error",e)
        return False
    return True

def updateTestTable(data, test_id):
    if skip_db:
        # print("skip db is on")
        return True
    elif not connected:
        print("Not connected")
        return False
    try:
        sql = "UPDATE pmi_remote_programming SET "
        dset = ""
        for key in data:
            if dset != "":
                dset += ", "
            dset += f"{key}='{data[key]}'"
        sql += dset + f" WHERE ID={test_id}"
        print(sql)
        cursor.execute(sql)
        cnx.commit()
    except Exception as e:
        print("database - updateTestTable - error","qry:",sql,"error:",e)
        return False
    return True
