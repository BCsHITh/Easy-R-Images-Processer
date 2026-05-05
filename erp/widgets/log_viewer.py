"""
日志查看器控件
"""
from PySide6.QtWidgets import QTextEdit
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QFont


class LogViewer(QTextEdit):
    """日志查看器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(200)
        self.setFont(QFont("Consolas", 9))
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
            }
        """)

    def append_log(self, message, level="INFO"):
        """添加日志"""
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")

        # 根据级别设置颜色
        if level == "ERROR":
            color = "#f48771"
        elif level == "WARNING":
            color = "#dcdcaa"
        elif level == "SUCCESS":
            color = "#89d185"
        else:
            color = "#d4d4d4"

        html = f'<span style="color: #6a9955;">[{timestamp}]</span> <span style="color: {color};">{level}:</span> {message}'
        self.append(html)

        # ← 修复：使用兼容的方式滚动到底部
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """滚动到底部（兼容不同 PySide6 版本）"""
        try:
            # 方法 1：直接使用 scrollToBottom
            if hasattr(self, 'scrollToBottom'):
                self.scrollToBottom()
            # 方法 2：使用垂直滚动条
            elif hasattr(self, 'verticalScrollBar'):
                scrollbar = self.verticalScrollBar()
                if scrollbar:
                    scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            pass  # 静默失败，不影响功能

    def clear_log(self):
        """清空日志"""
        self.clear()