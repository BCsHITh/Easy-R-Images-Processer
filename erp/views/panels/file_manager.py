"""
文件管理面板（增强版）
布局：左侧文件库 + 右侧（上预览 + 下信息）
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
from erp.widgets.coronal_viewer import CoronalViewer


class FileManagerPanel(BasePanel):
    """文件管理面板"""

    # 信号：文件被选中，通知其他面板
    file_selected = Signal(str, str)  # 文件路径，文件类型

    def __init__(self, config, parent=None, with_preview=True):
        self.config = config
        self.registry = FileRegistry()
        # 跳过父类的 _init_ui，我们自己实现
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
            # 主分割器：左侧文件树 + 右侧内容
            main_splitter = QSplitter(Qt.Horizontal)

            # 左侧：文件库
            file_tree_widget = self._create_file_tree()
            main_splitter.addWidget(file_tree_widget)

            # 右侧：垂直分割（上预览 + 下信息）
            right_widget = QWidget()
            right_layout = QVBoxLayout(right_widget)
            right_layout.setContentsMargins(0, 0, 0, 0)
            right_layout.setSpacing(10)

            # 右侧分割器：上预览 + 下信息
            right_splitter = QSplitter(Qt.Vertical)

            # 上半部分：图像预览
            preview_widget = self._create_preview_panel()
            right_splitter.addWidget(preview_widget)

            # 下半部分：文件信息
            info_widget = self._create_file_info()
            right_splitter.addWidget(info_widget)

            # 设置比例（预览：信息 = 2:1）
            right_splitter.setStretchFactor(0, 2)
            right_splitter.setStretchFactor(1, 1)

            right_layout.addWidget(right_splitter)
            main_splitter.addWidget(right_widget)

            # 设置比例（文件树：右侧 = 1:1）
            main_splitter.setStretchFactor(0, 1)
            main_splitter.setStretchFactor(1, 1)

            layout.addWidget(main_splitter)
        else:
            # 无预览模式
            file_widget = self._create_file_tree()
            layout.addWidget(file_widget)

        # 底部：日志
        from erp.widgets.log_viewer import LogViewer
        self.log_viewer = LogViewer()
        layout.addWidget(self.log_viewer)

    def _create_file_tree(self):
        """创建文件树面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 文件库组
        group = QGroupBox("文件库")
        group_layout = QVBoxLayout()

        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索文件...")
        self.search_edit.textChanged.connect(self._filter_files)
        group_layout.addWidget(self.search_edit)

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
        group_layout.addWidget(self.file_tree)

        group.setLayout(group_layout)
        layout.addWidget(group)

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

        layout.addLayout(btn_layout)
        layout.addStretch()

        return widget

    def _create_preview_panel(self):
        """创建预览面板（冠状面）"""
        group = QGroupBox("👁 图像预览")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        # ← 关键：上方添加弹性空间（使内容向下推）
        layout.addStretch()

        # 使用冠状面预览控件
        self.coronal_viewer = CoronalViewer()
        self.coronal_viewer.image_loaded.connect(self._on_image_loaded)
        self.coronal_viewer.setFocusPolicy(Qt.StrongFocus)
        layout.addWidget(self.coronal_viewer)

        # ← 关键：下方添加弹性空间（使内容向上推）
        layout.addStretch()

        return group

    def _create_file_info(self):
        """创建文件信息面板"""
        group = QGroupBox("文件信息")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 信息标签
        self.info_labels = {}
        info_fields = [
            ("file_name", "文件名:"),
            ("file_type", "类型:"),
            ("file_status", "状态:"),
            ("file_size", "大小:"),
            ("file_path", "路径:"),
            ("file_used_by", "使用过:")
        ]

        for key, label_text in info_fields:
            label = QLabel(f"{label_text} —")
            label.setStyleSheet("font-size: 11px; color: #888;")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(label)
            self.info_labels[key] = label

        layout.addStretch()

        # 操作按钮
        btn_layout1 = QHBoxLayout()

        self.use_t1_btn = QPushButton("设为 T1w")
        self.use_t1_btn.clicked.connect(lambda: self._use_file("T1w"))
        self.use_t1_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3a8eef;
            }
        """)
        btn_layout1.addWidget(self.use_t1_btn)

        self.use_t2_btn = QPushButton("设为 T2w")
        self.use_t2_btn.clicked.connect(lambda: self._use_file("T2w"))
        self.use_t2_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3a8eef;
            }
        """)
        btn_layout1.addWidget(self.use_t2_btn)

        layout.addLayout(btn_layout1)

        btn_layout2 = QHBoxLayout()

        self.use_bold_btn = QPushButton("设为 BOLD")
        self.use_bold_btn.clicked.connect(lambda: self._use_file("BOLD"))
        self.use_bold_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #e88e00;
            }
        """)
        btn_layout2.addWidget(self.use_bold_btn)

        self.remove_btn = QPushButton("移除")
        self.remove_btn.clicked.connect(self._remove_current_file)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
        """)
        btn_layout2.addWidget(self.remove_btn)

        layout.addLayout(btn_layout2)

        return group

    # 修改 _refresh_tree 方法
    def _refresh_tree(self):
        """刷新文件树（按实验编号 → 文件类型 两级分类）"""
        self.file_tree.clear()

        # 获取所有实验编号
        subjects = self.registry.get_all_subjects()

        if not subjects:
            # 没有文件时显示提示
            empty_item = QTreeWidgetItem(["📭 暂无文件", "", "", ""])
            empty_item.setForeground(0, Qt.gray)
            self.file_tree.addTopLevelItem(empty_item)
            return

        for subject_id in subjects:
            # 创建实验编号节点
            subject_item = QTreeWidgetItem([f"🧪 {subject_id}", "", "", ""])
            subject_item.setForeground(0, Qt.darkBlue)
            subject_item.setExpanded(True)

            # 按类型分组该实验编号的文件
            subject_files = self.registry.get_files_by_subject(subject_id)

            type_groups = {
                "🧠 T1w 结构像": FileType.T1W,
                "🧠 T2w 结构像": FileType.T2W,
                "⚡ BOLD 功能像": FileType.BOLD,
                "🔬 DWI 扩散像": FileType.DWI,
                "📄 其他文件": FileType.OTHER,
            }

            for type_name, file_type in type_groups.items():
                files = [f for f in subject_files if f.file_type == file_type]
                if files:
                    type_item = QTreeWidgetItem([type_name, "", "", ""])
                    type_item.setForeground(0, Qt.darkGray)
                    type_item.setExpanded(True)

                    for f in sorted(files, key=lambda x: x.file_path.name):
                        item = QTreeWidgetItem([
                            f.file_path.name,
                            f.file_type.value,
                            f.status.value,
                            str(f.file_path.parent)
                        ])
                        item.setData(0, Qt.UserRole, str(f.file_path))
                        item.setToolTip(0, str(f.file_path))

                        # 状态颜色
                        if f.status == FileStatus.NEW:
                            item.setForeground(2, Qt.green)
                        elif f.status == FileStatus.USED:
                            item.setForeground(2, Qt.blue)
                        elif f.status == FileStatus.CONVERTED:
                            item.setForeground(2, Qt.darkGreen)

                        # ← 关键修复：添加到 type_item，不是 type_item 自己
                        type_item.addChild(item)  # ✅ 正确

                    subject_item.addChild(type_item)

            self.file_tree.addTopLevelItem(subject_item)

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
            dir_path_obj = Path(dir_path)

            for f in dir_path_obj.rglob("*.nii*"):
                if f.is_file():
                    file_type = self.registry.classify_file(str(f))
                    self.registry.add_file(str(f), file_type)
                    count += 1

            self._refresh_tree()
            self.log(f"扫描目录，添加 {count} 个文件", "SUCCESS")

    def _filter_files(self, text):
        """过滤文件"""
        # 简单实现：刷新时过滤
        self._refresh_tree()

    def _on_item_clicked(self, item, column):
        """文件被单击"""
        file_path = item.data(0, Qt.UserRole)
        if file_path:
            record = self.registry.get_file(file_path)
            if record:
                # 更新信息面板
                self._update_file_info(record)

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

    def _update_file_info(self, record):
        """更新文件信息显示"""
        self.info_labels["file_name"].setText(f"文件名：{record.file_path.name}")
        self.info_labels["file_type"].setText(f"类型：{record.file_type.value}")
        self.info_labels["file_status"].setText(f"状态：{record.status.value}")

        # 文件大小
        try:
            size_kb = record.file_path.stat().st_size / 1024
            if size_kb > 1024:
                size_str = f"{size_kb / 1024:.1f} MB"
            else:
                size_str = f"{size_kb:.1f} KB"
        except:
            size_str = "—"
        self.info_labels["file_size"].setText(f"大小：{size_str}")

        self.info_labels["file_path"].setText(f"路径：{str(record.file_path.parent)}")
        self.info_labels["file_used_by"].setText(
            f"使用过：{', '.join(record.used_by) if record.used_by else '—'}"
        )

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

            remove_action = menu.addAction("移除")
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
                self._on_item_clicked(item, 0)
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

    def _remove_current_file(self):
        """移除当前选中的文件"""
        item = self.file_tree.currentItem()
        if item:
            self._remove_file(item)

    def _use_file(self, use_type):
        """标记文件被使用"""
        item = self.file_tree.currentItem()
        if item:
            file_path = item.data(0, Qt.UserRole)
            if file_path:
                self.registry.mark_used(file_path, use_type)
                self.registry._save()
                self._refresh_tree()
                self._on_item_clicked(item, 0)
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