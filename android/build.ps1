$ErrorActionPreference = "Stop"

# 可按自己的环境覆盖这三个变量
if (-not $env:JAVA_HOME) { $env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-21.0.8.9-hotspot" }
if (-not $env:ANDROID_HOME) { $env:ANDROID_HOME = "D:\zcodework1\android-sdk" }
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME

Set-Location $PSScriptRoot

$gradle = $null
if ($env:GRADLE_BIN) {
    $gradle = $env:GRADLE_BIN
} elseif (Get-Command gradle -ErrorAction SilentlyContinue) {
    $gradle = "gradle"
} elseif (Test-Path "D:\zcodework1\gradle-8.9\bin\gradle.bat") {
    $gradle = "D:\zcodework1\gradle-8.9\bin\gradle.bat"
} else {
    throw "未找到 Gradle。请安装 Gradle 8.9+，或设置 GRADLE_BIN 指向 gradle.bat。"
}

& $gradle assembleDebug --no-daemon
