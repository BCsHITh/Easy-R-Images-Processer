"""
配置管理模块
"""
import json
import os
from pathlib import Path
from datetime import datetime


class ConfigManager:
    """应用程序配置管理器"""

    def __init__(self):
        self.config_dir = Path("config")
        self.config_file = self.config_dir / "settings.json"
        self.default_config_file = self.config_dir / "default_settings.json"
        self.logs_dir = Path("logs")

        # 确保目录存在
        self.config_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

        # 加载配置
        self.settings = self.load()

    def load(self):
        """加载配置文件"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("⚠️ 配置文件格式错误，使用默认配置")
                return self.get_default_config()
        else:
            return self.get_default_config()

    def get_default_config(self):
        """获取默认配置"""
        return {
            "dcm2niix_path": "",
            "last_work_dir": "",
            "recent_files": [],
            "output_dir": "",
            "auto_convert": True,
            "compression": True,
            "verbose": False
        }

    def save(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ 保存配置失败：{e}")

    def get(self, key, default=None):
        """获取配置项"""
        return self.settings.get(key, default)

    def set(self, key, value):
        """设置配置项"""
        self.settings[key] = value
        self.save()

    @property
    def dcm2niix_path(self):
        """获取 dcm2niix 路径"""
        return self.settings.get("dcm2niix_path", "")

    @dcm2niix_path.setter
    def dcm2niix_path(self, path):
        """设置 dcm2niix 路径"""
        self.settings["dcm2niix_path"] = path
        self.save()

    @property
    def last_work_dir(self):
        """获取上次工作目录"""
        return self.settings.get("last_work_dir", "")

    @last_work_dir.setter
    def last_work_dir(self, path):
        """设置上次工作目录"""
        self.settings["last_work_dir"] = str(path)
        self.save()

    @property
    def log_file(self):
        """获取日志文件路径"""
        date_str = datetime.now().strftime("%Y%m%d")
        return self.logs_dir / f"erp_{date_str}.log"