# main.py
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
    QVBoxLayout, QDesktopWidget, QSpacerItem, QSizePolicy, QTextEdit, QComboBox
)
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

import auto_login

# 配置文件路径
CONFIG_FILE = "UESTC_AutoConnect_config.ini"

# 全局控制台输出缓存
console_buffer = deque(maxlen=300)
console_lock = threading.Lock()


# 自定义输出流（修改：安全 flush，避免 windowed 模式报错）
class ConsoleCapture(io.StringIO):
    def write(self, text):
        if text.strip():
            with console_lock:
                console_buffer.append(text.strip())
        if getattr(sys, "__stdout__", None):
            try:
                sys.__stdout__.flush()
            except Exception:
                pass
        return super().write(text)

    def flush(self):
        if getattr(sys, "__stdout__", None):
            try:
                sys.__stdout__.flush()
            except Exception:
                pass
        return super().flush()


# 重定向标准输出
original_stdout = sys.stdout
sys.stdout = ConsoleCapture()


def save_credentials(username, password, login_mode):
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")
    if "credentials" not in config:
        config["credentials"] = {}
    config["credentials"]["username"] = username
    config["credentials"]["password"] = password
    config["credentials"]["login_mode"] = login_mode
    with open(CONFIG_FILE, "w") as f:
        config.write(f)
    print("账号密码保存成功!")


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def on_quit(icon, item):
    icon.stop()
    print("程序即将退出")
    threading.Thread(target=lambda: (time.sleep(0.1), sys.exit(0)), daemon=True).start()


class ConsoleWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("电科校园网自动保持连接 by Eliyah")
        self.resize(600, 400)
        self.center()
        self.line_count = 0
        self.max_lines = 100
        self.setFont(QFont("Microsoft YaHei", 10))

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 15)

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

        self.footer_label = QLabel()
        self.footer_label.setText(
            '<a href="https://github.com/eliyahgan/UESTC_SchoolNet_AutoConnect" style="color:gray; text-decoration:none;">'
            '主页: https://github.com/eliyahgan/UESTC_SchoolNet_AutoConnect</a>'
        )
        self.footer_label.setOpenExternalLinks(True)
        self.footer_label.setAlignment(Qt.AlignCenter)
        self.footer_label.setFont(QFont("Arial", 9))
        layout.addWidget(self.footer_label)

        self.setLayout(layout)

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
        self.line_count += 1
        if self.line_count > self.max_lines:
            cursor = self.text_area.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
            cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar()
            self.line_count = self.max_lines
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_area.setTextCursor(cursor)
        self.text_area.ensureCursorVisible()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self.activateWindow)
        QTimer.singleShot(100, self.raise_)

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class ConsoleUpdateThread(QThread):
    update_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.last_size = 0

    def run(self):
        while True:
            try:
                with console_lock:
                    current_size = len(console_buffer)
                    if current_size > self.last_size:
                        for i in range(self.last_size, current_size):
                            self.update_signal.emit(console_buffer[i])
                        self.last_size = current_size
                time.sleep(0.1)
            except Exception as e:
                print(f"控制台更新线程错误: {e}")
                time.sleep(1)


console_window = None


# 修改：延迟激活窗口，修复第一次点击无效
def show_console(icon, item):
    global console_window
    if console_window is None:
        console_window = ConsoleWindow()
        with console_lock:
            buffer_list = list(console_buffer)
            recent_lines = buffer_list[-100:] if len(buffer_list) > 100 else buffer_list
            for line in recent_lines:
                console_window.text_area.append(line)
                console_window.line_count += 1
    console_window.show()
    QTimer.singleShot(50, console_window.activateWindow)
    QTimer.singleShot(100, console_window.raise_)


def create_tray_icon():
    icon_path = resource_path("app_icon.ico")
    image = Image.open(icon_path)
    menu = Menu(
        MenuItem('显示控制台', show_console),
        MenuItem('退出', on_quit)
    )
    icon = Icon("AppName", image, "电科校园网自动登录小程序", menu)
    return icon


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("电科校园网自动保持连接 by Eliyah")
        self.resize(500, 300)
        self.center()
        self.setFont(QFont("Microsoft YaHei", 10))

        self.layout = QVBoxLayout()
        self.layout.setSpacing(12)
        self.layout.setContentsMargins(40, 30, 40, 20)

        self.username_label = QLabel("用户名")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入校园网账号")

        self.password_label = QLabel("密码")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("请输入密码")

        self.login_mode_label = QLabel("登录方式")
        self.login_mode_combo = QComboBox()
        self.login_mode_combo.addItem("移动登录", "@cmcc")
        self.login_mode_combo.addItem("电信登录", "@dx")

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

        self.layout.addWidget(self.username_label)
        self.layout.addWidget(self.username_input)
        self.layout.addWidget(self.password_label)
        self.layout.addWidget(self.password_input)
        self.layout.addWidget(self.login_mode_label)
        self.layout.addWidget(self.login_mode_combo)
        self.layout.addWidget(self.save_button)
        self.layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.footer_label = QLabel()
        self.footer_label.setText(
            '<a href="https://github.com/eliyahgan/UESTC_SchoolNet_AutoConnect" style="color:gray; text-decoration:none;">'
            '主页: https://github.com/eliyahgan/UESTC_SchoolNet_AutoConnect</a>'
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
        login_mode = self.login_mode_combo.currentData()
        save_credentials(username, password, login_mode)
        self.close()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self.activateWindow)
        QTimer.singleShot(100, self.raise_)


def check_credentials():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        if "credentials" in config:
            username = config.get("credentials", "username", fallback="")
            password = config.get("credentials", "password", fallback="")
            login_mode = config.get("credentials", "login_mode", fallback="@cmcc")
            return username, password, login_mode
    return "", "", "@cmcc"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    username, password, login_mode = check_credentials()
    if not username or not password:
        print("第一次使用请输入账号密码")
        window = LoginWindow()
        window.show()
        app.exec_()
    else:
        print("已查询到上次输入的账号")
    show_console(None, None)
    main_thread = threading.Thread(target=auto_login.main)
    main_thread.daemon = True
    main_thread.start()
    icon = create_tray_icon()
    icon.run()
