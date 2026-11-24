@echo off
D:\source\zdhcs\install-interception.exe install > D:\source\zdhcs\driver_install_log.txt 2>&1
echo exit_code=%ERRORLEVEL% >> D:\source\zdhcs\driver_install_log.txt
