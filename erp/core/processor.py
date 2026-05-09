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
        #add
        fixed = ants.image_read(fixed_path)
        moving = ants.image_read(moving_path)

        fixed_orient = ants.get_orientation(fixed)
        moving_orient = ants.get_orientation(moving)

        self.logger.info(f"刚性配准方向检查：")
        self.logger.info(f"  Fixed:  {fixed_path} → {fixed_orient}")
        self.logger.info(f"  Moving: {moving_path} → {moving_orient}")

        if fixed_orient != moving_orient:
            self.logger.warning(f"  ⚠️ 方向不一致！可能导致配准问题")
        #add
        self.logger.info(f"刚性配准：{moving_path} → {fixed_path}")

        if progress_callback:
            progress_callback(0, "加载图像...")

        fixed = ants.image_read(fixed_path)
        moving = ants.image_read(moving_path)

        if progress_callback:
            progress_callback(20, "执行刚性配准...")

        # 执行配准
        reg = ants.registration(
            fixed=fixed,
            moving=moving,
            type_of_transform='Rigid',
            metric='CC',
            verbose=False
        )

        if progress_callback:
            progress_callback(80, "保存结果...")

        # 保存配准后的图像
        ants.image_write(reg['warpedmovout'], output_path)

        # ← 修复：处理变换文件
        transform_path = str(Path(output_path).parent / "transform.mat")

        # reg['fwdtransforms'][0] 通常已经是文件路径字符串
        source_transform = reg['fwdtransforms'][0]

        import shutil
        if Path(source_transform).exists():
            # 如果已经是文件，直接复制
            shutil.copy(source_transform, transform_path)
        else:
            # 如果是对象（极少情况），才尝试写入
            try:
                ants.write_transform(transform_path, source_transform)
            except Exception as e:
                self.logger.warning(f"无法写入变换文件，尝试直接复制：{e}")
                # 如果写入失败，可能已经是路径但文件被临时清理了，这里做个容错
                pass

        if progress_callback:
            progress_callback(100, "刚性配准完成")

        return {
            "success": True,
            "output_path": output_path,
            "transform_path": transform_path,
            "metric_value": reg.get('metric_value')
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

        # ← 修复：同上
        transform_path = str(Path(output_path).parent / "transform_affine.mat")
        source_transform = reg['fwdtransforms'][0]

        import shutil
        if Path(source_transform).exists():
            shutil.copy(source_transform, transform_path)
        else:
            try:
                ants.write_transform(transform_path, source_transform)
            except:
                pass

        if progress_callback:
            progress_callback(100, "仿射配准完成")

        return {
            "success": True,
            "output_path": output_path,
            "transform_path": transform_path,
            "metric_value": reg.get('metric_value')
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
        # self.logger.info(f"SyN 配准：{moving_path} → {fixed_path}")
        #
        # if progress_callback:
        #     progress_callback(0, "加载图像...")
        #
        # fixed = ants.image_read(fixed_path)
        # moving = ants.image_read(moving_path)
        #
        # if progress_callback:
        #     progress_callback(10, "执行 SyN 配准（可能需要几分钟）...")
        #
        # reg = ants.registration(
        #     fixed=fixed,
        #     moving=moving,
        #     type_of_transform='SyN',    #由SynRA改为Syn
        #     metric='CC',
        #     reg_iterations=[40, 20, 0],
        #     verbose=False
        # )
        #
        # if progress_callback:
        #     progress_callback(80, "保存结果...")
        #
        # ants.image_write(reg['warpedmovout'], output_path)
        #
        # # ← 修复：处理多个变换文件（Affine + Warp）
        # transform_paths = []
        # import shutil
        #
        # for i, transform_source in enumerate(reg['fwdtransforms']):
        #     # 判断是 Affine (.mat) 还是 Warp (.nii.gz)
        #     if 'Warp' in str(transform_source) or transform_source.endswith('.nii.gz'):
        #         target_path = f"{output_transform_prefix}_warp.nii.gz"
        #     else:
        #         target_path = f"{output_transform_prefix}_affine.mat"
        #
        #     if Path(transform_source).exists():
        #         shutil.copy(transform_source, target_path)
        #         transform_paths.append(target_path)
        #     else:
        #         # 尝试写入（备用方案）
        #         try:
        #             ants.write_transform(target_path, transform_source)
        #             transform_paths.append(target_path)
        #         except Exception as e:
        #             self.logger.error(f"保存变换文件失败：{e}")
        #
        # if progress_callback:
        #     progress_callback(100, "SyN 配准完成")
        #
        # return {
        #     "success": True,
        #     "output_path": output_path,
        #     "transform_paths": transform_paths,
        #     "metric_value": reg.get('metric_value')
        # }
        self.logger.info(f"SyN 配准：{moving_path} → {fixed_path}")

        if progress_callback:
            progress_callback(0, "加载图像...")

        fixed = ants.image_read(fixed_path)
        moving = ants.image_read(moving_path)

        # ← 新增：验证方向一致性
        fixed_direction = fixed.direction
        moving_direction = moving.direction

        if not np.allclose(fixed_direction, moving_direction, atol=1e-4):
            self.logger.warning(f"  ⚠️ 配准前方向不一致！")
            self.logger.warning(f"  Fixed direction:\n{fixed_direction}")
            self.logger.warning(f"  Moving direction:\n{moving_direction}")
            # 这里可以选择自动重定向或报错
            # 建议在 process_structural 中已经处理了方向统一

        if progress_callback:
            progress_callback(10, "执行 SyN 配准（可能需要几分钟）...")

        # ← 优化：使用更保守的配准参数
        reg = ants.registration(
            fixed=fixed,
            moving=moving,
            type_of_transform='SyN',  # Rigid + Affine + SyN
            metric='CC',
            reg_iterations=[40, 20, 0],  # 减少迭代次数
            shrink_factors=[4, 2, 1],  # 多分辨率
            smoothing_sigmas=[2, 1, 0],  # 平滑参数
            flow_sigma=3.0,  # ← 新增：限制形变场平滑度
            total_sigma=0.0,  # ← 新增：总变换平滑度
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
            transform_str = str(transform_source) if transform_source is not None else ""

            if not transform_str:
                continue

            if 'Warp' in transform_str or transform_str.endswith('.nii.gz'):
                target_path = f"{output_transform_prefix}_warp.nii.gz"
            else:
                target_path = f"{output_transform_prefix}_affine.mat"

            try:
                if Path(transform_source).exists():
                    shutil.copy(str(transform_source), target_path)
                    if target_path not in transform_paths:
                        transform_paths.append(target_path)
            except Exception as e:
                self.logger.error(f"保存变换文件失败：{e}")

        if progress_callback:
            progress_callback(100, "SyN 配准完成")

        return {
            "success": True,
            "output_path": output_path,
            "transform_paths": transform_paths,
            "metric_value": reg.get('metric_value')
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

        if not input_paths:
            raise ValueError("输入图像列表不能为空")

        # 验证输入路径
        valid_paths = []
        for i, p in enumerate(input_paths):
            if isinstance(p, str) and p.strip():
                if Path(p).exists():
                    valid_paths.append(p)
                else:
                    self.logger.warning(f"忽略不存在的路径：{p}")
            else:
                self.logger.error(f"忽略无效的路径对象 (类型：{type(p)}): {p}")

        if not valid_paths:
            raise ValueError("没有有效的输入图像路径")

        input_paths = valid_paths

        if progress_callback:
            progress_callback(0, f"加载 {len(input_paths)} 个图像...")

        try:
            # 加载所有图像
            images = []
            for i, p in enumerate(input_paths):
                if progress_callback:
                    progress_callback(int(i * 10 / len(input_paths)), f"加载图像 {i + 1}/{len(input_paths)}...")
                img = ants.image_read(p)
                images.append(img)

            if len(images) == 0:
                raise ValueError("未能加载任何图像")

            # ← 关键修复：始终配准到第一个图像（参考）
            reference = images[0]
            aligned_images = [reference]

            if len(images) > 1:
                if progress_callback:
                    progress_callback(10, "配准到参考图像...")

                for i, img in enumerate(images[1:], 1):
                    try:
                        # 使用刚性配准
                        reg = ants.registration(
                            fixed=reference,
                            moving=img,
                            type_of_transform='Rigid',
                            metric='CC',
                            verbose=False
                        )
                        aligned_images.append(reg['warpedmovout'])

                        if progress_callback:
                            progress_callback(10 + int(40 * i / len(images)), f"配准图像 {i}/{len(images) - 1}...")
                    except Exception as e:
                        self.logger.warning(f"  配准失败 {input_paths[i]}: {e}")
                        # 配准失败时使用原始图像
                        aligned_images.append(img)

            if progress_callback:
                progress_callback(50, "计算平均值...")

            # 转换为 numpy 数组并平均
            data_stack = np.stack([img.numpy() for img in aligned_images], axis=0)
            avg_data = np.mean(data_stack, axis=0)

            # 创建平均图像（使用参考图像的几何信息）
            avg_img = ants.from_numpy(
                avg_data,
                origin=reference.origin,
                spacing=reference.spacing,
                direction=reference.direction
            )

            # 保存
            ants.image_write(avg_img, output_path)

            if progress_callback:
                progress_callback(100, "平均化完成")

            self.logger.info(f"  平均化完成：{output_path}")
            self.logger.info(f"  输入数量：{len(input_paths)}")
            self.logger.info(f"  输出 Spacing: {avg_img.spacing}")
            self.logger.info(f"  输出 Shape: {avg_img.shape}")

            return {
                "success": True,
                "output_path": output_path,
                "input_count": len(input_paths)
            }

        except Exception as e:
            self.logger.error(f"平均化过程出错：{e}", exc_info=True)
            raise


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
            mean = np.mean(data)
            std = np.std(data)
            if std > 0:
                data_normalized = (data - mean) / std
            else:
                data_normalized = data - mean
        elif method == 'minmax':
            data_min = np.percentile(data, 2)
            data_max = np.percentile(data, 98)
            if data_max > data_min:
                data_normalized = (data - data_min) / (data_max - data_min)
            else:
                data_normalized = data - data_min
        elif method == 'histogram':
            img_normalized = ants.iMath(img, 'Normalize')
            ants.image_write(img_normalized, output_path)

            return {
                "success": True,
                "output_path": output_path,
                "method": method
            }
        else:
            raise ValueError(f"未知的标准化方法：{method}")

        # 创建标准化后的图像
        img_normalized = ants.from_numpy(
            data_normalized,
            origin=img.origin,
            spacing=img.spacing,
            direction=img.direction
        )

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
            t1w_paths: List[str],
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
        """完整的结构像处理流程"""
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
            # ========== 预处理：方向统一 ==========
            processed_t1w_paths = []

            if progress_callback:
                progress_callback(5, "检查并统一方向...")

            for i, t1w_path in enumerate(t1w_paths):
                # ← 关键修复：如果有模板，统一到模板方向；否则统一到第一个 T1w
                if template_path and do_syn:
                    reoriented_path = str(output_dir / f"T1w_{i}_reoriented.nii.gz")
                    self._reorient_to_standard(t1w_path, template_path, reoriented_path)
                    processed_t1w_paths.append(reoriented_path)
                elif i == 0:
                    # 第一个文件作为参考，直接复制
                    reoriented_path = str(output_dir / f"T1w_{i}_reoriented.nii.gz")
                    import shutil
                    shutil.copy(t1w_path, reoriented_path)
                    processed_t1w_paths.append(reoriented_path)
                else:
                    # 其他文件统一到第一个文件的方向
                    reoriented_path = str(output_dir / f"T1w_{i}_reoriented.nii.gz")
                    self._reorient_to_standard(t1w_path, processed_t1w_paths[0], reoriented_path)
                    processed_t1w_paths.append(reoriented_path)

            # 使用重定向后的文件进行后续处理
            t1w_paths = processed_t1w_paths

            # ========== 步骤 1: 刚性配准（多 T1w 对齐到第一个） ==========
            if do_rigid and len(t1w_paths) > 1:
                if progress_callback:
                    progress_callback(10, "刚性配准（多 T1w 对齐）...")

                reference = t1w_paths[0]
                aligned_paths = [reference]

                for i, t1w_path in enumerate(t1w_paths[1:], 1):
                    rigid_output = str(output_dir / f"T1w_{i}_rigid.nii.gz")
                    self.rigid_registration(
                        fixed_path=reference,
                        moving_path=t1w_path,
                        output_path=rigid_output,
                        progress_callback=lambda v, t: progress_callback(int(10 + v * 20 / len(t1w_paths)),
                                                                         t) if progress_callback else None
                    )
                    aligned_paths.append(rigid_output)

                results["outputs"]["aligned_t1w"] = aligned_paths
                results["steps_completed"].append("rigid_alignment")

            # ========== 步骤 2: 强度标准化 ==========
            if do_normalize:
                if progress_callback:
                    progress_callback(30, "强度标准化...")

                first_t1w = t1w_paths[0]
                norm_output = str(output_dir / "T1w_normalized.nii.gz")
                self.normalize_intensity(
                    input_path=first_t1w,
                    output_path=norm_output,
                    method='zscore',
                    progress_callback=lambda v, t: progress_callback(int(30 + v * 20 / 100),
                                                                     t) if progress_callback else None
                )
                results["outputs"]["normalized"] = norm_output
                results["steps_completed"].append("normalize")

            # ========== 步骤 3: 平均化 ==========
            if do_average and len(t1w_paths) > 1:
                if progress_callback:
                    progress_callback(50, "结构像平均化...")

                # ← 关键修复：使用对齐后的文件平均
                if "aligned_t1w" in results["outputs"]:
                    input_for_avg = results["outputs"]["aligned_t1w"]
                else:
                    input_for_avg = t1w_paths

                avg_output = str(output_dir / "T1w_averaged.nii.gz")
                self.average_images(
                    input_paths=input_for_avg,
                    output_path=avg_output,
                    reference_path=t1w_paths[0],  # ← 明确指定参考
                    progress_callback=lambda v, t: progress_callback(int(50 + v * 30 / 100),
                                                                     t) if progress_callback else None
                )
                results["outputs"]["averaged"] = avg_output
                results["steps_completed"].append("average")
            elif len(t1w_paths) == 1:
                import shutil
                avg_output = str(output_dir / "T1w_averaged.nii.gz")
                shutil.copy(t1w_paths[0], avg_output)
                results["outputs"]["averaged"] = avg_output

            # ========== 步骤 4: T2 配准到 T1 ==========
            if do_t2_to_t1 and t2w_path:
                if progress_callback:
                    progress_callback(80, "T2 配准到 T1...")

                t1w_ref = results["outputs"].get("averaged", t1w_paths[0])
                t2_output = str(output_dir / "T2w_to_T1w.nii.gz")
                self.rigid_registration(
                    fixed_path=t1w_ref,
                    moving_path=t2w_path,
                    output_path=t2_output,
                    progress_callback=lambda v, t: progress_callback(int(80 + v * 10 / 100),
                                                                     t) if progress_callback else None
                )
                results["outputs"]["t2_registered"] = t2_output
                results["steps_completed"].append("t2_to_t1")

            # ========== 步骤 5: SyN 配准到模板 ==========
            if do_syn and template_path:
                if progress_callback:
                    progress_callback(90, "SyN 配准到模板...")

                t1w_ref = results["outputs"].get("averaged", t1w_paths[0])
                syn_output = str(output_dir / "T1w_to_template.nii.gz")
                transform_prefix = str(output_dir / "T1w_to_template")

                self.syn_registration(
                    fixed_path=template_path,
                    moving_path=t1w_ref,
                    output_path=syn_output,
                    output_transform_prefix=transform_prefix,
                    progress_callback=lambda v, t: progress_callback(int(90 + v * 10 / 100),
                                                                     t) if progress_callback else None
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
            self.logger.error(f"结构像处理失败：{e}", exc_info=True)
            if progress_callback:
                progress_callback(100, f"处理失败：{e}")

        return results

    def _reorient_to_standard(self, image_path: str, reference_image_path: str, output_path: str) -> str:
        """
        将图像重定向到参考图像的方向

        Args:
            image_path: 需要重定向的图像
            reference_image_path: 参考方向（通常是模板）
            output_path: 输出路径

        Returns:
            str: 重定向后的图像路径
        """
        self.logger.info(f"检查并统一方向：{image_path}")

        try:
            import nibabel as nib
            import shutil

            # 读取参考图像的方向信息
            ref_nii = nib.load(reference_image_path)
            ref_affine = ref_nii.affine.copy()

            self.logger.info(f"  参考图像 Affine:\n{ref_affine}")

            # 读取原始图像
            img_nii = nib.load(image_path)
            img_affine = img_nii.affine.copy()

            self.logger.info(f"  原始图像 Affine:\n{img_affine}")
            self.logger.info(f"  原始图像 Shape: {img_nii.shape}")

            # 检查 Affine 是否相同（允许小误差）
            if np.allclose(img_affine, ref_affine, atol=1e-4):
                self.logger.info("  ✅ Affine 矩阵一致，无需修改")
                shutil.copy(image_path, output_path)
                return output_path

            # ← 正确方法：从 Affine 提取 spacing 和旋转
            # 计算原始图像的 spacing（体素大小）
            img_spacing = np.sqrt(np.sum(img_affine[:3, :3] ** 2, axis=0))
            ref_spacing = np.sqrt(np.sum(ref_affine[:3, :3] ** 2, axis=0))

            self.logger.info(f"  原始图像 Spacing: {img_spacing}")
            self.logger.info(f"  参考图像 Spacing: {ref_spacing}")

            # 提取旋转矩阵（归一化方向向量）
            def extract_rotation(affine):
                """从 Affine 矩阵提取旋转部分"""
                rotation = affine[:3, :3].copy()
                # 归一化每一列（去除 scaling）
                for i in range(3):
                    norm = np.linalg.norm(rotation[:, i])
                    if norm > 1e-10:
                        rotation[:, i] /= norm
                return rotation

            img_rotation = extract_rotation(img_affine)
            ref_rotation = extract_rotation(ref_affine)

            self.logger.info(f"  原始旋转矩阵:\n{img_rotation}")
            self.logger.info(f"  参考旋转矩阵:\n{ref_rotation}")

            # 检查旋转是否相同
            if np.allclose(img_rotation, ref_rotation, atol=1e-4):
                self.logger.info("  ✅ 旋转矩阵一致，无需修改方向")
                shutil.copy(image_path, output_path)
                return output_path

            # ← 关键：构建新的 Affine 矩阵
            # 使用参考图像的旋转 + 原始图像的 spacing + 原始图像的 origin
            img_origin = img_affine[:3, 3].copy()

            # 构建新的旋转 - 缩放矩阵
            new_zooms = np.diag(img_spacing)
            new_rotation_scaled = np.dot(ref_rotation, new_zooms)

            # 构建完整的 4x4 Affine 矩阵
            new_affine = np.eye(4)
            new_affine[:3, :3] = new_rotation_scaled
            new_affine[:3, 3] = img_origin  # 保持原始 origin

            self.logger.info(f"  新 Affine 矩阵:\n{new_affine}")
            self.logger.info(f"  新 Spacing: {np.sqrt(np.sum(new_affine[:3, :3] ** 2, axis=0))}")

            # 获取原始图像数据（不修改）
            img_data = img_nii.get_fdata()

            # 创建新的 NIfTI 图像，使用新的 Affine
            new_nii = nib.Nifti1Image(img_data, new_affine, header=img_nii.header)
            new_nii.header.set_data_dtype(img_nii.get_data_dtype())

            # 保存新文件
            nib.save(new_nii, output_path)

            self.logger.info(f"  ✅ 方向修改完成：{output_path}")

            # 验证结果
            verify_nii = nib.load(output_path)
            verify_affine = verify_nii.affine
            verify_spacing = np.sqrt(np.sum(verify_affine[:3, :3] ** 2, axis=0))

            self.logger.info(f"  验证：输出 Spacing: {verify_spacing}")
            self.logger.info(f"  验证：输出 Shape: {verify_nii.shape}")

            # 验证 spacing 是否保持不变
            if np.allclose(verify_spacing, img_spacing, atol=1e-4):
                self.logger.info(f"  ✅ Spacing 验证通过（保持不变）")
            else:
                self.logger.warning(f"  ⚠️ Spacing 发生变化！")

            # 验证旋转是否与参考一致
            verify_rotation = extract_rotation(verify_affine)
            if np.allclose(verify_rotation, ref_rotation, atol=1e-4):
                self.logger.info(f"  ✅ 旋转矩阵验证通过（与参考一致）")
            else:
                self.logger.warning(f"  ⚠️ 旋转矩阵仍有差异")

            return output_path

        except Exception as e:
            self.logger.error(f"  ❌ 方向修改失败：{e}", exc_info=True)
            import shutil
            shutil.copy(image_path, output_path)
            return output_path