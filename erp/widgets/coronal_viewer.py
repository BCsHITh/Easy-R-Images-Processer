"""
冠状面预览控件（文件管理器专用）
单视图设计，为文件目录留出空间
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
import numpy as np


class CoronalViewer(QWidget):
    """冠状面预览器（单视图）"""

    # 信号
    slice_changed = Signal(int)  # 切片索引
    image_loaded = Signal(str)  # 图像路径

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_data = None
        self.current_slice = 0
        self.image_shape = (0, 0, 0)
        self.spacing = [1.0, 1.0, 1.0]
        self.current_file = None

        self._init_ui()

    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 标题
        self.title_label = QLabel("未加载图像")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #4a9eff;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        # 图像显示区域
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(256, 256)
        self.image_label.setStyleSheet("background-color: #000; border: 1px solid #3e3e3e;")
        self.image_label.setMouseTracking(True)
        self.image_label.installEventFilter(self)
        layout.addWidget(self.image_label)

        # 坐标信息
        self.coord_label = QLabel("X: 0.00  Y: 0.00  Z: 0.00  (mm)")
        self.coord_label.setStyleSheet("color: #666; font-size: 10px; font-family: Consolas;")
        self.coord_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.coord_label)

        # 切片信息
        self.slice_label = QLabel("冠状面切片：0/0")
        self.slice_label.setStyleSheet("color: #666; font-size: 10px;")
        self.slice_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.slice_label)

        # 切片控制（可选，默认隐藏）
        self.slider_layout = QHBoxLayout()
        self.slice_slider = QLabel("🖱 滚轮切换切片")
        self.slice_slider.setStyleSheet("color: #888; font-size: 10px;")
        self.slice_slider.setAlignment(Qt.AlignCenter)
        self.slider_layout.addWidget(self.slice_slider)
        layout.addLayout(self.slider_layout)

    def eventFilter(self, obj, event):
        """事件过滤器 - 处理滚轮"""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QWheelEvent

        if event.type() == QEvent.Wheel:
            if isinstance(event, QWheelEvent):
                delta = event.angleDelta().y()
                if delta > 0:
                    self._next_slice()
                else:
                    self._prev_slice()
                return True

        return super().eventFilter(obj, event)

    def _next_slice(self):
        """下一切片"""
        if self.image_data is None:
            return
        self.current_slice = min(self.current_slice + 1, self.image_shape[1] - 1)
        self._update_view()

    def _prev_slice(self):
        """上一切片"""
        if self.image_data is None:
            return
        self.current_slice = max(self.current_slice - 1, 0)
        self._update_view()

    def load_image(self, nii_path, title=None):
        """加载 NIfTI 图像"""
        try:
            import nibabel as nib

            img = nib.load(nii_path)
            self.image_data = img.get_fdata()
            self.image_shape = self.image_data.shape
            self.current_file = nii_path

            # 获取间距信息
            if img.header.get_zooms():
                self.spacing = list(img.header.get_zooms()[:3])

            # 处理 4D 数据
            if len(self.image_data.shape) == 4:
                self.image_data = np.mean(self.image_data, axis=3)
                self.image_shape = self.image_data.shape

            # 更新标题
            if title:
                self.title_label.setText(title)
            else:
                self.title_label.setText(nii_path.split("/")[-1])

            # 初始化切片位置（居中 - 冠状面）
            self.current_slice = self.image_shape[1] // 2

            # 更新显示
            self._update_view()
            self._update_coord_display()

            # 发射信号
            self.image_loaded.emit(nii_path)

        except Exception as e:
            self.title_label.setText(f"加载失败：{str(e)}")

    def _update_view(self):
        """更新视图（冠状面）"""
        if self.image_data is None:
            return

        # 冠状面 (XZ 平面，固定 Y)
        y = self.current_slice
        if y < self.image_shape[1]:
            data = self.image_data[:, y, :]

            # 归一化
            data_min = np.percentile(data, 2)
            data_max = np.percentile(data, 98)
            if data_max > data_min:
                data = np.clip(data, data_min, data_max)
                data = (data - data_min) / (data_max - data_min) * 255
            data = data.astype(np.uint8)

            # 创建 QImage
            h, w = data.shape
            image = QImage(data.data, w, h, w, QImage.Format_Grayscale8)
            pixmap = QPixmap.fromImage(image)

            self.image_label.setPixmap(pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))

            self.slice_label.setText(f"冠状面切片：{y + 1}/{self.image_shape[1]}")
            self.slice_changed.emit(y)

    def _update_coord_display(self):
        """更新坐标显示"""
        if self.image_data is None:
            return

        x_mm = (self.image_shape[0] // 2) * self.spacing[0]
        y_mm = self.current_slice * self.spacing[1]
        z_mm = (self.image_shape[2] // 2) * self.spacing[2]

        self.coord_label.setText(f"X: {x_mm:.2f}  Y: {y_mm:.2f}  Z: {z_mm:.2f}  (mm)")

    def clear(self):
        """清空显示"""
        self.image_data = None
        self.current_file = None
        self.title_label.setText("未加载图像")
        self.image_label.clear()
        self.coord_label.setText("X: 0.00  Y: 0.00  Z: 0.00  (mm)")
        self.slice_label.setText("冠状面切片：0/0")

    def get_current_file(self):
        """获取当前文件路径"""
        return self.current_file