"""
DICOM 转 NIfTI 转换器
"""
import subprocess
import shutil
from pathlib import Path
from typing import Callable, Optional


class DICOMConverter:
    """DICOM 到 NIfTI 转换器"""

    def __init__(self, dcm2niix_path: str = ""):
        """
        初始化转换器

        Args:
            dcm2niix_path: dcm2niix 可执行文件路径
        """
        self.dcm2niix_path = dcm2niix_path
        self._find_dcm2niix()

    def _find_dcm2niix(self):
        """自动查找 dcm2niix"""
        if not self.dcm2niix_path:
            # 尝试在系统 PATH 中查找
            exe_path = shutil.which("dcm2niix")
            if exe_path:
                self.dcm2niix_path = exe_path
                return

            # 尝试在 tools 目录查找
            tools_path = Path("tools/dcm2niix.exe")
            if tools_path.exists():
                self.dcm2niix_path = str(tools_path.absolute())
                return

            # 尝试在 Conda 环境查找
            conda_paths = [
                Path("miniconda3/envs/erp-env/Library/bin/dcm2niix.exe"),
                Path("Anaconda3/envs/erp-env/Library/bin/dcm2niix.exe"),
            ]
            for p in conda_paths:
                if p.exists():
                    self.dcm2niix_path = str(p.absolute())
                    return

        # 验证路径
        if self.dcm2niix_path and not Path(self.dcm2niix_path).exists():
            raise FileNotFoundError(
                f"dcm2niix 未找到：{self.dcm2niix_path}\n"
                "请在设置中配置 dcm2niix 路径，或将 dcm2niix.exe 放入 tools/ 目录"
            )

    def convert(
            self,
            dicom_dir: str,
            output_dir: str,
            compression: bool = True,
            filename_pattern: str = "%p_%s",
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> dict:
        """
        转换 DICOM 到 NIfTI

        Args:
            dicom_dir: DICOM 文件目录
            output_dir: 输出目录
            compression: 是否压缩输出文件
            filename_pattern: 文件名模式
            progress_callback: 进度回调函数 (value, text)

        Returns:
            dict: 转换结果信息

        Raises:
            FileNotFoundError: dcm2niix 未找到
            RuntimeError: 转换失败
        """
        if progress_callback:
            progress_callback(0, "准备转换...")

        # 验证输入目录
        dicom_path = Path(dicom_dir)
        if not dicom_path.exists():
            raise FileNotFoundError(f"DICOM 目录不存在：{dicom_dir}")

        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(10, "查找 dcm2niix...")

        # 构建命令
        cmd = [
            self.dcm2niix_path,
            "-o", str(output_path),
            "-f", filename_pattern,
        ]

        if compression:
            cmd.append("-z")
            cmd.append("y")  # 压缩为 .nii.gz
        else:
            cmd.append("-z")
            cmd.append("n")  # 不压缩

        # 添加源目录
        cmd.append(str(dicom_path))

        if progress_callback:
            progress_callback(20, "执行转换...")

        # 执行转换
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            # 读取输出
            stdout_lines = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    stdout_lines.append(line.strip())
                    if progress_callback:
                        # 简单解析进度
                        if "Convert" in line:
                            progress_callback(50, "转换中...")
                        elif "Write" in line:
                            progress_callback(80, "写入文件...")

            # 等待完成
            stderr = process.stderr.read()
            return_code = process.wait()

            if return_code != 0:
                raise RuntimeError(f"dcm2niix 错误：{stderr}")

            if progress_callback:
                progress_callback(100, "转换完成")

            # 查找生成的文件
            nii_files = list(output_path.glob("*.nii*"))

            return {
                "success": True,
                "output_dir": str(output_path),
                "files": [str(f) for f in nii_files],
                "file_count": len(nii_files),
                "log": stdout_lines
            }

        except Exception as e:
            raise RuntimeError(f"转换过程出错：{str(e)}")

    def set_path(self, path: str):
        """设置 dcm2niix 路径"""
        self.dcm2niix_path = path
        self._find_dcm2niix()