import os,sys
import subprocess
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
from multiprocessing import freeze_support

base_path = os.path.dirname(os.path.abspath(__file__))
if getattr(sys,'frozen',False):
    base_path = sys._MEIPASS
if not base_path in sys.path:
    sys.path.append(base_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ruyi.settings')

class RuyiService(win32serviceutil.ServiceFramework):
    _svc_name_ = 'RuyiService'
    _svc_display_name_ = 'RuyiService'
    _svc_description_ = 'RuyiService running as Windows service. Author lybbn.'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self._is_running = True
        socket.setdefaulttimeout(60)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._is_running = False
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,servicemanager.PYS_SERVICE_STARTED,(self._svc_name_, ''))
        self.main()

    def main(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        self.process = subprocess.Popen(['python', 'start.py'])
        while self._is_running:
            wait_result = win32event.WaitForSingleObject(self.hWaitStop, 5000)
            if wait_result == win32event.WAIT_OBJECT_0:
                break
        if self.process:
            self.process.terminate()
            self.process.wait()
        self.process = None

if __name__ == '__main__':
    freeze_support()
    win32serviceutil.HandleCommandLine(RuyiService)