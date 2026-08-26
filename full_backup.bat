@echo off
chcp 65001 > nul
echo ===================================================
echo   СТВОРЕННЯ ПОВНОГО БЕКАПУ СКЛАДУ (БАЗА + ФОТО)
echo ===================================================

:: Налаштування підключення
set KEY_PATH="C:/Users/vanno/Downloads/ssh-key-2026-08-20.key"
set SERVER_USER=ubuntu
set SERVER_IP=152.70.164.207
set REMOTE_DIR=/home/ubuntu/warehouse

:: Створення локальної папки за датою
set CURR_DATE=%date:~-4%-%date:~3,2%-%date:~0,2%_%time:~0,2%-%time:~3,2%
set CURR_DATE=%CURR_DATE: =0%
set TARGET_DIR=C:\Backups\Warehouse_%CURR_DATE%

mkdir "%TARGET_DIR%"

echo [1/3] Пакування бази та фото всередині Docker...
ssh -i %KEY_PATH% %SERVER_USER%@%SERVER_IP% "docker exec nesterov_warehouse tar -czf /app/backup_temp.tar.gz db.sqlite3 media"

echo [2/3] Копіювання з сервера на комп'ютер...
scp -i %KEY_PATH% %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/backup_temp.tar.gz "%TARGET_DIR%\full_backup.tar.gz"

echo [3/3] Очищення тимчасового файлу на сервері...
ssh -i %KEY_PATH% %SERVER_USER%@%SERVER_IP% "rm -f %REMOTE_DIR%/backup_temp.tar.gz"

echo.
echo ===================================================
echo ✓ Повний бекап успішно збережено в:
echo   %TARGET_DIR%\full_backup.tar.gz
echo ===================================================
pause
