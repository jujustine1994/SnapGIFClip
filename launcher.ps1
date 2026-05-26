# SnapGIFClip 啟動器

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$host.UI.RawUI.WindowTitle = "SnapGIFClip"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Clear-Host
Write-Host "[INFO] Starting SnapGIFClip..." -ForegroundColor Green
Write-Host ""

# ======================================
# [1/4] 檢查 Python
# ======================================
Write-Host "[1/4] 檢查 Python 環境..." -ForegroundColor Cyan
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[WARNING] 未偵測到 Python。" -ForegroundColor Yellow
    $ans = Read-Host "是否要立即安裝 Python？[Y/n] - 直接按 Enter 代表同意"
    if ($ans -eq "" -or $ans -ieq "Y") {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            winget install --id Python.Python.3 -e --silent --accept-source-agreements --accept-package-agreements
        } else {
            Write-Host "[ERROR] 請手動至 https://www.python.org/ 下載安裝後重新執行。" -ForegroundColor Red
            Read-Host "按 Enter 關閉"; exit 1
        }
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
        if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
            Write-Host "[INFO] 請關閉後重新點兩下啟動檔。" -ForegroundColor Yellow
            Read-Host "按 Enter 關閉"; exit 0
        }
    } else { Write-Host "已取消。"; Read-Host "按 Enter 關閉"; exit 1 }
} else {
    Write-Host "[OK] $(python --version) 已安裝。" -ForegroundColor Green
}

# ======================================
# [2/4] 檢查 uv
# ======================================
Write-Host "[2/4] 檢查 uv..." -ForegroundColor Cyan
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] 安裝 uv..." -ForegroundColor Gray
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","User") + ";" + $env:PATH
}
Write-Host "[OK] uv 就緒。" -ForegroundColor Green

# ======================================
# [3/4] 檢查虛擬環境
# ======================================
Write-Host "[3/4] 檢查虛擬環境..." -ForegroundColor Cyan
if (-not (Test-Path "venv")) {
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "    SnapGIFClip - 首次安裝說明" -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  接下來程式會自動幫你安裝以下東西：" -ForegroundColor White
    Write-Host ""
    Write-Host "    1. Python 虛擬環境（venv）" -ForegroundColor Yellow
    Write-Host "       讓這個工具有獨立乾淨的執行空間" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    2. mss" -ForegroundColor Yellow
    Write-Host "       高效率螢幕截圖，用於錄製畫面" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    3. Pillow + imageio" -ForegroundColor Yellow
    Write-Host "       圖片處理與 GIF 輸出" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    4. pynput" -ForegroundColor Yellow
    Write-Host "       快捷鍵監聽" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    5. sv-ttk" -ForegroundColor Yellow
    Write-Host "       Windows 11 風格 UI 主題（可選）" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  全程只需要一直按 Enter 同意即可。" -ForegroundColor Green
    Write-Host "  如果有任何疑問，可以把這段說明貼給 AI 詢問。" -ForegroundColor Green
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    $ans = Read-Host "[WARNING] 找不到虛擬環境，現在建立並安裝套件？[Y/n]"
    if ($ans -eq "" -or $ans -ieq "Y") {
        uv venv venv
        uv pip install -r requirements.txt --python venv\Scripts\python.exe
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] 套件安裝失敗。" -ForegroundColor Red
            Read-Host "按 Enter 關閉"; exit 1
        }
        Write-Host "[OK] 套件安裝完成。" -ForegroundColor Green
    } else { Write-Host "已取消。"; Read-Host "按 Enter 關閉"; exit 1 }
} else {
    $broken = Get-ChildItem "venv\Lib\site-packages" -Directory -Filter "*dist-info" -ErrorAction SilentlyContinue | Where-Object {
        -not (Test-Path (Join-Path $_.FullName "METADATA"))
    }
    foreach ($dir in $broken) { Remove-Item -Recurse -Force $dir.FullName }
    uv pip install -r requirements.txt --python venv\Scripts\python.exe -q
    Write-Host "[OK] 虛擬環境就緒。" -ForegroundColor Green
}

# ======================================
# [4/4] 檢查 ffmpeg
# ======================================
Write-Host "[4/4] 檢查 ffmpeg..." -ForegroundColor Cyan
$ffmpegPath = Join-Path $ScriptDir "bin\ffmpeg.exe"
if (-not (Test-Path $ffmpegPath)) {
    Write-Host ""
    Write-Host "  !! 缺少元件：ffmpeg" -ForegroundColor Yellow
    Write-Host "     ffmpeg 是 MP4 輸出所需的影片處理工具，約 80 MB。" -ForegroundColor Gray
    Write-Host "     如果不需要 MP4 輸出，可以跳過；GIF 功能不受影響。" -ForegroundColor Gray
    Write-Host "     如果有任何疑問，可以把這段說明貼給 AI 詢問。" -ForegroundColor Gray
    Write-Host ""
    $ans = Read-Host "是否要立即下載 ffmpeg？[Y/n] - 直接按 Enter 代表同意"
    if ($ans -eq "" -or $ans -ieq "Y") {
        $ffmpegZip = Join-Path $env:TEMP "ffmpeg.zip"
        $ffmpegUrl = "https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-essentials_build.zip"
        Write-Host "[INFO] 下載中，請稍候..." -ForegroundColor Gray
        try {
            Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZip -UseBasicParsing
            Write-Host "[INFO] 解壓縮中..." -ForegroundColor Gray
            $extractDir = Join-Path $env:TEMP "ffmpeg_extract"
            Expand-Archive -Path $ffmpegZip -DestinationPath $extractDir -Force
            $ffmpegExe = Get-ChildItem -Path $extractDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
            if ($ffmpegExe) {
                $binDir = Join-Path $ScriptDir "bin"
                if (-not (Test-Path $binDir)) { New-Item -ItemType Directory -Force $binDir | Out-Null }
                Copy-Item $ffmpegExe.FullName $ffmpegPath -Force
                Write-Host "[OK] ffmpeg 安裝完成。" -ForegroundColor Green
            } else {
                Write-Host "[WARNING] 找不到 ffmpeg.exe，MP4 功能將停用。" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "[WARNING] ffmpeg 下載失敗，MP4 功能將停用。請確認網路連線。" -ForegroundColor Yellow
        } finally {
            Remove-Item $ffmpegZip -ErrorAction SilentlyContinue
            Remove-Item $extractDir -Recurse -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "[INFO] 跳過 ffmpeg，MP4 功能停用。" -ForegroundColor Gray
    }
} else {
    Write-Host "[OK] ffmpeg 已就緒。" -ForegroundColor Green
}

. ".\venv\Scripts\Activate.ps1"

Write-Host ""
Write-Host "[START] 啟動中，請保持此視窗開啟..." -ForegroundColor Green
Write-Host ""

python src\main.py
$exitCode = $LASTEXITCODE

if (Test-Path "src\__pycache__") { Remove-Item -Recurse -Force "src\__pycache__" }

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] 程式意外停止，請回報上方錯誤訊息。" -ForegroundColor Red
    Read-Host "按 Enter 關閉"
} else {
    Write-Host ""
    Write-Host "5 秒後自動關閉..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
}
