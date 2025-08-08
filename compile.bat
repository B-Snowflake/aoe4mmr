cd .
call .\.venv\Scripts\activate
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
echo %TIME%
nuitka --output-dir=d:\aoe4mmr\aoe4mmr --enable-plugin=pyside6 --lto=yes --windows-icon-from-ico=resources/icon/Aoe4mmr.ico --standalone --include-data-files=resources/~.pck=resources/~.pck --windows-console-mode=disable Aoe4mmr.py
echo %TIME% & ping -n 2 127.0.0.1 > nul