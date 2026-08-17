# -*- coding: utf-8 -*-
"""
质检报告生成工具 —— 安卓版（Kivy）
功能：6 组照片（相机拍摄 / 相册多选）-> 离线 OCR 识别包装要求 -> 生成 Excel 质检报告 -> 保存到手机下载目录。
复用了桌面版的 excel_worker / image_utils / ocr_local 逻辑，OCR 在安卓上改用 Google ML Kit（离线、支持中文）。
"""
import os
import sys
import json
import traceback
import threading

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image as KivyImage
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.core.window import Window
from kivy.utils import platform

# ---- 移动端专属库（桌面导入会失败，需 try 保护）----
try:
    from plyer import camera
    from plyer import share as plyer_share
except Exception:
    camera = None
    plyer_share = None

try:
    from android.permissions import request_permissions, Permission
except Exception:
    request_permissions = None
    Permission = None

# ---- 复用桌面版核心逻辑 ----
from excel_worker import process_excel
from ocr_local import extract_packaging_info
import image_utils

PLATFORM = platform  # 'android' / 'win' / 'linux' ...

# 项目目录（安卓上即 app 包目录）
APP_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(APP_DIR, "template.xlsx")


# ---------- 中文显示字体（Kivy 默认字体不含 CJK，需指定系统字体）----------
def resolve_cn_font():
    """返回安卓上可用的中文字体路径，找不到则用 None（用 Kivy 默认）。"""
    if PLATFORM != "android":
        return None
    candidates = [
        "/system/fonts/NotoSansCJK-Regular.ttc",
        "/system/fonts/NotoSansSC-Regular.otf",
        "/system/fonts/DroidSansFallback.ttf",
        "/system/fonts/DroidSansFallbackFull.ttf",
        "/system/fonts/NotoSansCJKsc-Regular.otf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


CN_FONT = resolve_cn_font()


def lbl(text="", **kw):
    kw.setdefault("font_name", CN_FONT or "Roboto")
    kw.setdefault("text_size", (None, None))
    return Label(text=text, **kw)


def btn(text="", **kw):
    kw.setdefault("font_name", CN_FONT or "Roboto")
    return Button(text=text, **kw)


# ---------- 配置 ----------
def load_config():
    try:
        with open(os.path.join(APP_DIR, "config.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "photo_groups": [
                {"key": "label_mark", "label": "请上传产品标示照片", "cell": "C51"},
                {"key": "eve_barcode", "label": "请上传EVE条码及条码机照片", "cell": "D87"},
                {"key": "lve_barcode", "label": "请上传LVE条码及条码机照片", "cell": "D91"},
                {"key": "print_each_side", "label": "请上传产品印刷每一面照片", "cell": "D107"},
                {"key": "inner_box", "label": "请上传内盒包装照片", "cell": "D108"},
                {"key": "outer_box", "label": "请上传外箱包装照片", "cell": "D109"},
            ],
            "fields": {
                "quantity_cell": "D6", "order_no_cell": "D11", "date_cell": "D12",
                "sample_cartons_cell": "E31", "sample_numbers_cell": "E32",
                "total_cartons_cell": "E33",
            },
            "image": {"target_size_kb": 700, "quality": 90, "max_dimension": 2048,
                      "auto_rotate_portrait": True, "min_height_px": 110,
                      "gap_px": 6, "fit_margin_px": 8, "fit_safety_px": 12},
        }


CONFIG = load_config()
GROUP_DEFS = CONFIG.get("photo_groups", [])


# ---------- 数据目录 / 工具 ----------
def data_dir():
    return App.get_running_app().user_data_dir


def ensure_dir(p):
    if not os.path.isdir(p):
        os.makedirs(p, exist_ok=True)
    return p


# ---------- 图片来源（相机 / 相册）----------
def request_perms():
    if PLATFORM == "android" and request_permissions is not None:
        perms = [Permission.CAMERA, Permission.READ_EXTERNAL_STORAGE,
                 Permission.WRITE_EXTERNAL_STORAGE]
        # Android 13+ 用 READ_MEDIA_IMAGES 替代 READ_EXTERNAL_STORAGE
        try:
            perms.append(Permission.READ_MEDIA_IMAGES)
        except Exception:
            pass
        try:
            request_permissions(perms)
        except Exception:
            pass


def take_photo(group_panel):
    """调用系统相机拍照，存到应用私有目录，回调加入组。"""
    if PLATFORM != "android" or camera is None:
        App.get_running_app().toast("相机功能仅安卓可用")
        return
    d = ensure_dir(os.path.join(data_dir(), "captured"))
    fname = "cap_{}.jpg".format(os.getpid())
    path = os.path.join(d, fname)

    def _done(filepath):
        if filepath and os.path.exists(filepath):
            Clock.schedule_once(lambda dt: group_panel.add_photos([filepath]))

    try:
        camera.take_picture(filename=path, on_complete=_done)
    except Exception as e:
        App.get_running_app().toast("拍照失败: {}".format(e))


def pick_gallery(group_panel):
    """调用系统相册多选，回调加入组。"""
    if PLATFORM != "android":
        App.get_running_app().toast("相册多选功能仅安卓可用")
        return
    from android_gallery import pick_images

    def _done(paths):
        if paths:
            group_panel.add_photos(paths)

    pick_images(_done)


# ---------- 离线 OCR（安卓用 ML Kit，桌面开发用 RapidOCR）----------
def ocr_photo(path):
    """返回图片全部文本。安卓走 ML Kit，其它环境走 RapidOCR。"""
    if PLATFORM == "android":
        from android_ocr import ocr_image as ml_ocr
        return ml_ocr(path)
    else:
        from ocr_local import ocr_image as rapid_ocr
        return rapid_ocr(path)


# ---------- 单组面板 ----------
class GroupPanel(BoxLayout):
    def __init__(self, defn, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.defn = defn
        self.cell = defn.get("cell")
        self.paths = []
        self.spacing = 6
        self.size_hint_y = None
        self.bind(minimum_height=self.setter("height"))

        title = lbl(text="[{}] {}".format(self.cell, defn.get("label", "")),
                    size_hint_y=None, height=34, font_size=15,
                    color=(0.1, 0.1, 0.1, 1), halign="left")
        self.add_widget(title)

        # 缩略图网格
        self.thumbs = GridLayout(cols=4, spacing=4, size_hint_y=None)
        self.thumbs.bind(minimum_height=self.thumbs.setter("height"))
        self.add_widget(self.thumbs)

        # 按钮行
        row = BoxLayout(size_hint_y=None, height=44, spacing=8)
        b1 = btn(text="拍照", on_press=lambda x: take_photo(self))
        b2 = btn(text="相册多选", on_press=lambda x: pick_gallery(self))
        row.add_widget(b1)
        row.add_widget(b2)
        self.add_widget(row)

    def add_photos(self, paths):
        for p in paths:
            if p and os.path.exists(p) and p not in self.paths:
                self.paths.append(p)
                img = KivyImage(source=p, size_hint=(None, None),
                                size=(78, 78), allow_stretch=True,
                                keep_ratio=True, nocache=True)
                self.thumbs.add_widget(img)
        # 更新高度
        n = len(self.paths)
        self.thumbs.height = max(1, ((n + 3) // 4) * 82)

    def clear_photos(self):
        self.paths = []
        self.thumbs.clear_widgets()
        self.thumbs.height = 1


# ---------- 生成逻辑 ----------
class QCReportApp(App):
    def build(self):
        self.title = "质检报告生成工具"
        Window.softinput_mode = "below_target"
        request_perms()

        root = ScrollView()
        self.container = BoxLayout(orientation="vertical", padding=10, spacing=10,
                                   size_hint_y=None)
        self.container.bind(minimum_height=self.container.setter("height"))
        root.add_widget(self.container)

        # 标题
        self.container.add_widget(lbl(text="质检报告生成工具（安卓）",
                                      font_size=20, size_hint_y=None, height=40,
                                      bold=True, color=(0.05, 0.3, 0.6, 1)))
        self.container.add_widget(lbl(
            text="分别上传 6 组照片（可拍照或从相册多选），填写下方信息后点生成。",
            font_size=13, size_hint_y=None, height=36, color=(0.3, 0.3, 0.3, 1)))

        # 6 组
        self.groups = {}
        for d in GROUP_DEFS:
            gp = GroupPanel(d)
            self.groups[d.get("cell")] = gp
            self.container.add_widget(gp)

        # 手动字段
        self.container.add_widget(lbl(text="— 手动填写（优先于 OCR）—",
                                      size_hint_y=None, height=30, font_size=14,
                                      color=(0.05, 0.3, 0.6, 1)))
        self.ent_quantity = self._field("数量 (填入 D6)：", "如 600")
        self.ent_order = self._field("订单号 (填入 D11)：", "如 26T449491208")
        self.ent_sample = self._field("抽检箱数 (E31)：", "如 5")
        self.ent_num = self._field("箱号 (E32)：", "如 1-5")
        self.ent_total = self._field("总出货箱数 (E33)：", "如 100")

        # 生成按钮
        gen = btn(text="生成质检报告", size_hint_y=None, height=52,
                  background_color=(0.1, 0.55, 0.2, 1),
                  on_press=lambda x: self.on_generate())
        self.container.add_widget(gen)

        self.container.add_widget(lbl(text="提示：报告生成后自动保存到手机下载目录。",
                                      font_size=12, size_hint_y=None, height=30,
                                      color=(0.4, 0.4, 0.4, 1)))
        return root

    def _field(self, label, hint):
        box = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=8)
        box.add_widget(lbl(text=label, size_hint=(0.45, 1), font_size=13))
        ti = TextInput(text="", hint_text=hint, multiline=False,
                       size_hint=(0.55, 1), font_size=14,
                       input_type="text")
        box.add_widget(ti)
        self.container.add_widget(box)
        return ti

    def toast(self, msg):
        try:
            from android import mActivity
            from jnius import autoclass
            Toast = autoclass("android.widget.Toast")
            context = mActivity.getApplicationContext()
            Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
        except Exception:
            print("[toast]", msg)

    def _ts(self):
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def on_generate(self):
        # 收集照片分组
        photo_groups = {}
        for cell, gp in self.groups.items():
            if gp.paths:
                photo_groups[cell] = list(gp.paths)

        fields = CONFIG.get("fields", {})
        image_config = CONFIG.get("image", {})

        # 手动字段
        quantity = (self.ent_quantity.text or "").strip()
        order_no = (self.ent_order.text or "").strip()
        sample_cartons = (self.ent_sample.text or "").strip()
        sample_numbers = (self.ent_num.text or "").strip()
        total_cartons = (self.ent_total.text or "").strip()

        # 进度弹窗
        self.progress_popup = self._busy("正在生成报告（首次识别需联网下载模型）")
        self.progress_popup.open()

        def work():
            try:
                # 1) OCR 合并包装信息（所有上传图）
                packaging_info = {}
                if PLATFORM == "android" and photo_groups:
                    for cell, paths in photo_groups.items():
                        for p in paths:
                            try:
                                text = ocr_photo(p)
                            except Exception as e:
                                print("OCR 失败", p, e)
                                continue
                            if not text:
                                continue
                            info = extract_packaging_info(text)
                            for k, v in info.items():
                                if v is not None and packaging_info.get(k) is None:
                                    packaging_info[k] = v

                # 2) 手动字段覆盖
                if quantity:
                    try:
                        packaging_info["quantity"] = int(quantity)
                    except ValueError:
                        packaging_info["quantity"] = quantity
                if order_no:
                    packaging_info["order_no"] = order_no

                # 3) 生成 Excel
                out_dir = ensure_dir(os.path.join(data_dir(), "reports"))
                stamp = self._ts()
                out_path = os.path.join(out_dir, "质检报告_{}.xlsx".format(stamp))
                process_excel(
                    template_path=TEMPLATE_PATH,
                    output_path=out_path,
                    packaging_info=packaging_info,
                    photo_groups=photo_groups,
                    fields=fields,
                    image_config=image_config,
                    sample_cartons=sample_cartons,
                    sample_numbers=sample_numbers,
                    total_cartons=total_cartons,
                )

                # 4) 保存到下载目录
                saved = None
                if PLATFORM == "android":
                    try:
                        from android_storage import save_to_downloads
                        saved = save_to_downloads(out_path)
                    except Exception as e:
                        print("保存到下载失败", e)
                Clock.schedule_once(lambda dt: self._finish_ok(out_path, saved, packaging_info))
            except Exception:
                err = traceback.format_exc()
                print(err)
                Clock.schedule_once(lambda dt: self._finish_err(err))

        threading.Thread(target=work, daemon=True).start()

    def _busy(self, msg):
        box = BoxLayout(orientation="vertical", padding=16, spacing=10)
        box.add_widget(lbl(text=msg, font_size=15))
        pb = ProgressBar(size_hint_y=None, height=20, value=30)
        box.add_widget(pb)
        return Popup(title="请稍候", content=box, size_hint=(0.8, 0.3),
                     auto_dismiss=False)

    @mainthread
    def _finish_ok(self, out_path, saved_uri, packaging_info):
        try:
            self.progress_popup.dismiss()
        except Exception:
            pass
        q = packaging_info.get("quantity") or "未识别"
        o = packaging_info.get("order_no") or "未识别"
        msg = ("生成成功！\n数量: {}\n订单号: {}\n文件: {}\n\n已保存到手机下载目录。"
               .format(q, o, os.path.basename(out_path)))
        self.toast("报告已生成")
        box = BoxLayout(orientation="vertical", padding=14, spacing=8)
        box.add_widget(lbl(text=msg, font_size=14))
        ok = btn(text="好的", size_hint_y=None, height=42,
                 on_press=lambda x: popup.dismiss())
        box.add_widget(ok)
        popup = Popup(title="完成", content=box, size_hint=(0.9, 0.55))
        popup.open()

    @mainthread
    def _finish_err(self, err):
        try:
            self.progress_popup.dismiss()
        except Exception:
            pass
        box = BoxLayout(orientation="vertical", padding=14, spacing=8)
        box.add_widget(lbl(text="生成失败：\n{}".format(err[-600:]), font_size=12))
        ok = btn(text="关闭", size_hint_y=None, height=42,
                 on_press=lambda x: popup.dismiss())
        box.add_widget(ok)
        popup = Popup(title="错误", content=box, size_hint=(0.9, 0.6))
        popup.open()


if __name__ == "__main__":
    QCReportApp().run()
