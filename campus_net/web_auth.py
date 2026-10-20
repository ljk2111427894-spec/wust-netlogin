import json
import time
import urllib.request
import urllib.parse
from typing import Dict, Any, Tuple, Optional

class WebAuthenticator:
    """针对 59.68.177.9 校园网 Web Portal 的认证客户端"""

    def __init__(self, base_url: str = "http://59.68.177.9", timeout: int = 6):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # 强制直连，绕过 Windows 系统代理 / VPN / Clash 代理
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor()
        )

    def _request(self, path: str, method: str = "GET", data: Optional[dict] = None) -> Tuple[bool, Any]:
        """向认证服务器发送 HTTP 请求"""
        url = f"{self.base_url}{path}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.base_url}/"
        }
        
        encoded_data = None
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
            # 过滤空值键
            clean_data = {k: str(v) for k, v in data.items() if v is not None and str(v) != ""}
            encoded_data = urllib.parse.urlencode(clean_data).encode("utf-8")

        req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                resp_text = resp.read().decode("utf-8", errors="ignore")
                try:
                    res_json = json.loads(resp_text)
                    return True, res_json
                except json.JSONDecodeError:
                    return False, f"服务器响应非JSON: {resp_text[:120]}"
        except urllib.error.URLError as e:
            return False, f"无法连接到校园网认证服务器({url}): {e.reason}"
        except Exception as e:
            return False, f"请求异常: {str(e)}"

    def get_server_config(self) -> Dict[str, Any]:
        """获取服务端配置参数 (nasId, title等)"""
        ok, res = self._request("/api/config")
        if ok and isinstance(res, dict) and res.get("code") == 0:
            return res.get("data", {}).get("config", {})
        return {}

    def fetch_redirect_info(self) -> Dict[str, str]:
        """请求 /api/r/1 追踪重定向以探测当前客户端在网关处的 IP 及 nasId"""
        nas_id = "1"
        cfg = self.get_server_config()
        if cfg.get("default_nas"):
            nas_id = str(cfg.get("default_nas"))
        
        url = f"{self.base_url}/api/r/{nas_id}"
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                final_url = resp.geturl()
                parsed = urllib.parse.urlparse(final_url)
                params = urllib.parse.parse_qs(parsed.query)
                return {k: v[0] for k, v in params.items()}
        except Exception:
            return {"nasId": nas_id}

    def check_status(self) -> Dict[str, Any]:
        """查询当前账号在线状态及流量时长信息"""
        ok, res = self._request("/api/account/status")
        result = {
            "reachable": ok,
            "is_online": False,
            "username": "",
            "name": "",
            "ip": "",
            "mac": "",
            "bytes_in": 0,
            "bytes_str": "",
            "add_time": "",
            "dial_code": "",
            "dial_msg": "",
            "enable_dial": False,
            "raw_msg": ""
        }
        
        if not ok:
            result["raw_msg"] = str(res)
            return result

        if isinstance(res, dict):
            result["enable_dial"] = res.get("enableDial", False)
            result["dial_code"] = res.get("dialCode", "")
            result["dial_msg"] = res.get("dialMsg", "")
            result["raw_msg"] = res.get("msg", "")

            if res.get("code") == 0:
                online = res.get("online") or {}
                result["is_online"] = True
                result["username"] = online.get("Username", "")
                result["name"] = online.get("Name", "")
                result["ip"] = online.get("UserIpv4", "")
                result["mac"] = online.get("UserMac", "")
                raw_bytes = online.get("BytesIn4", 0)
                try:
                    b_int = int(raw_bytes)
                    result["bytes_in"] = b_int
                    result["bytes_str"] = self._format_bytes(b_int)
                except (ValueError, TypeError):
                    result["bytes_str"] = str(raw_bytes)
                result["add_time"] = online.get("AddTime", "")
        return result

    def login(self, username: str, password: str, nas_id: str = "1", ip: str = None, mac: str = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        执行 Web 认证登录
        返回: (成功标志 bool, 消息文本 str, 详情字典 dict)
        """
        if not username or not password:
            return False, "用户名或密码不能为空", {}

        # 尝试拉取重定向参数
        redirect_params = self.fetch_redirect_info()
        actual_nas = redirect_params.get("nasId", nas_id)
        actual_ip = ip or redirect_params.get("wlanuserip") or redirect_params.get("ip")
        actual_mac = mac or redirect_params.get("mac")

        post_data = {
            "username": username,
            "password": password,
            "nasId": actual_nas,
            "userIpv4": actual_ip,
            "userMac": actual_mac,
            "switchip": redirect_params.get("switchip")
        }

        ok, res = self._request("/api/account/login", method="POST", data=post_data)
        if not ok:
            return False, f"请求登录接口失败: {res}", {}

        if not isinstance(res, dict):
            return False, f"登录接口返回异常: {res}", {}

        code = res.get("code")
        msg = res.get("msg", "")

        if code == 0:
            # 登录认证成功
            enable_dial = res.get("enableDial", False)
            dial_code = res.get("dialCode", "")
            
            # 若系统需要后端二次拨号且尚未完成，则触发二次重拨轮询
            if enable_dial and dial_code != "ok:dialup":
                self.redial()
                # 轮询拨号状态
                for _ in range(6):
                    time.sleep(1.2)
                    status = self.check_status()
                    if status.get("dial_code") == "ok:dialup":
                        break
            return True, msg or "校园网认证成功", res

        elif code == 1:
            return False, f"认证失败: {msg}", res
        elif code == 2:
            return False, f"需要输入验证码: {msg}", res
        else:
            return False, f"未知返回状态码({code}): {msg}", res

    def redial(self) -> Tuple[bool, str]:
        """向服务端请求二次拨号重拨"""
        ok, res = self._request("/api/account/redial", method="POST", data={})
        if ok and isinstance(res, dict) and res.get("code") == 0:
            return True, "已发送重拨请求"
        return False, f"重拨失败: {res}"

    def logout(self) -> Tuple[bool, str]:
        """向服务端请求注销退出"""
        ok, res = self._request("/api/account/logout", method="GET")
        if ok and isinstance(res, dict):
            return res.get("code") == 0, res.get("msg", "已退出登录")
        return False, f"注销请求失败: {res}"

    @staticmethod
    def _format_bytes(bytes_num: int) -> str:
        """字节数人类可读格式化"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_num < 1024.0:
                return f"{bytes_num:.2f} {unit}"
            bytes_num /= 1024.0
        return f"{bytes_num:.2f} PB"
