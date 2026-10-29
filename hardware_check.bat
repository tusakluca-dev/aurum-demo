@echo off
chcp 65001 >nul
powershell -NoProfile -Command "Get-CimInstance Win32_ComputerSystem | Select-Object @{Name='RAM_GB';Expression={[math]::Round($_.TotalPhysicalMemory/1GB)}}; Get-CimInstance Win32_Processor | Select-Object Name; Get-CimInstance Win32_VideoController | Select-Object Name"
where nvidia-smi >nul 2>nul
if not errorlevel 1 nvidia-smi --query-gpu=name,memory.total --format=csv
pause
