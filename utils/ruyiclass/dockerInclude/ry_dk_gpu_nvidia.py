#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-03-10
# +-------------------------------------------------------------------
# | EditDate: 2025-03-10
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Docker Nvidia GPU类
# ------------------------------

from utils.common import RunCommand,get_python_pip

SYS_PIP = get_python_pip()['pip']

try:
    import pynvml
except:
    RunCommand(f"{SYS_PIP} install nvidia-ml-py -i https://mirrors.aliyun.com/pypi/simple/")
    import pynvml

class NVIDIAGPU:
    support = False
    device_nums = 0
    def __init__(self):
        self.support = self.is_support()
        if self.support:
            self.device_nums = pynvml.nvmlDeviceGetCount()

    def is_support(self):
        try:
            pynvml.nvmlInit()
            return True
        except:
            return False
    
    def close(self):
        try:
            pynvml.nvmlShutdown()
        except:
            pass
        
    def get_gpu_info(self):
        data = {}
        data['system'] = self.get_system_info()
        data['gpus'] = []
        for i in range(self.device_nums):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)

            # 获取 GPU 名称
            name = pynvml.nvmlDeviceGetName(handle)
            
            # 获取 GPU 温度
            temperature = 0
            try:
                temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except pynvml.NVMLError or AttributeError:
                temperature = pynvml.nvmlDeviceGetTemperatureV1(handle, pynvml.NVML_TEMPERATURE_GPU)

            # 获取 GPU 利用率
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            # print(f"  GPU Utilization: {utilization.gpu}%")
            # print(f"  Memory Utilization: {utilization.memory}%")

            # 获取 GPU 时钟信息
            clock_info = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
            # print(f"  Graphics Clock: {clock_info} MHz")

            # 获取 GPU 最大时钟信息
            max_clock_info = pynvml.nvmlDeviceGetMaxClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
            # print(f"  Max Graphics Clock: {max_clock_info} MHz")

            data['gpus'].append({
                'name':name,
                'temperature':temperature,
                'mem':self.get_mem_info(handle),
                'fan':self.get_fan_info(handle),
                'utilization':{
                    'gpu':utilization.gpu,
                    'memory':utilization.memory
                },
                'power':self.get_power_info(handle),
                'clock':{
                    'graphics': clock_info,
                    'max_graphics':max_clock_info,
                    'sm': pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM),
                    'mem': pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM),
                    'video':pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_VIDEO),
                },
                'process':self.get_process_list(handle)
            })
            
        return data
    
    def get_system_info(self):
        info = {}
        info['driver'] = pynvml.nvmlSystemGetDriverVersion()
        try:
            info['cuda'] = pynvml.nvmlSystemGetCudaDriverVersion()
        except pynvml.NVMLError or AttributeError:
            info['cuda'] = pynvml.nvmlSystemGetCudaDriverVersion_v2()
        info['count'] = self.device_nums
        return info
    
    def get_mem_info(self,handle):
        info = {}
        memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        info['total'] = f'{memory_info.total/ 1024**3:.2f}'
        info['free'] = f'{memory_info.free/ 1024**3:.2f}'
        info['used'] = f'{memory_info.used/ 1024**3:.2f}'
        return info
    
    def get_fan_info(self, handle):
        info = {}
        try:
            info['speed'] = pynvml.nvmlDeviceGetFanSpeedRPM(handle).speed
        except AttributeError:
            info['speed'] = pynvml.nvmlDeviceGetFanSpeed(handle)
        except pynvml.NVMLError:
            num_fans = pynvml.nvmlDeviceGetNumFans(handle)
            if num_fans>0:
                info['speed'] = pynvml.nvmlDeviceGetFanSpeed_v2(handle, 0)
            else:
                info['speed'] = 0
        except:
            info['speed'] = 0
        return info
    
    def get_power_info(self,handle):
        info = {}
        # 获取 GPU 电源使用情况
        power_usage = pynvml.nvmlDeviceGetPowerUsage(handle)
        # print(f"  Power Usage: {power_usage/ 1000.0} W")
        try:
            # 获取 GPU 电源限制
            power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
            # print(f"  Power Limit: {power_limit / 1000.0} W")
        except:
            power_limit = 0
        info = {
            'usage':power_usage,
            'max': power_limit
        }
        return info
    
    def get_process_list(self,handle):
        data = []
        for p in pynvml.nvmlDeviceGetComputeRunningProcesses(handle):
            p.__dict__['name'] = pynvml.nvmlSystemGetProcessName(p.pid)
            p.__dict__['type'] = 'Compute'
            data.append(p.__dict__)

        for p in pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle):
            p.__dict__['name'] = pynvml.nvmlSystemGetProcessName(p.pid)
            p.__dict__['type'] = 'Graphics'
            data.append(p.__dict__)

        for p in pynvml.nvmlDeviceGetMPSComputeRunningProcesses(handle):
            p.__dict__['name'] = pynvml.nvmlSystemGetProcessName(p.pid)
            p.__dict__['type'] = 'MPS'
            data.append(p.__dict__)
        return data