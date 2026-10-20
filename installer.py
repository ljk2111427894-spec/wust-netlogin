import os
import sys
import zipfile
import threading
import winreg
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import win32com.client

APP_NAME = "CampusNetAutoLogin"
APP_DISPLAY_NAME = "校园网自动登录与状态栏守护"
APP_VERSION = "1.0.0"
APP_PUBLISHER = "WUST CampusNet Helper"

class InstallerApp(tk.Tk):
    """现代化 Windows 图形化安装向导"""

    def __init__(self):
        super().__init__()
        self.title(f"{APP_DISPLAY_NAME} - 安装向导 (v{APP_VERSION})")
        self.geometry("620x460")
        self.resizable(False, False)

        # 样式配色
        self.colors = {
            "bg": "#f8fafc",
            "card_bg": "#ffffff",
            "header_bg": "#1e293b",
            "header_fg": "#ffffff",
            "primary": "#2563eb",
            "primary_hover": "#1d4ed8",
            "success": "#16a34a",
            "text": "#0f172a",
            "text_muted": "#64748b",
            "border": "#e2e8f0"
        }
        self.configure(bg=self.colors["bg"])

        # 默认安装在当前用户的 LocalAppData 目录下，完全免管理员 UAC 权限
        default_dir = os.path.join(os.path.expandvars(r"%LOCALAPPDATA%"), "Programs", "CampusNetLogin")
        self.install_dir = tk.StringVar(value=default_dir)

        self.var_desktop_icon = tk.BooleanVar(value=True)
        self.var_start_menu = tk.BooleanVar(value=True)
        self.var_autostart = tk.BooleanVar(value=True)
        self.var_launch_now = tk.BooleanVar(value=True)

        self._init_ui()

    def _init_ui(self):
        # 1. 顶部 Header
        header = tk.Frame(self, bg=self.colors["header_bg"], height=70)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(
            header,
            text=f"🎓 {APP_DISPLAY_NAME}",
            font=("Microsoft YaHei UI", 13, "bold"),
            bg=self.colors["header_bg"],
            fg=self.colors["header_fg"]
        ).pack(anchor="w", padx=20, pady=(12, 2))

        tk.Label(
            header,
            text=f"版本 v{APP_VERSION}  |  支持 59.68.177.9 Web认证、PPPoE宽带拨号与状态栏守护",
            font=("Microsoft YaHei UI", 9),
            bg=self.colors["header_bg"],
            fg="#94a3b8"
        ).pack(anchor="w", padx=20)

        # 2. 中间卡片容器
        self.body = tk.Frame(self, bg=self.colors["bg"], padx=20, pady=16)
        self.body.pack(fill=tk.BOTH, expand=True)

        # 安装路径卡片
        card_dir = tk.LabelFrame(
            self.body,
            text=" 📁 安装目录选择 ",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text"],
            padx=14,
            pady=10,
            relief=tk.GROOVE,
            bd=1
        )
        card_dir.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            card_dir,
            text="程序将安装到以下文件夹 (推荐默认路径，免管理员权限):",
            font=("Microsoft YaHei UI", 9),
            bg=self.colors["card_bg"],
            fg=self.colors["text_muted"]
        ).pack(anchor="w", pady=(0, 6))

        dir_box = tk.Frame(card_dir, bg=self.colors["card_bg"])
        dir_box.pack(fill=tk.X)

        self.ent_dir = tk.Entry(dir_box, textvariable=self.install_dir, font=("Microsoft YaHei UI", 9))
        self.ent_dir.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        btn_browse = tk.Button(
            dir_box,
            text="浏览...",
            font=("Microsoft YaHei UI", 9),
            command=self._browse_dir,
            bg="#f1f5f9",
            relief=tk.FLAT,
            padx=12,
            pady=2
        )
        btn_browse.pack(side=tk.RIGHT)

        # 快捷方式与自启选项卡片
        card_opts = tk.LabelFrame(
            self.body,
            text=" ⚙️ 快捷选项配置 ",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text"],
            padx=14,
            pady=10,
            relief=tk.GROOVE,
            bd=1
        )
        card_opts.pack(fill=tk.X, pady=(0, 10))

        tk.Checkbutton(
            card_opts,
            text="创建桌面快捷方式 (桌面一键呼出控制面板)",
            variable=self.var_desktop_icon,
            font=("Microsoft YaHei UI", 9),
            bg=self.colors["card_bg"]
        ).pack(anchor="w", pady=2)

        tk.Checkbutton(
            card_opts,
            text="添加到 Windows 开始菜单快捷方式列表",
            variable=self.var_start_menu,
            font=("Microsoft YaHei UI", 9),
            bg=self.colors["card_bg"]
        ).pack(anchor="w", pady=2)

        tk.Checkbutton(
            card_opts,
            text="设置开机自动启动 (静默常驻右下角状态栏托盘，断网自动重连)",
            variable=self.var_autostart,
            font=("Microsoft YaHei UI", 9),
            bg=self.colors["card_bg"]
        ).pack(anchor="w", pady=2)

        # 进度与提示
        self.lbl_progress = tk.Label(
            self.body,
            text="准备就绪，点击下方【立即安装】开始部署...",
            font=("Microsoft YaHei UI", 9),
            bg=self.colors["bg"],
            fg=self.colors["text_muted"]
        )
        self.lbl_progress.pack(anchor="w", pady=(0, 4))

        self.progress_bar = ttk.Progressbar(self.body, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))

        # 3. 底部按钮栏
        self.bottom_bar = tk.Frame(self, bg=self.colors["bg"], padx=20, pady=10)
        self.bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_install = tk.Button(
            self.bottom_bar,
            text="🚀 立即安装",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors["primary"],
            fg="#ffffff",
            activebackground=self.colors["primary_hover"],
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=18,
            pady=6,
            cursor="hand2",
            command=self._start_install
        )
        self.btn_install.pack(side=tk.RIGHT, padx=(8, 0))

        self.btn_cancel = tk.Button(
            self.bottom_bar,
            text="取消",
            font=("Microsoft YaHei UI", 10),
            bg="#e2e8f0",
            fg=self.colors["text"],
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.destroy
        )
        self.btn_cancel.pack(side=tk.RIGHT)

    def _browse_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.install_dir.get(), title="选择安装目标文件夹")
        if chosen:
            self.install_dir.set(os.path.normpath(chosen))

    def _start_install(self):
        target_dir = self.install_dir.get().strip()
        if not target_dir:
            messagebox.showwarning("提示", "请输入有效的安装目录！")
            return

        self.btn_install.config(state=tk.DISABLED)
        self.btn_cancel.config(state=tk.DISABLED)
        self.ent_dir.config(state=tk.DISABLED)

        threading.Thread(target=self._install_worker, args=(target_dir,), daemon=True).start()

    def _find_payload_zip(self) -> str:
        """定位打包的 payload.zip 资源文件"""
        # 1. PyInstaller 单文件解压运行目录
        if hasattr(sys, "_MEIPASS"):
            p1 = os.path.join(sys._MEIPASS, "payload.zip")
            if os.path.exists(p1):
                return p1

        # 2. 当前运行目录或当前脚本同级目录
        base = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base, "payload.zip"),
            os.path.join(base, "release", "payload.zip"),
            os.path.join(os.getcwd(), "payload.zip")
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return ""

    def _install_worker(self, target_dir: str):
        try:
            self._update_progress(10, "正在寻找安装程序包资源...")
            zip_path = self._find_payload_zip()
            if not zip_path:
                raise FileNotFoundError("未能找到内嵌的 payload.zip 安装资源文件！")

            self._update_progress(25, f"正在创建安装目标目录: {target_dir} ...")
            os.makedirs(target_dir, exist_ok=True)

            self._update_progress(40, "正在解压并部署应用程序核心文件...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(target_dir)

            exe_path = os.path.join(target_dir, "CampusNetLogin.exe")
            if not os.path.exists(exe_path):
                raise FileNotFoundError(f"解压后未找到核心执行程序: {exe_path}")

            self._update_progress(65, "正在创建桌面与开始菜单快捷方式...")
            shell = win32com.client.Dispatch("WScript.Shell")

            # 1. 桌面快捷方式
            if self.var_desktop_icon.get():
                desktop = os.path.expandvars(r"%USERPROFILE%\Desktop")
                lnk_desk = os.path.join(desktop, f"{APP_DISPLAY_NAME}.lnk")
                sc = shell.CreateShortCut(lnk_desk)
                sc.TargetPath = exe_path
                sc.WorkingDirectory = target_dir
                sc.Description = "校园网自动登录与状态栏守护 (59.68.177.9)"
                sc.Save()

            # 2. 开始菜单快捷方式
            if self.var_start_menu.get():
                programs_dir = os.path.join(os.path.expandvars(r"%APPDATA%"), r"Microsoft\Windows\Start Menu\Programs", "CampusNetLogin")
                os.makedirs(programs_dir, exist_ok=True)
                lnk_menu = os.path.join(programs_dir, f"{APP_DISPLAY_NAME}.lnk")
                sc = shell.CreateShortCut(lnk_menu)
                sc.TargetPath = exe_path
                sc.WorkingDirectory = target_dir
                sc.Description = "校园网自动登录与状态栏守护 (59.68.177.9)"
                sc.Save()

            self._update_progress(80, "正在配置 Windows 启动项与卸载信息...")
            # 3. 开机自启
            if self.var_autostart.get():
                try:
                    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
                        cmd = f'"{exe_path}" --tray'
                        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                except Exception as e:
                    print(f"写入开机启动项警告: {e}")

            # 4. 生成 Uninstall.bat
            uninstaller_bat = os.path.join(target_dir, "Uninstall.bat")
            with open(uninstaller_bat, "w", encoding="ansi") as f:
                f.write(f"""@echo off
title 卸载校园网自动登录程序
cd /d "%~dp0"
echo 正在准备卸载 {APP_DISPLAY_NAME}...
taskkill /f /im CampusNetLogin.exe >nul 2>nul
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "{APP_NAME}" /f >nul 2>nul
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" /f >nul 2>nul
del /f /q "%USERPROFILE%\\Desktop\\{APP_DISPLAY_NAME}.lnk" >nul 2>nul
rmdir /s /q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\CampusNetLogin" >nul 2>nul
echo 正在清理安装文件...
timeout /t 1 >nul
cd ..
start "" cmd /c "rmdir /s /q \\"{target_dir}\\" && msg * 校园网自动登录程序已成功卸载！"
exit
""")

            # 5. 注册到 Windows 设置“应用与功能”卸载列表
            try:
                uninst_key = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninst_key) as k:
                    winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, f"{APP_DISPLAY_NAME}")
                    winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
                    winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, APP_PUBLISHER)
                    winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, exe_path)
                    winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ, f'"{uninstaller_bat}"')
                    winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, target_dir)
            except Exception as e:
                print(f"注册卸载信息警告: {e}")

            self._update_progress(100, "🎉 安装成功！")
            self.after(300, lambda: self._show_finish_ui(exe_path))

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("安装失败", f"安装过程出现异常:\n{str(e)}"))
            self.after(0, lambda: self.btn_cancel.config(state=tk.NORMAL))

    def _update_progress(self, val: int, msg: str):
        self.after(0, lambda: self.progress_bar.config(value=val))
        self.after(0, lambda: self.lbl_progress.config(text=msg))

    def _show_finish_ui(self, exe_path: str):
        # 清空 body 并展示完成页面
        for w in self.body.winfo_children():
            w.destroy()

        box = tk.Frame(self.body, bg=self.colors["bg"], pady=30)
        box.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            box,
            text="🎉 恭喜！校园网自动登录程序已成功安装！",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg=self.colors["success"],
            bg=self.colors["bg"]
        ).pack(pady=(10, 8))

        tk.Label(
            box,
            text="您可以在桌面直接双击图标打开控制看板，也可以随时在屏幕右下角状态栏查看实时网络监控。",
            font=("Microsoft YaHei UI", 9),
            fg=self.colors["text_muted"],
            bg=self.colors["bg"],
            wraplength=500
        ).pack(pady=(0, 20))

        tk.Checkbutton(
            box,
            text="立即启动校园网自动登录程序",
            variable=self.var_launch_now,
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors["bg"]
        ).pack(pady=4)

        for w in self.bottom_bar.winfo_children():
            w.destroy()

        btn_finish = tk.Button(
            self.bottom_bar,
            text="完成",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors["success"],
            fg="#ffffff",
            relief=tk.FLAT,
            padx=24,
            pady=6,
            cursor="hand2",
            command=lambda: self._on_finish(exe_path)
        )
        btn_finish.pack(side=tk.RIGHT)

    def _on_finish(self, exe_path: str):
        if self.var_launch_now.get() and os.path.exists(exe_path):
            try:
                os.startfile(exe_path)
            except Exception as e:
                print(f"启动异常: {e}")
        self.destroy()

if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()
