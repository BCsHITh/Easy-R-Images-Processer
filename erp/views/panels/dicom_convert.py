"""
DICOM 转换面板
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QFileDialog, QCheckBox, QProgressBar, QLabel, QGroupBox,
    QHBoxLayout
)
from PySide6.QtCore import QThread, Signal, Qt
from pathlib import Path

from erp.views.panels.base_panel import BasePanel
from erp.core.converter import DICOMConverter


class ConvertWorker(QThread):
    """转换工作线程"""
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, converter, dicom_dir, output_dir, compression, preserve_structure):
        super().__init__()
        self.converter = converter
        self.dicom_dir = dicom_dir
        self.output_dir = output_dir
        self.compression = compression
        self.preserve_structure = preserve_structure

    def run(self):
        try:
            result = self.converter.convert(
                dicom_dir=self.dicom_dir,
                output_dir=self.output_dir,
                compression=self.compression,
                preserve_structure=self.preserve_structure,
                progress_callback=lambda v, t: self.progress.emit(v, t)
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DicomConvertPanel(BasePanel):
    """DICOM 转换面板"""

    def __init__(self, config, parent=None):
        self.config = config
        # 跳过父类的 _init_ui，我们自己实现
        QWidget.__init__(self, parent)
        self.title = "1. DICOM 转 NIfTI"
        self.converter = None
        self.current_worker = None
        self._init_ui()

    def _init_ui(self):
        """初始化界面（无预览）"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 标题
        title_label = QLabel(self.title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a9eff;")
        layout.addWidget(title_label)

        # 工具面板（占满整个宽度）
        self.tool_panel = self._create_tool_panel()
        layout.addWidget(self.tool_panel)

        # 日志
        from erp.widgets.log_viewer import LogViewer
        self.log_viewer = LogViewer()
        layout.addWidget(self.log_viewer)

    def _create_tool_panel(self):
        """创建工具面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 参数组
        param_group = QGroupBox("转换参数")
        param_layout = QFormLayout()

        # DICOM 目录
        self.dicom_dir_edit = QLineEdit()
        self.dicom_dir_edit.setPlaceholderText("选择 DICOM 目录...")
        dicom_btn = QPushButton("浏览...")
        dicom_btn.clicked.connect(self._select_dicom_dir)

        dicom_layout = QHBoxLayout()
        dicom_layout.addWidget(self.dicom_dir_edit)
        dicom_layout.addWidget(dicom_btn)
        param_layout.addRow("DICOM 目录:", dicom_layout)

        # 输出目录
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("选择输出目录...")
        output_btn = QPushButton("浏览...")
        output_btn.clicked.connect(self._select_output_dir)

        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(output_btn)
        param_layout.addRow("输出目录:", output_layout)

        # 选项
        self.compress_check = QCheckBox("压缩输出 (.nii.gz)")
        self.compress_check.setChecked(True)
        param_layout.addRow("", self.compress_check)

        self.structure_check = QCheckBox("保持文件夹结构")
        self.structure_check.setChecked(True)
        param_layout.addRow("", self.structure_check)

        param_group.setLayout(param_layout)
        layout.addWidget(param_group)

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

        # 按钮
        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.clicked.connect(self._start_conversion)
        self.convert_btn.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #666;
            }
        """)
        layout.addWidget(self.convert_btn)

        layout.addStretch()

        return widget

    def _select_dicom_dir(self):
        """选择 DICOM 目录"""
        last_dir = self.config.last_work_dir or ""
        dir_path = QFileDialog.getExistingDirectory(self, "选择 DICOM 目录", last_dir)
        if dir_path:
            self.dicom_dir_edit.setText(dir_path)
            self.config.last_work_dir = dir_path
            if not self.output_dir_edit.text():
                self.output_dir_edit.setText(str(Path(dir_path).parent / "nii_output"))

    def _select_output_dir(self):
        """选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录", "")
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def _start_conversion(self):
        """开始转换"""
        dicom_dir = self.dicom_dir_edit.text().strip()
        output_dir = self.output_dir_edit.text().strip()

        if not dicom_dir or not output_dir:
            self.log("请选择 DICOM 目录和输出目录", "WARNING")
            return

        try:
            self.converter = DICOMConverter(self.config.dcm2niix_path)
        except FileNotFoundError as e:
            self.log(str(e), "ERROR")
            return

        self.convert_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        self.current_worker = ConvertWorker(
            self.converter,
            dicom_dir,
            output_dir,
            self.compress_check.isChecked(),
            self.structure_check.isChecked()
        )
        self.current_worker.progress.connect(self._on_progress)
        self.current_worker.finished.connect(self._on_finished)
        self.current_worker.error.connect(self._on_error)
        self.current_worker.start()

        self.log(f"开始转换：{dicom_dir} → {output_dir}")

    def _on_progress(self, value, text):
        self.progress_bar.setValue(value)
        self.progress_label.setText(text)
        self.log(text)

    def _on_finished(self, result):
        self.convert_btn.setEnabled(True)
        if result.get("success"):
            self.log(f"✅ 转换成功！生成 {len(result.get('files', []))} 个文件", "SUCCESS")
        else:
            self.log("❌ 转换失败", "ERROR")

    def _on_error(self, error_msg):
        self.convert_btn.setEnabled(True)
        self.log(error_msg, "ERROR")

    def log(self, message, level="INFO"):
        """添加日志"""
        self.log_viewer.append_log(message, level)