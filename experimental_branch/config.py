# config.py
import platform

class CONFIG:
    os_name = platform.system()

    DB_HOST = 'localhost'
    DB_USER = 'root'
    DB_PASSWD = ''
    DB_NAME = 'pmi_inspextor_v2'

    if os_name  == "WINNT" or os_name == "Darwin":
        BASE_URL = "http://localhost/inx-i/www/"
        PIDFilePath = '/Applications/XAMPP/htdocs/inx-i/www/inx-logs/'
    else:
        BASE_URL = "http://localhost/inxs/"
        PIDFilePath = '/var/inx-logs/'
        DB_PASSWD = 'p@$$me2015'

    @staticmethod
    def savePID(pid, filename):
        try:
            with open(CONFIG.PIDFilePath + filename, 'w') as file:
                file.write(str(pid))
            print('savePID - ok')
        except Exception as e:
            print('savePID - error',e)