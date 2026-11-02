$ErrorActionPreference = "Stop"
$src = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dst = Join-Path $PSScriptRoot "app\src\main\assets\wanjie"
$items = @("server.py", "engine", "apps", "assets", "rules", "knowledge", "portal")
foreach ($item in $items) {
    $from = Join-Path $src $item
    $to = Join-Path $dst $item
    if (Test-Path $to) { Remove-Item $to -Recurse -Force }
    Copy-Item $from $to -Recurse -Force
}
Get-ChildItem $dst -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force

# Android 窄屏补丁：八列在 360dp 内等比压缩，避免横向截断（网页版保持原样）
$old = '@media(max-width:640px){.manual-panel .mp-grid{grid-template-columns:repeat(8,46px);overflow-x:auto;padding-bottom:4px}}'
$new = '@media(max-width:640px){.manual-panel .mp-grid{grid-template-columns:repeat(8,minmax(0,1fr));gap:2px}.manual-panel .mp-opt{font-size:12.5px;padding:1px 0;border-radius:4px}.manual-panel .mp-col-title{font-size:11px;letter-spacing:0}}'
foreach ($app in @("bazi", "ziwei")) {
    $file = Join-Path $dst "apps\$app\index.html"
    $text = Get-Content $file -Raw
    $patched = $text.Replace($old, $new)
    if ($patched -ne $text) { Set-Content -Path $file -Value $patched -NoNewline -Encoding utf8 }
}
Write-Host "Payload synced (with Android narrow-screen patch). Bump versionCode if already installed."
