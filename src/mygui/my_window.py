#!/usr/bin/env python3 
# Author: B_Snowflake 
# Date: 2026/5/27 18:45:19 
# LastEditTime: 2026/5/27 18:45:19#!/usr/bin/python3
# Author: B_Snowflake
# Date: 2026/3/21

import re
import sys
import threading
import debugpy
import keyboard
# noinspection PyPackages
from . import window_rc
from . import my_widgets
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pynput.mouse import Listener, Controller


class MyWindow(QMainWindow):

    cursor_signal = Signal(str)
    gui_reload_signal = Signal(dict)
    settings_changed_signal = Signal(tuple)
    add_new_account_signal = Signal(tuple)
    add_new_game_history_signal = Signal(tuple)
    keyboard_single = Signal(str)
    new_version_signal = Signal()

    def __init__(self, settings, civilization_icon_dic, map_dic, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.dragging, self.location, self.resize_dragging, self.edge_size = False, None, False, 8
        self.setWindowTitle('Aoe4Mmr')

        self.settings = settings
        self.mouse = Controller()
        self.cursor_signal.connect(self.set_resize_cursor)
        self.gui_reload_signal.connect(self.gui_reload)
        self.keyboard_single.connect(self.on_hotkey_changed)
        # self.set_theme("src/mygui/Themes/theme.qss")
        self.set_theme()
        self.center_widget = QWidget(parent=self, ObjectName="center_widget")
        self.setCentralWidget(self.center_widget)
        self.new_version_signal.connect(self.on_new_version_founded)
        self.menu_page = my_widgets.MenuPage(self.add_new_account_signal, self.settings_changed_signal, self.settings.max_show_gamehistory, self.settings.max_accounts, self.settings.picked_profile_id, civilization_icon_dic, map_dic, parent=self, ObjectName="menu_page")
        self.menu_page.apply_signal.connect(self.apply_new)
        self.left_menu = my_widgets.LeftMenu(parent=self, pages=self.menu_page)
        
        self.setting_button = QPushButton(parent=self, ObjectName='setting_button')
        self.setting_button.setIcon(QPixmap(":images/icons/cil-settings.svg"))
        self.setting_button.clicked.connect(self.show_setting_page)
        self.setting_button.setFixedSize(34, 34)
        
        self.min_button = QPushButton(parent=self, ObjectName='min_button')
        self.min_button.setIcon(QPixmap(":images/icons/icon_minimize.png"))
        self.min_button.clicked.connect(self.showMinimized)
        self.min_button.setFixedSize(35, 35)

        # self.max_button = QPushButton(parent=self, ObjectName='max_button')
        # self.max_button.setIcon(QPixmap(":images/icons/icon_maximize.png"))
        # self.max_button.clicked.connect(self.toggle_max_restore)
        # self.max_button.setFixedSize(35, 35)

        self.close_button = QPushButton(parent=self, ObjectName='close_button')
        self.close_button.setIcon(QPixmap(":images/icons/icon_close.png"))
        self.close_button.clicked.connect(self.close)
        self.close_button.setFixedSize(34, 34)

        self.center_layout = QVBoxLayout(self.center_widget)
        self.center_layout.setContentsMargins(0, 0, 0, 0)
        self.center_layout.setSpacing(0)
        self.title_bar = QWidget(parent=self, ObjectName='title_bar')
        self.title_bar.setMaximumHeight(35)
        self.title_bar.setMinimumHeight(35)
        self.title_bar_layout = QHBoxLayout(self.title_bar)
        self.body_layout = QHBoxLayout()
        self.body_layout.setContentsMargins(10, 10, 20, 20)
        self.body_layout.setSpacing(10)
        self.center_layout.addWidget(self.title_bar)
        self.center_layout.addLayout(self.body_layout)

        self.title_bar_layout.setContentsMargins(0, 1, 1, 0)
        self.title_bar_layout.setSpacing(0)
        self.title_bar_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.title_bar_layout.addWidget(self.setting_button)
        self.title_bar_layout.addWidget(self.min_button)
        # self.title_bar_layout.addWidget(self.max_button)
        self.title_bar_layout.addWidget(self.close_button)
        self.body_layout.addWidget(self.left_menu)
        self.body_layout.addWidget(self.menu_page)
        self.set_setting_page()
        if not debugpy.is_client_connected():
            threading.Thread(target=self.mouse_listening, daemon=True).start()
    
    def on_new_version_founded(self):
        msg = CustomMessageBox(parent=self, message="发现新版本，是否下载？")
        if msg.exec() == QDialog.Accepted:
            QDesktopServices.openUrl(QUrl("https://github.com/B-Snowflake/aoe4mmr/releases/latest"))
    
    def show_message(self, message):
        CustomMessageBox(message=message)
    
    def gui_reload(self, data):
        self.menu_page.add_my_accounts_to_combobox(data)
        for pushbutton, button_info in self.setting_page_account_setting_widget_dic.items():
            profile_id, account_label = button_info
            account_label.deleteLater()
            pushbutton.deleteLater()
        self.setting_page_account_setting_widget_dic.clear()
        for account in self.settings.profile_id.values():
            account_label = QLabel(parent=self.setting_page_account_setting_widget, text=account.profile_name)
            account_label.setMinimumWidth(130)
            account_pushbutton = QPushButton(parent=self.setting_page_account_setting_widget, text="删除")
            account_pushbutton.setMaximumWidth(60)
            account_pushbutton.clicked.connect(self.on_account_delete_pushbutton_clicked)
            self.setting_page_account_setting_widget_dic[account_pushbutton] = (account.profile_id, account_label)
            self.setting_page_account_setting_widget_layout.addRow(account_label, account_pushbutton)
        
    def apply_new(self):
        self.left_menu.toolbutton_dic['new_button'][0].click()
        self.menu_page.search_completer.setText('')
        
    def show_setting_page(self):
        self.setting_page_frame.setGeometry(self.size().width()/2 - 170, self.size().height()/2 - 140, 340, 280)
        self.setting_page_widget_close_button.setGeometry((self.setting_page_frame.width()-28), 0, 28, 28)
        self.setting_page_left_menu_widget_normal_setting_button.click()
        self.setting_page_frame.show()
    
    def on_account_delete_pushbutton_clicked(self):
        for pushbutton, button_info in self.setting_page_account_setting_widget_dic.items():
            if pushbutton == self.sender():
                profile_id, account_label = button_info
                self.settings_changed_signal.emit(('delete_profile_id', profile_id))
                pushbutton.deleteLater()
                account_label.deleteLater()
                return
                
    def on_setting_page_left_menu_clicked(self):
        for pushbutton, index in self.setting_page_left_menu_widget_pushbutton_list.items():
            if self.sender() == pushbutton:
                self.setting_page_stackwidget.setCurrentIndex(index)
                pushbutton.setChecked(True)
            else:
                pushbutton.setChecked(False)
        
    def on_setting_page_widget_max_show_gamehistory_lineedit_editingFinished(self):
        number = int(self.setting_page_widget_max_show_gamehistory_lineedit.text())
        if number == self.settings.max_show_gamehistory:
            return
        number = min(max(3, number), 99)
        self.setting_page_widget_max_show_gamehistory_lineedit.setText(str(number))
        self.settings.max_show_gamehistory = number
        self.settings.save()
        self.menu_page.max_show_gamehistory = number
        self.menu_page.on_player_account_widget_combobox_currentIndexChanged(self.menu_page.player_account_widget_combobox.currentIndex())
        
    def set_setting_page(self):
        
        def set_setting_page_account_setting_widget():
            self.setting_page_account_setting_widget = QWidget(parent=self.setting_page_frame)
            self.setting_page_account_setting_widget_layout = QFormLayout(self.setting_page_account_setting_widget)
            self.setting_page_account_setting_widget_layout.setContentsMargins(20, 35, 30, 30)
            self.setting_page_account_setting_widget_layout.setVerticalSpacing(20)
            self.setting_page_account_setting_widget_layout.setHorizontalSpacing(10)
            self.setting_page_account_setting_widget_dic = {}
            for account in self.settings.profile_id.values():
                account_label = QLabel(parent=self.setting_page_account_setting_widget, text=account.profile_name)
                account_label.setMinimumWidth(130)
                account_pushbutton = QPushButton(parent=self.setting_page_account_setting_widget, text="删除")
                account_pushbutton.setMaximumWidth(60)
                account_pushbutton.clicked.connect(self.on_account_delete_pushbutton_clicked)
                self.setting_page_account_setting_widget_dic[account_pushbutton] = (account.profile_id, account_label)
                self.setting_page_account_setting_widget_layout.addRow(account_label, account_pushbutton)
                
        def set_setting_page_left_menu_widget():
            self.setting_page_left_menu_widget_pushbutton_list = {}
            self.setting_page_left_menu_widget = QWidget(parent=self.setting_page_frame, ObjectName="setting_page_left_menu_widget")
            self.setting_page_left_menu_widget.setFixedWidth(80)
            self.setting_page_left_menu_widget_layout = QVBoxLayout(self.setting_page_left_menu_widget)
            self.setting_page_left_menu_widget_layout.setContentsMargins(0, 35, 0, 0)
            self.setting_page_left_menu_widget_layout.setSpacing(10)
            self.setting_page_left_menu_widget_normal_setting_button = QPushButton(self.setting_page_left_menu_widget, ObjectName="setting_page_left_menu_widget_button", text="通用")
            self.setting_page_left_menu_widget_pushbutton_list[self.setting_page_left_menu_widget_normal_setting_button] = 0
            self.setting_page_left_menu_widget_normal_setting_button.setFixedSize(80, 30)
            self.setting_page_left_menu_widget_normal_setting_button.setCheckable(True)
            self.setting_page_left_menu_widget_normal_setting_button.clicked.connect(self.on_setting_page_left_menu_clicked)
            self.setting_page_left_menu_widget_account_setting_button = QPushButton(self.setting_page_left_menu_widget, ObjectName="setting_page_left_menu_widget_button", text="账号")
            self.setting_page_left_menu_widget_pushbutton_list[self.setting_page_left_menu_widget_account_setting_button] = 1
            self.setting_page_left_menu_widget_account_setting_button.setFixedSize(80, 30)
            self.setting_page_left_menu_widget_account_setting_button.setCheckable(True)
            self.setting_page_left_menu_widget_account_setting_button.clicked.connect(self.on_setting_page_left_menu_clicked)
            self.setting_page_left_menu_widget_layout.addWidget(self.setting_page_left_menu_widget_normal_setting_button)
            self.setting_page_left_menu_widget_layout.addWidget(self.setting_page_left_menu_widget_account_setting_button)
            self.setting_page_left_menu_widget_layout.addStretch(1)
        
        def set_setting_page_normal_setting_widget():
            self.setting_page_normal_setting_widget = QWidget(parent=self.setting_page_frame)
            self.setting_page_normal_setting_widget_layout = QFormLayout(self.setting_page_normal_setting_widget)
            self.setting_page_normal_setting_widget_layout.setContentsMargins(20, 35, 30, 30)
            self.setting_page_normal_setting_widget_layout.setVerticalSpacing(20)
            self.setting_page_normal_setting_widget_layout.setHorizontalSpacing(10)
            
            self.setting_page_widget_showgui_switchbutton_label = QLabel(parent=self.setting_page_normal_setting_widget, text="启动时显示主界面：")
            self.setting_page_widget_showgui_switchbutton = SwitchButton(parent=self.setting_page_normal_setting_widget)
            self.setting_page_widget_showgui_switchbutton.setChecked(self.settings.show_gui_when_startup)
            self.setting_page_widget_showgui_switchbutton.toggled.connect(self.on_switch_button_clicked)
            self.setting_page_widget_showgui_switchbutton.setFixedSize(QSize(40, 20))
            
            self.setting_page_widget_dragwin_switchbutton_label = QLabel(parent=self.setting_page_normal_setting_widget, text="支持拖拽窗口：")
            self.setting_page_widget_dragwin_switchbutton = SwitchButton(parent=self.setting_page_normal_setting_widget)
            self.setting_page_widget_dragwin_switchbutton.setChecked(self.settings.enable_dragging)
            self.setting_page_widget_dragwin_switchbutton.toggled.connect(self.on_switch_button_clicked)
            self.setting_page_widget_dragwin_switchbutton.setFixedSize(QSize(40, 20))
            
            self.setting_page_widget_max_show_gamehistory_lineedit_label = QLabel(parent=self.setting_page_normal_setting_widget, text="最多显示游戏场数：")
            self.setting_page_widget_max_show_gamehistory_lineedit = QLineEdit(parent=self.setting_page_normal_setting_widget, ObjectName='setting_page_widget_max_show_gamehistory_lineedit')
            validator = QIntValidator(0, 99, self.setting_page_normal_setting_widget)
            self.setting_page_widget_max_show_gamehistory_lineedit.setValidator(validator)
            self.setting_page_widget_max_show_gamehistory_lineedit.editingFinished.connect(self.on_setting_page_widget_max_show_gamehistory_lineedit_editingFinished)
            self.setting_page_widget_max_show_gamehistory_lineedit.setText(str(self.settings.max_show_gamehistory))
            
            self.setting_page_widget_show_win_label = QLabel(text="打开窗口快捷键：")
            self.setting_page_widget_show_win_button = QPushButton(parent=self.setting_page_normal_setting_widget, text=self.settings.hotkey, ObjectName="setting_page_widget_show_win_button")
            self.setting_page_widget_show_win_button.clicked.connect(self.edit_hotkey)
            self.setting_page_widget_show_win_button.setFixedSize(QSize(80, 28))
            
            self.setting_page_normal_setting_widget_layout.addRow(self.setting_page_widget_showgui_switchbutton_label, self.setting_page_widget_showgui_switchbutton)
            self.setting_page_normal_setting_widget_layout.addRow(self.setting_page_widget_dragwin_switchbutton_label, self.setting_page_widget_dragwin_switchbutton)
            self.setting_page_normal_setting_widget_layout.addRow(self.setting_page_widget_max_show_gamehistory_lineedit_label, self.setting_page_widget_max_show_gamehistory_lineedit)
            self.setting_page_normal_setting_widget_layout.addRow(self.setting_page_widget_show_win_label, self.setting_page_widget_show_win_button)
        
        self.setting_page_frame = QFrame(parent=self, ObjectName="setting_page_frame")
        self.setting_page_widget_layout = QHBoxLayout(self.setting_page_frame)
        self.setting_page_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.setting_page_widget_layout.setSpacing(0)
        self.setting_page_stackwidget = QStackedWidget(parent=self.setting_page_frame)
        
        set_setting_page_left_menu_widget()
        set_setting_page_normal_setting_widget()
        set_setting_page_account_setting_widget()

        self.setting_page_stackwidget.addWidget(self.setting_page_normal_setting_widget)
        self.setting_page_stackwidget.addWidget(self.setting_page_account_setting_widget)
        
        self.setting_page_widget_layout.addWidget(self.setting_page_left_menu_widget)
        self.setting_page_widget_layout.addWidget(self.setting_page_stackwidget)
        
        self.setting_page_widget_close_button = QPushButton(parent=self.setting_page_frame, ObjectName='setting_page_widget_close_button')
        self.setting_page_widget_close_button.setIcon(QPixmap(":images/icons/icon_close.png"))
        self.setting_page_widget_close_button.clicked.connect(lambda: [self.on_setting_page_widget_max_show_gamehistory_lineedit_editingFinished(), self.setting_page_frame.hide()])
        
        
        self.setting_page_frame.hide()
    
    def on_switch_button_clicked(self, checked):
        if self.sender() == self.setting_page_widget_showgui_switchbutton:
            self.settings_changed_signal.emit(('show_gui_when_startup', checked))
        elif self.sender() == self.setting_page_widget_dragwin_switchbutton:
            self.settings_changed_signal.emit(('enable_dragging', checked))
            
    def edit_hotkey(self):
        # 自定义快捷键
        self.setting_page_widget_show_win_button.setText('请输入')
        threading.Thread(target=self.wait_keyboard, daemon=True).start()

    @staticmethod
    def on_key_event(event):
        return event.name
    
    def on_hotkey_changed(self, values):
        self.setting_page_widget_show_win_button.setText(values)
        self.settings.hotkey = values
        self.settings.save()
    
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
        
    def toggle_max_restore(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def set_theme(self, themeFile=":themes/Themes/theme.qss"):
        qfile = QFile(themeFile)
        qfile.open(QIODeviceBase.OpenModeFlag.ReadOnly | QIODeviceBase.OpenModeFlag.Text)
        stream = QTextStream(qfile)
        style = stream.readAll()
        self.setStyleSheet(style)

    def resizeEvent(self, event: QResizeEvent, /):
        super().resizeEvent(event)

    def mouseMoveEvent(self, event: QEvent, /):
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.mouse_start_pos)

    def mouseReleaseEvent(self, event: QEvent, /):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def leaveEvent(self, event):
        # 当鼠标离开窗口区域
        self.setCursor(Qt.CursorShape.ArrowCursor)
        # self.cursor_signal.emit('out of window')

    def set_resize_cursor(self, location):
        self.location = location
        self.setCursor(self.get_cursor_shape(location))
        if self.resize_dragging or self.dragging:
            self.resize_transparent_window()

    def resize_transparent_window(self):
        topleft_x = self.mapToGlobal(QPoint(0, 0)).x()
        topleft_y = self.mapToGlobal(QPoint(0, 0)).y()
        botright_x = self.mapToGlobal(QPoint(self.geometry().width(), self.geometry().height())).x()
        botright_y = self.mapToGlobal(QPoint(self.geometry().width(), self.geometry().height())).y()
        event_x, event_y = self.mouse.position
        if self.location == 'topleft' and self.resize_dragging:
            self.setGeometry(min(event_x, botright_x - self.minimumSize().width()), min(event_y, botright_y - self.minimumSize().height()),
                             max(botright_x - event_x, self.minimumSize().width()), max(botright_y - event_y, self.minimumSize().height()))
        elif self.location == 'topright' and self.resize_dragging:
            self.setGeometry(topleft_x, min(event_y, botright_y - self.minimumSize().height()),
                             max(event_x - topleft_x, self.minimumSize().width()), max(botright_y - event_y, self.minimumSize().height()))
        elif self.location == 'botright' and self.resize_dragging:
            self.setGeometry(topleft_x, topleft_y,
                             max(abs(event_x - topleft_x), self.minimumSize().width()), max(abs(event_y - topleft_y), self.minimumSize().height()))
        elif self.location == 'botleft' and self.resize_dragging:
            self.setGeometry(min(event_x, botright_x - self.minimumSize().width()), topleft_y,
                             max(abs(botright_x - event_x), self.minimumSize().width()), max(abs(event_y - topleft_y), self.minimumSize().height()))
        elif self.location == 'left' and self.resize_dragging:
            self.setGeometry(min(event_x, botright_x - self.minimumSize().width()), topleft_y,
                             max(abs(botright_x - event_x), self.minimumSize().width()), self.size().height())
        elif self.location == 'top' and self.resize_dragging:
            self.setGeometry(topleft_x, min(event_y, (botright_y - self.minimumSize().height())),
                             self.size().width(), max(botright_y - event_y, self.minimumSize().height()))
        elif self.location == 'right' and self.resize_dragging:
            self.setGeometry(topleft_x, topleft_y,
                             max(abs(event_x - topleft_x), self.minimumSize().width()), self.size().height())
        elif self.location == 'bot' and self.resize_dragging:
            self.setGeometry(topleft_x, topleft_y,
                             self.size().width(), max(abs(event_y - topleft_y), self.minimumSize().height()))
        elif self.location == 'normal' and self.dragging:
            self.move(event_x - self.mouse_start_pos.x(), event_y - self.mouse_start_pos.y())

    def mousePressEvent(self, event: QEvent, /):
        if event.button() == Qt.MouseButton.LeftButton and self.location == 'normal':
            self.mouse_start_pos = event.globalPosition().toPoint() - self.pos()
            self.dragging = True
        elif event.button() == Qt.MouseButton.LeftButton and self.location != 'normal':
            self.resize_dragging = True

    def mouseReleaseEvent(self, event: QEvent, /):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.resize_dragging = False

    def mouse_listening(self):
        self.listener = Listener(on_move=self.on_mouse_move, on_click=self.on_mouse_click)
        self.listener.start()

    def on_mouse_click(self, x, y, button, pressed):
        if button == button.left and not pressed:
            self.dragging = False
            self.resize_dragging = False

    def on_mouse_move(self, x, y):
        try:
            if self.isActiveWindow():
                topleft_x = self.mapToGlobal(QPoint(0, 0)).x()
                topleft_y = self.mapToGlobal(QPoint(0, 0)).y()
                botright_x = self.mapToGlobal(QPoint(self.geometry().width(), self.geometry().height())).x()
                botright_y = self.mapToGlobal(QPoint(self.geometry().width(), self.geometry().height())).y()
                if topleft_x - self.edge_size < x < topleft_x + self.edge_size and topleft_y - self.edge_size < y < topleft_y + self.edge_size:
                    self.cursor_signal.emit('topleft')
                elif botright_x - self.edge_size < x < botright_x + self.edge_size and topleft_y - self.edge_size < y < topleft_y + self.edge_size:
                    self.cursor_signal.emit('topright')
                elif botright_x - self.edge_size < x < botright_x + self.edge_size and botright_y - self.edge_size < y < botright_y + self.edge_size:
                    self.cursor_signal.emit('botright')
                elif topleft_x - self.edge_size < x < topleft_x + self.edge_size and botright_y - self.edge_size < y < botright_y + self.edge_size:
                    self.cursor_signal.emit('botleft')
                elif topleft_x - self.edge_size < x < topleft_x + self.edge_size and topleft_y + self.edge_size < y < botright_y - self.edge_size:
                    self.cursor_signal.emit('left')
                elif topleft_x + self.edge_size < x < botright_x - self.edge_size and topleft_y - self.edge_size < y < topleft_y + self.edge_size:
                    self.cursor_signal.emit('top')
                elif botright_x - self.edge_size < x < botright_x + self.edge_size and topleft_y + self.edge_size < y < botright_y - self.edge_size:
                    self.cursor_signal.emit('right')
                elif topleft_x + self.edge_size < x < botright_x - self.edge_size and botright_y - self.edge_size < y < botright_y + self.edge_size:
                    self.cursor_signal.emit('bot')
                elif topleft_x + self.edge_size < x < botright_x - self.edge_size and topleft_y + self.edge_size < y < botright_y - self.edge_size:
                    self.cursor_signal.emit('normal')
                else:
                    self.cursor_signal.emit('out of window')
        except:
            pass

    @staticmethod
    def get_cursor_shape(edge):
        """根据边缘方向返回对应光标形状"""
        cursor = {
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top": Qt.CursorShape.SizeVerCursor,
            "bot": Qt.CursorShape.SizeVerCursor,
            "topleft": Qt.CursorShape.SizeFDiagCursor,
            "topright": Qt.CursorShape.SizeBDiagCursor,
            "botleft": Qt.CursorShape.SizeBDiagCursor,
            "botright": Qt.CursorShape.SizeFDiagCursor
            }.get(edge, Qt.CursorShape.ArrowCursor)
        return cursor

    def paintEvent(self, event, /):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. 绘制主体背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(243, 243, 243))
        painter.drawRoundedRect(self.rect(), 10, 10)

        # 2. 绘制黑色边框
        pen = QPen(QColor(0, 0, 0, 100))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # 绘制矩形内缩 0.5 像素，确保线条完全在窗口内部
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(rect, 10, 10)


class MmrWindow(QMainWindow):
    
    gui_reload_signal = Signal(tuple)
    settings_changed_signal = Signal(tuple)
    
    def __init__(self, now_availiable_id, civilization_icon_dic, rank_icon_dic, window_location, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.now_availiable_id = now_availiable_id
        self.civilization_icon_dic = civilization_icon_dic
        self.rank_icon_dic = rank_icon_dic
        self.enable_dragging = False
        self.resize(965, 190)
        self.window_location = window_location
        self.set_mmr_rank_map()
        self.gui_reload_signal.connect(self.gui_reload)
        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(300000)
        self.hide_timer.timeout.connect(self.hide)
        self.setupUI()

    def player_icon(self, civilization):
        # 根据文明返回图标
        pixmap = QPixmap()
        pixmap.loadFromData(self.civilization_icon_dic.get(civilization))
        player_icon = QGraphicsScene()
        icon = pixmap.scaled(36, 18)
        player_icon.addPixmap(icon)
        player_icon.setSceneRect(0, 0, 36, 18)
        return player_icon
    
    def set_mmr_rank_map(self):
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
        if pixmap.isNull():
            return
        rank_icon = QGraphicsScene()
        icon = pixmap.scaled(26, 40)
        rank_icon.addPixmap(icon)
        rank_icon.setSceneRect(0, 0, 26, 40)
        return rank_icon
    
    def setupUI(self):
        # 初始化主界面
        self.uiwidget = QWidget(parent=self)
        self.uiwidget.setGeometry(0, 0, 965, 190)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setWindowTitle('Aoe4mmr')
        if not self.window_location:
            screen = QApplication.primaryScreen()
            screen_geo = screen.geometry()
            new_x = (screen_geo.width() - self.width()) // 2
            location = (new_x, 0)
        else:
            location = self.window_location
        self.move(location[0], location[1])
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
        self.player1.set_text_color("#CC9F4A")
        self.player1.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.player2 = OutlinedLabel(parent=self.uiwidget)
        self.player2.setObjectName('player2')
        self.player2.setGeometry(80, 80, 240, 30)
        self.player2.setText('player2')
        self.player2.set_text_color("#CC9F4A")
        self.player2.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.player3 = OutlinedLabel(parent=self.uiwidget)
        self.player3.setObjectName('player3')
        self.player3.setGeometry(80, 120, 240, 30)
        self.player3.setText('player3')
        self.player3.set_text_color("#CC9F4A")
        self.player3.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.player4 = OutlinedLabel(parent=self.uiwidget)
        self.player4.setObjectName('player4')
        self.player4.setGeometry(80, 160, 240, 30)
        self.player4.setText('player4')
        self.player4.set_text_color("#CC9F4A")
        self.player4.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.player1mmr = OutlinedLabel(parent=self.uiwidget)
        self.player1mmr.setObjectName('player1mmr')
        self.player1mmr.set_text_color("#CC9F4A")
        self.player1mmr.setGeometry(330, 38, 120, 30)
        self.player1mmr.setText('1500')

        self.player2mmr = OutlinedLabel(parent=self.uiwidget)
        self.player2mmr.setObjectName('player2mmr')
        self.player2mmr.set_text_color("#CC9F4A")
        self.player2mmr.setGeometry(330, 78, 120, 30)
        self.player2mmr.setText('1500')

        self.player3mmr = OutlinedLabel(parent=self.uiwidget)
        self.player3mmr.setObjectName('player3mmr')
        self.player3mmr.set_text_color("#CC9F4A")
        self.player3mmr.setGeometry(330, 118, 120, 30)
        self.player3mmr.setText('1500')

        self.player4mmr = OutlinedLabel(parent=self.uiwidget)
        self.player4mmr.setObjectName('player4mmr')
        self.player4mmr.set_text_color("#CC9F4A")
        self.player4mmr.setGeometry(330, 158, 120, 30)
        self.player4mmr.setText('1500')

        self.player5 = OutlinedLabel(parent=self.uiwidget)
        self.player5.setObjectName('player5')
        self.player5.setGeometry(650, 40, 240, 30)
        self.player5.setText('player5')
        self.player5.set_text_color("#CC9F4A")
        self.player5.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.player6 = OutlinedLabel(parent=self.uiwidget)
        self.player6.setObjectName('player6')
        self.player6.setGeometry(650, 80, 240, 30)
        self.player6.set_text_color("#CC9F4A")
        self.player6.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player6.setText('player6')

        self.player7 = OutlinedLabel(parent=self.uiwidget)
        self.player7.setObjectName('player7')
        self.player7.setGeometry(650, 120, 240, 30)
        self.player7.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player7.setText('player7')
        self.player7.set_text_color("#CC9F4A")

        self.player8 = OutlinedLabel(parent=self.uiwidget)
        self.player8.setObjectName('player8')
        self.player8.setGeometry(650, 160, 240, 30)
        self.player8.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player8.setText('player8')
        self.player8.set_text_color("#CC9F4A")

        self.player5mmr = OutlinedLabel(parent=self.uiwidget)
        self.player5mmr.setObjectName('player5mmr')
        self.player5mmr.setGeometry(510, 38, 120, 30)
        self.player5mmr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player5mmr.setText('1500')
        self.player5mmr.set_text_color("#CC9F4A")

        self.player6mmr = OutlinedLabel(parent=self.uiwidget)
        self.player6mmr.setObjectName('player6mmr')
        self.player6mmr.setGeometry(510, 78, 120, 30)
        self.player6mmr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player6mmr.setText('1500')
        self.player6mmr.set_text_color("#CC9F4A")

        self.player7mmr = OutlinedLabel(parent=self.uiwidget)
        self.player7mmr.setObjectName('player7mmr')
        self.player7mmr.setGeometry(510, 118, 120, 30)
        self.player7mmr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player7mmr.setText('1500')
        self.player7mmr.set_text_color("#CC9F4A")

        self.player8mmr = OutlinedLabel(parent=self.uiwidget)
        self.player8mmr.setObjectName('player8mmr')
        self.player8mmr.setGeometry(510, 158, 120, 30)
        self.player8mmr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.player8mmr.setText('1500')
        self.player8mmr.set_text_color("#CC9F4A")

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

    def gui_reload(self, data):
        # 获取到新数据时，刷新主界面或设置窗口
        map_name, game_id, game_mode, reload_data, kind = data
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

    def islongname(self, string):
        
        def has_chinese(string):
            # 判断游戏ID是否包含中文
            pattern = '[\u4e00-\u9fa5]'
            result = re.search(pattern, string)
            if result is not None:
                return True
            else:
                return False
        # 如果游戏ID包含中文，则在主界面仅显示ID前10个字符，否则显示25个
        language = has_chinese(string)
        if language:
            if len(string) > 10:
                string = string[0:10] + '...'
        else:
            if len(string) > 25:
                string = string[0:25] + '...'
        return string
    
    def checkplayer(self, player_id):
        # 检查该选手是否玩家本人
        return player_id == self.now_availiable_id
    
    def close(self):
        self.hide()
        
    def mousePressEvent(self, event: QEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.enable_dragging:
            self.mouse_start_pos = event.globalPosition().toPoint() - self.pos()
            self.dragging = True

    def mouseMoveEvent(self, event: QEvent):
        if self.dragging and self.enable_dragging:
            self.move(event.globalPosition().toPoint() - self.mouse_start_pos)

    def mouseReleaseEvent(self, event: QEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.resize_dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.settings_changed_signal.emit(('window_location', self.pos()))

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
        

class SwitchButton(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent=None, bg_color="#44475a", active_color="#06B75B", handle_color="#f8f8f2"):
        super().__init__(parent)
        self._checked = False
        self._offset = 2

        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(160)
        self._animation.setEasingCurve(QEasingCurve.InOutQuad)

        # 颜色
        self.bg_color = QColor(bg_color)
        self.active_color = QColor(active_color)
        self.handle_color = QColor(handle_color)

        # 推荐的最小尺寸，保证控件可见
        self.setMinimumSize(40, 20)

    # 鼠标切换
    def mousePressEvent(self, event):
        if not self.isEnabled():
            return
        self.setChecked(not self._checked)
        super().mousePressEvent(event)

    # 绘制
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = max(1, self.width())
        h = max(1, self.height())

        # 背景颜色
        if not self.isEnabled():
            bg = QColor("#777")
        else:
            bg = self.active_color if self._checked else self.bg_color

        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(QRect(0, 0, w, h), h / 2, h / 2)

        # 滑块尺寸与位置（夹定 offset）
        diameter = max(1, h - 4)            # 直径
        min_off = 2
        max_off = max(min_off, w - diameter - 2)
        off = max(min_off, min(self._offset, max_off))

        painter.setBrush(self.handle_color if self.isEnabled() else QColor("#ccc"))
        painter.drawEllipse(int(off), 2, int(diameter), int(diameter))

    # Property 用于动画
    def getOffset(self):
        return int(self._offset)

    def setOffset(self, value):
        self._offset = int(value)
        self.update()

    offset = Property(int, getOffset, setOffset)

    # API
    def isChecked(self):
        return self._checked

    def setChecked(self, state: bool, animated: bool = True):
        if self._checked == state:
            return
        self._checked = state
        self.toggled.emit(self._checked)

        # 计算目标位置（夹定，避免越界）
        w = self.width()
        h = self.height()
        diameter = max(1, h - 4)
        min_off = 2
        max_off = max(min_off, w - diameter - 2)
        end = max_off if self._checked else min_off

        # 如果控件还没布局好（宽度可能为0），不要做动画，直接设置位置，
        # resizeEvent 会在显示时把位置矫正到正确值
        if animated and w > 0:
            self._animation.stop()
            self._animation.setStartValue(self._offset)
            self._animation.setEndValue(end)
            self._animation.start()
        else:
            # 直接跳到最终位置（无动画）
            self._animation.stop()
            self.setOffset(end)

    # 窗口大小改变时保持滑块在正确端点
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 立即修正位置（不做动画）
        w = self.width()
        h = self.height()
        diameter = max(1, h - 4)
        min_off = 2
        max_off = max(min_off, w - diameter - 2)
        self._offset = max_off if self._checked else min_off
        self.update()

    def sizeHint(self):
        return QSize(40, 20)
    
    
class CustomMessageBox(QDialog):
    def __init__(self, title='提示', message='', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.main_layout = QVBoxLayout(self)
        self.add_title(title)
        self.add_message(message)
        self.setFixedSize(300, 180)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.title_widget)
        self.main_layout.addWidget(self.message_widget)
        self.show()

    def add_title(self, title):
        self.title_widget = QWidget(parent=self)
        self.title_widget.setObjectName('title_widget')
        self.title_widget.setMinimumHeight(25)
        self.title_widget.setMaximumHeight(25)
        self.title_widget_layout = QHBoxLayout(self.title_widget)
        self.title_widget_layout.setContentsMargins(8, 1, 1, 2)
        self.title_label = QLabel(self.title_widget, text=title)
        self.title_label.setFixedSize(100, 20)
        self.close_button = QPushButton(self.title_widget)
        icon = QIcon()
        icon_file = ":images/icons/icon_close.png"
        icon.addFile(icon_file, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.close_button.setIcon(icon)
        self.close_button.setObjectName('close_button')
        self.close_button.setFixedSize(20, 20)
        self.close_button.clicked.connect(self.reject)
        self.title_widget_layout.addWidget(self.title_label)
        self.title_widget_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.title_widget_layout.addWidget(self.close_button)
        
    def add_message(self, message):
        self.message_widget = QWidget(parent=self)
        self.message_widget_layout = QVBoxLayout(self.message_widget)
        self.message_widget_layout.setContentsMargins(10, 5, 10, 25)
        self.message_layout = QHBoxLayout()
        self.message_layout.setContentsMargins(0, 0, 0, 0)
        self.message_layout.setSpacing(20)
        self.message_icon = QLabel(self.message_widget)
        icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation)
        self.message_icon.setPixmap(icon.pixmap(40, 40))
        self.message_icon.setScaledContents(True)
        self.message_icon.setFixedSize(40, 40)
        
        self.message_label = QLabel(self.message_widget, text=message)
        self.message_label.setMinimumWidth(150)
        self.message_label.setWordWrap(True)
        self.message_layout.addStretch(1)
        self.message_layout.addWidget(self.message_icon)
        self.message_layout.addWidget(self.message_label)
        self.message_layout.addStretch(1)

        self.message_button_layout = QHBoxLayout()
        self.message_confirm_button = QPushButton(self.message_widget, text='确定')
        self.message_confirm_button.setFixedSize(100, 30)
        self.message_confirm_button.setObjectName('message_confirm_button')
        self.message_confirm_button.clicked.connect(self.accept)
        self.message_cancle_button = QPushButton(self.message_widget, text='取消')
        self.message_cancle_button.setFixedSize(100, 30)
        self.message_cancle_button.setObjectName('message_cancle_button')
        self.message_cancle_button.clicked.connect(self.reject)
        self.message_button_layout.addWidget(self.message_confirm_button)
        self.message_button_layout.addWidget(self.message_cancle_button)
        self.message_widget_layout.addLayout(self.message_layout)
        self.message_widget_layout.addLayout(self.message_button_layout)
        