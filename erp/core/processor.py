"""
医学影像处理核心模块
实现配准、平均化、标准化等功能
"""
import logging
from pathlib import Path
from typing import Callable, Optional, List, Dict
import numpy as np

try:
    import ants
except ImportError:
    ants = None
    logging.warning("ANTsPy 未安装，配准功能将不可用")


class StructuralProcessor:
    """结构像处理器"""

    def __init__(self):
        self.logger = logging.getLogger("ERP.Processor")
        self._check_ants()

    def _check_ants(self):
        """检查 ANTsPy 是否可用"""
        if ants is None:
            raise ImportError(
                "ANTsPy 未安装！\n"
                "请使用 conda 安装：conda install -c conda-forge antspyx"
            )

    # ========== 1. 刚性配准 ==========
    def rigid_registration(
            self,
            fixed_path: str,
            moving_path: str,
            output_path: str,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """
        刚性配准（6 自由度：3 平移 + 3 旋转）

        Args:
            fixed_path: 固定图像路径（参考）
            moving_path: 移动图像路径（需要配准的）
            output_path: 输出路径
            progress_callback: 进度回调

        Returns:
            dict: 配准结果信息
        """
        self.logger.info(f"刚性配准：{moving_path} → {fixed_path}")

        if progress_callback:
            progress_callback(0, "加载图像...")

        # 加载图像
        fixed = ants.image_read(fixed_path)
        moving = ants.image_read(moving_path)

        if progress_callback:
            progress_callback(20, "执行刚性配准...")

        # 执行配准
        reg = ants.registration(
            fixed=fixed,
            moving=moving,
            type_of_transform='Rigid',
            metric='CC',  # 互相关（同模态）
            verbose=False
        )

        if progress_callback:
            progress_callback(80, "保存结果...")

        # 保存配准后的图像
        ants.image_write(reg['warpedmovout'], output_path)

        # 保存变换矩阵
        transform_path = str(Path(output_path).parent / "transform.mat")
        ants.write_transform(transform_path, reg['fwdtransforms'][0])

        if progress_callback:
            progress_callback(100, "刚性配准完成")

        self.logger.info(f"刚性配准完成：{output_path}")

        return {
            "success": True,
            "output_path": output_path,
            "transform_path": transform_path,
            "metric_value": reg['metric_value'] if 'metric_value' in reg else None
        }

    # ========== 2. 仿射配准 ==========
    def affine_registration(
            self,
            fixed_path: str,
            moving_path: str,
            output_path: str,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """
        仿射配准（12 自由度：刚性 + 缩放 + 剪切）
        """
        self.logger.info(f"仿射配准：{moving_path} → {fixed_path}")

        if progress_callback:
            progress_callback(0, "加载图像...")

        fixed = ants.image_read(fixed_path)
        moving = ants.image_read(moving_path)

        if progress_callback:
            progress_callback(20, "执行仿射配准...")

        reg = ants.registration(
            fixed=fixed,
            moving=moving,
            type_of_transform='Affine',
            metric='CC',
            verbose=False
        )

        if progress_callback:
            progress_callback(80, "保存结果...")

        ants.image_write(reg['warpedmovout'], output_path)

        transform_path = str(Path(output_path).parent / "transform_affine.mat")
        ants.write_transform(transform_path, reg['fwdtransforms'][0])

        if progress_callback:
            progress_callback(100, "仿射配准完成")

        return {
            "success": True,
            "output_path": output_path,
            "transform_path": transform_path,
            "metric_value": reg['metric_value'] if 'metric_value' in reg else None
        }

    # ========== 3. SyN 非线性配准 ==========
    def syn_registration(
            self,
            fixed_path: str,
            moving_path: str,
            output_path: str,
            output_transform_prefix: str,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """
        SyN 非线性配准（可变形配准）

        Args:
            output_transform_prefix: 变换场输出前缀（会生成 Warp 和 Affine 文件）
        """
        self.logger.info(f"SyN 配准：{moving_path} → {fixed_path}")

        if progress_callback:
            progress_callback(0, "加载图像...")

        fixed = ants.image_read(fixed_path)
        moving = ants.image_read(moving_path)

        if progress_callback:
            progress_callback(10, "执行 SyN 配准（可能需要几分钟）...")

        # SyN 配准（使用 SyNRA = Rigid + Affine + SyN）
        reg = ants.registration(
            fixed=fixed,
            moving=moving,
            type_of_transform='SyNRA',
            metric='CC',
            reg_iterations=[40, 20, 0],  # 迭代次数
            verbose=False
        )

        if progress_callback:
            progress_callback(80, "保存结果...")

        # 保存配准后的图像
        ants.image_write(reg['warpedmovout'], output_path)

        # 保存变换场（可能有多个文件）
        transform_paths = []
        for i, transform in enumerate(reg['fwdtransforms']):
            transform_path = f"{output_transform_prefix}_transform_{i}.mat" if 'mat' in transform else f"{output_transform_prefix}_warp.nii.gz"
            ants.write_transform(transform_path, transform)
            transform_paths.append(transform_path)

        if progress_callback:
            progress_callback(100, "SyN 配准完成")

        self.logger.info(f"SyN 配准完成：{output_path}")

        return {
            "success": True,
            "output_path": output_path,
            "transform_paths": transform_paths,
            "metric_value": reg['metric_value'] if 'metric_value' in reg else None
        }

    # ========== 4. 图像平均化 ==========
    def average_images(
            self,
            input_paths: List[str],
            output_path: str,
            reference_path: Optional[str] = None,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """
        多图像平均化（提高信噪比）

        Args:
            input_paths: 输入图像列表
            output_path: 输出路径
            reference_path: 参考图像（用于先配准再平均）
        """
        self.logger.info(f"图像平均化：{len(input_paths)} 个图像 → {output_path}")

        if len(input_paths) == 0:
            raise ValueError("输入图像列表不能为空")

        if progress_callback:
            progress_callback(0, f"加载 {len(input_paths)} 个图像...")

        # 加载所有图像
        images = [ants.image_read(p) for p in input_paths]

        # 如果需要先配准
        if reference_path and len(images) > 1:
            if progress_callback:
                progress_callback(20, "配准到参考图像...")

            reference = ants.image_read(reference_path)
            aligned_images = [reference]  # 参考图像不动

            for i, img in enumerate(images[1:], 1):
                reg = ants.registration(
                    fixed=reference,
                    moving=img,
                    type_of_transform='Rigid',
                    verbose=False
                )
                aligned_images.append(reg['warpedmovout'])

                if progress_callback:
                    progress_callback(20 + int(60 * i / len(images)), f"配准图像 {i}/{len(images) - 1}...")
        else:
            aligned_images = images

        if progress_callback:
            progress_callback(80, "计算平均值...")

        # 转换为 numpy 数组并平均
        data_stack = np.stack([img.numpy() for img in aligned_images], axis=0)
        avg_data = np.mean(data_stack, axis=0)

        # 创建平均图像（使用第一个图像的几何信息）
        avg_img = aligned_images[0].new_image(avg_data)

        # 保存
        ants.image_write(avg_img, output_path)

        if progress_callback:
            progress_callback(100, "平均化完成")

        self.logger.info(f"图像平均化完成：{output_path}")

        return {
            "success": True,
            "output_path": output_path,
            "input_count": len(input_paths)
        }

    # ========== 5. 强度标准化 ==========
    def normalize_intensity(
            self,
            input_path: str,
            output_path: str,
            method: str = 'zscore',
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """
        图像强度标准化

        Args:
            method: 'zscore' (Z 分数), 'minmax' (0-1), 'histogram' (直方图匹配)
        """
        self.logger.info(f"强度标准化：{input_path} → {output_path} ({method})")

        if progress_callback:
            progress_callback(0, "加载图像...")

        img = ants.image_read(input_path)
        data = img.numpy()

        if progress_callback:
            progress_callback(30, f"执行 {method} 标准化...")

        # 标准化方法
        if method == 'zscore':
            # Z 分数标准化
            mean = np.mean(data)
            std = np.std(data)
            if std > 0:
                data_normalized = (data - mean) / std
            else:
                data_normalized = data - mean
        elif method == 'minmax':
            # Min-Max 标准化到 0-1
            data_min = np.percentile(data, 2)
            data_max = np.percentile(data, 98)
            if data_max > data_min:
                data_normalized = (data - data_min) / (data_max - data_min)
            else:
                data_normalized = data - data_min
        elif method == 'histogram':
            # 直方图匹配（使用 ANTs 内置）
            img_normalized = ants.iMath(img, 'Normalize')
            ants.image_write(img_normalized, output_path)

            if progress_callback:
                progress_callback(100, "标准化完成")

            return {
                "success": True,
                "output_path": output_path,
                "method": method
            }
        else:
            raise ValueError(f"未知的标准化方法：{method}")

        # 创建标准化后的图像
        img_normalized = img.new_image(data_normalized)

        # 保存
        ants.image_write(img_normalized, output_path)

        if progress_callback:
            progress_callback(100, "标准化完成")

        self.logger.info(f"强度标准化完成：{output_path}")

        return {
            "success": True,
            "output_path": output_path,
            "method": method
        }

    # ========== 6. 完整结构像处理流程 ==========
    # 修改 process_structural 方法
    def process_structural(
            self,
            t1w_paths: List[str],  # ← 改为列表
            output_dir: str,
            t2w_path: Optional[str] = None,
            template_path: Optional[str] = None,
            do_rigid: bool = True,
            do_normalize: bool = True,
            do_average: bool = True,
            do_syn: bool = False,
            do_t2_to_t1: bool = False,
            progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """
        完整的结构像处理流程（支持多 T1w 批量处理）
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {
            "success": True,
            "outputs": {},
            "steps_completed": [],
            "input_paths": t1w_paths
        }

        if len(t1w_paths) == 0:
            raise ValueError("T1w 文件列表不能为空")

        try:
            # 步骤 1: 刚性配准（多 T1w 对齐到第一个）
            if do_rigid and len(t1w_paths) > 1:
                if progress_callback:
                    progress_callback(10, "刚性配准（多 T1w 对齐）...")

                reference = t1w_paths[0]
                aligned_paths = [reference]

                for i, t1w_path in enumerate(t1w_paths[1:], 1):
                    rigid_output = str(output_dir / f"T1w_{i}_rigid.nii.gz")
                    self.rigid_registration(
                        reference, t1w_path, rigid_output,
                        lambda v, t: progress_callback(int(10 + v * 20 / len(t1w_paths)),
                                                       t) if progress_callback else None
                    )
                    aligned_paths.append(rigid_output)

                results["outputs"]["aligned_t1w"] = aligned_paths
                results["steps_completed"].append("rigid_alignment")

            # 步骤 2: 强度标准化
            if do_normalize:
                if progress_callback:
                    progress_callback(30, "强度标准化...")

                # 对第一个 T1w 进行标准化
                first_t1w = t1w_paths[0]
                norm_output = str(output_dir / "T1w_normalized.nii.gz")
                self.normalize_intensity(
                    first_t1w, norm_output, 'zscore',
                    lambda v, t: progress_callback(int(30 + v * 20 / 100), t) if progress_callback else None
                )
                results["outputs"]["normalized"] = norm_output
                results["steps_completed"].append("normalize")

            # 步骤 3: 平均化
            if do_average and len(t1w_paths) > 1:
                if progress_callback:
                    progress_callback(50, "结构像平均化...")

                # 使用对齐后的文件平均（如果已配准）
                if "aligned_t1w" in results["outputs"]:
                    input_for_avg = results["outputs"]["aligned_t1w"]
                else:
                    input_for_avg = t1w_paths

                avg_output = str(output_dir / "T1w_averaged.nii.gz")
                self.average_images(
                    input_for_avg, avg_output,
                    lambda v, t: progress_callback(int(50 + v * 30 / 100), t) if progress_callback else None
                )
                results["outputs"]["averaged"] = avg_output
                results["steps_completed"].append("average")
            elif len(t1w_paths) == 1:
                # 只有一个文件时，复制作为输出
                import shutil
                avg_output = str(output_dir / "T1w_averaged.nii.gz")
                shutil.copy(t1w_paths[0], avg_output)
                results["outputs"]["averaged"] = avg_output

            # 步骤 4: T2 配准到 T1
            if do_t2_to_t1 and t2w_path:
                if progress_callback:
                    progress_callback(80, "T2 配准到 T1...")

                t1w_ref = results["outputs"].get("averaged", t1w_paths[0])
                t2_output = str(output_dir / "T2w_to_T1w.nii.gz")
                self.rigid_registration(
                    t1w_ref, t2w_path, t2_output,
                    lambda v, t: progress_callback(int(80 + v * 10 / 100), t) if progress_callback else None
                )
                results["outputs"]["t2_registered"] = t2_output
                results["steps_completed"].append("t2_to_t1")

            # 步骤 5: SyN 配准到模板
            if do_syn and template_path:
                if progress_callback:
                    progress_callback(90, "SyN 配准到模板...")

                t1w_ref = results["outputs"].get("averaged", t1w_paths[0])
                syn_output = str(output_dir / "T1w_to_template.nii.gz")
                transform_prefix = str(output_dir / "T1w_to_template")
                self.syn_registration(
                    template_path, t1w_ref, syn_output, transform_prefix,
                    lambda v, t: progress_callback(int(90 + v * 10 / 100), t) if progress_callback else None
                )
                results["outputs"]["syn_registered"] = syn_output
                results["outputs"]["syn_transforms"] = transform_prefix
                results["steps_completed"].append("syn_to_template")

            if progress_callback:
                progress_callback(100, "结构像处理完成")

            self.logger.info(f"结构像处理完成：{results['steps_completed']}")

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)
            self.logger.error(f"结构像处理失败：{e}")
            if progress_callback:
                progress_callback(100, f"处理失败：{e}")

        return results