"""Runtime English/Russian UI catalog; external game titles are never translated."""
DEFAULT_LANGUAGE = "ru"

ENGLISH = {
    "Настройки": "Settings", "Статистика": "Statistics", "Статистика игр": "Game statistics",
    "Включить декор": "Enable decoration", "Выключить декор": "Disable decoration",
    "Сейчас играет": "Now playing", "Сейчас не играет": "Not playing",
    "Игра не запущена": "No game running", "Ожидание игры на PlayStation 3": "Waiting for a PlayStation 3 game",
    "В игре · ": "Playing · ", "Платформа": "Platform", "Авторизация": "Authorization",
    "Копировать": "Copy", "Копировать весь лог": "Copy entire log", "Выделить всё": "Select all",
    "Переподключить Discord": "Reconnect Discord", "Закрыть": "Close", "Отмена": "Cancel",
    "Сохранить": "Save", "Готово": "Done", "Версия": "Version",
    "Ник скопирован": "Username copied",
    "Сообщить о проблеме": "Report an issue",
    "Не удалось открыть ссылку в браузере.": "Could not open the link in your browser.",
    "Не удалось открыть профиль. Ник скопирован — найди автора в Discord.":
        "Could not open the profile. Username copied — find the author in Discord.",
    "Подключение, опрос и автозапуск": "Connection, polling and startup",
    "Интервал опроса, секунд": "Polling interval, seconds", "Не менее 15 секунд": "At least 15 seconds",
    "Fallback-обложка": "Fallback cover", "Необязательный ключ изображения": "Optional image key",
    "Запускать вместе с Windows": "Start with Windows", "Обновить NPSSO": "Update NPSSO",
    "Обновление NPSSO": "Update NPSSO", "Открыть вход Sony": "Open Sony sign-in",
    "Открыть страницу ssocookie": "Open ssocookie page", "Вставить из буфера": "Paste from clipboard",
    "1. Войди в PSN в обычном браузере.\n2. Открой ssocookie в той же вкладке.\n3. Скопируй весь JSON-ответ.\n4. Вернись сюда и вставь его из буфера.":
        "1. Sign in to PSN in your browser.\n2. Open ssocookie in the same browser.\n3. Copy the entire JSON response.\n4. Return here and paste it from the clipboard.",
    "Ботаника": "Botanical", "Роса": "Dew", "Терракота": "Terracotta", "Индиго": "Indigo",
    "Сакура": "Sakura", "Аврора": "Aurora", "Новогодняя": "New Year",
    "Общее время": "Total playtime", "Игр: ": "Games: ", "Статистика с ": "Tracking since ",
    "Подсчёт начнётся с первого обнаружения игры": "Tracking starts with the first detected game",
    "Игры": "Games", "Сессии": "Sessions", "Сессий: ": "Sessions: ",
    "Время в игре": "Playtime", "Последний запуск": "Last played",
    "Пока нет статистики\nЗапусти игру на PS3 — она появится здесь": "No statistics yet\nStart a PS3 game to see it here",
    "Сейчас в игре": "Currently playing", "Подсчёт приостановлен · нет данных PSN": "Tracking paused · PSN unavailable",
    "Последний запуск: ": "Last played: ", "Первая сессия: ": "First session: ", "Последняя сессия: ": "Last session: ",
    "Подробная история появится после обнаружения игры в этой версии.\nСтарые часы сохранены во вкладке «Игры».":
        "Session history starts with games detected in this version.\nPrevious playtime is kept in the Games tab.",
    "Показаны последние 100 сессий; все записи хранятся в базе. Длительность — наблюдаемое время, без сна и пропусков PSN.":
        "Showing the latest 100 sessions; all records are stored in the database. Duration excludes sleep and gaps in PSN data.",
    "Считается только наблюдаемое время при работающем приложении. Потеря PSN и сон компьютера не прибавляют игровое время.":
        "Only time observed while this app runs is counted. Sleep and gaps in PSN data do not add playtime.",
    "Подключение": "Connecting", "Подключение…": "Connecting…", "Ожидание PSN": "Waiting for PSN",
    "Ожидание Discord": "Waiting for Discord", "PSN подключён": "PSN connected",
    "Игра отображается": "Game displayed", "PS3 без игры": "PS3 idle", "Остановлено": "Stopped",
    "Подключён": "Connected", "Не подключён": "Disconnected", "Ожидание данных PSN": "Waiting for PSN data",
    "Срок неизвестен": "Expiry unknown", "Ошибка настройки": "Configuration error",
    "Активна: ": "Active: ", "NPSSO ещё не сохранён": "NPSSO not saved yet",
    "NPSSO сохранён": "NPSSO saved", "NPSSO загружен из .env": "NPSSO loaded from .env",
    "Осталось: ": "Remaining: ", "Срок действия неизвестен": "Expiry unknown",
    "Discord Application ID должен состоять из цифр": "Discord Application ID must contain digits only",
    "Интервал опроса должен быть целым числом не менее 15 секунд": "Polling interval must be an integer of at least 15 seconds",
    "В буфере нет NPSSO или JSON-ответа Sony": "Clipboard contains no NPSSO or Sony JSON response",
    "NPSSO получен. Нажми «Готово», затем «Сохранить» в настройках. Значение скрыто.":
        "NPSSO received. Click Done, then Save in Settings. Its value is hidden.",
    "NPSSO готов к сохранению. Нажми «Сохранить» в настройках. Значение скрыто.":
        "NPSSO ready to save. Click Save in Settings. Its value is hidden.",
    "База статистики недоступна; текущий подсчёт без сохранения: ": "Statistics database unavailable; current tracking is not saved: ",
    "Не удалось сохранить статистику: ": "Could not save statistics: ",
    "Не удалось сохранить тему: ": "Could not save theme: ", "Не удалось сохранить язык: ": "Could not save language: ",
    "Некорректная запись истории сессий": "Invalid session-history record",
    "Некорректная дата истории сессий": "Invalid session-history date",
    "Некорректная длительность истории сессий": "Invalid session-history duration",
    "Некорректная дата статистики игры": "Invalid game-statistics date",
    "Неизвестная версия базы статистики": "Unknown statistics database version",
    "Некорректная статистика игры": "Invalid game statistics",
    "Сессия завершена": "Session ended", "Смена игры": "Game changed", "Смена аккаунта": "Account changed",
    "Программа остановлена": "Application stopped", "Программа закрыта": "Application closed",
    "Прервана · последнее сохранённое наблюдение": "Interrupted · last saved observation",
    "Подготовка интерфейса…": "Preparing interface…", "Загрузка настроек и статистики…": "Loading settings and statistics…",
    "Открытие главного окна…": "Opening main window…",
    "Запуск подключения к PSN…": "Connecting to PSN…", "Открыть": "Open", "Выйти": "Quit",
    "Гирлянда: ": "Garland: ", "устройство вывода звука недоступно": "audio output device unavailable",
    "не удалось воспроизвести ": "could not play ",
}


def normalize_language(value: object) -> str:
    return value if value in ("ru", "en") else DEFAULT_LANGUAGE


def translate(text: str, language: str) -> str:
    if language != "en":
        return text
    if text in ENGLISH:
        return ENGLISH[text]
    # Diagnostics can append an exception or time to a translated prefix.
    for original in sorted(ENGLISH, key=len, reverse=True):
        if original.endswith((": ", "воспроизвести ")) and text.startswith(original):
            return ENGLISH[original] + translate(text[len(original):], language)
    return text
