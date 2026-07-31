@echo off

REM ===== 定义输出目录和工具链路径 =====
set "BASE_DIR=D:\aoe4mmr"  ::输出目录
set "INNO_PATH=E:\Program Files (x86)\Inno Setup 6\ISCC.exe"  ::打包工具路径
set "VC++_PATH=D:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"  ::C++工具链路径

echo %TIME%
:: 记录起始时间
set "st_time=%TIME: =0%"

REM ===== C++工具链 =====
call "%VC++_PATH%"

set CL=/Zm500
set "APP_DIR=%BASE_DIR%\output"
set "DIST_DIR=%APP_DIR%\bin"
set "ICON_TARGET=%APP_DIR%\resources\icon"
set "PACKAGE_DIR=%BASE_DIR%\Aoe4mmr-SetupFiles"
set "ICON_SOURCE=%CD%\main_app\resources\icon\Aoe4mmr.ico"

call .\.venv\Scripts\activate

echo =============================
echo ====  开始编译Python代码 ====
echo =============================

call nuitka ^
	--output-dir=d:\aoe4mmr\aoe4mmr ^
	--output-filename=Aoe4mmr.exe ^
	--enable-plugin=pyside6 --lto=yes ^
	--windows-icon-from-ico=resources/icon/Aoe4mmr.ico ^
	--standalone ^
    --windows-console-mode=disable ^
	main.py

@REM 	--windows-console-mode=disable ^

REM ===== 复制 bin =====
robocopy "%BASE_DIR%\aoe4mmr\main.dist" "%APP_DIR%" /E >nul 2>&1

REM ===== 复制 ico 文件 =====
copy /Y "%ICON_SOURCE%" "%ICON_TARGET%\Aoe4mmr.ico"

echo =============================
echo =====  正在打包安装程序 =====
echo =============================
REM ==== 打包安装程序 ====
"%INNO_PATH%" "aoe4overlay.iss" /DPACKAGE_DIR=%PACKAGE_DIR% /DAPP_DIR=%APP_DIR%

:: 删除文件
rd /s /q "%APP_DIR%" 

:: 记录结束时间（同样替换空格）
set "end_time=%TIME: =0%"

:: 处理开始时间
for /f "tokens=1-4 delims=:.," %%a in ("%st_time%") do (
    set /a "start_res=( ( (1%%a-100)*60 + 1%%b %% 100)*60 + 1%%c %% 100 )*100 + 1%%d %% 100"
)

:: 处理结束时间
for /f "tokens=1-4 delims=:.," %%a in ("%end_time%") do (
    set /a "end_res=( ( (1%%a-100)*60 + 1%%b %% 100)*60 + 1%%c %% 100 )*100 + 1%%d %% 100"
)

:: 计算差值
set /a "diff_ms=end_res - start_res"
if %diff_ms% lss 0 set /a "diff_ms+=8640000"

:: 1. 计算总秒数
set /a "total_sec=diff_ms / 100"
set /a "ms=diff_ms %% 100"

:: 2. 计算小时、分钟、秒
set /a "hr=total_sec / 3600"
set /a "rem_sec=total_sec %% 3600"
set /a "min=rem_sec / 60"
set /a "sec=rem_sec %% 60"

:: 输出结果
if %hr% gtr 0 (
    echo 耗时: %hr% 小时 %min% 分 %sec% 秒
) else if %min% gtr 0 (
    echo 耗时: %min% 分 %sec% 秒
) else (
    echo 耗时: %sec%.%ms% 秒
)
echo 完成于: %TIME%