# WeChatBillOCR

Automatically capture WeChat Wallet bill pages from an Android phone, extract transaction text via OCR, and export statistics to CSV/JSON.

## Features

- 📱 **Wireless / USB Android control** via ADB
- 🖼️ **Screenshot + OCR** for WeChat bill pages (bypassing accessibility restrictions)
- 📊 **Export results** to CSV and JSON with summaries
- ⏱️ **Date range filtering** (e.g., last N months)
- 🔄 **Auto-scroll** until no new records or date limit is reached
- 🛑 **Safe interrupt** with `Ctrl+C` saves already captured data

## Requirements

- Windows PC
- Android phone with **Developer Options** and **USB / Wireless debugging** enabled
- Python 3.13+
- [Umi-OCR](https://github.com/hiroi-sora/Umi-OCR) running locally (HTTP API on `127.0.0.1:1224`)
- ADB & scrcpy (place under `platform-tools/` and `scrcpy/`)

## Setup

Download and extract the following tools into the project root:

- [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) → `platform-tools/`
- [scrcpy](https://github.com/Genymobile/scrcpy/releases) → `scrcpy/`
- [Umi-OCR Rapid](https://github.com/hiroi-sora/Umi-OCR/releases) → `Umi-OCR/`

## Quick Start

1. Connect your phone:

   ```powershell
   scrcpy\scrcpy-win64-v3.2\adb.exe connect <PHONE_IP>:<PORT>
   ```

2. Start Umi-OCR in headless mode:

   ```powershell
   Umi-OCR\Umi-OCR_Rapid_v2.1.5\Umi-OCR.exe --no_win
   ```

3. Open WeChat → Me → Services → Wallet → Bill, and scroll to the top.

4. Run the script:

   ```bash
   python wechat_bill_ocr.py --months 2
   ```

   Or use the interactive launcher:

   ```powershell
   一键统计.bat
   ```

## CLI Options

```bash
# Last 2 months
python wechat_bill_ocr.py --months 2

# Specific date range
python wechat_bill_ocr.py --start-date 2024-01-01 --end-date 2024-12-31

# Specify device
python wechat_bill_ocr.py --device 192.168.x.x:xxxxx --months 2

# Limit scrolls
python wechat_bill_ocr.py --months 2 --max-scrolls 50
```

## Output

Results are saved under `output/`:

- `wechat_bills_ocr_YYYYMMDD_HHMMSS.csv` — Excel-friendly
- `wechat_bills_ocr_YYYYMMDD_HHMMSS.json` — detailed records + summary

## Project Structure

```
WeChatBillOCR
├── wechat_bill_ocr.py      # Main script
├── 一键统计.bat             # Interactive launcher
├── tests/                   # Regression tests
├── fixtures/                # Real OCR samples
├── output/                  # Generated CSV/JSON/screenshots
├── platform-tools/          # Google ADB
├── scrcpy/                  # Screen mirror & control
└── Umi-OCR/                 # Local OCR engine
```

## Notes

- WeChat bill pages are protected from Accessibility inspection, so this project uses screenshot-based OCR instead of `uiautomator dump`.
- Screenshot binary integrity is preserved with `adb exec-out screencap -p`.
- OCR accuracy depends on screen clarity and scroll position; please spot-check results.

## License

MIT
