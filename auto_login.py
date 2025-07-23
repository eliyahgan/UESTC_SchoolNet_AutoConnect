import time
import traceback
import subprocess
import configparser
import os
import requests
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options  # ✅ 改为 EdgeOptions
from selenium.webdriver.edge.service import Service  # ✅ Edge 驱动服务
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# 配置信息
LOGIN_URL = "http://10.253.0.235/srun_portal_pc?ac_id=3"
USERNAME = None  # 替换为你的实际用户名
PASSWORD = None  # 替换为你的实际密码
html_opened = False
html_path = None


def get_credentials():
    try:
        # 获取exe所在目录，而不是脚本目录
        if getattr(sys, 'frozen', False):
            # 打包后的exe环境
            config_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境
            config_dir = os.path.dirname(os.path.abspath(__file__))

        config_path = os.path.join(config_dir, 'UESTC_AutoConnect_config.ini')

        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')

        username = config.get('credentials', 'username')
        password = config.get('credentials', 'password')

        return username, password
    except Exception as e:
        print(f"读取配置文件失败: {e}")
        return None, None

def auto_login():
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - 尝试登录中。。。")

    # 设置 Edge 选项
    edge_options = Options()
    edge_options.add_argument("--headless")
    edge_options.add_argument("--disable-gpu")
    edge_options.add_argument("--no-sandbox")
    edge_options.add_argument("--disable-dev-shm-usage")

    driver = None
    try:
        # 启动 Edge 浏览器并使用本地驱动
        driver_path = os.path.join(os.path.dirname(__file__), "msedgedriver.exe")  # ✅ 放在项目目录
        service = Service(executable_path=driver_path)

        driver = webdriver.Edge(service=service, options=edge_options)
        driver.get(LOGIN_URL)

        wait = WebDriverWait(driver, 10)

        username_element = wait.until(
            EC.element_to_be_clickable((By.ID, "username"))
        )
        username_element.clear()
        username_element.send_keys(USERNAME)

        password_element = wait.until(
            EC.element_to_be_clickable((By.ID, "password"))
        )
        password_element.clear()
        password_element.send_keys(PASSWORD)

        login_button = wait.until(
            EC.element_to_be_clickable((By.ID, "login"))
        )
        login_button.click()

        time.sleep(5)

        current_url = driver.current_url
        print(f"登录后的URL: {current_url}")

        if "success" in current_url.lower() or "online" in current_url.lower():
            print("登录成功!")
        else:
            page_source = driver.page_source
            if "成功" in page_source or "已登录" in page_source:
                print("登录成功!")
            elif "失败" in page_source or "错误" in page_source or "刷新页面" in page_source:
                print("登录失败，可能是用户名或密码错误")
                print("****************************************************************")
                print("****请删除同路径UESTC_AutoConnect_config.ini以重新输入账号密码****")
                print("****************************************************************")
            else:
                print("无法确定登录状态,请手动尝试登录寻找问题")

    except TimeoutException:
        print("等待元素超时，页面可能加载过慢或元素不存在")
    except Exception as e:
        print(f"登录失败: {e}")
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()


def request_miui204():
    # 请求小米服务器检查是否联网
    try:
        r = requests.get("http://connect.rom.miui.com/generate_204", timeout=3)
        if r.status_code == 204:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - 网络连接正常")
            return True
        else:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - 无网络（无法连接到connect.rom.miui.com）")
            return False
    except Exception as e:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - 检测联网过程出错: {e}")

def main():
    print("自动网络监控和登录程序已启动")
    print("每30秒检查网络状态，如果连接失败则尝试登录校园网...")
    global USERNAME, PASSWORD
    USERNAME, PASSWORD = get_credentials()
    if USERNAME and PASSWORD:
        print(f"用户名: {USERNAME}, 密码: {PASSWORD} ")
    else:
        print("未获取到凭据！")
    while True:
        if not request_miui204():
            print("检测到网络断开，尝试登录校园网...")
            auto_login()
        time.sleep(30)
