
# auto_login.py
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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# 配置信息
LOGIN_URL = "http://10.253.0.235/srun_portal_pc?ac_id=3"
USERNAME = None  # 替换为你的实际用户名
PASSWORD = None  # 替换为你的实际密码
LOGIN_MODE = "@cmcc"
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
        login_mode = config.get('credentials', 'login_mode', fallback='@cmcc')

        return username, password, login_mode
    except Exception as e:
        print(f"读取配置文件失败: {e}")
        return None, None, '@cmcc'

def auto_login():
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - 尝试登录中。。。")

    # 设置 Edge 选项
    edge_options = Options()
    edge_options.add_argument("--headless")
    edge_options.add_argument("--disable-gpu")
    edge_options.add_argument("--no-sandbox")
    edge_options.add_argument("--disable-dev-shm-usage")

    driver = None

    def find_element_with_locators(ctx, locators, timeout=5):
        for locator in locators:
            try:
                return WebDriverWait(ctx, timeout).until(
                    EC.element_to_be_clickable(locator)
                )
            except TimeoutException:
                continue
        return None

    def try_login_in_context(ctx):
        username_locators = [
            (By.ID, "username"),
            (By.NAME, "username"),
            (By.ID, "user"),
            (By.NAME, "user"),
            (By.ID, "account"),
        ]
        password_locators = [
            (By.ID, "password"),
            (By.NAME, "password"),
            (By.ID, "pwd"),
            (By.NAME, "pwd"),
            (By.ID, "pass"),
        ]
        login_locators = [
            (By.CSS_SELECTOR, f"button.btn-login.login-domain[mode='{LOGIN_MODE}']"),
            (By.CSS_SELECTOR, "button.btn-login.login-domain"),
            (By.ID, "login"),
            (By.NAME, "login"),
            (By.ID, "submit"),
            (By.NAME, "submit"),
            (By.CSS_SELECTOR, "button[type='submit']"),
        ]

        username_element = find_element_with_locators(ctx, username_locators)
        password_element = find_element_with_locators(ctx, password_locators)
        login_button = find_element_with_locators(ctx, login_locators)

        if not username_element or not password_element or not login_button:
            return False

        username_element.clear()
        username_element.send_keys(USERNAME)

        password_element.clear()
        password_element.send_keys(PASSWORD)

        login_button.click()
        return True
    try:
        # 启动 Edge 浏览器（Selenium Manager 自动匹配驱动）
        driver = webdriver.Edge(options=edge_options)
        driver.get(LOGIN_URL)
        print(f"登录页URL: {driver.current_url}")

        login_success = try_login_in_context(driver)
        if not login_success:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                driver.switch_to.frame(frame)
                if try_login_in_context(driver):
                    login_success = True
                    driver.switch_to.default_content()
                    break
                driver.switch_to.default_content()

        if not login_success:
            print("未找到登录表单元素（可能页面结构变更或未正确加载）")
            try:
                with open("login_page_dump.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("已保存页面到 login_page_dump.html 以便排查")
            except Exception:
                pass
            return

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


def ensure_driver_downloaded():
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - 初始化 EdgeDriver（Selenium Manager）...")
    edge_options = Options()
    edge_options.add_argument("--headless")
    edge_options.add_argument("--disable-gpu")
    edge_options.add_argument("--no-sandbox")
    edge_options.add_argument("--disable-dev-shm-usage")
    driver = None
    try:
        driver = webdriver.Edge(options=edge_options)
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - EdgeDriver 初始化完成")
    except Exception as e:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - EdgeDriver 初始化失败: {e}")
    finally:
        if driver:
            driver.quit()

def main():
    print("自动网络监控和登录程序已启动")
    print("每30秒检查网络状态，如果连接失败则尝试登录校园网...")
    global USERNAME, PASSWORD, LOGIN_MODE
    USERNAME, PASSWORD, LOGIN_MODE = get_credentials()
    if USERNAME and PASSWORD:
        print(f"用户名: {USERNAME}, 密码: {PASSWORD} ")
        print(f"登录方式: {LOGIN_MODE}")
    else:
        print("未获取到凭据！")
    ensure_driver_downloaded()
    while True:
        if not request_miui204():
            print("检测到网络断开，尝试登录校园网...")
            auto_login()
        time.sleep(30)