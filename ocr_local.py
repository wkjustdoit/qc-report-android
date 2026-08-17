# -*- coding: utf-8 -*-
"""
本地离线 OCR（RapidOCR / ONNX Runtime）。
完全免费、无需任何 API Key、可离线运行。
模型随包自带，无需联网下载。
"""
import re

try:
    from rapidocr_onnxruntime import RapidOCR
    _IMPORT_ERROR = None
except Exception as _e:  # 未安装 / 依赖版本不兼容 等，均不崩
    RapidOCR = None
    _IMPORT_ERROR = str(_e)

_ENGINE = None


def is_available():
    """
    返回 (是否可用, 原因)。
    可用时原因 None；不可用时原因为具体错误信息，便于界面提示。
    """
    if RapidOCR is None:
        if _IMPORT_ERROR is None:
            return False, "未安装 rapidocr-onnxruntime"
        # 区分“包未安装”与“包已装但类导入失败”
        if "No module named" in _IMPORT_ERROR:
            return False, ("未安装 rapidocr-onnxruntime。\n"
                           "请运行：python -m pip install -r requirements.txt")
        return False, ("rapidocr-onnxruntime 已安装，但 RapidOCR 类加载失败：\n"
                       + _IMPORT_ERROR + "\n\n"
                       "多半是 onnxruntime 版本不兼容。请尝试：\n"
                       "  python -m pip install onnxruntime==1.8.1\n"
                       "  python -m pip install rapidocr-onnxruntime --no-deps\n"
                       "  python -m pip install opencv-python pyclipper PyYAML Shapely six")
    return True, None


def _get_engine():
    global _ENGINE
    if RapidOCR is None:
        ok, reason = is_available()
        raise RuntimeError(reason or "OCR 引擎不可用")
    if _ENGINE is None:
        _ENGINE = RapidOCR()
    return _ENGINE


def ocr_image(image_path: str) -> str:
    """
    识别图片全部文本，返回 \n 拼接的字符串。
    """
    engine = _get_engine()
    result, _ = engine(image_path)
    if not result:
        return ""
    return "\n".join(text for _, text, _ in result)


def extract_packaging_info(text: str) -> dict:
    """
    从包装要求 OCR 文本中提取：
      - quantity : 彩套数量 / 外箱数量 / ~数字
      - batch_no : batch no. 后的代码（如 26T4）
      - item_no  : 货号（优先取较长的数字串，如 49491208）
      - order_no : batch_no + item_no（无法识别时为空，需手动填）
      - size     : 尺寸（如 100x70x26mm）
    返回 dict，未识别到的字段为 None。识别结果可在界面手动修正。
    """
    info = {
        "quantity": None,
        "batch_no": None,
        "item_no": None,
        "order_no": None,
        "size": None,
    }
    if not text:
        return info

    # 尺寸：数字x数字x数字mm（兼容中文 × 与空格）
    size_pat = re.compile(r'(\d{2,4})\s*[xX×]\s*(\d{2,4})\s*[xX×]\s*(\d{2,4})\s*mm', re.IGNORECASE)
    m = size_pat.search(text)
    if m:
        info["size"] = "{}x{}x{}mm".format(m.group(1), m.group(2), m.group(3))

    # 货号：优先取“货号”后紧跟的 6 位以上数字；
    # 若 OCR 把“货号”与数字拆成两行，则退而求其次，取文中独立的 8 位数字（最常见货号长度）。
    item_candidates = [int(x) for x in re.findall(r'货号[:：]?\s*(\d{6,})', text, re.IGNORECASE)]
    eight = re.search(r'\b(\d{8})\b', text)
    if eight:
        item_candidates.append(int(eight.group(1)))
    if item_candidates:
        info["item_no"] = str(max(item_candidates))

    # batch no：batch no.26T4 / batchno.26T4 等
    batch_pat = re.compile(r'batch\s*no\.?\s*([A-Za-z0-9]+)', re.IGNORECASE)
    m = batch_pat.search(text)
    if m:
        info["batch_no"] = m.group(1).upper()

    # 数量：优先“彩套数量 / 彩卡数量”后数字；其次“外箱数量”；
    # 再其次“数量”后数字（兼容跨行）；最后 ~数字
    qty_pat = re.compile(r'彩[套卡]数量\D{0,12}?(\d{2,6})', re.IGNORECASE)
    m = qty_pat.search(text)
    if not m:
        m = re.search(r'外箱数量\D{0,12}?(\d{2,6})', text, re.IGNORECASE)
    if not m:
        m = re.search(r'数量\D{0,12}?(\d{2,6})', text, re.IGNORECASE)
    if not m:
        m = re.search(r'[~～]\s*(\d{3,5})', text)
    if m:
        info["quantity"] = int(m.group(1))

    # 订单号：batch_no + item_no；若照片里直接有“订单”后数字则优先采用
    order_pat = re.compile(r'订单[:：]?\s*([A-Za-z0-9]{6,})', re.IGNORECASE)
    m = order_pat.search(text)
    if m:
        info["order_no"] = m.group(1)
    elif info["batch_no"] and info["item_no"]:
        info["order_no"] = info["batch_no"] + info["item_no"]

    return info
