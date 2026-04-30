"""
文件管理面板（增强版）
使用独立的冠状面预览控件
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QMenu, QLineEdit, QSplitter
)
from PySide6.QtCore import Qt, Signal
from pathlib import Path

from erp.views.panels.base_panel import BasePanel
from erp.utils.file_registry import FileRegistry, FileType, FileStatus
from erp.widgets.coronal_viewer import CoronalViewer  # ← 使用新的冠状面预览


class FileManagerPanel(BasePanel):
    """文件管理面板"""

    # 信号：文件被选中，通知其他面板
    file_selected = Signal(str, str)  # 文件路径，文件类型

    def __init__(self, config, parent=None, with_preview=True):
        self.config = config
        self.registry = FileRegistry()
        # 注意：这里跳过父类的 _init_ui，我们自己实现
        QWidget.__init__(self, parent)
        self.title = "2. 文件管理"
        self.with_preview = with_preview
        self._init_ui()

    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 标题
        title_label = QLabel(self.title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a9eff;")
        layout.addWidget(title_label)

        if self.with_preview:
            # 分割器：左侧文件树 + 右侧预览
            splitter = QSplitter(Qt.Horizontal)

            # 左侧：文件管理
            file_widget = self._create_file_panel()
            splitter.addWidget(file_widget)

            # 右侧：冠状面预览
            preview_widget = self._create_preview_panel()
            splitter.addWidget(preview_widget)

            splitter.setStretchFactor(0, 2)
            splitter.setStretchFactor(1, 1)

            layout.addWidget(splitter)
        else:
            # 无预览模式
            file_widget = self._create_file_panel()
            layout.addWidget(file_widget)

        # 底部：日志
        from erp.widgets.log_viewer import LogViewer
        self.log_viewer = LogViewer()
        layout.addWidget(self.log_viewer)

    def _create_file_panel(self):
        """创建文件管理面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 分割器：文件树 + 文件信息
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：文件目录树
        tree_widget = self._create_file_tree()
        splitter.addWidget(tree_widget)

        # 右侧：文件信息
        info_widget = self._create_file_info()
        splitter.addWidget(info_widget)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        # 底部按钮
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("📁 添加文件")
        add_btn.clicked.connect(self._add_files)
        btn_layout.addWidget(add_btn)

        add_dir_btn = QPushButton("📂 添加目录")
        add_dir_btn.clicked.connect(self._add_directory)
        btn_layout.addWidget(add_dir_btn)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_tree)
        btn_layout.addWidget(refresh_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        return widget

    def _create_preview_panel(self):
        """创建预览面板（冠状面）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 使用独立的冠状面预览控件
        self.coronal_viewer = CoronalViewer()
        self.coronal_viewer.image_loaded.connect(self._on_image_loaded)
        layout.addWidget(self.coronal_viewer)

        return widget

    def _create_file_tree(self):
        """创建文件树"""
        group = QGroupBox("文件库")
        layout = QVBoxLayout()

        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索文件...")
        self.search_edit.textChanged.connect(self._filter_files)
        layout.addWidget(self.search_edit)

        # 文件树
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["文件名", "类型", "状态", "路径"])
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.file_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.file_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.file_tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.file_tree.itemClicked.connect(self._on_item_clicked)
        self.file_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.file_tree)

        group.setLayout(layout)
        return group

    def _create_file_info(self):
        """创建文件信息面板"""
        group = QGroupBox("文件信息")
        layout = QVBoxLayout()

        # 信息标签
        self.info_labels = {}
        info_fields = [
            ("file_name", "文件名:"),
            ("file_type", "类型:"),
            ("file_status", "状态:"),
            ("file_path", "路径:"),
            ("file_used_by", "使用过:")
        ]

        for key, label_text in info_fields:
            label = QLabel(f"{label_text} —")
            label.setStyleSheet("font-size: 11px; color: #888;")
            label.setWordWrap(True)
            layout.addWidget(label)
            self.info_labels[key] = label

        layout.addStretch()

        # 操作按钮
        self.use_t1_btn = QPushButton("设为 T1w")
        self.use_t1_btn.clicked.connect(lambda: self._use_file("T1w"))
        layout.addWidget(self.use_t1_btn)

        self.use_bold_btn = QPushButton("设为 BOLD")
        self.use_bold_btn.clicked.connect(lambda: self._use_file("BOLD"))
        layout.addWidget(self.use_bold_btn)

        self.use_t2_btn = QPushButton("设为 T2w")
        self.use_t2_btn.clicked.connect(lambda: self._use_file("T2w"))
        layout.addWidget(self.use_t2_btn)

        group.setLayout(layout)
        return group

    # ... 其余方法保持不变（_refresh_tree, _add_files, _on_item_clicked 等）

    def _refresh_tree(self):
        """刷新文件树"""
        self.file_tree.clear()

        # 按类型分组
        categories = {
            "T1w 结构像": FileType.T1W,
            "T2w 结构像": FileType.T2W,
            "BOLD 功能像": FileType.BOLD,
            "DWI 扩散像": FileType.DWI,
            "其他文件": FileType.OTHER,
            "未分类": FileType.UNKNOWN
        }

        for cat_name, file_type in categories.items():
            files = self.registry.get_files_by_type(file_type)
            if files:
                cat_item = QTreeWidgetItem([cat_name, "", "", ""])
                cat_item.setForeground(0, Qt.darkGray)

                for f in files:
                    item = QTreeWidgetItem([
                        f.file_path.name,
                        f.file_type.value,
                        f.status.value,
                        str(f.file_path.parent)
                    ])
                    item.setData(0, Qt.UserRole, str(f.file_path))

                    # 状态颜色
                    if f.status == FileStatus.NEW:
                        item.setForeground(2, Qt.green)
                    elif f.status == FileStatus.USED:
                        item.setForeground(2, Qt.blue)
                    elif f.status == FileStatus.COMPLETED:
                        item.setForeground(2, Qt.darkGreen)

                    cat_item.addChild(item)

                self.file_tree.addTopLevelItem(cat_item)

    def _add_files(self):
        """添加文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择 NIfTI 文件", "", "NIfTI Files (*.nii *.nii.gz)"
        )

        for f in files:
            file_type = self.registry.classify_file(f)
            self.registry.add_file(f, file_type)

        self._refresh_tree()
        self.log(f"添加 {len(files)} 个文件", "SUCCESS")

    def _add_directory(self):
        """添加目录（递归扫描）"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择目录")
        if dir_path:
            count = 0
            for f in Path(dir_path).rglob("*.nii*"):
                file_type = self.registry.classify_file(str(f))
                self.registry.add_file(str(f), file_type)
                count += 1
            self._refresh_tree()
            self.log(f"扫描目录，添加 {count} 个文件", "SUCCESS")

    def _filter_files(self, text):
        """过滤文件"""
        self._refresh_tree()

    def _on_item_clicked(self, item, column):
        """文件被单击"""
        file_path = item.data(0, Qt.UserRole)
        if file_path:
            record = self.registry.get_file(file_path)
            if record:
                # 更新信息面板
                self.info_labels["file_name"].setText(f"文件名：{record.file_path.name}")
                self.info_labels["file_type"].setText(f"类型：{record.file_type.value}")
                self.info_labels["file_status"].setText(f"状态：{record.status.value}")
                self.info_labels["file_path"].setText(f"路径：{str(record.file_path.parent)}")
                self.info_labels["file_used_by"].setText(f"使用过：{', '.join(record.used_by) if record.used_by else '—'}")

                # 发射信号，通知其他面板
                self.file_selected.emit(str(file_path), record.file_type.value)

    def _on_item_double_clicked(self, item, column):
        """文件被双击 - 在预览窗显示"""
        file_path = item.data(0, Qt.UserRole)
        if file_path and hasattr(self, 'coronal_viewer'):
            self.coronal_viewer.load_image(file_path)
            self.log(f"预览：{Path(file_path).name}")

    def _on_image_loaded(self, file_path):
        """图像加载完成"""
        self.log(f"加载预览：{Path(file_path).name}")

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        item = self.file_tree.itemAt(pos)
        if item:
            menu = QMenu(self)

            preview_action = menu.addAction("👁 预览")
            preview_action.triggered.connect(lambda: self._on_item_double_clicked(item, 0))

            menu.addSeparator()

            t1_action = menu.addAction("标记为 T1w")
            t1_action.triggered.connect(lambda: self._set_file_type(item, FileType.T1W))

            t2_action = menu.addAction("标记为 T2w")
            t2_action.triggered.connect(lambda: self._set_file_type(item, FileType.T2W))

            bold_action = menu.addAction("标记为 BOLD")
            bold_action.triggered.connect(lambda: self._set_file_type(item, FileType.BOLD))

            menu.addSeparator()

            remove_action = menu.addAction("❌ 移除")
            remove_action.triggered.connect(lambda: self._remove_file(item))

            menu.exec_(self.file_tree.viewport().mapToGlobal(pos))

    def _set_file_type(self, item, file_type):
        """设置文件类型"""
        file_path = item.data(0, Qt.UserRole)
        if file_path:
            record = self.registry.get_file(file_path)
            if record:
                record.file_type = file_type
                self.registry._save()
                self._refresh_tree()
                self.log(f"设置类型：{Path(file_path).name} → {file_type.value}")

    def _remove_file(self, item):
        """移除文件"""
        file_path = item.data(0, Qt.UserRole)
        if file_path:
            if file_path in self.registry.files:
                del self.registry.files[file_path]
                self.registry._save()
                self._refresh_tree()
                self.log(f"移除：{Path(file_path).name}")

    def _use_file(self, use_type):
        """标记文件被使用"""
        current_item = self.file_tree.currentItem()
        if current_item:
            file_path = current_item.data(0, Qt.UserRole)
            if file_path:
                self.registry.mark_used(file_path, use_type)
                self._refresh_tree()
                self.log(f"标记使用：{Path(file_path).name} → {use_type}")

    def register_file_from_convert(self, file_path: str):
        """从转换模块注册文件"""
        file_type = self.registry.classify_file(file_path)
        self.registry.add_file(file_path, file_type, FileStatus.CONVERTED)
        self._refresh_tree()
        self.log(f"转换生成：{Path(file_path).name}", "SUCCESS")

    def log(self, message, level="INFO"):
        """添加日志"""
        self.log_viewer.append_log(message, level)