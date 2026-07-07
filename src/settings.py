#!/usr/bin/env python3 
# Author: B_Snowflake 
# Date: 2026/5/25 03:24:41 
# LastEditTime: 2026/5/25 03:24:41

import json
import os
from dataclasses import asdict, dataclass, field, fields


@dataclass
class ProfileId:
    profile_id: str = ""
    profile_name: str = ""
    

@dataclass
class Settings:
    setting_path: str = field(default="", repr=False)
    hotkey: str = "ctrl+q"
    enable_dragging: bool = False
    show_gui_when_startup: bool = True
    window_location: list = field(default_factory=list)
    max_show_game_history: int = 10
    max_accounts: int = 6
    picked_profile_id: str = ""
    profile_id: dict[str, ProfileId] = field(default_factory=dict)

    @staticmethod
    def _to_json(obj):
        if isinstance(obj, dict):    
            return { 
                k: __class__._to_json(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [__class__._to_json(v) for v in obj]
        if hasattr(obj, "__dict__") or hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        return obj

    def load(self, path: str):
        self.setting_path = path
        if not os.path.exists(path):
            return self
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for f in fields(self):
                if f.name == "setting_path":
                    continue
                if f.name not in data:
                    continue
                value = data[f.name]
                # 特殊处理 dict[str, ProfileId]
                if f.name == "profile_id" and isinstance(value, dict):
                    value = self._from_dict_profile_map(value)
                setattr(self, f.name, value)
            if not self.picked_profile_id:
                self.picked_profile_id = list(self.profile_id.keys())[0] if self.profile_id else ""
            return self
        except Exception as e:
            print(f"load error: {e}")
            return self

    @staticmethod
    def _from_dict_profile_map(data: dict) -> dict[str, ProfileId]:
        result = {}
        for k, v in data.items():
            result[k] = ProfileId(**v)
        return result

    def save(self):
        if not self.setting_path:
            raise ValueError("setting_path is empty")
        try:
            data = {}
            for f in fields(self):
                if f.name in ("setting_path", "max_accounts"):
                    continue
                value = getattr(self, f.name)
                data[f.name] = self._to_json(value)
            path = self.setting_path
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    data,
                    f,
                    ensure_ascii=False,
                    indent=4
                )
            return True
        except Exception as e:
            print(f"save error: {e}")
            return False
            
    def update_profile_id(self, new_profile_id, new_profile_name):
        """更新profile_id，并保存"""
        for old_profile_id in self.profile_id.keys():
            if old_profile_id == new_profile_id:
                self.profile_id[old_profile_id] = ProfileId(profile_id=new_profile_id, profile_name=new_profile_name)
                return
        self.profile_id[new_profile_id] = ProfileId(profile_id=new_profile_id, profile_name=new_profile_name)
        self.save()
        
    def delete_profile_id(self, profile_id):
        """删除profile_id，并保存"""
        if profile_id in self.profile_id:
            del self.profile_id[profile_id]
            self.save()
        else:
            print(f"Profile ID {profile_id} not found.")
            return
        if profile_id == self.picked_profile_id:
            if len(self.profile_id.keys()) > 0:
                self.picked_profile_id = list(self.profile_id.keys())[0]
        
    def update_picked_profile_id(self, new_picked_profile_id):
        """更新picked_profile_id，并保存"""
        for old_profile_id in self.profile_id.keys():
            if old_profile_id == new_picked_profile_id:
                self.picked_profile_id = new_picked_profile_id
                return
        print(f"Profile ID {new_picked_profile_id} not found.")
