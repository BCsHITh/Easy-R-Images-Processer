"""
主窗口
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog,
    QProgressBar, QGroupBox, QFormLayout,
    QMessageBox, QCheckBox, QStatusBar, QMenuBar,
    QMenu, QTextEdit, QSplitter
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QDateTime
from pathlib import Path
import logging

from erp.core.converter import DICOMConverter
from erp.utils.workers import WorkerThread


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.logger = logging.getLogger("ERP")
        self.converter = None
        self.current_worker = None

        self._init_ui()
        self._init_menu()
        self._load_config()

        self.logger.info("主窗口初始化完成")

    def _init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("Easy-R-Images-Processer")
        self.setMinimumSize(900, 700)

        # 中央控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # === DICOM 转换区域 ===
        convert_group = QGroupBox("DICOM 转 NIfTI")
        convert_layout = QFormLayout()

        # DICOM 目录
        self.dicom_dir_edit = QLineEdit()
        self.dicom_dir_edit.setPlaceholderText("选择 DICOM 文件目录...")
        self.dicom_dir_btn = QPushButton("浏览...")
        self.dicom_dir_btn.clicked.connect(self._select_dicom_dir)

        dicom_dir_layout = QHBoxLayout()
        dicom_dir_layout.addWidget(self.dicom_dir_edit)
        dicom_dir_layout.addWidget(self.dicom_dir_btn)
        convert_layout.addRow("DICOM 目录:", dicom_dir_layout)

        # 输出目录
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("选择输出目录...")
        self.output_dir_btn = QPushButton("浏览...")
        self.output_dir_btn.clicked.connect(self._select_output_dir)

        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(self.output_dir_btn)
        convert_layout.addRow("输出目录:", output_dir_layout)

        # 压缩选项
        self.compress_check = QCheckBox("压缩输出文件 (.nii.gz)")
        self.compress_check.setChecked(True)
        convert_layout.addRow("", self.compress_check)

        # 转换按钮
        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.clicked.connect(self._start_conversion)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self._cancel_conversion)
        self.cancel_btn.setEnabled(False)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.convert_btn)
        btn_layout.addWidget(self.cancel_btn)
        convert_layout.addRow("", btn_layout)

        convert_group.setLayout(convert_layout)
        main_layout.addWidget(convert_group)

        # === 进度区域 ===
        progress_group = QGroupBox("转换进度")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("就绪")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)

        # === 日志区域 ===
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)

        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")

    def _init_menu(self):
        """初始化菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        # 设置 dcm2niix 路径
        set_dcm2niix_action = QAction("设置 dcm2niix 路径...", self)
        set_dcm2niix_action.triggered.connect(self._set_dcm2niix_path)
        file_menu.addAction(set_dcm2niix_action)

        file_menu.addSeparator()

        # 退出
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        # 关于
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _load_config(self):
        """加载配置"""
        # 加载 dcm2niix 路径
        dcm2niix_path = self.config.dcm2niix_path
        if dcm2niix_path:
            try:
                self.converter = DICOMConverter(dcm2niix_path)
                self._log(f"dcm2niix 路径：{dcm2niix_path}")
            except FileNotFoundError as e:
                self._log(f"⚠️ {e}")
                QMessageBox.warning(
                    self,
                    "dcm2niix 未找到",
                    str(e) + "\n\n请在 文件 → 设置 dcm2niix 路径 中配置"
                )
        else:
            self._log("⚠️ 未配置 dcm2niix 路径")

        # 加载上次工作目录
        last_dir = self.config.last_work_dir
        if last_dir:
            self.dicom_dir_edit.setText(last_dir)
            self.output_dir_edit.setText(last_dir)

    def _select_dicom_dir(self):
        """选择 DICOM 目录"""
        last_dir = self.config.last_work_dir or ""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择 DICOM 目录",
            last_dir
        )

        if dir_path:
            self.dicom_dir_edit.setText(dir_path)
            self.config.last_work_dir = dir_path

            # 如果没有设置输出目录，默认输出到 DICOM 目录的上一级
            if not self.output_dir_edit.text():
                output_dir = str(Path(dir_path).parent / "nii_output")
                self.output_dir_edit.setText(output_dir)

    def _select_output_dir(self):
        """选择输出目录"""
        last_dir = self.config.last_work_dir or ""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            last_dir
        )

        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def _set_dcm2niix_path(self):
        """设置 dcm2niix 路径"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 dcm2niix 可执行文件",
            "",
            "Executable Files (*.exe);;All Files (*)"
        )

        if file_path:
            try:
                self.converter = DICOMConverter(file_path)
                self.config.dcm2niix_path = file_path
                self._log(f"✅ dcm2niix 路径已设置：{file_path}")
                QMessageBox.information(
                    self,
                    "成功",
                    f"dcm2niix 路径已设置：\n{file_path}"
                )
            except FileNotFoundError as e:
                QMessageBox.critical(self, "错误", str(e))

    def _start_conversion(self):
        """开始转换"""
        # 验证输入
        dicom_dir = self.dicom_dir_edit.text().strip()
        output_dir = self.output_dir_edit.text().strip()

        if not dicom_dir:
            QMessageBox.warning(self, "警告", "请选择 DICOM 目录")
            return

        if not output_dir:
            QMessageBox.warning(self, "警告", "请选择输出目录")
            return

        if not self.converter:
            QMessageBox.warning(
                self,
                "警告",
                "dcm2niix 未配置\n\n请在 文件 → 设置 dcm2niix 路径 中配置"
            )
            return

        # 禁用转换按钮，启用取消按钮
        self.convert_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)

        # 创建转换任务
        def convert_task(progress_callback=None):
            return self.converter.convert(
                dicom_dir=dicom_dir,
                output_dir=output_dir,
                compression=self.compress_check.isChecked(),
                progress_callback=progress_callback
            )

        # 创建工作线程
        self.current_worker = WorkerThread(convert_task)
        self.current_worker.progress.connect(self._on_progress)
        self.current_worker.finished.connect(self._on_finished)
        self.current_worker.error.connect(self._on_error)
        self.current_worker.log.connect(self._log)

        # 启动线程
        self._log(f"开始转换：{dicom_dir} → {output_dir}")
        self.current_worker.start()

    def _cancel_conversion(self):
        """取消转换"""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self._log("用户取消转换")
            self.convert_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def _on_progress(self, value, text):
        """进度更新"""
        self.progress_bar.setValue(value)
        self.progress_label.setText(text)
        self.statusBar.showMessage(text)

    def _on_finished(self, result):
        """转换完成"""
        self.convert_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        if result.get("success"):
            file_count = result.get("file_count", 0)
            self._log(f"✅ 转换成功！生成 {file_count} 个文件")
            self._log(f"输出目录：{result.get('output_dir')}")

            QMessageBox.information(
                self,
                "转换成功",
                f"成功转换 {file_count} 个文件\n\n输出目录：\n{result.get('output_dir')}"
            )
        else:
            self._log("❌ 转换失败")
            QMessageBox.critical(self, "错误", "转换失败")

    def _on_error(self, error_msg):
        """发生错误"""
        self.convert_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._log(f"❌ {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)

    def _log(self, message):
        """添加日志"""
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
        log_msg = f"[{timestamp}] {message}"
        self.log_text.append(log_msg)
        self.logger.info(message)

    def _show_about(self):
        """显示关于对话框"""
        from erp import __version__

        QMessageBox.about(
            self,
            "关于 Easy-R-Images-Processer",
            f"<h2>Easy-R-Images-Processer</h2>"
            f"<p>版本：{__version__}</p>"
            f"<p>小鼠/兔子脑 MRI 序列管理与后处理工具</p>"
            f"<p>功能：DICOM 转 NIfTI、影像配准、3D 重建等</p>"
        )

    def closeEvent(self, event):
        """关闭窗口事件"""
        if self.current_worker and self.current_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认退出",
                "转换任务正在进行中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.current_worker.cancel()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# 需要导入 QDateTime
from PySide6.QtCore import QDateTime
from pathlib import Path