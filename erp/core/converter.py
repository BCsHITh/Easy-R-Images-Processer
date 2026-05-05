"""
DICOM 转 NIfTI 转换器
"""
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Callable, Optional, List


class DICOMConverter:
    """DICOM 到 NIfTI 转换器"""

    def __init__(self, dcm2niix_path: str = ""):
        """
        初始化转换器

        Args:
            dcm2niix_path: dcm2niix 可执行文件路径
        """
        self.dcm2niix_path = dcm2niix_path
        self.logger = logging.getLogger("ERP.Converter")  # ← 初始化 logger
        self._find_dcm2niix()

    def _find_dcm2niix(self):
        """自动查找 dcm2niix"""
        if not self.dcm2niix_path:
            # 尝试在系统 PATH 中查找
            exe_path = shutil.which("dcm2niix")
            if exe_path:
                self.dcm2niix_path = exe_path
                self.logger.info(f"在系统 PATH 中找到 dcm2niix: {exe_path}")
                return

            # 尝试在 tools 目录查找
            tools_path = Path("tools/dcm2niix.exe")
            if tools_path.exists():
                self.dcm2niix_path = str(tools_path.absolute())
                self.logger.info(f"在 tools 目录找到 dcm2niix: {self.dcm2niix_path}")
                return

            # 尝试在 Conda 环境查找
            conda_paths = [
                Path("miniconda3/envs/erp-env/Library/bin/dcm2niix.exe"),
                Path("Anaconda3/envs/erp-env/Library/bin/dcm2niix.exe"),
            ]
            for p in conda_paths:
                if p.exists():
                    self.dcm2niix_path = str(p.absolute())
                    self.logger.info(f"在 Conda 环境找到 dcm2niix: {self.dcm2niix_path}")
                    return

        # 验证路径
        if self.dcm2niix_path and not Path(self.dcm2niix_path).exists():
            raise FileNotFoundError(
                f"dcm2niix 未找到：{self.dcm2niix_path}\n"
                "请在设置中配置 dcm2niix 路径，或将 dcm2niix.exe 放入 tools/ 目录"
            )

        self.logger.info(f"dcm2niix 路径：{self.dcm2niix_path}")

    def _find_dicom_series(self, dicom_dir: Path) -> List[Path]:
        """
        递归查找所有包含 DICOM 文件的目录

        Args:
            dicom_dir: 根目录

        Returns:
            包含 DICOM 文件的目录列表
        """
        dicom_dirs = []

        # 检查当前目录是否包含 DICOM 文件
        dicom_extensions = {'.dcm', '.dicom', '.DCM', '.DICOM'}
        try:
            has_dicom = any(
                f.suffix.upper() in dicom_extensions or 'DICOMDIR' in f.name
                for f in dicom_dir.iterdir() if f.is_file()
            )
        except PermissionError:
            self.logger.warning(f"无权限访问目录：{dicom_dir}")
            return dicom_dirs

        if has_dicom:
            # 当前目录就是 DICOM 序列目录
            dicom_dirs.append(dicom_dir)
        else:
            # 递归检查子目录
            for subdir in dicom_dir.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('.'):
                    dicom_dirs.extend(self._find_dicom_series(subdir))

        return dicom_dirs

    def convert(
        self,
        dicom_dir: str,
        output_dir: str,
        compression: bool = True,
        filename_pattern: str = "%p_%s",
        preserve_structure: bool = True,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> dict:
        """
        转换 DICOM 到 NIfTI

        Args:
            dicom_dir: DICOM 文件目录（根目录）
            output_dir: 输出根目录
            compression: 是否压缩输出文件
            filename_pattern: 文件名模式
            preserve_structure: 是否保持原始文件夹结构
            progress_callback: 进度回调函数 (value, text)

        Returns:
            dict: 转换结果信息
        """
        if progress_callback:
            progress_callback(0, "扫描 DICOM 目录...")

        # ← 使用 Path 统一路径处理
        dicom_path = Path(dicom_dir)
        if not dicom_path.exists():
            raise FileNotFoundError(f"DICOM 目录不存在：{dicom_dir}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"开始转换：{dicom_path} → {output_path}")

        # 查找所有 DICOM 序列目录
        if progress_callback:
            progress_callback(10, "查找 DICOM 序列...")

        if preserve_structure:
            # 保持结构模式：查找所有子目录中的 DICOM 序列
            series_dirs = self._find_dicom_series(dicom_path)
        else:
            # 简单模式：整个目录作为一个序列
            series_dirs = [dicom_path]

        if not series_dirs:
            raise FileNotFoundError(f"在 {dicom_dir} 中未找到 DICOM 文件")

        total_series = len(series_dirs)
        self.logger.info(f"找到 {total_series} 个 DICOM 序列")

        # 转换结果统计
        results = {
            "success": True,
            "total_series": total_series,
            "converted_series": 0,
            "failed_series": 0,
            "files": [],
            "output_dir": str(output_path),
            "details": []
        }

        # 逐个转换每个序列
        for idx, series_dir in enumerate(series_dirs):
            try:
                if progress_callback:
                    progress = 20 + int(80 * idx / total_series)
                    progress_callback(progress, f"转换序列 {idx + 1}/{total_series}...")

                # 计算输出路径（保持相对结构）
                if preserve_structure:
                    relative_path = series_dir.relative_to(dicom_path)
                    series_output_dir = output_path / relative_path  # ← 使用 / 连接 Path
                else:
                    series_output_dir = output_path

                # 转换单个序列
                series_result = self._convert_single_series(
                    dicom_dir=series_dir,
                    output_dir=series_output_dir,
                    compression=compression,
                    filename_pattern=filename_pattern
                )

                results["converted_series"] += 1
                results["files"].extend(series_result["files"])
                results["details"].append({
                    "source": str(series_dir),
                    "output": str(series_output_dir),
                    "files": series_result["files"],
                    "success": True
                })

                self.logger.info(f"转换成功：{series_dir.name} → {len(series_result['files'])} 个文件")

            except Exception as e:
                results["failed_series"] += 1
                results["details"].append({
                    "source": str(series_dir),
                    "error": str(e),
                    "success": False
                })
                self.logger.error(f"转换失败 {series_dir}: {e}")

        # 最终统计
        if results["failed_series"] > 0:
            results["success"] = False

        if progress_callback:
            progress_callback(100, f"完成：{results['converted_series']}/{total_series} 序列")

        self.logger.info(f"转换完成：成功 {results['converted_series']}/{total_series} 序列")

        return results

    def _convert_single_series(
        self,
        dicom_dir: Path,
        output_dir: Path,
        compression: bool = True,
        filename_pattern: str = "%p_%s"
    ) -> dict:
        """
        转换单个 DICOM 序列

        Args:
            dicom_dir: DICOM 序列目录
            output_dir: 输出目录
            compression: 是否压缩
            filename_pattern: 文件名模式

        Returns:
            dict: 转换结果
        """
        # 创建输出目录
        output_dir.mkdir(parents=True, exist_ok=True)

        # 构建命令（所有路径转为字符串）
        cmd = [
            str(self.dcm2niix_path),  # ← 确保是字符串
            "-o", str(output_dir),    # ← 确保是字符串
            "-f", filename_pattern,
        ]

        if compression:
            cmd.extend(["-z", "y"])
        else:
            cmd.extend(["-z", "n"])

        cmd.append(str(dicom_dir))  # ← 确保是字符串

        self.logger.debug(f"执行命令：{' '.join(cmd)}")

        # 执行转换
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding='utf-8'
        )

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            self.logger.error(f"dcm2niix 错误：{stderr}")
            raise RuntimeError(f"dcm2niix 错误：{stderr}")

        # 查找生成的文件
        nii_files = list(output_dir.glob("*.nii*"))

        self.logger.info(f"生成 {len(nii_files)} 个 NIfTI 文件")

        return {
            "success": True,
            "output_dir": str(output_dir),
            "files": [str(f) for f in nii_files],  # ← 转为字符串
            "file_count": len(nii_files)
        }

    def set_path(self, path: str):
        """设置 dcm2niix 路径"""
        self.dcm2niix_path = path
        self._find_dcm2niix()