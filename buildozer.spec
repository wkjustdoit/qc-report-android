[app]

# (str) 应用标题
title = 质检报告生成工具

# (str) 包名（需唯一，小写）
package.name = qcreport
package.domain = org.qcreport

# (str) 源码目录（当前目录）
source.dir = .

# (list) 需要打包进 apk 的源码/资源扩展名
# 必须包含 xlsx（内置模板）与 json（配置）
source.include_exts = py,png,jpg,jpeg,xlsx,json,txt,kv

# (list) 额外需要包含的文件/目录（glob）
source.include_patterns = template.xlsx,config.json

# (str) 应用版本
version = 0.1

# (list) 应用依赖（python-for-android recipe 名）
# 不写 numpy/openpyxl 之外的额外原生库；rapidocr 仅桌面用，安卓端用 ML Kit。
requirements = python3==3.11.9, kivy==2.3.1, pillow, openpyxl, plyer, pyjnius

# (str) 横竖屏：portrait / landscape / all
orientation = portrait

# (list) 权限
android.permissions = CAMERA, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, READ_MEDIA_IMAGES, INTERNET

# (int) 目标 / 最低 API
android.api = 33
android.minapi = 24

# (str) NDK 版本
android.ndk = 25b

# (bool) 启用 AndroidX（ML Kit 需要）
android.enable_androidx = True

# (list) Gradle 依赖：ML Kit 中文识别 + play-services-tasks（Tasks.await 需要）+ androidx
android.gradle_dependencies = androidx.appcompat:appcompat:1.6.1, com.google.mlkit:text-recognition-chinese:16.0.0, com.google.android.gms:play-services-tasks:18.0.2

# (str) 是否用 AAB（这里要 apk，设为 False）
android.arch = arm64-v8a

# 日志级别
log_level = 2

# (str) 应用入口
android.entrypoint = org.kivy.android.PythonActivity
android.wakelock = False

# (bool) 自动接受 SDK 许可
android.accept_sdk_license = True

[buildozer]

# (int) 默认构建目标
default.target = android

# (str) 存放构建产物的目录
bin_dir = bin
