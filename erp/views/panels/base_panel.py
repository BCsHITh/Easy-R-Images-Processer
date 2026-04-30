"""
功能面板基类
所有功能面板继承此类，保证统一布局
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter
from PySide6.QtCore import Signal, Qt
from erp.widgets.image_viewer import ImageViewer
from erp.widgets.log_viewer import LogViewer


class BasePanel(QWidget):
    """功能面板基类"""

    # 信号
    log_signal = Signal(str, str)  # 消息，级别
    progress_signal = Signal(int, str)  # 进度值，文本
    completed_signal = Signal(object)  # 结果数据

    def __init__(self, title, parent=None, with_preview=True):
        super().__init__(parent)
        self.title = title
        self.with_preview = with_preview
        self._init_ui()

    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 标题
        from PySide6.QtWidgets import QLabel
        title_label = QLabel(self.title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a9eff;")
        layout.addWidget(title_label)

        if self.with_preview:
            # 主分割器（左侧工具 + 右侧预览）
            splitter = QSplitter(Qt.Horizontal)

            # 左侧：工具面板
            self.tool_panel = self._create_tool_panel()
            splitter.addWidget(self.tool_panel)

            # 右侧：图像预览
            self.preview_panel = self._create_preview_panel()
            splitter.addWidget(self.preview_panel)

            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 2)

            layout.addWidget(splitter)
        else:
            # 无预览模式：工具面板占满
            self.tool_panel = self._create_tool_panel()
            layout.addWidget(self.tool_panel)

        # 底部：日志
        self.log_viewer = LogViewer()
        layout.addWidget(self.log_viewer)

        # 连接信号
        self.log_signal.connect(self.log_viewer.append_log)

    def _create_tool_panel(self):
        """创建工具面板（子类实现）"""
        raise NotImplementedError("子类必须实现 _create_tool_panel")

    def _create_preview_panel(self):
        """创建预览面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_viewer = ImageViewer()
        layout.addWidget(self.image_viewer)

        return widget

    def log(self, message, level="INFO"):
        """添加日志"""
        self.log_signal.emit(message, level)

    def set_progress(self, value, text=""):
        """设置进度"""
        self.progress_signal.emit(value, text)

    def on_completed(self, result):
        """处理完成（子类可重写）"""
        pass

    def reset(self):
        """重置面板"""
        if self.with_preview and hasattr(self, 'image_viewer'):
            self.image_viewer.clear()
        self.log_viewer.clear_log()