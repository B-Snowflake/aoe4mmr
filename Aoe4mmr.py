#!/usr/bin/python3
# Author: B_Snowflake
# Date: 2025/4/1

import os
import re
import sys
import tempfile
import win32process
import pynput
import data
import time
import psutil
import sqlite3
import keyboard
import threading
from pathlib import Path
import pygetwindow as gw
from types import SimpleNamespace
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Signal, QTimer, Qt, QUrl, QEvent
from PySide6.QtGui import QFont, QPixmap, QAction, QIcon, QColor, QPainter, QKeyEvent, QFocusEvent
from PySide6.QtWidgets import QGraphicsScene, QWidget, QGraphicsView, QLineEdit, QListWidget, QVBoxLayout
from PySide6.QtWidgets import QMainWindow, QMenu, QSystemTrayIcon, QApplication, QLabel, QPushButton, QCheckBox, QComboBox, QMessageBox


class MainWindow(QMainWindow):
    gui_reload_signal = Signal(str)
    keyboard_single = Signal(str)
    searching_signal = Signal(str)
    hotkey_signal = Signal(str)

    def __init__(self, pid_path):
        super().__init__()
        # 初始化数据保存路径
        if not os.path.exists(Path.home() / "AppData" / "Local" / "Aoe4mmr"):
            os.mkdir(Path.home() / "AppData" / "Local" / "Aoe4mmr")
        databasepath = Path.home() / "AppData" / "Local" / "Aoe4mmr" / "database.db"
        logpath = Path.home() / "AppData" / "Local" / "Aoe4mmr" / "data.log"
        self.pid_path = pid_path
        # 初始化数据库
        self.database_version = '1.0.7'
        self.conn = sqlite3.connect(databasepath, check_same_thread=False)
        self.cur = self.conn.cursor()
        self.initilize_database()
        self.get_all_data()
        # 初始化快捷键和启动显示设置
        try:
            self.hotkey = self.cur.execute("select value from settings where type = 'hotkey'").fetchone()[0]
        except:
            self.hotkey = 'ctrl+q'  # 默认快捷键ctrl+q
        try:
            self.show_gui_when_start = self.cur.execute("select cast(value as integer) from settings where type = 'show_gui_when_start'").fetchone()[0]
        except:
            self.show_gui_when_start = 0  # 启动时，默认隐藏主界面
        try:
            self.show_apm = self.cur.execute("select cast(value as integer) from settings where type = 'show_apm'").fetchone()[0]
        except:
            self.show_apm = 0  # 启动时，默认隐藏APM界面
        try:
            self.able_dragging = self.cur.execute("select cast(value as integer) from settings where type = 'able_dragging'").fetchone()[0]
        except:
            self.able_dragging = 0  # 启动时，默认禁止拖拽
        try:
            rs = self.cur.execute("select window, x_location, y_location from window_location")
            self.window_location = {loc[0]:  (loc[1], loc[2]) for loc in rs.fetchall()}
        except:
            self.window_location = {}
        # 初始化gui界面基本配置
        self.resize(965, 190)
        self.global_font = QFont("Arial", 14)
        app.setFont(self.global_font)
        self.try_icon_font = QFont("Arial", 10)
        self.widget_font = QFont("Arial", 12)
        self.setWindowTitle('Aoe4mmr')
        self.icon = QIcon(self.app_icon)
        self.setWindowIcon(self.icon)
        # 初始化任务栏图标和菜单
        exit_action1 = QAction("设置", self)
        exit_action2 = QAction("退出", self)
        exit_action1.setFont(self.try_icon_font)
        exit_action2.setFont(self.try_icon_font)
        exit_action1.triggered.connect(self.setting)
        exit_action2.triggered.connect(self.exit)
        self.tray_icon_menu = QMenu()
        self.tray_icon_menu.addAction(exit_action1)
        self.tray_icon_menu.addAction(exit_action2)
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.icon)
        self.tray_icon.setContextMenu(self.tray_icon_menu)
        self.tray_icon.activated.connect(self.tray_icon_clicked)
        self.tray_icon.show()
        # 初始化gui界面
        self.mmr_rank_map()
        self.ui()
        self.setwindow()
        self.set_profile_id()
        self.apmwindow()
        self.get_now_availiable()
        # 初始化定时器，新对局开始时，自动显示对局数据，显示数据4分钟后（游戏对局约3分钟45秒左右），自动隐藏界面
        self.hide_timer = QTimer()
        self.hide_timer.setInterval(240000)
        self.hide_timer.timeout.connect(self.hide_when_timeout)
        # 初始化其他内部数据或类
        self.last_game_id, self.last_game_data, self.query_rs = None, None, {}
        self.data = data.Data(self, self.now_availiable_id, databasepath, logpath, self.map_dic)
        self.load_data_from_database()
        # 绑定信号动作
        self.gui_reload_signal.connect(self.gui_reload)
        self.keyboard_single.connect(self.update_hotkey)
        self.searching_signal.connect(self.refresh_game_id)
        self.hotkey_signal.connect(self.toggle_window)
        # 初始化子线程
        self.data_thread = threading.Thread(target=self.data.worker, daemon=True)
        self.check_thread = threading.Thread(target=self.process_control, daemon=True)
        self.check_thread.start()
        # 根据设置，显示/隐藏窗口
        self.window_show()
        self.dragging = False
        if self.show_gui_when_start == 1:
            self.show()
        else:
            self.hide()

    @staticmethod
    def is_process_running(pid_path):
        # 仅支持单实例运行，通过pid文件判断进程是否已存在
        try:
            with open(pid_path, 'r', encoding='utf-8') as f:
                pid = int(f.read())
            if psutil.pid_exists(pid) and psutil.Process(pid).name() in ('Aoe4mmr.exe', 'python.exe'):
                return False
            else:
                with open(pid_path, 'w', encoding='utf-8') as f:
                    f.write(str(os.getpid()))
                return True
        except:
            with open(pid_path, 'w', encoding='utf-8') as f:
                f.write(str(os.getpid()))
            return True

    def get_all_data(self):
        # 连接资源数据库，获取地图和图标数据
        data_conn = sqlite3.connect('resources/~.pck', check_same_thread=False)
        data_cur = data_conn.cursor()
        pixmap = QPixmap()
        pixmap.loadFromData(data_cur.execute('select data from t_icon where type = ?', ('app_icon',)).fetchone()[0])
        self.app_icon = pixmap
        civilization_icon_rs = data_cur.execute('select name,data from t_icon where type = ?', ('civilization',))
        self.civilization_icon_dic = {row[0]: row[1] for row in civilization_icon_rs.fetchall()}
        rank_icon_rs = data_cur.execute('select name,data from t_icon where type in (?,?) ', ('rank', 'team_rank'))
        self.rank_icon_dic = {row[0]: row[1] for row in rank_icon_rs.fetchall()}
        map_dic_rs = data_cur.execute('select english_name,chinese_name from t_map', )
        self.map_dic = {row[0]: row[1] for row in map_dic_rs.fetchall()}
        data_cur.execute("SELECT content FROM t_html WHERE id=?", (1,))
        temp_html = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        data = data_cur.fetchone()[0]  # noqa
        with open(temp_html.name, 'wb') as f:
            f.write(data)
        print(temp_html.name)
        self.temp_html = temp_html.name
        data_conn.close()

    def mmr_rank_map(self):
        # 排位mmr对应段位表
        self.team_mmr_rank_map = [
            (1600, 'team_conqueror_3'),
            (1500, 'team_conqueror_2'),
            (1400, 'team_conqueror_1'),
            (1350, 'team_diamond_3'),
            (1300, 'team_diamond_2'),
            (1200, 'team_diamond_1'),
            (1150, 'team_platinum_3'),
            (1100, 'team_platinum_2'),
            (1000, 'team_platinum_1'),
            (900, 'team_gold_3'),
            (800, 'team_gold_2'),
            (700, 'team_gold_1'),
            (650, 'team_silver_3'),
            (600, 'team_silver_2'),
            (500, 'team_silver_1'),
            (450, 'team_bronze_3'),
            (400, 'team_bronze_2'),
            (0, 'team_bronze_1')
        ]
        self.solo_mmr_rank_map = [
            (1600, 'solo_conqueror_3'),
            (1500, 'solo_conqueror_2'),
            (1400, 'solo_conqueror_1'),
            (1350, 'solo_diamond_3'),
            (1300, 'solo_diamond_2'),
            (1200, 'solo_diamond_1'),
            (1150, 'solo_platinum_3'),
            (1100, 'solo_platinum_2'),
            (1000, 'solo_platinum_1'),
            (900, 'solo_gold_3'),
            (800, 'solo_gold_2'),
            (700, 'solo_gold_1'),
            (650, 'solo_silver_3'),
            (600, 'solo_silver_2'),
            (500, 'solo_silver_1'),
            (450, 'solo_bronze_3'),
            (400, 'solo_bronze_2'),
            (0, 'solo_bronze_1')
        ]

    def check_process(self, process_name='RelicCardinal.exe'):
        # 检查游戏是否已经运行
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == process_name:  # NOQA
                return True
        return False

    def checking_forwardwindow(self, target_process='RelicCardinal.exe'):
        # 检查游戏窗口是否激活
        while self.checking:
            try:
                window = gw.getActiveWindow()
                if window:
                    _, pid = win32process.GetWindowThreadProcessId(window._hWnd)
                    process = psutil.Process(pid).name()
                    if process == target_process:
                        if not self.is_counting:
                            self.initialize_count()
                            self.keyboard_listener_thread = threading.Thread(target=self.keyboard_listener_func, daemon=True)
                            self.keyboard_listener_thread.start()
                            self.mouse_listener_thread = threading.Thread(target=self.mouse_listener_func, daemon=True)
                            self.mouse_listener_thread.start()
                            self.is_counting = True
                    else:
                        if self.is_counting:
                            self.keyboard_listener.stop()
                            del self.keyboard_listener
                            self.mouse_listener.stop()
                            del self.mouse_listener
                            self.is_counting = False
                            self.initialize_count()
            except Exception as e:
                print(e)
            finally:
                time.sleep(1)

    def process_control(self):
        # 每5s一次，检查游戏是否打开，如果打开启动数据线程、绑定快捷键，反之关闭
        print('listening thread start')
        while True:
            try:
                self.data_thread_alive = self.data_thread.is_alive()
            except:
                self.data_thread_alive = False
            if not self.check_process():
                if self.data_thread_alive:
                    self.data.quit_signal = True
                    self.remove_hotkey(self.hotkey)
                    self.hide()
            else:
                if not self.data_thread_alive:
                    self.data.quit_signal = False
                    self.set_hotkey(self.hotkey)
                    self.data_thread = threading.Thread(target=self.data.worker, daemon=True)
                    self.data_thread.start()
            time.sleep(5)

    def hide_when_timeout(self):
        # 定时器超时，自动隐藏界面
        self.hide()
        self.hide_timer.stop()

    def window_show(self):
        # 如果已经有已保存的账户，显示主界面，否则显示新增账户页面
        if self.now_availiable_id is not None:
            self.setwindowwidget.hide()
            self.setprofileidwidget.hide()
            self.show()
            self.uiwidget.show()
        else:
            self.hide()
            self.setwindowwidget.hide()
            self.setprofileidwidget.show()
            self.setprofileidwidget.raise_()
            self.setprofileidwidget.activateWindow()
        if self.show_apm == 1:
            self.apmwindowwidget.show()

    def initilize_database(self):
        # 读取游戏信息数据库版本号，如果是低版本数据库或无数据库，重新初始化
        try:
            self.cur.execute('select version from version')
            version = self.cur.fetchone()[0]
        except:
            version = None
        if version != self.database_version:
            try:
                self.cur.execute('select profile_id,player_name from profile_id')
                old_pid = self.cur.fetchall()
            except:
                old_pid = []
            try:
                self.cur.execute('select value,type from settings')
                old_settings = self.cur.fetchall()
            except:
                old_settings = []
            self.cur.execute('create table if not exists window_location(window text, x_location int, y_location int, primary key(window))')
            self.cur.execute('drop table if exists last_game')
            self.cur.execute('drop table if exists profile_id')
            self.cur.execute('drop table if exists version')
            self.cur.execute('drop table if exists settings')
            self.cur.execute('create table if not exists profile_id (profile_id int,player_name text,status int default 1,create_time date '
                             'default current_timestamp,primary key (profile_id))')
            self.cur.execute(
                'create table if not exists last_game (game_id TEXT NOT NULL,player TEXT,win_rate TEXT,civilization TEXT,map TEXT,profile_id INTEGER,'
                'player_mmr TEXT,team TEXT, kind Text,PRIMARY KEY (game_id,player))')
            self.cur.execute('create table if not exists version (version text, PRIMARY KEY (version))')
            self.cur.execute('create table if not exists settings (value TEXT,type TEXT,PRIMARY KEY (type))')
            try:
                self.cur.executemany('insert into profile_id(profile_id, player_name) values (?,?)', old_pid)
            except Exception as e:
                print(e)
            try:
                self.cur.executemany('insert into settings(value, type) values (?,?)', old_settings)
            except Exception as e:
                print(e)
            self.cur.execute('delete from version')
            self.cur.execute("insert into version(version) values(?)", (self.database_version,))
            self.conn.commit()

    def on_data_change(self, message):
        # 获取到新的数据时，刷新主界面
        self.gui_reload_signal.emit(message)

    @staticmethod
    def center_window(win, is_top=True, is_right=False):
        # 窗口置中
        screen = QApplication.primaryScreen()
        screen_geo = screen.geometry()
        new_x = (screen_geo.width() - win.width()) // 2 - 100
        new_y = (screen_geo.height() - win.height()) // 2
        if is_top:
            if is_right:
                win.move(screen_geo.width() - win.width() - 150, 0)
            else:
                win.move(new_x, 0)
        else:
            if is_right:
                win.move(screen_geo.width() - win.width() - 150, new_y)
            else:
                win.move(new_x, new_y)

    def set_hotkey(self, hotkey):
        # 绑定快捷键
        try:
            keyboard.add_hotkey(hotkey, self.toggle_window)
        except:
            pass

    def remove_hotkey(self, hotkey):
        # 移除快捷键
        try:
            keyboard.remove_hotkey(hotkey)
        except:
            pass

    def get_now_availiable(self):
        # 读取当前需要追踪数据的账户（status=1或最新添加的账户）
        try:
            self.cur.execute('select profile_id,player_name from profile_id where case when (select count(1) from profile_id where status =1) = 0 then '
                             '1=1 else status = 1 end order by create_time desc limit 1')
            result = self.cur.fetchone()
            self.now_availiable_id, self.now_availiable_name = result
        except:
            self.now_availiable_id, self.now_availiable_name = (None, None)
        return self.now_availiable_id, self.now_availiable_name

    @staticmethod
    def on_key_event(event):
        return event.name

    @staticmethod
    def has_chinese(string):
        # 判断游戏ID是否包含中文
        pattern = '[\u4e00-\u9fa5]'
        result = re.search(pattern, string)
        if result is not None:
            return True
        else:
            return False

    def islongname_button(self, string):
        # 如果游戏ID包含中文，则在设置界面仅显示ID前9个字符，否则显示18个
        language = self.has_chinese(string)
        if language:
            return len(string) > 9
        else:
            return len(string) > 18

    def islongname(self, string):
        # 如果游戏ID包含中文，则在主界面仅显示ID前10个字符，否则显示25个
        language = self.has_chinese(string)
        if language:
            if len(string) > 10:
                string = string[0:10] + '...'
        else:
            if len(string) > 25:
                string = string[0:25] + '...'
        return string

    def show_apm_changed(self):
        # 更改设置（是否显示APM）
        if not self.show_apm_checkbox.isChecked():
            self.checking = False
            self.web_view_timer.stop()
            self.cur.execute("insert or replace into settings values('0','show_apm')")
            self.show_apm = 0
            self.apmwindowwidget.hide()
        else:
            self.cur.execute("insert or replace into settings values('1','show_apm')")
            self.show_apm = 1
            self.start_check_threads()
            self.web_view_timer.start(1000)
        self.conn.commit()

    def able_dragging_changed(self):
        # 更改设置（是否允许拖拽窗口）
        if not self.able_dragging_checkbox.isChecked():
            self.able_dragging = 0
            self.apmwindowwidget.able_dragging = 0
            self.cur.execute("insert or replace into settings values('0','able_dragging')")
            self.apmwindowwidget.hide()
        else:
            self.able_dragging = 1
            self.apmwindowwidget.able_dragging = 1
            self.cur.execute("insert or replace into settings values('1','able_dragging')")
        self.conn.commit()

    def show_gui_when_start_changed(self):
        # 更改设置（启动时是否显示界面）
        if not self.show_gui_when_start_checkbox.isChecked():
            self.cur.execute("insert or replace into settings values('0','show_gui_when_start')")
            self.show_gui_when_start = 0
        else:
            self.cur.execute("insert or replace into settings values('1','show_gui_when_start')")
            self.show_gui_when_start = 1
        self.conn.commit()

    def apmwindow(self):
        self.apm = 0
        self.is_counting = False
        self.apm_timer = QTimer(interval=600)
        self.apm_timer.timeout.connect(self.apm_count)
        self.apm_timer.start()
        self.apm_result_list = []
        self.initialize_count()
        if self.show_apm == 1:
            self.start_check_threads()
        self.apmwindowwidget = SubWindow(self, self.uiwidget, self.save_window_position, self.able_dragging)
        self.apmwindowwidget.setWindowTitle('apmtool')
        self.apmwindowwidget.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.apmwindowwidget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.apmwindowwidget.resize(350, 150)
        self.center_widget = QWidget()
        self.apmwindowwidget.setCentralWidget(self.center_widget)
        self.main_layout = QVBoxLayout()
        self.center_widget.setLayout(self.main_layout)
        self.apm_count_label = QLabel(parent=self.center_widget, text='0  APM')
        font = QFont()
        font.setFamily("Arial")
        font.setPointSize(16)
        font.setBold(True)
        self.apm_count_label.setStyleSheet('color: green')
        self.apm_count_label.setFont(font)
        self.web_view = QWebEngineView()
        self.web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.web_view.load(QUrl.fromLocalFile(self.temp_html))
        self.web_view.setStyleSheet("background: transparent;")
        self.web_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.web_view.loadFinished.connect(self.on_load_finished)
        self.web_view.setMinimumSize(350, 130)
        self.main_layout.addWidget(self.apm_count_label)
        self.main_layout.addWidget(self.web_view)
        location = self.window_location.get(self.apmwindowwidget.windowTitle())
        try:
            self.apmwindowwidget.move(location[0], location[1])
        except:
            self.center_window(self.apmwindowwidget, is_top=True, is_right=True)

    def start_check_threads(self):
        self.checking = True
        self.checking_forwardwindow_thread = threading.Thread(target=self.checking_forwardwindow, daemon=True)
        self.checking_forwardwindow_thread.start()

    def on_load_finished(self):
        self.web_view_timer = QTimer()
        self.web_view_timer.timeout.connect(self.update_chart)
        self.web_view_timer.start(1000)  # 每秒更新一次

    def initialize_count(self):
        self.key_count = 0
        self.mouse_count = 0
        self.apm_count_list = []

    def apm_count(self):
        th_time = time.time()
        if self.is_counting:
            if len(self.apm_result_list) > 200:
                self.apm_result_list = self.apm_result_list[-200:]
            self.apm_count_list.append((time.time(), self.key_count+self.mouse_count))
            if len(self.apm_count_list) > 5:
                self.apm_count_list = self.apm_count_list[-5:]
                st_value = self.apm_count_list[-1]
                ed_value = self.apm_count_list[-5]
            else:
                st_value = self.apm_count_list[0]
                ed_value = self.apm_count_list[-1]
            self.apm = str(int((ed_value[1] - st_value[1]) / ((ed_value[0] - st_value[0]) if (ed_value[0] - st_value[0]) != 0 else 1) * 60))
            self.apm_count_label.setText(f'{self.apm}  APM')
            self.apm_result_list.append((th_time, self.apm))
        else:
            self.apm_result_list.append((th_time, '0'))

    def keyboard_listener_func(self):
        self.keyboard_listener = pynput.keyboard.Listener(on_release=self.on_keyboard_press)
        self.keyboard_listener.start()
        self.keyboard_listener.join()

    def mouse_listener_func(self):
        self.mouse_listener = pynput.mouse.Listener(on_click=self.on_mouse_click)
        self.mouse_listener.start()
        self.mouse_listener.join()

    def normalize_tuple_list(self, data, target_len=20, fill_value=(0, 0)):
        if len(data) < target_len:
            # 补足
            return data + [fill_value] * (target_len - len(data))
        else:
            # 截取最后 target_len 个
            return data[-target_len:]

    def update_chart(self):
        if self.is_counting:
            # 生成图表数据（只保留最近 20 个）
            data = self.normalize_tuple_list(self.apm_result_list)
            datax, datay = [], []
            y = 0
            for value in data:
                datax.append(value[0])
                datay.append(int(value[1]))
                y = max(y, int(value[1]))
            if len(str(y)) in (1, 2):
                maxy = 100
            elif len(str(y)) == 3:
                maxy = int((y//100+1)*100)
            else:
                maxy = 10000
            # 调用 JavaScript 函数替换数据
            self.web_view.page().runJavaScript(f"update_chart({datax}, {datay}, {maxy});")
            self.apmwindowwidget.show()
        else:
            self.apmwindowwidget.hide()

    def on_keyboard_press(self, key):
        self.key_count += 1

    def on_mouse_click(self, x, y, button, pressed):
        if pressed:
            self.mouse_count += 1

    def restore_window_location(self):
        #  复原APM和主窗口位置
        self.center_window(self.apmwindowwidget, is_top=True, is_right=True)
        self.center_window(self, is_top=True)
        self.cur.execute('delete from window_location')
        self.conn.commit()

    def setwindow(self):
        # 初始化设置窗口
        self.setwindowwidget = SubWindow(self, self.uiwidget, self.save_window_position)
        self.setwindowwidget.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        self.setwindowwidget.setWindowIcon(self.icon)
        self.setwindowwidget.resize(790, 230)
        self.setwindowwidget.setFont(self.widget_font)
        self.setwindowwidget.setWindowTitle('设置')
        location = self.window_location.get(self.setwindowwidget.windowTitle())
        try:
            self.setwindowwidget.move(location[0], location[1])
        except:
            self.center_window(self.setwindowwidget, is_top=False)
        self.set_hotkey_text = QLabel(parent=self.setwindowwidget)
        self.set_hotkey_text.setText("隐藏/打开界面快捷键（游戏启动时有效）：")
        self.set_hotkey_text.setGeometry(80, 20, 300, 30)
        self.set_hotkey_label = QLabel(parent=self.setwindowwidget)
        self.set_hotkey_label.setGeometry(330, 20, 220, 30)
        self.set_hotkey_button = QPushButton(parent=self.setwindowwidget)
        self.set_hotkey_button.setText("修改快捷键")
        self.set_hotkey_button.setGeometry(560, 20, 160, 30)
        self.set_hotkey_button.clicked.connect(self.edit_hotkey)

        self.show_gui_when_start_label = QLabel(parent=self.setwindowwidget)
        self.show_gui_when_start_label.setText("启动时显示界面：")
        self.show_gui_when_start_label.setGeometry(80, 60, 150, 30)
        self.show_gui_when_start_checkbox = QCheckBox(parent=self.setwindowwidget)
        self.show_gui_when_start_checkbox.setGeometry(205, 60, 20, 30)
        self.show_gui_when_start_checkbox.setChecked([False if self.show_gui_when_start == 0 else True][0])
        self.show_gui_when_start_checkbox.stateChanged.connect(self.show_gui_when_start_changed)

        self.show_apm_label = QLabel(parent=self.setwindowwidget, text="显示实时APM：")
        self.show_apm_label.setGeometry(250, 60, 300, 30)
        self.show_apm_checkbox = QCheckBox(parent=self.setwindowwidget)
        self.show_apm_checkbox.setGeometry(360, 60, 20, 30)
        self.show_apm_checkbox.setChecked([False if self.show_apm == 0 else True][0])
        self.show_apm_checkbox.stateChanged.connect(self.show_apm_changed)
        self.able_dragging_label = QLabel(parent=self.setwindowwidget, text='支持拖拽窗口：')
        self.able_dragging_label.setGeometry(400, 60, 300, 30)
        self.able_dragging_checkbox = QCheckBox(parent=self.setwindowwidget)
        self.able_dragging_checkbox.setGeometry(505, 60, 20, 30)
        self.able_dragging_checkbox.setChecked([False if self.able_dragging == 0 else True][0])
        self.able_dragging_checkbox.stateChanged.connect(self.able_dragging_changed)
        self.restore_window_location_button = QPushButton(parent=self.setwindowwidget)
        self.restore_window_location_button.setText('复原窗口位置')
        self.restore_window_location_button.setGeometry(560, 60, 160, 30)
        self.restore_window_location_button.clicked.connect(self.restore_window_location)

        self.name1 = QPushButton(parent=self.setwindowwidget)
        self.name1.setObjectName('name1')
        self.name1.clicked.connect(self.click_on_button)
        self.name1.resize(200, 30)
        self.name1.hide()

        self.name2 = QPushButton(parent=self.setwindowwidget)
        self.name2.setObjectName('name2')
        self.name2.clicked.connect(self.click_on_button)
        self.name2.resize(200, 30)
        self.name2.hide()

        self.name3 = QPushButton(parent=self.setwindowwidget)
        self.name3.setObjectName('name3')
        self.name3.clicked.connect(self.click_on_button)
        self.name3.resize(200, 30)
        self.name3.hide()

        self.name4 = QPushButton(parent=self.setwindowwidget)
        self.name4.setObjectName('name4')
        self.name4.clicked.connect(self.click_on_button)
        self.name4.resize(200, 30)
        self.name4.hide()

        self.name5 = QPushButton(parent=self.setwindowwidget)
        self.name5.setObjectName('name5')
        self.name5.clicked.connect(self.click_on_button)
        self.name5.resize(200, 30)
        self.name5.hide()

        self.name6 = QPushButton(parent=self.setwindowwidget)
        self.name6.setObjectName('name6')
        self.name6.clicked.connect(self.click_on_button)
        self.name6.resize(200, 30)
        self.name6.hide()

        self.add_button = QPushButton(parent=self.setwindowwidget)
        self.add_button.setText('添加新账户')
        self.add_button.clicked.connect(self.add_player)
        self.add_button.resize(200, 30)
        self.set_hotkey_label.setText(self.hotkey)
        self.set_hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cur.execute('select count(1) from profile_id')
        accounts = self.cur.fetchone()[0]
        now_availiable_id, now_availiable_name = self.get_now_availiable()
        self.cur.execute('select profile_id,player_name from profile_id order by create_time desc limit 6')
        location_list = [(80, 100), (300, 100), (520, 100), (80, 140), (300, 140), (520, 140)]
        player_id_name = self.cur.fetchall()
        i = -1
        # 根据已保存的ID数据，显示ID按钮
        for id_and_name in player_id_name:
            i += 1
            widget_name = self.setwindowwidget.findChild(QPushButton, 'name' + str(i + 1))
            widget_name.show()
            widget_name.setObjectName(str(id_and_name[0]))
            widget_name.setText(id_and_name[1])
            widget_name.move(location_list[i][0], location_list[i][1])
            length = self.islongname_button(widget_name.text())
            if id_and_name[0] == now_availiable_id and length is True:
                widget_name.setStyleSheet("color: #33ff99; text-align: left;")
            elif id_and_name[0] == now_availiable_id and length is False:
                widget_name.setStyleSheet("color: #33ff99")
            elif id_and_name[0] != now_availiable_id and length is True:
                widget_name.setStyleSheet("text-align: left;")
        if accounts == 0:
            self.add_button.move(location_list[0][0], location_list[0][1])
        elif accounts == 1 or accounts == 2:
            self.add_button.move(location_list[2][0], location_list[2][1])
        elif accounts == 3:
            self.add_button.move(location_list[4][0], location_list[4][1])
        elif accounts == 4 or accounts == 5:
            self.add_button.move(location_list[5][0], location_list[5][1])
        elif accounts == 6:
            self.add_button.hide()
        self.delete_accounts_label = QLabel(text='删除账户：', parent=self.setwindowwidget)
        self.delete_accounts_label.setGeometry(80, 180, 100, 30)
        self.delete_accounts_combobox = QComboBox(parent=self.setwindowwidget)
        self.delete_accounts_combobox.setGeometry(200, 180, 350, 30)
        for player_id, player_name in player_id_name:
            self.delete_accounts_combobox.addItem(player_name)
            self.delete_accounts_combobox.setItemData(self.delete_accounts_combobox.count() - 1, player_id)
        self.delete_accounts_combobox.setCurrentIndex(-1)
        self.delete_accounts_combobox.setEditable(True)
        self.delete_accounts_combobox.lineEdit().setReadOnly(True)
        self.delete_accounts_combobox.lineEdit().setPlaceholderText('选择一个账户，点击删除')
        self.delete_accounts_button = QPushButton(text='删除账户', parent=self.setwindowwidget)
        self.delete_accounts_button.clicked.connect(self.delete_accounts)
        self.delete_accounts_button.setGeometry(560, 180, 160, 30)
        self.setwindowwidget.hide()

    def delete_accounts(self):
        # 删除账户，从数据库移除，并重新初始化设置窗口
        if self.delete_accounts_combobox.currentIndex() != -1:
            player_id = self.delete_accounts_combobox.itemData(self.delete_accounts_combobox.currentIndex())
            self.cur.execute('delete from profile_id where profile_id=?', (player_id,))
            self.conn.commit()
        else:
            self.mbox = QMessageBox(self.setwindowwidget)
            self.mbox.information(self, '提示', '请先选择一个账户')
        self.setwindowwidget.deleteLater()
        self.setwindow()
        self.get_now_availiable()
        self.data.profile_id = self.now_availiable_id
        self.setwindowwidget.show()

    def edit_hotkey(self):
        # 自定义快捷键
        self.set_hotkey_label.setText('请输入')
        threading.Thread(target=self.wait_keyboard, daemon=True).start()

    def wait_keyboard(self):
        # 通过子线程读取键盘输入的快捷键，支持组合键
        combination_key_list = ['ctrl', 'shift', 'alt']
        key_event = keyboard.read_event()
        key1 = self.on_key_event(key_event)
        values = key1
        if key1 in combination_key_list:
            while True:
                key_event = keyboard.read_event()
                key2 = self.on_key_event(key_event)
                if key2 != key1:
                    break
            values = values + '+' + key2
            combination_key_list.remove(key1)
            if key2 in combination_key_list:
                while True:
                    key_event = keyboard.read_event()
                    key3 = self.on_key_event(key_event)
                    if key3 != key1 and key3 != key2:
                        break
                values = values + '+' + key3
                combination_key_list.remove(key2)
                if key3 in combination_key_list:
                    while True:
                        key_event = keyboard.read_event()
                        key4 = self.on_key_event(key_event)
                        if key4 not in ['ctrl', 'shift', 'alt']:
                            break
                    values = values + '+' + key4
        self.keyboard_single.emit(values)

    def update_hotkey(self, hotkey):
        # 更新最新快捷键到数据库，不支持绑定windows键
        if 'windows' not in hotkey:
            self.cur.execute("insert or replace into settings(value,type) values (?,'hotkey')", (hotkey,))
            self.conn.commit()
            self.set_hotkey_label.setText(hotkey)
            self.set_hotkey(hotkey)
        else:
            self.mbox = QMessageBox(self)
            self.mbox.information(self, '提示', '不支持绑定windows键')

    def click_on_button(self):
        # 单击账户时，切换数据追踪到该账户，同时改变按钮颜色为绿色
        self.sender().setStyleSheet("color: #33ff99")
        for widget in self.setwindowwidget.findChildren(QPushButton):
            if widget.objectName() == str(self.now_availiable_id):
                widget.setStyleSheet("color: black")
        self.cur.execute('update profile_id set status = -1')
        self.cur.execute('update profile_id set status = 1 where profile_id = ?', (self.sender().objectName(),))
        self.conn.commit()
        self.get_now_availiable()
        self.data.profile_id = self.now_availiable_id

    def add_player(self):
        # 打开新增账户窗口
        self.setwindowwidget.hide()
        self.setprofileidwidget.show()

    def set_profile_id(self):
        # 初始化新增账户窗口
        on_focus = SimpleNamespace(value=False)
        self.setprofileidwidget = SubWindow(self, self.uiwidget, self.save_window_position, on_focus=on_focus, objectName="setprofileidwidget")
        # self.setprofileidwidget = QMainWindow()
        # self.setprofileidwidget.setWindowFlags(Qt.WindowType.SubWindow)
        self.setprofileidwidget.setWindowIcon(self.icon)
        self.setprofileidwidget.setWindowTitle('新增账户')
        self.setprofileidwidget.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        self.setprofileidwidget.resize(790, 190)
        self.setprofileidwidget.setFont(self.widget_font)
        location = self.window_location.get(self.setprofileidwidget.windowTitle())
        try:
            self.setprofileidwidget.move(location[0], location[1])
        except:
            self.center_window(self.setprofileidwidget, is_top=False)
        self.game_id = SearchCompleter(parent=self.setprofileidwidget, PlaceholderText="请输入游戏ID...       ID并不唯一，请根据最后一场比赛判断你的账户", on_focus=on_focus)
        self.game_id.setStyleSheet("border: none")
        self.game_id.textChanged.connect(self.search_player)
        self.game_id.setGeometry(30, 81, 640, 30)
        self.configurm = QPushButton(parent=self.setprofileidwidget)
        self.configurm.setGeometry(690, 81, 80, 30)
        self.configurm.setText('确认')
        self.configurm.clicked.connect(self.name_configurm)
        self.setprofileidwidget.hide()

    def search_player(self):
        # 用户输入游戏ID时，打开搜索线程，通过API接口搜索ID
        self.game_id.set_suggestions_list({"正在检索ID，请稍候...": ""})
        search_threading = threading.Thread(target=self.data.player_search, daemon=True, args=(self.game_id.text(),))
        search_threading.start()

    def refresh_game_id(self, message):
        # API接口返回数据时，刷新gui界面
        self.game_id.blockSignals(True)
        max_timestamp = max(map(float, self.query_rs))
        player_data = self.query_rs.get(max_timestamp)
        searching_dic = {f'{player_name}({profile_id}) 最后一场比赛({player_last_game})': (profile_id, player_name) for profile_id, player_name, player_last_game in player_data}
        self.game_id.set_suggestions_list(searching_dic)
        self.game_id.blockSignals(False)

    def name_configurm(self):
        # 单击确认按钮时，将选中的游戏ID写入数据库，并将数据线程的追踪账户切换到该ID
        try:
            self.game_id.suggestion_list.hide()
            pid, player_name = self.game_id.applied_suggestion
            try:
                self.cur.execute('insert into profile_id(profile_id, player_name) values(?, ?)', (pid, player_name))
                self.conn.commit()
            except:
                pass
            self.data.profile_id = pid
            self.now_availiable_id = pid
            self.setwindowwidget.deleteLater()
            self.setwindow()
            self.game_id.setText('')
            self.show()
            self.setwindowwidget.hide()
            self.setprofileidwidget.hide()
        except Exception as e:
            print(e)
            self.mbox = QMessageBox(self.setwindowwidget)
            self.mbox.information(self, '提示', '必须选择你的账户')

    def setting(self):
        # 任务栏右键单开菜单，单击设置时，打开设置窗口
        self.setwindowwidget.show()
        # self.hide()
        self.setprofileidwidget.hide()

    def exit(self):
        # 清理pid文件，关闭程序
        self.tray_icon.hide()
        self.setwindowwidget.close()
        self.setprofileidwidget.close()
        try:
            os.remove(self.pid_path)
        except:
            pass
        try:
            os.remove(self.temp_html)
        except:
            pass
        QApplication.instance().quit()

    def tray_icon_clicked(self, reason):
        # 双击任务栏图标时，显示/隐藏主界面
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_window()

    def toggle_window(self):
        # 检测是否由主线程调度，若是执行，若否重新提交至主线程
        if threading.current_thread() == threading.main_thread():
            # 切换主界面显隐
            if self.isVisible():
                self.hide()
            else:
                self.show()
        else:
            self.hotkey_signal.emit('')

    def load_data_from_database(self):
        # 启动时，从数据库读取已保存的游戏对局数据，无数据则跳过
        try:
            self.cur.execute('select game_id from last_game limit 1')
            game_id = self.cur.fetchone()[0]
            if game_id != self.last_game_id:
                self.cur.execute('select count(1) from last_game')
                game_mode = self.cur.fetchone()[0]
                self.cur.execute('select map from last_game limit 1')
                map_name = self.cur.fetchone()[0]
                self.cur.execute('select kind from last_game limit 1')
                kind = self.cur.fetchone()[0]
                self.cur.execute('select player,civilization,profile_id,player_mmr,win_rate,kind from last_game order by team,player')
                player_data = self.cur.fetchall()
                self.last_game_data = (map_name, game_id, game_mode, player_data, kind)
                self.gui_reload('reload game')
                self.last_game_id = game_id
                self.data.last_game_id = game_id
        except Exception as e:
            pass

    def player_icon(self, civilization):
        # 根据文明返回图标
        pixmap = QPixmap()
        pixmap.loadFromData(self.civilization_icon_dic.get(civilization))
        player_icon = QGraphicsScene()
        icon = pixmap.scaled(36, 18)
        player_icon.addPixmap(icon)
        player_icon.setSceneRect(0, 0, 36, 18)
        return player_icon
    
    def player_rank(self, player_mmr, game_mode=8):
        # 根据玩家mmr返回段位图标
        if game_mode > 2:
            map = self.team_mmr_rank_map
        else:
            map = self.solo_mmr_rank_map
        for threshold, r in map:
            try:
                if int(player_mmr) >= threshold:
                    rank = r
                    break
            except:
                rank = 'unranked'
        pixmap = QPixmap()
        pixmap.loadFromData(self.rank_icon_dic.get(rank))
        rank_icon = QGraphicsScene()
        icon = pixmap.scaled(26, 40)
        rank_icon.addPixmap(icon)
        rank_icon.setSceneRect(0, 0, 26, 40)
        return rank_icon

    def ui(self):
        # 初始化主界面
        self.uiwidget = QWidget(parent=self)
        self.uiwidget.setGeometry(0, 0, 965, 190)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle('Aoe4mmr')
        location = self.window_location.get(self.windowTitle())
        try:
            self.move(location[0], location[1])
        except:
            self.center_window(self, is_top=True)
        self.uiwidget.setFont(self.global_font)
        self.player1_rank = QGraphicsView(parent=self.uiwidget)
        self.player1_rank.setObjectName('player1_rank')
        self.player1_rank.setGeometry(10, 30, 26, 40)
        self.player1_rank.setStyleSheet('background: transparent;border:0px')
        self.player1_rank.setScene(self.player_rank(1500))
        self.player1_rank.hide()

        self.player1_icon = QGraphicsView(parent=self.uiwidget)
        self.player1_icon.setObjectName('player1_icon')
        self.player1_icon.setGeometry(40, 40, 38, 20)
        self.player1_icon.setStyleSheet('background: transparent;border:0px')
        self.player1_icon.setScene(self.player_icon('chinese'))

        self.player2_rank = QGraphicsView(parent=self.uiwidget)
        self.player2_rank.setObjectName('player2_rank')
        self.player2_rank.setGeometry(10, 70, 26, 40)
        self.player2_rank.setStyleSheet('background: transparent;border:0px')
        self.player2_rank.setScene(self.player_rank(1500))
        self.player2_rank.hide()

        self.player2_icon = QGraphicsView(parent=self.uiwidget)
        self.player2_icon.setObjectName('player2_icon')
        self.player2_icon.setGeometry(40, 80, 38, 20)
        self.player2_icon.setStyleSheet('background: transparent;border:0px')
        self.player2_icon.setScene(self.player_icon('chinese'))

        self.player3_rank = QGraphicsView(parent=self.uiwidget)
        self.player3_rank.setObjectName('player3_rank')
        self.player3_rank.setGeometry(10, 110, 26, 40)
        self.player3_rank.setStyleSheet('background: transparent;border:0px')
        self.player3_rank.setScene(self.player_rank(1500))
        self.player3_rank.hide()

        self.player3_icon = QGraphicsView(parent=self.uiwidget)
        self.player3_icon.setObjectName('player3_icon')
        self.player3_icon.setGeometry(40, 120, 38, 20)
        self.player3_icon.setStyleSheet('background: transparent;border:0px')
        self.player3_icon.setScene(self.player_icon('chinese'))

        self.player4_rank = QGraphicsView(parent=self.uiwidget)
        self.player4_rank.setObjectName('player4_rank')
        self.player4_rank.setGeometry(10, 150, 26, 40)
        self.player4_rank.setStyleSheet('background: transparent;border:0px')
        self.player4_rank.setScene(self.player_rank(1500))
        self.player4_rank.hide()

        self.player4_icon = QGraphicsView(parent=self.uiwidget)
        self.player4_icon.setObjectName('player4_icon')
        self.player4_icon.setGeometry(40, 160, 38, 20)
        self.player4_icon.setStyleSheet('background: transparent;border:0px')
        self.player4_icon.setScene(self.player_icon('chinese'))

        self.player5_rank = QGraphicsView(parent=self.uiwidget)
        self.player5_rank.setObjectName('player5_rank')
        self.player5_rank.setGeometry(940, 30, 26, 40)
        self.player5_rank.setStyleSheet('background: transparent;border:0px')
        self.player5_rank.setScene(self.player_rank(1500))
        self.player5_rank.hide()

        self.player5_icon = QGraphicsView(parent=self.uiwidget)
        self.player5_icon.setObjectName('player5_icon')
        self.player5_icon.setGeometry(895, 40, 38, 20)
        self.player5_icon.setStyleSheet('background: transparent;border:0px')
        self.player5_icon.setScene(self.player_icon('chinese'))

        self.player6_rank = QGraphicsView(parent=self.uiwidget)
        self.player6_rank.setObjectName('player6_rank')
        self.player6_rank.setGeometry(940, 70, 26, 40)
        self.player6_rank.setStyleSheet('background: transparent;border:0px')
        self.player6_rank.setScene(self.player_rank(1500))
        self.player6_rank.hide()

        self.player6_icon = QGraphicsView(parent=self.uiwidget)
        self.player6_icon.setObjectName('player6_icon')
        self.player6_icon.setGeometry(895, 80, 38, 20)
        self.player6_icon.setStyleSheet('background: transparent;border:0px')
        self.player6_icon.setScene(self.player_icon('chinese'))

        self.player7_rank = QGraphicsView(parent=self.uiwidget)
        self.player7_rank.setObjectName('player7_rank')
        self.player7_rank.setGeometry(940, 110, 26, 40)
        self.player7_rank.setStyleSheet('background: transparent;border:0px')
        self.player7_rank.setScene(self.player_rank(1500))
        self.player7_rank.hide()

        self.player7_icon = QGraphicsView(parent=self.uiwidget)
        self.player7_icon.setObjectName('player7_icon')
        self.player7_icon.setGeometry(895, 120, 38, 20)
        self.player7_icon.setStyleSheet('background: transparent;border:0px')
        self.player7_icon.setScene(self.player_icon('chinese'))

        self.player8_rank = QGraphicsView(parent=self.uiwidget)
        self.player8_rank.setObjectName('player8_rank')
        self.player8_rank.setGeometry(940, 150, 26, 40)
        self.player8_rank.setStyleSheet('background: transparent;border:0px')
        self.player8_rank.setScene(self.player_rank(1500))
        self.player8_rank.hide()

        self.player8_icon = QGraphicsView(parent=self.uiwidget)
        self.player8_icon.setObjectName('player8_icon')
        self.player8_icon.setGeometry(895, 160, 38, 20)
        self.player8_icon.setStyleSheet('background: transparent;border:0px')
        self.player8_icon.setScene(self.player_icon('chinese'))

        self.map = OutlinedLabel(parent=self.uiwidget)
        self.map.setGeometry(0, 5, 960, 30)
        self.map.set_text_color("#CC9F4A")
        self.map.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.map.setText('mapname')

        self.vs = OutlinedLabel(parent=self.uiwidget)
        self.vs.setGeometry(0, 40, 960, 30)
        self.vs.set_text_color("#CC9F4A")
        self.vs.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vs.setText('vs')

        self.player1 = OutlinedLabel(parent=self.uiwidget)
        self.player1.setObjectName('player1')
        self.player1.setGeometry(80, 40, 240, 30)
        self.player1.setText('player1')
        self.player1.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.player2 = OutlinedLabel(parent=self.uiwidget)
        self.player2.setObjectName('player2')
        self.player2.setGeometry(80, 80, 240, 30)
        self.player2.setText('player2')
        self.player2.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.player3 = OutlinedLabel(parent=self.uiwidget)
        self.player3.setObjectName('player3')
        self.player3.setGeometry(80, 120, 240, 30)
        self.player3.setText('player3')
        self.player3.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.player4 = OutlinedLabel(parent=self.uiwidget)
        self.player4.setObjectName('player4')
        self.player4.setGeometry(80, 160, 240, 30)
        self.player4.setText('player4')
        self.player4.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.player1mmr = OutlinedLabel(parent=self.uiwidget)
        self.player1mmr.setObjectName('player1mmr')
        self.player1mmr.setFont(self.global_font)
        self.player1mmr.setGeometry(330, 38, 120, 30)
        self.player1mmr.setText('1500')

        self.player2mmr = OutlinedLabel(parent=self.uiwidget)
        self.player2mmr.setObjectName('player2mmr')
        self.player2mmr.setGeometry(330, 78, 120, 30)
        self.player2mmr.setText('1500')

        self.player3mmr = OutlinedLabel(parent=self.uiwidget)
        self.player3mmr.setObjectName('player3mmr')
        self.player3mmr.setGeometry(330, 118, 120, 30)
        self.player3mmr.setText('1500')

        self.player4mmr = OutlinedLabel(parent=self.uiwidget)
        self.player4mmr.setObjectName('player4mmr')
        self.player4mmr.setGeometry(330, 158, 120, 30)
        self.player4mmr.setText('1500')

        self.player5 = OutlinedLabel(parent=self.uiwidget)
        self.player5.setObjectName('player5')
        self.player5.setGeometry(650, 40, 240, 30)
        self.player5.setText('player5')
        self.player5.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.player6 = OutlinedLabel(parent=self.uiwidget)
        self.player6.setObjectName('player6')
        self.player6.setGeometry(650, 80, 240, 30)
        self.player6.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player6.setText('player6')

        self.player7 = OutlinedLabel(parent=self.uiwidget)
        self.player7.setObjectName('player7')
        self.player7.setGeometry(650, 120, 240, 30)
        self.player7.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player7.setText('player7')

        self.player8 = OutlinedLabel(parent=self.uiwidget)
        self.player8.setObjectName('player8')
        self.player8.setGeometry(650, 160, 240, 30)
        self.player8.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player8.setText('player8')

        self.player5mmr = OutlinedLabel(parent=self.uiwidget)
        self.player5mmr.setObjectName('player5mmr')
        self.player5mmr.setGeometry(510, 38, 120, 30)
        self.player5mmr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player5mmr.setText('1500')

        self.player6mmr = OutlinedLabel(parent=self.uiwidget)
        self.player6mmr.setObjectName('player6mmr')
        self.player6mmr.setGeometry(510, 78, 120, 30)
        self.player6mmr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player6mmr.setText('1500')

        self.player7mmr = OutlinedLabel(parent=self.uiwidget)
        self.player7mmr.setObjectName('player7mmr')
        self.player7mmr.setGeometry(510, 118, 120, 30)
        self.player7mmr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player7mmr.setText('1500')

        self.player8mmr = OutlinedLabel(parent=self.uiwidget)
        self.player8mmr.setObjectName('player8mmr')
        self.player8mmr.setGeometry(510, 158, 120, 30)
        self.player8mmr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player8mmr.setText('1500')

    def format_text(self, player_mmr, win_rate, i):
        if i < 5:
            try:
                if float(win_rate) != 100 and float(win_rate) > 10:
                    return str(player_mmr) + " " * 2 * (7-len(player_mmr)) + f'{float(win_rate):.2f}%'
                elif float(win_rate) == 100:
                    return str(player_mmr) + " " * 2 * (7 - len(player_mmr)) + f'{float(win_rate):.1f}%'
                elif float(win_rate) < 10:
                    return str(player_mmr) + " " * 2 * (7 - len(player_mmr)) + f'{float(win_rate):.3f}%'
            except:
                return str(player_mmr) + " " * 14 + str(win_rate)
        else:
            try:
                if float(win_rate) != 100 and float(win_rate) > 10:
                    return f'{float(win_rate):.2f}%' + " " * 2 * (7 - len(player_mmr)) + str(player_mmr)
                elif float(win_rate) == 100:
                    return f'{float(win_rate):.1f}%' + " " * 2 * (7 - len(player_mmr)) + str(player_mmr)
                elif float(win_rate) < 10:
                    return f'{float(win_rate):.3f}%' + " " * 2 * (7 - len(player_mmr)) + str(player_mmr)
            except:
                return str(player_mmr) + " " * 14 + str(win_rate)

    def gui_reload(self, message):
        # 获取到新数据时，刷新主界面或设置窗口
        if message == 'reload playername':
            visiable = self.setwindowwidget.isVisible()
            self.setwindowwidget.deleteLater()
            self.setwindow()
            if visiable:
                self.setwindowwidget.show()
        elif message == 'reload game':
            map_name, game_id, game_mode, reload_data, kind = self.last_game_data
            i = 0
            self.map.setText(map_name)
            # 根据对局人数，设置窗口尺寸
            if game_mode == 8:
                self.resize(965, 190)
                for data in reload_data:
                    i += 1
                    (player, civilization, pid, player_mmr, win_rate, kind) = data
                    player = self.islongname(player)
                    widget_player = self.findChild(QLabel, 'player' + str(i))
                    widget_player.setText(player)
                    widget_mmr = self.findChild(QLabel, 'player' + str(i) + 'mmr')
                    widget_mmr.setText(self.format_text(player_mmr, win_rate, i))
                    widget_icon = self.findChild(QGraphicsView, 'player' + str(i) + '_icon')
                    # 设置文明图标
                    icon = self.player_icon(civilization)
                    widget_icon.setScene(icon)
                    # 设置颜色（自己红色，其他人金色）
                    if self.checkplayer(pid):
                        text_color = "#FF2400"
                    else:
                        text_color = "#CC9F4A"
                    widget_player.set_text_color(text_color)
                    widget_mmr.set_text_color(text_color)
                    widget_rank = self.findChild(QGraphicsView, 'player' + str(i) + '_rank')
                    # 如果是排位模式，显示段位图标
                    if 'rm' in kind:
                        widget_rank.show()
                        widget_rank.setScene(self.player_rank(player_mmr, game_mode))
                    else:
                        widget_rank.hide()
            if game_mode == 6:
                self.resize(965, 150)
                for data in reload_data:
                    i += 1
                    if i == 4:
                        i = 5
                    (player, civilization, pid, player_mmr, win_rate, kind) = data
                    widget_player = self.findChild(QLabel, 'player' + str(i))
                    widget_player.setText(player)
                    widget_mmr = self.findChild(QLabel, 'player' + str(i) + 'mmr')
                    widget_mmr.setText(self.format_text(player_mmr, win_rate, i))
                    widget_icon = self.findChild(QGraphicsView, 'player' + str(i) + '_icon')
                    widget_icon.setScene(self.player_icon(civilization))
                    if self.checkplayer(pid):
                        text_color = "#FF2400"
                    else:
                        text_color = "#CC9F4A"
                    widget_player.set_text_color(text_color)
                    widget_mmr.set_text_color(text_color)
                    widget_rank = self.findChild(QGraphicsView, 'player' + str(i) + '_rank')
                    if 'rm' in kind:
                        widget_rank.show()
                        widget_rank.setScene(self.player_rank(player_mmr, game_mode))
                    else:
                        widget_rank.hide()
            if game_mode == 4:
                self.resize(965, 110)
                for data in reload_data:
                    i += 1
                    if i == 3:
                        i = 5
                    (player, civilization, pid, player_mmr, win_rate, kind) = data
                    widget_player = self.findChild(QLabel, 'player' + str(i))
                    widget_player.setText(player)
                    widget_mmr = self.findChild(QLabel, 'player' + str(i) + 'mmr')
                    if i < 5:
                        widget_mmr.setText(f'{player_mmr}   {win_rate}%')
                    else:
                        widget_mmr.setText(f'{win_rate}%   {player_mmr}')
                    widget_icon = self.findChild(QGraphicsView, 'player' + str(i) + '_icon')
                    widget_icon.setScene(self.player_icon(civilization))
                    if self.checkplayer(pid):
                        text_color = "#FF2400"
                    else:
                        text_color = "#CC9F4A"
                    widget_player.set_text_color(text_color)
                    widget_mmr.set_text_color(text_color)
                    widget_rank = self.findChild(QGraphicsView, 'player' + str(i) + '_rank')
                    if 'rm' in kind:
                        widget_rank.show()
                        widget_rank.setScene(self.player_rank(player_mmr, game_mode))
                    else:
                        widget_rank.hide()
            if game_mode == 2:
                self.resize(965, 70)
                for data in reload_data:
                    i += 1
                    if i == 2:
                        i = 5
                    (player, civilization, pid, player_mmr, win_rate, kind) = data
                    widget_player = self.findChild(QLabel, 'player' + str(i))
                    widget_player.setText(player)
                    widget_mmr = self.findChild(QLabel, 'player' + str(i) + 'mmr')
                    widget_mmr.setText(self.format_text(player_mmr, win_rate, i))
                    widget_icon = self.findChild(QGraphicsView, 'player' + str(i) + '_icon')
                    widget_icon.setScene(self.player_icon(civilization))
                    if self.checkplayer(pid):
                        text_color = "#FF2400"
                    else:
                        text_color = "#CC9F4A"
                    widget_player.set_text_color(text_color)
                    widget_mmr.set_text_color(text_color)
                    widget_rank = self.findChild(QGraphicsView, 'player' + str(i) + '_rank')
                    if 'rm' in kind:
                        widget_rank.show()
                        widget_rank.setScene(self.player_rank(player_mmr, game_mode))
                    else:
                        widget_rank.hide()
            self.show()
            self.hide_timer.stop()
            self.hide_timer.start()

    def checkplayer(self, player_id):
        # 检查该选手是否玩家本人
        return player_id == self.now_availiable_id

    def save_window_position(self, window: QMainWindow):
        windowname = window.windowTitle()
        x_position, y_position = window.pos().x(), window.pos().y()
        self.cur.execute('insert or replace into window_location(window, x_location, y_location) values(?, ?, ?)', (windowname, x_position, y_position))
        self.conn.commit()

    def mousePressEvent(self, event: QEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.able_dragging == 1:
            self.mouse_start_pos = event.globalPosition().toPoint() - self.pos()
            self.dragging = True

    def mouseMoveEvent(self, event: QEvent):
        if self.dragging and self.able_dragging == 1:
            self.move(event.globalPosition().toPoint() - self.mouse_start_pos)

    def mouseReleaseEvent(self, event: QEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.resize_dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.save_window_position(self)


class OutlinedLabel(QLabel):
    # 主界面使用带有描边效果的Label显示
    def __init__(self, text=None, outline_color=QColor(255, 255, 255), text_color=QColor(0, 0, 0), font_size=12, parent=None):
        super().__init__(parent)
        self.outline_color = outline_color
        self.text_color = text_color
        self.font_size = font_size
        self.start_x = 0
        self.setText(text)  # 设置文本

    def set_text_color(self, text_color):
        self.text_color = QColor(text_color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 设置字体
        font = QFont("Arial", self.font_size)
        painter.setFont(font)
        # 获取文本行
        lines = self.text().split("<br>")
        # 计算文本的绘制位置
        line_height = self.font_size  # 行高
        total_height = len(lines) * line_height
        start_y = self.height() - total_height - 2  # 垂直居中
        # 绘制轮廓文本
        painter.setPen(self.outline_color)
        for dx in [-1, 0, 1]:  # 水平偏移
            for dy in [-1, 0, 1]:  # 垂直偏移
                if dx != 0 or dy != 0:  # 排除正常文本
                    for i, line in enumerate(lines):
                        # 计算水平居中
                        if self.start_x is None:
                            start_x = (self.width() - painter.fontMetrics().boundingRect(line).width()) / 2
                        elif self.start_x == -1:
                            start_x = (self.width() - painter.fontMetrics().boundingRect(line).width() - 2)
                        else:
                            start_x = 0
                        painter.drawText(int(start_x + dx), int(start_y + dy + i * line_height), line)
        # 绘制正常文本
        painter.setPen(self.text_color)  # 正常文本颜色
        for i, line in enumerate(lines):
            # 计算水平居中
            if self.start_x is None:
                start_x = (self.width() - painter.fontMetrics().boundingRect(line).width()) / 2
            elif self.start_x == -1:
                start_x = (self.width() - painter.fontMetrics().boundingRect(line).width() - 2)
            else:
                start_x = 0
            painter.drawText(int(start_x), int(start_y + i * line_height), line)
        painter.end()

    def setText(self, text):
        super().setText(text)  # 调用父类的 setText 方法
        self.update()

    def setAlignment(self, Alignment):
        super().setAlignment(Alignment)
        if Alignment == Qt.AlignmentFlag.AlignCenter:
            self.start_x = None
        if Alignment == Qt.AlignmentFlag.AlignRight:
            self.start_x = -1
        self.update()


class SubWindow(QMainWindow):
    def __init__(self, main_window, main_widget, postion_func=None, able_dragging=1, on_focus=SimpleNamespace(value=False), objectName=None):
        self.on_focus = on_focus
        super().__init__()
        self.main_window = main_window
        self.main_widget = main_widget
        self.postion_func = postion_func
        self.dragging = False
        self.setObjectName(objectName)
        self.able_dragging = able_dragging

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        try:
            self.main_window.game_id.suggestion_list.hide()
        except:
            pass

    def mousePressEvent(self, event: QEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.testAttribute(Qt.WA_TranslucentBackground) and self.able_dragging == 1:
            self.mouse_start_pos = event.globalPosition().toPoint() - self.pos()
            self.dragging = True

    def mouseMoveEvent(self, event: QEvent):
        if self.dragging and self.testAttribute(Qt.WA_TranslucentBackground):
            self.move(event.globalPosition().toPoint() - self.mouse_start_pos)

    def mouseReleaseEvent(self, event: QEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.testAttribute(Qt.WA_TranslucentBackground):
            self.dragging = False
            self.resize_dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self.postion_func(self)

    def changeEvent(self, event: QEvent):
        """
        重写 changeEvent 以检测窗口激活/停用。
        """
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                self.on_focus.value = False
                try:
                    self.main_window.game_id.suggestion_list.hide()
                except:
                    pass
            else:
                self.on_focus.value = True
                try:
                    if len(self.main_window.game_id.suggestions_dic) > 0 and self.objectName() == "setprofileidwidget":
                        self.main_window.game_id.show_suggestions()
                except:
                    pass
        super().changeEvent(event)


class SearchCompleter(QLineEdit):
    # 使用Listview和linedit编写的自定义搜索框，类似百度的效果
    def __init__(self, parent=None, PlaceholderText=None, on_focus=SimpleNamespace(value=False)):
        super().__init__(parent)
        self.on_focus = on_focus
        self.setPlaceholderText(PlaceholderText)
        # 下拉建议列表
        self.suggestion_list = QListWidget()
        self.suggestion_list.setWindowFlags(Qt.WindowType.Tool |
                                            Qt.WindowType.FramelessWindowHint |
                                            Qt.WindowType.WindowStaysOnTopHint |
                                            Qt.WindowType.WindowDoesNotAcceptFocus)
        self.suggestion_list.setFocusPolicy(Qt.NoFocus)  # 明确不要焦点
        self.suggestion_list.setVisible(False)
        self.suggestions = []
        # self.textChanged.connect(self.show_suggestions)
        # 连接信号
        self.suggestion_list.itemClicked.connect(self.apply_suggestion)

    def set_suggestions_list(self, suggestions_dic):
        print(suggestions_dic)
        if len(suggestions_dic) == 0:
            suggestions_dic = {"没有检索到相关ID": ""}
        self.suggestions = [k for k, v in suggestions_dic.items()]
        self.suggestions_dic = suggestions_dic
        self.show_suggestions()

    def show_suggestions(self):
        """显示建议列表(如果窗口激活)"""
        if self.on_focus.value:
            text = self.text()
            if not text:
                self.suggestion_list.hide()
                return
            # 过滤建议
            filtered = [s for s in self.suggestions if text.lower() in s.lower() or s == "正在检索ID，请稍候..." or s == "没有检索到相关ID"]
            self.suggestion_list.clear()
            for item in filtered:
                self.suggestion_list.addItem(item)
            if filtered:
                # 定位下拉列表
                position = self.mapToGlobal(self.rect().bottomLeft())
                self.suggestion_list.move(position)
                self.suggestion_list.setFixedWidth(self.width())
                self.suggestion_list.setVisible(True)
                self.suggestion_list.setFocus()
            else:
                self.suggestion_list.hide()

    def apply_suggestion(self, item):
        """应用选中的建议"""
        if item.text() != "正在检索ID，请稍候..." and item.text() != "没有检索到相关ID":
            self.blockSignals(True)
            self.setText(item.text())
            self.suggestion_list.hide()
            self.applied_suggestion = self.suggestions_dic.get(item.text())
            self.blockSignals(False)

    def keyPressEvent(self, event: QKeyEvent):
        """处理键盘事件"""
        if self.suggestion_list.isVisible():
            if event.key() == Qt.Key_Down:
                self.suggestion_list.setCurrentRow(
                    min(self.suggestion_list.currentRow() + 1,
                        self.suggestion_list.count() - 1)
                )
                return
            elif event.key() == Qt.Key_Up:
                self.suggestion_list.setCurrentRow(
                    max(self.suggestion_list.currentRow() - 1, 0)
                )
                return
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if self.suggestion_list.currentItem():
                    self.apply_suggestion(self.suggestion_list.currentItem())
                return
            elif event.key() == Qt.Key_Escape:
                self.suggestion_list.hide()
                self.setFocus()
                return
        super().keyPressEvent(event)


if __name__ == "__main__":
    pid_path = Path.home() / "AppData" / "Local" / "Aoe4mmr" / "pid"
    # 仅单实例运行，启动时校验实例是否已经运行
    if MainWindow.is_process_running(pid_path):
        app = QApplication(sys.argv)
        window = MainWindow(pid_path)
        sys.exit(app.exec())
    else:
        print("Another instance is already running.")
