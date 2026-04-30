"""
3D 重建预览控件（预留接口）
未来使用 VTK 实现
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal


class Viewport3D(QWidget):
    """3D 重建视图（预留接口）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 占位标签
        self.placeholder = QLabel("3D 重建\n(暂未实现)")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("""
            color: #444;
            font-size: 14px;
            background-color: #0a0a0a;
        """)
        layout.addWidget(self.placeholder)

    def load_volume(self, volume_data):
        """加载 3D 体积数据（预留接口）"""
        # TODO: 使用 VTK 实现 3D 重建
        pass

    def set_visibility(self, visible):
        """设置可见性"""
        self.setVisible(visible)