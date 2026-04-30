"""
主窗口
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget,
    QMenuBar, QMenu, QStatusBar, QLabel, QFrame,
    QPushButton, QVBoxLayout, QListWidget, QListWidgetItem
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QSize

from erp.views.panels.dicom_convert import DicomConvertPanel
from erp.views.panels.file_manager import FileManagerPanel
from erp.views.panels.structural import StructuralPanel
from erp.views.panels.functional import FunctionalPanel
from erp.views.panels.transform import TransformPanel

class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_panel = None

        self._init_ui()
        self._init_menu()
        self._load_config()

    def _init_ui(self):
        """初始化界面"""
        self.setWindowTitle("Easy-R-Images-Processer")
        self.setMinimumSize(1200, 800)

        # 中央控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧导航栏
        self.nav_panel = self._create_nav_panel()
        main_layout.addWidget(self.nav_panel)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setStyleSheet("background-color: #3e3e3e;")
        main_layout.addWidget(line)

        # 右侧内容区
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack)

        # 创建功能面板
        self._create_panels()

    def _create_nav_panel(self):
        """创建导航面板"""
        widget = QWidget()
        widget.setMaximumWidth(200)
        widget.setStyleSheet("""
            QWidget {
                background-color: #252526;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setSpacing(5)

        # 标题
        title = QLabel("Easy-R")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #4a9eff; padding: 10px;")
        layout.addWidget(title)

        # 导航列表
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                color: #d4d4d4;
                border: none;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 12px 10px;
                border-radius: 4px;
                margin: 2px 0;
            }
            QListWidget::item:hover {
                background-color: #3e3e3e;
            }
            QListWidget::item:selected {
                background-color: #4a9eff;
                color: white;
            }
        """)

        nav_items = [
            "1. DICOM 转换",
            "2. 文件管理",
            "3. 结构像处理",
            "4. 功能像处理",
            "5. 变换与合并"
        ]

        for item in nav_items:
            list_item = QListWidgetItem(item)
            list_item.setSizeHint(QSize(180, 40))
            self.nav_list.addItem(list_item)

        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        layout.addWidget(self.nav_list)

        layout.addStretch()

        # 版本信息
        from erp import __version__
        version_label = QLabel(f"v{__version__}")
        version_label.setStyleSheet("color: #666; font-size: 11px;")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        return widget

    def _create_panels(self):
        """创建功能面板"""
        self.dicom_panel = DicomConvertPanel(self.config)
        self.file_panel = FileManagerPanel(self.config)
        self.structural_panel = StructuralPanel(self.config)
        self.functional_panel = FunctionalPanel(self.config)
        self.transform_panel = TransformPanel(self.config)

        self.content_stack.addWidget(self.dicom_panel)
        self.content_stack.addWidget(self.file_panel)
        self.content_stack.addWidget(self.structural_panel)
        self.content_stack.addWidget(self.functional_panel)
        self.content_stack.addWidget(self.transform_panel)

    def _on_nav_changed(self, index):
        """导航切换"""
        self.content_stack.setCurrentIndex(index)

        # 更新导航项样式
        for i in range(self.nav_list.count()):
            item = self.nav_list.item(i)
            if i == index:
                item.setSelected(True)
            else:
                item.setSelected(False)

    def _init_menu(self):
        """初始化菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件 (&F)")

        set_dcm2niix_action = QAction("设置 dcm2niix 路径...", self)
        set_dcm2niix_action.triggered.connect(self._set_dcm2niix_path)
        file_menu.addAction(set_dcm2niix_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 工具菜单
        tool_menu = menubar.addMenu("工具 (&T)")

        clear_config_action = QAction("重置配置", self)
        clear_config_action.triggered.connect(self._reset_config)
        tool_menu.addAction(clear_config_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助 (&H)")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _load_config(self):
        """加载配置"""
        if self.config.dcm2niix_path:
            self.dicom_panel.converter = None  # 会在首次转换时初始化

    def _set_dcm2niix_path(self):
        """设置 dcm2niix 路径"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 dcm2niix 可执行文件", "",
            "Executable Files (*.exe);;All Files (*)"
        )

        if file_path:
            self.config.dcm2niix_path = file_path
            QMessageBox.information(self, "成功", f"dcm2niix 路径已设置")

    def _reset_config(self):
        """重置配置"""
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self, "确认", "确定要重置所有配置吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.config.settings = self.config.get_default_config()
            self.config.save()
            QMessageBox.information(self, "成功", "配置已重置")

    def _show_about(self):
        """显示关于"""
        from PySide6.QtWidgets import QMessageBox
        from erp import __version__

        QMessageBox.about(
            self, "关于",
            f"<h2>Easy-R-Images-Processer</h2>"
            f"<p>版本：{__version__}</p>"
            f"<p>小鼠/兔子脑 MRI 序列管理与后处理工具</p>"
        )