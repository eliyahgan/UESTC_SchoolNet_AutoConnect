import sys
import os
import time
import threading
import configparser
import io
from collections import deque
from PIL import Image
from pystray import Icon, MenuItem, Menu
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QDesktopWidget, QSpacerItem, QSizePolicy, QTextEdit
)
from PyQt5.QtGui import QFont, QDesktopServices
from PyQt5.QtCore import Qt, QUrl, QThread, pyqtSignal

import auto_login

# 配置文件路径
CONFIG_FILE = "UESTC_AutoConnect_config.ini"

# 全局控制台输出缓存
console_buffer = deque(maxlen=100)
console_lock = threading.Lock()


# 自定义输出流，用于捕获print输出
class ConsoleCapture(io.StringIO):
    def write(self, text):
        if text.strip():  # 忽略空行
            with console_lock:
                console_buffer.append(text.strip())
        return super().write(text)


# 重定向标准输出
original_stdout = sys.stdout
sys.stdout = ConsoleCapture()


def save_credentials(username, password):
    # 写入配置文件
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")
    if "credentials" not in config:
        config["credentials"] = {}
    config["credentials"]["username"] = username
    config["credentials"]["password"] = password
    with open(CONFIG_FILE, "w") as f:
        config.write(f)
    print("账号密码保存成功!")


def resource_path(relative_path):
    """获取资源文件的绝对路径，兼容开发环境和 PyInstaller 打包环境"""
    if hasattr(sys, '_MEIPASS'):
        # 如果是打包后的exe，从临时目录加载
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def on_quit(icon, item):
    icon.stop()
    print("程序即将退出")
    threading.Thread(target=lambda: (time.sleep(0.1), sys.exit(0)), daemon=True).start()


# 控制台窗口类
class ConsoleWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("电科校园网自动保持连接 by Eliyah")
        self.resize(600, 400)
        self.center()

        # 主字体设置
        self.setFont(QFont("Microsoft YaHei", 10))

        # 主布局
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 15)

        # 文本区域
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setStyleSheet("""
            QTextEdit {
                background-color: #f7f7f7;
                border: 1px solid #ccc;
                padding: 8px;
                font-family: Consolas, Courier New, monospace;
            }
        """)
        layout.addWidget(self.text_area)

        # 弹性空白区域
        # layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # 灰色点击链接
        self.footer_label = QLabel()
        self.footer_label.setText(
            '<a href="https://github.com/eliyahgan/UESTC_ShoolNet_AutoConnect" style="color:gray; text-decoration:none;">'
            '主页: https://github.com/eliyahgan/UESTC_ShoolNet_AutoConnect</a>'
        )
        self.footer_label.setOpenExternalLinks(True)
        self.footer_label.setAlignment(Qt.AlignCenter)
        self.footer_label.setFont(QFont("Arial", 9))
        layout.addWidget(self.footer_label)

        self.setLayout(layout)

        # 启动更新线程
        self.update_thread = ConsoleUpdateThread()
        self.update_thread.update_signal.connect(self.update_console)
        self.update_thread.start()

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def update_console(self, text):
        self.text_area.append(text)
        # 自动滚动到底部
        cursor = self.text_area.textCursor()
        cursor.movePosition(cursor.End)
        self.text_area.setTextCursor(cursor)


# 控制台更新线程
class ConsoleUpdateThread(QThread):
    update_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.last_size = 0

    def run(self):
        while True:
            with console_lock:
                current_size = len(console_buffer)
                if current_size > self.last_size:
                    # 发送新的输出内容
                    for i in range(self.last_size, current_size):
                        self.update_signal.emit(console_buffer[i])
                    self.last_size = current_size
            time.sleep(0.1)  # 100ms更新一次


# 全局控制台窗口实例
console_window = None


def show_console(icon, item):
    global console_window
    if console_window is None:
        console_window = ConsoleWindow()
        # 显示历史记录
        with console_lock:
            for line in console_buffer:
                console_window.text_area.append(line)
    console_window.show()
    console_window.raise_()  # 将窗口置于前台


def create_tray_icon():
    # 读取图标文件
    icon_path = resource_path("app_icon.ico")
    image = Image.open(icon_path)
    menu = Menu(
        MenuItem('显示控制台', show_console),
        MenuItem('退出', on_quit)
    )
    icon = Icon("AppName", image, "托盘图标", menu)
    return icon


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("电科校园网自动保持连接 by Eliyah")
        self.resize(500, 300)
        self.center()

        # 设置整体字体
        self.setFont(QFont("Microsoft YaHei", 10))

        # 主布局
        self.layout = QVBoxLayout()
        self.layout.setSpacing(12)
        self.layout.setContentsMargins(40, 30, 40, 20)

        # 用户名
        self.username_label = QLabel("用户名")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入校园网账号")

        # 密码
        self.password_label = QLabel("密码")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("请输入密码")

        # 保存按钮
        self.save_button = QPushButton("保存")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                color: white;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        self.save_button.clicked.connect(self.save_credentials)

        # 添加控件到布局
        self.layout.addWidget(self.username_label)
        self.layout.addWidget(self.username_input)
        self.layout.addWidget(self.password_label)
        self.layout.addWidget(self.password_input)
        self.layout.addWidget(self.save_button)

        # 空白弹性区
        self.layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # 可点击链接 label
        self.footer_label = QLabel()
        self.footer_label.setText(
            '<a href="https://github.com/eliyahgan/UESTC_ShoolNet_AutoConnect" style="color:gray; text-decoration:none;">'
            '主页: https://github.com/eliyahgan/UESTC_ShoolNet_AutoConnect</a>'
        )
        self.footer_label.setOpenExternalLinks(True)
        self.footer_label.setAlignment(Qt.AlignCenter)
        self.footer_label.setFont(QFont("Arial", 9))
        self.layout.addWidget(self.footer_label)

        self.setLayout(self.layout)

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def save_credentials(self):
        username = self.username_input.text()
        password = self.password_input.text()
        save_credentials(username, password)
        self.close()

def check_credentials():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        if "credentials" in config:
            username = config.get("credentials", "username", fallback="")
            password = config.get("credentials", "password", fallback="")
            return username, password
    return "", ""


if __name__ == "__main__":
    app = QApplication(sys.argv)
    username, password = check_credentials()
    if not username or not password:
        print("第一次使用请输入账号密码")
        window = LoginWindow()
        window.show()
        app.exec_()
    else:
        print("已查询到上次输入的账号")
    # 启动主功能线程
    main_thread = threading.Thread(target=auto_login.main)
    main_thread.daemon = True  # 设置为守护线程
    main_thread.start()
    # 创建并运行托盘图标
    icon = create_tray_icon()
    icon.run()