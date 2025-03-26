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
# Docker 应用GPU
# ------------------------------
import os
import subprocess
from utils.common import current_os,RunCommand
try:
    from utils.ruyiclass.dockerInclude.ry_dk_gpu_nvidia import NVIDIAGPU
except:
    NVIDIAGPU = None

class GPUMain:
    support = False
    support_gpus = ['NVIDIA']
    gpu_brand = ""
    sys_dist = ""
    is_windows = False
    def __init__(self):
        self.is_windows = True if current_os == 'windows' else False
        self.gpu_brand = self.get_gpu_brand()
        if self.gpu_brand in self.support_gpus:
            self.support = True
        self.sys_dist = self.get_system_distribution()
        
    @staticmethod
    def is_installed_ctk():
        stdout, stderr = RunCommand("nvidia-ctk -v")
        if len(stderr) != 0:
            return False
        if not stdout.lower().find('version'):
            return False
        return True
        
    def get_gpu_brand(self):
        try:
            if not self.is_windows:
                result = subprocess.run(['lspci'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode != 0:
                    return ""
                for line in result.stdout.split('\n'):
                    if 'VGA' in line or '3D' in line:
                        if 'NVIDIA' in line:
                            return "NVIDIA"
                        elif 'AMD' in line:
                            return "AMD"
                        elif 'Intel' in line:
                            return "Intel"
                        elif 'VMware' in line:
                            return "VMware"
                        else:
                            return "unknown"
                return ""
            else:
                cmd = 'Get-WmiObject Win32_VideoController | Select-Object -ExpandProperty Name'
                result = subprocess.run(['powershell', '-Command', cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode != 0:
                    return ""
                line = result.stdout
                if 'NVIDIA' in line:
                    return "NVIDIA"
                elif 'AMD' in line:
                    return "AMD"
                elif 'Intel' in line:
                    return "Intel"
                elif 'VMware' in line:
                    return "VMware"
                return "unknown"
        except Exception as e:
            return ""

    def get_install_gpu_command(self,logpath):
        if not self.support:return False,"不支持GPU"
        if self.gpu_brand == "NVIDIA":
            return True,self.install_nvidia_container_toolkit(logpath)
        return True,""
        
    def get_system_distribution(self):
        if not current_os == "windows":
            try:
                with open("/etc/os-release", "r", encoding="utf-8") as f:
                    os_release = dict(line.strip().split("=", 1) for line in f if "=" in line)
                    dist_id = os_release.get("ID", "").lower()
                    id_like = os_release.get("ID_LIKE", "").lower()

                    if dist_id in ["debian", "ubuntu"] or "debian" in id_like:
                        return "debian"
                    elif dist_id in ["centos", "rhel", "fedora"] or any(x in id_like for x in ["rhel", "fedora"]):
                        return "centos"
            except FileNotFoundError:
                if os.path.exists("/etc/debian_version"):
                    return "debian"
                elif os.path.exists("/etc/redhat-release"):
                    return "centos"
            except Exception:
                return ""
        else:
            return "windows"
  
    def install_nvidia_container_toolkit(self,logpath):
        if self.sys_dist == "debian":
            commands = [
                f"curl -fsSL https://mirrors.ustc.edu.cn/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg >> {logpath}",
                f"curl -s -L https://mirrors.ustc.edu.cn/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://nvidia.github.io#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://mirrors.ustc.edu.cn#g' | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >> {logpath}",
                f"apt-get update >> {logpath}",
                f"apt-get install -y nvidia-container-toolkit >> {logpath}",
                f"nvidia-ctk runtime configure --runtime=docker >> {logpath}",
                f"systemctl restart docker >> {logpath}"
            ]
        elif self.sys_dist == "centos":
            commands = [
                f"curl -s -L https://mirrors.ustc.edu.cn/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | sed 's#nvidia.github.io/libnvidia-container/stable/#mirrors.ustc.edu.cn/libnvidia-container/stable/#g' | sed 's#nvidia.github.io/libnvidia-container/experimental/#mirrors.ustc.edu.cn/libnvidia-container/experimental/#g' | tee /etc/yum.repos.d/nvidia-container-toolkit.repo >> {logpath}",
                f"yum install -y nvidia-container-toolkit >> {logpath}",
                f"nvidia-ctk runtime configure --runtime=docker >> {logpath}",
                f"systemctl restart docker >> {logpath}"
            ]
        else:
            commands=[]
        return ";".join(commands)
    
    def get_gpu_info(self):
        data = {
            'system':{},
            'gpus':[]
        }
        try:
            if self.gpu_brand == "NVIDIA":
                gpu_device = NVIDIAGPU()
            else:
                return data
            data = gpu_device.get_gpu_info()
            return data
        except:
            return data