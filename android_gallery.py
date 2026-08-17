# -*- coding: utf-8 -*-
"""
安卓相册多选：调用系统 ACTION_PICK + EXTRA_ALLOW_MULTIPLE，
借助 python-for-android 的 android.activity 回调收集多张图，并复制为本地文件。
仅安卓可用。
"""
import os
import uuid

from jnius import autoclass
from android import activity as android_activity
from kivy.app import App

_PICK_REQ = 7301


def _picked_dir():
    return os.path.join(App.get_running_app().user_data_dir, "picked")


def _copy_uri_to_file(uri):
    """把 content:// Uri 复制为应用私有目录下的普通文件，返回路径。"""
    context = autoclass("org.kivy.android.PythonActivity").mActivity
    cr = context.getContentResolver()
    inp = cr.openInputStream(uri)
    d = _picked_dir()
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    target = os.path.join(d, "p_{}.jpg".format(uuid.uuid4().hex))
    with open(target, "wb") as f:
        buf = inp.read(65536)
        while buf:
            f.write(buf)
            buf = inp.read(65536)
    inp.close()
    return target


def pick_images(callback, request_code=_PICK_REQ):
    """
    打开系统相册（多选），用户确认后通过 callback(list_of_file_paths) 返回。
    callback 在主线程（Kivy）调用，可直接更新 UI。
    """
    Intent = autoclass("android.content.Intent")
    intent = Intent(Intent.ACTION_PICK)
    intent.setType("image/*")
    intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)

    act = autoclass("org.kivy.android.PythonActivity").mActivity
    act.startActivityForResult(intent, request_code)

    def on_result(request, result, data):
        if request != request_code:
            return
        paths = []
        if data:
            clip = data.getClipData()
            if clip is not None:
                for i in range(clip.getItemCount()):
                    item = clip.getItemAt(i)
                    u = item.getUri()
                    if u is not None:
                        paths.append(_copy_uri_to_file(u))
            else:
                u = data.getData()
                if u is not None:
                    paths.append(_copy_uri_to_file(u))
        try:
            android_activity.unbind(on_activity_result=on_result)
        except Exception:
            pass
        callback(paths)

    android_activity.bind(on_activity_result=on_result)
