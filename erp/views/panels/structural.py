"""
结构像处理面板（支持批量处理）
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QPushButton, QFormLayout, QLineEdit, QFileDialog, QComboBox,
    QProgressBar, QLabel, QMessageBox, QListWidget, QListWidgetItem,
    QAbstractItemView,QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal

from erp.views.panels.base_panel import BasePanel
from erp.core.processor import StructuralProcessor
from pathlib import Path


class StructuralWorker(QThread):
    """结构像处理工作线程"""
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, processor, params):
        super().__init__()
        self.processor = processor
        self.params = params

    def run(self):
        try:
            result = self.processor.process_structural(
                t1w_paths=self.params['t1w_paths'],  # ← 支持列表
                output_dir=self.params['output_dir'],
                t2w_path=self.params.get('t2w_path'),
                template_path=self.params.get('template_path'),
                do_rigid=self.params.get('do_rigid', True),
                do_normalize=self.params.get('do_normalize', True),
                do_average=self.params.get('do_average', True),
                do_syn=self.params.get('do_syn', False),
                do_t2_to_t1=self.params.get('do_t2_to_t1', False),
                progress_callback=lambda v, t: self.progress.emit(v, t)
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class StructuralPanel(BasePanel):
    """结构像处理面板"""

    def __init__(self, config, parent=None, with_preview=True):
        self.config = config
        self.processor = None
        self.current_worker = None
        super().__init__("3. 结构像处理", parent, with_preview)

    def _create_tool_panel(self):
        """创建工具面板（带滚动区域）"""
        # ← 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)

        # ← 滚动区域的内容 widget
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)  # ← 减小组件间距

        # ========== 1. 实验对象筛选 ==========
        subject_group = QGroupBox("🧪 实验对象筛选")
        subject_layout = QHBoxLayout()

        subject_label = QLabel("实验编号:")
        subject_label.setStyleSheet("font-weight: bold;")
        subject_layout.addWidget(subject_label)

        self.subject_combo = QComboBox()
        self.subject_combo.setMinimumWidth(150)
        self.subject_combo.currentTextChanged.connect(self._on_subject_changed)
        subject_layout.addWidget(self.subject_combo)

        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedWidth(40)
        refresh_btn.setToolTip("刷新实验编号列表")
        refresh_btn.clicked.connect(self._refresh_subjects)
        subject_layout.addWidget(refresh_btn)

        subject_layout.addStretch()
        subject_group.setLayout(subject_layout)
        layout.addWidget(subject_group)

        # ========== 2. T1w 文件列表 ==========
        t1w_group = QGroupBox("📁 T1w 文件（可多选）")
        t1w_layout = QVBoxLayout()

        self.t1w_list = QListWidget()
        self.t1w_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.t1w_list.setMinimumHeight(80)
        self.t1w_list.setMaximumHeight(120)
        self.t1w_list.itemDoubleClicked.connect(self._remove_t1w_item)
        t1w_layout.addWidget(self.t1w_list)

        t1w_btn_layout = QHBoxLayout()

        add_single_btn = QPushButton("➕ 单个")
        add_single_btn.setFixedWidth(70)
        add_single_btn.clicked.connect(self._add_single_t1w)
        t1w_btn_layout.addWidget(add_single_btn)

        add_multi_btn = QPushButton("➕ 多个")
        add_multi_btn.setFixedWidth(70)
        add_multi_btn.clicked.connect(self._add_multiple_t1w)
        t1w_btn_layout.addWidget(add_multi_btn)

        clear_btn = QPushButton("🗑 清空")
        clear_btn.setFixedWidth(70)
        clear_btn.clicked.connect(self._clear_t1w_list)
        t1w_btn_layout.addWidget(clear_btn)

        t1w_btn_layout.addStretch()
        t1w_layout.addLayout(t1w_btn_layout)

        self.t1w_count_label = QLabel("已选择：0 个文件")
        self.t1w_count_label.setStyleSheet("color: #888; font-size: 10px;")
        t1w_layout.addWidget(self.t1w_count_label)

        t1w_group.setLayout(t1w_layout)
        layout.addWidget(t1w_group)

        # ========== 3. T2w 文件 ==========
        t2w_group = QGroupBox("📁 T2w 文件（可选）")
        t2w_layout = QHBoxLayout()

        self.t2w_edit = QLineEdit()
        self.t2w_edit.setPlaceholderText("从文件管理器选择...")
        self.t2w_edit.setReadOnly(True)
        t2w_btn = QPushButton("浏览")
        t2w_btn.setFixedWidth(60)
        t2w_btn.clicked.connect(lambda: self._select_file(self.t2w_edit, "T2w"))

        t2w_layout.addWidget(self.t2w_edit)
        t2w_layout.addWidget(t2w_btn)
        t2w_group.setLayout(t2w_layout)
        layout.addWidget(t2w_group)

        # ========== 4. 输出目录 ==========
        output_group = QGroupBox("📂 输出目录")
        output_layout = QHBoxLayout()

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("选择输出目录...")
        output_btn = QPushButton("浏览")
        output_btn.setFixedWidth(60)
        output_btn.clicked.connect(self._select_output_dir)

        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(output_btn)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # ========== 5. 处理流程 ==========
        process_group = QGroupBox("⚙️ 处理流程")
        process_layout = QVBoxLayout()
        process_layout.setSpacing(5)  # ← 更紧凑的间距

        self.rigid_check = QCheckBox("① 刚性配准（多 T1w 对齐到第一个）")
        self.rigid_check.setChecked(True)
        process_layout.addWidget(self.rigid_check)

        self.normalize_check = QCheckBox("② 强度标准化（Z-score）")
        self.normalize_check.setChecked(True)
        process_layout.addWidget(self.normalize_check)

        self.average_check = QCheckBox("③ 结构像平均化（多 T1w 平均）")
        self.average_check.setChecked(True)
        process_layout.addWidget(self.average_check)

        self.syn_check = QCheckBox("④ SyN 配准到模板")
        self.syn_check.setChecked(False)
        process_layout.addWidget(self.syn_check)

        self.t2_to_t1_check = QCheckBox("⑤ T2 配准到 T1")
        self.t2_to_t1_check.setChecked(False)
        process_layout.addWidget(self.t2_to_t1_check)

        # 模板选择（内嵌）
        template_widget = QWidget()
        template_layout = QHBoxLayout(template_widget)
        template_layout.setContentsMargins(20, 0, 0, 0)  # ← 缩进

        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("选择模板文件...")
        template_btn = QPushButton("浏览")
        template_btn.setFixedWidth(60)
        template_btn.clicked.connect(lambda: self._select_file(self.template_edit, "模板"))

        template_layout.addWidget(QLabel("模板:"))
        template_layout.addWidget(self.template_edit)
        template_layout.addWidget(template_btn)

        process_layout.addWidget(template_widget)

        process_group.setLayout(process_layout)
        layout.addWidget(process_group)

        # ========== 6. 进度 ==========
        progress_group = QGroupBox("📊 进度")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(25)
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("就绪")
        self.progress_label.setStyleSheet("color: #888; font-size: 11px;")
        progress_layout.addWidget(self.progress_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # ========== 7. 执行按钮 ==========
        self.run_btn = QPushButton("▶ 开始处理")
        self.run_btn.setFixedHeight(45)
        self.run_btn.clicked.connect(self._start_processing)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #3a8eef;
            }
            QPushButton:disabled {
                background-color: #666;
            }
        """)
        layout.addWidget(self.run_btn)

        layout.addStretch()

        # ← 将内容 widget 放入滚动区域
        scroll_area.setWidget(scroll_content)

        return scroll_area

    def _refresh_subjects(self):
        """刷新实验编号列表"""
        from erp.utils.file_registry import FileRegistry
        registry = FileRegistry()
        subjects = registry.get_all_subjects()

        self.subject_combo.blockSignals(True)
        self.subject_combo.clear()
        self.subject_combo.addItem("全部", "")
        for s in subjects:
            self.subject_combo.addItem(f"🧪 {s}", s)
        self.subject_combo.blockSignals(False)

    def _on_subject_changed(self, text):
        """实验编号变化时筛选文件"""
        subject_id = self.subject_combo.currentData()
        # 可以在此处筛选 T1w 列表
        pass

    def _add_single_t1w(self):
        """添加单个 T1w 文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 T1w 文件", "", "NIfTI Files (*.nii *.nii.gz)"
        )
        if file_path:
            self._add_t1w_to_list(file_path)

    def _add_multiple_t1w(self):
        """添加多个 T1w 文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择多个 T1w 文件", "", "NIfTI Files (*.nii *.nii.gz)"
        )
        for f in files:
            self._add_t1w_to_list(f)

    def _add_t1w_to_list(self, file_path):
        """添加文件到 T1w 列表"""
        # 检查是否已存在
        for i in range(self.t1w_list.count()):
            if self.t1w_list.item(i).data(Qt.UserRole) == file_path:
                return

        item = QListWidgetItem(Path(file_path).name)
        item.setData(Qt.UserRole, file_path)
        item.setToolTip(file_path)
        self.t1w_list.addItem(item)

        self._update_t1w_count()
        self.log(f"添加 T1w: {Path(file_path).name}")

    def _remove_t1w_item(self, item):
        """双击移除 T1w 文件"""
        row = self.t1w_list.row(item)
        if row >= 0:
            self.t1w_list.takeItem(row)
            self._update_t1w_count()

    def _clear_t1w_list(self):
        """清空 T1w 列表"""
        self.t1w_list.clear()
        self._update_t1w_count()

    def _update_t1w_count(self):
        """更新 T1w 文件计数"""
        count = self.t1w_list.count()
        self.t1w_count_label.setText(f"已选择：{count} 个文件")

        # 至少需要 1 个文件
        self.run_btn.setEnabled(count >= 1)

    def _select_file(self, line_edit, file_type):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"选择{file_type}文件", "", "NIfTI Files (*.nii *.nii.gz)"
        )
        if file_path:
            line_edit.setText(file_path)

    def _select_output_dir(self):
        """选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_edit.setText(dir_path)

    def set_file(self, file_path: str, file_type: str):
        """从文件管理器设置文件"""
        if file_type == "T1w":
            self._add_t1w_to_list(file_path)
        elif file_type == "T2w":
            self.t2w_edit.setText(file_path)
            self.log(f"已设置 T2w: {file_path}")

    def _start_processing(self):
        """开始处理"""
        # 获取所有选中的 T1w 文件
        t1w_paths = []
        # for i in range(self.t1w_list.count()):
        #     t1w_paths.append(self.t1w_list.item(i).data(Qt.UserRole))
        #
        # output_dir = self.output_edit.text().strip()
        for i in range(self.t1w_list.count()):
            item = self.t1w_list.item(i)
            path = item.data(Qt.UserRole)

            # ← 新增：双重检查数据类型
            if isinstance(path, str) and path:
                t1w_paths.append(path)
            else:
                self.log(f"警告：跳过无效的 T1w 路径项 (类型：{type(path)})")

        output_dir = self.output_edit.text().strip()

        if len(t1w_paths) == 0:
            QMessageBox.warning(self, "警告", "请至少选择 1 个 T1w 文件")
            return

        if not output_dir:
            QMessageBox.warning(self, "警告", "请选择输出目录")
            return

        # 检查 ANTsPy
        try:
            self.processor = StructuralProcessor()
        except ImportError as e:
            QMessageBox.critical(self, "错误", str(e))
            return

        # 准备参数
        params = {
            't1w_paths': t1w_paths,
            'output_dir': output_dir,
            't2w_path': self.t2w_edit.text().strip() or None,
            'template_path': self.template_edit.text().strip() or None,
            'do_rigid': self.rigid_check.isChecked(),
            'do_normalize': self.normalize_check.isChecked(),
            'do_average': self.average_check.isChecked(),
            'do_syn': self.syn_check.isChecked(),
            'do_t2_to_t1': self.t2_to_t1_check.isChecked()
        }

        # 禁用按钮
        self.run_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        # 创建工作线程
        self.current_worker = StructuralWorker(self.processor, params)
        self.current_worker.progress.connect(self._on_progress)
        self.current_worker.finished.connect(self._on_finished)
        self.current_worker.error.connect(self._on_error)
        self.current_worker.start()

        self.log(f"开始结构像处理：{len(t1w_paths)} 个 T1w 文件")

    def _on_progress(self, value, text):
        self.progress_bar.setValue(value)
        self.progress_label.setText(text)
        self.log(text)

    def _on_finished(self, result):
        self.run_btn.setEnabled(True)
        if result.get("success"):
            steps = result.get("steps_completed", [])
            outputs = result.get("outputs", {})

            self.log(f"✅ 结构像处理完成！", "SUCCESS")
            self.log(f"完成步骤：{', '.join(steps)}")

            for step, path in outputs.items():
                if isinstance(path, str):
                    self.log(f"  {step}: {path}")

            if "averaged" in outputs:
                if hasattr(self, 'image_viewer'):
                    self.image_viewer.load_image(outputs["averaged"], "平均化结果")

            QMessageBox.information(
                self,
                "处理完成",
                f"完成 {len(steps)} 个步骤\n处理 {len(result.get('input_paths', []))} 个 T1w 文件\n\n"
                f"输出目录：\n{self.output_edit.text()}"
            )
        else:
            error = result.get("error", "未知错误")
            self.log(f"❌ 处理失败：{error}", "ERROR")
            QMessageBox.critical(self, "错误", f"处理失败：\n{error}")

    def _on_error(self, error_msg):
        self.run_btn.setEnabled(True)
        self.log(error_msg, "ERROR")
        QMessageBox.critical(self, "错误", error_msg)