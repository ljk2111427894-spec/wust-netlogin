import os
import re
import subprocess
from typing import Tuple, List, Optional

ERROR_CODES = {
    691: "账号或密码错误，或者账号已欠费/停机",
    651: "调制解调器(网卡)报告了错误：请检查网线是否插紧、网卡驱动是否正常",
    678: "远程计算机没有响应：请检查网线连接或校园网交换机端口",
    629: "连接被远程计算机关闭：可能同时在线设备超限或服务端强制下线",
    720: "无法配置PPPoE连接协议：尝试重启网卡或重置TCP/IP协议",
    734: "PPP链路控制协议被终止：账号格式或运营商拨号规则有误",
    633: "调制解调器已在使用或未配置：请关闭占用的拨号软件重试",
}

class PPPoEManager:
    """Windows 网线宽带拨号 (PPPoE / rasdial) 控制器"""

    def __init__(self, entry_name: str = "宽带连接"):
        self.entry_name = entry_name

    def _run_cmd(self, args: List[str], timeout: int = 15) -> Tuple[int, str]:
        """运行命令行并尝试多种编码解码"""
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
        except subprocess.TimeoutExpired:
            return -1, "执行超时"
        except Exception as e:
            return -2, f"执行异常: {str(e)}"

    def is_connected(self) -> bool:
        """检查指定拨号连接当前是否已连接"""
        code, out = self._run_cmd(["rasdial"], timeout=5)
        if code == 0:
            lines = [line.strip() for line in out.splitlines() if line.strip()]
            for line in lines:
                if self.entry_name.lower() in line.lower():
                    return True
        return False

    def get_connected_entries(self) -> List[str]:
        """获取所有当前已连接的拨号项名称"""
        code, out = self._run_cmd(["rasdial"], timeout=5)
        entries = []
        if code == 0:
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            # rasdial 格式通常第一行"已连接"，随后是连接名称，最后"命令已完成"
            for line in lines:
                if any(x in line for x in ["已连接", "没有连接", "命令已完成", "No connections", "Connected to"]):
                    continue
                entries.append(line)
        return entries

    def get_configured_entries(self) -> List[str]:
        """扫描 Windows 中已创建的所有宽带拨号项 (PBK 电话簿)"""
        pbk_paths = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Network\Connections\Pbk\rasphone.pbk"),
            os.path.expandvars(r"%ALLUSERSPROFILE%\Microsoft\Network\Connections\Pbk\rasphone.pbk"),
        ]
        found = set()
        for p in pbk_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            m = re.match(r"^\[(.*?)\]", line.strip())
                            if m:
                                name = m.group(1).strip()
                                if name:
                                    found.add(name)
                except Exception:
                    pass
        return sorted(list(found))

    def connect(self, username: str, password: str, timeout: int = 20) -> Tuple[bool, str]:
        """执行宽带拨号连接"""
        if not username or not password:
            return False, "用户名或密码不能为空"

        # 确保存在该拨号项
        self.ensure_pbk_entry(self.entry_name)

        if self.is_connected():
            return True, f"宽带连接 [{self.entry_name}] 当前已处于连接状态"

        code, out = self._run_cmd(["rasdial", self.entry_name, username, password], timeout=timeout)
        if code == 0:
            return True, f"宽带连接 [{self.entry_name}] 拨号成功！"

        # 提取 Windows 错误代码 (例如 错误 691)
        err_msg = out
        m = re.search(r"(\d{3,4})", out)
        if m:
            err_code = int(m.group(1))
            detail = ERROR_CODES.get(err_code, "未知拨号错误")
            err_msg = f"错误代码 {err_code} ({detail})\n原始输出: {out}"

        return False, f"宽带拨号失败: {err_msg}"

    def disconnect(self, timeout: int = 10) -> Tuple[bool, str]:
        """断开宽带拨号连接"""
        code, out = self._run_cmd(["rasdial", self.entry_name, "/DISCONNECT"], timeout=timeout)
        if code == 0:
            return True, f"已成功断开宽带连接 [{self.entry_name}]"
        return False, f"断开失败: {out}"

    @staticmethod
    def ensure_pbk_entry(entry_name: str = "宽带连接") -> bool:
        """
        若 Windows 尚未配置该宽带拨号连接，自动在当前用户的电话簿中生成标准 PPPoE 配置项
        """
        pbk_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Network\Connections\Pbk")
        pbk_path = os.path.join(pbk_dir, "rasphone.pbk")

        # 检查是否已包含该名称
        if os.path.exists(pbk_path):
            try:
                with open(pbk_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if f"[{entry_name}]" in content:
                    return True
            except Exception:
                pass

        os.makedirs(pbk_dir, exist_ok=True)
        # 写入标准 Windows PPPoE 拨号配置模板
        template = f"""
[{entry_name}]
Encoding=1
PBVersion=6
Type=5
AutoLogon=0
DialParamsUID=0
Guid=00000000000000000000000000000000
BaseProtocol=1
VpnStrategy=0
ExcludedProtocols=0
LcpExtensions=1
DataEncryption=0
SwCompression=0
NegotiateMultilinkAlways=0
SkipNdisNegotiation=0
SkipDoubleAuth=0
DialMode=1
DialPercent=75
DialSeconds=120
HangUpPercent=10
HangUpSeconds=120
OverridePref=15
RedialAttempts=3
RedialPause=5
AutoRedialOnDrop=0
RedialOnLinkFailure=0
CallbackMode=0
AuthenticateServer=0
ShareMsFilePrint=0
BindMsNetClient=0
SharedPhoneNumbers=0
GlobalAuthenticationProperties=0
IpPrioritizeRemote=1
IpHeaderCompression=0
IpAddress=0.0.0.0
IpDnsAddress=0.0.0.0
IpDns2Address=0.0.0.0
IpWinsAddress=0.0.0.0
IpWins2Address=0.0.0.0
IpAssign=1
IpNameAssign=1
IpDnsFlags=0
IpNetmask=0.0.0.0
MEDIA=rastapi
Port=PPPoE
Device=WAN Miniport (PPPOE)
DEVICE=rastapi
"""
        try:
            with open(pbk_path, "a", encoding="utf-8") as f:
                f.write(template)
            return True
        except Exception as e:
            print(f"[PPPoE] 自动写入 PBK 失败: {e}")
            return False
