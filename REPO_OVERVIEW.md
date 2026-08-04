# RPi Jukebox RFID - Repository Overview

## Project Summary

**RPi Jukebox RFID Version 3** (aka "future3") is a complete rewrite of the RFID-based jukebox system for Raspberry Pi. It's a music player that uses RFID cards to trigger playlists and control audio playback.

**Current Version:** 3.7.0-alpha
**Repository:** <https://github.com/MiczFlor/RPi-Jukebox-RFID>
**Branch:** future3/develop

---

## Technology Stack

### Backend

- **Language:** Python 3
- **Music Player:** MPD (Music Player Daemon)
- **Communication:**
  - RPC (Remote Procedure Call) for client-server communication
  - MQTT for messaging
  - ZMQ (ZeroMQ) for pub/sub messaging
- **Testing:** pytest with coverage tracking
- **Configuration:** YAML-based configuration files

### Frontend

- **Type:** Web application (details in webapp directory)
- **Build System:** Custom bundling (see GitHub workflows)

### Hardware/Integration

- **RFID Readers:** Multiple hardware support
  - RC522 (SPI)
  - PN532 (I2C)
  - RDM6300 (Serial)
  - Generic USB readers
  - Generic NFC readers
- **GPIO Control:** Custom gpioz wrapper (with mock support for testing)
- **Audio Hardware:** HiFiBerry and other sound card support
- **Power Management:** Battery monitoring (ADS1015, INA219)
- **Connectivity:** Bluetooth audio buttons, event devices

---

## Project Structure

```text
src/jukebox/
├── components/          # Pluggable hardware/feature modules
│   ├── battery_monitor/     # Power management
│   ├── controls/            # Input devices (bluetooth buttons, event devices)
│   ├── gpio/                # GPIO control (gpioz wrapper + mock)
│   ├── jingle/              # Audio notification system
│   ├── mqtt/                # MQTT integration
│   ├── player/              # Audio playback abstraction
│   ├── playermpd/           # MPD-specific player implementation
│   ├── publishing/          # Pub/Sub messaging
│   ├── rfid/                # RFID card reader system
│   │   ├── hardware/        # Multiple reader implementations
│   │   ├── cards/           # Card database/management
│   │   └── configure/       # RFID setup tools
│   ├── synchronisation/     # RFID card sync
│   ├── timers/              # Idle shutdown, volume fadeout
│   └── volume/              # Volume control
├── jukebox/             # Core jukebox system
│   ├── daemon.py            # Main service daemon
│   ├── cfghandler.py        # Configuration management
│   ├── plugs.py             # Plugin/component loading
│   ├── playlistgenerator.py # Playlist generation
│   ├── publishing/          # Message publishing
│   └── rpc/                 # RPC server/client
├── misc/                # Utilities (logging, colors, input handling)
└── *.py                 # Entry point scripts (run_jukebox.py, etc.)

documentation/          # User and developer docs
├── builders/            # End-user setup guides
└── developers/          # Development environment setup

test/                   # Automated tests (pytest)
resources/              # Default configuration templates
docker/                 # Docker setup for development/deployment
```

---

## Key Components

### 1. **Core Daemon** (`src/jukebox/jukebox/daemon.py`)

- Main jukebox service that orchestrates all components
- Manages lifecycle of plugins and features
- Handles system events and callbacks

### 2. **RFID System** (`src/jukebox/components/rfid/`)

- Abstraction layer supporting multiple reader hardware
- Card database and configuration
- Maps physical cards to playlists/actions
- Includes a fake GUI reader for testing without hardware

### 3. **MPD Player Integration** (`src/jukebox/components/playermpd/`)

- Communicates with Music Player Daemon
- Cover art caching
- Playlist generation and queuing
- Callback system for playback events

### 4. **RPC Communication** (`src/jukebox/jukebox/rpc/`)

- Server for receiving commands
- Client for making requests
- Integration with CLI tools

### 5. **GPIO & Hardware Control** (`src/jukebox/components/gpio/`)

- Custom gpioz wrapper around GPIO libraries
- Full mock support for testing without hardware
- Input/output device management
- Connectivity plugins

### 6. **Configuration System** (`src/jukebox/jukebox/cfghandler.py`)

- YAML-based configuration
- Template defaults in `resources/default-settings/`
- Runtime configuration management

---

## Configuration Files

Key configuration templates (in `resources/default-settings/`):

- `jukebox.default.yaml` - Main jukebox settings
- `cards.example.yaml` - RFID card mapping
- `gpio.example.yaml` - GPIO pin configuration
- `evdev.example.yaml` - Event device mapping
- `logger.default.yaml` - Logging configuration
- `sync_rfidcards.default.yaml` - Card synchronization settings

---

## Development Setup

### Testing

- **Test Framework:** pytest
- **Coverage:** Tracked with .coveragerc
- **Pre-commit Hooks:** Located in `.githooks/`
- **CI/CD:** GitHub Actions workflows for:
  - Python package testing (pythonpackage_future3.yml)
  - Debian installation testing (test_docker_debian_v3.yml)
  - Webapp build testing (test_build_webapp_v3.yml)
  - CodeQL security analysis

### Docker Support

- Multiple Dockerfiles for different services
- `docker-compose.yml` for local development
- Platform-specific compose files (Linux, Mac)
- Custom MPD and webapp containers

---

## Documentation

- **User Guides:** `documentation/builders/` - Installation, configuration, troubleshooting
- **Developer Docs:** `documentation/developers/` - Development environment, architecture
- **API Reference:** RPC commands documentation
- **Component Guides:** Hardware, audio setup, GPIO configuration

---

## Build & Release

- **Release Process:** GitHub Actions workflow (bundle_webapp_and_release_v3.yml)
- **Versioning:** Semantic versioning (currently 3.7.0-alpha)
- **Version File:** `src/jukebox/jukebox/version.py`

---

## Notable Features

✅ **Modular Architecture** - Plugin-based component system
✅ **Hardware Abstraction** - Support for multiple RFID readers and audio devices
✅ **Mock/Testing** - Comprehensive mock implementations for testing without hardware
✅ **Web Interface** - Modern web app for control and configuration
✅ **Automation** - Timer-based automation (idle shutdown, volume fadeout)
✅ **Smart Home Integration** - MQTT support for home automation
✅ **Extensive Docs** - Detailed guides for builders and developers

---

## Recent Activity

- Version 3.7.0-alpha (current)
- Release: 3.6.0
- Active development on future3/develop branch
- Regular maintenance and documentation updates

---

## Community & Support

- **Issue Templates:** Bug reports, feature requests, future3-specific
- **Code of Conduct:** CONTRIBUTING.md
- **Matrix Chat:** Community discussion channel
- **CI/CD:** Automated testing and deployment pipelines
