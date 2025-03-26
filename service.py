import os
import sys
import subprocess
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import logging
from multiprocessing import freeze_support

# 设置基本路径和环境变量
base_path = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
if base_path not in sys.path:
    sys.path.append(base_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ruyi.settings')

class RuyiService(win32serviceutil.ServiceFramework):
    _svc_name_ = 'RuyiService'
    _svc_display_name_ = 'Ruyi Service'
    _svc_description_ = 'Ruyi Service running as Windows service. Author lybbn.'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self._is_running = False  # 初始状态设为False
        self.process = None
        socket.setdefaulttimeout(60)
        self._setup_logging()

    def _setup_logging(self):
        """配置日志记录"""
        log_dir = os.path.join(base_path, 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        logging.basicConfig(
            filename=os.path.join(log_dir, 'ruyi_service.log'),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger('RuyiService')

    def SvcStop(self):
        """处理服务停止请求"""
        self.logger.info("Service stop requested")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._is_running = False
        win32event.SetEvent(self.hWaitStop)
        
        # 确保子进程被终止
        if self.process:
            try:
                self.logger.info("Terminating subprocess...")
                self.process.terminate()
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.logger.warning("Subprocess did not terminate gracefully, killing it")
                self.process.kill()
            except Exception as e:
                self.logger.error(f"Error stopping subprocess: {str(e)}")
            finally:
                self.process = None
        
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        self.logger.info("Service stopped successfully")

    def SvcDoRun(self):
        """服务主运行方法"""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.logger.info("Service starting...")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        
        try:
            self._is_running = True
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            self.main()
        except Exception as e:
            self.logger.error(f"Service error: {str(e)}", exc_info=True)
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            raise

    def main(self):
        """主业务逻辑"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        self.logger.info("Starting subprocess...")
        try:
            # 使用Popen的上下文管理确保资源释放
            with subprocess.Popen(
                ['python', 'start.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            ) as self.process:
                
                # 启动日志重定向线程
                self._start_output_logging(self.process)
                
                self.logger.info("Service is now running")
                while self._is_running:
                    # 检查子进程状态
                    if self.process.poll() is not None:
                        self.logger.error(f"Subprocess exited with code {self.process.returncode}")
                        break
                    
                    # 等待停止事件或超时
                    wait_result = win32event.WaitForSingleObject(self.hWaitStop, 1000)
                    if wait_result == win32event.WAIT_OBJECT_0:
                        break
                        
        except Exception as e:
            self.logger.error(f"Error in main process: {str(e)}", exc_info=True)
            raise
        finally:
            self.process = None

    def _start_output_logging(self, process):
        """启动子进程输出日志记录线程"""
        import threading
        
        def log_stream(stream, logger_func):
            for line in iter(stream.readline, ''):
                logger_func(line.strip())
        
        # 标准输出日志线程
        stdout_thread = threading.Thread(
            target=log_stream,
            args=(process.stdout, self.logger.info),
            daemon=True
        )
        
        # 错误输出日志线程
        stderr_thread = threading.Thread(
            target=log_stream,
            args=(process.stderr, self.logger.error),
            daemon=True
        )
        
        stdout_thread.start()
        stderr_thread.start()

    def GetAcceptedControls(self):
        """指定服务接受哪些控制命令"""
        return (win32service.SERVICE_ACCEPT_STOP | 
                win32service.SERVICE_ACCEPT_SHUTDOWN |
                win32service.SERVICE_ACCEPT_PAUSE_CONTINUE)

if __name__ == '__main__':
    freeze_support()
    if len(sys.argv) == 1:
        # 服务模式运行
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(RuyiService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # 命令行模式运行
        win32serviceutil.HandleCommandLine(RuyiService)