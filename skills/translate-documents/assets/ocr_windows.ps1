# Windows.Media.Ocr -> JSON with pixel bounding boxes (top-left origin).
#
# Usage:  powershell -ExecutionPolicy Bypass -File ocr_windows.ps1 <image.png> <langTag>
#         powershell -ExecutionPolicy Bypass -File ocr_windows.ps1 -ListLangs
#
# - Run with Windows PowerShell 5.1 (powershell.exe), NOT pwsh 7 — this uses the
#   WinRT projection, which PowerShell Core does not load the same way.
# - Language coverage = the OCR language packs installed on the machine (this
#   engine DOES support Hebrew, unlike Apple Vision) — check with -ListLangs;
#   packs install via Settings > Time & Language > Language & Region.
# - Emits WORD-level boxes like tesseract: cluster them into labels per
#   references/ocr-pipeline.md. conf is always 1.0 (the API exposes none).
# - The engine caps input at OcrEngine.MaxImageDimension (~2600 px): render
#   PDF pages at 150 dpi, not 200, and set the spec's "dpi" to match.
# - NOTE: authored and reviewed, but not yet exercised on a real Windows box —
#   verify the first run's output against the page before trusting it.
param(
    [Parameter(Position = 0)] [string]$ImagePath,
    [Parameter(Position = 1)] [string]$Language,
    [switch]$ListLangs
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]

if ($ListLangs) {
    [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | ForEach-Object { $_.LanguageTag }
    exit 0
}
if (-not $ImagePath -or -not $Language) {
    [Console]::Error.WriteLine('usage: ocr_windows.ps1 <image> <langTag>   (or -ListLangs)')
    exit 2
}

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
                   $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $null = $netTask.Wait(-1)
    $netTask.Result
}

$lang = New-Object Windows.Globalization.Language $Language
if (-not [Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($lang)) {
    [Console]::Error.WriteLine("language '$Language' has no installed OCR pack; run -ListLangs")
    exit 3
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync((Resolve-Path $ImagePath).Path)) `
              ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) `
                ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) `
                 ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

$max = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
if ($bitmap.PixelWidth -gt $max -or $bitmap.PixelHeight -gt $max) {
    [Console]::Error.WriteLine("image $($bitmap.PixelWidth)x$($bitmap.PixelHeight) exceeds the OCR cap of $max px - render at a lower dpi")
    exit 4
}

$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

$words = foreach ($line in $result.Lines) {
    foreach ($w in $line.Words) {
        [pscustomobject]@{
            text = $w.Text
            conf = 1.0            # Windows OCR exposes no confidence
            x    = [math]::Round($w.BoundingRect.X, 1)
            y    = [math]::Round($w.BoundingRect.Y, 1)
            w    = [math]::Round($w.BoundingRect.Width, 1)
            h    = [math]::Round($w.BoundingRect.Height, 1)
        }
    }
}
ConvertTo-Json @($words)
