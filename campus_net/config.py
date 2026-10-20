import json
import os
import sys
from typing import Dict, Any

def get_app_dir() -> str:
    """获取应用程序所在的真实目录 (适配源码运行与 PyInstaller 打包环境)"""
    if getattr(sys, 'frozen', False):
        # 打包为 exe 时，获取 exe 所在的实际目录
        return os.path.dirname(os.path.abspath(sys.executable))
    # 源码运行时，获取项目根目录 (campus_net 的上一级目录)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONFIG: Dict[str, Any] = {
    # 校园网认证基础设置
    "auth_url": "http://59.68.177.9",
    "username": "",
    "password": "",
    "carrier": "",  # 运营商后缀："" (校园网默认), "@telecom" (电信), "@cmcc" (移动), "@unicom" (联通)

    # 连接模式:
    # "wifi_web": WiFi连接 + 网页Portal认证
    # "cable_pppoe": 有线网线 + Windows宽带拨号(rasdial)
    # "cable_web": 有线网线直连 + 网页Portal认证
    # "auto": 智能混合自适应模式 (优先有线，回退无线)
    "connect_mode": "wifi_web",

    # WiFi 配置
    "wifi_ssid": "WUST-WiFi6",

    # 网线 PPPoE 宽带拨号配置
    "pppoe_name": "宽带连接",

    # 守护与检测参数
    "check_interval": 15,       # 心跳检测周期 (秒)
    "auto_reconnect": True,     # 断线是否自动重连
    "auto_start": False,        # 是否开机自启
    "auto_daemon_on_start": True,  # 启动程序后是否自动开启守护
    "minimize_on_start": False, # 启动后是否自动收缩到状态栏托盘
    "minimize_on_daemon": False, # 开启守护时是否自动收缩到状态栏托盘
    "close_to_tray": True,      # 点击窗口关闭[X]时收缩到状态栏托盘

    # 窗口与界面尺寸偏好
    "window_geometry": "860x720",
    "window_is_maximized": False,

    # 网络连通性探测地址 (直接连通性检测，跳过系统代理)
    "probe_urls": [
        "http://connectivitycheck.platform.hicloud.com/generate_204",
        "http://connect.rom.miui.com/generate_204",
        "http://www.baidu.com",
        "http://www.msftconnecttest.com/connecttest.txt"
    ]
}

class ConfigManager:
    """配置文件管理器"""
    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = get_app_dir()
            config_path = os.path.join(base_dir, "config.json")
        self.config_path = os.path.abspath(config_path)
        self.data: Dict[str, Any] = self.load()

    def load(self) -> Dict[str, Any]:
        """读取配置文件，若不存在则创建默认配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(user_cfg)
                return merged
            except Exception as e:
                print(f"[配置] 读取配置文件异常({self.config_path})，将恢复默认值: {e}")
        return DEFAULT_CONFIG.copy()

    def save(self) -> bool:
        """保存配置到文件"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            return True
        except Exception as e:
            print(f"[配置] 保存配置文件失败({self.config_path}): {e}")
            return False

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value

    def get_full_username(self) -> str:
        """拼接完整的登录账号（包含运营商后缀）"""
        user = str(self.data.get("username", "")).strip()
        carrier = str(self.data.get("carrier", "")).strip()
        if carrier and not user.endswith(carrier):
            return f"{user}{carrier}"
        return user
