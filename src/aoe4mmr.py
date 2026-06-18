#!/usr/bin/env python3 
# Author: B_Snowflake 
# Date: 2026/5/25 03:36:13 
# LastEditTime: 2026/5/25 03:36:13

import ctypes
import os
import sqlite3
import threading
import keyboard
from . import data
from . import data_rc
from . import settings
from .mygui import my_window as win
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *


class Aoe4mmr:                                                                                                                                    
    def __init__(self, base_path, pid_path, app_name):
        self.base_path = base_path
        self.pid_path = pid_path
        self.database_version = 'v1.2.0'
        self.app_version = 'v1.2.0'
        self.get_all_rc_data()
        self.app_name = app_name
        self.settings_path = self.base_path / "settings.json"
        self.database_path = self.base_path / "database.db"
        self.initilize_database()
        self.conn = sqlite3.connect(self.database_path)
        self.cur = self.conn.cursor()
        self.settings = settings.Settings()
        self.settings.load(self.settings_path)                      
        self.data = data.Data(self.gui_reload, self.settings.picked_profile_id, self.database_path, self.map_dic, self.settings.profile_id.keys(), self.new_version)
        self.game_process_check_timer = QTimer()
        self.game_process_check_timer.setInterval(10000)
        self.game_process_check_timer.timeout.connect(self.game_process_check_timer_timeout)
        self.game_process_check_timer.start()
        self.setupUI()
        
    def setupUI(self):
        # 设置界面UI
        self.mmr_window = win.MmrWindow(self.settings.picked_profile_id, self.civilization_icon_dic, self.rank_icon_dic, self.settings.window_location)
        self.main_window = win.MyWindow(self.settings, self.civilization_icon_dic, self.map_dic)
        self.main_window.setWindowIcon(self.app_icon)
        self.main_window.setWindowTitle(self.app_name)
        self.main_window.keyboard_single.connect(self.on_hotkey_changed)
        self.main_window.add_new_account_signal.connect(self.add_new_account)
        self.main_window.settings_changed_signal.connect(self.on_settings_changed)
        self.mmr_window.settings_changed_signal.connect(self.on_settings_changed)
        self.main_window.setFixedSize(900, 600)
        self.main_window.setMinimumSize(900, 600)
        self.main_window.setMaximumSize(900, 600)
        self.on_hotkey_changed()
        if self.settings.show_gui_when_startup:
            self.main_window.show()
            self.main_window.raise_()
        else:
            self.main_window.hide()
        action1 = QAction("主页", self.mmr_window)
        action2 = QAction("退出", self.mmr_window)
        action1.triggered.connect(lambda: self.toggle_window(window=self.main_window))
        action2.triggered.connect(self.close)
        self.tray_icon_menu = QMenu(self.mmr_window)
        self.tray_icon_menu.addAction(action1)
        self.tray_icon_menu.addAction(action2)
        self.tray_icon = QSystemTrayIcon(self.mmr_window)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip('Aoe4mmr')
        self.tray_icon.setContextMenu(self.tray_icon_menu)
        self.tray_icon.activated.connect(self.tray_icon_clicked)
        self.tray_icon.show()
        self.load_data_from_database()
        if not self.settings.profile_id:
            self.main_window.left_menu.toolbutton_dic['new_button'][0].click()
        else:
            self.gui_reload(reason="reload player", data=self.settings.profile_id)        
    
    def new_version(self, version):
        if version != self.app_version:
            self.main_window.new_version_signal.emit()
    
    def on_settings_changed(self, data):
        key, values = data
        if key == 'show_gui_when_startup':
            self.settings.show_gui_when_startup = values
        elif key == 'enable_dragging':
            self.settings.enable_dragging = values
            self.mmr_window.enable_dragging = values
        elif key == 'window_location':
            self.settings.window_location = [values.x(), values.y()]
        elif key == 'picked_profile_id':
            self.settings.picked_profile_id = values
            self.data.profile_id = values
        elif key == 'delete_profile_id':
            self.settings.delete_profile_id(values)
            self.gui_reload('reload player', self.settings.profile_id)
        self.settings.save()
    
    def add_new_account(self, player_info):
        try:
            self.settings.update_profile_id(*player_info)
            self.settings.picked_profile_id = (player_info[0])
            self.data.profile_id = self.settings.picked_profile_id
            self.main_window.left_menu.toolbutton_dic['home_button'][0].click()
            self.gui_reload(reason='reload player', data=self.settings.profile_id)
        except Exception as e:
            self.main_window.show_message(message=f"添加失败，{e}")
    
    def load_data_from_database(self):
        # 启动时，从数据库读取已保存的游戏对局数据，无数据则跳过
        try:
            self.cur.execute('select game_id from last_game limit 1')
            game_id = self.cur.fetchone()[0]
            self.cur.execute('select count(1) from last_game')
            game_mode = self.cur.fetchone()[0]
            self.cur.execute('select map from last_game limit 1')
            map_name = self.cur.fetchone()[0]
            self.cur.execute('select kind from last_game limit 1')
            kind = self.cur.fetchone()[0]
            self.cur.execute('select player, civilization, profile_id, player_mmr, win_rate, kind from last_game order by team, player')
            player_data = self.cur.fetchall()
            last_game_data = (map_name, game_id, game_mode, player_data, kind)
            self.gui_reload('reload game', last_game_data)
            self.data.last_game_id = game_id
            QTimer.singleShot(0, self.mmr_window.hide)
        except Exception as e:
            pass
        
    def initilize_database(self):
        # 读取用户信息数据库版本号，如果是低版本数据库或无数据库，重新初始化
        def connect():
            conn = sqlite3.connect(self.database_path)
            cur = conn.cursor()
            return conn, cur
        
        conn, cur = connect()
        try:
            cur.execute('select name, version from version where name = "database"')
            database_version = cur.fetchone()[1]
        except Exception as e:
            database_version = None
        if database_version != self.database_version:
            conn.close()
            os.remove(self.database_path)
            conn, cur = connect()
            cur.execute(
                'create table if not exists last_game (game_id TEXT NOT NULL,player TEXT,win_rate TEXT,civilization TEXT,map TEXT,profile_id INTEGER,'
                'player_mmr TEXT,team TEXT, kind Text,PRIMARY KEY (game_id,player))')
            cur.execute('create table if not exists version (name TEXT NOT NULL,version TEXT, PRIMARY KEY (name))')
            cur.execute("insert into version(name, version) values(?, ?)", ('database', self.database_version))
            conn.commit()
        conn.close()
    
    def tray_icon_clicked(self, reason):
        # 双击任务栏图标时，显示/隐藏界面
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.mmr_window.isVisible():
                self.mmr_window.hide()
            else:
                self.mmr_window.show()
                
    def gui_reload(self, reason, data):
        # 刷新界面数据
        if reason == 'reload game':
            self.mmr_window.gui_reload_signal.emit(data)
            self.mmr_window.hide()
            self.main_window.menu_page.search_player_details.get_game_history(self.settings.picked_profile_id)
        elif reason == 'reload player':
            self.main_window.gui_reload_signal.emit(data)
        
    def toggle_window(self, checked=False, window=None):
        window = self.mmr_window if window is None else window
        if window == self.mmr_window and not self.check_process():
            return
        if window == self.mmr_window:
            if window.isVisible():
                window.hide()
            else:
                window.show()
        else:  
            if window.isVisible() and window.isActiveWindow():
                window.hide()
            else:
                window.hide()
                window.show()
                window.raise_()

    def on_hotkey_changed(self):
        try:
            keyboard.remove_hotkey(self.added_hotkey)
        except:
            pass
        keyboard.add_hotkey(self.settings.hotkey, self.toggle_window)
        self.added_hotkey = self.settings.hotkey
    
    def game_process_check_timer_timeout(self):
        if self.check_process():
            if self.data.quit_signal:
                self.data.quit_signal = False
                self.start_data_thread()
        else:
            if not self.data.quit_signal:
                self.data.quit_signal = True
                self.mmr_window.hide()

    def start_data_thread(self):
        if hasattr(self, "data_thread"):
            alive = self.data_thread.is_alive()
        else:            
            alive = False
        if not alive:
            self.data_thread = threading.Thread(target=self.data.worker, daemon=True)
            self.data_thread.start()
        
    def close(self, checked=False):
        self.tray_icon.hide()
        self.mmr_window.close()
        self.main_window.close()
        try:
            os.remove(self.pid_path)
        except:
            pass
        QApplication.instance().quit()
    
    def switch_now_availiable_id(self, new_id):
        self.settings.update_picked_profile_id(new_id)
        self.mmr_window.now_availiable_id = new_id
        self.data.now_availiable_id = new_id
      
    @staticmethod
    def is_process_running(pid_path):
        # 仅支持单实例运行，通过pid文件判断程序是否已打开
        if not os.path.exists(pid_path):
            os.makedirs(os.path.dirname(pid_path), exist_ok=True)
            with open(pid_path, 'w', encoding='utf-8') as f:
                f.write(str(os.getpid()))
            return True
        else:
            try:
                with open(pid_path, 'r', encoding='utf-8') as f:
                    pid = int(f.read())
                if __class__.get_process_name_by_pid(pid) in ('Aoe4mmr.exe', 'python.exe'):   # NOQA
                    return False
                else:
                    with open(pid_path, 'w', encoding='utf-8') as f:
                        f.write(str(os.getpid()))
                    return True
            except Exception as e:
                with open(pid_path, 'w', encoding='utf-8') as f:
                    f.write(str(os.getpid()))
                return True
            
    def get_all_rc_data(self):
        # 连接资源数据库，获取地图和图标数据
        # 从 .qrc 资源中读取二进制数据
        file = QFile(':/data/resources/data.pck')
        if not file.open(QIODevice.ReadOnly):
            raise IOError(f"error when open qrc sqlite")
        db_data = file.readAll().data() # 获取字节流
        file.close()
        # 创建内存连接
        data_conn = sqlite3.connect(':memory:', check_same_thread=False)
        # 将字节流写入内存
        try:
            data_conn.deserialize(db_data)
        except AttributeError as e:
            print('error when open db:', {e})
        data_cur = data_conn.cursor()
        
        self.app_icon = QPixmap()
        self.app_icon.loadFromData(data_cur.execute('select data from t_icon where type = ?', ('app_icon',)).fetchone()[0])
        
        civilization_icon_rs = data_cur.execute('select name, data from t_icon where type = ?', ('civilization',))
        self.civilization_icon_dic = {row[0]: row[1] for row in civilization_icon_rs.fetchall()}
        
        rank_icon_rs = data_cur.execute('select name, data from t_icon where type in (?,?) ', ('rank', 'team_rank'))
        self.rank_icon_dic = {row[0]: row[1] for row in rank_icon_rs.fetchall()}
        
        map_dic_rs = data_cur.execute('select english_name, chinese_name, icon from t_map', )
        self.map_dic = {row[0]: (row[1], row[2]) for row in map_dic_rs.fetchall()}
        
        data_conn.close()
        del data_conn
        data_rc.qCleanupResources()
        
    @staticmethod
    def check_process(process_name='RelicCardinal.exe'):
        # 检查游戏是否已经运行
        """Windows API"""
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.WinDLL('kernel32')
        # 创建进程快照
        hSnapshot = kernel32.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ('dwSize', ctypes.c_ulong),
                ('cntUsage', ctypes.c_ulong),
                ('th32ProcessID', ctypes.c_ulong),
                ('th32DefaultHeapID', ctypes.c_void_p),
                ('th32ModuleID', ctypes.c_ulong),
                ('cntThreads', ctypes.c_ulong),
                ('th32ParentProcessID', ctypes.c_ulong),
                ('pcPriClassBase', ctypes.c_long),
                ('dwFlags', ctypes.c_ulong),
                ('szExeFile', ctypes.c_char * 260)
            ]
        pe32 = PROCESSENTRY32()
        pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if kernel32.Process32First(hSnapshot, ctypes.byref(pe32)):
            while True:
                if pe32.szExeFile.decode().lower() == process_name.lower():
                    kernel32.CloseHandle(hSnapshot)
                    return True
                if not kernel32.Process32Next(hSnapshot, ctypes.byref(pe32)):
                    break
        kernel32.CloseHandle(hSnapshot)
        return False
    
    @staticmethod
    def get_process_name_by_pid(pid):
        # 定义常量
        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
        # 定义结构体
        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ('dwSize', ctypes.wintypes.DWORD),
                ('cntUsage', ctypes.wintypes.DWORD),
                ('th32ProcessID', ctypes.wintypes.DWORD),
                ('th32DefaultHeapID', ctypes.POINTER(ctypes.wintypes.ULONG)),  # 使用指针类型
                ('th32ModuleID', ctypes.wintypes.DWORD),
                ('cntThreads', ctypes.wintypes.DWORD),
                ('th32ParentProcessID', ctypes.wintypes.DWORD),
                ('pcPriClassBase', ctypes.wintypes.LONG),
                ('dwFlags', ctypes.wintypes.DWORD),
                ('szExeFile', ctypes.c_char * 260)  # 进程名缓冲区
            ]
        # 加载kernel32并设置函数原型
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        # 设置函数原型
        kernel32.CreateToolhelp32Snapshot.restype = ctypes.wintypes.HANDLE
        kernel32.CreateToolhelp32Snapshot.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.DWORD]
        kernel32.Process32First.restype = ctypes.wintypes.BOOL
        kernel32.Process32First.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
        kernel32.Process32Next.restype = ctypes.wintypes.BOOL
        kernel32.Process32Next.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
        kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
        kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
        # 创建进程快照
        hSnapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        # 检查快照句柄是否有效
        if hSnapshot == INVALID_HANDLE_VALUE or not hSnapshot:
            error_code = ctypes.get_last_error()
            if error_code:
                raise ctypes.WinError(error_code)
            return None
        pe32 = PROCESSENTRY32()
        pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)
        # 遍历进程列表
        process_name = None
        # 获取第一个进程
        if kernel32.Process32First(hSnapshot, ctypes.byref(pe32)):
            while True:
                # 检查是否匹配PID
                if pe32.th32ProcessID == pid:
                    # 提取文件名部分（去掉路径）
                    full_name = pe32.szExeFile.decode('latin-1', errors='ignore')
                    process_name = full_name.split('\\')[-1]
                    break
                # 获取下一个进程
                if not kernel32.Process32Next(hSnapshot, ctypes.byref(pe32)):
                    break
        # 关闭句柄
        kernel32.CloseHandle(hSnapshot)
        return process_name