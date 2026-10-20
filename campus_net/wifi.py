import os
import re
import subprocess
import tempfile
import time
from typing import Dict, Any, List, Tuple

class WiFiManager:
    """Windows WiFi 管理与自动重连模块 (基于 netsh wlan)"""

    def __init__(self, default_ssid: str = "WUST-WiFi6"):
        self.default_ssid = default_ssid

    def _run_cmd(self, args: List[str], timeout: int = 10) -> Tuple[int, str]:
        """执行 netsh 等命令行"""
        try:
            res = subprocess.run(
                args,
                capture_output=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )
            raw = res.stdout + b"\n" + res.stderr
            out = ""
            for enc in ("gbk", "cp936", "utf-8", "ansi"):
                try:
                    out = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if not out:
                out = raw.decode("utf-8", errors="ignore")
            return res.returncode, out.strip()
        except Exception as e:
            return -1, str(e)

    def get_status(self) -> Dict[str, Any]:
        """获取当前无线网卡状态、连接的 SSID、信号强度等"""
        code, out = self._run_cmd(["netsh", "wlan", "show", "interfaces"])
        info = {
            "has_adapter": False,
            "connected": False,
            "adapter_name": "",
            "ssid": "",
            "bssid": "",
            "signal": "",
            "state": "未知"
        }
        if code != 0 or not out:
            return info

        info["has_adapter"] = True
        for line in out.splitlines():
            line_str = line.strip()
            if ":" not in line_str:
                continue
            k, v = line_str.split(":", 1)
            k = k.strip()
            v = v.strip()

            if any(name_key in k for name_key in ["名称", "Name"]):
                info["adapter_name"] = v
            elif any(state_key in k for state_key in ["状态", "State"]):
                info["state"] = v
                if "connected" in v.lower() or "已连接" in v:
                    info["connected"] = True
            elif k.upper() == "SSID":
                info["ssid"] = v
            elif k.upper() == "BSSID" or "AP BSSID" in k:
                info["bssid"] = v
            elif any(sig_key in k for sig_key in ["信号", "Signal"]):
                info["signal"] = v

        return info

    def list_available_ssids(self) -> List[str]:
        """扫描当前周围可见的 WiFi 网络列表"""
        code, out = self._run_cmd(["netsh", "wlan", "show", "networks"])
        ssids = set()
        if code == 0:
            for line in out.splitlines():
                line = line.strip()
                m = re.match(r"^SSID\s+\d+\s*:\s*(.+)$", line)
                if m:
                    ssid = m.group(1).strip()
                    if ssid:
                        ssids.add(ssid)
        return sorted(list(ssids))

    def has_profile(self, ssid: str) -> bool:
        """检查系统中是否已存在指定 SSID 的无线配置文件"""
        code, out = self._run_cmd(["netsh", "wlan", "show", "profile", f"name={ssid}"])
        return code == 0

    def create_open_profile(self, ssid: str) -> bool:
        """为开放式无密码校园网 WiFi (如 WUST-WiFi6) 创建系统配置文件"""
        xml_template = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <name>{ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>open</authentication>
                <encryption>none</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
        </security>
    </MSM>
</WLANProfile>"""
        try:
            temp_xml = os.path.join(tempfile.gettempdir(), f"wlan_prof_{os.getpid()}.xml")
            with open(temp_xml, "w", encoding="utf-8") as f:
                f.write(xml_template)
            code, _ = self._run_cmd(["netsh", "wlan", "add", "profile", f"filename={temp_xml}"])
            if os.path.exists(temp_xml):
                os.remove(temp_xml)
            return code == 0
        except Exception:
            return False

    def connect(self, target_ssid: str = None, timeout: int = 12) -> Tuple[bool, str]:
        """连接到指定 WiFi SSID，并等待连接就绪"""
        ssid = target_ssid or self.default_ssid
        current = self.get_status()
        if current.get("connected") and current.get("ssid") == ssid:
            return True, f"WiFi 当前已连接至: {ssid}"

        # 检查是否有配置文件，若无则尝试创建开放式配置
        if not self.has_profile(ssid):
            self.create_open_profile(ssid)

        code, out = self._run_cmd(["netsh", "wlan", "connect", f"name={ssid}"])
        if code != 0:
            return False, f"发送 WiFi 连接指令失败: {out}"

        # 轮询等待连接成功
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(1.0)
            status = self.get_status()
            if status.get("connected") and status.get("ssid") == ssid:
                return True, f"已成功连接至 WiFi: {ssid} (信号: {status.get('signal', '-')})"

        return False, f"连接 WiFi [{ssid}] 超时，未能在 {timeout} 秒内完成关联"

    def disconnect(self) -> Tuple[bool, str]:
        """断开当前 WiFi 连接"""
        code, out = self._run_cmd(["netsh", "wlan", "disconnect"])
        return code == 0, out
