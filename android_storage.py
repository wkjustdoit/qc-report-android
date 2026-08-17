# -*- coding: utf-8 -*-
"""
把生成的 xlsx 写入手机「下载」目录（MediaStore），返回公开 Uri 字符串。
仅安卓可用；生成的文件会出现在系统「文件管理 / 下载」中，便于用户取用或转发。
"""
import os

from jnius import autoclass


def save_to_downloads(src_path):
    """
    复制 src_path 到 Downloads 目录，返回插入的 Uri 字符串。
    """
    context = autoclass("org.kivy.android.PythonActivity").mActivity
    cr = context.getContentResolver()
    ContentValues = autoclass("android.content.ContentValues")
    Downloads = autoclass("android.provider.MediaStore$Downloads")

    uri = Downloads.EXTERNAL_CONTENT_URI
    cv = ContentValues()
    name = os.path.basename(src_path)
    cv.put("_display_name", name)
    cv.put("mime_type",
           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    cv.put("relative_path", "Download")  # API 29+ 生效

    item_uri = cr.insert(uri, cv)
    out = cr.openOutputStream(item_uri)
    with open(src_path, "rb") as f:
        out.write(f.read())
    out.close()
    return item_uri.toString()
