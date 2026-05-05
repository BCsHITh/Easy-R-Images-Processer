"""
功能像处理面板（支持文件管理器联动）
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QCheckBox, QPushButton,
    QFormLayout, QLineEdit, QHBoxLayout, QFileDialog,
    QProgressBar, QLabel
)
from PySide6.QtCore import Qt

from erp.views.panels.base_panel import BasePanel


class FunctionalPanel(BasePanel):
    """功能像处理面板"""

    def __init__(self, config, parent=None, with_preview=True):
        self.config = config
        # ← 关键：正确传递 with_preview 给父类
        super().__init__("4. 功能像处理", parent, with_preview)

    def _create_tool_panel(self):
        """创建工具面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 输入文件
        input_group = QGroupBox("输入文件")
        input_layout = QFormLayout()

        self.bold_edit = QLineEdit()
        self.bold_edit.setPlaceholderText("从文件管理器选择或浏览...")
        self.bold_edit.setReadOnly(True)
        bold_btn = QPushButton("浏览...")
        bold_btn.clicked.connect(lambda: self._select_file(self.bold_edit, "BOLD"))

        bold_layout = QHBoxLayout()
        bold_layout.addWidget(self.bold_edit)
        bold_layout.addWidget(bold_btn)
        input_layout.addRow("BOLD:", bold_layout)

        self.t1w_ref_edit = QLineEdit()
        self.t1w_ref_edit.setPlaceholderText("从文件管理器选择或浏览...")
        self.t1w_ref_edit.setReadOnly(True)
        t1w_btn = QPushButton("浏览...")
        t1w_btn.clicked.connect(lambda: self._select_file(self.t1w_ref_edit, "T1w"))

        t1w_layout = QHBoxLayout()
        t1w_layout.addWidget(self.t1w_ref_edit)
        t1w_layout.addWidget(t1w_btn)
        input_layout.addRow("T1w 参考:", t1w_layout)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 处理流程
        process_group = QGroupBox("处理流程")
        process_layout = QVBoxLayout()

        self.mean_check = QCheckBox("i. BOLD 平均化")
        self.mean_check.setChecked(True)
        process_layout.addWidget(self.mean_check)

        self.motion_check = QCheckBox("ii. 运动校准 (刚性配准)")
        self.motion_check.setChecked(True)
        process_layout.addWidget(self.motion_check)

        self.register_check = QCheckBox("iii. BOLD 映射到 T1w")
        self.register_check.setChecked(True)
        process_layout.addWidget(self.register_check)

        process_group.setLayout(process_layout)
        layout.addWidget(process_group)

        # 进度
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
        layout.addWidget(self.run_btn)

        layout.addStretch()

        return widget

    def _select_file(self, line_edit, file_type):
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"选择{file_type}文件", "", "NIfTI Files (*.nii *.nii.gz)"
        )
        if file_path:
            line_edit.setText(file_path)

    def set_file(self, file_path: str, file_type: str):
        """从文件管理器设置文件"""
        if file_type == "BOLD":
            self.bold_edit.setText(file_path)
            self.log(f"已设置 BOLD: {file_path}")
        elif file_type == "T1w":
            self.t1w_ref_edit.setText(file_path)
            self.log(f"已设置 T1w 参考：{file_path}")

    def _start_processing(self):
        self.log("功能像处理功能开发中...", "WARNING")