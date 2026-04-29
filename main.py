import sys
from PySide6.QtWidgets import QApplication

def main():
    app = QApplication(sys.argv)
    # TODO: 导入主窗口
    # from erp.views.mainwindow import MainWindow
    # window = MainWindow()
    # window.show()
    print("工程初始化成功！")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
