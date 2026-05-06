"""
Easy-R-Images-Processer
主程序入口
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from erp.views.mainwindow import MainWindow
from erp.utils.config import ConfigManager
from erp.utils.logger import setup_logger


def main():
    # 1. 初始化配置
    config = ConfigManager()

    from erp.utils.file_registry import FileRegistry
    FileRegistry._instance = None  # 重置单例

    # 2. 设置日志
    setup_logger(config.log_file)

    # 3. 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # 4. 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("Easy-R-Images-Processer")
    app.setOrganizationName("Easy-R-Lab")

    # 5. 设置样式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1e1e1e;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #3e3e3e;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: #4a9eff;
        }
    """)

    # 6. 创建主窗口
    window = MainWindow(config)
    window.show()

    # 7. 运行
    sys.exit(app.exec())


if __name__ == "__main__":
    main()