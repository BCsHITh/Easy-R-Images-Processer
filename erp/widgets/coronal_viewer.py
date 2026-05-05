"""
冠状面预览控件（文件管理器专用）
支持 3D 和 4D 数据，滚轮控制切片
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QImage, QPixmap, QWheelEvent
import numpy as np


class CoronalViewer(QWidget):
    """冠状面预览器（单视图）"""

    slice_changed = Signal(int)
    image_loaded = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_data = None
        self.current_slice = 0
        self.current_frame = 0
        self.image_shape = (0, 0, 0)
        self.is_4d = False
        self.spacing = [1.0, 1.0, 1.0]
        self.tr = 2.0
        self.current_file = None

        # 固定预览窗口尺寸
        self.viewer_size = QSize(280, 280)

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

        # ← 修复：图像容器 - 使用最大尺寸，而非固定尺寸
        self.image_container = QWidget()
        self.image_container.setMaximumSize(280, 280)  # ← 最大尺寸
        self.image_container.setMinimumSize(200, 200)  # ← 最小尺寸
        self.image_container.setSizePolicy(
            QSizePolicy.Expanding,  # ← 水平可扩展
            QSizePolicy.Expanding  # ← 垂直可扩展
        )
        self.image_container.setStyleSheet("background-color: #000; border: 1px solid #3e3e3e;")

        # 安装事件过滤器
        self.image_container.installEventFilter(self)

        container_layout = QVBoxLayout(self.image_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # ← 修复：图像标签 - 使用最大尺寸
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMaximumSize(280, 280)  # ← 最大尺寸
        self.image_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )
        self.image_label.setStyleSheet("background-color: #000;")
        self.image_label.setMouseTracking(True)

        # 安装事件过滤器
        self.image_label.installEventFilter(self)

        container_layout.addWidget(self.image_label)
        layout.addWidget(self.image_container, 0, Qt.AlignCenter)

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

    def eventFilter(self, obj, event):
        """事件过滤器 - 处理滚轮"""
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.Wheel:
            if isinstance(event, QWheelEvent):
                delta = event.angleDelta().y()
                if delta > 0:
                    self._next_slice()
                else:
                    self._prev_slice()
                return True  # ← 消费事件，不再传递

        return super().eventFilter(obj, event)

    def wheelEvent(self, event):
        """直接处理滚轮事件（备用方案）"""
        delta = event.angleDelta().y()
        if delta > 0:
            self._next_slice()
        else:
            self._prev_slice()
        event.accept()  # ← 消费事件

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
        """加载 NIfTI 图像（支持 3D 和 4D）"""
        try:
            import nibabel as nib

            img = nib.load(nii_path)
            data = img.get_fdata()
            self.image_shape = data.shape
            self.current_file = nii_path

            # 获取间距信息
            if img.header.get_zooms():
                self.spacing = list(img.header.get_zooms()[:3])
                if len(img.header.get_zooms()) >= 4:
                    self.tr = img.header.get_zooms()[3]

            # 判断是否是 4D 数据
            if len(data.shape) == 4:
                self.is_4d = True
                self.image_data = data
                self.current_frame = 0
                if title:
                    self.title_label.setText(f"{title} [4D: {data.shape[3]} 帧]")
                else:
                    self.title_label.setText(f"{nii_path.split('/')[-1]} [4D: {data.shape[3]} 帧]")
            else:
                self.is_4d = False
                self.image_data = data
                if title:
                    self.title_label.setText(title)
                else:
                    self.title_label.setText(nii_path.split('/')[-1])

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

        # 获取当前帧的数据
        if self.is_4d:
            data_3d = self.image_data[:, :, :, self.current_frame]
        else:
            data_3d = self.image_data

        # 冠状面 (XZ 平面，固定 Y)
        y = self.current_slice
        if y < data_3d.shape[1]:
            data = data_3d[:, y, :]

            # 归一化
            data_min = np.percentile(data, 2)
            data_max = np.percentile(data, 98)
            if data_max > data_min:
                data = np.clip(data, data_min, data_max)
                data = (data - data_min) / (data_max - data_min) * 255
            data = data.astype(np.uint8)

            # 确保 C-contiguous
            data = np.ascontiguousarray(data)

            # 创建 QImage
            h, w = data.shape
            image = QImage(data.data, w, h, w, QImage.Format_Grayscale8)
            pixmap = QPixmap.fromImage(image)

            # ← 修复：使用标签的实际尺寸进行缩放
            self.image_label.setPixmap(pixmap.scaled(
                self.image_label.size(),  # ← 使用标签当前尺寸
                Qt.KeepAspectRatio,  # ← 保持长宽比
                Qt.SmoothTransformation  # ← 平滑变换
            ))

            self.slice_label.setText(f"冠状面切片：{y + 1}/{data_3d.shape[1]}")
            self.slice_changed.emit(y)

    def _update_coord_display(self):
        """更新坐标显示"""
        if self.image_data is None:
            return

        x_mm = (self.image_shape[0] // 2) * self.spacing[0]
        y_mm = self.current_slice * self.spacing[1]
        z_mm = (self.image_shape[2] // 2) * self.spacing[2]

        if self.is_4d:
            time_sec = self.current_frame * self.tr
            self.coord_label.setText(
                f"X: {x_mm:.2f}  Y: {y_mm:.2f}  Z: {z_mm:.2f}  (mm)  |  T: {time_sec:.2f}s"
            )
        else:
            self.coord_label.setText(f"X: {x_mm:.2f}  Y: {y_mm:.2f}  Z: {z_mm:.2f}  (mm)")

    def clear(self):
        """清空显示"""
        self.image_data = None
        self.is_4d = False
        self.current_file = None
        self.title_label.setText("未加载图像")
        self.image_label.clear()
        self.coord_label.setText("X: 0.00  Y: 0.00  Z: 0.00  (mm)")
        self.slice_label.setText("冠状面切片：0/0")

    def get_current_file(self):
        """获取当前文件路径"""
        return self.current_file

    def sizeHint(self):
        """返回建议尺寸"""
        return QSize(300, 400)

    def minimumSizeHint(self):
        """返回最小尺寸"""
        return QSize(280, 350)