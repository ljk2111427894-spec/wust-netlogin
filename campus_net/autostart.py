import os
import sys
import winreg
from typing import Tuple

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "CampusNetAutoLogin"

class AutostartManager:
    """Windows 开机自启管理器 (基于注册表 HKCU Run 项)"""

    @staticmethod
    def get_launch_command() -> str:
        """获取用于开机自启的启动命令行 (出现在系统状态栏托盘中，不占用任务栏，随时可唤醒监控)"""
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
            return f'"{exe_path}" --tray'

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        exe_path = os.path.join(base_dir, "CampusNetLogin.exe")
        if os.path.exists(exe_path):
            return f'"{exe_path}" --tray'

        # Python 脚本模式：启动后直接收缩至系统状态栏托盘
        main_script = os.path.join(base_dir, "main.py")
        python_dir = os.path.dirname(sys.executable)
        pythonw = os.path.join(python_dir, "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable
        return f'"{pythonw}" "{main_script}" --tray'

    @classmethod
    def is_enabled(cls) -> bool:
        """检查当前是否已开启开机自启"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, APP_NAME)
                return bool(val)
        except FileNotFoundError:
            return False
        except Exception:
            return False

    @classmethod
    def set_enabled(cls, enable: bool) -> Tuple[bool, str]:
        """设置开启或关闭开机自启"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    cmd = cls.get_launch_command()
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                    return True, "已成功设置开机自启"
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError:
                        pass
                    return True, "已取消开机自启"
        except Exception as e:
            return False, f"操作注册表失败: {str(e)}"
