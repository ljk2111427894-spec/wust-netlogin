import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray

def generate_tray_icon(bg_color: str = "#16a34a") -> Image.Image:
    """动态绘制系统状态栏托盘图标 (64x64 高清抗锯齿圆环+WiFi波纹)"""
    img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 底色圆徽标
    d.ellipse((3, 3, 61, 61), fill=bg_color)
    d.ellipse((5, 5, 59, 59), outline=(255, 255, 255, 180), width=2)
    # 绘制 WiFi 信号波纹线条
    d.arc((14, 14, 50, 50), start=210, end=330, fill="white", width=3)
    d.arc((21, 21, 43, 43), start=210, end=330, fill="white", width=3)
    # 核心信号发射点
    d.ellipse((29, 39, 35, 45), fill="white")
    return img

class SysTrayManager:
    """Windows 系统状态栏 / 托盘图标管理器 (基于 pystray)"""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_login: Optional[Callable[[], None]] = None,
        on_logout: Optional[Callable[[], None]] = None,
        on_toggle_daemon: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None
    ):
        self.on_show = on_show
        self.on_login = on_login
        self.on_logout = on_logout
        self.on_toggle_daemon = on_toggle_daemon
        self.on_exit = on_exit

        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        self._current_state = "UNKNOWN"

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("🖥️ 显示主界面", lambda icon, item: self.on_show(), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚡ 立即登录认证", lambda icon, item: self.on_login() if self.on_login else None),
            pystray.MenuItem("🔌 注销断开连接", lambda icon, item: self.on_logout() if self.on_logout else None),
            pystray.MenuItem("🛡️ 开启/停止守护", lambda icon, item: self.on_toggle_daemon() if self.on_toggle_daemon else None),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ 彻底退出程序", lambda icon, item: self._handle_exit()),
        )

    def start(self):
        """启动托盘图标线程"""
        if self._icon is not None:
            return

        initial_img = generate_tray_icon("#16a34a")
        self._icon = pystray.Icon(
            name="CampusNetAutoLogin",
            icon=initial_img,
            title="校园网自动认证守护 (59.68.177.9)",
            menu=self._build_menu()
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True, name="SysTrayThread")
        self._thread.start()

    def update_status(self, state: str, tooltip: str = ""):
        """更新托盘图标颜色与鼠标悬停提示文本"""
        if not self._icon:
            return

        color_map = {
            "ONLINE": "#16a34a",            # 绿色：正常在线
            "CAPTIVE_PORTAL": "#d97706",    # 黄色：被拦截/待认证
            "OFFLINE": "#dc2626",           # 红色：掉线
            "CONNECTING": "#2563eb"         # 蓝色：正在连接中
        }
        color = color_map.get(state, "#64748b")
        try:
            self._icon.icon = generate_tray_icon(color)
            if tooltip:
                # Windows 托盘提示限制在 127 字符内
                self._icon.title = tooltip[:125]
        except Exception:
            pass

    def stop(self):
        """停止托盘图标"""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None

    def _handle_exit(self):
        self.stop()
        if self.on_exit:
            self.on_exit()
