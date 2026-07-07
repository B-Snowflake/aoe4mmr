#!/usr/bin/env python3 
# Author: B_Snowflake 
# Date: 2026/5/25 00:26:11 
# LastEditTime: 2026/5/25 00:26:11#!/usr/bin/python3
# Author: B_Snowflake
# Date: 2025/4/2

import pytz
import json
import time
import sqlite3
import threading
import traceback
import requests
import func_timeout
from retrying import retry
from datetime import datetime


class Data:
    def __init__(self, gui_reload, profile_id, database_queue, map_dic, profile_id_list, new_version_func):
        self.quit_signal = True  # 是否结束数据追踪动作的标志（由主线程设定）
        self.last_game_id = None
        self.database_queue = database_queue
        self.profile_id_list = profile_id_list
        self.new_version_func = new_version_func
        self.profile_id = profile_id  # 追踪游戏对局数据的账户PID（由主线程设定）
        self.gui_reload = gui_reload
        self.map_dic = {key: values[0] for key, values in map_dic.items()}  # 地图中英文对照表
        self.version_check_url = 'https://github.com/B-Snowflake/aoe4mmr/releases/latest'
        self.version_check_time = None
        self.version_player_check()
        
    def version_player_check(self):
        threading.Thread(target=self.update_player_name, daemon=True).start()
        threading.Thread(target=self.new_version_check, daemon=True).start()

    def new_version_check(self):
        if self.version_check_time is None or (time.time() - self.version_check_time) > 86400:
            self.version_check_time = time.time()
            response = requests.get(self.version_check_url, allow_redirects=True)
            latest_version = response.url.split("/")[-1]
            self.new_version_func(latest_version)

    @staticmethod
    def timezone_convert(utc_time_str):
        # 将UTC时间转换到北京时间
        utc_dt = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
        beijing_tz = pytz.timezone("Asia/Shanghai")
        beijing_dt = utc_dt.astimezone(beijing_tz)
        return beijing_dt.strftime("%Y-%m-%d %H:%M:%S")

    def update_player_name(self):
        # 启动时更新已保存的账户名（考虑用户可能会更改ID）
        result = {}
        for profile_id in self.profile_id_list:
            name = None
            try:
                playerdata = self.get_response('https://aoe4world.com/api/v0/players/' + str(profile_id))
                if playerdata.status_code == 200:
                    name = json.loads(playerdata.content.decode())['name']
            except Exception as e:
                print(e)
            if name is not None:
                result[profile_id] = name
        self.gui_reload('reload playername', result)

    @retry(stop_max_attempt_number=10)
    def get_response(self, url):
        # 从API接口获取数据，最多重试10次
        try:
            response = requests.get(url=url)
            return response
        except Exception as network_error:
            print(network_error)

    @func_timeout.func_set_timeout(80)
    def get_data(self):
        # 从API接口获取最新的游戏对局数据
        player_data_list = []
        error = False
        try:
            # 获取最新游戏对局
            last_game = self.get_response(url=f'https://aoe4world.com/api/v0/players/{self.profile_id}/games/last')
            if last_game:
                last_game_json = json.loads(last_game.content.decode())
                game_id = last_game_json['game_id']
                # 如果该局游戏是新开的，则请求该对局数据
                if game_id != self.last_game_id and last_game_json['ongoing']:
                # if game_id != self.last_game_id:
                    map_english = last_game_json['map']
                    map_chinese = self.map_dic.get(map_english, map_english)
                    teams = last_game_json['teams']
                    last_game_kind = last_game_json['kind']
                    # 根据游戏类型，来拼接请求url
                    if last_game_kind == 'rm_1v1':
                        kind = 'rm_solo'
                    elif last_game_kind == 'rm_2v2' or last_game_kind == 'rm_3v3' or last_game_kind == 'rm_4v4':
                        kind = 'rm_team'
                    elif last_game_kind == 'qm_ffa_nomad':
                        kind = 'qm_ffa'
                    else:
                        kind = last_game_kind
                    i = 0
                    player_counts = 0
                    for elements in teams:
                        i += 1
                        for element in elements:
                            player_counts += 1
                            player = str(element['name'])
                            try:
                                player_mmr = element['rating']
                            except:
                                player_mmr = '--'
                            player = str.replace(player, "'", "''")
                            civilization = element['civilization']
                            player_profile_id = element['profile_id']
                            # 根据游戏类型（排位、快速比赛、3V3/4V4/2V2/1V1）请求玩家mmr
                            player_leaderboards = self.get_response(f'https://aoe4world.com/api/v0/leaderboards/{kind}?profile_id={player_profile_id}')
                            player_leaderboards_json = json.loads(player_leaderboards.content.decode())
                            if bool(player_leaderboards_json['players']):
                                # player_mmr = player_leaderboards_json['players'][0]['rating']
                                win_rate = player_leaderboards_json['players'][0]['win_rate']
                            else:
                                # player_mmr = '--'
                                win_rate = '--'
                            values = (game_id, player, str(win_rate), civilization, map_chinese, str(player_profile_id), str(player_mmr), str(i), kind)
                            insert_sql = ("INSERT INTO last_game ( game_id, player, win_rate, civilization, map, profile_id, player_mmr, team, kind ) "
                                          "VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ? )")
                            # 写入数据库
                            self.database_queue.put((insert_sql, values))
                            player_data_list.append((str(player), civilization, str(player_profile_id), str(player_mmr), str(win_rate), str(kind)))
                    # 数据校验，如果本次请求的数据缺失，终止
                    if last_game_kind in ('rm_1v1', 'qm_1v1') and player_counts != 2:
                        error = True
                    elif last_game_kind in ('rm_2v2', 'qm_2v2') and player_counts != 4:
                        error = True
                    elif last_game_kind in ('rm_3v3', 'qm_3v3') and player_counts != 6:
                        error = True
                    elif last_game_kind in ('rm_4v4', 'qm_4v4') and player_counts != 8:
                        error = True
                    if error:
                        self.database_queue.put(("delete from last_game where game_id = ?", (game_id, )))
                        print(f'game_id:{game_id}, 本次获取的数据不完整')
                        return
                    else:
                        self.last_game_id = game_id
                        # 重载gui界面
                        last_game_data = (map_chinese, str(game_id), len(player_data_list), player_data_list, kind)
                        self.gui_reload('reload game', last_game_data)
                        self.database_queue.put(("delete from last_game where game_id <> ?", (game_id, )))
        except Exception as e:
            # 发生异常时，写入异常信息
            new_content = "\n" + time.strftime("%Y.%m.%d %H:%M:%S") + ": when request exception -- " + str(traceback.format_exc())
            print(new_content)
            
    def worker(self):
        print('data thread start')
        self.version_player_check()
        while True:
            if not self.quit_signal:
                try:
                    self.get_data()
                except func_timeout.exceptions.FunctionTimedOut as e:
                    new_content = "\n" + time.strftime("%Y.%m.%d %H:%M:%S") + ": when timesleep exception -- " + str(e)
                    print(new_content)
                time.sleep(10)
            else:
                break
