@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo AURUM - lokale KI einrichten
where ollama >nul 2>nul
if errorlevel 1 (
  echo Bitte Ollama fuer Windows installieren. Danach dieses Fenster schliessen und erneut starten.
  start "Ollama Download" https://ollama.com/download/windows
  pause
  exit /b 1
)
ollama list
if errorlevel 1 (
  echo Ollama ist nicht erreichbar. Bitte Ollama ueber das Windows-Startmenue starten.
  pause
  exit /b 1
)
echo Das Modell qwen2.5:7b wird heruntergeladen. Dafuer werden mehrere GB Speicher benoetigt.
ollama pull qwen2.5:7b
if errorlevel 1 goto failed
echo Teste die lokale KI. Der erste Start kann dauern.
ollama run qwen2.5:7b "Antworte auf Deutsch nur mit: Lokale KI bereit."
if errorlevel 1 goto failed
echo Fertig. Jetzt start.bat ausfuehren. Im Dashboard steht der Status unter Lokale Trading-KI.
pause
exit /b
:failed
echo Einrichtung fehlgeschlagen. Internetverbindung, Ollama-Status und freien Speicher pruefen.
pause
