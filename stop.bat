@echo off
echo Stopping all MiMo processes...
taskkill /FI "WINDOWTITLE eq MimoServe" /F 2>NUL
taskkill /FI "IMAGENAME eq python.exe" /F 2>NUL
taskkill /FI "IMAGENAME eq ngrok.exe" /F 2>NUL
taskkill /FI "IMAGENAME eq Kakadu.exe" /F 2>NUL
echo Done.
