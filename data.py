#!/usr/bin/python3
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
    def __init__(self, gui_class, profile_id, databasepath, logpath, map_dic):
        self.quit_signal = False  # 是否结束数据追踪动作的标志（由主线程设定）
        self.last_game_id = None
        self.databasepath = databasepath
        self.logpath = logpath
        self.conn = sqlite3.connect(self.databasepath, check_same_thread=False)
        self.cur = self.conn.cursor()
        self.profile_id = profile_id  # 追踪游戏对局数据的账户PID（由主线程设定）
        self.gui_class = gui_class
        self.map_dic = map_dic  # 地图中英文对照表

    def timezone_convert(self, utc_time_str):
        # 将UTC时间转换到北京时间
        utc_dt = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
        beijing_tz = pytz.timezone("Asia/Shanghai")
        beijing_dt = utc_dt.astimezone(beijing_tz)
        return beijing_dt.strftime("%Y-%m-%d %H:%M:%S")

    def player_search(self, query):
        # 通过API搜索接口返回账户数据
        start_time = time.time()
        url = f'https://aoe4world.com/api/v0/players/search?query={query}'
        response = self.get_response(url)
        data = json.loads(response.text)
        self.gui_class.query_rs[start_time] = [(player['profile_id'], player['name'], self.timezone_convert(player['last_game_at'])) for player in data['players']]
        self.gui_class.searching_signal.emit('okay')

    def update_player_name(self):
        # 启动时更新已保存的账户名（考虑用户可能会更改ID）
        cursor = self.conn.cursor()
        cursor.execute("select profile_id from profile_id order by create_time desc limit 6")
        id_list = cursor.fetchall()
        for _id in id_list:
            _id = _id[0]
            name = None
            try:
                playerdata = self.get_response('https://aoe4world.com/api/v0/players/' + str(_id))
                if playerdata.status_code == 200:
                    name = json.loads(playerdata.content.decode())['name']
                else:
                    pass
            except Exception as e:
                print(e)
            if name is not None:
                cursor.execute("update profile_id set player_name = ? where profile_id = ?", (name, _id))
                self.conn.commit()
        self.gui_class.on_data_change('reload playername')

    @retry(stop_max_attempt_number=10)
    def get_response(self, url):
        # 从API接口获取数据，最多重试10次
        try:
            response = requests.get(url=url)
            return response
        except Exception as network_error:
            print(network_error)

    def count(self):
        # 统计log文件的行数
        counts = 0
        try:
            with open(self.logpath, 'r') as log:
                counts = len(log.readlines())
        except:
            pass
        return counts

    @func_timeout.func_set_timeout(80)
    def get_data(self, log):
        # 从API接口获取最新的游戏对局数据
        values = ''
        player_data = []
        counts = self.count()
        # 如果log文件超过1000行，清理文件
        if counts > 1000:
            log.truncate(0)
        try:
            # 获取最新游戏对局
            lastgame = self.get_response(url=f'https://aoe4world.com/api/v0/players/{self.profile_id}/games/last')
            last_game_json = json.loads(lastgame.content.decode())
            game_id = str(last_game_json['game_id'])
            # 如果该局游戏是新开的，则请求该对局数据
            if game_id != self.last_game_id:
                map = last_game_json['map']
                try:
                    map_chinese = self.map_dic[map]
                except:
                    map_chinese = map
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
                        player = str.replace(player, "'", "''")
                        civilization = element['civilization']
                        player_profile_id = element['profile_id']
                        # 根据游戏类型（排位、快速比赛、3V3/4V4/2V2/1V1）请求玩家mmr
                        player_leaderboards = self.get_response(f'https://aoe4world.com/api/v0/leaderboards/{kind}?profile_id={player_profile_id}')
                        player_leaderboards_json = json.loads(player_leaderboards.content.decode())
                        if bool(player_leaderboards_json['players']):
                            player_mmr = player_leaderboards_json['players'][0]['rating']
                            win_rate = player_leaderboards_json['players'][0]['win_rate']
                        else:
                            player_mmr = '--'
                            win_rate = '--'
                        value = "(" + str(game_id) + ",'" + str(player) + "','" + str(win_rate) + "','" + str(civilization) + "','" + str(map_chinese) + (
                            "','") + str(player_profile_id) + "','" + str(player_mmr) + "'," + str(i) + ",'" + str(kind) + "')"
                        values = ",".join([values, value])
                        player_data.append((str(player), civilization, player_profile_id, str(player_mmr), str(win_rate), str(kind)))
                # 数据校验，如果本次请求的数据缺失，终止
                if last_game_kind in ('rm_1v1', 'qm_1v1') and player_counts != 2:
                    return
                elif last_game_kind in ('rm_2v2', 'qm_2v2') and player_counts != 4:
                    return
                elif last_game_kind in ('rm_3v3', 'qm_3v3') and player_counts != 6:
                    return
                elif last_game_kind in ('rm_4v4', 'qm_4v4') and player_counts != 8:
                    return
                self.last_game_id = game_id
                new_content = "\n" + str(time.ctime()) + ": when request -- " + values
                # 数据记入日志文件
                log.write(new_content)
                # 重载gui界面
                self.gui_class.last_game_data = (map_chinese, str(game_id), len(player_data), player_data, kind)
                self.gui_class.on_data_change('reload game')
                # 写入数据库
                insert_sql = "insert into last_game select * from (" + values.replace(values[0], 'values', 1) + ")"
                self.cur.execute(insert_sql)
                self.cur.execute("delete from last_game where game_id <> ?", (str(game_id),))
                self.conn.commit()
        except Exception as e:
            # 发生异常时，写入异常信息
            new_content = "\n" + str(time.ctime()) + ": when request exception -- " + str(traceback.print_exc())
            log.write(new_content)

    def worker(self):
        print('data thread start')
        update_thread = threading.Thread(target=self.update_player_name)
        update_thread.start()
        while True:
            if not self.quit_signal:
                log = open(self.logpath, 'a+', encoding='utf-8')
                try:
                    self.get_data(log)
                except func_timeout.exceptions.FunctionTimedOut as e:
                    new_content = "\n" + str(time.ctime()) + ": when timesleep exception -- " + str(e)
                    log.write(new_content)
                    pass
                else:
                    pass
                log.close()
                time.sleep(10)
            else:
                break
