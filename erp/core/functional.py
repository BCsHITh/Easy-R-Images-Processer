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
import weakref

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


class ProcessingMode(Enum):
    """处理模式"""
    FAST = "fast"  # 快速模式：3mm 分辨率
    STANDARD = "standard"  # 标准模式：2mm 分辨率
    HIGH_QUALITY = "high"  # 高质量：1mm 分辨率


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
                # nibabel 4.0+ 支持 close()
                if hasattr(nii, 'close'):
                    nii.close()
                # 清理 dataobj
                if hasattr(nii, '_dataobj') and nii._dataobj is not None:
                    del nii._dataobj
            except:
                pass
            gc.collect()

    def _get_direction_3x3_from_nibabel(self, nii):
        """从 nibabel NIfTI 提取 3x3 方向矩阵"""
        affine = nii.affine
        rotation = affine[:3, :3].copy()
        for i in range(3):
            norm = np.linalg.norm(rotation[:, i])
            if norm > 1e-10:
                rotation[:, i] /= norm
        return rotation

    # def _resample_template(
    #         self,
    #         template_path: str,
    #         target_resolution: float,
    #         output_path: str,
    #         progress_callback: Optional[Callable[[int, str], None]] = None
    # ) -> str:
    #     """重采样模板到目标分辨率（修复版）"""
    #     self.logger.info(f"重采样模板：{target_resolution}mm 各向同性")
    #
    #     template = None
    #     resampled = None
    #
    #     try:
    #         if progress_callback:
    #             progress_callback(0, "重采样模板...")
    #
    #         # ← 关键修复：验证路径
    #         template_path = str(Path(template_path).absolute())
    #         output_path = str(Path(output_path).absolute())
    #
    #         self.logger.info(f"  输入路径：{template_path}")
    #         self.logger.info(f"  输出路径：{output_path}")
    #
    #         # 检查文件是否存在
    #         if not Path(template_path).exists():
    #             raise FileNotFoundError(f"模板文件不存在：{template_path}")
    #
    #         # 检查路径是否包含特殊字符
    #         if any(c in template_path for c in [' ', '中文', '()']):
    #             self.logger.warning(f"  ⚠️ 路径包含特殊字符，可能导致问题")
    #
    #         # 读取模板
    #         self.logger.info(f"  读取模板图像...")
    #         template = ants.image_read(template_path)
    #
    #         self.logger.info(f"  原始形状：{template.shape}")
    #         self.logger.info(f"  原始分辨率：{template.spacing}")
    #
    #         # ← 关键修复：确保 resample_params 是正确的类型
    #         resample_params = [float(target_resolution)] * 3
    #
    #         self.logger.info(f"  重采样参数：{resample_params}")
    #
    #         # 重采样
    #         self.logger.info(f"  执行重采样...")
    #         resampled = ants.resample_image(
    #             template,
    #             resample_params=resample_params,  # ← 使用关键字参数
    #             interp_type='linear',
    #             use_voxels=False
    #         )
    #
    #         self.logger.info(f"  重采样后形状：{resampled.shape}")
    #         self.logger.info(f"  重采样后分辨率：{resampled.spacing}")
    #
    #         if progress_callback:
    #             progress_callback(50, "保存重采样模板...")
    #
    #         # 保存
    #         self.logger.info(f"  保存重采样模板...")
    #         ants.image_write(resampled, output_path)
    #
    #         # 验证输出文件
    #         if not Path(output_path).exists():
    #             raise RuntimeError(f"重采样模板保存失败：{output_path}")
    #
    #         verify_img = ants.image_read(output_path)
    #         self.logger.info(f"  验证输出：{verify_img.shape}, {verify_img.spacing}")
    #         self._cleanup_ants_image(verify_img)
    #
    #         if progress_callback:
    #             progress_callback(100, "模板重采样完成")
    #
    #         self.logger.info(f"  ✅ 模板重采样完成")
    #
    #         return output_path
    #
    #     except Exception as e:
    #         self.logger.error(f"  ❌ 重采样失败：{e}", exc_info=True)
    #
    #         # 提供详细的调试信息
    #         self.logger.error(f"  输入路径：{template_path}")
    #         self.logger.error(f"  输出路径：{output_path}")
    #         self.logger.error(f"  目标分辨率：{target_resolution}")
    #
    #         raise
    #
    #     finally:
    #         self._cleanup_ants_image(template)
    #         self._cleanup_ants_image(resampled)
    def _resample_template(
            self,
            template_path: str,
            target_resolution: float,
            output_path: str,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> str:
        """
        重采样模板到目标分辨率
        使用 nibabel + scipy（保持正交方向矩阵）
        """
        self.logger.info(f"重采样模板：{target_resolution}mm 各向同性")

        import nibabel as nib
        from scipy.ndimage import zoom

        try:
            if progress_callback:
                progress_callback(0, "重采样模板...")

            # 标准化路径
            template_path = str(Path(template_path).absolute())
            output_path = str(Path(output_path).absolute())

            self.logger.info(f"  输入：{template_path}")
            self.logger.info(f"  输出：{output_path}")

            # 读取模板
            if progress_callback:
                progress_callback(10, "读取模板...")

            nii = nib.load(template_path)
            data = np.asanyarray(nii.dataobj)  # 确保是 numpy 数组
            original_affine = nii.affine.copy()
            original_zooms = nii.header.get_zooms()[:3]

            self.logger.info(f"  原始形状：{data.shape}")
            self.logger.info(f"  原始分辨率：{original_zooms}")
            self.logger.info(f"  原始 Affine:\n{original_affine}")

            # ========== 关键修复：分解 Affine 矩阵 ==========
            # Affine = 旋转 × 缩放 × 平移
            # 我们需要保持旋转不变，只修改缩放

            target_res = float(target_resolution)

            # 计算缩放因子
            scale_factors = tuple(float(z) / target_res for z in original_zooms)

            self.logger.info(f"  缩放因子：{scale_factors}")
            self.logger.info(f"  目标分辨率：{target_res}mm")

            # 重采样
            if progress_callback:
                progress_callback(30, "执行重采样...")

            resampled_data = zoom(data, scale_factors, order=1)

            self.logger.info(f"  重采样后形状：{resampled_data.shape}")

            # ========== 关键修复：创建新的正交 Affine ==========
            # 方法：从原始 affine 提取旋转和平移，应用新的缩放

            # 1. 提取平移（第 4 列前 3 个元素）
            translation = original_affine[:3, 3].copy()

            # 2. 提取旋转部分（前 3x3，去除缩放）
            rotation = original_affine[:3, :3].copy()
            for i in range(3):
                norm = np.linalg.norm(rotation[:, i])
                if norm > 1e-10:
                    rotation[:, i] /= norm

            self.logger.info(f"  旋转矩阵:\n{rotation}")

            # 3. 验证旋转矩阵是否正交
            identity_check = np.dot(rotation.T, rotation)
            self.logger.info(f"  正交性检查 (应接近单位矩阵):\n{identity_check}")

            if not np.allclose(identity_check, np.eye(3), atol=1e-3):
                self.logger.warning(f"  ⚠️ 旋转矩阵不是严格正交，尝试正交化...")
                # 使用 SVD 正交化
                U, S, Vt = np.linalg.svd(rotation)
                rotation = np.dot(U, Vt)

            # 4. 创建新的缩放矩阵
            new_zooms = np.diag([target_res, target_res, target_res])

            # 5. 构建新的 Affine：旋转 × 新缩放 + 平移
            new_affine = np.eye(4)
            new_affine[:3, :3] = np.dot(rotation, new_zooms)
            new_affine[:3, 3] = translation

            self.logger.info(f"  新 Affine:\n{new_affine}")

            # 6. 验证新 Affine 的方向余弦是否正交
            new_direction = new_affine[:3, :3].copy()
            for i in range(3):
                norm = np.linalg.norm(new_direction[:, i])
                if norm > 1e-10:
                    new_direction[:, i] /= norm

            ortho_check = np.dot(new_direction.T, new_direction)
            self.logger.info(f"  新方向正交性检查:\n{ortho_check}")

            if not np.allclose(ortho_check, np.eye(3), atol=1e-3):
                self.logger.error(f"  ❌ 新 Affine 方向不是正交的！")
                raise ValueError("无法创建正交方向矩阵")

            # 创建新的 NIfTI 文件
            if progress_callback:
                progress_callback(80, "保存重采样模板...")

            new_nii = nib.Nifti1Image(
                resampled_data.astype(np.float32),
                new_affine
            )
            new_nii.header.set_data_dtype(np.float32)

            # 保存
            nib.save(new_nii, output_path)

            # 验证输出
            verify_nii = nib.load(output_path)
            verify_zooms = verify_nii.header.get_zooms()[:3]
            verify_affine = verify_nii.affine

            self.logger.info(f"  验证分辨率：{verify_zooms}")
            self.logger.info(f"  验证形状：{verify_nii.shape}")
            self.logger.info(f"  验证 Affine:\n{verify_affine}")

            # 验证方向是否正交
            verify_direction = verify_affine[:3, :3].copy()
            for i in range(3):
                norm = np.linalg.norm(verify_direction[:, i])
                if norm > 1e-10:
                    verify_direction[:, i] /= norm

            verify_ortho = np.dot(verify_direction.T, verify_direction)
            self.logger.info(f"  验证正交性:\n{verify_ortho}")

            if np.allclose(verify_ortho, np.eye(3), atol=1e-3):
                self.logger.info(f"  ✅ 方向矩阵正交性验证通过")
            else:
                self.logger.warning(f"  ⚠️ 方向矩阵正交性验证未通过")

            self._close_nibabel_file(verify_nii)

            if progress_callback:
                progress_callback(100, "模板重采样完成")

            self.logger.info(f"  ✅ 模板重采样完成")

            return output_path

        except Exception as e:
            self.logger.error(f"  ❌ 重采样失败：{e}", exc_info=True)
            raise

    # def apply_transform_to_bold(
    #         self,
    #         bold_path: str,
    #         transform_prefix: str,
    #         template_path: str,
    #         output_path: str,
    #         target_resolution: Optional[float] = None,
    #         progress_callback: Optional[Callable[[int, str], None]] = None
    # ) -> Dict:
    #     """应用变换到 4D BOLD 数据（修复版）"""
    #     self.logger.info(f"应用变换到 4D BOLD: {bold_path}")
    #
    #     # 初始化所有清理变量为 None
    #     bold_nii = None
    #     template_nii = None
    #     template = None
    #     transformed_mm = None
    #     resampled_template_path = None
    #     volume_img = None
    #     transformed_img = None
    #     temp_img = None
    #     final_img = None
    #
    #     try:
    #         # ========== 1. 验证并标准化路径 ==========
    #         bold_path = str(Path(bold_path).absolute())
    #         template_path = str(Path(template_path).absolute())
    #         output_path = str(Path(output_path).absolute())
    #         transform_prefix = str(Path(transform_prefix).absolute())
    #
    #         self.logger.info(f"  BOLD 路径：{bold_path}")
    #         self.logger.info(f"  模板路径：{template_path}")
    #         self.logger.info(f"  输出路径：{output_path}")
    #
    #         # 检查文件是否存在
    #         if not Path(bold_path).exists():
    #             raise FileNotFoundError(f"BOLD 文件不存在：{bold_path}")
    #         if not Path(template_path).exists():
    #             raise FileNotFoundError(f"模板文件不存在：{template_path}")
    #
    #         # ========== 2. 加载模板并检查分辨率 ==========
    #         template_nii = nib.load(template_path)
    #         template_zooms = template_nii.header.get_zooms()[:3]
    #         current_resolution = min(template_zooms)
    #
    #         actual_template_path = template_path
    #
    #         if target_resolution:
    #             if current_resolution < target_resolution:
    #                 self.logger.info(f"  模板分辨率 ({current_resolution:.1f}mm) 高于目标 ({target_resolution}mm)")
    #                 self.logger.info(f"  正在重采样模板以降低内存占用...")
    #
    #                 template_dir = Path(template_path).parent
    #                 resampled_name = f"template_{target_resolution:.1f}mm.nii.gz"
    #                 resampled_template_path = str(template_dir / resampled_name)
    #
    #                 self.logger.info(f"  重采样输出：{resampled_template_path}")
    #
    #                 if not Path(resampled_template_path).exists():
    #                     self._resample_template(
    #                         template_path,
    #                         float(target_resolution),  # ← 确保是 float 类型
    #                         resampled_template_path,
    #                         progress_callback=lambda v, t: progress_callback(int(v * 5 / 100),
    #                                                                          t) if progress_callback else None
    #                     )
    #                 else:
    #                     self.logger.info(f"  重采样模板已存在，跳过")
    #
    #                 self._close_nibabel_file(template_nii)
    #                 template_nii = nib.load(resampled_template_path)
    #                 template_zooms = template_nii.header.get_zooms()[:3]
    #                 actual_template_path = resampled_template_path
    #
    #         # ========== 3. 读取模板图像 ==========
    #         self.logger.info(f"  读取模板图像：{actual_template_path}")
    #         template = ants.image_read(actual_template_path)
    #         template_affine = template_nii.affine.copy()
    #         template_shape = template_nii.shape[:3]
    #
    #         self._close_nibabel_file(template_nii)
    #         template_nii = None
    #
    #         self.logger.info(f"  目标空间形状：{template_shape}")
    #         self.logger.info(f"  目标分辨率：{template_zooms}")
    #
    #         # ========== 4. 加载原始 BOLD ==========
    #         bold_nii = nib.load(bold_path)
    #         bold_dataobj = bold_nii.dataobj
    #         n_timepoints = bold_dataobj.shape[3]
    #
    #         self.logger.info(f"  时间点数：{n_timepoints}")
    #
    #         # ========== 5. 验证变换文件 ==========
    #         transform_files = []
    #         for suffix in ['_affine.mat', '_warp.nii.gz']:
    #             tf = f"{transform_prefix}{suffix}"
    #             tf_path = Path(tf)
    #
    #             if tf_path.exists():
    #                 transform_files.append(str(tf_path.absolute()))
    #                 self.logger.info(f"  ✅ 变换文件：{transform_files[-1]}")
    #             else:
    #                 self.logger.warning(f"  ⚠️ 变换文件不存在：{tf}")
    #
    #         if not transform_files:
    #             raise ValueError(f"未找到变换文件：{transform_prefix}*")
    #
    #         time.sleep(0.5)
    #
    #         # ========== 6. 创建内存映射文件 ==========
    #         temp_output_path = output_path.replace('.nii.gz', '.nii')
    #         if temp_output_path == output_path:
    #             temp_output_path = output_path
    #
    #         self.logger.info(f"  创建内存映射文件：{temp_output_path}")
    #
    #         transformed_mm = np.memmap(
    #             temp_output_path,
    #             dtype=np.float32,
    #             mode='w+',
    #             shape=(template_shape[0], template_shape[1], template_shape[2], n_timepoints)
    #         )
    #
    #         # ========== 7. 流式处理循环 ==========
    #         for i in range(n_timepoints):
    #             if progress_callback:
    #                 progress_callback(10 + int(80 * i / n_timepoints), f"变换时间点 {i + 1}/{n_timepoints}...")
    #
    #             try:
    #                 volume_img = None
    #                 transformed_img = None
    #
    #                 volume_data = np.asarray(bold_dataobj[:, :, :, i]).astype(np.float32)
    #
    #                 origin_3d = list(bold_nii.header.get_best_affine()[:3, 3])
    #                 spacing_3d = list(bold_nii.header.get_zooms()[:3])
    #                 direction_3d = self._get_direction_3x3_from_nibabel(bold_nii)
    #
    #                 volume_img = ants.from_numpy(
    #                     volume_data,
    #                     origin=origin_3d,
    #                     spacing=spacing_3d,
    #                     direction=direction_3d
    #                 )
    #                 del volume_data
    #
    #                 transformed_img = ants.apply_transforms(
    #                     fixed=template,
    #                     moving=volume_img,
    #                     transformlist=transform_files,
    #                     interpolator='linear',
    #                     verbose=False
    #                 )
    #
    #                 self._cleanup_ants_image(volume_img)
    #                 volume_img = None
    #
    #                 transformed_mm[:, :, :, i] = transformed_img.numpy()
    #
    #                 self._cleanup_ants_image(transformed_img)
    #                 transformed_img = None
    #
    #                 if i % 10 == 0:
    #                     transformed_mm.flush()
    #                     gc.collect()
    #
    #             except Exception as e:
    #                 self.logger.error(f"  时间点 {i} 变换失败：{e}")
    #                 transformed_mm[:, :, :, i] = 0
    #                 self._cleanup_ants_image(volume_img)
    #                 volume_img = None
    #                 self._cleanup_ants_image(transformed_img)
    #                 transformed_img = None
    #                 gc.collect()
    #
    #         if transformed_mm is not None:
    #             transformed_mm.flush()
    #
    #         self.logger.info(f"  ✅ 流式写入完成")
    #
    #         # ========== 8. 写入 NIfTI 头信息 ==========
    #         self.logger.info(f"  写入 NIfTI 头信息...")
    #
    #         output_header = nib.Nifti1Header()
    #         output_header.set_data_dtype(np.float32)
    #         output_header['pixdim'][1:4] = template_zooms
    #
    #         temp_img = nib.load(temp_output_path)
    #         final_img = nib.Nifti1Image(temp_img.dataobj, template_affine, header=output_header)
    #         nib.save(final_img, output_path)
    #
    #         self._close_nibabel_file(temp_img)
    #         temp_img = None
    #         self._close_nibabel_file(final_img)
    #         final_img = None
    #
    #         # 清理临时文件
    #         if temp_output_path != output_path and os.path.exists(temp_output_path):
    #             try:
    #                 os.remove(temp_output_path)
    #                 self.logger.info(f"  清理临时文件：{temp_output_path}")
    #             except:
    #                 pass
    #
    #         if progress_callback:
    #             progress_callback(100, "变换应用完成")
    #
    #         self.logger.info(f"  完成：{output_path}")
    #
    #         return {
    #             "success": True,
    #             "output_path": output_path,
    #             "n_timepoints": n_timepoints
    #         }
    #
    #     except Exception as e:
    #         self.logger.error(f"  ❌ 处理过程中断：{e}", exc_info=True)
    #         raise
    #
    #     finally:
    #         self.logger.info("  清理资源...")
    #
    #         if transformed_mm is not None:
    #             try:
    #                 transformed_mm.flush()
    #                 del transformed_mm
    #             except:
    #                 pass
    #
    #         if template is not None:
    #             self._cleanup_ants_image(template)
    #         if volume_img is not None:
    #             self._cleanup_ants_image(volume_img)
    #         if transformed_img is not None:
    #             self._cleanup_ants_image(transformed_img)
    #         if bold_nii is not None:
    #             self._close_nibabel_file(bold_nii)
    #         if template_nii is not None:
    #             self._close_nibabel_file(template_nii)
    #         if temp_img is not None:
    #             self._close_nibabel_file(temp_img)
    #         if final_img is not None:
    #             self._close_nibabel_file(final_img)
    #
    #         if resampled_template_path and not os.path.exists(output_path):
    #             try:
    #                 os.remove(resampled_template_path)
    #                 self.logger.info(f"  清理临时模板：{resampled_template_path}")
    #             except:
    #                 pass
    #
    #         gc.collect()
    #         self.logger.info("  资源清理完成")
    def apply_transform_to_bold(
            self,
            bold_path: str,
            transform_prefix: str,
            template_path: str,
            output_path: str,
            target_resolution: Optional[float] = None,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """应用变换到 4D BOLD 数据（修复文件类型错误）"""
        self.logger.info(f"应用变换到 4D BOLD: {bold_path}")

        # 初始化所有清理变量
        # ← 关键修复：在函数开头初始化所有清理变量为 None
        bold_nii = None
        template_nii = None
        template = None
        transformed_data = None
        resampled_template_path = None
        volume_img = None
        transformed_img = None
        temp_img = None
        final_img = None
        output_img = None

        try:
            # ========== 1. 标准化路径 ==========
            bold_path = str(Path(bold_path).absolute())
            template_path = str(Path(template_path).absolute())
            output_path = str(Path(output_path).absolute())
            transform_prefix = str(Path(transform_prefix).absolute())

            # ========== 2. 检查分辨率并重采样 ==========
            template_nii = nib.load(template_path)
            template_zooms = template_nii.header.get_zooms()[:3]
            current_resolution = min(template_zooms)

            actual_template_path = template_path

            if target_resolution:
                target_res = float(target_resolution)

                if current_resolution < target_res:
                    self.logger.info(f"  模板分辨率 ({current_resolution:.1f}mm) 高于目标 ({target_res:.1f}mm)")
                    self.logger.info(f"  正在重采样模板...")

                    template_dir = Path(template_path).parent
                    resampled_name = f"template_{target_res:.1f}mm.nii.gz"
                    resampled_template_path = str(template_dir / resampled_name)

                    if not Path(resampled_template_path).exists():
                        self._resample_template(
                            template_path,
                            target_res,
                            resampled_template_path,
                            progress_callback=lambda v, t: progress_callback(int(v * 5 / 100),
                                                                             t) if progress_callback else None
                        )
                    else:
                        self.logger.info(f"  重采样模板已存在，跳过")

                    self._close_nibabel_file(template_nii)
                    template_nii = nib.load(resampled_template_path)
                    template_zooms = template_nii.header.get_zooms()[:3]
                    actual_template_path = resampled_template_path

            # ========== 3. 读取模板为 ANTs 图像 ==========
            template = ants.image_read(actual_template_path)
            template_affine = template_nii.affine.copy()
            template_shape = template_nii.shape[:3]

            self._close_nibabel_file(template_nii)
            template_nii = None

            self.logger.info(f"  目标空间：{template_shape}, {template_zooms}")

            # ========== 4. 加载 BOLD ==========
            bold_nii = nib.load(bold_path)
            bold_dataobj = bold_nii.dataobj
            n_timepoints = bold_dataobj.shape[3]

            self.logger.info(f"  时间点数：{n_timepoints}")

            # ========== 5. 验证变换文件 ==========
            transform_files = []
            for suffix in ['_affine.mat', '_warp.nii.gz']:
                tf = f"{transform_prefix}{suffix}"
                if Path(tf).exists():
                    transform_files.append(str(Path(tf).absolute()))

            if not transform_files:
                raise ValueError(f"未找到变换文件：{transform_prefix}*")

            time.sleep(0.5)

            # ========== 6. 关键修复：预分配 numpy 数组（不用 memmap） ==========
            self.logger.info(f"  分配输出数组：{template_shape + (n_timepoints,)}")

            # 使用 numpy 数组而不是 memmap
            # 对于 3mm 模板，通常内存足够（约 1-2GB）
            transformed_data = np.zeros(
                template_shape + (n_timepoints,),
                dtype=np.float32
            )

            # ========== 7. 流式处理 ==========
            volume_img = None
            transformed_img = None

            for i in range(n_timepoints):
                if progress_callback:
                    progress_callback(10 + int(80 * i / n_timepoints), f"变换时间点 {i + 1}/{n_timepoints}...")

                try:
                    volume_img = None
                    transformed_img = None

                    volume_data = np.asarray(bold_dataobj[:, :, :, i]).astype(np.float32)

                    origin_3d = list(bold_nii.header.get_best_affine()[:3, 3])
                    spacing_3d = list(bold_nii.header.get_zooms()[:3])
                    direction_3d = self._get_direction_3x3_from_nibabel(bold_nii)

                    volume_img = ants.from_numpy(
                        volume_data,
                        origin=origin_3d,
                        spacing=spacing_3d,
                        direction=direction_3d
                    )
                    del volume_data

                    transformed_img = ants.apply_transforms(
                        fixed=template,
                        moving=volume_img,
                        transformlist=transform_files,
                        interpolator='linear',
                        verbose=False
                    )

                    self._cleanup_ants_image(volume_img)
                    volume_img = None

                    # 直接写入 numpy 数组
                    transformed_data[:, :, :, i] = transformed_img.numpy()

                    self._cleanup_ants_image(transformed_img)
                    transformed_img = None

                    # 定期清理内存
                    if i % 20 == 0:
                        gc.collect()

                except Exception as e:
                    self.logger.error(f"  时间点 {i} 变换失败：{e}")
                    transformed_data[:, :, :, i] = 0
                    gc.collect()

            # ========== 8. 关键修复：正确创建并保存 NIfTI 文件 ==========
            self.logger.info(f"  创建 NIfTI 图像...")

            # 创建输出 header
            output_header = nib.Nifti1Header()
            output_header.set_data_dtype(np.float32)
            output_header['pixdim'][1:4] = template_zooms

            # 创建 NIfTI 图像对象
            output_img = nib.Nifti1Image(
                transformed_data,
                template_affine,
                header=output_header
            )

            # ← 关键修复：使用 nib.save 直接保存（自动处理 .nii 或 .nii.gz）
            self.logger.info(f"  保存到：{output_path}")
            nib.save(output_img, output_path)

            # 清理
            del transformed_data
            del output_img
            gc.collect()

            # 验证输出文件
            if not Path(output_path).exists():
                raise RuntimeError(f"输出文件保存失败：{output_path}")

            verify_nii = nib.load(output_path)
            self.logger.info(f"  验证输出：{verify_nii.shape}, {verify_nii.header.get_zooms()[:3]}")
            self._close_nibabel_file(verify_nii)

            if progress_callback:
                progress_callback(100, "变换应用完成")

            self.logger.info(f"  ✅ 完成：{output_path}")

            return {
                "success": True,
                "output_path": output_path,
                "n_timepoints": n_timepoints
            }


        except Exception as e:

            self.logger.error(f"  ❌ 处理失败：{e}", exc_info=True)

            raise


        # finally:
        #
        #     # ← 关键修复：清理前检查是否为 None
        #
        #     self.logger.info("  清理资源...")
        #
        #     if transformed_data is not None:
        #         del transformed_data
        #
        #     if output_img is not None:
        #         del output_img
        #
        #     if template is not None:
        #         self._cleanup_ants_image(template)
        #
        #     if volume_img is not None:
        #         self._cleanup_ants_image(volume_img)
        #
        #     if transformed_img is not None:
        #         self._cleanup_ants_image(transformed_img)
        #
        #     if bold_nii is not None:
        #         self._close_nibabel_file(bold_nii)
        #
        #     if template_nii is not None:
        #         self._close_nibabel_file(template_nii)
        #
        #     if temp_img is not None:
        #         self._close_nibabel_file(temp_img)
        #
        #     if final_img is not None:
        #         self._close_nibabel_file(final_img)
        #
        #     if resampled_template_path and not os.path.exists(output_path):
        #
        #         try:
        #
        #             os.remove(resampled_template_path)
        #
        #         except:
        #
        #             pass
        #
        #     gc.collect()
        #
        #     self.logger.info("  资源清理完成")

    def motion_correction(
            self,
            bold_path: str,
            output_path: str,
            reference_volume: int = 0,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """运动校正"""
        self.logger.info(f"运动校正：{bold_path}")

        # ← 关键：在函数最开始初始化 ALL 变量为 None
        bold_nii = None
        reference_img = None
        volume_img = None
        corrected_data = None
        output_img = None

        reg = None

        try:
            if progress_callback:
                progress_callback(0, "加载 4D BOLD 数据...")

            bold_nii = nib.load(bold_path)
            bold_dataobj = bold_nii.dataobj

            if len(bold_dataobj.shape) != 4:
                raise ValueError(f"BOLD 数据必须是 4D，当前形状：{bold_dataobj.shape}")

            n_timepoints = bold_dataobj.shape[3]
            self.logger.info(f"  时间点数：{n_timepoints}")

            # 获取几何信息
            origin_3d = list(bold_nii.header.get_best_affine()[:3, 3])
            spacing_3d = list(bold_nii.header.get_zooms()[:3])
            direction_3d = self._get_direction_3x3_from_nibabel(bold_nii)

            # 提取参考体积
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
            gc.collect()

            # 分配输出数组
            self.logger.info(f"  分配输出数组...")

            corrected_data = np.zeros(
                (bold_dataobj.shape[0], bold_dataobj.shape[1], bold_dataobj.shape[2], n_timepoints),
                dtype=np.float32
            )

            # 对每个时间点进行配准
            for i in range(n_timepoints):
                if progress_callback:
                    progress_callback(10 + int(80 * i / n_timepoints), f"校正时间点 {i + 1}/{n_timepoints}...")

                try:
                    volume_img = None

                    volume_data = np.asarray(bold_dataobj[:, :, :, i]).astype(np.float32)
                    volume_img = ants.from_numpy(
                        volume_data,
                        origin=origin_3d,
                        spacing=spacing_3d,
                        direction=direction_3d
                    )
                    del volume_data

                    if i == reference_volume:
                        corrected_data[:, :, :, i] = volume_img.numpy()
                    else:
                        reg = ants.registration(
                            fixed=reference_img,
                            moving=volume_img,
                            type_of_transform='Rigid',
                            metric='CC',
                            verbose=False
                        )
                        corrected_data[:, :, :, i] = reg['warpedmovout'].numpy()

                    if volume_img is not None:
                        self._cleanup_ants_image(volume_img)
                        volume_img = None

                    if i % 50 == 0:
                        gc.collect()

                except Exception as e:
                    self.logger.warning(f"  时间点 {i} 配准失败：{e}，使用原始数据")
                    volume_data = np.asarray(bold_dataobj[:, :, :, i]).astype(np.float32)
                    corrected_data[:, :, :, i] = volume_data
                    del volume_data
                    gc.collect()

            # 创建 NIfTI 图像
            self.logger.info(f"  创建 NIfTI 图像...")

            output_img = nib.Nifti1Image(
                corrected_data,
                bold_nii.affine,
                header=bold_nii.header
            )
            output_img.header.set_data_dtype(np.float32)

            nib.save(output_img, output_path)

            if progress_callback:
                progress_callback(100, "运动校正完成")

            self.logger.info(f"  运动校正完成：{output_path}")

            return {
                "success": True,
                "output_path": output_path,
                "n_timepoints": n_timepoints,
                "reference_volume": reference_volume
            }

        except Exception as e:
            self.logger.error(f"  ❌ 运动校正失败：{e}", exc_info=True)
            raise

        finally:
            # ← 关键：使用 locals() 检查变量是否存在
            local_vars = locals()

            if 'corrected_data' in local_vars and corrected_data is not None:
                del corrected_data

            if 'output_img' in local_vars and output_img is not None:
                del output_img

            if 'reference_img' in local_vars and reference_img is not None:
                self._cleanup_ants_image(reference_img)

            if 'volume_img' in local_vars and volume_img is not None:
                self._cleanup_ants_image(volume_img)

            if 'bold_nii' in local_vars and bold_nii is not None:
                self._close_nibabel_file(bold_nii)

            gc.collect()

    def bold_mean(
            self,
            bold_path: str,
            output_path: str,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """BOLD 平均化"""
        self.logger.info(f"BOLD 平均化：{bold_path}")

        bold_nii = None

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

            # 使用 nibabel 直接计算平均（内存高效）
            mean_data = np.mean(bold_dataobj, axis=3)

            origin_3d = list(bold_nii.header.get_best_affine()[:3, 3])
            spacing_3d = list(bold_nii.header.get_zooms()[:3])
            direction_3d = self._get_direction_3x3_from_nibabel(bold_nii)

            mean_img = ants.from_numpy(
                mean_data.astype(np.float32),
                origin=origin_3d,
                spacing=spacing_3d,
                direction=direction_3d
            )

            del mean_data
            gc.collect()

            if progress_callback:
                progress_callback(80, "保存平均图像...")

            ants.image_write(mean_img, output_path)
            self._cleanup_ants_image(mean_img)

            if progress_callback:
                progress_callback(100, "BOLD 平均化完成")

            self.logger.info(f"  BOLD 平均化完成：{output_path}")

            return {
                "success": True,
                "output_path": output_path,
                "n_timepoints": n_timepoints
            }

        finally:
            self._close_nibabel_file(bold_nii)
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
            import shutil

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
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """完整的功能像处理流程"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if target_resolution is None:
            if processing_mode == "fast":
                target_resolution = 3.0
            elif processing_mode == "standard":
                target_resolution = 2.0
            elif processing_mode == "high":
                target_resolution = 1.0
            else:
                target_resolution = 3.0

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

        temp_files = []  # 跟踪临时文件

        try:
            # 步骤 1: 运动校正
            if do_motion_correction:
                if progress_callback:
                    progress_callback(0, "步骤 1/4: 运动校正...")

                mc_output = str(output_dir / "bold_motion_corrected.nii.gz")
                self.motion_correction(
                    bold_path, mc_output,
                    progress_callback=lambda v, t: progress_callback(int(v * 25 / 100),
                                                                     t) if progress_callback else None
                )
                results["outputs"]["motion_corrected"] = mc_output
                results["steps_completed"].append("motion_correction")

            # 步骤 2: BOLD 平均化
            if do_bold_mean:
                if progress_callback:
                    progress_callback(25, "步骤 2/4: BOLD 平均化...")

                mean_output = str(output_dir / "bold_mean.nii.gz")
                self.bold_mean(
                    mc_output, mean_output,
                    progress_callback=lambda v, t: progress_callback(int(25 + v * 25 / 100),
                                                                     t) if progress_callback else None
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
                    progress_callback=lambda v, t: progress_callback(int(50 + v * 25 / 100),
                                                                     t) if progress_callback else None
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

                self.apply_transform_to_bold(
                    mc_output,
                    results["outputs"]["bold_to_t1w_transform"],
                    template_path,
                    template_output,
                    target_resolution=target_resolution,
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