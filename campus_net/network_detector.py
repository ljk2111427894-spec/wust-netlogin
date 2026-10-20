import socket
import subprocess
import time
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Tuple

STATE_ONLINE = "ONLINE"                     # 真正通外网
STATE_CAPTIVE_PORTAL = "CAPTIVE_PORTAL"     # 被校园网认证页拦截 (需登录)
STATE_OFFLINE = "OFFLINE"                   # 彻底无网络或断线

class NetworkDetector:
    """多层网络连通性探测器 (支持跳过系统代理)"""

    def __init__(self, probe_urls: List[str] = None, portal_ip: str = "59.68.177.9"):
        self.probe_urls = probe_urls or [
            "http://connectivitycheck.platform.hicloud.com/generate_204",
            "http://connect.rom.miui.com/generate_204",
            "http://www.baidu.com",
            "http://www.msftconnecttest.com/connecttest.txt"
        ]
        self.portal_ip = portal_ip
        # 强制直连探测
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def check_internet(self, timeout: float = 2.5) -> Tuple[str, str, float]:
        """
        探测外网连通状态
        返回: (状态码, 说明信息, 延迟ms)
        """
        for url in self.probe_urls:
            start = time.time()
            try:
                req = urllib.request.Request(
                    url, 
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Cache-Control": "no-cache"
                    }
                )
                with self._opener.open(req, timeout=timeout) as resp:
                    latency = (time.time() - start) * 1000
                    final_url = resp.geturl()

                    # 检查是否被重定向到校园网认证页
                    if self.portal_ip in final_url:
                        return STATE_CAPTIVE_PORTAL, f"被校园网认证拦截 (重定向至 {self.portal_ip})", latency

                    status = resp.status
                    # 204 探测点返回 204 即表示畅通
                    if "generate_204" in url and status == 204:
                        return STATE_ONLINE, "互联网畅通", latency

                    # 针对微软连通性探测
                    if "connecttest.txt" in url:
                        content = resp.read(100).decode("utf-8", errors="ignore")
                        if "Microsoft Connect Test" in content:
                            return STATE_ONLINE, "互联网畅通", latency
                        else:
                            return STATE_CAPTIVE_PORTAL, "被校园网重定向拦截", latency

                    # 常规 200 页面
                    if status == 200:
                        content_sample = resp.read(200).decode("utf-8", errors="ignore")
                        if self.portal_ip in content_sample or "wust" in content_sample.lower():
                            return STATE_CAPTIVE_PORTAL, "被校园网认证拦截", latency
                        return STATE_ONLINE, "互联网畅通", latency

            except urllib.error.HTTPError as e:
                # 若被拦截并返回 302 重定向
                if e.code in (301, 302, 307):
                    location = e.headers.get("Location", "")
                    if self.portal_ip in location:
                        return STATE_CAPTIVE_PORTAL, f"被校园网重定向至 {location}", (time.time() - start) * 1000
            except Exception:
                # 单个测试点失败，尝试下一个
                continue

        return STATE_OFFLINE, "外网完全无法访问 (所有探测点超时或断开)", 0.0

    def is_portal_reachable(self, timeout: float = 2.0) -> bool:
        """测试认证服务器 IP (59.68.177.9) 端口 80 是否可达"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            res = sock.connect_ex((self.portal_ip, 80))
            sock.close()
            return res == 0
        except Exception:
            return False

    def get_adapter_states(self) -> Dict[str, Any]:
        """获取 Windows 各物理网络接口状态 (以太网/有线、WLAN/无线)"""
        info = {
            "ethernet_connected": False,
            "ethernet_name": "",
            "wifi_connected": False,
            "wifi_name": "",
            "details": []
        }
        try:
            # 指定输出 UTF8 编码
            cmd = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-NetAdapter | Select-Object -Property Name, InterfaceDescription, Status | ConvertTo-Json -Compress"
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )
            import json
            raw = res.stdout.decode("utf-8", errors="ignore").strip()
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    name = str(item.get("Name", ""))
                    status = str(item.get("Status", ""))
                    desc = str(item.get("InterfaceDescription", "")).lower()
                    is_up = (status == "Up" or status == "已启用" or status == "2")

                    if any(w in desc or w in name.lower() for w in ["wi-fi", "wifi", "wlan", "wireless", "802.11"]):
                        info["wifi_name"] = name
                        if is_up:
                            info["wifi_connected"] = True
                    elif any(e in desc for e in ["ethernet", "gbe", "realtek pcie", "intel", "gigabit"]):
                        info["ethernet_name"] = name
                        if is_up:
                            info["ethernet_connected"] = True

                    info["details"].append({"name": name, "status": status, "desc": desc})
        except Exception:
            pass
        return info

    def run_full_diagnostic(self) -> Dict[str, Any]:
        """运行全面网络诊断报告"""
        adapters = self.get_adapter_states()
        portal_ok = self.is_portal_reachable()
        state, msg, latency = self.check_internet()

        return {
            "internet_state": state,
            "message": msg,
            "latency_ms": round(latency, 1),
            "portal_reachable": portal_ok,
            "ethernet_connected": adapters["ethernet_connected"],
            "ethernet_name": adapters["ethernet_name"],
            "wifi_connected": adapters["wifi_connected"],
            "wifi_name": adapters["wifi_name"],
        }
