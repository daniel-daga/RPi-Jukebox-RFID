# CLAUDE.md - RPi Jukebox RFID Development Guide

## Project Overview

**RPi Jukebox RFID Version 3** (future3/develop branch) is a Python-based RFID music player system for Raspberry Pi. It's a complete rewrite with a modular architecture supporting multiple hardware configurations.

- **Current Version:** 3.7.0-alpha
- **Primary Branch:** future3/develop
- **Tech Stack:** Python 3, MPD (Music Player Daemon), YAML config, pytest
- **Full Details:** See [REPO_OVERVIEW.md](REPO_OVERVIEW.md)

## Key Development Areas

### Backend Architecture
- **Modular Components:** Pluggable hardware/feature modules in `src/jukebox/components/`
- **Core Daemon:** `src/jukebox/jukebox/daemon.py` orchestrates plugins
- **Configuration:** YAML-based, templates in `resources/default-settings/`
- **Hardware Abstraction:** Multiple RFID readers, audio devices, GPIO control

### Testing Approach
- **Framework:** pytest with coverage tracking
- **Mock Support:** Comprehensive mocks for hardware (GPIO, readers) to test without physical devices
- **CI/CD:** GitHub Actions workflows for testing (python, docker, webapp)
- **Pre-commit Hooks:** Located in `.githooks/`

### Critical Considerations

1. **Hardware Abstraction Matters**
   - GPIO control uses custom gpioz wrapper with full mock support
   - RFID readers have multiple implementations (RC522, PN532, RDM6300, USB, NFC)
   - Changes to hardware layers should maintain mock compatibility

2. **Configuration is User-Facing**
   - Config files in `resources/default-settings/` are templates
   - Changes to configuration schema may affect existing installations
   - Document config changes in migration guides

3. **Component Integration**
   - Components communicate via RPC, MQTT, and ZMQ
   - Lifecycle management is critical (startup/shutdown order)
   - Callback systems are used for playback/RFID events

4. **Testing Without Hardware**
   - Use mock GPIO, RFID readers, and MPD interfaces
   - Tests should run on any platform (Linux/Mac/Windows)
   - Avoid platform-specific shell commands in Python code

## File Organization Reference

```
src/jukebox/
├── components/              # Hardware/feature modules (stateless)
│   ├── player*/             # Audio playback implementations
│   ├── rfid/                # RFID system (readers + card DB)
│   ├── gpio/                # GPIO control + mocking
│   └── ...                  # Other features
├── jukebox/                 # Core system
│   ├── daemon.py            # Main service entry point
│   ├── cfghandler.py        # Config loading/validation
│   ├── plugs.py             # Component plugin system
│   └── rpc/                 # Communication protocol
└── misc/                    # Utilities (logging, colors, etc.)
```

## Common Tasks

### Adding a Feature or Component
1. Create module in `src/jukebox/components/`
2. Follow plugin interface pattern
3. Add YAML config template to `resources/default-settings/`
4. Write tests using mocks (no hardware required)
5. Update documentation in `documentation/developers/`

### Fixing a Bug
1. Identify affected component
2. Write a test that reproduces the issue
3. Fix the code
4. Verify test passes and related tests still pass
5. Check if configuration or documentation needs updating

### Modifying Configuration
1. Update YAML template in `resources/default-settings/`
2. Update `cfghandler.py` if schema changes
3. Add migration notes to documentation if breaking

## Before Making Changes

- **Read REPO_OVERVIEW.md** for architecture and component relationships
- **Check tests** in `test/` to understand existing patterns
- **Verify mocking approach** for any hardware-dependent code
- **Consider backwards compatibility** for configuration and APIs
- **Review related GitHub issues/PRs** (if context is available)

## Development Environment

- **Host OS:** Windows 11 — use PowerShell syntax, avoid Linux-only shell idioms; Python is `py` not `python`
- **Target Device:** Raspberry Pi at `pi@phoniebox`, password `raspberry`
- **SSH Access:** Use `paramiko` (Python SSH library) to connect and run commands on the Pi
  - Always call `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` before printing SSH output (Unicode bullet chars in systemctl output crash cp1252)
  - **Use IP `192.168.50.8` not hostname** — `phoniebox` hostname doesn't always resolve in paramiko; `phoniebox.local` works for ping but may fail in scripts
  - **Use `py -c "..."` inline for short commands** — running script files (`.py`) via PowerShell causes the tool to background the command. Inline `py -c "single-line"` runs in foreground. For multi-step tasks that need output, keep the entire script on one line.
  - Avoid parentheses in `echo` strings joined with `;` — they trigger bash subshell syntax errors
  - **MPD polling interval is 250ms** — MPD publishes playerstatus every 250ms; the Spotify plugin polls the Spotify Web API every 2s and publishes 'playerstatus' only while it is the active backend. The **player arbiter** (`src/jukebox/components/player/__init__.py`) ensures exactly one backend publishes status at a time — MPD is silenced while Spotify is active, and transport commands (`play`/`pause`/`next`/`prev`/`seek`) are routed to the active backend
- **Pi Services:** All jukebox services run as **user services** under `pi`; use `systemctl --user` not `sudo systemctl`
  - `jukebox-daemon.service` — main jukebox daemon (RPC on ZMQ tcp:5555, publisher on 5557/5558)
  - `librespot.service` — Spotify Connect **playback device** on the Pi (device name `Phoniebox`; plays through PulseAudio). Auto-logged-in with the jukebox's own OAuth token after "Connect with Spotify", so it never needs activating from a phone/desktop app — see `src/jukebox/components/playerspotify/setup_librespot.inc.sh`. The Spotify plugin itself drives playback via the **Spotify Web API** (spotipy + OAuth), not a local HTTP API
  - `mpd.service` — Music Player Daemon
  - `pulseaudio.service` — PulseAudio sound server (both MPD and librespot route through it)
  - `journalctl --user -u <service>` for user service logs (system journal may show nothing)
- **Webapp Deployment:** Build the webapp locally (`src/webapp/`), then copy the `build/` folder to the Pi over SSH/SCP — do NOT build on the Pi

## Development Workflow

1. Work on `future3/develop` branch
2. Run tests: `pytest` (or check CI configuration for full test suite)
3. Keep commits focused and well-described
4. Follow existing code patterns (see similar components)
5. Update docs if user-facing behavior changes

## Important Branches & Files

- **Main Config:** `resources/default-settings/jukebox.default.yaml`
- **Card Mappings:** `resources/default-settings/cards.example.yaml`
- **GPIO Setup:** `resources/default-settings/gpio.example.yaml`
- **Version File:** `src/jukebox/jukebox/version.py`
- **Documentation:** `documentation/builders/` (users) + `documentation/developers/` (dev)

## Questions or Issues?

When stuck:
1. Check the component's `__init__.py` for plugin interface
2. Look at similar components for patterns
3. Review existing tests for usage examples
4. Check documentation in `documentation/developers/`
