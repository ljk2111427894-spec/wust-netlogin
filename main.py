import sys
import os
import time
import signal
import argparse

# 确保导入模块路径正确
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from campus_net.config import ConfigManager
from campus_net.daemon import CampusNetDaemon
from campus_net.web_auth import WebAuthenticator
from campus_net.network_detector import NetworkDetector

def run_cli_daemon(config_mgr: ConfigManager):
    """无界面的命令行 / 后台静默守护模式"""
    print("=" * 60)
    print("   🎓 校园网自动登录与断线重连守护系统 (后台模式)   ")
    print("   认证服务器: 59.68.177.9")
    print("=" * 60)

    daemon = CampusNetDaemon(config_mgr=config_mgr)

    def signal_handler(sig, frame):
        print("\n[系统] 接收到退出信号，正在停止后台守护...")
        daemon.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    daemon.start()

    # 保持主线程存活
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        daemon.stop()

def run_once_login(config_mgr: ConfigManager):
    """单次立即登录"""
    daemon = CampusNetDaemon(config_mgr=config_mgr)
    success = daemon.perform_login()
    sys.exit(0 if success else 1)

def run_once_logout(config_mgr: ConfigManager):
    """单次注销下线"""
    daemon = CampusNetDaemon(config_mgr=config_mgr)
    success = daemon.perform_logout()
    sys.exit(0 if success else 1)

def run_status_query(config_mgr: ConfigManager):
    """查询当前状态"""
    auth = WebAuthenticator(base_url=config_mgr.get("auth_url", "http://59.68.177.9"))
    nd = NetworkDetector()
    state, msg, lat = nd.check_internet()
    status = auth.check_status()

    print("\n--- 校园网网络状态查询 ---")
    print(f"外网连通状态: {state} ({msg}) [延迟: {round(lat, 1)}ms]")
    print(f"Portal在线: {status.get('is_online')}")
    print(f"当前账号: {status.get('username') or '-'}")
    print(f"当前IP: {status.get('ip') or '-'}")
    print(f"物理MAC: {status.get('mac') or '-'}")
    print(f"已用流量: {status.get('bytes_str') or '-'}")
    print(f"拨号状态: {status.get('dial_msg') or '-'}")
    print("--------------------------\n")

def main():
    parser = argparse.ArgumentParser(description="校园网自动认证与断线守护程序 (59.68.177.9)")
    parser.add_argument("--daemon", action="store_true", help="以纯后台/无界面守护模式运行")
    parser.add_argument("--tray", action="store_true", help="启动并直接收缩至系统状态栏托盘 (不占用任务栏)")
    parser.add_argument("--minimized", action="store_true", help="启动并直接收缩至系统状态栏托盘")
    parser.add_argument("--login", action="store_true", help="单次执行登录认证后退出")
    parser.add_argument("--logout", action="store_true", help="单次执行注销断开后退出")
    parser.add_argument("--status", action="store_true", help="查询当前网络与账号状态")
    args = parser.parse_args()

    config_mgr = ConfigManager()

    if args.daemon:
        run_cli_daemon(config_mgr)
    elif args.login:
        run_once_login(config_mgr)
    elif args.logout:
        run_once_logout(config_mgr)
    elif args.status:
        run_status_query(config_mgr)
    else:
        # 默认启动现代化 GUI 界面
        from gui import CampusNetApp
        start_in_tray = bool(args.tray or args.minimized)
        app = CampusNetApp(config_mgr=config_mgr, start_in_tray=start_in_tray)
        app.mainloop()

if __name__ == "__main__":
    main()
