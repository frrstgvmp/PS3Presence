# PS3 Presence 0.7.0 Beta

## Русский

Первый публичный тестовый релиз для Windows x64.

- Текущая PS3-игра, обложка и таймер сессии в Discord Rich Presence.
- Локальная статистика игрового времени и история сессий.
- Русский и английский интерфейс.
- Обновлённое About: контакт автора в Discord, ссылка на GitHub и «Сообщить о проблеме».

Скачайте **PS3Presence-0.7.0-beta-win64-portable.zip** из Assets, распакуйте весь архив и запустите **PS3Presence/PS3Presence.exe**. Установка и Python не нужны. Папка **_internal** должна оставаться рядом с EXE.

Для работы нужны настольный Discord, Discord Application ID и NPSSO вашего PSN-аккаунта. Инструкция: [README на русском](https://github.com/frrstgvmp/PS3Presence/blob/v0.7.0-beta/README.md).

Настройки и статистика хранятся в `%LOCALAPPDATA%\PS3Presence`. Перед запуском завершите старую копию через меню трея. Поддерживаются игры PS3; учёт времени идёт только при работающем приложении и доступных данных PSN. Не публикуйте NPSSO или JSON-ответ Sony.

Контрольная сумма ZIP находится в **SHA256SUMS.txt**. Это beta: об ошибках можно сообщить в [Issues](https://github.com/frrstgvmp/PS3Presence/issues).

## English

First public beta release for Windows x64.

- Your current PS3 game, artwork and session timer in Discord Rich Presence.
- Local playtime statistics and session history.
- Russian and English UI.
- Updated About: author contact on Discord, GitHub link and Report an issue.

Download **PS3Presence-0.7.0-beta-win64-portable.zip** from Assets, extract the entire archive and run **PS3Presence/PS3Presence.exe**. No installer or Python is required. Keep the **_internal** folder beside the EXE.

Desktop Discord, a Discord Application ID and your PSN account's NPSSO are required. Instructions: [English README](https://github.com/frrstgvmp/PS3Presence/blob/v0.7.0-beta/README.en.md).

Settings and statistics are stored in `%LOCALAPPDATA%\PS3Presence`. Quit any older copy from its tray menu before launching. Only PS3 games are supported; time is counted while the application runs and PSN data is available. Never publish NPSSO or Sony's JSON response.

The ZIP checksum is provided in **SHA256SUMS.txt**. This is a beta: report problems in [Issues](https://github.com/frrstgvmp/PS3Presence/issues).
