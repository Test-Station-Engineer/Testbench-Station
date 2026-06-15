def runTest(ctx): #TODO No return type specified

    cfg = ctx.test_config

    #
    # ─────────────────────────────────────────────
    # 1. Code Version Test
    # ─────────────────────────────────────────────
    if 'code_version' in cfg:
        if testCodeVersion(ctx, cfg['code_version']):
            updateState('runTest','pass - code_version','Pass','code_version')
        else:
            updateState('runTest','fail - code_version','Fail','code_version')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    
    #
    # ─────────────────────────────────────────────
    # 2. Trigger Test (optional, probabilistic)
    # ─────────────────────────────────────────────
    if cfg.get('trigger_1_test'):
        chance = cfg.get('chance_to_test_trigger_1', 0)
        if random.random() < chance / 100:
            print("Starting Trigger 1 Test")
            attempts = cfg.get('number_of_trigger_1_attempts', 1)
            wait_sec = cfg.get('seconds_to_wait_for_restart', 5)
            if testTrigger(ctx, attempts, wait_sec):
                updateState('runTest', 'pass - trigger1', 'Pass', 'trigger1')
            else:
                updateState('runTest', 'fail - trigger1', 'Fail', 'trigger1')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False

    #
    # ─────────────────────────────────────────────
    # 3. Update DB flag (unchanged behavior)
    # ─────────────────────────────────────────────
    if cfg.get('update_db'):
        coap_client.putValue(ctx.ip, '/network', 'cmd', 'update_db')
        time.sleep(8.0)
    
    #
    # ─────────────────────────────────────────────
    # 4. Capture SN + MAC (after DB update)
    # ─────────────────────────────────────────────
    if not ctx.battery_backup_test:
        sn = coap_client.getSN(ctx.ip)
        ctx.serial_number = sn  # write into context
        if ctx.mini_node_test: 
            mac = coap_client.getValue(ctx.ip, '/network', 'mac')
        else:
            mac = coap_client.getMAC(ctx.ip)
        ctx.mac_address = str(mac).upper()
        updateLog('SN:', sn, 'MAC:', ctx.mac_address)
    else:
        # Battery Backup test uses a special SN provided earlier
        ctx.mac_address = 'N/A'
    
    #
    # ─────────────────────────────────────────────
    # 5. Device-specific initialization
    # ─────────────────────────────────────────────
    if ctx.mini_node_test:
        ctx.node_channels = 1
        mnode.init(ctx.ip, cfg, ctx.serial_number)
        print("Initializing Mini Node Test")


    elif ctx.els_node_test: 
        print("Initializing ELS test")
        coap_client.putValue(ctx.ip,'/actuators/actuator1','els','true')
        coap_client.putValue(ctx.ip,'/actuators/actuator1','els','true')
        coap_client.putValue(ctx.ip,'/actuators/actuator1','dimels',100)
        coap_client.putValue(ctx.ip,'/actuators/actuator2','dimels',100)

    elif ctx.usbc_node_test: 
        print("Initializing USBC Node Test")
    elif ctx.battery_backup_test:
        print("Initializing battery backup test")
    elif ctx.supernode_test:
        ctx.node_channels = 8
        print("Initializing supernode test")
        snode.init(ctx.ip, cfg)

        
        # igain setup logic
        igain_var = 'cv_igain10'
        if ctx.device_name in ('Supernode CC', 'Supernode'):
            igain_var = 'cc_igain10'
        for target in [(igain_var, 7), ('cv_igain10', 15)]:
            name, val = target
            for attempt in range(10):
                coap_client.putValue(ctx.ip,'/actuators/actuator1',name,val)
                got = coap_client.getValue(ctx.ip,'/actuators/actuator1',name)
                if got == val:
                    print(name, "has been set to", got)
                    break
                else:
                    print(name, "failed to set to", val, "after", attempt+1, "retries")

        for i in range(1,8):
            coap_client.putValue(ctx.ip,'/sensors/input'+str(i),'sentype','disable') # change sensor 1 events supernode version
            coap_client.putValue(ctx.ip,'/sensors/input'+str(i),'eventlh','default') 
            coap_client.putValue(ctx.ip,'/sensors/input'+str(i),'eventhl','default') # change sensor 1 events supernode version

    else:
        if not ctx.mini_node_test:
            coap_client.putValue(ctx.ip,'/network','cmd','set_ws 0')
            coap_client.putValue(ctx.ip,'/network','cmd','set_max_amp 3 2500')
        
    #
    # ─────────────────────────────────────────────
    # 6. Subnet Validation
    # ─────────────────────────────────────────────
    if 'subnet' in cfg:
        if testSubnet(ctx, cfg['subnet']):
            updateState('runTest','pass - subnet','Pass','subnet')
        else:
            updateState('runTest','fail - subnet','Fail','subnet')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    
    #
    # ─────────────────────────────────────────────
    # 7. Serial Number Test
    # ─────────────────────────────────────────────
    
    if ctx.serial_number not in ('', '0'):
        if testSerialNumber(ctx,ctx.serial_number):
            updateState('runTest','pass - serial_number','Pass','serial_number')
        else:
            updateState('runTest','fail - serial_number','Fail','serial_number')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    
    #
    # ─────────────────────────────────────────────
    # 8. Board Version Test
    # ─────────────────────────────────────────────
    if ctx.board_version and not ctx.supernode_test:
        if testBoardVersion(ctx,ctx.board_version):
            updateState('runTest','pass - board_version','Pass', f'board_version:{ctx.board_version}')
        else:
            updateState('runTest','fail - board_version','Fail', f'board_version:{ctx.board_version}')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False

    #
    # ─────────────────────────────────────────────
    # 9. CCCV Test
    # ─────────────────────────────────────────────
    if 'cccv' in cfg:
        if testCCCV(ctx, cfg['cccv']):
            updateState('runTest','pass - cccv','Pass','cccv')
        else:
            updateState('runTest','fail - cccv','Fail','cccv')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    
    #
    # ─────────────────────────────────────────────
    # 10. MAXW Test
    # ─────────────────────────────────────────────
    if 'maxw' in cfg:
        if testMAXW(ctx, cfg['maxw']):
            updateState('runTest','pass - maxw','Pass','maxw')
        else:
            updateState('runTest','fail - maxw','Fail','maxw')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    
    #
    # ─────────────────────────────────────────────
    # 11. Single Load Test
    # ─────────────────────────────────────────────
    if 'load' in cfg:
        load_cfg = cfg['load']
        if misc.check_toggle(load_cfg):
            print("Starting Load Test")
            if testLoad(ctx, load_cfg):
                updateState('runTest','pass - load','Pass','load')
            else:
                updateState('runTest','fail - load','Fail','load')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        else:
            print("LOAD TEST TOGGLE IS SET TO OFF (0). SKIPPING LOAD TEST.")
            updateState('runTest','skip - load','Skip','load')
    
    #
    # ─────────────────────────────────────────────
    # 12. Multi-step Load Tests
    # ─────────────────────────────────────────────
    if 'loads' in cfg:
        loads_cfg = cfg['loads']
        if misc.check_toggle(loads_cfg):
            print("Starting Loads Test")
            if testLoads(ctx, loads_cfg['test_steps']):
                updateState('runTest','pass - loads','Pass','loads')
            else:
                updateState('runTest','fail - loads','Fail','loads')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        else:
            print("LOADS TEST TOGGLE IS SET TO OFF (0). SKIPPING LOADS TEST.")
            updateState('runTest','skip - loads','Skip','loads')
    
    #
    # ─────────────────────────────────────────────
    # 13. RGBW Test
    # ─────────────────────────────────────────────
    if 'rgbw' in cfg:
        rgbw_sets = cfg['rgbw']
        if not isinstance(rgbw_sets, list) or not all(isinstance(x, int) for x in rgbw_sets):
            print("RGBW Sets in test_config must be formatted as a list of ints. Proceeding with default values.")
            rgbw_sets = [4278190080,16711680,65280,255,4294967295]
        if ctx.mini_node_test:
            mnode.rgbw_test(rgbw_sets)

    # 
    # ─────────────────────────────────────────────
    # 14. Sensor 1 Test
    # ─────────────────────────────────────────────
    if 'sensor1' in cfg:
        val = cfg['sensor1']
        if val in (1, True):
            if testSensor1(ctx, val):
                updateState('runTest','pass - sensor1','Pass','sensor1')
            else:
                updateState('runTest','fail - sensor1','Fail','sensor1')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        elif val in (0, False):
            print(f"SENSOR1 TEST TOGGLE IS SET TO OFF {val}. SKIPPING SENSOR1 TEST.")
        else:
            print(f"SENSOR1 TEST TOGGLE INVALID: {val}. SKIPPING.")
    
    #
    # ─────────────────────────────────────────────
    # 15. PDLine Test
    # ─────────────────────────────────────────────
    if 'pdline' in cfg:
        v = cfg['pdline']
        if v in (1, True):
            if testPDLine(ctx, v):
                updateState('runTest','pass - pdline','Pass','pdline')
            else:
                updateState('runTest','fail - pdline','Fail','pdline')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        else:
            print(f"PDLINE TEST TOGGLE IS SET TO OFF {v}. SKIPPING PDLINE TEST.")

    #
    # ─────────────────────────────────────────────
    # 16. Battery Backup Loads Test
    # ─────────────────────────────────────────────
    if 'battery_backup_loads' in cfg:
        ctx.battery_backup_test = True
        ctx.mac_address = ''
        if testBatteryBackup(ctx, cfg["battery_backup_loads"]):
            print('pass','battbackup')
            updateState('runTest','pass - battbackup','Pass','battbackup')
        else:
            updateState('runTest','fail - battbackup','Fail','battbackup')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    
    #
    # ─────────────────────────────────────────────
    # 17. Mini Node Firmware Upgrade
    # ─────────────────────────────────────────────
    if ctx.mini_node_test and cfg.get('firmware_upgrade'):
        print("Starting firmware upgrade...")
        mnode.firmware_upgrade_test()
    
    #
    # ─────────────────────────────────────────────
    # 18. Supernode DC-IN Test
    # ─────────────────────────────────────────────
    if ctx.supernode_test and 'dc_in' in cfg:
        if cfg['dc_in'] in (1, True):
            print("Starting DC IN Test")
            if snode.dc_in_test():
                updateState('runtest','pass - dc in','Pass','dc in')
            else:
                ctx.test_status = 'Fail'
                updateState('runtest','fail - dc in','Fail','dc in')
                if ctx.stop_on_failure:
                    return False
        else:
            print("DC IN TEST TOGGLE SET TO OFF (0). SKIPPING.")
            updateState('runtest','skip - dc in','Skip','dc in')    
    
    #
    # ─────────────────────────────────────────────
    # 19. Commissioning
    # ─────────────────────────────────────────────
    if 'commission' in cfg:
        commission_settings = cfg['commission']
        if misc.check_toggle(commission_settings):
            print("Commissioning Node")
            if commission(ctx, commission_settings):
                updateState('runtest','pass - commission','Pass','commission')
            else:
                ctx.test_status = 'Fail'
                updateState('runtest','fail - commission','Fail','commission')
                if ctx.stop_on_failure:
                    return False
        else:
            print("Commission settings missing or toggled off.")
    
    #
    # ─────────────────────────────────────────────
    # 20. CMD list execution
    # ─────────────────────────────────────────────
    if 'cmd' in cfg:
        if testCMD(ctx, cfg['cmd']):
            updateState('runTest','pass - cmd','Pass','cmd')
        else:
            updateState('runTest','fail - cmd','Fail','cmd')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False

    #
    # ─────────────────────────────────────────────
    # 21. RS485 test
    # ─────────────────────────────────────────────
    if 'rs485' in cfg and cfg['rs485'] in (1, True):
        if testRS485(ctx):
            updateState('runTest','pass - rs485','Pass','rs485')
        else:
            updateState('runTest','fail - rs485','Fail','rs485')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False

    #
    # ─────────────────────────────────────────────
    # Final return
    # ─────────────────────────────────────────────
    return ctx.test_status != 'Fail'