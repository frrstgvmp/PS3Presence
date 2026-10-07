from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

from runtime_bootstrap import prepare_native_libraries

prepare_native_libraries()

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, Property, QThread, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
import transparent_animation  # Register the software-compatible QML GIF item.

from bridge import BridgePhase, BridgeSnapshot, PresenceBridge, MIN_POLL_INTERVAL_SECONDS, load_settings
from autostart import is_autostart_enabled, set_autostart_enabled
from garland_audio import GarlandAudio
from app_metadata import VERSION, DEFAULT_LIGHT_OFFSETS, AUTHOR_DISCORD_USERNAME, AUTHOR_DISCORD_USER_ID
from time_format import format_exact_remaining
from settings_store import APP_DATA_DIR, DEFAULT_THEME_ID, StoredConfiguration, is_new_year_theme_available, load_configuration, load_npsso, load_npsso_expires_at, save_configuration, save_npsso, save_theme
from game_statistics import GameTimeTracker, format_playtime
from game_statistics_model import GameStatisticsModel, SessionHistoryModel
from cover_art import load_local_cover_index
from localization import DEFAULT_LANGUAGE, translate
from settings_store import save_language


PROJECT_DIR = Path(__file__).resolve().parent
QML_FILE = PROJECT_DIR / "qml" / "Main.qml"
ICON_FILE = PROJECT_DIR / "assets" / "ps3-presence.ico"
WINDOW_TITLE = "PS3 Presence"
STATISTICS_FILE = APP_DATA_DIR / "game_statistics.sqlite3"

WINDOW_CAPTION_COLORS = {
    "botanical": ("#101b0d", "#f4fbe8"),
    "light": ("#edf2ee", "#17211f"),
    "oled": ("#000000", "#ffffff"),
    "terracotta": ("#211411", "#fff5ed"),
    "indigo": ("#0f1024", "#f5f4ff"),
    "sakura": ("#21121c", "#fff3f8"),
    "aurora": ("#151e29", "#eef5fc"),
    "newyear": ("#07130f", "#fff7df"),
}


def _windows_color_ref(hex_color: str) -> int:
    """Convert #RRGGBB to the COLORREF layout expected by Windows DWM."""
    red = int(hex_color[1:3], 16)
    green = int(hex_color[3:5], 16)
    blue = int(hex_color[5:7], 16)
    return red | (green << 8) | (blue << 16)


def apply_windows_caption_theme(window: object, theme_id: str) -> None:
    """Keep the native Windows 11 caption consistent with the app theme."""
    if sys.platform != "win32":
        return
    caption, text = WINDOW_CAPTION_COLORS.get(theme_id, WINDOW_CAPTION_COLORS[DEFAULT_THEME_ID])
    try:
        hwnd = ctypes.c_void_p(int(window.winId()))
        dwm = ctypes.WinDLL("dwmapi")
        dark_mode = ctypes.c_int(theme_id != "light")
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode))
        for attribute, color in ((35, caption), (36, text), (34, caption)):
            color_ref = ctypes.c_uint32(_windows_color_ref(color))
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(color_ref), ctypes.sizeof(color_ref))
    except (AttributeError, OSError, ValueError):
        # Older Windows versions simply retain their system-managed caption.
        return


class BridgeWorker(QObject):
    snapshot_changed = Signal(object)
    log_written = Signal(str)
    finished = Signal()

    def __init__(self, bridge: PresenceBridge) -> None:
        super().__init__()
        self.bridge = bridge

    @Slot()
    def run(self) -> None:
        try:
            self.bridge.run()
        finally:
            self.finished.emit()

    @Slot()
    def reconnect(self) -> None:
        self.bridge.request_reconnect()

    @Slot()
    def stop(self) -> None:
        self.bridge.stop()


class SecretThemeKeyFilter(QObject):
    """Read the literal digit sequence before Qt Quick forwards key events."""

    def __init__(self, window: object, controller: object) -> None:
        super().__init__(window)
        self.window = window
        self.controller = controller
        self._digits = ""
        window.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.WindowDeactivate:
            self._digits = ""
        if event.type() != QEvent.KeyPress:
            return False
        if not self.window.isActive() or self.window.property("settingsVisible") or self.window.property("npssoVisible") or self.window.property("statisticsVisible") or self.window.property("aboutVisible"):
            self._digits = ""
            return False
        if event.isAutoRepeat():
            return False
        blocked = Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier | Qt.ShiftModifier
        if event.modifiers() & blocked:
            self._digits = ""
            return False
        if Qt.Key_0 <= event.key() <= Qt.Key_9:
            self._digits = (self._digits + str(event.key() - Qt.Key_0))[-4:]
            if self._digits == "3112":
                self._digits = ""
                self.controller.toggleNewYearThemeButton()
                return True
        else:
            self._digits = ""
        return False


class PresenceController(QObject):
    changed = Signal()
    statistics_changed = Signal()
    log_received = Signal(str)
    open_settings_requested = Signal()
    theme_changed = Signal(str)
    language_changed = Signal()
    quit_requested = Signal()

    def __init__(self, *, statistics_path: Path | None = STATISTICS_FILE) -> None:
        super().__init__()
        try:
            stored_configuration = load_configuration()
        except ValueError:
            stored_configuration = StoredConfiguration()
        self._language = stored_configuration.language
        self._secret_leaf_images = {
            "botanical": QImage(str(PROJECT_DIR / "assets" / "botanical-cannabis-theme.png")),
            "default": QImage(str(PROJECT_DIR / "assets" / "botanical-theme.png")),
        }
        self._new_year_visibility_override: bool | None = None
        self._phase = "Подключение"
        self._bridge_phase: BridgePhase | None = BridgePhase.STARTING
        self._color = "#f0ad4e"
        self._psn = "Подключение…"
        self._avatar = ""
        self._discord = "Не подключён"
        self._game = "Игра не запущена"
        self._detail = "Ожидание данных PSN"
        self._cover = ""
        self._auth = "Срок неизвестен"
        self._logs: list[str] = []
        self._has_game = False
        self._statistics_error = ""
        self._local_covers = load_local_cover_index()
        self._statistics_model = GameStatisticsModel(self)
        self._history_model = SessionHistoryModel(self)
        self._statistics_sort_ascending = False
        self._statistics_sort_mode = "playtime"
        try:
            self._statistics = GameTimeTracker(statistics_path)
        except (OSError, ValueError, sqlite3.Error) as error:
            # Preserve a damaged/unknown database; never replace it with zeroes.
            self._statistics = GameTimeTracker(None)
            self._statistics_error = f"База статистики недоступна; текущий подсчёт без сохранения: {error}"
        self._update_statistics_model()
        self._garland_audio = GarlandAudio(self)
        self._garland_audio.warning.connect(self.append_log)
        self._bridge_expires_at: float | None = None
        try:
            self._npsso_source = "saved" if load_npsso() is not None else None
            self._npsso_expires_at = load_npsso_expires_at()
        except ValueError:
            # The bridge will still try its normal credential sources.  This
            # keeps the UI usable if a DPAPI credential is unavailable.
            self._npsso_expires_at = None
            self._npsso_source = None
        if self._npsso_source is None:
            try:
                if load_settings().npsso:
                    self._npsso_source = "environment"
            except ValueError:
                pass
        self._worker: BridgeWorker | None = None
        self._thread: QThread | None = None
        self._restart_after_stop = False
        self._settings_client_id = ""
        self._settings_interval = 30
        self._settings_image = ""
        self._settings_autostart = False
        self._settings_error = ""
        self._npsso_message = self._saved_npsso_status()
        self._pending_npsso = ""
        self._pending_expires_in: int | None = None
        self._npsso_edit_backup: tuple[str, int | None, str] | None = None
        statistics_poll_interval = 30
        self._light_offsets = {**DEFAULT_LIGHT_OFFSETS, **stored_configuration.light_offsets}
        self._theme_id = stored_configuration.theme_id
        statistics_poll_interval = stored_configuration.poll_interval or 30
        self._statistics.stale_after = max(90, statistics_poll_interval * 3)
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._refresh_auth)
        self._clock.start(1_000)

    def _get(self, name: str) -> str:
        return getattr(self, name)

    @Slot(str, result=str)
    def translate(self, text: str) -> str:
        return translate(text, self._language)

    language = Property(str, lambda self: self._language, notify=language_changed)

    @Slot(str)
    def saveLanguage(self, language: str) -> None:
        if language not in ("ru", "en") or language == self._language:
            return
        try:
            self._language = save_language(language)
        except (OSError, ValueError) as error:
            self.append_log(f"Не удалось сохранить язык: {error}")
            return
        if not self._pending_npsso:
            self._npsso_message = self._saved_npsso_status()
        self._refresh_auth()
        self.language_changed.emit()
        self.changed.emit()

    def _saved_npsso_status(self) -> str:
        if self._npsso_source is None:
            return self.translate("NPSSO ещё не сохранён")
        source_text = self.translate("NPSSO сохранён" if self._npsso_source == "saved" else "NPSSO загружен из .env")
        expires_at = self._npsso_expires_at or self._bridge_expires_at
        if expires_at:
            return f"{source_text}. {self.translate('Осталось: ')}{format_exact_remaining(expires_at, language=self._language)}"
        return f"{source_text}. {self.translate('Срок действия неизвестен')}"

    def _psn_connection_state(self) -> str:
        if self._bridge_phase in (BridgePhase.STARTING, BridgePhase.WAITING_FOR_PSN):
            return "connecting"
        if self._bridge_phase in (BridgePhase.WAITING_FOR_DISCORD, BridgePhase.WATCHING, BridgePhase.ACTIVE, BridgePhase.IDLE):
            return "online"
        return "offline"

    phase = Property(str, lambda self: self.translate(self._phase), notify=changed)
    psnConnectionState = Property(str, _psn_connection_state, notify=changed)
    color = Property(str, lambda self: self._color, notify=changed)
    psn = Property(str, lambda self: self.translate(self._psn) if self._psn == "Подключение…" else self._psn, notify=changed)
    avatar = Property(str, lambda self: self._avatar, notify=changed)
    garlandAudio = Property(QObject, lambda self: self._garland_audio, constant=True)
    version = Property(str, lambda self: VERSION, constant=True)
    authorDiscordUsername = Property(str, lambda self: AUTHOR_DISCORD_USERNAME, constant=True)
    discord = Property(str, lambda self: self.translate(self._discord), notify=changed)
    game = Property(str, lambda self: self._game if self._has_game else self.translate(self._game), notify=changed)
    detail = Property(str, lambda self: self._detail if self._has_game else self.translate(self._detail), notify=changed)
    cover = Property(str, lambda self: self._cover, notify=changed)
    hasGame = Property(bool, lambda self: self._has_game, notify=changed)
    sessionElapsed = Property(str, lambda self: self._statistics.session_elapsed, notify=changed)
    gameStatistics = Property(QObject, lambda self: self._statistics_model, constant=True)
    statisticsSortAscending = Property(bool, lambda self: self._statistics_sort_ascending, notify=statistics_changed)
    statisticsSortMode = Property(str, lambda self: self._statistics_sort_mode, notify=statistics_changed)
    sessionHistory = Property(QObject, lambda self: self._history_model, constant=True)
    statisticsAccount = Property(str, lambda self: self._statistics.account or "—", notify=statistics_changed)
    statisticsError = Property(str, lambda self: self.translate(self._statistics_error), notify=statistics_changed)
    statisticsSince = Property(str, lambda self: self._statistics.format_collection_started_date(self._language), notify=statistics_changed)
    totalPlaytime = Property(str, lambda self: format_playtime(sum(row["totalSeconds"] for row in self._statistics.rows())), notify=statistics_changed)
    auth = Property(str, lambda self: self.translate(self._auth), notify=changed)
    logs = Property(str, lambda self: "\n".join(entry[:11] + self.translate(entry[11:]) for entry in self._logs), notify=changed)
    settingsClientId = Property(str, lambda self: self._settings_client_id, notify=changed)
    settingsInterval = Property(int, lambda self: self._settings_interval, notify=changed)
    settingsImage = Property(str, lambda self: self._settings_image, notify=changed)
    settingsAutostart = Property(bool, lambda self: self._settings_autostart, notify=changed)
    settingsError = Property(str, lambda self: self.translate(self._settings_error), notify=changed)
    npssoMessage = Property(str, lambda self: self.translate(self._npsso_message), notify=changed)
    lightOffsets = Property(str, lambda self: json.dumps(self._light_offsets), notify=changed)
    themeId = Property(str, lambda self: self._theme_id, notify=changed)
    defaultThemeId = Property(str, lambda self: DEFAULT_THEME_ID, constant=True)
    newYearThemeAvailable = Property(bool, lambda self: self._new_year_theme_available(), notify=changed)

    def _new_year_theme_available(self) -> bool:
        if self._new_year_visibility_override is not None:
            return self._new_year_visibility_override
        return is_new_year_theme_available()

    @Slot()
    def toggleNewYearThemeButton(self) -> None:
        self._new_year_visibility_override = not self._new_year_theme_available()
        if not self._new_year_visibility_override and self._theme_id == "newyear":
            self.saveTheme(DEFAULT_THEME_ID)
        else:
            self.changed.emit()

    def start(self) -> None:
        try:
            bridge = PresenceBridge(load_settings())
            self._statistics.stale_after = max(90, bridge.settings.poll_interval * 3)
        except ValueError as error:
            self._phase, self._color, self._detail = "Ошибка настройки", "#ef4444", str(error)
            self._bridge_phase = None
            self.changed.emit()
            return
        self._thread = QThread(self)
        self._worker = BridgeWorker(bridge)
        self._worker.moveToThread(self._thread)
        bridge.set_callbacks(on_status=self._worker.snapshot_changed.emit, on_log=self._worker.log_written.emit)
        self._thread.started.connect(self._worker.run)
        self._worker.snapshot_changed.connect(self.set_snapshot)
        self._worker.log_written.connect(self.append_log)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._on_worker_finished)
        self._thread.start()

    @Slot(object)
    def set_snapshot(self, snapshot: BridgeSnapshot) -> None:
        self._bridge_phase = snapshot.phase
        if snapshot.game and snapshot.game.title_id and snapshot.local_cover_url:
            self._local_covers[snapshot.game.title_id] = snapshot.local_cover_url
        self._has_game = bool(snapshot.game and snapshot.game.is_online and snapshot.game.is_ps3 and snapshot.game.title_name)
        new_session = self._statistics.observe(snapshot.game, snapshot.online_id, snapshot.cover_url,
            started_at=snapshot.game_started_at,
            end_reason="stopped" if snapshot.phase == BridgePhase.STOPPED else "idle",
            confirmed_idle=snapshot.phase in (BridgePhase.IDLE, BridgePhase.STOPPED) or (snapshot.phase == BridgePhase.WATCHING and snapshot.game is None))
        self._flush_statistics(force=new_session or snapshot.phase in (BridgePhase.IDLE, BridgePhase.STOPPED))
        self._update_statistics_model()
        labels = {
            BridgePhase.STARTING: ("Подключение", "#f0ad4e"), BridgePhase.WAITING_FOR_PSN: ("Ожидание PSN", "#f0ad4e"),
            BridgePhase.WAITING_FOR_DISCORD: ("Ожидание Discord", "#f0ad4e"), BridgePhase.WATCHING: ("PSN подключён", "#5cb85c"),
            BridgePhase.ACTIVE: ("Игра отображается", "#60a5fa"), BridgePhase.IDLE: ("PS3 без игры", "#94a3b8"),
            BridgePhase.STOPPED: ("Остановлено", "#ef4444"),
        }
        self._phase, self._color = labels[snapshot.phase]
        self._psn = snapshot.online_id or "—"
        self._avatar = snapshot.avatar_url or ""
        self._discord = "Подключён" if snapshot.discord_connected else "Не подключён"
        self._game = snapshot.game.title_name if snapshot.game else "Игра не запущена"
        self._detail = (snapshot.game.game_status or "PlayStation 3") if snapshot.game else snapshot.message
        self._cover = (snapshot.local_cover_url or snapshot.cover_url or snapshot.game.title_icon_url or "") if snapshot.game else ""
        self._bridge_expires_at = snapshot.refresh_token_expires_at
        self._refresh_auth()
        self.changed.emit()

    @Slot(str)
    def append_log(self, message: str) -> None:
        entry = f"[{datetime.now():%H:%M:%S}] {message}"
        self._logs = (self._logs + [entry])[-120:]
        print(entry[:11] + self.translate(entry[11:]), flush=True)
        self.changed.emit()

    @Slot()
    def _refresh_auth(self) -> None:
        self._statistics.advance()
        self._flush_statistics()
        self._update_statistics_model()
        expiry = self._npsso_expires_at or self._bridge_expires_at
        self._auth = f"{self.translate('Активна: ')}{format_exact_remaining(expiry, language=self._language)}" if expiry else "Срок неизвестен"
        self.changed.emit()

    def _update_statistics_model(self) -> None:
        games = self._statistics.rows(language=self._language)
        sort_field = "lastPlayedAt" if self._statistics_sort_mode == "lastPlayed" else "totalSeconds"
        direction = 1 if self._statistics_sort_ascending else -1
        games = sorted(games, key=lambda row: (direction * row.get(sort_field, 0), row["title"].casefold(), row["gameKey"]))
        sessions = self._statistics.history_rows(language=self._language)
        for row in games + sessions:
            local = self._local_covers.get(row.get("gameKey"))
            if local:
                row["coverUrl"] = local
        self._statistics_model.update(games)
        self._history_model.update(sessions)
        self.statistics_changed.emit()

    def _flush_statistics(self, *, force=False) -> None:
        try:
            saved = self._statistics.flush(force=force)
            if saved and self._statistics_error.startswith("Не удалось сохранить статистику:"):
                self._statistics_error = ""
        except (OSError, ValueError, sqlite3.Error) as error:
            message = f"Не удалось сохранить статистику: {error}"
            if message != self._statistics_error:
                self._statistics_error = message
                self.append_log(message)

    @Slot()
    def shutdownStatistics(self) -> None:
        self._clock.stop()
        self._statistics.advance()
        self._statistics.finish_session("closed")
        self._flush_statistics(force=True)

    @Slot()
    def refreshStatistics(self) -> None:
        self._statistics.advance()
        self._update_statistics_model()

    @Slot(str)
    def sortStatisticsBy(self, mode: str) -> None:
        if mode not in ("playtime", "lastPlayed"):
            return
        self._statistics_sort_ascending = not self._statistics_sort_ascending if mode == self._statistics_sort_mode else False
        self._statistics_sort_mode = mode
        self._update_statistics_model()

    @Slot()
    def reconnect(self) -> None:
        if self._worker:
            self._worker.reconnect()

    @Slot()
    def openSettings(self) -> None:
        stored = load_configuration()
        self._settings_client_id = stored.discord_client_id or ""
        self._settings_interval = stored.poll_interval or 30
        self._settings_image = stored.large_image or ""
        self._settings_autostart = is_autostart_enabled()
        self._settings_error = ""
        if not self._pending_npsso:
            self._npsso_message = self._saved_npsso_status()
        self.changed.emit()
        self.open_settings_requested.emit()

    @Slot(str, int, str, bool, result=bool)
    def saveSettings(self, client_id: str, interval: int, image: str, autostart: bool) -> bool:
        self._settings_error = ""
        client_id = client_id.strip()
        if not client_id.isdigit():
            self._settings_error = "Discord Application ID должен состоять из цифр"
            self.changed.emit()
            return False
        if interval < MIN_POLL_INTERVAL_SECONDS:
            self._settings_error = f"Интервал опроса должен быть целым числом не менее {MIN_POLL_INTERVAL_SECONDS} секунд"
            self.changed.emit()
            return False
        try:
            set_autostart_enabled(autostart)
            existing = load_configuration()
            save_configuration(StoredConfiguration(client_id, interval, image.strip() or None, existing.light_offsets, existing.theme_id, existing.language))
            self._settings_client_id = client_id
            self._settings_interval = interval
            self._settings_image = image.strip()
            self._settings_autostart = autostart
            if self._pending_npsso:
                save_npsso(self._pending_npsso, self._pending_expires_in)
                self._npsso_source = "saved"
                self._pending_npsso = ""
                self._pending_expires_in = None
            self._npsso_expires_at = load_npsso_expires_at()
            self._npsso_message = self._saved_npsso_status()
            self.changed.emit()
            self.restart()
            return True
        except (OSError, RuntimeError, ValueError) as error:
            self._settings_error = str(error)
            self.changed.emit()
            return False

    @Slot(str)
    def saveTheme(self, theme_id: str) -> None:
        try:
            if theme_id == "newyear" and not self._new_year_theme_available():
                return
            if theme_id == "newyear" and not is_new_year_theme_available():
                # The secret code unlocks an out-of-season theme only for this
                # session; the normally persisted theme remains unchanged.
                self._theme_id = "newyear"
            else:
                self._theme_id = save_theme(theme_id)
            self.changed.emit()
            self.theme_changed.emit(self._theme_id)
        except (OSError, ValueError) as error:
            self._npsso_message = f"Не удалось сохранить тему: {error}"
            self.changed.emit()

    @Slot(float, float, result=bool)
    def isSecretLeafHit(self, x: float, y: float) -> bool:
        """Accept only visible pixels of the bottom leaf, not its stem or empty space."""
        px, py = int(x * 1536 / 680), int(y * 1536 / 680)
        botanical = self._theme_id == "botanical"
        image = self._secret_leaf_images["botanical" if botanical else "default"]
        left, top, right, bottom = (1415, 932, 1536, 1012) if botanical else (1462, 934, 1502, 995)
        return (self._theme_id != "newyear" and left <= px < right and top <= py < bottom
                and not image.isNull() and image.pixelColor(px, py).alpha() >= 96)

    @Slot()
    def openSonyLogin(self) -> None:
        QDesktopServices.openUrl(QUrl("https://www.playstation.com/"))

    @Slot(result=bool)
    def openAuthorDiscord(self) -> bool:
        """Prefer the desktop profile, with a web link if no handler is installed."""
        # Discord's '-' authority is rejected by QUrl's hostname validation.
        # Windows accepts the application's original protocol URI directly.
        if sys.platform == "win32":
            try:
                os.startfile(f"discord://-/users/{AUTHOR_DISCORD_USER_ID}")
                return True
            except OSError:
                pass
        return QDesktopServices.openUrl(QUrl(f"https://discord.com/users/{AUTHOR_DISCORD_USER_ID}"))

    @Slot()
    def copyAuthorDiscordUsername(self) -> None:
        QApplication.clipboard().setText(AUTHOR_DISCORD_USERNAME)

    @Slot()
    def openSsoCookie(self) -> None:
        QDesktopServices.openUrl(QUrl("https://ca.account.sony.com/api/v1/ssocookie"))

    @Slot()
    def beginNpssoEdit(self) -> None:
        if self._npsso_edit_backup is None:
            self._npsso_edit_backup = (self._pending_npsso, self._pending_expires_in, self._npsso_message)

    @Slot()
    def cancelNpssoEdit(self) -> None:
        if self._npsso_edit_backup is not None:
            self._pending_npsso, self._pending_expires_in, self._npsso_message = self._npsso_edit_backup
            self._npsso_edit_backup = None
            if not self._pending_npsso:
                self._npsso_message = self._saved_npsso_status()
            self.changed.emit()

    @Slot()
    def confirmNpssoEdit(self) -> None:
        # Keep the confirmed token pending until the main settings are saved.
        self._npsso_edit_backup = None
        if self._pending_npsso:
            self._npsso_message = "NPSSO готов к сохранению. Нажми «Сохранить» в настройках. Значение скрыто."
            self.changed.emit()

    @Slot()
    def pasteNpsso(self) -> None:
        raw = QApplication.clipboard().text().strip()
        try:
            payload = json.loads(raw)
            value = payload.get("npsso") if isinstance(payload, dict) else None
            expires = payload.get("expires_in") if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            value, expires = raw, None
        if not isinstance(value, str) or not value.strip():
            self._npsso_message = "В буфере нет NPSSO или JSON-ответа Sony"
        else:
            self._pending_npsso = value.strip()
            self._pending_expires_in = expires if isinstance(expires, int) and expires > 0 else None
            self._npsso_message = "NPSSO получен. Нажми «Готово», затем «Сохранить» в настройках. Значение скрыто."
        self.changed.emit()

    @Slot()
    def quit(self) -> None:
        self.quit_requested.emit()

    def restart(self) -> None:
        try:
            self._npsso_expires_at = load_npsso_expires_at()
        except ValueError:
            self._npsso_expires_at = None
        if self._worker:
            self._restart_after_stop = True
            self._worker.stop()
        else:
            self.start()

    @Slot()
    def _on_worker_finished(self) -> None:
        self._worker = None
        self._thread = None
        if self._restart_after_stop:
            self._restart_after_stop = False
            QTimer.singleShot(0, self.start)


def show_main_window(window: object, splash: object | None = None) -> None:
    """Hand off to Qt Quick without QSplashScreen.finish(QWidget)'s type mismatch.

    Interface readiness, not PSN/Discord connectivity, ends the startup screen.
    The same path also safely restores the main window from the tray.
    """
    window.showNormal()
    if splash is not None:
        splash.close()
    window.raise_()
    window.requestActivate()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tray", action="store_true")
    parser.add_argument("--software-rendering", action="store_true",
                        help="Render the 2D interface on the CPU, without a 3D graphics device")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-test-audio", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    software_api = None
    if args.software_rendering:
        from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
        software_api = QSGRendererInterface.GraphicsApi.Software
        QQuickWindow.setGraphicsApi(software_api)
    QQuickStyle.setStyle("Basic")
    app = QApplication(sys.argv[:1])
    icon = QIcon(str(ICON_FILE))
    app.setWindowIcon(icon)
    app.setQuitOnLastWindowClosed(False)
    splash = None
    startup_elapsed = QElapsedTimer()
    startup_elapsed.start()
    if not args.tray and not (args.smoke_test or args.smoke_test_audio):
        from startup_screen import StartupScreen
        try:
            startup_language = load_configuration().language
        except ValueError:
            startup_language = DEFAULT_LANGUAGE
        splash = StartupScreen(icon, language=startup_language)
        app.aboutToQuit.connect(splash.close)
        splash.show()
        app.processEvents()
    controller = PresenceController(statistics_path=None if args.smoke_test or args.smoke_test_audio else STATISTICS_FILE)
    if splash is not None:
        splash.set_stage("Загрузка настроек и статистики…", 0.5)
        app.processEvents()
    app.aboutToQuit.connect(controller.shutdownStatistics)
    app.aboutToQuit.connect(controller.garlandAudio.shutdown)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("presence", controller)
    engine.load(QUrl.fromLocalFile(str(QML_FILE)))
    if not engine.rootObjects():
        if splash is not None:
            splash.close()
        return 1
    window = engine.rootObjects()[0]
    key_filter = SecretThemeKeyFilter(window, controller)
    apply_windows_caption_theme(window, controller.themeId)
    if args.smoke_test or args.smoke_test_audio:
        from release_checks import run_release_checks
        return run_release_checks(app, controller, engine, window,
                                  tuple(WINDOW_CAPTION_COLORS), with_audio=args.smoke_test_audio,
                                  expected_graphics_api=software_api)
    tray = QSystemTrayIcon(icon, app)
    menu = QMenu()
    show_action = QAction("Открыть", menu)
    reconnect_action = QAction("Переподключить Discord", menu); reconnect_action.triggered.connect(controller.reconnect)
    quit_action = QAction("Выйти", menu); quit_action.triggered.connect(controller.quit)
    def update_tray_language():
        show_action.setText(controller.translate("Открыть"))
        reconnect_action.setText(controller.translate("Переподключить Discord"))
        quit_action.setText(controller.translate("Выйти"))
    update_tray_language()
    controller.language_changed.connect(update_tray_language)
    menu.addActions([show_action, reconnect_action]); menu.addSeparator(); menu.addAction(quit_action)
    tray.setContextMenu(menu); tray.show()
    def show_window():
        show_main_window(window, splash)
    show_action.triggered.connect(show_window)
    tray.activated.connect(lambda reason: show_window() if reason in (
        QSystemTrayIcon.ActivationReason.Trigger,
        QSystemTrayIcon.ActivationReason.DoubleClick,
    ) else None)
    controller.open_settings_requested.connect(lambda: window.setProperty("settingsVisible", True))
    controller.theme_changed.connect(lambda theme_id: apply_windows_caption_theme(window, theme_id))
    controller.quit_requested.connect(app.quit)
    controller.changed.connect(lambda: tray.setToolTip(f"{WINDOW_TITLE}: {controller.game}"))
    controller.start()
    if not args.tray:
        if splash is not None:
            splash.set_stage("Открытие главного окна…", 1.0)
        QTimer.singleShot(max(0, 650 - startup_elapsed.elapsed()), show_window)
    return app.exec()
