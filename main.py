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
    # 1. 初始化配置管理器
    config = ConfigManager()

    # 2. 设置日志
    setup_logger(config.log_file)

    # 3. 启用高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # 4. 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("Easy-R-Images-Processer")
    app.setOrganizationName("Easy-R-Lab")

    # 5. 创建并显示主窗口
    window = MainWindow(config)
    window.show()

    # 6. 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()