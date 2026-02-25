# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Postock is a Windows desktop application for real-time Korean (KR) and US stock price monitoring with a system tray interface. It consists of three components:

- **`client_cs/`** — C# WPF desktop client (primary)
- **`client_py/`** — Python PyQt alternative client
- **`server/`** — Python FastAPI backend (stock data + licensing)

## Commands

### C# Client (`client_cs/KRStockTray.Client/`)
```bash
dotnet build
dotnet run
dotnet publish -c Release -r win-x64 --self-contained  # single EXE
```

### Python Server (`server/`)
```bash
# Run dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Run tests
pytest                    # all tests
pytest app/tests/test_foo.py  # single file

# Docker
docker build -t stock-api .
docker run -p 8080:8080 stock-api
```

### Python Client (`client_py/`)
```bash
python main.py
pyinstaller Postock.spec  # build EXE
```

## Architecture

### C# Client Design Principles

**`SettingsService`** is the single source of truth — never copy `Config.WatchList`. The `ObservableCollection<WatchItem>` is used directly by the UI via WPF data binding. Call `NotifyChanged()` to reflect changes in UI vs `Save()` to persist to disk (`%APPDATA%\KRStockTray\config.json`).

Key service flow:
1. `App.xaml.cs` initializes `SettingsService`, creates tray icon, loads KR symbol cache
2. `QuotePoller` runs a background loop polling `/quote/{market}/{code}` every 10s (market hours) or 30s (off-hours)
3. `OnConfigChanged` event propagates from `SettingsService` → `QuotePoller` + UI

### Server Architecture

Provider pattern: `ProviderFactory.get_provider(market)` returns `KRProvider` (NAVER Finance scraping) or `USProvider` (Yahoo Finance). Both return the same response shape: `{market, code, name, price, ref_price, delta, pct, price_type}`.

Serial/licensing flow: device hash → trial auto-issued on first `/activate/trial` call → serial validated on every `/quote` request → plan determines rate limits.

Rate limits by plan (requests/min): trial=20, free=30, pro=300, enterprise=3000.

SQLite (`server/data/app.db`) stores serials table only. Quotes are cached 3 seconds in-memory.

### Server Environment Variables
- `ENV` — `dev` or `prod` (default: `dev`)
- `DB_PATH` — SQLite path (default: `data/app.db`)
- `ADMIN_TOKEN` — Admin API bearer token (default: `4165`)

## Key API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/quote/{market}/{code}` | Single stock quote |
| `GET` | `/tray/{market}/{codes}` | Batch quotes (comma-separated) |
| `POST` | `/activate/trial` | Device-based trial serial |
| `GET` | `/symbols/kr` | KR symbol list (for autocomplete) |
| `POST` | `/admin/serials/issue` | Issue serial (requires `Authorization: Bearer {token}`) |
| `POST` | `/admin/serials/revoke` | Revoke serial |

Quote request headers: `X-Serial`, `X-Device`.

## Documentation Files

- `client_cs/KRStockTray.Client/Design.txt` — C# client design principles and anti-patterns
- `client_cs/KRStockTray.Client/KRStockTray_FILE_READING_GUIDE.txt` — Recommended file reading order
- `server/파일의존관계.txt` — Server module dependency diagram (Korean)
