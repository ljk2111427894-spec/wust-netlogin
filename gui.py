import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import ctypes

from campus_net.config import ConfigManager
from campus_net.daemon import CampusNetDaemon
from campus_net.autostart import AutostartManager
from campus_net.wifi import WiFiManager
from campus_net.pppoe import PPPoEManager
from campus_net.network_detector import NetworkDetector
from campus_net.tray import SysTrayManager

# 启用高 DPI 缩放适配
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class CampusNetApp(tk.Tk):
    """校园网自动登录与断线重连主界面"""

    def __init__(self, config_mgr: ConfigManager, start_in_tray: bool = False):
        super().__init__()
        self.config_mgr = config_mgr
        self.title("校园网自动登录与断线守护 (59.68.177.9)")

        # 初始化系统状态栏托盘管理器 (托盘常驻，双击呼出主面板)
        self.tray_mgr = SysTrayManager(
            on_show=self.show_from_tray,
            on_login=self._manual_login,
            on_logout=self._manual_logout,
            on_toggle_daemon=self._toggle_daemon,
            on_exit=self._quit_app
        )
        self.tray_mgr.start()

        # 恢复上次保存的窗口尺寸与位置
        saved_geom = self.config_mgr.get("window_geometry", "860x720")
        try:
            self.geometry(saved_geom)
        except Exception:
            self.geometry("860x720")

        self.minsize(800, 680)

        # 记录普通状态下的窗口几何尺寸 (用于非最大化恢复)
        self._last_normal_geometry = saved_geom
        self.bind("<Configure>", self._on_configure)

        # 恢复最大化状态
        if self.config_mgr.get("window_is_maximized", False):
            try:
                self.state("zoomed")
            except Exception:
                pass

        # 样式与配色
        self.colors = {
            "bg": "#f4f6f9",
            "card_bg": "#ffffff",
            "header_bg": "#1e293b",
            "header_fg": "#ffffff",
            "primary": "#2563eb",
            "primary_hover": "#1d4ed8",
            "success": "#16a34a",
            "warning": "#d97706",
            "danger": "#dc2626",
            "text": "#1e293b",
            "text_muted": "#64748b",
            "border": "#e2e8f0"
        }
        self.configure(bg=self.colors["bg"])

        # 初始化后台守护管理器
        self.daemon = CampusNetDaemon(
            config_mgr=self.config_mgr,
            log_callback=self._append_log_threadsafe,
            status_callback=self._update_status_threadsafe
        )

        self._show_password = False
        self._init_ui()
        self._load_config_to_ui()

        # 启动后若配置了自动开启守护，延时执行
        if self.config_mgr.get("auto_daemon_on_start", True):
            self.after(600, self._toggle_daemon)

        # 启动时执行一次状态快速获取
        self.after(300, self._quick_status_check)

        # 若要求以系统状态栏托盘方式启动 (如开机自启或传入 --tray 参数)
        if start_in_tray or self.config_mgr.get("minimize_on_start", False):
            self.withdraw()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def show_from_tray(self):
        """从系统状态栏托盘唤醒恢复显示主窗口"""
        self.after(0, self._restore_ui)

    def _restore_ui(self):
        self.deiconify()
        if self.config_mgr.get("window_is_maximized", False):
            try:
                self.state("zoomed")
            except Exception:
                pass
        else:
            self.state("normal")
        self.lift()
        self.focus_force()

    def hide_to_tray(self):
        """收缩隐藏主窗口至右下角系统状态栏托盘 (不占用任务栏)"""
        self._append_log("INFO", "主窗口已收缩至系统状态栏托盘，守护监控中。双击托盘图标可唤醒面板。")
        self.withdraw()

    def _quit_app(self):
        """彻底退出程序"""
        self._save_window_state()
        self._save_config_from_ui(show_prompt=False)
        if self.daemon.is_running():
            self.daemon.stop()
        if hasattr(self, "tray_mgr") and self.tray_mgr:
            self.tray_mgr.stop()
        self.destroy()
        sys.exit(0)

    def _save_window_state(self):
        try:
            curr_state = self.state()
            if curr_state == "zoomed":
                self.config_mgr.set("window_is_maximized", True)
                if hasattr(self, "_last_normal_geometry") and self._last_normal_geometry:
                    self.config_mgr.set("window_geometry", self._last_normal_geometry)
            elif curr_state == "normal":
                self.config_mgr.set("window_is_maximized", False)
                self.config_mgr.set("window_geometry", self.geometry())
        except Exception:
            pass

    def _on_configure(self, event):
        """窗口尺寸变动时动态记录尺寸 (排除最大化和最小化状态)"""
        if event.widget == self:
            try:
                if self.state() == "normal":
                    self._last_normal_geometry = self.geometry()
            except Exception:
                pass

    def _init_ui(self):
        # 1. 顶部 Header
        header = tk.Frame(self, bg=self.colors["header_bg"], height=64)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        title_lbl = tk.Label(
            header,
            text="🎓 校园网自动登录与断线重连守护系统",
            font=("Microsoft YaHei UI", 14, "bold"),
            bg=self.colors["header_bg"],
            fg=self.colors["header_fg"]
        )
        title_lbl.pack(side=tk.LEFT, padx=20, pady=16)

        subtitle_lbl = tk.Label(
            header,
            text="认证服务器: 59.68.177.9  |  支持 WiFi / 网线宽带拨号 / 有线Web",
            font=("Microsoft YaHei UI", 9),
            bg=self.colors["header_bg"],
            fg="#94a3b8"
        )
        subtitle_lbl.pack(side=tk.RIGHT, padx=20, pady=20)

        # 2. 主体滚动区容器
        main_container = tk.Frame(self, bg=self.colors["bg"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # 3. 状态看板卡片
        self._build_status_card(main_container)

        # 4. 配置卡片区 (双列并排)
        cfg_container = tk.Frame(main_container, bg=self.colors["bg"])
        cfg_container.pack(fill=tk.X, pady=8)

        self._build_account_card(cfg_container)
        self._build_network_mode_card(cfg_container)

        # 5. 操作控制按钮区
        self._build_action_bar(main_container)

        # 6. 实时运行日志卡片
        self._build_log_card(main_container)

    def _build_status_card(self, parent):
        card = tk.LabelFrame(
            parent,
            text=" 📊 当前网络与认证实时状态 ",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text"],
            padx=16,
            pady=10,
            relief=tk.GROOVE,
            bd=1
        )
        card.pack(fill=tk.X, pady=(0, 6))

        top_row = tk.Frame(card, bg=self.colors["card_bg"])
        top_row.pack(fill=tk.X, pady=(0, 8))

        # 状态指示胶囊
        self.lbl_status_badge = tk.Label(
            top_row,
            text="🟡 正在检测网络...",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#fef3c7",
            fg="#b45309",
            padx=12,
            pady=4,
            relief=tk.FLAT
        )
        self.lbl_status_badge.pack(side=tk.LEFT)

        # 守护状态标识
        self.lbl_daemon_badge = tk.Label(
            top_row,
            text="🛡️ 守护状态: 未运行",
            font=("Microsoft YaHei UI", 9),
            bg="#e2e8f0",
            fg="#475569",
            padx=10,
            pady=4
        )
        self.lbl_daemon_badge.pack(side=tk.RIGHT)

        # 详细参数指标网格
        grid = tk.Frame(card, bg=self.colors["card_bg"])
        grid.pack(fill=tk.X)

        self.val_ip = tk.StringVar(value="-")
        self.val_user = tk.StringVar(value="-")
        self.val_medium = tk.StringVar(value="-")
        self.val_traffic = tk.StringVar(value="-")
        self.val_latency = tk.StringVar(value="-")
        self.val_time = tk.StringVar(value="-")

        items = [
            ("校园网 IP:", self.val_ip, 0, 0),
            ("认证账号:", self.val_user, 0, 1),
            ("当前网络介质:", self.val_medium, 0, 2),
            ("已用流量:", self.val_traffic, 1, 0),
            ("网络延迟:", self.val_latency, 1, 1),
            ("登录时间:", self.val_time, 1, 2),
        ]

        for label_text, var, row, col in items:
            box = tk.Frame(grid, bg=self.colors["card_bg"], padx=8, pady=2)
            box.grid(row=row, column=col, sticky="w", padx=10, pady=2)
            tk.Label(box, text=label_text, font=("Microsoft YaHei UI", 9), fg=self.colors["text_muted"], bg=self.colors["card_bg"]).pack(side=tk.LEFT)
            tk.Label(box, textvariable=var, font=("Microsoft YaHei UI", 9, "bold"), fg=self.colors["text"], bg=self.colors["card_bg"]).pack(side=tk.LEFT, padx=4)

        for col in range(3):
            grid.grid_columnconfigure(col, weight=1)

    def _build_account_card(self, parent):
        card = tk.LabelFrame(
            parent,
            text=" 👤 账号与认证凭据 ",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text"],
            padx=12,
            pady=8,
            relief=tk.GROOVE,
            bd=1
        )
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        # 账号
        f_user = tk.Frame(card, bg=self.colors["card_bg"])
        f_user.pack(fill=tk.X, pady=4)
        tk.Label(f_user, text="账号 / 学号:", font=("Microsoft YaHei UI", 9), width=10, anchor="w", bg=self.colors["card_bg"]).pack(side=tk.LEFT)
        self.ent_username = tk.Entry(f_user, font=("Microsoft YaHei UI", 9))
        self.ent_username.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # 密码
        f_pwd = tk.Frame(card, bg=self.colors["card_bg"])
        f_pwd.pack(fill=tk.X, pady=4)
        tk.Label(f_pwd, text="校园网密码:", font=("Microsoft YaHei UI", 9), width=10, anchor="w", bg=self.colors["card_bg"]).pack(side=tk.LEFT)
        self.ent_password = tk.Entry(f_pwd, font=("Microsoft YaHei UI", 9), show="*")
        self.ent_password.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.btn_pwd_toggle = tk.Button(f_pwd, text="👁", font=("Microsoft YaHei UI", 8), width=3, command=self._toggle_password_view, relief=tk.FLAT, bg="#e2e8f0")
        self.btn_pwd_toggle.pack(side=tk.RIGHT)

        # 运营商后缀
        f_carrier = tk.Frame(card, bg=self.colors["card_bg"])
        f_carrier.pack(fill=tk.X, pady=4)
        tk.Label(f_carrier, text="运营商选择:", font=("Microsoft YaHei UI", 9), width=10, anchor="w", bg=self.colors["card_bg"]).pack(side=tk.LEFT)
        self.cmb_carrier = ttk.Combobox(f_carrier, values=[
            "校园网内网/无后缀",
            "中国电信 (@telecom)",
            "中国移动 (@cmcc)",
            "中国联通 (@unicom)"
        ], state="readonly", font=("Microsoft YaHei UI", 9))
        self.cmb_carrier.current(0)
        self.cmb_carrier.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # 认证服务器
        f_url = tk.Frame(card, bg=self.colors["card_bg"])
        f_url.pack(fill=tk.X, pady=4)
        tk.Label(f_url, text="认证服务器:", font=("Microsoft YaHei UI", 9), width=10, anchor="w", bg=self.colors["card_bg"]).pack(side=tk.LEFT)
        self.ent_url = tk.Entry(f_url, font=("Microsoft YaHei UI", 9))
        self.ent_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

    def _build_network_mode_card(self, parent):
        card = tk.LabelFrame(
            parent,
            text=" 🌐 连接模式与守护参数 ",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text"],
            padx=12,
            pady=8,
            relief=tk.GROOVE,
            bd=1
        )
        card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        # 连接模式
        f_mode = tk.Frame(card, bg=self.colors["card_bg"])
        f_mode.pack(fill=tk.X, pady=2)
        tk.Label(f_mode, text="连接方式:", font=("Microsoft YaHei UI", 9), width=10, anchor="w", bg=self.colors["card_bg"]).pack(side=tk.LEFT)
        self.var_mode = tk.StringVar(value="wifi_web")
        self.cmb_mode = ttk.Combobox(
            f_mode,
            textvariable=self.var_mode,
            values=[
                "WiFi无线 + 网页认证 (推荐无线)",
                "网线宽带拨号 PPPoE (宿舍有线)",
                "网线直连 + 网页认证 (有线Web)",
                "智能混合自适应 (优先有线回退WiFi)"
            ],
            state="readonly",
            font=("Microsoft YaHei UI", 9)
        )
        self.cmb_mode.current(0)
        self.cmb_mode.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # WiFi SSID
        f_wifi = tk.Frame(card, bg=self.colors["card_bg"])
        f_wifi.pack(fill=tk.X, pady=3)
        tk.Label(f_wifi, text="WiFi SSID:", font=("Microsoft YaHei UI", 9), width=10, anchor="w", bg=self.colors["card_bg"]).pack(side=tk.LEFT)
        self.ent_ssid = tk.Entry(f_wifi, font=("Microsoft YaHei UI", 9))
        self.ent_ssid.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        btn_scan = tk.Button(f_wifi, text="🔍扫描", font=("Microsoft YaHei UI", 8), command=self._scan_wifis, relief=tk.FLAT, bg="#e2e8f0")
        btn_scan.pack(side=tk.RIGHT)

        # 宽带连接名称
        f_pppoe = tk.Frame(card, bg=self.colors["card_bg"])
        f_pppoe.pack(fill=tk.X, pady=3)
        tk.Label(f_pppoe, text="拨号连接名:", font=("Microsoft YaHei UI", 9), width=10, anchor="w", bg=self.colors["card_bg"]).pack(side=tk.LEFT)
        self.ent_pppoe = tk.Entry(f_pppoe, font=("Microsoft YaHei UI", 9))
        self.ent_pppoe.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        btn_pbk = tk.Button(f_pppoe, text="➕创建拨号", font=("Microsoft YaHei UI", 8), command=self._create_pppoe_entry, relief=tk.FLAT, bg="#e2e8f0")
        btn_pbk.pack(side=tk.RIGHT)

        # 选项复选框
        f_opts = tk.Frame(card, bg=self.colors["card_bg"])
        f_opts.pack(fill=tk.X, pady=2)
        self.var_reconnect = tk.BooleanVar(value=True)
        self.chk_reconnect = tk.Checkbutton(f_opts, text="断线自动重连", variable=self.var_reconnect, font=("Microsoft YaHei UI", 9), bg=self.colors["card_bg"])
        self.chk_reconnect.pack(side=tk.LEFT, padx=(0, 10))

        self.var_autostart = tk.BooleanVar(value=False)
        self.chk_autostart = tk.Checkbutton(f_opts, text="开机自启(状态栏托盘常驻)", variable=self.var_autostart, font=("Microsoft YaHei UI", 9), bg=self.colors["card_bg"], command=self._toggle_autostart)
        self.chk_autostart.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(f_opts, text="心跳(秒):", font=("Microsoft YaHei UI", 9), bg=self.colors["card_bg"]).pack(side=tk.LEFT)
        self.spn_interval = tk.Spinbox(f_opts, from_=5, to=300, width=4, font=("Microsoft YaHei UI", 9))
        self.spn_interval.pack(side=tk.LEFT, padx=4)

        # 守护最小化偏好
        f_opts2 = tk.Frame(card, bg=self.colors["card_bg"])
        f_opts2.pack(fill=tk.X, pady=2)
        self.var_minimize_on_daemon = tk.BooleanVar(value=False)
        self.chk_min_daemon = tk.Checkbutton(
            f_opts2,
            text="开启守护后收缩至状态栏",
            variable=self.var_minimize_on_daemon,
            font=("Microsoft YaHei UI", 9),
            bg=self.colors["card_bg"]
        )
        self.chk_min_daemon.pack(side=tk.LEFT, padx=(0, 10))

        self.var_close_to_tray = tk.BooleanVar(value=True)
        self.chk_close_tray = tk.Checkbutton(
            f_opts2,
            text="点击关闭[X]时收缩到状态栏",
            variable=self.var_close_to_tray,
            font=("Microsoft YaHei UI", 9),
            bg=self.colors["card_bg"]
        )
        self.chk_close_tray.pack(side=tk.LEFT)

    def _build_action_bar(self, parent):
        bar = tk.Frame(parent, bg=self.colors["bg"])
        bar.pack(fill=tk.X, pady=4)

        # 立即登录
        self.btn_login = tk.Button(
            bar,
            text="⚡ 立即登录认证",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors["primary"],
            fg="#ffffff",
            activebackground=self.colors["primary_hover"],
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._manual_login
        )
        self.btn_login.pack(side=tk.LEFT, padx=(0, 6))

        # 注销断开
        self.btn_logout = tk.Button(
            bar,
            text="🔌 注销 / 断开",
            font=("Microsoft YaHei UI", 10),
            bg="#e2e8f0",
            fg=self.colors["text"],
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._manual_logout
        )
        self.btn_logout.pack(side=tk.LEFT, padx=(0, 6))

        # 启动/停止守护
        self.btn_daemon_toggle = tk.Button(
            bar,
            text="🛡️ 开启自动守护 (重连)",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors["success"],
            fg="#ffffff",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._toggle_daemon
        )
        self.btn_daemon_toggle.pack(side=tk.LEFT, padx=(0, 6))

        # 最小化到状态栏托盘 (不占任务栏)
        self.btn_minimize = tk.Button(
            bar,
            text="🗕 最小化到状态栏",
            font=("Microsoft YaHei UI", 10),
            bg="#e2e8f0",
            fg=self.colors["text"],
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.hide_to_tray
        )
        self.btn_minimize.pack(side=tk.LEFT, padx=(0, 6))

        # 全面诊断
        btn_diag = tk.Button(
            bar,
            text="🔍 网络诊断",
            font=("Microsoft YaHei UI", 10),
            bg="#e2e8f0",
            fg=self.colors["text"],
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._run_diagnostic
        )
        btn_diag.pack(side=tk.LEFT, padx=(0, 6))

        # 退出程序
        btn_exit = tk.Button(
            bar,
            text="❌ 退出程序",
            font=("Microsoft YaHei UI", 10),
            bg="#fee2e2",
            fg="#b91c1c",
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._quit_app
        )
        btn_exit.pack(side=tk.RIGHT, padx=(6, 0))

        # 保存设置
        btn_save = tk.Button(
            bar,
            text="💾 保存配置",
            font=("Microsoft YaHei UI", 10),
            bg="#f1f5f9",
            fg=self.colors["text"],
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._save_config_from_ui
        )
        btn_save.pack(side=tk.RIGHT)

    def _build_log_card(self, parent):
        card = tk.LabelFrame(
            parent,
            text=" 📝 运行日志与重连记录 ",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text"],
            padx=10,
            pady=6,
            relief=tk.GROOVE,
            bd=1
        )
        card.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        # 控制小工具栏
        tool_bar = tk.Frame(card, bg=self.colors["card_bg"])
        tool_bar.pack(fill=tk.X, pady=(0, 4))
        tk.Label(tool_bar, text="实时日志流 (自动记录认证、断线与重连结果):", font=("Microsoft YaHei UI", 8), fg=self.colors["text_muted"], bg=self.colors["card_bg"]).pack(side=tk.LEFT)

        btn_clear = tk.Button(tool_bar, text="清空日志", font=("Microsoft YaHei UI", 8), command=self._clear_log, relief=tk.FLAT, bg="#f1f5f9")
        btn_clear.pack(side=tk.RIGHT)

        # 文本框
        self.txt_log = scrolledtext.ScrolledText(
            card,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#ffffff",
            relief=tk.FLAT
        )
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        # 配置文本样式高亮标签
        self.txt_log.tag_config("SUCCESS", foreground="#4ade80")
        self.txt_log.tag_config("INFO", foreground="#60a5fa")
        self.txt_log.tag_config("WARN", foreground="#fbbf24")
        self.txt_log.tag_config("ERROR", foreground="#f87171", font=("Consolas", 9, "bold"))
        self.txt_log.tag_config("TIME", foreground="#94a3b8")

    def _toggle_password_view(self):
        self._show_password = not self._show_password
        self.ent_password.config(show="" if self._show_password else "*")
        self.btn_pwd_toggle.config(text="🔒" if self._show_password else "👁")

    def _load_config_to_ui(self):
        cfg = self.config_mgr.data
        self.ent_username.delete(0, tk.END)
        self.ent_username.insert(0, cfg.get("username", ""))

        self.ent_password.delete(0, tk.END)
        self.ent_password.insert(0, cfg.get("password", ""))

        self.ent_url.delete(0, tk.END)
        self.ent_url.insert(0, cfg.get("auth_url", "http://59.68.177.9"))

        self.ent_ssid.delete(0, tk.END)
        self.ent_ssid.insert(0, cfg.get("wifi_ssid", "WUST-WiFi6"))

        self.ent_pppoe.delete(0, tk.END)
        self.ent_pppoe.insert(0, cfg.get("pppoe_name", "宽带连接"))

        self.var_reconnect.set(cfg.get("auto_reconnect", True))
        self.var_autostart.set(AutostartManager.is_enabled())
        self.var_minimize_on_daemon.set(cfg.get("minimize_on_daemon", False))
        self.var_close_to_tray.set(cfg.get("close_to_tray", True))

        self.spn_interval.delete(0, tk.END)
        self.spn_interval.insert(0, str(cfg.get("check_interval", 15)))

        # 匹配运营商
        carrier = cfg.get("carrier", "")
        if carrier == "@telecom":
            self.cmb_carrier.current(1)
        elif carrier == "@cmcc":
            self.cmb_carrier.current(2)
        elif carrier == "@unicom":
            self.cmb_carrier.current(3)
        else:
            self.cmb_carrier.current(0)

        # 匹配模式
        mode = cfg.get("connect_mode", "wifi_web")
        mode_idx = {"wifi_web": 0, "cable_pppoe": 1, "cable_web": 2, "auto": 3}.get(mode, 0)
        self.cmb_mode.current(mode_idx)

    def _save_config_from_ui(self, show_prompt: bool = True):
        self.config_mgr.set("username", self.ent_username.get().strip())
        self.config_mgr.set("password", self.ent_password.get().strip())
        self.config_mgr.set("auth_url", self.ent_url.get().strip())
        self.config_mgr.set("wifi_ssid", self.ent_ssid.get().strip())
        self.config_mgr.set("pppoe_name", self.ent_pppoe.get().strip())
        self.config_mgr.set("auto_reconnect", self.var_reconnect.get())

        try:
            interval = int(self.spn_interval.get())
            if interval < 5: interval = 5
            self.config_mgr.set("check_interval", interval)
        except ValueError:
            self.config_mgr.set("check_interval", 15)

        # 运营商后缀解析 (兼容索引与文本匹配)
        carrier_idx = self.cmb_carrier.current()
        carrier_str = self.cmb_carrier.get()
        if carrier_idx == 1 or "@telecom" in carrier_str:
            carrier = "@telecom"
        elif carrier_idx == 2 or "@cmcc" in carrier_str:
            carrier = "@cmcc"
        elif carrier_idx == 3 or "@unicom" in carrier_str:
            carrier = "@unicom"
        else:
            carrier = ""
        self.config_mgr.set("carrier", carrier)

        # 连接模式解析 (兼容索引与文本匹配)
        mode_idx = self.cmb_mode.current()
        mode_str = self.cmb_mode.get()
        if mode_idx == 1 or "PPPoE" in mode_str or "拨号" in mode_str:
            mode = "cable_pppoe"
        elif mode_idx == 2 or "有线Web" in mode_str or "网线直连" in mode_str:
            mode = "cable_web"
        elif mode_idx == 3 or "智能混合" in mode_str:
            mode = "auto"
        else:
            mode = "wifi_web"
        self.config_mgr.set("connect_mode", mode)
        self.config_mgr.set("minimize_on_daemon", self.var_minimize_on_daemon.get())
        self.config_mgr.set("close_to_tray", self.var_close_to_tray.get())

        # 保存当前窗口尺寸与最大化偏好 (支持关闭重启后完全还原)
        try:
            curr_state = self.state()
            if curr_state == "zoomed":
                self.config_mgr.set("window_is_maximized", True)
                if hasattr(self, "_last_normal_geometry") and self._last_normal_geometry:
                    self.config_mgr.set("window_geometry", self._last_normal_geometry)
            elif curr_state == "normal":
                self.config_mgr.set("window_is_maximized", False)
                self.config_mgr.set("window_geometry", self.geometry())
        except Exception:
            pass

        ok = self.config_mgr.save()
        if ok:
            self._append_log("SUCCESS", f"配置已保存至: {self.config_mgr.config_path}")
            if show_prompt:
                messagebox.showinfo("成功", f"配置已成功保存！\n\n文件路径:\n{self.config_mgr.config_path}")
        else:
            self._append_log("ERROR", f"配置写入失败: {self.config_mgr.config_path}")
            if show_prompt:
                messagebox.showerror("错误", f"配置文件写入失败，请检查文件写入权限！\n路径: {self.config_mgr.config_path}")

    def _toggle_autostart(self):
        enable = self.var_autostart.get()
        ok, msg = AutostartManager.set_enabled(enable)
        if ok:
            self._append_log("INFO", msg)
        else:
            messagebox.showerror("错误", msg)
            self.var_autostart.set(not enable)

    def _manual_login(self):
        self._save_config_from_ui(show_prompt=False)
        self.btn_login.config(state=tk.DISABLED)

        def worker():
            try:
                self.daemon.perform_login()
            finally:
                self.after(500, lambda: self.btn_login.config(state=tk.NORMAL))
                self.after(800, self._quick_status_check)

        threading.Thread(target=worker, daemon=True).start()

    def _manual_logout(self):
        self._save_config_from_ui(show_prompt=False)
        def worker():
            self.daemon.perform_logout()
            self.after(500, self._quick_status_check)
        threading.Thread(target=worker, daemon=True).start()

    def _toggle_daemon(self):
        self._save_config_from_ui(show_prompt=False)
        if self.daemon.is_running():
            self.daemon.stop()
            self.btn_daemon_toggle.config(
                text="🛡️ 开启自动守护 (重连)",
                bg=self.colors["success"]
            )
            self.lbl_daemon_badge.config(
                text="🛡️ 守护状态: 未运行",
                bg="#e2e8f0",
                fg="#475569"
            )
        else:
            self.daemon.start()
            self.btn_daemon_toggle.config(
                text="⏹ 停止守护进程",
                bg=self.colors["danger"]
            )
            self.lbl_daemon_badge.config(
                text="🛡️ 守护状态: 正在后台监控",
                bg="#dcfce7",
                fg="#15803d"
            )
            if self.var_minimize_on_daemon.get():
                self._append_log("INFO", "守护已启动，1秒后将自动收缩至状态栏托盘。双击托盘图标可查看实时监控。")
                self.after(1000, self.hide_to_tray)

    def _minimize_window(self):
        """最小化到 Windows 任务栏，保留图标方便随时点击查看实时监控"""
        self._append_log("INFO", "程序已最小化至任务栏。守护进行中，点击任务栏图标随时查看实时监控。")
        self.iconify()

    def _scan_wifis(self):
        wm = WiFiManager()
        ssids = wm.list_available_ssids()
        if not ssids:
            messagebox.showinfo("WiFi扫描", "未扫描到可用网络，请检查无线网卡是否已开启")
            return
        
        # 弹窗或直接选择
        top = tk.Toplevel(self)
        top.title("选择要连接的校园网 WiFi")
        top.geometry("340x300")
        top.transient(self)

        tk.Label(top, text="双击或选择后点击确定填入:", font=("Microsoft YaHei UI", 9)).pack(pady=8)
        lb = tk.Listbox(top, font=("Microsoft YaHei UI", 9), selectmode=tk.SINGLE)
        lb.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        for s in ssids:
            lb.insert(tk.END, s)

        def on_select(event=None):
            sel = lb.curselection()
            if sel:
                chosen = lb.get(sel[0])
                self.ent_ssid.delete(0, tk.END)
                self.ent_ssid.insert(0, chosen)
                self._append_log("INFO", f"已从扫描列表选择 WiFi: {chosen}")
                top.destroy()

        # 绑定双击与回车键直接确认
        lb.bind("<Double-Button-1>", on_select)
        lb.bind("<Return>", on_select)

        btn_box = tk.Frame(top)
        btn_box.pack(pady=8)
        btn = tk.Button(btn_box, text="确定选择", command=on_select, font=("Microsoft YaHei UI", 9), bg=self.colors["primary"], fg="#ffffff", padx=14, pady=3)
        btn.pack(side=tk.LEFT, padx=6)
        btn_cancel = tk.Button(btn_box, text="取消", command=top.destroy, font=("Microsoft YaHei UI", 9), bg="#e2e8f0", padx=10, pady=3)
        btn_cancel.pack(side=tk.LEFT, padx=6)

    def _create_pppoe_entry(self):
        name = self.ent_pppoe.get().strip() or "宽带连接"
        ok = PPPoEManager.ensure_pbk_entry(name)
        if ok:
            messagebox.showinfo("成功", f"已在 Windows 拨号配置中创建 [{name}]！\n现在您可以直接插上网线使用拨号模式。")
        else:
            messagebox.showerror("失败", "写入拨号配置文件失败，请以管理员身份运行。")

    def _run_diagnostic(self):
        self._append_log("INFO", "正在启动全面网络诊断...")
        def worker():
            nd = NetworkDetector(probe_urls=self.config_mgr.get("probe_urls"))
            diag = nd.run_full_diagnostic()
            self._append_log("INFO", "========== 网络诊断报告 ==========")
            self._append_log("INFO", f"外网连通状态: {diag['internet_state']} ({diag['message']})")
            self._append_log("INFO", f"网络往返延迟: {diag['latency_ms']} ms")
            self._append_log("INFO", f"校园网认证服务器 (59.68.177.9): {'可达 (在线)' if diag['portal_reachable'] else '不可达 (离线/未插网线/未连WiFi)'}")
            self._append_log("INFO", f"有线网卡状态: {'已接入网线' if diag['ethernet_connected'] else '未连接/无网线'} ({diag['ethernet_name']})")
            self._append_log("INFO", f"无线网卡状态: {'已连上无线' if diag['wifi_connected'] else '未连接'} ({diag['wifi_name']})")
            self._append_log("INFO", "==================================")
        threading.Thread(target=worker, daemon=True).start()

    def _quick_status_check(self):
        def worker():
            wm = WiFiManager()
            w_status = wm.get_status()
            nd = NetworkDetector()
            state, reason, latency = nd.check_internet(timeout=2.0)
            from campus_net.web_auth import WebAuthenticator
            auth = WebAuthenticator(base_url=self.config_mgr.get("auth_url", "http://59.68.177.9"))
            p_status = auth.check_status()

            self._update_status_threadsafe({
                "is_online": (state == "ONLINE"),
                "internet_state": state,
                "latency_ms": round(latency, 1),
                "portal_online": p_status.get("is_online", False),
                "username": p_status.get("username", ""),
                "user_ip": p_status.get("ip", ""),
                "bytes_str": p_status.get("bytes_str", ""),
                "online_time": p_status.get("add_time", ""),
                "wifi_ssid": w_status.get("ssid", ""),
                "wifi_connected": w_status.get("connected", False),
                "wifi_signal": w_status.get("signal", "")
            })
        threading.Thread(target=worker, daemon=True).start()

    def _update_status_threadsafe(self, s: Dict[str, Any]):
        self.after(0, lambda: self._apply_status_ui(s))

    def _apply_status_ui(self, s: Dict[str, Any]):
        is_online = s.get("is_online", False)
        portal_online = s.get("portal_online", False)

        if is_online:
            self.lbl_status_badge.config(
                text="🟢 正常在线 (网络畅通)",
                bg="#dcfce7",
                fg="#15803d"
            )
        elif portal_online:
            self.lbl_status_badge.config(
                text="🟡 已登录Portal，外网检查中",
                bg="#fef3c7",
                fg="#b45309"
            )
        else:
            self.lbl_status_badge.config(
                text="🔴 未连接 / 已离线",
                bg="#fee2e2",
                fg="#b91c1c"
            )

        self.val_ip.set(s.get("user_ip") or "-")
        self.val_user.set(s.get("username") or "-")
        
        ssid = s.get("wifi_ssid")
        sig = s.get("wifi_signal")
        if ssid:
            self.val_medium.set(f"WiFi: {ssid} ({sig})")
        else:
            self.val_medium.set("以太网 / 宽带")

        self.val_traffic.set(s.get("bytes_str") or "-")
        lat = s.get("latency_ms", 0)
        self.val_latency.set(f"{lat} ms" if lat > 0 else "-")
        raw_time = s.get("online_time", "")
        self.val_time.set(raw_time[:19].replace("T", " ") if raw_time else "-")

        # 同步更新右下角系统状态栏托盘图标与鼠标悬浮提示
        if hasattr(self, "tray_mgr") and self.tray_mgr:
            state = s.get("internet_state", "UNKNOWN")
            lat = s.get("latency_ms", 0)
            user = s.get("username", "")
            ip = s.get("user_ip", "")
            is_online = s.get("is_online", False)
            status_text = "正常在线" if is_online else ("待认证" if s.get("portal_online") else "已离线")
            tooltip = f"校园网状态: {status_text} | 延迟: {lat}ms\n账号: {user} | IP: {ip}\n(双击托盘图标打开主面板)"
            self.tray_mgr.update_status(state, tooltip)

    def _append_log_threadsafe(self, level: str, msg: str):
        self.after(0, lambda: self._append_log(level, msg))

    def _append_log(self, level: str, msg: str):
        t = time.strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{t}] ", "TIME")
        self.txt_log.insert(tk.END, f"[{level}] ", level)
        self.txt_log.insert(tk.END, f"{msg}\n")
        self.txt_log.see(tk.END)

    def _clear_log(self):
        self.txt_log.delete("1.0", tk.END)

    def _on_close(self):
        # 记录当前窗口尺寸与最大化偏好 (供下次打开时精确还原)
        self._save_window_state()
        self._save_config_from_ui(show_prompt=False)

        # 若勾选了关闭时隐藏到状态栏托盘 (默认开启)，则收缩到托盘保持后台守护
        if self.var_close_to_tray.get():
            self.hide_to_tray()
        else:
            self._quit_app()
