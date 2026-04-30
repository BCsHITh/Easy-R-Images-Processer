"""
医学影像预览控件（2x2 网格布局）
参考 ITK-SNAP 风格
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap, QWheelEvent
import numpy as np


class ImageViewer(QWidget):
    """影像预览器（2x2 网格布局）"""

    slice_changed = Signal(int, int, int)  # x, y, z 索引

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_data = None
        self.current_slices = [0, 0, 0]  # 轴状、冠状、矢状
        self.image_shape = (0, 0, 0)
        self.spacing = [1.0, 1.0, 1.0]  # 体素间距 (mm)

        self._init_ui()

    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 标题
        self.title_label = QLabel("未加载图像")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #4a9eff;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        # 2x2 网格布局
        grid_layout = QGridLayout()
        grid_layout.setSpacing(5)

        # 轴状面 (Axial) - 左上
        self.axial_widget = self._create_viewport("轴状面 (Axial)", 0)
        grid_layout.addWidget(self.axial_widget, 0, 0)

        # 冠状面 (Coronal) - 右上
        self.coronal_widget = self._create_viewport("冠状面 (Coronal)", 1)
        grid_layout.addWidget(self.coronal_widget, 0, 1)

        # 矢状面 (Sagittal) - 左下
        self.sagittal_widget = self._create_viewport("矢状面 (Sagittal)", 2)
        grid_layout.addWidget(self.sagittal_widget, 1, 0)

        # 3D 重建 (预留) - 右下
        self.viewer3d_widget = self._create_3d_viewport()
        grid_layout.addWidget(self.viewer3d_widget, 1, 1)

        layout.addLayout(grid_layout)

        # 全局坐标显示
        self.coord_label = QLabel("X: 0.00  Y: 0.00  Z: 0.00  (mm)")
        self.coord_label.setStyleSheet("color: #888; font-size: 11px; font-family: Consolas;")
        self.coord_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.coord_label)

    def _create_viewport(self, title, view_axis):
        """创建视图窗口"""
        widget = QWidget()
        widget.setStyleSheet("background-color: #000; border: 1px solid #3e3e3e;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 图像标签
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setMinimumSize(256, 256)
        image_label.setStyleSheet("background-color: #000;")

        # 启用鼠标追踪和滚轮
        image_label.setMouseTracking(True)
        image_label.installEventFilter(self)

        # 坐标信息标签
        coord_label = QLabel("X: 0.00  Y: 0.00  Z: 0.00")
        coord_label.setStyleSheet("color: #666; font-size: 10px; font-family: Consolas; background-color: #111;")
        coord_label.setAlignment(Qt.AlignCenter)
        coord_label.setFixedHeight(20)

        layout.addWidget(image_label)
        layout.addWidget(coord_label)

        # 存储引用
        widget.image_label = image_label
        widget.coord_label = coord_label
        widget.view_axis = view_axis
        widget.title = title

        return widget

    def _create_3d_viewport(self):
        """创建 3D 视图窗口（预留接口）"""
        widget = QWidget()
        widget.setStyleSheet("background-color: #0a0a0a; border: 1px solid #3e3e3e;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 占位标签
        placeholder = QLabel("3D 重建\n(暂未实现)")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #444; font-size: 14px; background-color: #0a0a0a;")
        layout.addWidget(placeholder)

        # 坐标信息
        coord_label = QLabel("—")
        coord_label.setStyleSheet("color: #444; font-size: 10px; font-family: Consolas; background-color: #111;")
        coord_label.setAlignment(Qt.AlignCenter)
        coord_label.setFixedHeight(20)
        layout.addWidget(coord_label)

        widget.placeholder = placeholder
        widget.coord_label = coord_label

        return widget

    def eventFilter(self, obj, event):
        """事件过滤器 - 处理滚轮和鼠标移动"""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QWheelEvent, QMouseEvent

        if event.type() == QEvent.Wheel:
            # 滚轮控制切片
            if isinstance(event, QWheelEvent):
                delta = event.angleDelta().y()
                if delta > 0:
                    self._next_slice()
                else:
                    self._prev_slice()
                return True

        elif event.type() == QEvent.MouseMove:
            # 鼠标移动显示坐标
            if isinstance(event, QMouseEvent):
                pos = event.pos()
                label = obj
                # 获取当前视图的切片信息
                self._update_coord_display(label, pos)

        return super().eventFilter(obj, event)

    def _next_slice(self):
        """下一切片"""
        if self.image_data is None:
            return
        # 默认控制轴状面
        self.current_slices[2] = min(self.current_slices[2] + 1, self.image_shape[2] - 1)
        self._update_all_views()

    def _prev_slice(self):
        """上一切片"""
        if self.image_data is None:
            return
        self.current_slices[2] = max(self.current_slices[2] - 1, 0)
        self._update_all_views()

    def load_image(self, nii_path, title=None):
        """加载 NIfTI 图像"""
        try:
            import nibabel as nib

            img = nib.load(nii_path)
            self.image_data = img.get_fdata()
            self.image_shape = self.image_data.shape

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

            # 初始化切片位置（居中）
            self.current_slices = [
                self.image_shape[0] // 2,
                self.image_shape[1] // 2,
                self.image_shape[2] // 2
            ]

            # 更新所有视图
            self._update_all_views()
            self._update_coord_display()

            self.log_info(f"加载图像：{self.image_shape}, 间距：{self.spacing}")

        except Exception as e:
            self.title_label.setText(f"加载失败：{str(e)}")

    def _update_all_views(self):
        """更新所有视图"""
        if self.image_data is None:
            return

        # 轴状面 (XY 平面，固定 Z)
        z = self.current_slices[2]
        if z < self.image_shape[2]:
            axial_slice = self.image_data[:, :, z]
            self._display_slice(self.axial_widget, axial_slice, 'axial')

        # 冠状面 (XZ 平面，固定 Y)
        y = self.current_slices[1]
        if y < self.image_shape[1]:
            coronal_slice = self.image_data[:, y, :]
            self._display_slice(self.coronal_widget, coronal_slice, 'coronal')

        # 矢状面 (YZ 平面，固定 X)
        x = self.current_slices[0]
        if x < self.image_shape[0]:
            sagittal_slice = self.image_data[x, :, :]
            self._display_slice(self.sagittal_widget, sagittal_slice, 'sagittal')

        # 更新坐标显示
        self._update_coord_display()

    def _display_slice(self, viewport, data, view_type):
        """显示切片"""
        if data is None or data.size == 0:
            return

        # 归一化到 0-255
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

        # 缩放适应标签
        viewport.image_label.setPixmap(pixmap.scaled(
            viewport.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))

    def _update_coord_display(self, viewport=None, mouse_pos=None):
        """更新坐标显示"""
        if self.image_data is None:
            return

        # 计算物理坐标 (mm)
        x_mm = self.current_slices[0] * self.spacing[0]
        y_mm = self.current_slices[1] * self.spacing[1]
        z_mm = self.current_slices[2] * self.spacing[2]

        # 全局坐标
        self.coord_label.setText(f"X: {x_mm:.2f}  Y: {y_mm:.2f}  Z: {z_mm:.2f}  (mm)")

        # 各视图坐标
        if viewport:
            if hasattr(viewport, 'view_axis'):
                axis = viewport.view_axis
                if axis == 0:  # Axial
                    viewport.coord_label.setText(f"X: {x_mm:.1f}  Y: {y_mm:.1f}  Z: {z_mm:.1f}")
                elif axis == 1:  # Coronal
                    viewport.coord_label.setText(f"X: {x_mm:.1f}  Y: {y_mm:.1f}  Z: {z_mm:.1f}")
                elif axis == 2:  # Sagittal
                    viewport.coord_label.setText(f"X: {x_mm:.1f}  Y: {y_mm:.1f}  Z: {z_mm:.1f}")

    def clear(self):
        """清空显示"""
        self.image_data = None
        self.title_label.setText("未加载图像")
        self.coord_label.setText("X: 0.00  Y: 0.00  Z: 0.00  (mm)")

        for viewport in [self.axial_widget, self.coronal_widget, self.sagittal_widget]:
            viewport.image_label.clear()
            viewport.coord_label.setText("X: 0.00  Y: 0.00  Z: 0.00")

    def log_info(self, message):
        """日志输出（简单打印）"""
        print(f"[ImageViewer] {message}")