import os
import sys
import shutil
import zipfile
import hashlib
import json
import subprocess

VERSION = "1.0.0"
APP_NAME = "CampusNetLogin"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RELEASE_DIR = os.path.join(BASE_DIR, "release")
STAGE_DIR = os.path.join(BASE_DIR, "build_stage")

def compute_sha256(filepath: str) -> str:
    """计算文件的 SHA256 哈希值"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def prepare_stage():
    """准备纯净的发布资源临时目录"""
    if os.path.exists(STAGE_DIR):
        shutil.rmtree(STAGE_DIR, ignore_errors=True)
    os.makedirs(STAGE_DIR, exist_ok=True)
    os.makedirs(RELEASE_DIR, exist_ok=True)

    # 1. 复制可执行文件
    src_exe = os.path.join(BASE_DIR, f"{APP_NAME}.exe")
    if not os.path.exists(src_exe):
        raise FileNotFoundError(f"未找到 {src_exe}，请先编译主程序！")
    shutil.copy2(src_exe, os.path.join(STAGE_DIR, f"{APP_NAME}.exe"))

    # 2. 复制启动批处理与说明文件
    shutil.copy2(os.path.join(BASE_DIR, "Start_CampusNet.bat"), os.path.join(STAGE_DIR, "Start_CampusNet.bat"))
    shutil.copy2(os.path.join(BASE_DIR, "Daemon_CampusNet.bat"), os.path.join(STAGE_DIR, "Daemon_CampusNet.bat"))
    shutil.copy2(os.path.join(BASE_DIR, "README.md"), os.path.join(STAGE_DIR, "README.md"))

    # 3. 写入纯净模板配置 (清除个人密码与私有信息)
    clean_config = {
        "auth_url": "http://59.68.177.9",
        "username": "",
        "password": "",
        "carrier": "",
        "connect_mode": "wifi_web",
        "wifi_ssid": "WUST-WiFi6",
        "pppoe_name": "宽带连接",
        "check_interval": 15,
        "auto_reconnect": True,
        "auto_start": False,
        "auto_daemon_on_start": True,
        "minimize_on_start": False,
        "minimize_on_daemon": False,
        "close_to_tray": True,
        "window_geometry": "860x720",
        "window_is_maximized": False,
        "probe_urls": [
            "http://connectivitycheck.platform.hicloud.com/generate_204",
            "http://connect.rom.miui.com/generate_204",
            "http://www.baidu.com",
            "http://www.msftconnecttest.com/connecttest.txt"
        ]
    }
    with open(os.path.join(STAGE_DIR, "config.json"), "w", encoding="utf-8") as f:
        json.dump(clean_config, f, ensure_ascii=False, indent=2)

    print("[1/5] 纯净发布资源目录已就绪 (个人隐私密码已脱敏)")

def build_portable_zip():
    """打包绿色免安装便携版 ZIP"""
    zip_name = f"{APP_NAME}-v{VERSION}-Windows-Portable.zip"
    zip_path = os.path.join(RELEASE_DIR, zip_name)
    if os.path.exists(zip_path):
        os.remove(zip_path)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(STAGE_DIR):
            for file in files:
                file_full = os.path.join(root, file)
                rel_path = os.path.relpath(file_full, STAGE_DIR)
                zf.write(file_full, arcname=rel_path)

    print(f"[2/5] 绿色便携版已生成: {zip_path}")
    return zip_path

def build_installer_exe():
    """生成单文件 Windows 图形安装包 Setup.exe"""
    # 1. 先打包 stage 为 payload.zip 供安装包内嵌
    payload_zip = os.path.join(BASE_DIR, "payload.zip")
    if os.path.exists(payload_zip):
        os.remove(payload_zip)

    with zipfile.ZipFile(payload_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(STAGE_DIR):
            for file in files:
                file_full = os.path.join(root, file)
                rel_path = os.path.relpath(file_full, STAGE_DIR)
                zf.write(file_full, arcname=rel_path)

    installer_name = f"{APP_NAME}-v{VERSION}-Setup"
    installer_script = os.path.join(BASE_DIR, "installer.py")

    print("[3/5] 正在通过 PyInstaller 编译图形化安装向导 Setup.exe ...")
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        f"--add-data={payload_zip};.",
        f"--name={installer_name}",
        "--hidden-import=win32com.client",
        installer_script
    ]
    subprocess.run(cmd, check=True, cwd=BASE_DIR)

    # 移动产物到 release 目录并清理 build
    dist_exe = os.path.join(BASE_DIR, "dist", f"{installer_name}.exe")
    final_setup_exe = os.path.join(RELEASE_DIR, f"{installer_name}.exe")
    if os.path.exists(final_setup_exe):
        os.remove(final_setup_exe)
    shutil.move(dist_exe, final_setup_exe)

    # 清理临时文件
    if os.path.exists(payload_zip):
        os.remove(payload_zip)
    for p in [os.path.join(BASE_DIR, "build"), os.path.join(BASE_DIR, "dist"), os.path.join(BASE_DIR, f"{installer_name}.spec")]:
        if os.path.exists(p):
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)

    print(f"[4/5] 一键安装包已生成: {final_setup_exe}")
    return final_setup_exe

def generate_release_notes(portable_zip: str, setup_exe: str):
    """生成 GitHub Release 发布说明与校验和"""
    hash_portable = compute_sha256(portable_zip)
    size_portable = os.path.getsize(portable_zip) / (1024 * 1024)

    hash_setup = compute_sha256(setup_exe)
    size_setup = os.path.getsize(setup_exe) / (1024 * 1024)

    notes = f"""# 🎓 校园网自动登录与状态栏守护 v{VERSION}

专为校园网认证网关（**59.68.177.9**）打造的全功能自动化登录与断线重连守护系统。

---

## 🚀 下载地址与安装包文件说明

| 文件名 | 类型 | 文件大小 | SHA-256 校验和 |
| :--- | :--- | :--- | :--- |
| **`{os.path.basename(setup_exe)}`** | **一键安装向导 (推荐)** | `{size_setup:.2f} MB` | `{hash_setup}` |
| **`{os.path.basename(portable_zip)}`** | **绿色免安装便携版** | `{size_portable:.2f} MB` | `{hash_portable}` |

---

## 🌟 核心功能一览

1. **针对 59.68.177.9 网关深度定制**：
   - 自动模拟 Web Portal 认证、在线心跳拉取与二次自动拨号。
   - 底层请求强制跳过系统代理/VPN/Clash，防止代理中断影响校园网认证。
2. **多连接模式全支持**：
   - 📻 **WiFi 自动连接 + 网页认证**（支持扫描周围 WiFi 并双击直接选择）。
   - 🔌 **网线宽带拨号 PPPoE**（集成 Windows `rasdial` 核心，支持一键在系统生成宽带连接）。
   - 🌐 **网线直连 Web 认证** 与 ⚡ **智能混合自适应模式**（插网线优先有线，拔网线回退无线）。
3. **右下角状态栏（系统托盘）深度集成**：
   - 守护运行时可一键收缩至屏幕右下角系统状态栏托盘，不占用任务栏。
   - 绿/黄/红三色动态状态图标，鼠标悬浮即时显示延迟、流量与 IP。
   - 开机自启后直接在状态栏托盘静默守护，透明可控，拒绝暗中偷跑。
4. **窗口记忆还原**：
   - 自动记忆放大/缩小的窗口尺寸与最大化状态，重启后 100% 精确还原。

---

## 💻 安装说明

- **安装版**：下载运行 `{os.path.basename(setup_exe)}`，可自定义安装路径，自动创建桌面/开始菜单快捷方式与开机自启动。
- **便携版**：解压 `{os.path.basename(portable_zip)}` 至任意文件夹，双击 `CampusNetLogin.exe` 或 `Start_CampusNet.bat` 即可直接使用。
"""
    notes_path = os.path.join(RELEASE_DIR, "RELEASE_NOTES.md")
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write(notes)

    print(f"[5/5] Release 发布日志已生成: {notes_path}")

def cleanup():
    """清理临时 stage"""
    if os.path.exists(STAGE_DIR):
        shutil.rmtree(STAGE_DIR, ignore_errors=True)

if __name__ == "__main__":
    print("=" * 60)
    print(f"   开始生成 {APP_NAME} v{VERSION} Release 发布安装包")
    print("=" * 60)
    try:
        prepare_stage()
        portable_zip = build_portable_zip()
        setup_exe = build_installer_exe()
        generate_release_notes(portable_zip, setup_exe)
        cleanup()
        print("\n[SUCCESS] Release packages created successfully in release/ folder!")
    except Exception as e:
        print(f"\n[ERROR] Build failed: {e}")
        cleanup()
        sys.exit(1)
