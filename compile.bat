cd .
call .\.venv\Scripts\activate
call "D:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
echo %TIME%
nuitka ^
--output-dir=d:\aoe4mmr\aoe4mmr ^
--output-filename=Aoe4mmr.exe ^
--enable-plugin=pyside6 --lto=yes ^
--windows-icon-from-ico=resources/icon/Aoe4mmr.ico ^
--standalone ^
--include-package-data=certifi ^
main.py
echo %TIME% & ping -n 2 127.0.0.1 > nul