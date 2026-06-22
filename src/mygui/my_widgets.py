#!/usr/bin/python3
# Author: B_Snowflake
# Date: 2026/3/22

import re
import time
import pytz
import json
import urllib3
import requests
import threading
from rapidfuzz import fuzz
from datetime import datetime
from retrying import retry
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from collections import defaultdict


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LeftMenu(QWidget):
    def __init__(self, pages: QStackedWidget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("left_menu")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(15)
        self.toolbutton_dic = {}
        self.add_toolbutton("home_button", "主页", ":images/icons/cil-home.svg", 0)
        self.add_toolbutton("new_button", "新增", ":images/icons/cil-library-add.svg", 1)
        self.main_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        self.toolbutton_dic['home_button'][0].setChecked(True)
        self.pages = pages
        self.toolbutton_record = []
        self.record_offset_index = 0

    def add_toolbutton(self, objectname, text, icon, page_index):
        toolbutton = QToolButton(text=text, parent=self)
        toolbutton.setObjectName(objectname)
        toolbutton.setIcon(QIcon(icon))
        toolbutton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbutton.setFixedSize(50, 50)
        toolbutton.setIconSize(QSize(24, 24))
        toolbutton.clicked.connect(self.switch_page)
        toolbutton.setCheckable(True)
        self.toolbutton_dic[objectname] = (toolbutton, page_index)
        self.main_layout.addWidget(toolbutton)

    def switch_page(self, checked=None, sender=None, no_record=False):
        sender = sender if sender else self.sender() 
        if not no_record:
            if self.toolbutton_record.__len__() > 6:
                self.toolbutton_record = self.toolbutton_record[1:]
            if self.record_offset_index != 0:
                index = self.toolbutton_record.__len__() + self.record_offset_index
                self.toolbutton_record[0:index]
            self.record_offset_index = 0
            self.toolbutton_record.append(sender)
        else:
            sender.setChecked(True)
        for objectname, values in self.toolbutton_dic.items():
            button, page_index = values
            if button != sender:
                button.setChecked(False)
            else:
                # button.setChecked(True)
                index = page_index
        self.pages.setCurrentIndex(index)


class MenuPage(QStackedWidget):
    detail_signal = Signal(dict)
    apply_signal = Signal(tuple)
    mark_signal = Signal(tuple)
    add_new_game_history_signal = Signal(list)
    
    def __init__(self, add_new_account_signal, settings_changed_signal, max_show_gamehistory, max_accounts, 
                 picked_profile_id, civilization_icon_dic, map_dic, database_queue, player_mark_dic, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.home_page = QWidget()
        self.new_page = QWidget()
        self.applyed_player_info = None
        self.civilization_icon_dic = civilization_icon_dic
        self.player_mark_dic = player_mark_dic
        self.max_accounts = max_accounts
        self.picked_profile_id = picked_profile_id
        self.settings_changed_signal = settings_changed_signal
        self.map_dic = map_dic
        self.database_queue = database_queue
        self.max_show_gamehistory = max_show_gamehistory
        self.addWidget(self.home_page)
        self.addWidget(self.new_page)  
        self.set_home_page()
        self.set_new_page()
        self.search_player_details = PlayerDetail(self.detail_signal, self.add_new_game_history_signal)
        self.add_new_game_history_signal.connect(self.add_new_game_history)
        self.mark_signal.connect(self.mark_player)
        self.detail_signal.connect(self.reload_player_details)
        self.apply_signal.connect(self.apply_player_details)
        self.add_new_account_signal = add_new_account_signal
        self.game_history_widgets_collection = {}
    
    def apply_player_details(self, player_info):
        profile_id, profile_name = player_info
        self.applyed_player_info = player_info
        self.search_player_details.get_detail(profile_id)
    
    def mark_player(self, data):
        profile_id, flag, reason = data
        create_time = int(time.time())
        self.player_mark_dic[profile_id] = (flag, reason, create_time)
        sql = """INSERT INTO player_mark (profile_id, flag, reason, create_time) VALUES (?, ?, ?, ?) ON CONFLICT(profile_id) 
        DO UPDATE SET flag = excluded.flag, reason = excluded.reason"""
        self.database_queue.put((sql, (profile_id, flag, reason, create_time)))
    
    def reload_player_details(self, data):
        def add_data_to_table(data_list, tablewidget):
            data_list = data_list[0:4]
            tablewidget.setRowCount(0)
            tablewidget.setRowCount(len(data_list))
            for row, row_data in enumerate(data_list):
                for col, value in enumerate(row_data):
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignCenter)   # 水平+垂直居中
                    tablewidget.setItem(row, col, item)
        
        try:
            player_id = data['name']
            avatar = data['avatars']['full']
            country = data['country']
            if avatar:
                avatar_pixmap = QPixmap()
                avatar_pixmap.loadFromData(avatar)
                self.player_detail_icon.setPixmap(avatar_pixmap.scaled(80, 80))
                self.player_detail_icon.show()
            else:
                self.player_detail_icon.hide()
            if country:
                country_pixmap = QPixmap()
                country_pixmap.loadFromData(country)
                self.player_detail_icon_widget_country_icon.setPixmap(country_pixmap.scaled(40, 27))
                self.player_detail_icon_widget_country_icon.show()
            else:
                self.player_detail_icon_widget_country_icon.hide()
            self.player_detail_icon_widget_player_name.setText(player_id)
            self.player_detail_icon_widget_player_name.show()
        except Exception as e:
            print('error when get player info', e)
        mode_dic = defaultdict(list)
        nodata = [("", "未找到相关数据", "")]
        for keys in data['modes']:           
            if keys.startswith("qm_"):
                mode_dic['qm_data'].append(keys)
            elif keys.endswith("_elo"):
                mode_dic['rm_elo_data'].append(keys)
            elif "rm_team" in keys:
                mode_dic['rm_team_data'].append(keys)
            elif "rm_solo" in keys:
                mode_dic['rm_solo_data'].append(keys)
        try:
            if mode_dic.get('qm_data'):   
                qm_data = [(value.replace('qm_', ''), data['modes'][value]['rating'], data['modes'][value]['win_rate']) for value in mode_dic['qm_data']]
            else:
                qm_data = nodata
                print('no qm_data')
        except Exception as e:
            qm_data = nodata
            print('error when get qm_data', e)
        add_data_to_table(qm_data, self.player_detail_qm_widget_table)
        self.player_detail_qm_widget.show()
        try:
            if mode_dic.get('rm_team_data'):
                rm_team_data = [(season['season'], season['rating'], season['win_rate']) for season in data['modes']['rm_team']['previous_seasons']]
                try:
                    now_season_rm_team_data = (data['modes']['rm_team']['season'], data['modes']['rm_team']['rating'], data['modes']['rm_team']['win_rate'])
                    rm_team_data.insert(0, now_season_rm_team_data)
                except:
                    pass
            else:
                rm_team_data = nodata
                print('no rm_team_data')
        except Exception as e:
            rm_team_data = nodata
            print('error when get rm_team_data', e)
        add_data_to_table(rm_team_data, self.player_detail_tm_rank_widget_table)
        self.player_detail_tm_rank_widget.show()
        try:
            if mode_dic.get('rm_solo_data'):
                rm_solo_data = [(season['season'], season['rating'], season['win_rate']) for season in data['modes']['rm_solo']['previous_seasons']] 
                try:  
                    now_season_rm_solo_data = (data['modes']['rm_solo']['season'], data['modes']['rm_solo']['rating'], data['modes']['rm_solo']['win_rate'])
                    rm_solo_data.insert(0, now_season_rm_solo_data)
                except:
                    pass
            else:
                rm_solo_data = nodata
                print('no rm_solo_data')
        except Exception as e:
            rm_solo_data = nodata
            print('error when get rm_solo_data', e)
        add_data_to_table(rm_solo_data, self.player_detail_solo_rank_widget_table)
        self.player_detail_solo_rank_widget.show()
        try:
            if mode_dic.get('rm_elo_data'):
                rm_elo_data = [(value.replace('rm_', ''), data['modes'][value]['rating'], data['modes'][value]['win_rate']) for value in mode_dic['rm_elo_data']]
            else:
                rm_elo_data = nodata
                print('no rm_elo_data')
        except Exception as e:
            rm_elo_data = nodata
            print('error when get rm_elo_data', e)
        add_data_to_table(rm_elo_data, self.player_detail_rank_matchmaking_widget_table)
        self.player_detail_rank_matchmaking_widget.show()
        self.add_new_account_button.show() if self.search_completer.text() and self.player_account_widget_combobox.count() < self.max_accounts else self.add_new_account_button.hide()
        
    def add_new_game_history(self, data_list):
        self.player_account_widget_combobox.setEnabled(True)
        for data in data_list[0:self.max_show_gamehistory]:
            if data[1] in self.game_history_widgets_collection.keys():
                self.game_history_widgets_collection[data[1]].deleteLater()
            game_history_widgets = GameHistoryWidget(self.civilization_icon_dic, self.map_dic, data, self.apply_signal, self.mark_signal, self.player_mark_dic, parent=self.player_game_history_widget)
            game_id = game_history_widgets.game_id
            self.game_history_widgets_collection[game_id] = game_history_widgets
            self.player_game_history_widget_layout.addWidget(game_history_widgets)
        self.sort_game_history_widgets()
            
    def sort_game_history_widgets(self):
        # 1. 取排序后的 key
        game_history_list = sorted((int(k) for k in self.game_history_widgets_collection.keys()), reverse=True)
        # 2. 暂存 widget
        widgets = [self.game_history_widgets_collection[i] for i in game_history_list]
        # 3. 清空 layout（关键）
        while self.player_game_history_widget_layout.count():
            item = self.player_game_history_widget_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        # 4. 按顺序重新加入
        for w in widgets:
            self.player_game_history_widget_layout.addWidget(w)
            
    @staticmethod
    def set_by_data(combo, target):
        index = combo.findData(target) if combo.findData(target) != -1 else 0
        return index
    
    def set_home_page(self):
        self.home_page_layout = QVBoxLayout(self.home_page)
        self.player_account_widget = QTableWidget(self.home_page)
        self.player_account_widget_layout = QHBoxLayout(self.player_account_widget)
        self.player_account_widget_label = QLabel(self.player_account_widget, text="我的账户：")
        self.player_account_widget_combobox = QComboBox(self.player_account_widget)
        self.player_account_widget_combobox.setMaximumWidth(250)
        self.player_account_widget_combobox.currentIndexChanged.connect(self.on_player_account_widget_combobox_currentIndexChanged)
        
        self.player_game_history_widget_scrollarea = QScrollArea(self.home_page)
        self.player_game_history_widget_scrollarea.setViewportMargins(0, 0, 0, 0)
        self.player_game_history_widget = QWidget(self.home_page)
   
        self.player_game_history_widget_scrollarea.setWidgetResizable(True)
        self.player_game_history_widget_scrollarea.setFrameShape(QFrame.NoFrame)
        self.player_game_history_widget_layout = QVBoxLayout(self.player_game_history_widget) 
        self.player_game_history_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.player_game_history_widget_layout.setSpacing(30)
        self.player_game_history_widget_scrollarea.setWidget(self.player_game_history_widget)
        
        self.player_account_widget_layout.addWidget(self.player_account_widget_combobox)
        
        self.home_page_layout.addWidget(self.player_account_widget_label)
        self.home_page_layout.addWidget(self.player_account_widget_combobox)
        self.home_page_layout.addWidget(self.player_game_history_widget_scrollarea)

    def on_player_account_widget_combobox_currentIndexChanged(self, index):
        if index != -1:
            self.player_account_widget_combobox.setEnabled(False)
            profile_id = self.player_account_widget_combobox.currentData()
            for key, value in self.game_history_widgets_collection.items():
                value.deleteLater()
            self.game_history_widgets_collection.clear()
            self.search_player_details.get_game_history(profile_id)
            self.settings_changed_signal.emit(('picked_profile_id', profile_id))

    def add_my_accounts_to_combobox(self, data):
        self.player_account_widget_combobox.blockSignals(True)
        self.player_account_widget_combobox.clear()
        accounts = [(value.profile_name, value.profile_id) for key, value in data.items()]
        for profile_name, profile_id in accounts:
            self.player_account_widget_combobox.addItem(profile_name, profile_id)
        self.player_account_widget_combobox.setCurrentIndex(-1)
        self.player_account_widget_combobox.blockSignals(False)
        picked_profile_id = self.applyed_player_info[0] if self.applyed_player_info else self.picked_profile_id
        self.player_account_widget_combobox.setCurrentIndex(self.set_by_data(self.player_account_widget_combobox, picked_profile_id))
        self.applyed_player_info = None
            
    def set_new_page(self):
        
        def set_player_detail_icon_widget():
            self.player_detail_icon_widget = QWidget(parent=self.player_detail_widget, ObjectName="player_detail_icon_widget")
            self.player_detail_icon_widget.setFixedSize(600, 80)
            self.player_detail_icon_widget_layout = QHBoxLayout(self.player_detail_icon_widget)
            self.player_detail_icon_widget_layout.setContentsMargins(0, 0, 0, 0)
            self.player_detail_icon_widget_layout.setSpacing(20)
            self.player_detail_icon = QLabel(self.player_detail_widget)
            self.player_detail_icon.setFixedSize(80, 80)
            self.player_detail_icon.setPixmap(QPixmap(":/images/icons/cil-contact.svg").scaled(80, 80))
            self.player_detail_icon.hide()
            self.player_detail_icon_widget_country_layout = QVBoxLayout()
            self.player_detail_icon_widget_country_layout.setContentsMargins(0, 0, 0, 5)
            self.player_detail_icon_widget_country_layout.setSpacing(10)
            self.player_detail_icon_widget_country_icon = QLabel(self.player_detail_widget)
            self.player_detail_icon_widget_country_icon.hide()
            
            self.player_detail_icon_widget_player_name = QLabel(parent=self.player_detail_widget, text="PlayerID", ObjectName="player_detail_icon_widget_player_name")
            self.player_detail_icon_widget_player_name.hide()
            self.player_detail_icon_widget_country_layout.addWidget(self.player_detail_icon_widget_player_name)
            self.player_detail_icon_widget_country_layout.addStretch(1)
            self.player_detail_icon_widget_country_layout.addWidget(self.player_detail_icon_widget_country_icon)
             
            self.player_detail_icon_widget_layout.addWidget(self.player_detail_icon)
            self.player_detail_icon_widget_layout.addLayout(self.player_detail_icon_widget_country_layout)
            
        def set_player_deatil_solo_rank_widget():
            self.player_detail_solo_rank_widget = QWidget(parent=self.player_detail_widget, ObjectName="player_detail_solo_rank_widget")
            self.player_detail_solo_rank_widget.hide()
            self.player_detail_solo_rank_widget_layout = QVBoxLayout(self.player_detail_solo_rank_widget)
            self.player_detail_solo_rank_widget_layout.setSpacing(10)
            self.player_detail_solo_rank_widget_label = QLabel(parent=self.player_detail_solo_rank_widget, text="单人排名", ObjectName="player_detail_solo_rank_widget_label")
            self.player_detail_solo_rank_widget_table = QTableWidget(self.player_detail_solo_rank_widget, ObjectName="player_detail_solo_rank_widget_table")
            self.player_detail_solo_rank_widget_table.verticalHeader().setVisible(False)
            self.player_detail_solo_rank_widget_table.setFrameShape(QFrame.NoFrame)
            self.player_detail_solo_rank_widget_table.setShowGrid(False)
            self.player_detail_solo_rank_widget_table.setColumnCount(3)
            self.player_detail_solo_rank_widget_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.player_detail_solo_rank_widget_table.setHorizontalHeaderLabels(["赛季", "分值", "胜率"])

            self.player_detail_solo_rank_widget_layout.addWidget(self.player_detail_solo_rank_widget_label)
            self.player_detail_solo_rank_widget_layout.addWidget(self.player_detail_solo_rank_widget_table)
            
        def set_player_detail_tm_rank_widget():
            self.player_detail_tm_rank_widget = QWidget(parent=self.player_detail_widget, ObjectName="player_detail_tm_rank_widget")
            self.player_detail_tm_rank_widget.hide()
            self.player_detail_tm_rank_widget_layout = QVBoxLayout(self.player_detail_tm_rank_widget)
            self.player_detail_tm_rank_widget_layout.setSpacing(10)
            self.player_detail_tm_rank_widget_label = QLabel(parent=self.player_detail_tm_rank_widget, text="组队排名", ObjectName="player_detail_tm_rank_widget_label")
            self.player_detail_tm_rank_widget_table = QTableWidget(self.player_detail_tm_rank_widget, ObjectName="player_detail_tm_rank_widget_table")
            self.player_detail_tm_rank_widget_table.verticalHeader().setVisible(False)
            self.player_detail_tm_rank_widget_table.setFrameShape(QFrame.NoFrame)
            self.player_detail_tm_rank_widget_table.setShowGrid(False)
            self.player_detail_tm_rank_widget_table.setColumnCount(3)
            self.player_detail_tm_rank_widget_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.player_detail_tm_rank_widget_table.setHorizontalHeaderLabels(["赛季", "分值", "胜率"])
            
            self.player_detail_tm_rank_widget_layout.addWidget(self.player_detail_tm_rank_widget_label)
            self.player_detail_tm_rank_widget_layout.addWidget(self.player_detail_tm_rank_widget_table)
           
        def set_player_detail_qm_widget():
            self.player_detail_qm_widget = QWidget(parent=self.player_detail_widget, ObjectName="player_detail_qm_widget")
            self.player_detail_qm_widget.hide()
            self.player_detail_qm_widget_layout = QVBoxLayout(self.player_detail_qm_widget)
            self.player_detail_qm_widget_layout.setSpacing(10)
            self.player_detail_qm_widget_label = QLabel(parent=self.player_detail_qm_widget, text="快速比赛", ObjectName="player_detail_qm_widget_label")
            self.player_detail_qm_widget_table = QTableWidget(self.player_detail_qm_widget, ObjectName="player_detail_qm_widget_table")
            self.player_detail_qm_widget_table.verticalHeader().setVisible(False)
            self.player_detail_qm_widget_table.setFrameShape(QFrame.NoFrame)
            self.player_detail_qm_widget_table.setShowGrid(False)
            self.player_detail_qm_widget_table.setColumnCount(3)
            self.player_detail_qm_widget_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.player_detail_qm_widget_table.setHorizontalHeaderLabels(["模式", "分值", "胜率"])
            
            self.player_detail_qm_widget_layout.addWidget(self.player_detail_qm_widget_label)
            self.player_detail_qm_widget_layout.addWidget(self.player_detail_qm_widget_table)
            
        def set_player_detail_rank_matchmaking_widget():
            self.player_detail_rank_matchmaking_widget = QWidget(parent=self.player_detail_widget, ObjectName="player_detail_rank_matchmaking_widget")
            self.player_detail_rank_matchmaking_widget.hide()
            self.player_detail_rank_matchmaking_widget_layout = QVBoxLayout(self.player_detail_rank_matchmaking_widget)
            self.player_detail_qm_widget_layout.setSpacing(10)
            self.player_detail_rank_matchmaking_widget_label = QLabel(parent=self.player_detail_rank_matchmaking_widget, text="排名ELO", ObjectName="player_detail_rank_matchmaking_widget_label")
            self.player_detail_rank_matchmaking_widget_table = QTableWidget(self.player_detail_rank_matchmaking_widget, ObjectName="player_detail_rank_matchmaking_widget_table")
            self.player_detail_rank_matchmaking_widget_table.verticalHeader().setVisible(False)
            self.player_detail_rank_matchmaking_widget_table.setFrameShape(QFrame.NoFrame)
            self.player_detail_rank_matchmaking_widget_table.setShowGrid(False)
            self.player_detail_rank_matchmaking_widget_table.setColumnCount(3)
            self.player_detail_rank_matchmaking_widget_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.player_detail_rank_matchmaking_widget_table.setHorizontalHeaderLabels(["模式", "ELO", "胜率"])
            
            self.player_detail_rank_matchmaking_widget_layout.addWidget(self.player_detail_rank_matchmaking_widget_label)
            self.player_detail_rank_matchmaking_widget_layout.addWidget(self.player_detail_rank_matchmaking_widget_table)
            
        self.new_page_layout = QVBoxLayout(self.new_page)
        self.search_completer = SearchCompleter(parent=self.new_page, PlaceholderText="请输入玩家名称", apply_signal=self.apply_signal)
        self.search_completer.setMinimumHeight(30)
        self.player_detail_widget = QWidget(self.new_page)
        self.add_new_account_button = QPushButton(parent=self.player_detail_widget, text="添加至我的账号")
        self.add_new_account_button.clicked.connect(self.add_new_account)
        self.add_new_account_button.setFixedSize(120, 30)
        self.add_new_account_button.hide()
        self.player_detail_widget_layout = QVBoxLayout(self.player_detail_widget)
        self.player_detail_widget_rank_layout = QHBoxLayout()
        self.player_detail_widget_qm_layout = QHBoxLayout()
        self.player_detail_button_layout = QHBoxLayout()
        self.player_detail_button_layout.addStretch(1)
        self.new_page_layout.setContentsMargins(9, 0, 0, 9)
        self.player_detail_button_layout.addWidget(self.add_new_account_button)
        self.player_detail_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.player_detail_widget_layout.setSpacing(0)
        self.player_detail_widget_rank_layout.setContentsMargins(0, 0, 0, 0)
        self.player_detail_widget_qm_layout.setContentsMargins(0, 0, 0, 0)
        self.player_detail_button_layout.setContentsMargins(0, 0, 40, 0)
        
        set_player_detail_icon_widget()
        set_player_deatil_solo_rank_widget()
        set_player_detail_tm_rank_widget()
        set_player_detail_qm_widget()
        set_player_detail_rank_matchmaking_widget()
        
        self.player_detail_widget_rank_layout.addWidget(self.player_detail_solo_rank_widget)
        self.player_detail_widget_rank_layout.addWidget(self.player_detail_tm_rank_widget)
        self.player_detail_widget_qm_layout.addWidget(self.player_detail_rank_matchmaking_widget)
        self.player_detail_widget_qm_layout.addWidget(self.player_detail_qm_widget)
                
        self.player_detail_widget_layout.addWidget(self.player_detail_icon_widget)
        self.player_detail_widget_layout.addLayout(self.player_detail_widget_rank_layout)
        self.player_detail_widget_layout.addLayout(self.player_detail_widget_qm_layout)

        self.new_page_layout.addWidget(self.search_completer)
        self.new_page_layout.addWidget(self.player_detail_widget)
        self.new_page_layout.addLayout(self.player_detail_button_layout)
    
    def add_new_account(self):
        if self.applyed_player_info:
            self.add_new_account_signal.emit(self.applyed_player_info)
        
class SearchCompleter(QLineEdit):
    # 使用Listview和linedit编写的自定义搜索框，类似百度的效果
    search_signal = Signal(str, list)
    
    def __init__(self, parent=None, PlaceholderText=None, apply_signal=None):
        super().__init__(parent)
        self.focused_on = False
        self.setFrame(False)
        self.setPlaceholderText(PlaceholderText)
        self.apply_signal = apply_signal
        # 下拉建议列表
        self.suggestion_list = QListWidget()
        self.suggestion_list.setWindowFlags(Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.suggestion_list.setFocusPolicy(Qt.NoFocus)  # 明确不要焦点
        self.suggestion_list.setVisible(False)
        self.suggestions = []
        # self.textChanged.connect(self.show_suggestions)
        # 连接信号
        self.suggestion_list.itemClicked.connect(self.apply_suggestion)
        self.search_signal.connect(self.set_suggestions_list)
        self.search = PlayerSearch(self.search_signal)
        self.textChanged.connect(self.text_changed)
    
    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focused_on = True
        if self.suggestion_list.count() > 0:
            self.suggestion_list.show()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focused_on = False
        if self.suggestion_list.count() > 0:
            self.suggestion_list.hide()
        
    def text_changed(self, text):
        self.applyed = False
        if text:
            self.search.search(text)
            self.query_rs = []
            self.search_signal.emit(text, [])
        else:
            self.suggestion_list.hide()

    def set_suggestions_list(self, query, query_rs):
        if query and query == self.text():
            if len(query_rs) == 0:
                self.suggestions = ["正在检索，请稍候..."]
            else:
                self.suggestions = [f"{str(item[1])}     最后游戏时间：{str(item[2])}" for item in query_rs]
            self.query_rs = query_rs
            self.show_suggestions()

    def show_suggestions(self):
        """显示建议列表(如果窗口激活)"""
        # if self.on_focus.value:
        text = self.text()
        self.suggestion_list.clear()
        if not text:
            self.suggestion_list.hide()
            return
        for item in self.suggestions:
            self.suggestion_list.addItem(item)
        if self.suggestions and self.focused_on:
            # 定位下拉列表
            self.suggestion_list.move(self.mapToGlobal(self.rect().bottomLeft()))
            self.suggestion_list.setFixedWidth(self.width())
            self.suggestion_list.show()
            self.suggestion_list.setFocus()
        else:
            self.suggestion_list.hide()

    def apply_suggestion(self, item):
        """应用选中的建议"""
        if item.text() != "正在检索，请稍候..." and item.text() != "没有检索到相关ID":
            self.blockSignals(True)
            row = self.suggestion_list.currentRow()
            profile_id = str(self.query_rs[row][0])
            name = self.query_rs[row][1]
            self.apply_signal.emit((profile_id, name))
            self.suggestion_list.clear()
            self.setText(name)
            self.suggestion_list.hide()
            self.blockSignals(False)

    def keyPressEvent(self, event: QKeyEvent):
        """处理键盘事件"""
        if self.suggestion_list.isVisible():
            if event.key() == Qt.Key.Key_Down:
                self.suggestion_list.setCurrentRow(
                    min(self.suggestion_list.currentRow() + 1,
                        self.suggestion_list.count() - 1)
                )
                return
            elif event.key() == Qt.Key.Key_Up:
                self.suggestion_list.setCurrentRow(
                    max(self.suggestion_list.currentRow() - 1, 0)
                )
                return
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.suggestion_list.currentItem():
                    self.apply_suggestion(self.suggestion_list.currentItem())
                return
            elif event.key() == Qt.Key.Key_Escape:
                self.suggestion_list.hide()
                self.setFocus()
                return
        super().keyPressEvent(event)
        
        
class PlayerSearch:
    def __init__(self, search_signal):
        self.search_url = 'https://aoe4world.com/api/v0/players/search?query={}'
        self.search_signal = search_signal

    def search(self, query):
        def req(query):
            try:
                response = self.get_response(self.search_url.format(query))
                data = json.loads(response.text)
                result_list = self.sort_players(query, [(player['profile_id'], player['name'], self.timezone_convert(player['last_game_at'])) for player in data['players']])
            except Exception as e:
                result_list = ["没有检索到相关ID"]
                print('search error:', e)
            self.search_signal.emit(query, result_list)
        threading.Thread(target=req, args=(query,), daemon=True).start()
    
    @retry(stop_max_attempt_number=10)
    def get_response(self, url):
        # 从API接口获取数据，最多重试10次
        try:
            response = requests.get(url=url)
            return response
        except Exception as network_error:
            print(network_error)
            
    @staticmethod 
    def sort_players(query: str, players):
        def sort_key(item):
            _, name, last_game_at_str = item
            last_game_at = datetime.strptime(last_game_at_str, "%Y-%m-%d %H:%M:%S")
            name_l = name.lower()
            # fuzz 相似度（主排序，越大越靠前）
            similarity = fuzz.ratio(q, name_l)
            # 时间排序（次排序，越近越靠前）
            # sorted 是升序，所以用负时间戳
            time_score = last_game_at.timestamp() if last_game_at else float("inf")
            return similarity, time_score

        q = query.lower().strip()
        return sorted(players, key=sort_key, reverse=True)

    @staticmethod
    def timezone_convert(utc_time_str):
        # 将UTC时间转换到北京时间
        utc_dt = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
        beijing_tz = pytz.timezone("Asia/Shanghai")
        beijing_dt = utc_dt.astimezone(beijing_tz)
        return beijing_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    
class PlayerDetail:
    def __init__(self, detail_signal, add_new_game_history_signal):
        self.detail_url = 'https://aoe4world.com/api/v0/players/{}'
        self.game_history_url = 'https://aoe4world.com/api/v0/players/{}/games'
        self.detail_signal = detail_signal
        self.add_new_game_history_signal = add_new_game_history_signal
        
    def get_game_history(self, profile_id):
        def req(profile_id):
            data_list = []
            try:
                response = self.get_response(self.game_history_url.format(profile_id))
                response_data = json.loads(response.text)
                index = 0
                for game in response_data['games']:
                    index = index + 1 
                    if index > 100:
                        break
                    player_data = []
                    map_name = game['map']
                    game_id = game['game_id']
                    kind = game['kind']
                    teams = game['teams']
                    for team in teams:
                        for player in team:
                            player_profile_id = player['player']['profile_id']
                            player_name = player['player']['name']
                            player_mmr = str(player['player']['rating']) if player['player']['rating'] else '--'
                            civilization = player['player']['civilization']
                            win_rate = '0%'
                            kind = kind
                            if player_profile_id == int(profile_id):
                                rating_diff = player['player']['rating_diff']
                                result = player['player']['result']
                            player_data.append((player_name, civilization, player_profile_id, player_mmr, win_rate, kind))
                    game_mode = str(len(player_data))
                    data = (map_name, game_id, game_mode, player_data, kind, rating_diff, result, profile_id)
                    data_list.append(data)
            except Exception as e:
                print('detail error:', e)
            finally:
                self.add_new_game_history_signal.emit(data_list)
                
        threading.Thread(target=req, args=(profile_id,), daemon=True).start()
        
    def get_detail(self, profile_id):
        def req(profile_id):
            try:
                response = self.get_response(self.detail_url.format(profile_id))
                data = json.loads(response.text)
                avatar_full_url = data['avatars']['full'] if data['avatars']['full'] else "https://avatars.akamai.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg"
                if avatar_full_url:
                    avatar_full_img = self.get_response(avatar_full_url)
                    if avatar_full_img:
                        data['avatars']['full'] = avatar_full_img.content
                    else:
                        data['avatars']['full'] = None
                country_flag = data['country']
                if country_flag:
                    country_flag = self.get_response(f"https://flagcdn.com/w40/{country_flag.lower()}.png")
                    if country_flag:
                        data['country'] = country_flag.content
                    else:
                        data['country'] = None
                self.detail_signal.emit(data)
            except Exception as e:
                print('detail error:', e)
                
        threading.Thread(target=req, args=(profile_id,), daemon=True).start()
        
    @retry(stop_max_attempt_number=10)
    def get_response(self, url):
        # 从API接口获取数据，最多重试10次
        try:
            response = requests.get(url=url, verify=False)
            return response
        except Exception as network_error:
            print(network_error)
            
            
class GameHistoryWidget(QWidget):
    
    
    def __init__(self, civilization_icon_dic, map_dic, data, apply_signal, mark_signal, player_mark_dic, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_name, self.game_id, self.game_mode, self.player_data, self.kind, self.rating_diff, self.result, self.profile_id = data
        self.civilization_icon_dic = civilization_icon_dic
        self.player_mark_dic = player_mark_dic
        self.map_dic = map_dic
        self.apply_signal = apply_signal
        self.mark_signal = mark_signal
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(25)
        self.result_widget = QWidget(parent=self)
        self.left_side_widget = QWidget(parent=self)
        self.mid_side_widget = QWidget(parent=self)
        self.right_side_widget = QWidget(parent=self)
        
        self.main_layout.addWidget(self.result_widget)
        self.main_layout.addWidget(self.left_side_widget)
        self.main_layout.addWidget(self.mid_side_widget)
        self.main_layout.addWidget(self.right_side_widget)
        
        self.left_side_widget_layout = QVBoxLayout(self.left_side_widget)
        self.right_side_widget_layout = QVBoxLayout(self.right_side_widget)
        self.mid_side_widget_layout = QVBoxLayout(self.mid_side_widget)
        self.mid_side_widget_layout.setSpacing(0)

        # if game_mode == 2:
        #     self.setFixedSize(760, 70)
        #     self.icon_size = QSize(40, 40)
        #     self.mid_side_widget_layout.setContentsMargins(0, 0, 0, 0)
        #     self.mid_side_widget.setFixedSize(110, 70)
        # elif game_mode == 4:
        #     self.setFixedSize(760, 70)
        #     self.icon_size = QSize(40, 40)
        #     self.mid_side_widget_layout.setContentsMargins(0, 5, 0, 5)
        #     self.mid_side_widget.setFixedSize(110, 70)
        # elif game_mode == 6:
        #     self.setFixedSize(760, 110)
        #     self.icon_size = QSize(60, 60)
        #     self.mid_side_widget_layout.setContentsMargins(0, 10, 0, 15)
        #     self.mid_side_widget.setFixedSize(110, 110)
        # elif game_mode ==8:
        #     self.setFixedSize(760, 150)
        #     self.icon_size = QSize(80, 80)
        #     self.mid_side_widget_layout.setContentsMargins(0, 15, 0, 25)
        #     self.mid_side_widget.setFixedSize(110, 150)
        # else:
        self.setFixedSize(760, 150)
        self.icon_size = QSize(80, 80)
        self.mid_side_widget_layout.setContentsMargins(0, 15, 0, 25)
        self.mid_side_widget.setFixedSize(110, 150)
            
        self.widgets_collection = []
        self.set_mid_side_widget()
        self.set_left_and_right_side_widget()

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
    
    def on_player_name_clicked(self, player_info):
        self.apply_signal.emit(player_info)
        
    def on_player_mark_combobox_currentIndexChanged(self):
        sender = self.sender()
        sender.effect.setOpacity(1)
        player_profile_id = sender.profile_id
        flag = sender.currentIndex()
        reason = None
        self.mark_signal.emit((player_profile_id, flag, reason))
        
    def set_mid_side_widget(self):
        self.mid_side_widget_map_name_label = QLabel(parent=self.mid_side_widget, text=self.map_dic.get(self.map_name)[0])
        self.widgets_collection.append(self.mid_side_widget_map_name_label)
        self.mid_side_widget_layout.addWidget(self.mid_side_widget_map_name_label, alignment=Qt.AlignmentFlag.AlignCenter)
        if self.icon_size:
            self.mid_side_widget_map_icon_label = QLabel(parent=self.mid_side_widget)
            self.mid_side_widget_map_icon_label.setFixedSize(self.icon_size)
            self.widgets_collection.append(self.mid_side_widget_map_icon_label)
            self.mid_side_widget_map_icon_label.setPixmap(self.get_map_icon(self.map_name).scaled(self.icon_size))
            self.mid_side_widget_layout.addWidget(self.mid_side_widget_map_icon_label, alignment=Qt.AlignmentFlag.AlignCenter)        
    
    def set_left_and_right_side_widget(self):

        def set_result_widget():
            self.result_widget_layout = QHBoxLayout(self.result_widget)
            self.result_widget_layout.setContentsMargins(0, 0, 0, 0)
            self.result_widget_layout.setSpacing(5)
            if self.result:
                result_text = "↑" if self.result=='win' else "↓"
            else:
                result_text = " "
            self.result_label = QLabel(parent=self.result_widget, text=result_text)
            style = "color: green" if self.result=='win' else "color: red"
            self.result_label.setStyleSheet(style)

            if self.rating_diff:
                if self.rating_diff >= 10:
                    rating_diff_text = f'+{self.rating_diff}'
                elif 0 <= self.rating_diff < 10:
                    rating_diff_text = f' +{self.rating_diff}'
                elif -10 < self.rating_diff < 0:
                    rating_diff_text = f' {self.rating_diff}'
                elif self.rating_diff < -10:
                    rating_diff_text = f'{self.rating_diff}'
            else:
                rating_diff_text = ' --'
            self.rating_diff_label = QLabel(parent=self.result_widget, text=rating_diff_text)
            self.rating_diff_label.setStyleSheet(style)
            
            self.result_widget_layout.addWidget(self.result_label, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.result_widget_layout.addWidget(self.rating_diff_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        def create_contents(player, profile_id, civilization, player_mmr, side):
            parent = self.left_side_widget if side=='left' else self.right_side_widget
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)
            player_name_label = ClickableLabel(id=profile_id, name=player, parent=parent, text=self.islongname(player))         
            player_name_label.setStyleSheet("color: rgb(114, 137, 218)" if self.profile_id == profile_id else "")
            player_name_label.clicked.connect(self.on_player_name_clicked)
            player_civ_label = QLabel(parent=parent)
            player_civ_label.setPixmap(self.get_civ_icon(civilization).scaled(40, 24))
            player_mark_combobox = ReadOnlyComboBox(parent=parent, ObjectName="player_mark_combobox")
            player_mark_combobox.profile_id = profile_id
            player_mark_combobox.setFixedSize(22, 22)
            player_mark_combobox.addItem(QIcon(":images/icons/noob.png"), '')
            player_mark_combobox.addItem(QIcon(":images/icons/carry.png"), '')
            player_mark_combobox.addItem(QIcon(":images/icons/hacker.png"), '')
            if (mark := self.player_mark_dic.get(profile_id)):
                player_mark_combobox.setCurrentIndex(mark[0])
            else:
                player_mark_combobox.setCurrentIndex(-1)
            player_mark_combobox.currentIndexChanged.connect(self.on_player_mark_combobox_currentIndexChanged)
            player_mmr_label = QLabel(parent=parent, text=player_mmr)
            self.widgets_collection.append(player_name_label)
            self.widgets_collection.append(player_civ_label)
            self.widgets_collection.append(player_mark_combobox)
            self.widgets_collection.append(player_mmr_label)
            return layout, player_name_label, player_civ_label, player_mark_combobox, player_mmr_label
            
        def add_to_left_side(player, profile_id, civilization, player_mmr):
            layout, player_name_label, player_civ_label, player_mark_combobox, player_mmr_label = create_contents(player, profile_id, civilization, player_mmr, 'left')
            layout.addWidget(player_civ_label, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(player_name_label, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addStretch(1)
            layout.addWidget(player_mark_combobox, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(player_mmr_label, alignment=Qt.AlignmentFlag.AlignCenter)
            self.left_side_widget_layout.addLayout(layout)
        
        def add_to_right_side(player, profile_id, civilization, player_mmr):
            layout, player_name_label, player_civ_label, player_mark_combobox, player_mmr_label = create_contents(player, profile_id, civilization, player_mmr,  'right')
            layout.addWidget(player_mmr_label, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(player_mark_combobox, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addStretch(1)
            layout.addWidget(player_name_label, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(player_civ_label, alignment=Qt.AlignmentFlag.AlignCenter)
            self.right_side_widget_layout.addLayout(layout)
        
        players_count = len(self.player_data)
        self.right_side_widget_layout.addStretch(1)
        self.left_side_widget_layout.addStretch(1)
        set_result_widget()
        for index, player_info in enumerate(self.player_data):
            player, civilization, profile_id, player_mmr, win_rate, kind = player_info
            if index < players_count/2:
                add_to_left_side(player, profile_id, civilization, player_mmr)
            else:
                add_to_right_side(player, profile_id, civilization, player_mmr)
        self.right_side_widget_layout.addStretch(1)
        self.left_side_widget_layout.addStretch(1)
    
    def get_civ_icon(self, civ):
        img = self.civilization_icon_dic.get(civ)
        pixmap = QPixmap()
        pixmap.loadFromData(img)
        return pixmap
    
    def get_map_icon(self, map):
        img = self.map_dic.get(map)[1]
        pixmap = QPixmap()
        pixmap.loadFromData(img)
        return pixmap
    
    
class ClickableLabel(QLabel):
    clicked = Signal(tuple)
    
    def __init__(self, name, id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = id
        self.name = name
        
    def mousePressEvent(self, event):
        self.clicked.emit((self.id, self.name))
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.style = self.styleSheet()
        self.setStyleSheet("color: #0078D4")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        return super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.setStyleSheet(self.style)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().leaveEvent(event)
    
    
class ReadOnlyComboBox(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._locked = True

    def setLocked(self, locked: bool):
        self._locked = locked

    def mousePressEvent(self, e):
        if self._locked:
            return
        super().mousePressEvent(e)

    def wheelEvent(self, e):
        if self._locked:
            return
        super().wheelEvent(e)

    def keyPressEvent(self, e):
        if self._locked:
            return
        super().keyPressEvent(e)