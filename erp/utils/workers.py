"""
多线程工作线程
用于在后台执行耗时任务，避免阻塞 UI
"""
from PySide6.QtCore import QThread, Signal


class WorkerThread(QThread):
    """通用工作线程"""

    # 信号
    progress = Signal(int, str)  # 进度值，进度文本
    finished = Signal(object)  # 任务完成，返回结果
    error = Signal(str)  # 发生错误
    log = Signal(str)  # 日志消息

    def __init__(self, task_func, *args, **kwargs):
        """
        初始化工作线程

        Args:
            task_func: 要执行的任务函数
            *args: 任务函数的参数
            **kwargs: 任务函数的关键字参数
        """
        super().__init__()
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs
        self._is_cancelled = False

    def run(self):
        """执行任务"""
        try:
            self.log.emit("开始执行任务...")
            result = self.task_func(
                *self.args,
                **self.kwargs,
                progress_callback=self._progress_callback
            )

            if not self._is_cancelled:
                self.progress.emit(100, "完成")
                self.finished.emit(result)
                self.log.emit("任务完成")
        except Exception as e:
            error_msg = f"任务执行失败：{str(e)}"
            self.log.emit(error_msg)
            self.error.emit(error_msg)

    def _progress_callback(self, value, text):
        """进度回调"""
        if not self._is_cancelled:
            self.progress.emit(value, text)

    def cancel(self):
        """取消任务"""
        self._is_cancelled = True
        self.log.emit("任务已取消")