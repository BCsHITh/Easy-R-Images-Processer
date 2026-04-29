"""
日志系统
"""
import logging
from pathlib import Path


def setup_logger(log_file):
    """
    配置日志系统

    Args:
        log_file: 日志文件路径
    """
    # 创建日志目录
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # 配置日志格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger("ERP")
    logger.info("===== 程序启动 =====")
    return logger