"""
功能像处理面板（完整修复版）
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QPushButton, QFormLayout, QLineEdit, QFileDialog, QComboBox,
    QProgressBar, QLabel, QMessageBox, QScrollArea, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal
from pathlib import Path

from erp.views.panels.base_panel import BasePanel


class FunctionalWorker(QThread):
    """功能像处理工作线程"""
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, processor, params):
        super().__init__()
        self.processor = processor
        self.params = params

    def run(self):
        try:
            from erp.core.functional import FunctionalProcessor

            processor = FunctionalProcessor()

            result = processor.process_functional(
                bold_path=self.params['bold_path'],
                t1w_path=self.params['t1w_path'],
                output_dir=self.params['output_dir'],
                template_path=self.params.get('template_path'),
                processing_mode=self.params.get('processing_mode', 'fast'),
                target_resolution=self.params.get('target_resolution'),
                do_motion_correction=self.params.get('do_motion_correction', True),
                do_bold_mean=self.params.get('do_bold_mean', True),
                do_bold_to_t1=self.params.get('do_bold_to_t1', True),
                do_map_to_template=self.params.get('do_map_to_template', True),
                progress_callback=lambda v, t: self.progress.emit(v, t)
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class FunctionalPanel(BasePanel):
    """功能像处理面板"""

    def __init__(self, config, parent=None, with_preview=True):
        self.config = config
        self.processor = None
        self.current_worker = None
        super().__init__("4. 功能像处理", parent, with_preview)

    def _create_tool_panel(self):
        """创建工具面板（完整修复版）"""
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

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # ========== 1. BOLD 文件选择 ==========
        bold_group = QGroupBox("📁 BOLD 序列文件（4D）")
        bold_layout = QHBoxLayout()

        self.bold_edit = QLineEdit()
        self.bold_edit.setPlaceholderText("从文件管理器选择或浏览...")
        self.bold_edit.setReadOnly(True)
        bold_btn = QPushButton("浏览")
        bold_btn.setFixedWidth(60)
        bold_btn.clicked.connect(lambda: self._select_file(self.bold_edit, "BOLD"))

        bold_layout.addWidget(self.bold_edit)
        bold_layout.addWidget(bold_btn)
        bold_group.setLayout(bold_layout)
        layout.addWidget(bold_group)

        # ========== 2. T1w 参考文件 ==========
        t1w_group = QGroupBox("📁 T1w 结构像参考（已配准到模板）")
        t1w_layout = QHBoxLayout()

        self.t1w_edit = QLineEdit()
        self.t1w_edit.setPlaceholderText("从文件管理器选择或浏览...")
        self.t1w_edit.setReadOnly(True)
        t1w_btn = QPushButton("浏览")
        t1w_btn.setFixedWidth(60)
        t1w_btn.clicked.connect(lambda: self._select_file(self.t1w_edit, "T1w"))

        t1w_layout.addWidget(self.t1w_edit)
        t1w_layout.addWidget(t1w_btn)
        t1w_group.setLayout(t1w_layout)
        layout.addWidget(t1w_group)

        # ========== 3. 模板文件 ==========
        template_group = QGroupBox("📁 模板文件（可选）")
        template_layout = QHBoxLayout()

        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("选择模板文件...")
        template_btn = QPushButton("浏览")
        template_btn.setFixedWidth(60)
        template_btn.clicked.connect(lambda: self._select_file(self.template_edit, "模板"))

        template_layout.addWidget(self.template_edit)
        template_layout.addWidget(template_btn)
        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        # ← 新增：模板信息标签
        self.template_info_label = QLabel("模板信息：未选择")
        self.template_info_label.setStyleSheet("color: #888; font-size: 10px;")
        self.template_info_label.setWordWrap(True)
        layout.addWidget(self.template_info_label)

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

        # ========== 5. 处理模式/分辨率选择 ==========
        mode_group = QGroupBox("⚙️ 处理模式")
        mode_layout = QHBoxLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("🚀 快速模式 (0.5mm)", "0.5")
        self.mode_combo.addItem("⚖️ 标准模式 (0.3mm)", "0.3")
        self.mode_combo.addItem("🔬 高质量 (0.2mm)", "0.2")
        self.mode_combo.addItem("📐 自定义", "custom")
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.setToolTip("快速模式：内存占用低，速度快\n标准模式：平衡质量和速度\n高质量：最高分辨率，内存需求高")
        self.mode_combo.setMinimumWidth(180)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        mode_layout.addWidget(QLabel("目标分辨率:"))
        mode_layout.addWidget(self.mode_combo)

        # ← 关键修复：创建 resolution_spin
        self.resolution_spin = QDoubleSpinBox()
        self.resolution_spin.setRange(0.1, 5.0)
        self.resolution_spin.setValue(0.5)
        self.resolution_spin.setSingleStep(0.1)
        self.resolution_spin.setSuffix(" mm")
        self.resolution_spin.setEnabled(False)
        self.resolution_spin.setMinimumWidth(100)
        mode_layout.addWidget(self.resolution_spin)

        mode_layout.addStretch()
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # ========== 6. 处理流程 ==========
        process_group = QGroupBox("⚙️ 处理流程")
        process_layout = QVBoxLayout()
        process_layout.setSpacing(5)

        self.motion_check = QCheckBox("① 运动校正（所有时间点配准）")
        self.motion_check.setChecked(True)
        process_layout.addWidget(self.motion_check)

        self.mean_check = QCheckBox("② BOLD 平均化（生成 mean BOLD）")
        self.mean_check.setChecked(True)
        process_layout.addWidget(self.mean_check)

        self.reg_check = QCheckBox("③ BOLD 到 T1w 配准（仿射）")
        self.reg_check.setChecked(True)
        process_layout.addWidget(self.reg_check)

        self.template_check = QCheckBox("④ 映射到模板空间（需要模板文件）")
        self.template_check.setChecked(True)
        process_layout.addWidget(self.template_check)

        process_group.setLayout(process_layout)
        layout.addWidget(process_group)

        # ========== 7. 进度 ==========
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

        # ========== 8. 执行按钮 ==========
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

        scroll_area.setWidget(scroll_content)

        return scroll_area

    def _on_mode_changed(self, text):
        """模式变化时启用/禁用自定义输入"""
        if text == "📐 自定义":
            self.resolution_spin.setEnabled(True)
        else:
            self.resolution_spin.setEnabled(False)

    def _select_file(self, line_edit, file_type):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"选择{file_type}文件", "", "NIfTI Files (*.nii *.nii.gz)"
        )
        if file_path:
            line_edit.setText(file_path)

            # ← 新增：如果是模板文件，显示信息
            if file_type == "模板":
                try:
                    import nibabel as nib
                    import numpy as np
                    nii = nib.load(file_path)
                    zooms = nii.header.get_zooms()[:3]
                    shape = nii.shape[:3]
                    min_zoom = min(zooms)

                    size_gb = np.prod(shape) * 4 / (1024**3)

                    self.template_info_label.setText(
                        f"模板信息：形状{shape}, 分辨率{zooms}, 大小{size_gb:.2f}GB\n"
                        f"{'⚠️ 分辨率过高，将自动降采样' if min_zoom < 0.5 else '✅ 分辨率合适'}"
                    )
                except Exception as e:
                    self.template_info_label.setText(f"模板信息：无法读取 - {e}")

    def _select_output_dir(self):
        """选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_edit.setText(dir_path)

    def set_file(self, file_path: str, file_type: str):
        """从文件管理器设置文件"""
        if file_type == "BOLD":
            self.bold_edit.setText(file_path)
            self.log(f"已设置 BOLD: {file_path}")
        elif file_type == "T1w":
            self.t1w_edit.setText(file_path)
            self.log(f"已设置 T1w 参考：{file_path}")

    def _start_processing(self):
        """开始处理"""
        bold_path = self.bold_edit.text().strip()
        t1w_path = self.t1w_edit.text().strip()
        output_dir = self.output_edit.text().strip()

        if not bold_path:
            QMessageBox.warning(self, "警告", "请选择 BOLD 序列文件")
            return

        if not t1w_path:
            QMessageBox.warning(self, "警告", "请选择 T1w 结构像参考")
            return

        if not output_dir:
            QMessageBox.warning(self, "警告", "请选择输出目录")
            return

        # 检查 ANTsPy
        try:
            from erp.core.functional import FunctionalProcessor
            self.processor = FunctionalProcessor()
        except ImportError as e:
            QMessageBox.critical(self, "错误", str(e))
            return

        # ← 关键修复：获取分辨率设置
        mode_text = self.mode_combo.currentText()
        if mode_text == "📐 自定义":
            target_resolution = self.resolution_spin.value()
            processing_mode = "custom"
        else:
            # 从 combo box 的 data 获取分辨率
            target_resolution = float(self.mode_combo.currentData())
            processing_mode = "auto"

        # 准备参数
        params = {
            'bold_path': bold_path,
            't1w_path': t1w_path,
            'output_dir': output_dir,
            'template_path': self.template_edit.text().strip() or None,
            'processing_mode': processing_mode,
            'target_resolution': target_resolution,
            'do_motion_correction': self.motion_check.isChecked(),
            'do_bold_mean': self.mean_check.isChecked(),
            'do_bold_to_t1': self.reg_check.isChecked(),
            'do_map_to_template': self.template_check.isChecked()
        }

        # 禁用按钮
        self.run_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        # 创建工作线程
        self.current_worker = FunctionalWorker(self.processor, params)
        self.current_worker.progress.connect(self._on_progress)
        self.current_worker.finished.connect(self._on_finished)
        self.current_worker.error.connect(self._on_error)
        self.current_worker.start()

        self.log(f"开始功能像处理：{Path(bold_path).name}")
        self.log(f"目标分辨率：{target_resolution}mm")

    def _on_progress(self, value, text):
        self.progress_bar.setValue(value)
        self.progress_label.setText(text)
        self.log(text)

    def _on_finished(self, result):
        self.run_btn.setEnabled(True)
        if result.get("success"):
            steps = result.get("steps_completed", [])
            outputs = result.get("outputs", {})

            self.log(f"✅ 功能像处理完成！", "SUCCESS")
            self.log(f"完成步骤：{', '.join(steps)}")

            for step, path in outputs.items():
                if isinstance(path, str):
                    self.log(f"  {step}: {path}")

            # 自动加载结果到预览
            if "bold_in_template" in outputs:
                if hasattr(self, 'image_viewer'):
                    self.image_viewer.load_image(outputs["bold_in_template"], "模板空间 BOLD")

            QMessageBox.information(
                self,
                "处理完成",
                f"完成 {len(steps)} 个步骤\n\n"
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