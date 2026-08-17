# -*- coding: utf-8 -*-
"""
Google ML Kit 离线文字识别（中文 + 拉丁），通过 pyjnius 调用。
仅安卓可用；首次使用需联网下载识别模型（之后完全离线）。
注意：ML Kit 的 Tasks.await 不能在主线程调用，调用方务必在后台线程执行。
"""
import os
import threading
from jnius import autoclass, JavaException

_ML_AVAILABLE = True
try:
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
except Exception:
    _ML_AVAILABLE = False

_CLIENT = None


def is_available():
    return _ML_AVAILABLE


def _get_activity():
    return PythonActivity.mActivity


def _get_recognizer():
    global _CLIENT
    if _CLIENT is None:
        ChineseOptions = autoclass(
            "com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions"
        )
        options = ChineseOptions.Builder().build()
        TextRecognition = autoclass(
            "com.google.mlkit.vision.text.TextRecognition"
        )
        _CLIENT = TextRecognition.getClient(options)
    return _CLIENT


def ocr_image(path):
    """
    识别图片全部文本，返回字符串（识别失败/为空返回 \"\"）。
    必须在后台线程调用。
    """
    if threading.current_thread() is threading.main_thread():
        raise RuntimeError("ML Kit OCR 必须在后台线程调用")

    if not os.path.exists(path):
        return ""

    context = _get_activity()
    File = autoclass("java.io.File")
    Uri = autoclass("android.net.Uri")
    InputImage = autoclass("com.google.mlkit.vision.common.InputImage")
    Tasks = autoclass("com.google.android.gms.tasks.Tasks")

    uri = Uri.fromFile(File(path))
    image = InputImage.fromFilePath(context, uri)
    recognizer = _get_recognizer()
    task = recognizer.process(image)
    try:
        # 注意：Java 静态方法名为 await，而 await 是 Python 关键字，
        # 不能用 Tasks.await(...) 直接调用，需用 getattr 获取。
        await_method = getattr(Tasks, "await")
        result = await_method(task)
    except JavaException as e:
        cause = e.cause or e
        raise RuntimeError("ML Kit OCR 失败: {}".format(cause))
    except Exception as e:
        raise RuntimeError("ML Kit OCR 失败: {}".format(e))
    if result is None:
        return ""
    return result.getText() or ""
