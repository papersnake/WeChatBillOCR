# AGENTS.md

## 项目背景

本目录用于通过电脑操作已 USB / 无线连接的 Android 手机，自动截图并识别微信账单，最终输出 CSV/JSON 统计结果。

## 目录结构

```
E:\rou
├── AGENTS.md                                 # 本文件
├── 一键统计.bat                              # 交互式一键启动（连接/OCR/统计）
├── last_device.txt                           # 上次连接的设备地址（bat 自动写入）
├── wechat_bill_ocr.py                        # 微信账单自动抓取统计脚本
├── test_dump.py                              # adb UI dump 测试脚本
├── test_ocr.py                               # Umi-OCR 接口测试脚本
├── tests/                                    # 回归测试（test_parse / test_interrupt / test_p1）
├── fixtures/                                 # 真实 OCR 样本数据
├── output/                                   # 所有生成的 CSV/JSON/截图
├── setup/                                    # 工具安装包（zip/7z）
├── platform-tools/                           # Google ADB 工具
├── scrcpy/                                   # scrcpy 屏幕镜像与控制工具
└── Umi-OCR/                                  # 本地 OCR 识别工具
```

## 环境准备

1. **Android 手机**：开启开发者选项、USB 调试或无线调试。
2. **电脑与手机在同一局域网**（无线调试时）。
3. **Python 3** 已安装。
4. **Umi-OCR 已启动**：运行后任务栏会出现黑色图标，HTTP API 监听 `127.0.0.1:1224`。

## 常用命令

### 无线调试连接手机

```powershell
E:\rou\scrcpy\scrcpy-win64-v3.2\adb.exe pair  手机IP:配对端口  配对码
E:\rou\scrcpy\scrcpy-win64-v3.2\adb.exe connect  手机IP:调试端口
E:\rou\scrcpy\scrcpy-win64-v3.2\adb.exe devices -l
```

### 启动屏幕镜像

```powershell
E:\rou\scrcpy\scrcpy-win64-v3.2\scrcpy.exe -s 设备IP:端口 --max-size 1024
```

### 启动 Umi-OCR（无窗口模式）

```powershell
E:\rou\Umi-OCR\Umi-OCR_Rapid_v2.1.5\Umi-OCR.exe --no_win
```

## 微信账单统计脚本

`wechat_bill_ocr.py` 会循环截图 → OCR 识别 → 解析账单条目 → 向上滚动 → 直到无新记录或超出日期范围。

### 使用方法

**推荐：双击 `一键统计.bat`**，菜单选择：

1. 一键运行（连接手机 + 启动OCR + 统计）
2. 只连接手机
3. 只启动 Umi-OCR
4. 退出

首次连接输入手机 `IP:端口`，之后直接回车沿用上次地址；统计月数直接回车默认 2 个月。

命令行方式：

```bash
# 统计最近 2 个月
python wechat_bill_ocr.py --months 2

# 统计最近 3 个月
python wechat_bill_ocr.py --months 3

# 指定日期范围
python wechat_bill_ocr.py --start-date 2024-01-01 --end-date 2024-12-31

# 指定设备（多设备时）
python wechat_bill_ocr.py --device 192.168.x.x:xxxxx --months 2

# 限制最大滚动次数
python wechat_bill_ocr.py --months 2 --max-scrolls 50
```

### 运行前确认

1. Umi-OCR 已启动。
2. 手机已连接 adb（`adb devices` 能看到设备）。
3. 微信已打开到：我 → 服务 → 钱包 → 账单，并滚动到最顶部。
4. 手机保持亮屏。

### 输出

脚本运行结束后会在 `output\` 目录生成：

- `output\wechat_bills_ocr_YYYYMMDD_HHMMSS.csv`：Excel 可直接打开
- `output\wechat_bills_ocr_YYYYMMDD_HHMMSS.json`：包含明细和汇总数据

## 换手机/换电脑说明

### 换手机

脚本已改为自动检测 adb 设备和自动读取屏幕分辨率，换手机后只需重新执行 `adb pair` / `adb connect`，然后运行脚本即可。

### 换电脑

将整个 `E:\rou` 文件夹复制到新电脑后，修改脚本中的 adb 路径：

```python
ADB_PATH = r"E:\rou\scrcpy\scrcpy-win64-v3.2\adb.exe"
```

改为新电脑上的实际路径。

## 注意事项

- 微信账单页面做了 Accessibility 保护，`uiautomator dump` 无法直接获取文本，因此采用截图 + OCR 方案。
- 截图使用 `adb exec-out screencap -p` 以保持二进制数据完整，避免 Windows 重定向导致 PNG 损坏。
- OCR 识别准确率受屏幕清晰度、文字遮挡、滚动位置影响，结果建议人工抽查核对。
- 按 `Ctrl+C` 可随时中断脚本，已抓取的数据会被保存。
- 命令行窗口中中文可能显示乱码，但保存的 CSV/JSON 文件编码正常。

## 依赖版本（当前）

- scrcpy: v3.2
- Android Platform Tools: latest
- Umi-OCR: v2.1.5 Rapid
- Python: 3.13+
