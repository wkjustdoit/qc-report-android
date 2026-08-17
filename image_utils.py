# -*- coding: utf-8 -*-
"""
图片处理工具：压缩、缩放、自然排序。
兼容 Python 3.8+ / Win7 SP1。
"""
import io
import os
import re
from PIL import Image


# 兼容 Pillow 8.x / 9.x / 10.x
LANCZOS = getattr(Image, 'Resampling', Image).LANCZOS if hasattr(
    getattr(Image, 'Resampling', Image), 'LANCZOS'
) else Image.LANCZOS

SUPPORTED_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}


def is_image_file(filename: str) -> bool:
    """根据扩展名判断是否为支持的图片文件。"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in SUPPORTED_EXTS


def natural_key(name: str):
    """
    自然排序 key：提取文件名开头的数字，没有数字则按 0 处理。
    例如：['1.png', '2.jpg', '11.png'] 会排成 1, 2, 11。
    """
    base = os.path.basename(name)
    m = re.match(r'(\d+)', base)
    num = int(m.group(1)) if m else 0
    return (num, base.lower())


def list_images_by_prefix(folder: str, prefix: str):
    """
    返回 folder 中文件名以 prefix 数字开头的所有图片路径，按自然排序。
    不区分扩展名。

    匹配规则：
      - 若 prefix 为单个数字（如 "2"），则匹配文件名开头第一位数字为 2 的文件，
        例如 2.png、21.png、22.png 都会归入前缀 "2"。
      - 若 prefix 为多位数字（如 "12"），则按精确前缀匹配，例如 12.png、123.png。"""
    if not folder or not os.path.isdir(folder):
        return []
    if not prefix:
        return []

    if len(prefix) == 1:
        # 按文件名开头第一位数字分组
        pattern = re.compile(r'^' + re.escape(prefix) + r'\d*\D')
    else:
        # 精确前缀匹配
        pattern = re.compile(r'^' + re.escape(prefix) + r'(\D|$)')

    files = []
    for name in os.listdir(folder):
        if not is_image_file(name):
            continue
        m = pattern.match(name)
        if m:
            files.append(os.path.join(folder, name))
    files.sort(key=natural_key)
    return files


def compress_image(src_path: str, target_size_kb: int = 700,
                   quality: int = 90, max_dimension: int = 2048,
                   auto_rotate_portrait: bool = True) -> bytes:
    """
    把单张图片压缩到目标大小附近（默认约 700KB），返回字节数据。
    策略：
      0. 先按 EXIF 方向校正（手机照片常见）。
      1. 若 auto_rotate_portrait 且为竖版（高>宽），自动顺时针旋转 90° 变为横版。
      2. 等比缩放到 max_dimension 以内（默认 2048px）。
      3. 用 JPEG 质量 quality 保存；若仍大于目标，逐步降低 quality 并缩小尺寸。
    """
    img = Image.open(src_path)

    # 0. 按 EXIF 方向校正（避免照片在 Excel 里躺倒）
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    # 1. 竖版自动旋转为横版
    if auto_rotate_portrait and img.height > img.width:
        img = img.rotate(90, expand=True)

    # 第一步：等比缩放，避免原图过大
    w, h = img.size
    if max(w, h) > max_dimension:
        ratio = max_dimension / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, LANCZOS)

    target_bytes = target_size_kb * 1024

    def save_with_quality(q: int, size: tuple) -> bytes:
        tmp = img if size == img.size else img.resize(size, LANCZOS)
        buf = io.BytesIO()
        tmp.save(buf, format='JPEG', quality=q, optimize=True)
        return buf.getvalue()

    # 第二步：从指定 quality 开始尝试，尽量贴近目标大小、且质量不低于 70（避免糊）
    current_size = img.size
    for q in range(min(quality, 92), 69, -3):
        data = save_with_quality(q, current_size)
        if len(data) <= target_bytes * 1.1:  # 允许 10% 上浮，≈700KB
            return data

    # 第三步：仍过大则逐步缩小尺寸，质量下限 70
    min_dimension = 1024
    while max(current_size) > min_dimension:
        current_size = (int(current_size[0] * 0.9), int(current_size[1] * 0.9))
        for q in range(90, 69, -3):
            data = save_with_quality(q, current_size)
            if len(data) <= target_bytes * 1.1:
                return data

    # 兜底：最小尺寸 + 质量 72
    return save_with_quality(72, current_size)


def prepare_image(src_path, max_dimension=2048, auto_rotate_portrait=True):
    """
    打开图片，做 EXIF 方向校正 + 竖版自动旋转为横版 + 缩到 max_dimension 以内，
    返回 RGB 模式的 PIL Image，供后续精确缩放到目标显示框。
    （不在此处做“按显示框缩放”，显示框缩放由调用方根据单元格几何决定，
     以保证最终图片字节尺寸与显示框完全一致，杜绝被 WPS 拉伸变形。）
    """
    img = Image.open(src_path)
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    if auto_rotate_portrait and img.height > img.width:
        img = img.rotate(90, expand=True)
    w, h = img.size
    if max(w, h) > max_dimension:
        ratio = max_dimension / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), LANCZOS)
    return img
