# PS3 Presence

[Русский](README.md) · English

PS3 Presence is a Windows application that displays your current PlayStation 3 game in Discord Rich Presence and keeps local playtime statistics.

It reads your status from PSN: no console installation or CFW/HEN is required. It works with official firmware when Sony returns the running game's information.

Current release: [**0.7.1 beta**](https://github.com/frrstgvmp/PS3Presence/releases/tag/v0.7.1-beta). This is not an official Sony or Discord product.

[Download for Windows x64 · ZIP](https://github.com/frrstgvmp/PS3Presence/releases/download/v0.7.1-beta/PS3Presence-0.7.1-beta-win64-portable.zip) · [SHA-256](https://github.com/frrstgvmp/PS3Presence/releases/download/v0.7.1-beta/SHA256SUMS.txt)

## Features

- Game title, artwork, current session timer and available in-game status in Discord.
- A dashboard with the current game, PSN avatar and connection state.
- Per-game statistics: accumulated playtime, detected session count and last played date.
- Session history with dates, duration and state; game sorting by playtime or last played.
- System tray operation, Discord reconnect and Windows autostart.
- Russian and English UI.
- Timestamped Event Log and a local artwork cache.

## Requirements

- Windows x64.
- A PS3 connected to PSN and access to the account used to play.
- The installed, running Discord desktop client. The browser client alone is not sufficient.
- Internet access to Sony's services; artwork also requires access to image servers.

Presence depends on Sony's data and updates at the polling interval. Some games, demos or network states may not provide a title or artwork.

## Quick start

### Portable application

1. Open the [0.7.1 beta release](https://github.com/frrstgvmp/PS3Presence/releases/tag/v0.7.1-beta).
2. Download `PS3Presence-0.7.1-beta-win64-portable.zip` under **Assets**. No installation or Python is required.
3. Extract the entire archive to a permanent folder and run `PS3Presence\PS3Presence.exe`.
4. Keep the `_internal` folder beside the EXE: the application needs it to run.
5. Open **Settings** and complete the configuration below.

Fully quit any older copy before updating. Settings, authentication and statistics remain in `%LOCALAPPDATA%\PS3Presence`; you do not need to move them into the new folder. Autostart does not automatically switch to a new application folder.

### Discord

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and create an application.
2. Copy its **Application ID** into **Discord Application ID** in PS3 Presence settings.
3. Keep the Discord desktop client running under your account.

Use the Application ID, not a bot token, Client Secret or Discord password. The application name may appear in some Discord views; the current game's title is sent separately.

**Large image asset key** is optional: it is a fallback image key previously added to your Discord application's Rich Presence assets. Leave it blank to use automatic artwork.

### PSN / NPSSO

NPSSO is a secret PSN authentication code. Never publish it, Sony's full JSON response or screenshots containing either.

1. In **Settings**, select **Update NPSSO**.
2. Select **Open Sony sign-in** and sign into the correct PSN account in your regular browser.
3. In the same browser, open the [ssocookie page](https://ca.account.sony.com/api/v1/ssocookie). An authenticated session should return JSON containing `npsso`.
4. Copy the entire JSON response and select **Paste from clipboard** in the application.
5. Select **Done**, then **Save** in the main settings dialog.
6. Start a game on your PS3 and wait for the next poll.

**Done** confirms the pasted value; the token is only saved and applied after **Save**. **Cancel** or Escape in the update dialog discards the new paste and restores the previous value.

Clipboard validation is currently minimal: the application accepts a JSON `npsso` field or non-empty plain text. Token validity is determined when connecting to PSN, not when selecting **Done**.

The default polling interval is **30 seconds**, with a **15-second** minimum. When authentication expires, obtain a new NPSSO using the same procedure.

## How statistics work

Statistics are collected locally while PS3 Presence runs, including in the tray. The application does not import historical PSN hours or recover time played while it was closed.

- Only observed time with a confirmed active PS3 game counts.
- Computer sleep and periods of unavailable or stale PSN data do not add playtime.
- Discord being unavailable does not, by itself, prevent tracking.
- Switching games, confirmed idle or quitting the application ends a session.
- A brief PSN outage or Discord reconnect does not automatically create a new session.
- **Sessions** counts sessions detected by this application, not Sony's historical launch count.
- The **Sessions** tab displays the latest 100 records for the account; older records remain in the database.
- Selecting the current sort option again reverses ascending/descending order.

Start/end dates are observation boundaries, not guaranteed console launch/exit times. Counted duration may be shorter than the interval between them. Last played uses the start of a recorded session; legacy records without history use the available last observation date.

Data is checkpointed approximately every 15 seconds and at important transitions. A crash may lose the most recent unsaved seconds. Do not run the EXE and Python version simultaneously: two copies may count the same game twice.

## Artwork

The application first checks PSN/PlayStation CDN images. If suitable artwork is unavailable, it searches [GameTDB](https://www.gametdb.com/PS3/Downloads) by game identifier or an exact normalized title. A demo may use the full game's artwork.

Images are cached locally for the UI; Discord receives a public URL. If sources are unreachable or no suitable artwork exists, a gamepad placeholder is shown. Missing artwork does not stop presence updates or statistics.

## Data and security

Settings, authentication, statistics and cache are stored in `%LOCALAPPDATA%\PS3Presence`:

- `config.json` — interface and connection settings.
- `auth.dat` — authentication protected by Windows DPAPI for the current user.
- `game_statistics.sqlite3` — playtime and session history.
- `covers` — catalog and artwork cache.

The `observed_game_statuses.json` file beside the application contains detected game titles and in-game statuses. The hidden Python launcher writes logs to `logs`. These files, `.env`, virtual environments and builds are excluded from Git.

To back up statistics, fully exit the application first, then copy the database. Copying protected authentication to another Windows user does not guarantee it will work.

The application does not ask for your PSN password: sign-in happens on Sony's website. Requests use the unofficial [PSNAWP](https://github.com/isFakeAccount/psnawp) library, whose author warns about account restrictions from excessive API use. This project cannot guarantee PSN availability or freedom from Sony-imposed restrictions.

## Running from source

Tested with **Python 3.12 x64**. Install Python and Git, then run in PowerShell:

```powershell
git clone https://github.com/frrstgvmp/PS3Presence.git
cd PS3Presence
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\gui.py
```

Optional manual configuration: copy `.env.example` to `.env` and fill in values locally only. Settings saved in the application take precedence. Never include `.env` in a commit or release.

Other modes:

```powershell
# Start directly in the tray
.\.venv\Scripts\python.exe .\gui.py --tray

# Software rendering without creating a 3D graphics device
.\.venv\Scripts\python.exe .\gui.py --software-rendering

# One PSN query without connecting to Discord; requires a valid NPSSO
.\.venv\Scripts\python.exe .\main.py --once
```

## Development and packaging

Install build dependencies and run the offline tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

Build for Windows x64:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Release
.\releases\0.7.1-beta\PS3Presence\PS3Presence.exe --smoke-test
```

Before packaging, create `releases/0.7.1-beta/README.txt` with user instructions and copy `LICENSE` to the same folder, then run:

```powershell
.\.venv\Scripts\python.exe .\tools\package_release.py .\releases\0.7.1-beta
```

The packager checks the file manifest, absence of known private data and ZIP integrity, then creates the archive and `SHA256SUMS.txt`. Attach them to a GitHub Release rather than committing them to source control. An existing version archive is not overwritten.

Main components: `qml/` — UI; `qml_app.py` — controller and tray; `bridge.py` — PSN/Discord; `game_statistics.py` and `session_history.py` — time tracking; `cover_art.py` — artwork; `assets/` — resources; `tests/` — checks; `tools/`, `hooks/` and `packaging/` — builds.

## Troubleshooting

**Why is Discord slow to show a game?**

The application polls PSN rather than the console directly. Wait for the next poll; Sony may update presence with an additional delay.

**PS3 is online, but the application says “No game running.”**

PSN did not return an active PS3 game. Check the console account and wait for an update. Not every game or state provides complete data.

**Are PS4, PS5 and PS Vita supported?**

The current bridge selects active PS3 games only. Other platforms are not implemented.

**Discord does not connect.**

Start desktop Discord in the same Windows session, check the Application ID and use **Reconnect Discord**. This application does not install or repair Discord itself.

**The log shows ProxyError, ConnectionError or a timeout.**

General internet access does not guarantee access to Sony or artwork servers. Check VPN/proxy settings, `HTTP_PROXY` / `HTTPS_PROXY` environment variables, DNS and service reachability. Compatibility with every proxy is not guaranteed.

**Antivirus warns about a build.**

Check the archive's origin and SHA-256; if uncertain, run reviewed source code. Do not disable protection system-wide to launch the application.

## Feedback and license

Report bugs and suggestions through [GitHub Issues](https://github.com/frrstgvmp/PS3Presence/issues). Include the version, reproduction steps and a log excerpt with personal data removed.

Author on Discord: [lapamivverh](https://discord.com/users/308300626062737411).

Project code is published under [MIT](LICENSE). Third-party libraries, logos, game images and audio may have separate usage terms; this project's license does not override them.

The interface is inspired by [ZenTimings](https://github.com/irusanov/ZenTimings). Thanks to the authors of [PSNAWP](https://github.com/isFakeAccount/psnawp), [pypresence](https://github.com/qwertyquerty/pypresence), [Qt/PySide6](https://doc.qt.io/qtforpython-6/) and the [GameTDB](https://www.gametdb.com/PS3/Downloads) catalog.
