from __future__ import annotations

from runtime_bootstrap import prepare_native_libraries

prepare_native_libraries()

import asyncio
import os
import sys
import threading
import time
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pypresence.types import StatusDisplayType
from psnawp_api import PSNAWP
from psnawp_api.models.trophies import PlatformType
from psnawp_api.utils.endpoints import API_PATH, BASE_PATH

from game_status_history import record_game_observation
from cover_art import CoverResolver, IMAGE_PROXY_URL, square_cover_url
from presence_parser import LegacyPresence, extract_legacy_presences, select_active_ps3_game
from settings_store import load_configuration, load_npsso


# A frozen build lives next to its optional local .env file; during development
# the project folder remains the source file's directory.
PROJECT_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
MIN_POLL_INTERVAL_SECONDS = 15
RPC_REFRESH_INTERVAL_SECONDS = 60
RPC_CONNECT_TIMEOUT_SECONDS = 15
AUTH_EXPIRY_WARNING_SECONDS = 3 * 24 * 60 * 60
STATUS_DATABASE_FILE = PROJECT_DIR / "observed_game_statuses.json"
LEGACY_PROFILE_FIELDS = (
    "npId,onlineId,accountId,avatarUrls,plus,aboutMe,languagesUsed,"
    "trophySummary(@default,level,progress,earnedTrophies),isOfficiallyVerified,"
    "personalDetail(@default,profilePictureUrls),personalDetailSharing,"
    "personalDetailSharingRequestMessageFlag,primaryOnlineStatus,"
    "presences(@default,@titleInfo,platform,lastOnlineDate,hasBroadcastData,gameStatus),"
    "requestMessageFlag,blocking,friendRelation,following,consoleAvailability"
)


@dataclass(frozen=True, slots=True)
class BridgeSettings:
    npsso: str
    discord_client_id: str | None
    poll_interval: int
    large_image: str | None


class BridgePhase(str, Enum):
    STARTING = "starting"
    WAITING_FOR_PSN = "waiting_for_psn"
    WAITING_FOR_DISCORD = "waiting_for_discord"
    WATCHING = "watching"
    ACTIVE = "active"
    IDLE = "idle"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class BridgeSnapshot:
    phase: BridgePhase
    message: str
    online_id: str | None = None
    game: LegacyPresence | None = None
    discord_connected: bool = False
    refresh_token_expires_at: float | None = None
    cover_url: str | None = None
    avatar_url: str | None = None
    game_started_at: int | None = None
    local_cover_url: str | None = None


StatusCallback = Callable[[BridgeSnapshot], None]
LogCallback = Callable[[str], None]


def extract_profile_avatar(payload: dict[str, Any]) -> str | None:
    """Read public avatar artwork already included in the legacy PSN profile."""
    profile = payload.get("profile", payload)
    if not isinstance(profile, dict):
        return None

    # The legacy endpoint returns avatarUrls for most profiles.  Some accounts
    # expose the same public image only via personalDetail.profilePictureUrls.
    # Accept both shapes so the UI does not lose an otherwise available avatar.
    candidate_lists: list[list[Any]] = []
    avatars = profile.get("avatarUrls")
    if isinstance(avatars, list):
        candidate_lists.append(avatars)
    personal_detail = profile.get("personalDetail")
    if isinstance(personal_detail, dict):
        pictures = personal_detail.get("profilePictureUrls")
        if isinstance(pictures, list):
            candidate_lists.append(pictures)

    sizes = {"xs": 16, "s": 32, "m": 64, "l": 128, "xl": 256}
    valid_avatars: list[tuple[int, str]] = []
    for candidates in candidate_lists:
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            url = candidate.get("avatarUrl", candidate.get("profilePictureUrl"))
            if not isinstance(url, str):
                continue
            url = url.strip()
            try:
                parsed = urlsplit(url)
            except ValueError:
                continue
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                continue
            size = str(candidate.get("size", "")).casefold()
            rank = sizes.get(size, int(size) if size.isdecimal() else 0)
            valid_avatars.append((rank, url))
    # Keep list order as a tie-breaker: avatarUrls is the PSN avatar requested
    # for the card, while profilePictureUrls is a useful fallback.
    return max(valid_avatars, key=lambda avatar: avatar[0])[1] if valid_avatars else None


def load_settings() -> BridgeSettings:
    load_dotenv(PROJECT_DIR / ".env", override=False)
    stored = load_configuration()

    npsso = load_npsso() or os.getenv("NPSSO", "").strip()
    if not npsso:
        raise ValueError("NPSSO is not configured. Add it in Settings or locally in .env.")

    discord_client_id = stored.discord_client_id or os.getenv("DISCORD_CLIENT_ID", "").strip() or None
    large_image = stored.large_image or os.getenv("DISCORD_LARGE_IMAGE", "").strip() or None

    raw_interval = str(stored.poll_interval or os.getenv("POLL_INTERVAL", "30").strip())
    try:
        poll_interval = int(raw_interval)
    except ValueError as error:
        raise ValueError("POLL_INTERVAL must be an integer.") from error
    if poll_interval < MIN_POLL_INTERVAL_SECONDS:
        raise ValueError(f"POLL_INTERVAL must be at least {MIN_POLL_INTERVAL_SECONDS} seconds.")

    return BridgeSettings(npsso, discord_client_id, poll_interval, large_image)


def get_legacy_profile_with_game_status(client: Any) -> dict[str, Any]:
    """Call PSNAWP's legacy profile endpoint while explicitly requesting gameStatus."""
    url = (
        f"{BASE_PATH['legacy_profile_uri']}"
        f"{API_PATH['legacy_profile'].format(online_id=client.online_id)}"
    )
    return client.authenticator.get(url=url, params={"fields": LEGACY_PROFILE_FIELDS}).json()


def fetch_legacy_profile(npsso: str) -> tuple[str, dict[str, Any]]:
    psn = PSNAWP(npsso)
    client = psn.me()
    return client.online_id, get_legacy_profile_with_game_status(client)


def discord_update_arguments(game: LegacyPresence, started_at: int, large_image: str | None) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "details": game.title_name or "Unknown game",
        # Show the game title, not the Discord application's name, in compact status.
        "status_display_type": StatusDisplayType.DETAILS,
        "start": started_at,
    }
    if game.game_status:
        arguments["state"] = game.game_status[:128]
    if large_image:
        arguments["large_image"] = large_image
        arguments["large_text"] = "PlayStation 3"
    return arguments


def resolve_ps3_cover_url(psn: PSNAWP, game: LegacyPresence, *, resolver: CoverResolver | None = None) -> str | None:
    """Check PSN artwork before falling back to GameTDB's PS3 catalog."""
    source = game.title_icon_url
    if not source and game.title_id:
        try:
            title = psn.game_title(title_id=game.title_id, platform=PlatformType.PS3, np_communication_id="ICON_ONLY")
            source = title.get_title_icon_url()
        except Exception:
            pass
    if resolver is not None:
        return resolver.resolve(game, source)
    temporary = CoverResolver()
    try:
        return temporary.resolve(game, source)
    finally:
        temporary.close()


def close_rpc_safely(rpc: Any | None) -> None:
    if rpc is None:
        return
    try:
        rpc.close()
    except Exception:
        pass


def connect_rpc_with_timeout(rpc: Any) -> None:
    """Bound the Discord handshake, including its otherwise unbounded first read."""
    rpc.loop.run_until_complete(asyncio.wait_for(rpc.handshake(), timeout=RPC_CONNECT_TIMEOUT_SECONDS))


def refresh_token_expiration(psn: PSNAWP) -> float | None:
    """Return the expiry timestamp exposed by PSNAWP without reading token text."""
    value = getattr(psn.authenticator, "refresh_token_expiration_time", 0)
    try:
        expiry = float(value)
    except (TypeError, ValueError):
        return None
    return expiry if expiry > time.time() else None


class PresenceBridge:
    """Blocking PSN-to-Discord worker with UI-safe status and reconnect hooks."""

    def __init__(
        self,
        settings: BridgeSettings,
        *,
        on_status: StatusCallback | None = None,
        on_log: LogCallback | None = None,
    ) -> None:
        if not settings.discord_client_id:
            raise ValueError("DISCORD_CLIENT_ID is empty. Set it in .env, or use --once for the PSN-only test.")
        self.settings = settings
        self._on_status = on_status
        self._on_log = on_log or print
        self._stop_event = threading.Event()
        self._reconnect_event = threading.Event()
        self._avatar_online_id: str | None = None
        self._avatar_url: str | None = None
        self._game_started_at: int | None = None
        self._game_cover_url: str | None = None
        self._game_cover_local_url: str | None = None

    def stop(self) -> None:
        self._stop_event.set()

    def request_reconnect(self) -> None:
        """Ask the worker to recreate its Discord RPC connection on the next loop."""
        self._reconnect_event.set()

    def set_callbacks(
        self,
        *,
        on_status: StatusCallback | None = None,
        on_log: LogCallback | None = None,
    ) -> None:
        """Attach observers without exposing the worker's internal state."""
        self._on_status = on_status
        self._on_log = on_log or print

    def _log(self, message: str) -> None:
        self._on_log(message)

    def _publish(self, snapshot: BridgeSnapshot) -> None:
        if self._on_status is None:
            return
        if snapshot.avatar_url is None and snapshot.online_id == self._avatar_online_id:
            snapshot = replace(snapshot, avatar_url=self._avatar_url)
        if snapshot.game is not None and snapshot.game_started_at is None:
            snapshot = replace(snapshot, game_started_at=self._game_started_at)
        if snapshot.game is not None and snapshot.cover_url is None:
            snapshot = replace(snapshot, cover_url=self._game_cover_url)
        if snapshot.game is not None and snapshot.local_cover_url is None:
            snapshot = replace(snapshot, local_cover_url=self._game_cover_local_url)
        try:
            self._on_status(snapshot)
        except Exception:
            # A GUI callback must never take down the bridge.
            self._log("Status callback failed; continuing without interrupting the bridge.")

    def _wait(self, seconds: float) -> bool:
        return self._stop_event.wait(seconds)

    def run(self) -> None:
        from pypresence import Presence

        self._publish(BridgeSnapshot(BridgePhase.STARTING, "Starting PSN bridge."))
        psn: PSNAWP | None = None
        client: Any | None = None
        rpc: Presence | None = None
        initial_identity = object()
        last_rpc_identity: object | tuple[str | None, str | None, str | None] | None = initial_identity
        last_recorded_identity: object | tuple[str | None, str | None, str | None] | None = initial_identity
        last_game_identity: object | tuple[str | None, str | None] | None = initial_identity
        last_cover_url: str | None = None
        last_rpc_sync = 0.0
        last_expiry_warning_day: int | None = None
        started_at = int(time.time())
        covers = CoverResolver(log=self._log, cancelled=self._stop_event.is_set)

        try:
            while not self._stop_event.is_set():
                if client is None or psn is None:
                    self._publish(BridgeSnapshot(BridgePhase.WAITING_FOR_PSN, "Connecting to PlayStation Network."))
                    try:
                        psn = PSNAWP(self.settings.npsso)
                        client = psn.me()
                        self._log(f"Watching legacy PSN presence for {client.online_id}.")
                    except Exception as error:
                        self._log(f"PSN connection failed ({type(error).__name__}); retrying in {self.settings.poll_interval} seconds.")
                        self._wait(self.settings.poll_interval)
                        continue

                if self._reconnect_event.is_set():
                    self._reconnect_event.clear()
                    close_rpc_safely(rpc)
                    rpc = None
                    last_rpc_identity = initial_identity
                    self._log("Discord reconnect requested.")

                try:
                    payload = get_legacy_profile_with_game_status(client)
                except Exception as error:
                    self._publish(BridgeSnapshot(BridgePhase.WAITING_FOR_PSN, "PSN request failed; retrying.", client.online_id))
                    self._log(f"PSN request failed ({type(error).__name__}); retrying in {self.settings.poll_interval} seconds.")
                    self._wait(self.settings.poll_interval)
                    continue

                if self._avatar_online_id != client.online_id:
                    self._avatar_url = None
                self._avatar_online_id = client.online_id
                self._avatar_url = extract_profile_avatar(payload) or self._avatar_url
                game = select_active_ps3_game(extract_legacy_presences(payload))
                token_expiry = refresh_token_expiration(psn)
                if token_expiry is not None:
                    remaining_seconds = token_expiry - time.time()
                    remaining_days = max(0, int(remaining_seconds // 86_400))
                    if remaining_seconds <= AUTH_EXPIRY_WARNING_SECONDS and remaining_days != last_expiry_warning_day:
                        self._log(f"PSN authorization may expire in about {remaining_days + 1} day(s); update NPSSO in Settings.")
                        last_expiry_warning_day = remaining_days
                rpc_identity = (game.title_id, game.title_name, game.game_status) if game else None
                game_identity = (game.title_id or (game.title_name or "").casefold(), game.platform) if game else None

                if game and rpc_identity != last_recorded_identity:
                    try:
                        record_game_observation(game, STATUS_DATABASE_FILE)
                        if game.game_status:
                            self._log(f"PSN gameStatus detected: {game.game_status}")
                        last_recorded_identity = rpc_identity
                    except Exception as error:
                        self._log(f"Game-status history update failed ({type(error).__name__}).")

                identity_changed = rpc_identity != last_rpc_identity
                game_changed = game_identity != last_game_identity
                refresh_due = time.monotonic() - last_rpc_sync >= RPC_REFRESH_INTERVAL_SECONDS
                # PSN observation defines a session, never the success of RPC.
                if game_changed:
                    self._game_started_at = started_at = int(time.time()) if game else None
                    last_game_identity = game_identity
                    last_cover_url = None
                    self._game_cover_url = None
                    self._game_cover_local_url = None
                self._publish(BridgeSnapshot(BridgePhase.WATCHING, "PSN presence updated.", client.online_id,
                    game, rpc is not None, token_expiry, last_cover_url))
                if game and (game_changed or (last_cover_url is None and refresh_due)):
                    last_cover_url = resolve_ps3_cover_url(psn, game, resolver=covers)
                    self._game_cover_url = last_cover_url
                    self._game_cover_local_url = covers.local_url(last_cover_url)
                if identity_changed or refresh_due:
                    synced = False
                    for attempt in range(2):
                        try:
                            if rpc is None:
                                self._publish(BridgeSnapshot(BridgePhase.WAITING_FOR_DISCORD, "Connecting to Discord.", client.online_id, game))
                                rpc = Presence(self.settings.discord_client_id, connection_timeout=RPC_CONNECT_TIMEOUT_SECONDS, response_timeout=10)
                                connect_rpc_with_timeout(rpc)
                                self._log("Discord RPC connected.")

                            if game:
                                cover_url = last_cover_url
                                selected_image = cover_url or self.settings.large_image
                                rpc.update(**discord_update_arguments(game, started_at, selected_image))
                                self._log(f"Discord updated: {game.title_name} [PS3]")
                                if cover_url:
                                    self._log(f"Game cover updated: {cover_url}")
                                elif self.settings.large_image:
                                    self._log(f"Cover fallback asset: {self.settings.large_image}")
                                else:
                                    self._log("Cover unavailable; presence was sent without artwork.")
                                self._publish(BridgeSnapshot(BridgePhase.ACTIVE, "Showing current PS3 game in Discord.", client.online_id, game, True, token_expiry, cover_url))
                            else:
                                last_cover_url = None
                                rpc.clear()
                                self._log("Discord cleared: no active PS3 game was returned by PSN.")
                                self._publish(BridgeSnapshot(BridgePhase.IDLE, "PS3 is online, but no active game was returned.", client.online_id, None, True, token_expiry))
                            synced = True
                            break
                        except Exception as error:
                            close_rpc_safely(rpc)
                            rpc = None
                            self._publish(BridgeSnapshot(BridgePhase.WAITING_FOR_DISCORD, "Discord is unavailable; reconnecting.", client.online_id, game))
                            self._log(f"Discord RPC unavailable ({type(error).__name__}); reconnecting.")
                            if attempt == 0:
                                self._wait(2)

                    if synced:
                        last_rpc_identity = rpc_identity
                        last_game_identity = game_identity
                        last_rpc_sync = time.monotonic()
                elif game:
                    self._publish(BridgeSnapshot(BridgePhase.ACTIVE, "Showing current PS3 game in Discord.", client.online_id, game, rpc is not None, token_expiry, last_cover_url))
                else:
                    self._publish(BridgeSnapshot(BridgePhase.IDLE, "PS3 is online, but no active game was returned.", client.online_id, None, rpc is not None, token_expiry))

                self._wait(self.settings.poll_interval)
        finally:
            covers.close()
            if rpc is not None:
                try:
                    rpc.clear()
                except Exception:
                    pass
            close_rpc_safely(rpc)
            self._publish(BridgeSnapshot(BridgePhase.STOPPED, "Bridge stopped."))
