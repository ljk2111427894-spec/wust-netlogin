import threading
import time
from typing import Callable, Optional, Dict, Any

from .config import ConfigManager
from .web_auth import WebAuthenticator
from .pppoe import PPPoEManager
from .wifi import WiFiManager
from .network_detector import NetworkDetector, STATE_ONLINE, STATE_CAPTIVE_PORTAL, STATE_OFFLINE

class CampusNetDaemon:
    """校园网自动认证、自动检测与断线重连守护守护线程"""

    def __init__(
        self,
        config_mgr: ConfigManager,
        log_callback: Optional[Callable[[str, str], None]] = None,
        status_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.config_mgr = config_mgr
        self.log_callback = log_callback or self._default_logger
        self.status_callback = status_callback

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

        # 核心功能组件
        self._init_components()

    def _init_components(self):
        """根据最新配置初始化各子组件"""
        auth_url = self.config_mgr.get("auth_url", "http://59.68.177.9")
        self.web_auth = WebAuthenticator(base_url=auth_url)
        self.pppoe_mgr = PPPoEManager(entry_name=self.config_mgr.get("pppoe_name", "宽带连接"))
        self.wifi_mgr = WiFiManager(default_ssid=self.config_mgr.get("wifi_ssid", "WUST-WiFi6"))
        self.detector = NetworkDetector(probe_urls=self.config_mgr.get("probe_urls"))

    def _log(self, level: str, msg: str):
        if self.log_callback:
            try:
                self.log_callback(level, msg)
            except Exception:
                pass

    @staticmethod
    def _default_logger(level: str, msg: str):
        t = time.strftime("%H:%M:%S")
        print(f"[{t}] [{level}] {msg}")

    def is_running(self) -> bool:
        return self._is_running

    def start(self):
        """启动后台守护监控"""
        if self._is_running:
            self._log("WARN", "守护进程已在运行中，请勿重复启动")
            return

        self._init_components()
        self._stop_event.clear()
        self._is_running = True
        self._thread = threading.Thread(target=self._run_loop, name="CampusNetWatchdog", daemon=True)
        self._thread.start()
        self._log("INFO", "校园网后台守护进程已启动，开始实时监测网络状态...")

    def stop(self):
        """停止后台守护监控"""
        if not self._is_running:
            return

        self._is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._log("INFO", "校园网后台守护进程已停止")

    def perform_login(self) -> bool:
        """根据当前配置模式，立即执行一次登录认证"""
        mode = self.config_mgr.get("connect_mode", "wifi_web")
        username = self.config_mgr.get_full_username()
        password = self.config_mgr.get("password", "")
        wifi_ssid = self.config_mgr.get("wifi_ssid", "WUST-WiFi6")
        pppoe_name = self.config_mgr.get("pppoe_name", "宽带连接")

        if not username or not password:
            self._log("ERROR", "登录失败：未配置账号或密码，请在设置中填写！")
            return False

        self._log("INFO", f"正在执行网络连接与认证 (模式: {self._get_mode_name(mode)})...")

        if mode == "wifi_web":
            # 1. 确保 WiFi 已连上指定 SSID
            w_status = self.wifi_mgr.get_status()
            if not (w_status.get("connected") and w_status.get("ssid") == wifi_ssid):
                self._log("INFO", f"正在连接无线网络: {wifi_ssid} ...")
                ok, w_msg = self.wifi_mgr.connect(wifi_ssid)
                if not ok:
                    self._log("ERROR", f"连接 WiFi 失败: {w_msg}")
                    return False
                self._log("SUCCESS", f"WiFi 已关联: {wifi_ssid}，等待 DHCP 获取 IP...")
                time.sleep(2.0)

            # 2. 执行 Web Portal 认证
            ok, msg, _ = self.web_auth.login(username, password)
            if ok:
                self._log("SUCCESS", f"Web Portal 认证成功: {msg}")
                return True
            else:
                self._log("ERROR", f"Web Portal 认证失败: {msg}")
                return False

        elif mode == "cable_pppoe":
            # 网线 PPPoE 宽带拨号
            self.pppoe_mgr.entry_name = pppoe_name
            self._log("INFO", f"正在使用 Windows 宽带拨号 [{pppoe_name}] 发起拨号...")
            ok, msg = self.pppoe_mgr.connect(username, password)
            if ok:
                self._log("SUCCESS", f"宽带拨号成功: {msg}")
                return True
            else:
                self._log("ERROR", f"宽带拨号失败: {msg}")
                return False

        elif mode == "cable_web":
            # 有线网卡直连 + Web 认证
            adapters = self.detector.get_adapter_states()
            if not adapters.get("ethernet_connected"):
                self._log("WARN", "提示：未检测到已连接的网线，请确认网线插好")

            ok, msg, _ = self.web_auth.login(username, password)
            if ok:
                self._log("SUCCESS", f"有线 Web 认证成功: {msg}")
                return True
            else:
                self._log("ERROR", f"有线 Web 认证失败: {msg}")
                return False

        elif mode == "auto":
            # 智能混合模式
            adapters = self.detector.get_adapter_states()
            if adapters.get("ethernet_connected"):
                self._log("INFO", "智能混合模式：检测到网线已接入，优先尝试 Web 认证...")
                ok, msg, _ = self.web_auth.login(username, password)
                if ok:
                    self._log("SUCCESS", f"有线 Web 认证成功: {msg}")
                    return True
                # 若 Web 失败，尝试 PPPoE
                self._log("INFO", "尝试使用网线宽带拨号...")
                ok_dial, msg_dial = self.pppoe_mgr.connect(username, password)
                if ok_dial:
                    self._log("SUCCESS", f"宽带拨号成功: {msg_dial}")
                    return True

            # 回退至 WiFi 模式
            self._log("INFO", "智能混合模式：回退至 WiFi 无线连接模式...")
            ok_w, _ = self.wifi_mgr.connect(wifi_ssid)
            if ok_w:
                time.sleep(2.0)
            ok, msg, _ = self.web_auth.login(username, password)
            if ok:
                self._log("SUCCESS", f"WiFi 认证成功: {msg}")
                return True
            else:
                self._log("ERROR", f"智能混合模式重连失败: {msg}")
                return False

        return False

    def perform_logout(self) -> bool:
        """断开连接与退出登录"""
        mode = self.config_mgr.get("connect_mode", "wifi_web")
        self._log("INFO", "正在执行注销退出...")

        if mode == "cable_pppoe":
            ok, msg = self.pppoe_mgr.disconnect()
            self._log("INFO" if ok else "WARN", msg)
            return ok
        else:
            ok, msg = self.web_auth.logout()
            self._log("INFO" if ok else "WARN", f"Web注销: {msg}")
            return ok

    def _run_loop(self):
        """守护监控主循环"""
        fail_count = 0
        last_online_state = False

        while not self._stop_event.is_set():
            interval = int(self.config_mgr.get("check_interval", 15))
            if interval < 5:
                interval = 5

            try:
                # 1. 探测网络连通性
                state, reason, latency = self.detector.check_internet()
                portal_status = self.web_auth.check_status()
                wifi_status = self.wifi_mgr.get_status()

                is_online = (state == STATE_ONLINE)

                # 广播当前状态给 UI
                if self.status_callback:
                    try:
                        self.status_callback({
                            "is_online": is_online,
                            "internet_state": state,
                            "latency_ms": round(latency, 1),
                            "portal_online": portal_status.get("is_online", False),
                            "username": portal_status.get("username", ""),
                            "user_ip": portal_status.get("ip", ""),
                            "user_mac": portal_status.get("mac", ""),
                            "bytes_str": portal_status.get("bytes_str", ""),
                            "online_time": portal_status.get("add_time", ""),
                            "wifi_ssid": wifi_status.get("ssid", ""),
                            "wifi_connected": wifi_status.get("connected", False),
                            "wifi_signal": wifi_status.get("signal", ""),
                            "dial_msg": portal_status.get("dial_msg", "")
                        })
                    except Exception:
                        pass

                if is_online:
                    if not last_online_state:
                        self._log("SUCCESS", f"✅ 网络正常在线 (延迟: {round(latency, 1)}ms)")
                    last_online_state = True
                    fail_count = 0
                else:
                    last_online_state = False
                    fail_count += 1
                    self._log("WARN", f"⚠️ 检测到网络异常 [{state}]: {reason}")

                    if self.config_mgr.get("auto_reconnect", True):
                        self._log("INFO", f"触发断线自动重连机制 (第 {fail_count} 次尝试)...")
                        success = self.perform_login()
                        if success:
                            # 等待复检
                            time.sleep(2.0)
                            check_state, _, _ = self.detector.check_internet()
                            if check_state == STATE_ONLINE:
                                self._log("SUCCESS", "🎉 断线重连成功，网络已恢复畅通！")
                                fail_count = 0
                                last_online_state = True
                            else:
                                self._log("WARN", "重连后网络仍未完全通畅，等待下个周期复测")
                        else:
                            # 失败后小幅避退，避免频繁撞库请求
                            backoff = min(fail_count * 3, 20)
                            self._log("WARN", f"重连未成功，将在 {backoff} 秒后再次重试")
                            self._stop_event.wait(backoff)

            except Exception as e:
                self._log("ERROR", f"守护监控异常: {str(e)}")

            # 正常周期等待 (可被 stop_event 随时打断)
            self._stop_event.wait(interval)

    @staticmethod
    def _get_mode_name(mode_key: str) -> str:
        mapping = {
            "wifi_web": "WiFi无线 + 网页认证",
            "cable_pppoe": "网线宽带拨号 (PPPoE)",
            "cable_web": "网线直连 + 网页认证",
            "auto": "智能混合自适应"
        }
        return mapping.get(mode_key, mode_key)
