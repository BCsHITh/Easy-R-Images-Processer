"""
结构像处理面板
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QPushButton, QFormLayout, QLineEdit, QFileDialog, QComboBox,
    QProgressBar, QLabel
)
from PySide6.QtCore import Qt

from erp.views.panels.base_panel import BasePanel


class StructuralPanel(BasePanel):
    """结构像处理面板"""

    def __init__(self, config, parent=None):
        self.config = config
        super().__init__("3. 结构像处理", parent, with_preview=True)

    def _create_tool_panel(self):
        """创建工具面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 输入文件组
        input_group = QGroupBox("输入文件")
        input_layout = QFormLayout()

        self.t1w_edit = QLineEdit()
        self.t1w_edit.setPlaceholderText("选择 T1w 文件...")
        t1w_btn = QPushButton("浏览...")
        t1w_btn.clicked.connect(lambda: self._select_file(self.t1w_edit, "T1w"))

        t1w_layout = QHBoxLayout()
        t1w_layout.addWidget(self.t1w_edit)
        t1w_layout.addWidget(t1w_btn)
        input_layout.addRow("T1w:", t1w_layout)

        self.t2w_edit = QLineEdit()
        self.t2w_edit.setPlaceholderText("选择 T2w 文件 (可选)...")
        t2w_btn = QPushButton("浏览...")
        t2w_btn.clicked.connect(lambda: self._select_file(self.t2w_edit, "T2w"))

        t2w_layout = QHBoxLayout()
        t2w_layout.addWidget(self.t2w_edit)
        t2w_layout.addWidget(t2w_btn)
        input_layout.addRow("T2w:", t2w_layout)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 处理流程组
        process_group = QGroupBox("处理流程")
        process_layout = QVBoxLayout()

        # 流程选项
        self.rigid_check = QCheckBox("i. 刚性配准 (T1w 对齐)")
        self.rigid_check.setChecked(True)
        process_layout.addWidget(self.rigid_check)

        self.normalize_check = QCheckBox("ii. 强度标准化")
        self.normalize_check.setChecked(True)
        process_layout.addWidget(self.normalize_check)

        self.average_check = QCheckBox("iii. 结构像平均化")
        process_layout.addWidget(self.average_check)

        self.syn_check = QCheckBox("iv. SyN 配准到模板")
        self.syn_check.setChecked(True)
        process_layout.addWidget(self.syn_check)

        self.t2_to_t1_check = QCheckBox("v. T2 配准到 T1")
        process_layout.addWidget(self.t2_to_t1_check)

        # 模板选择
        template_layout = QFormLayout()
        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("选择模板文件...")
        template_btn = QPushButton("浏览...")
        template_btn.clicked.connect(lambda: self._select_file(self.template_edit, "模板"))

        template_path_layout = QHBoxLayout()
        template_path_layout.addWidget(self.template_edit)
        template_path_layout.addWidget(template_btn)
        template_layout.addRow("模板:", template_path_layout)
        process_layout.addLayout(template_layout)

        process_group.setLayout(process_layout)
        layout.addWidget(process_group)

        # 进度组
        progress_group = QGroupBox("进度")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("就绪")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # 执行按钮
        self.run_btn = QPushButton("开始处理")
        self.run_btn.clicked.connect(self._start_processing)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a8eef;
            }
        """)
        layout.addWidget(self.run_btn)

        layout.addStretch()

        return widget

    def _select_file(self, line_edit, file_type):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"选择{file_type}文件", "", "NIfTI Files (*.nii *.nii.gz)"
        )
        if file_path:
            line_edit.setText(file_path)

    def _start_processing(self):
        """开始处理"""
        self.log("结构像处理功能开发中...", "WARNING")
        # 后续实现核心处理逻辑