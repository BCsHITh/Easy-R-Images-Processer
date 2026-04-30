"""
变换与合并面板
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QPushButton, QFormLayout,
    QLineEdit, QHBoxLayout, QComboBox, QLabel, QProgressBar,
    QFileDialog
)
from PySide6.QtCore import Qt

from erp.views.panels.base_panel import BasePanel


class TransformPanel(BasePanel):
    """变换与合并面板"""

    def __init__(self, config, parent=None):
        self.config = config
        super().__init__("5. 变换与合并", parent, with_preview=True)

    def _create_tool_panel(self):
        """创建工具面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 变换类型
        type_group = QGroupBox("变换类型")
        type_layout = QFormLayout()

        self.transform_type = QComboBox()
        self.transform_type.addItems([
            "应用变换场",
            "逆变换",
            "合并多个图像",
            "提取 ROI"
        ])
        type_layout.addRow("类型:", self.transform_type)

        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # 输入文件
        input_group = QGroupBox("输入")
        input_layout = QFormLayout()

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择输入文件...")
        input_btn = QPushButton("浏览...")
        input_btn.clicked.connect(lambda: self._select_file(self.input_edit, "输入"))

        input_path_layout = QHBoxLayout()
        input_path_layout.addWidget(self.input_edit)
        input_path_layout.addWidget(input_btn)
        input_layout.addRow("输入:", input_path_layout)

        self.transform_edit = QLineEdit()
        self.transform_edit.setPlaceholderText("选择变换文件...")
        transform_btn = QPushButton("浏览...")
        transform_btn.clicked.connect(lambda: self._select_file(self.transform_edit, "变换"))

        transform_path_layout = QHBoxLayout()
        transform_path_layout.addWidget(self.transform_edit)
        transform_path_layout.addWidget(transform_btn)
        input_layout.addRow("变换:", transform_path_layout)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 输出
        output_group = QGroupBox("输出")
        output_layout = QFormLayout()

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("选择输出路径...")
        output_btn = QPushButton("浏览...")
        output_btn.clicked.connect(self._select_output)

        output_path_layout = QHBoxLayout()
        output_path_layout.addWidget(self.output_edit)
        output_path_layout.addWidget(output_btn)
        output_layout.addRow("输出:", output_path_layout)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

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
        self.run_btn = QPushButton("执行变换")
        self.run_btn.clicked.connect(self._start_transform)
        layout.addWidget(self.run_btn)

        layout.addStretch()

        return widget

    def _select_file(self, line_edit, file_type):
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"选择{file_type}文件", "", "NIfTI Files (*.nii *.nii.gz)"
        )
        if file_path:
            line_edit.setText(file_path)

    def _select_output(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存输出文件", "", "NIfTI Files (*.nii.gz)"
        )
        if file_path:
            self.output_edit.setText(file_path)

    def _start_transform(self):
        self.log("变换与合并功能开发中...", "WARNING")