# PS3 to Discord Rich Presence (OFW experiment)

This project tests whether Sony's legacy PSN profile endpoint still exposes an
online PS3 and its current game for an account using official firmware. It uses
`PSNAWP.me().get_profile_legacy()` and can forward a detected game to Discord
Rich Presence.

Game artwork uses the title icon returned by legacy presence when available.
Otherwise, the bridge generates the official PlayStation CDN `ICON0.PNG` URL
from the PS3 Title ID using PSNAWP. `DISCORD_LARGE_IMAGE` remains an optional
fallback asset key.

## Security

- Put `NPSSO` only in `.env` on this computer.
- `.env` is ignored by Git.
- The probe prints only the PSN Online ID and presence fields. It never prints
  NPSSO or the full legacy profile response.
- PSNAWP is an unofficial, reverse-engineered PSN API wrapper. Its maintainers
  warn that excessive requests can lead to PSN account restrictions. The watch
  interval is therefore limited to at least 15 seconds and defaults to 30.

## Setup

The local virtual environment is created in `.venv`. Fill in this line in
`.env` without quotes:

```dotenv
NPSSO=your_local_value
```

Test PSN once, with the PS3 signed into PSN and a game running:

```powershell
.\.venv\Scripts\python.exe .\main.py --once
```

The useful result is:

```text
Platform: PS3
Game: <game name>
Result: PASS ...
```

## Discord mode

Create a Discord application at <https://discord.com/developers/applications>.
Name it `PlayStation 3`, copy its Application ID, and add it locally to `.env`:

```dotenv
DISCORD_CLIENT_ID=123456789012345678
```

Keep the Discord desktop client open, then run:

```powershell
.\.venv\Scripts\python.exe .\main.py
```

`DISCORD_LARGE_IMAGE` is optional. If used, it must be the asset key uploaded
under the Discord application's Rich Presence assets.

## Windows autostart

During development, keep the bridge running from the source tree so code
changes do not require rebuilding an executable. Install and immediately start
the per-user scheduled task with:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\install_autostart.ps1
```

It starts `run_hidden.pyw` at logon, keeps the console hidden, restarts the task
after failures, and writes rotating logs to `logs\bridge.log`. Discord Desktop
must be running in the same logged-in Windows user session.

## Tray application

Run the graphical version during development with:

```powershell
.\.venv\Scripts\python.exe .\gui.py
```

It displays the current PSN/Discord state and game, keeps the bridge running in
the system tray, and provides Discord reconnect, settings, and log controls.
Closing its window only hides it; choose **Exit** from the tray menu to stop it.
The Windows autostart launcher starts this tray application automatically.

The source interface uses a compact 390 × 526 layout inspired by ZenTimings,
with small controls, data rows, and a timestamped Event Log. **Декор** toggles
the artwork, bulb hit targets, particles, and Christmas audio together. It is
off on each launch; colour themes are still available independently. A small
branded startup screen appears on an interactive launch; tray launches stay hidden.

Settings are stored in `%LOCALAPPDATA%\PS3Presence`. A NPSSO entered through
the application is encrypted with Windows DPAPI and is only readable by the
same Windows user. The original `.env` token is retained as a manual fallback;
remove that `NPSSO=` line yourself after confirming the app reconnects.

The app shows an in-tray warning when PSNAWP reports less than roughly three
days until the current PSN refresh-token expiry. In **Settings**, choose
**Get NPSSO in browser** to open Sony's sign-in and `ssocookie` pages, then
copy the JSON response and use **Paste from clipboard**. The secret is never
written to the log or displayed after it is saved.

The bridge explicitly requests the optional PSN `gameStatus` field. Every game
seen on PS3 and every distinct non-empty status are recorded locally in
`observed_game_statuses.json`. This runtime file contains title/status data only,
is ignored by Git, and never stores NPSSO or PSN account/profile information.

Remove the task with:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\uninstall_autostart.ps1
```

## Musical Christmas garland

The Christmas theme is available December 10–January 20. Outside that period,
type `3112` in the main window (not a settings input) to reveal its theme button;
type it again to hide it. Hovering its existing bulbs plays local notes without
moving the artwork. Clicking still toggles their light; the lowest right
pinecone still toggles all lights and snowfall.

The 36 original, unmodified files live in `design/newyear/audio/sound1.mp3`
through `sound36.mp3`. `tools/prepare_audio_assets.py` decodes them at build
time to standard 16-bit PCM in `assets/newyear/pcm/`. The application loads
these WAV samples once and keeps them cached across theme changes. No MP3
decoder or FFmpeg/video codec libraries are needed at runtime. The existing zero-based bulb index
maps to `soundIndex = lampIndex % 36` (`soundIndex + 1` in the filename).
The current artwork exposes 16 bulbs; unavailable bulb slots do not respond.

Every new hover starts a separate voice from the beginning, allowing rapid
melodies and overlapping release tails. Leaving a bulb fades its voice
exponentially over one second, or until the original short recording ends.
Opening settings, hiding/minimizing the window, changing to another theme,
or exiting stops active voices. No external audio, CDN, or additional package
is used. The release includes only files listed in `packaging_policy.py`.

Run the interaction/audio regression tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_garland_audio
```

## Release 0.9.0

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Release
```

The portable build is in `releases/0.9.0/PS3Presence`. Keep its `_internal`
folder alongside `PS3Presence.exe`. The version is shown below Event Log;
temporary light-position controls are removed and calibrated defaults are
shipped without including private credentials or development logs.

The checked-in PyInstaller spec intentionally excludes host-tool ICU 78 and
pins both OpenSSL DLLs to Python's matching runtime pair. Do not regenerate it
with a plain `pyinstaller gui.py` command, which can collect incompatible DLLs.
An offline packaged-runtime check is available as `PS3Presence.exe --smoke-test`
(exit code 0 means QML, SSL, the version label, and all 36 sounds loaded).

The local `hooks/hook-PySide6.QtQml.py` collects only QML modules needed by the
interface: the Basic Controls style and its supporting imports. Unused SDK
modules such as WebEngine, alternative styles, PDF and media plugins are
excluded before plugin dependency analysis. Active artwork, all PCM notes
and software OpenGL remain included. Country databases and Russian Qt
translations remain available; unused country/Qt translation catalogs do not.
When adding new QML imports, review the allowlist and run the packaged check.

Raw PCM playback uses QAudioSink in the main Qt Multimedia library, without
the separate media backends, as described in the
[Qt Multimedia backend documentation](https://doc.qt.io/qt-6/qtmultimedia-index.html#target-platform-and-backend-notes).
`--smoke-test` renders all themes and both dialogs. The optional
`--smoke-test-audio` also checks three overlapping notes using the real output
device; it intentionally plays a short sound. Neither mode connects to
PSN/Discord, creates a scheduled task, or writes credentials/settings.

To produce a separate compact build without replacing an older release:

```powershell
.\build.ps1 -Release -OutputDirectory 'releases\0.9.0-compact'
.\releases\0.9.0-compact\PS3Presence\PS3Presence.exe --smoke-test
.\.venv\Scripts\python.exe .\tools\package_release.py .\releases\0.9.0-compact
```

The packager validates the runtime manifest, refuses private data and unused
media libraries, verifies every ZIP entry/CRC, and creates SHA256SUMS.txt.
Run the full offline regression suite with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

## Project layout

- `gui.py`: stable graphical launcher; old unreachable Widgets UI is removed.
- `qml_app.py`: controller, workers and tray lifecycle; no imports back into the launcher.
- `time_format.py`: calendar-aware expiry formatting, without GUI dependencies.
- `game_statistics.py`: observed playtime and transactional local SQLite storage.
- `game_statistics_model.py`: incremental Qt list model for game cards.
- `session_history.py`: observed session records and atomic checkpoint persistence.
- `garland_audio.py` / `audio_assets.py`: voices, fading and validated PCM data.
- `qml/`: the active interface and dialogs.
- `assets/`: active runtime artwork, icon and prepared PCM notes.
- `design/`: original artwork, unused design experiments and unmodified MP3 notes.
- `tests/`: automated offline regression checks.
- `tools/`, `hooks/`, `packaging/`, `PS3Presence.spec`: deterministic build and packaging.
- `archive/`: recoverable old experimental builds/configuration, never shipped.
- `releases/`: current and previous portable releases, kept separate.

After setting up a fresh development environment, prepare sounds before
launching `gui.py`: `python tools/prepare_audio_assets.py`.
Pillow is a build-only dependency for generating the icon, not an app dependency.
The packaged autostart checkbox uses the EXE with `--tray`; development
autostart continues using the original hidden Python launcher.

## Pending next release: light response and optional CPU rendering

The all-lights Easter egg now interrupts any previous fade immediately and
starts from a visible light level, with a 200 ms attack / 160 ms release.
The same transition is used by individual bulbs. Immutable halo textures
are reused instead of being redrawn on every click.

GPU rendering remains the default. On Windows, Qt Quick normally uses
[Direct3D 11](https://doc.qt.io/qt-6/qtquick-visualcanvas-scenegraph-renderer.html),
which can make capture/overlay software attach to this otherwise 2D window.
An optional, application-only software mode is available from source:

```powershell
.\.venv\Scripts\python.exe .\gui.py --software-rendering
```

It requests Qt's raster renderer rather than a 3D device. It does not modify
global NVIDIA/Windows settings. See [Qt's software renderer limitations](https://doc.qt.io/qt-6/qtquick-visualcanvas-adaptations-software.html).
Use `--software-rendering --smoke-test` to verify the selected renderer, themes
and dialogs without contacting PSN/Discord or writing settings.
These pending source changes do not replace an existing EXE or release ZIP.

## Pending next release: botanical artwork and idle gamepad

The Botanical theme alone uses `assets/botanical-cannabis-theme.png`: illustrated
serrated cannabis fan leaves and the original blue hanging pot filled with the
same plant. Other regular themes retain their original artwork. The new PNG
has genuine transparency and a theme-specific lowest-leaf click mask; the
all-lights Easter egg remains available. Image-generation prompts are recorded
in `design/botanical-cannabis-prompts.md`.

The idle gamepad is now an illustrated black DualShock 3 from
`assets/dualshock3.png`, centred on its body using a transparent-padding crop.
The PNG is decoded at 256 × 256 rather than full resolution. Its tile uses
explicit layout dimensions of 130 × 130; a loaded game cover continues to
replace the placeholder. The built-in generation prompt is recorded in
`design/dualshock3-prompt.md`.
These changes are source-only for testing; no EXE/ZIP is rebuilt.

The default/fallback theme is Aurora; an explicitly saved theme is retained.
The light theme is displayed as «Роса» (Dew), keeping its stable `light` ID.
The PS3 Presence heading has a white outline in Dew and a black outline in
every other theme, using the existing glyph layers without duplicate text.
Both internal e glyphs and s are above the raised leaf. The first e is removed
from the lower prefix, preserving its advance position without double drawing.
The additional low-left bulb in the cannabis artwork has its own Botanical-only
hit target and aligned halo, and participates in the all-lights Easter egg.
In Botanical, the lowest-right-leaf all-lights Easter egg also toggles falling
cannabis leaves. `qml/LeafFall.qml` reuses a transparent leaf crop from the
existing frame with drifting, spinning cached image particles. They do not
intercept clicks; movement pauses while hidden/minimized or in either dialog.
Other themes do not show this effect; Christmas snowfall remains unchanged.

## Release 0.9.1: game statistics and session timer

The temporary light direction pad is removed; previously saved bulb offsets
are retained. Clicking bulbs continues to switch their lights normally.

The main game card shows a live `HH:MM:SS` session timer using the same detected
session start as Discord. Changing an in-game status or reconnecting Discord
does not restart it. The Statistics button below the Event Log opens a themed,
centred dialog with game artwork, accumulated observed time, session counts
and the current-game indicator. Cards update without reloading covers each second.

Statistics are stored in `%LOCALAPPDATA%\PS3Presence\game_statistics.sqlite3`
using Python's standard-library SQLite: no extra heavyweight dependencies.
Time is checkpointed every 15 seconds and on a new session, idle, stop or normal
exit. A sudden crash may lose the uncheckpointed interval. An unreadable existing
database is preserved and reported in the dialog, never overwritten or deleted.
The database and its SQLite sidecars are excluded from portable packages.

Only time observed while this application runs (including in the tray) counts.
Closed-app intervals, sleep and unavailable/stale PSN data are excluded, and
older PSN playtime cannot be reconstructed. Detection precision depends on the
PSN polling interval (normally 30 seconds). Counting works even when Discord is
unavailable. A launch here means a detected session, not PSN's historical launch
count. Account statistics are separate. Do not run two tracking copies together:
both would count the same playtime. Covers use the available game URLs; failed
image loads show a PS3 fallback.

The total-time block now also shows `Статистика с 13 сентября 2026`. The collection
start is recorded at the first detected game and persists in an additive
`statistics_metadata` table, compatible with the 0.9.1 database and writer.
For existing databases without this field, Windows file birth time is used
(bounded by the earliest recorded activity); if birth time is unavailable,
the earliest recorded activity is used as a best-effort legacy date. The date
describes the overall collection period, not PSN's historical first play.
The collection-period date is included in release 0.9.2.

## Release 0.9.2: session history and settings fixes

Statistics now has Games and Sessions tabs. Each session card shows its game
cover, observed tracking start/end to the second, accumulated observed duration,
and current/paused/finished state. In-game status changes, a Discord reconnect
and a temporary PSN outage do not split a session. Switching games/accounts,
confirmed idle or stopping the app closes it. Sleep and unknown PSN intervals
remain excluded from both the aggregate and session duration; a wall-clock
start/end interval can therefore be longer than the counted time.

Session detail starts with this version: existing aggregate hours and
launch counts are retained, but old per-session dates cannot be reconstructed.
The additive `game_sessions` table shares the same SQLite transaction as game
totals, without changing the seven-column games schema or database version.
The UI/cache shows the latest 100 sessions per account; all records remain in
SQLite. A previous unclosed checkpoint is marked Interrupted at its last saved
observation, never backfilled through app downtime. Normal exit closes the
current record and saves it. After a crash, up to one checkpoint interval may
be lost. History and covers update without recreating cards on every clock tick.
Russian month names are spelled out in collection, game and session dates,
independent of the Windows language. Session date captions are «Первая сессия»
and «Последняя сессия»; this presentation change does not alter counted time.
Release files are in `releases/0.9.2/PS3Presence` with a compact ZIP alongside.
The original native Qt scrolling is restored without extra bounce animations.
Quit the installed EXE in the tray before testing `gui.py`, to avoid two
instances counting simultaneously. Previous release folders remain available.

Settings fields are editable drafts initialized whenever the dialog opens.
Status updates no longer overwrite an interval being typed (or other pending
edits). Saving persists the selected interval and restarts the bridge with it;
invalid values below 15 seconds and write errors keep the dialog open with an
explanation instead of silently reverting to the previous settings.

## Version 0.9.9 (source preview)

Compact dashboard with optional decoration, a crisp vector mascot and a graphic
decoration toggle. The title is left-aligned next to the centered mascot.
Decoration, light and click-target layers start at the toolbar divider.
The About toolbar button opens a themed dialog with a test Pac-Man GIF;
the animation is half-sized with its dark background keyed out when rendered,
and is unloaded while the dialog is closed. The original GIF is preserved.
Games and sessions have soft, theme-matched viewport edges while more content
is scrollable. At the end the lower fade disappears so the last card is visible.
Discord compact status uses the current game's title via `StatusDisplayType.DETAILS`,
while preserving the rich-presence cover, session timer and game-status details.
Russian is the default UI language. The RU | EN flag buttons switch the interface,
dates, expiry durations and tray menu immediately and persist the selection in
config.json without touching credentials or game statistics. The version is in
About, with the animation in its lower-left corner.
Application and Windows executable metadata are updated together; no new EXE
has been built for this source preview.

### Fallback artwork source: GameTDB

The bridge validates PSN artwork with a bounded public GET before using it.
If missing, it downloads GameTDB's PS3 catalog on demand and searches by PS3
serial (ignoring the `_00` suffix), then by an exact normalized game title.
A demo may use the full game's cover; its displayed title and statistics remain
unchanged. Subtitles, edition names and sequel numbers are never fuzzy-matched.
No account or API key is required. Catalog credit: https://www.gametdb.com/PS3/Downloads

The catalog and resolved public URLs are cached in `%LOCALAPPDATA%/PS3Presence/covers`.
Successful URL lookups expire after seven days. Confirmed missing artwork retries
after an hour; network/catalog failures retry after one minute, including across
restarts. Legacy unclassified negative cache entries are ignored, preserving
successful entries. An unavailable catalog can use its older local copy.
An unavailable square-image proxy falls back to the validated original image.
For GameTDB's public artwork/catalog only, a failed HTTPS request can fall back
to HTTP. The worker remembers a working HTTP route during that run; PSN login
and arbitrary URLs never use this fallback. ZIP/XML and image data remain size
limited and validated; downloaded metadata is never executed.
Image bytes are cached locally (up to 64 MiB, separate from the EXE). Dashboard,
games and past sessions use the local image; Discord retains the public URL.
Previously URL-only positive entries are revalidated before reuse. Game/session
records still store public URLs; local presentation does not rewrite playtime.
Existing games get their artwork refreshed when next observed; recorded times
and session counts are not modified. Downloads run on the existing worker,
with a 30-second lookup budget, request timeouts and size limits; failures leave
the normal artwork placeholder.
