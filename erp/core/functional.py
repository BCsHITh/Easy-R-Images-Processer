"""
功能像 fMRI 处理核心模块
实现运动校正、BOLD 平均化、BOLD-T1 配准等功能
"""
import logging
from pathlib import Path
from typing import Callable, Optional, List, Dict
from enum import Enum
import numpy as np
import gc
import time
import os
import tempfile
import shutil

try:
    import ants
except ImportError:
    ants = None
    logging.warning("ANTsPy 未安装，功能像处理功能将不可用")

try:
    import nibabel as nib
except ImportError:
    nib = None
    logging.warning("nibabel 未安装，部分功能将不可用")

try:
    from scipy.ndimage import zoom
except ImportError:
    zoom = None
    logging.warning("scipy.ndimage.zoom 未安装，模板重采样功能将不可用")


class ProcessingMode(Enum):
    """处理模式 - 针对实验动物优化"""
    FAST = "fast"          # 快速模式：0.5mm 分辨率 (小鼠/大鼠)
    STANDARD = "standard"  # 标准模式：0.3mm 分辨率
    HIGH_QUALITY = "high"  # 高质量：0.1mm 分辨率


class FunctionalProcessor:
    """功能像处理器（内存优化版）"""

    def __init__(self):
        self.logger = logging.getLogger("ERP.Functional")
        self._check_ants()
        self._check_nibabel()

    def _check_ants(self):
        """检查 ANTsPy 是否可用"""
        if ants is None:
            raise ImportError("ANTsPy 未安装！")

    def _check_nibabel(self):
        """检查 nibabel 是否可用"""
        if nib is None:
            raise ImportError("nibabel 未安装！")

    def _cleanup_ants_image(self, img):
        """显式清理 ANTs 图像对象"""
        if img is not None:
            try:
                del img
            except:
                pass
            gc.collect()

    def _close_nibabel_file(self, nii):
        """显式关闭 nibabel 文件句柄"""
        if nii is not None:
            try:
                if hasattr(nii, 'close'):
                    nii.close()
                if hasattr(nii, '_dataobj') and nii._dataobj is not None:
                    del nii._dataobj
            except:
                pass
            gc.collect()

    def _get_direction_3x3_from_nibabel(self, nii):
        """从 nibabel NIfTI 提取 3x3 方向矩阵（正确处理 zooms）"""
        affine = nii.affine
        zooms = nii.header.get_zooms()[:3]
        rotation = affine[:3, :3].copy()
        # 用 zooms 归一化而非列向量范数（避免 shear 导致的畸变）
        for i in range(3):
            if zooms[i] > 1e-10:
                rotation[:, i] /= zooms[i]
        return rotation

    def _resample_template(
            self,
            template_path: str,
            target_resolution: float,
            output_path: str,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> str:
        """重采样模板到目标分辨率（保持正交方向矩阵）"""
        self.logger.info(f"重采样模板：{target_resolution}mm 各向同性")

        try:
            if progress_callback:
                progress_callback(0, "重采样模板...")

            template_path = str(Path(template_path).absolute())
            output_path = str(Path(output_path).absolute())

            # 读取模板
            nii = nib.load(template_path)
            data = np.asanyarray(nii.dataobj)
            original_affine = nii.affine.copy()
            original_zooms = nii.header.get_zooms()[:3]

            self.logger.info(f"  原始形状：{data.shape}")
            self.logger.info(f"  原始分辨率：{original_zooms}")

            target_res = float(target_resolution)

            # 计算缩放因子
            scale_factors = tuple(float(z) / target_res for z in original_zooms)
            self.logger.info(f"  缩放因子：{scale_factors}")

            # 重采样
            if progress_callback:
                progress_callback(30, "执行重采样...")

            resampled_data = zoom(data, scale_factors, order=1)
            self.logger.info(f"  重采样后形状：{resampled_data.shape}")

            # 构建正交 Affine
            translation = original_affine[:3, 3].copy()
            rotation = original_affine[:3, :3].copy()
            for i in range(3):
                norm = np.linalg.norm(rotation[:, i])
                if norm > 1e-10:
                    rotation[:, i] /= norm

            # SVD 正交化
            U, S, Vt = np.linalg.svd(rotation)
            rotation = np.dot(U, Vt)

            new_zoom_matrix = np.diag([target_res, target_res, target_res])
            new_affine = np.eye(4)
            new_affine[:3, :3] = np.dot(rotation, new_zoom_matrix)
            new_affine[:3, 3] = translation

            # 创建新 NIfTI
            if progress_callback:
                progress_callback(80, "保存重采样模板...")

            new_header = nib.Nifti1Header()
            new_header.set_data_dtype(np.float32)
            new_header['pixdim'][1:4] = target_res

            new_nii = nib.Nifti1Image(
                resampled_data.astype(np.float32),
                new_affine,
                header=new_header
            )

            nib.save(new_nii, output_path)

            # 验证输出
            verify_nii = nib.load(output_path)
            self.logger.info(f"  验证形状：{verify_nii.shape}")
            self.logger.info(f"  验证分辨率：{verify_nii.header.get_zooms()[:3]}")
            self._close_nibabel_file(verify_nii)

            if progress_callback:
                progress_callback(100, "模板重采样完成")

            self.logger.info(f"  ✅ 模板重采样完成")
            return output_path

        except Exception as e:
            self.logger.error(f"  ❌ 重采样失败：{e}", exc_info=True)
            raise

    def apply_transform_to_bold(
            self,
            bold_path: str,
            transform_prefix: str,
            template_path: str,
            output_path: str,
            target_resolution: Optional[float] = None,
            secondary_transforms: Optional[List[str]] = None,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """
        应用变换到 4D BOLD 数据（支持变换链串联）

        Args:
            bold_path: BOLD 文件路径
            transform_prefix: BOLD->T1 变换文件前缀
            template_path: 目标模板路径
            output_path: 输出路径
            target_resolution: 目标分辨率
            secondary_transforms: T1->模板的变换文件列表（由外部结构像配准生成）
            progress_callback: 进度回调
        """
        self.logger.info(f"应用变换到 4D BOLD: {bold_path}")

        bold_nii = None
        template_nii = None
        template = None
        transformed_mm = None
        temp_output_path = None
        volume_img = None
        transformed_img = None

        try:
            # ========== 1. 标准化路径 ==========
            bold_path = str(Path(bold_path).absolute())
            template_path = str(Path(template_path).absolute())
            output_path = str(Path(output_path).absolute())
            transform_prefix = str(Path(transform_prefix).absolute())

            # ========== 2. 加载模板（优化内存管理） ==========
            if progress_callback:
                progress_callback(0, "加载模板...")

            template_nii = nib.load(template_path)
            template_zooms = template_nii.header.get_zooms()[:3]
            template_affine = template_nii.affine.copy()
            template_shape = template_nii.shape[:3]

            actual_template_path = template_path

            # 只有在没有预生成变换时，才允许降采样模板
            if target_resolution and secondary_transforms is None:
                current_resolution = min(template_zooms)
                if current_resolution < target_resolution * 0.8:
                    self.logger.info(f"  模板分辨率 ({current_resolution:.2f}mm) 高于目标 ({target_resolution}mm)")
                    self.logger.info(f"  正在重采样模板...")

                    template_dir = Path(template_path).parent
                    resampled_name = f"template_{target_resolution:.1f}mm.nii.gz"
                    temp_resampled_path = str(template_dir / resampled_name)

                    if not Path(temp_resampled_path).exists():
                        self._resample_template(
                            template_path,
                            float(target_resolution),
                            temp_resampled_path,
                            progress_callback=lambda v, t: progress_callback(int(v * 5 / 100),
                                                                             t) if progress_callback else None
                        )

                    self._close_nibabel_file(template_nii)
                    template_nii = nib.load(temp_resampled_path)
                    template_zooms = template_nii.header.get_zooms()[:3]
                    template_affine = template_nii.affine.copy()
                    template_shape = template_nii.shape[:3]
                    actual_template_path = temp_resampled_path

            self.logger.info(f"  目标空间形状：{template_shape}")
            self.logger.info(f"  目标分辨率：{template_zooms}")

            # 读取模板图像 (ANTs)
            if progress_callback:
                progress_callback(5, "转换模板为 ANTs 格式...")

            template = ants.image_read(actual_template_path)
            self._close_nibabel_file(template_nii)
            template_nii = None
            gc.collect()

            # ========== 3. 加载 BOLD（使用 dataobj 延迟加载） ==========
            if progress_callback:
                progress_callback(8, "加载 BOLD 数据...")

            bold_nii = nib.load(bold_path)
            bold_dataobj = bold_nii.dataobj
            n_timepoints = bold_dataobj.shape[3]

            self.logger.info(f"  BOLD 方向：{''.join(nib.orientations.aff2axcodes(bold_nii.affine))}")
            self.logger.info(f"  BOLD 形状：{bold_dataobj.shape}")

            # 获取几何信息（提前获取，避免重复访问）
            origin_3d = list(bold_nii.header.get_best_affine()[:3, 3])
            spacing_3d = list(bold_nii.header.get_zooms()[:3])
            direction_3d = self._get_direction_3x3_from_nibabel(bold_nii)

            # ========== 4. 验证并构建变换链 ==========
            transform_files = []

            # 添加 BOLD->T1 变换
            for suffix in ['_affine.mat', '_warp.nii.gz']:
                tf = f"{transform_prefix}{suffix}"
                if Path(tf).exists():
                    transform_files.append(str(Path(tf).absolute()))
                    self.logger.info(f"  ✅ BOLD->T1 变换：{transform_files[-1]}")

            # 添加 T1->模板变换（如果提供）
            if secondary_transforms:
                for tf in secondary_transforms:
                    if Path(tf).exists():
                        transform_files.append(str(Path(tf).absolute()))
                        self.logger.info(f"  ✅ T1->模板变换：{transform_files[-1]}")
                    else:
                        self.logger.warning(f"  ⚠️ 变换文件不存在：{tf}")

            if not transform_files:
                raise ValueError(f"未找到任何变换文件：{transform_prefix}*")

            time.sleep(0.5)

            # ========== 5. 创建内存映射文件 ==========
            temp_output_path = output_path.replace('.nii.gz', '_temp.nii')
            if temp_output_path == output_path:
                temp_output_path = output_path + '.temp'

            self.logger.info(f"  创建内存映射文件：{temp_output_path}")

            transformed_mm = np.memmap(
                temp_output_path,
                dtype=np.float32,
                mode='w+',
                shape=(template_shape[0], template_shape[1], template_shape[2], n_timepoints)
            )

            # ========== 6. 流式处理循环（优化内存） ==========
            for i in range(n_timepoints):
                if progress_callback:
                    progress_callback(10 + int(80 * i / n_timepoints), f"变换时间点 {i + 1}/{n_timepoints}...")

                try:
                    # 读取单个体积（立即转换为 float32）
                    volume_data = np.asarray(bold_dataobj[:, :, :, i]).astype(np.float32)

                    # 创建 ANTs 图像
                    volume_img = ants.from_numpy(
                        volume_data,
                        origin=origin_3d,
                        spacing=spacing_3d,
                        direction=direction_3d
                    )
                    del volume_data
                    volume_data = None

                    # 应用变换链
                    transformed_img = ants.apply_transforms(
                        fixed=template,
                        moving=volume_img,
                        transformlist=transform_files,
                        interpolator='linear',
                        verbose=False
                    )

                    # 写入内存映射
                    transformed_mm[:, :, :, i] = transformed_img.numpy()

                    # 立即清理
                    self._cleanup_ants_image(volume_img)
                    volume_img = None
                    self._cleanup_ants_image(transformed_img)
                    transformed_img = None

                    # 定期刷新和垃圾回收
                    if i % 50 == 0 or i == n_timepoints - 1:
                        transformed_mm.flush()
                        gc.collect()

                except Exception as e:
                    self.logger.error(f"  时间点 {i} 变换失败：{e}")
                    transformed_mm[:, :, :, i] = 0

                    # 异常时也要清理
                    if volume_img is not None:
                        self._cleanup_ants_image(volume_img)
                        volume_img = None
                    if transformed_img is not None:
                        self._cleanup_ants_image(transformed_img)
                        transformed_img = None
                    gc.collect()

            # 刷新内存映射
            if transformed_mm is not None:
                transformed_mm.flush()

            self.logger.info(f"  ✅ 流式写入完成")

            # ========== 7. 写入 NIfTI 头信息 ==========
            self.logger.info(f"  写入 NIfTI 头信息... ")

            output_header = nib.Nifti1Header()
            output_header.set_data_dtype(np.float32)
            output_header['pixdim'][1:4] = template_zooms

            # 先删除 memmap 引用，再保存
            del transformed_mm
            transformed_mm = None
            gc.collect()

            # 从文件重新加载为只读 memmap
            readonly_mm = np.memmap(
                temp_output_path,
                dtype=np.float32,
                mode='r',
                shape=(template_shape[0], template_shape[1], template_shape[2], n_timepoints)
            )

            output_img = nib.Nifti1Image(
                readonly_mm,
                template_affine,
                header=output_header
            )

            nib.save(output_img, output_path)

            del readonly_mm
            readonly_mm = None
            gc.collect()

            # 清理临时 memmap 文件
            if temp_output_path and os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                    self.logger.info(f"  清理临时文件：{temp_output_path}")
                except Exception as e:
                    self.logger.warning(f"  清理临时文件失败：{e}")

            if progress_callback:
                progress_callback(100, "变换应用完成")

            self.logger.info(f"  完成：{output_path}")

            return {
                "success": True,
                "output_path": output_path,
                "n_timepoints": n_timepoints
            }

        except Exception as e:
            self.logger.error(f"  ❌ 处理过程中断：{e}", exc_info=True)
            raise

        finally:
            self.logger.info("  清理资源...")

            if transformed_mm is not None:
                try:
                    transformed_mm.flush()
                    del transformed_mm
                except:
                    pass

            if template is not None:
                self._cleanup_ants_image(template)
                template = None
            if bold_nii is not None:
                self._close_nibabel_file(bold_nii)
                bold_nii = None
            if template_nii is not None:
                self._close_nibabel_file(template_nii)
                template_nii = None
            if volume_img is not None:
                self._cleanup_ants_image(volume_img)
                volume_img = None
            if transformed_img is not None:
                self._cleanup_ants_image(transformed_img)
                transformed_img = None

            # 确保清理临时文件
            if temp_output_path and os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                    self.logger.info(f"  清理残留临时文件：{temp_output_path}")
                except:
                    pass

            gc.collect()
            self.logger.info("  资源清理完成")

    def motion_correction(
            self,
            bold_path: str,
            output_path: str,
            reference_volume: int = 0,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """
        运动校正（内存优化版）
        使用 memmap 避免 4D 数据全量加载
        """
        self.logger.info(f"运动校正：{bold_path}")

        bold_nii = None
        reference_img = None
        volume_img = None
        corrected_mm = None
        temp_output_path = None
        volume_data = None

        try:
            # ========== 1. 加载 BOLD ==========
            bold_nii = nib.load(bold_path)
            bold_dataobj = bold_nii.dataobj

            if len(bold_dataobj.shape) != 4:
                raise ValueError(f"BOLD 数据必须是 4D，当前形状：{bold_dataobj.shape}")

            n_timepoints = bold_dataobj.shape[3]
            self.logger.info(f"  时间点数：{n_timepoints}")
            self.logger.info(f"  原始形状：{bold_dataobj.shape}")

            # 获取几何信息
            origin_3d = list(bold_nii.header.get_best_affine()[:3, 3])
            spacing_3d = list(bold_nii.header.get_zooms()[:3])
            direction_3d = self._get_direction_3x3_from_nibabel(bold_nii)

            # ========== 2. 提取参考体积 ==========
            if progress_callback:
                progress_callback(10, f"提取参考体积 (时间点 {reference_volume})...")

            reference_data = np.asarray(bold_dataobj[:, :, :, reference_volume]).astype(np.float32)
            reference_img = ants.from_numpy(
                reference_data,
                origin=origin_3d,
                spacing=spacing_3d,
                direction=direction_3d
            )
            del reference_data
            reference_data = None
            gc.collect()

            # ========== 3. 创建内存映射输出文件 ==========
            temp_output_path = output_path.replace('.nii.gz', '_temp.nii')
            if temp_output_path == output_path:
                temp_output_path = output_path + '.temp'

            self.logger.info(f"  创建内存映射文件：{temp_output_path}")

            corrected_mm = np.memmap(
                temp_output_path,
                dtype=np.float32,
                mode='w+',
                shape=bold_dataobj.shape
            )

            # ========== 4. 逐帧配准 ==========
            for i in range(n_timepoints):
                if progress_callback:
                    progress_callback(10 + int(80 * i / n_timepoints), f"校正时间点 {i + 1}/{n_timepoints}...")

                try:
                    volume_data = np.asarray(bold_dataobj[:, :, :, i]).astype(np.float32)
                    volume_img = ants.from_numpy(
                        volume_data,
                        origin=origin_3d,
                        spacing=spacing_3d,
                        direction=direction_3d
                    )
                    del volume_data
                    volume_data = None

                    if i == reference_volume:
                        corrected_mm[:, :, :, i] = volume_img.numpy()
                    else:
                        reg = ants.registration(
                            fixed=reference_img,
                            moving=volume_img,
                            type_of_transform='Rigid',
                            metric='CC',
                            verbose=False
                        )
                        corrected_mm[:, :, :, i] = reg['warpedmovout'].numpy()
                        self._cleanup_ants_image(reg.get('warpedmovout'))
                        reg = None

                    if volume_img is not None:
                        self._cleanup_ants_image(volume_img)
                        volume_img = None

                    if i % 50 == 0:
                        corrected_mm.flush()
                        gc.collect()

                except Exception as e:
                    self.logger.warning(f"  时间点 {i} 配准失败：{e}，使用原始数据")
                    if volume_data is None:
                        volume_data = np.asarray(bold_dataobj[:, :, :, i]).astype(np.float32)
                    corrected_mm[:, :, :, i] = volume_data
                    if volume_data is not None:
                        del volume_data
                        volume_data = None

                    if volume_img is not None:
                        self._cleanup_ants_image(volume_img)
                        volume_img = None

            # 刷新内存映射
            if corrected_mm is not None:
                corrected_mm.flush()

            # ========== 5. 保存结果 ==========
            output_header = nib.Nifti1Header()
            output_header.set_data_dtype(np.float32)
            output_header['pixdim'][1:4] = list(bold_nii.header.get_zooms()[:3])

            output_affine = bold_nii.affine.copy()
            output_header_obj = bold_nii.header.copy()

            # 先删除 memmap 引用
            del corrected_mm
            corrected_mm = None
            gc.collect()

            # 从文件重新加载为只读 memmap
            readonly_mm = np.memmap(
                temp_output_path,
                dtype=np.float32,
                mode='r',
                shape=bold_dataobj.shape
            )

            output_img = nib.Nifti1Image(
                readonly_mm,
                output_affine,
                header=output_header_obj
            )
            output_img.header.set_data_dtype(np.float32)

            nib.save(output_img, output_path)

            del readonly_mm
            readonly_mm = None
            gc.collect()

            # 清理临时 memmap 文件
            if temp_output_path and os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                    self.logger.info(f"  清理临时文件：{temp_output_path}")
                except Exception as e:
                    self.logger.warning(f"  清理临时文件失败：{e}")

            verify_nii = nib.load(output_path)
            verify_orientation = ''.join(nib.orientations.aff2axcodes(verify_nii.affine))
            self.logger.info(f"  输出方向：{verify_orientation}")
            self.logger.info(f"  输出形状：{verify_nii.shape}")
            self._close_nibabel_file(verify_nii)

            if progress_callback:
                progress_callback(100, "运动校正完成")

            self.logger.info(f"  运动校正完成：{output_path}")

            return {
                "success": True,
                "output_path": output_path,
                "n_timepoints": n_timepoints,
                "reference_volume": reference_volume,
                "orientation": verify_orientation
            }

        except Exception as e:
            self.logger.error(f"  ❌ 运动校正失败：{e}", exc_info=True)
            raise

        finally:
            if corrected_mm is not None:
                try:
                    corrected_mm.flush()
                    del corrected_mm
                except:
                    pass

            if temp_output_path and os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                    self.logger.info(f"  清理残留临时文件：{temp_output_path}")
                except:
                    pass

            if reference_img is not None:
                self._cleanup_ants_image(reference_img)
                reference_img = None
            if volume_img is not None:
                self._cleanup_ants_image(volume_img)
                volume_img = None
            if volume_data is not None:
                del volume_data
                volume_data = None
            if bold_nii is not None:
                self._close_nibabel_file(bold_nii)
                bold_nii = None

            gc.collect()

    def bold_mean(
            self,
            bold_path: str,
            output_path: str,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """BOLD 平均化（内存优化版）"""
        self.logger.info(f"BOLD 平均化：{bold_path}")

        bold_nii = None
        mean_img = None

        try:
            if progress_callback:
                progress_callback(0, "加载 4D BOLD 数据...")

            bold_nii = nib.load(bold_path)
            bold_dataobj = bold_nii.dataobj

            if len(bold_dataobj.shape) != 4:
                raise ValueError(f"BOLD 数据必须是 4D，当前形状：{bold_dataobj.shape}")

            n_timepoints = bold_dataobj.shape[3]
            self.logger.info(f"  时间点数：{n_timepoints}")

            if progress_callback:
                progress_callback(30, f"计算平均图像 ({n_timepoints} 时间点)...")

            # 使用分块计算避免全量加载
            shape_3d = bold_dataobj.shape[:3]
            mean_data = np.zeros(shape_3d, dtype=np.float64)

            chunk_size = 10
            for start in range(0, n_timepoints, chunk_size):
                end = min(start + chunk_size, n_timepoints)
                chunk = np.asarray(bold_dataobj[:, :, :, start:end]).astype(np.float64)
                mean_data += np.sum(chunk, axis=3)
                del chunk
                gc.collect()

                if progress_callback:
                    pct = 30 + int(40 * end / n_timepoints)
                    progress_callback(pct, f"计算平均图像 ({end}/{n_timepoints})...")

            mean_data /= n_timepoints
            mean_data = mean_data.astype(np.float32)

            origin_3d = list(bold_nii.header.get_best_affine()[:3, 3])
            spacing_3d = list(bold_nii.header.get_zooms()[:3])
            direction_3d = self._get_direction_3x3_from_nibabel(bold_nii)

            mean_img = ants.from_numpy(
                mean_data,
                origin=origin_3d,
                spacing=spacing_3d,
                direction=direction_3d
            )

            del mean_data
            mean_data = None
            gc.collect()

            if progress_callback:
                progress_callback(80, "保存平均图像...")

            ants.image_write(mean_img, output_path)
            self._cleanup_ants_image(mean_img)
            mean_img = None

            if progress_callback:
                progress_callback(100, "BOLD 平均化完成")

            self.logger.info(f"  BOLD 平均化完成：{output_path}")

            return {
                "success": True,
                "output_path": output_path,
                "n_timepoints": n_timepoints
            }

        finally:
            if mean_img is not None:
                self._cleanup_ants_image(mean_img)
                mean_img = None
            if bold_nii is not None:
                self._close_nibabel_file(bold_nii)
                bold_nii = None
            gc.collect()

    def bold_to_t1_registration(
            self,
            bold_mean_path: str,
            t1w_path: str,
            output_path: str,
            output_transform_prefix: str,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """BOLD 到 T1w 配准"""
        self.logger.info(f"BOLD 到 T1w 配准：{bold_mean_path} → {t1w_path}")

        bold_img = None
        t1w_img = None
        reg = None

        try:
            # ← 新增：检查方向一致性
            bold_nii_check = nib.load(bold_mean_path)
            t1w_nii_check = nib.load(t1w_path)

            bold_orientation = ''.join(nib.orientations.aff2axcodes(bold_nii_check.affine))
            t1w_orientation = ''.join(nib.orientations.aff2axcodes(t1w_nii_check.affine))

            self.logger.info(f"  BOLD 方向：{bold_orientation}")
            self.logger.info(f"  T1w 方向：{t1w_orientation}")

            self._close_nibabel_file(bold_nii_check)
            self._close_nibabel_file(t1w_nii_check)

            if bold_orientation != t1w_orientation:
                self.logger.warning(f"  ⚠️ BOLD 和 T1w 方向不一致！配准可能受影响")

            if progress_callback:
                progress_callback(0, "加载图像...")

            bold_img = ants.image_read(bold_mean_path)
            t1w_img = ants.image_read(t1w_path)

            if progress_callback:
                progress_callback(10, "执行刚性配准...")

            reg = ants.registration(
                fixed=t1w_img,
                moving=bold_img,
                type_of_transform='Affine',
                metric='CC',
                verbose=False
            )

            if progress_callback:
                progress_callback(80, "保存结果...")

            ants.image_write(reg['warpedmovout'], output_path)

            # 保存变换场
            transform_paths = []

            transforms_list = reg.get('fwdtransforms', [])
            if not isinstance(transforms_list, list):
                transforms_list = [transforms_list]

            for i, transform_source in enumerate(transforms_list):
                if transform_source is None:
                    continue

                transform_str = str(transform_source)

                if not Path(transform_str).exists():
                    self.logger.warning(f"  变换源文件不存在：{transform_str}")
                    continue

                if transform_str.endswith('.nii.gz'):
                    target_path = f"{output_transform_prefix}_warp.nii.gz"
                else:
                    target_path = f"{output_transform_prefix}_affine.mat"

                try:
                    target_path_abs = str(Path(target_path).absolute())
                    shutil.copy(str(transform_str), target_path_abs)

                    if Path(target_path_abs).exists():
                        with open(target_path_abs, 'rb') as f:
                            f.read(8)
                        transform_paths.append(target_path_abs)
                        self.logger.info(f"  ✅ 变换文件保存成功：{target_path_abs}")

                except Exception as e:
                    self.logger.error(f"  ❌ 保存变换文件失败：{target_path} - {e}")

            if not transform_paths:
                self.logger.error(f"  ❌ 未能保存任何变换文件")
                raise ValueError(f"变换文件保存失败：{output_transform_prefix}*")

            if progress_callback:
                progress_callback(100, "BOLD-T1 配准完成")

            self.logger.info(f"  BOLD-T1 配准完成：{output_path}")
            self.logger.info(f"  变换文件：{transform_paths}")

            return {
                "success": True,
                "output_path": output_path,
                "transform_paths": transform_paths,
                "metric_value": reg.get('metric_value')
            }

        finally:
            self._cleanup_ants_image(bold_img)
            self._cleanup_ants_image(t1w_img)
            self._cleanup_ants_image(reg.get('warpedmovout') if reg else None)
            gc.collect()

    def process_functional(
            self,
            bold_path: str,
            t1w_path: str,
            output_dir: str,
            template_path: Optional[str] = None,
            processing_mode: str = "fast",
            target_resolution: Optional[float] = None,
            do_motion_correction: bool = True,
            do_bold_mean: bool = True,
            do_bold_to_t1: bool = True,
            do_map_to_template: bool = True,
            t1_to_template_transforms: Optional[List[str]] = None,  # ← 新增
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """
        完整的功能像处理流程

        Args:
            bold_path: BOLD 文件路径
            t1w_path: T1w 文件路径
            output_dir: 输出目录
            template_path: 模板文件路径
            processing_mode: 处理模式
            target_resolution: 目标分辨率
            do_motion_correction: 是否进行运动校正
            do_bold_mean: 是否进行 BOLD 平均化
            do_bold_to_t1: 是否进行 BOLD-T1 配准
            do_map_to_template: 是否映射到模板空间
            t1_to_template_transforms: T1->模板的变换文件列表（由外部结构像配准生成）
            progress_callback: 进度回调
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if target_resolution is None:
            if processing_mode == "fast":
                target_resolution = 0.5  # 动物数据默认 0.5mm
            elif processing_mode == "standard":
                target_resolution = 0.3
            elif processing_mode == "high":
                target_resolution = 0.1
            else:
                target_resolution = 0.5

        self.logger.info(f"处理模式：{processing_mode} ({target_resolution}mm)")

        results = {
            "success": True,
            "outputs": {},
            "steps_completed": [],
            "input_bold": bold_path,
            "input_t1w": t1w_path,
            "processing_mode": processing_mode,
            "target_resolution": target_resolution
        }

        temp_files = []

        try:
            # 步骤 1: 运动校正
            if do_motion_correction:
                if progress_callback:
                    progress_callback(0, "步骤 1/4: 运动校正...")

                mc_output = str(output_dir / "bold_motion_corrected.nii.gz")
                self.motion_correction(
                    bold_path, mc_output,
                    progress_callback=lambda v, t: progress_callback(int(v * 25 / 100), t) if progress_callback else None
                )
                bold_for_mean = mc_output
                results["outputs"]["motion_corrected"] = mc_output
                results["steps_completed"].append("motion_correction")
            else:
                bold_for_mean = bold_path


            # 步骤 2: BOLD 平均化
            if do_bold_mean:
                if progress_callback:
                    progress_callback(25, "步骤 2/4: BOLD 平均化...")

                mean_output = str(output_dir / "bold_mean.nii.gz")
                self.bold_mean(
                    bold_for_mean, mean_output,
                    progress_callback=lambda v, t: progress_callback(int(25 + v * 25 / 100), t) if progress_callback else None
                )
                results["outputs"]["bold_mean"] = mean_output
                results["steps_completed"].append("bold_mean")

            # 步骤 3: BOLD 到 T1w 配准
            if do_bold_to_t1:
                if progress_callback:
                    progress_callback(50, "步骤 3/4: BOLD-T1 配准...")

                reg_output = str(output_dir / "bold_mean_to_t1w.nii.gz")
                transform_prefix = str(output_dir / "bold_to_t1w")

                self.bold_to_t1_registration(
                    mean_output, t1w_path, reg_output, transform_prefix,
                    progress_callback=lambda v, t: progress_callback(int(50 + v * 25 / 100), t) if progress_callback else None
                )
                results["outputs"]["bold_to_t1w"] = reg_output
                results["outputs"]["bold_to_t1w_transform"] = transform_prefix
                results["steps_completed"].append("bold_to_t1_registration")

                time.sleep(1.0)

            # 步骤 4: 映射到模板空间
            if do_map_to_template and template_path:
                if progress_callback:
                    progress_callback(75, "步骤 4/4: 映射到模板空间...")

                template_output = str(output_dir / "bold_in_template_space.nii.gz")

                # t1_to_template_transforms = self.params.get('t1_to_template_transforms', None)

                # self.apply_transform_to_bold(
                #     mc_output,
                #     results["outputs"]["bold_to_t1w_transform"],
                #     template_path,
                #     template_output,
                #     target_resolution=target_resolution,
                #     secondary_transforms=t1_to_template_transforms,  # ← 传递变换链
                #     progress_callback=lambda v, t: progress_callback(int(75 + v * 25 / 100),
                #                                                      t) if progress_callback else None
                # )
                self.apply_transform_to_bold(
                    mc_output,
                    results["outputs"]["bold_to_t1w_transform"],
                    template_path,
                    template_output,
                    target_resolution=target_resolution,
                    secondary_transforms=t1_to_template_transforms,  # ← 新增
                    progress_callback=lambda v, t: progress_callback(int(75 + v * 25 / 100),
                                                                     t) if progress_callback else None
                )
                results["outputs"]["bold_in_template"] = template_output
                results["steps_completed"].append("map_to_template")

            if progress_callback:
                progress_callback(100, "功能像处理完成")

            self.logger.info(f"功能像处理完成：{results['steps_completed']}")

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)
            self.logger.error(f"功能像处理失败：{e}", exc_info=True)
            if progress_callback:
                progress_callback(100, f"处理失败：{e}")

        finally:
            # 清理临时文件
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        self.logger.info(f"  清理临时文件：{temp_file}")
                except:
                    pass

            gc.collect()

        return results

    def _reorient_to_LIP(self, nii_path: str, output_path: str) -> str:
        """
        强制将图像方向统一为 LIP
        通过修改 Affine 矩阵实现（不重采样数据）
        """
        self.logger.info(f"统一方向到 LIP：{nii_path}")

        nii = nib.load(nii_path)
        data = nii.get_fdata()
        original_affine = nii.affine.copy()

        current_orientation = ''.join(nib.orientations.aff2axcodes(original_affine))
        self.logger.info(f"  当前方向：{current_orientation}")

        if current_orientation == "LIP":
            self.logger.info(f"  已是 LIP 方向，跳过")
            shutil.copy(nii_path, output_path)
            return output_path

        zooms = nii.header.get_zooms()[:3]
        self.logger.info(f"  体素大小：{zooms}")

        from nibabel import orientations

        current_ornt = orientations.axcodes2ornt(current_orientation)
        target_ornt = orientations.axcodes2ornt("LIP")

        self.logger.info(f"  当前方向编码：{current_ornt}")
        self.logger.info(f"  目标方向编码：{target_ornt}")

        transform = orientations.ornt_transform(current_ornt, target_ornt)
        self.logger.info(f"  变换矩阵：\n{transform}")

        reoriented_data = orientations.apply_orientation(data, transform)
        new_affine = orientations.inv_ornt_aff(transform, data.shape) @ original_affine

        self.logger.info(f"  新 Affine:\n{new_affine}")

        new_orientation = ''.join(nib.orientations.aff2axcodes(new_affine))
        self.logger.info(f"  新方向：{new_orientation}")

        new_nii = nib.Nifti1Image(
            reoriented_data.astype(np.float32),
            new_affine,
            header=nii.header
        )
        new_nii.header.set_data_dtype(np.float32)

        nib.save(new_nii, output_path)

        verify_nii = nib.load(output_path)
        verify_orientation = ''.join(nib.orientations.aff2axcodes(verify_nii.affine))
        self.logger.info(f"  验证方向：{verify_orientation}")
        self._close_nibabel_file(verify_nii)

        if verify_orientation != "LIP":
            self.logger.warning(f"  ⚠️ 方向仍为 {verify_orientation}，非 LIP")

        self.logger.info(f"  ✅ 方向统一完成")
        return output_path

    def _downsample_template(
            self,
            template_path: str,
            target_resolution: float,
            output_path: str,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> str:
        """
        对模板进行降采样，降低分辨率
        """
        from scipy.ndimage import zoom

        self.logger.info(f"=== 模板降采样 ===")
        self.logger.info(f"输入：{template_path}")
        self.logger.info(f"输出：{output_path}")
        self.logger.info(f"目标分辨率：{target_resolution}mm")

        try:
            if progress_callback:
                progress_callback(0, "读取模板...")

            nii = nib.load(template_path)
            data = np.asanyarray(nii.dataobj)
            original_affine = nii.affine.copy()
            original_zooms = nii.header.get_zooms()[:3]

            self.logger.info(f"=== 原始模板信息 ===")
            self.logger.info(f"  形状：{data.shape}")
            self.logger.info(f"  分辨率：{original_zooms}")
            self.logger.info(f"  方向：{''.join(nib.orientations.aff2axcodes(original_affine))}")

            target_res = float(target_resolution)
            scale_factors = tuple(float(z) / target_res for z in original_zooms)

            self.logger.info(f"=== 降采样计算 ===")
            self.logger.info(f"  目标分辨率：{target_res}mm")
            self.logger.info(f"  缩放因子：{scale_factors}")

            expected_shape = tuple(int(s * f) for s, f in zip(data.shape[:3], scale_factors))
            self.logger.info(f"  预期输出形状：{expected_shape}")

            estimated_size_gb = (np.prod(expected_shape) * 4) / (1024 ** 3)
            self.logger.info(f"  预估文件大小：{estimated_size_gb:.2f} GB")

            if progress_callback:
                progress_callback(20, "执行降采样...")

            resampled_data = zoom(data, scale_factors, order=1)

            self.logger.info(f"=== 降采样结果 ===")
            self.logger.info(f"  实际输出形状：{resampled_data.shape}")

            translation = original_affine[:3, 3].copy()
            rotation = original_affine[:3, :3].copy()
            for i in range(3):
                norm = np.linalg.norm(rotation[:, i])
                if norm > 1e-10:
                    rotation[:, i] /= norm

            U, S, Vt = np.linalg.svd(rotation)
            rotation = np.dot(U, Vt)

            new_zoom_matrix = np.diag([target_res, target_res, target_res])
            new_affine = np.eye(4)
            new_affine[:3, :3] = np.dot(rotation, new_zoom_matrix)
            new_affine[:3, 3] = translation

            self.logger.info(f"  新 Affine:\n{new_affine}")

            new_direction = new_affine[:3, :3].copy()
            for i in range(3):
                norm = np.linalg.norm(new_direction[:, i])
                if norm > 1e-10:
                    new_direction[:, i] /= norm
            ortho_check = np.dot(new_direction.T, new_direction)

            if not np.allclose(ortho_check, np.eye(3), atol=1e-3):
                self.logger.error(f"  ❌ 正交性验证失败！")
                raise ValueError("方向矩阵不是正交的")

            self.logger.info(f"  ✅ 正交性验证通过")

            if progress_callback:
                progress_callback(80, "保存降采样模板...")

            new_header = nib.Nifti1Header()
            new_header.set_data_dtype(np.float32)

            new_nii = nib.Nifti1Image(
                resampled_data.astype(np.float32),
                new_affine,
                header=new_header
            )

            nib.save(new_nii, output_path)

            self.logger.info(f"=== 输出验证 ===")
            verify_shape = new_nii.shape
            verify_zooms = tuple(float(new_header['pixdim'][i]) for i in range(1, 4))
            verify_dtype = new_nii.get_data_dtype()

            self.logger.info(f"  形状：{verify_shape}")
            self.logger.info(f"  分辨率：{verify_zooms}")
            self.logger.info(f"  方向：{''.join(nib.orientations.aff2axcodes(new_affine))}")
            self.logger.info(f"  数据类型：{verify_dtype}")

            if progress_callback:
                progress_callback(100, "模板降采样完成")

            self.logger.info(f"=== 模板降采样完成 ===")
            return output_path

        except Exception as e:
            self.logger.error(f"❌ 降采样失败：{e}", exc_info=True)
            raise