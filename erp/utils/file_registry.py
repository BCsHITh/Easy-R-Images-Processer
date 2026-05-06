"""
文件注册与状态管理器
追踪所有 NIfTI 文件的状态、分类和使用情况
"""
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import json
import re

class FileType(Enum):
    """文件类型枚举"""
    T1W = "T1w"
    T2W = "T2w"
    BOLD = "BOLD"
    DWI = "DWI"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class FileStatus(Enum):
    """文件状态枚举"""
    NEW = "New"  # 新导入，未处理
    CONVERTED = "Converted"  # DICOM 转换生成
    USED = "Used"  # 已被某流程使用
    PROCESSING = "Processing"  # 正在处理中
    COMPLETED = "Completed"  # 处理完成


class FileRecord:
    """单条文件记录"""

    def __init__(self, file_path: str, file_type: FileType = FileType.UNKNOWN):
        self.file_path = Path(file_path)
        self.file_type = file_type
        self.status = FileStatus.NEW
        self.subject_id = self._extract_subject_id()  # ← 新增：实验编号
        self.session_id = self._extract_session_id()  # ← 新增：会话编号
        self.created_time = datetime.now()
        self.last_used_time: Optional[datetime] = None
        self.used_by: List[str] = []  # 被哪些流程使用过
        self.notes: str = ""

    def _extract_subject_id(self) -> str:
        """从文件名提取实验编号"""
        name = self.file_path.name.upper()

        # 常见命名模式
        patterns = [
            r'(MOUSE\d+)',  # MOUSE001
            r'(RAT\d+)',  # RAT001
            r'(SUB\d+)',  # SUB001
            r'(S\d+)',  # S001
            r'([A-Z]+\d{3,})',  # ABC001
        ]

        for pattern in patterns:
            match = re.search(pattern, name)
            if match:
                return match.group(1)

        # 如果没有匹配，使用父目录名
        return self.file_path.parent.name or "Unknown"

    def _extract_session_id(self) -> str:
        """从文件名提取会话编号"""
        name = self.file_path.name.upper()

        patterns = [
            r'(SES\d+)',  # SES01
            r'(SESSION\d+)',  # SESSION01
            r'(_\d+)',  # _01
        ]

        for pattern in patterns:
            match = re.search(pattern, name)
            if match:
                return match.group(1)

        return "01"  # 默认会话

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "file_path": str(self.file_path),
            "file_type": self.file_type.value,
            "status": self.status.value,
            "subject_id": self.subject_id,
            "session_id": self.session_id,
            "created_time": self.created_time.isoformat(),
            "last_used_time": self.last_used_time.isoformat() if self.last_used_time else None,
            "used_by": self.used_by,
            "notes": self.notes
        }

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建"""
        record = cls(data["file_path"], FileType(data["file_type"]))
        record.status = FileStatus(data["status"])
        record.subject_id = data.get("subject_id", record._extract_subject_id())
        record.session_id = data.get("session_id", record._extract_session_id())
        record.created_time = datetime.fromisoformat(data["created_time"])
        if data.get("last_used_time"):
            record.last_used_time = datetime.fromisoformat(data["last_used_time"])
        record.used_by = data.get("used_by", [])
        record.notes = data.get("notes", "")
        return record


class FileRegistry:
    """文件注册表（单例模式）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.files: Dict[str, FileRecord] = {}
        self.config_path = Path("config/file_registry.json")
        self._load()

    def reset(self):
        """重置注册表（用于 debug 重启）"""
        self.files = {}
        self._load()

    def add_file(self, file_path: str, file_type: FileType = FileType.UNKNOWN,
                 status: FileStatus = FileStatus.NEW, subject_id: Optional[str] = None) -> FileRecord:
        """添加文件"""
        path_str = str(Path(file_path).absolute())
        if path_str not in self.files:
            record = FileRecord(path_str, file_type)
            record.status = status
            if subject_id:  # 允许手动设置实验编号
                record.subject_id = subject_id
            self.files[path_str] = record
            self._save()
        return self.files[path_str]

    def get_file(self, file_path: str) -> Optional[FileRecord]:
        """获取文件记录"""
        return self.files.get(str(Path(file_path).absolute()))

    def update_status(self, file_path: str, status: FileStatus):
        """更新文件状态"""
        record = self.get_file(file_path)
        if record:
            record.status = status
            self._save()

    def mark_used(self, file_path: str, used_by: str):
        """标记文件被使用"""
        record = self.get_file(file_path)
        if record:
            record.status = FileStatus.USED
            record.last_used_time = datetime.now()
            if used_by not in record.used_by:
                record.used_by.append(used_by)
            self._save()

    def set_subject_id(self, file_path: str, subject_id: str):
        """设置实验编号"""
        record = self.get_file(file_path)
        if record:
            record.subject_id = subject_id
            self._save()

    def classify_file(self, file_path: str) -> FileType:
        """根据文件名自动分类"""
        path = Path(file_path)
        name = path.name.upper()

        # 分类关键词
        if any(kw in name for kw in ['T1', 'MPRAGE', 'MP2RAGE', 'ANAT']):
            return FileType.T1W
        elif any(kw in name for kw in ['T2', 'SPACE', 'TSE']):
            return FileType.T2W
        elif any(kw in name for kw in ['BOLD', 'FUNC', 'REST', 'TASK', 'EPI']):
            return FileType.BOLD
        elif any(kw in name for kw in ['DWI', 'DTI', 'DIFFUSION']):
            return FileType.DWI
        else:
            return FileType.OTHER

    def get_files_by_type(self, file_type: FileType) -> List[FileRecord]:
        """按类型获取文件"""
        return [f for f in self.files.values() if f.file_type == file_type]

    def get_files_by_subject(self, subject_id: str) -> List[FileRecord]:
        """按实验编号获取文件"""
        return [f for f in self.files.values() if f.subject_id == subject_id]

    def get_files_by_subject_and_type(self, subject_id: str, file_type: FileType) -> List[FileRecord]:
        """按实验编号和类型获取文件"""
        return [f for f in self.files.values()
                if f.subject_id == subject_id and f.file_type == file_type]

    def get_all_subjects(self) -> List[str]:
        """获取所有实验编号"""
        return sorted(list(set(f.subject_id for f in self.files.values())))

    def get_all_files(self) -> List[FileRecord]:
        """获取所有文件"""
        return list(self.files.values())

    def _save(self):
        """保存到文件"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.to_dict() for k, v in self.files.items()}
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ 文件注册表已保存：{len(self.files)} 个文件")
        except Exception as e:
            print(f"❌ 保存文件注册表失败：{e}")

    def _load(self):
        """从文件加载"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for k, v in data.items():
                    self.files[k] = FileRecord.from_dict(v)
                print(f"✅ 文件注册表已加载：{len(self.files)} 个文件")
            except Exception as e:
                print(f"❌ 加载文件注册表失败：{e}")