# 质检报告生成工具 —— 安卓版（Kivy + ML Kit）

把桌面版质检报告工具做成**原生安卓 App（.apk）**：手机上传 6 组照片（拍照 / 相册多选）→ 离线 OCR 识别包装要求 → 生成 Excel 质检报告 → 自动保存到手机「下载」目录。

> ⚠️ 本目录是**可构建的安卓工程源码**，不是已编译的 apk。因为打包需要 Android SDK/NDK（本机没有），请用下面「GitHub Actions 云端构建」一键出包，**无需在本地装任何安卓环境**。

## 功能
- 6 组照片上传，每组都有【拍照】和【相册多选】两个按钮：
  - 产品标示照片 → C51
  - EVE 条码及条码机照片 → D87
  - LVE 条码及条码机照片 → D91
  - 产品印刷每一面照片 → D107
  - 内盒包装照片 → D108
  - 外箱包装照片 → D109
- 照片等比缩放不变形、不重叠；竖图自动旋转；压缩到约 700KB 高清。
- 离线 OCR（Google ML Kit，支持中文）自动识别包装要求里的**数量 / 订单号 / 尺寸**，填入 D6 / D11 / F26。
- 手动输入框（优先于 OCR）：数量(D6)、订单号(D11)、抽检箱数(E31)、箱号(E32)、总出货箱数(E33)。
- 报告生成后自动写入手机「下载」目录，可在文件管理里找到并转发。

## 怎么出包（GitHub Actions 云端构建，推荐）

1. 在 GitHub 新建一个**空仓库**（如 `qc-report-android`）。
2. 把本目录 `android_app/` 下的**全部文件**推到仓库（`.github/workflows/build.yml` 也要一起推上去）。
   ```bash
   cd android_app
   git init
   git add .
   git commit -m "init android app"
   git branch -M main
   git remote add origin https://github.com/你的用户名/qc-report-android.git
   git push -u origin main
   ```
3. 进入仓库的 **Actions** 标签页，等 `Build Android APK` 跑完（首次约 15–30 分钟，会下载 SDK/NDK）。
4. 构建完成后，在对应 run 的 **Artifacts** 里下载 `qc-report-apk`（里面是 `质检报告生成工具-0.1-debug.apk`）。
5. 把 apk 传到手机安装即可（允许「未知来源」安装）。

> 之后改了代码，只要 `git push`，Actions 会自动重新出包。

## 首次使用须知
- **OCR 模型下载**：ML Kit 中文识别模型在 App **首次识别时**需联网下载（约几 MB），下载后**完全离线**可用。所以第一次用 OCR 请保持联网。
- **权限**：App 会申请 相机 / 相册(存储) / 网络 权限，全部允许。
- **Android 版本**：目标 API 33，最低 Android 7.0（API 24）；支持 64 位 ARM 手机。

## 本地桌面调试（可选）
如果你想在本机用 Python 跑界面看布局（不含真机相机/OCR，OCR 会退回 RapidOCR）：
```bash
pip install kivy pillow openpyxl plyer
python main.py
```

## 文件说明
| 文件 | 作用 |
|---|---|
| `main.py` | Kivy 主程序（界面 + 生成流程） |
| `android_ocr.py` | ML Kit 离线 OCR 桥接（pyjnius） |
| `android_gallery.py` | 相册多选（ACTION_PICK + EXTRA_ALLOW_MULTIPLE） |
| `android_storage.py` | 写入「下载」目录（MediaStore） |
| `excel_worker.py` / `image_utils.py` / `ocr_local.py` | 复用桌面版 Excel 生成与图片处理 |
| `模版.xlsx` / `config.json` | 内置模板与配置 |
| `buildozer.spec` | 打包配置（权限 / ML Kit 依赖 / 包含模板） |
| `.github/workflows/build.yml` | 云端自动构建工作流 |

## 与桌面/网页版的差异
- OCR 引擎：桌面/网页用 RapidOCR，安卓用 **ML Kit**（更小、更快、安卓原生可靠）。
- 打包形态：桌面是 exe，网页是 Flask 服务，安卓是 Kivy 原生 apk。
- 核心 Excel 生成逻辑（单元格映射、防变形、约 700KB 压缩）三者完全一致。
