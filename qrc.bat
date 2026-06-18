@echo off

.\.venv\Scripts\pyside6-rcc .\resources.qrc -o .\src\data_rc.py

echo done