# ShowGo - Agent Instructions

Flask-based photo/video slideshow application for digital signage. Python 3.11+, SQLite database, uses ffmpeg/ffprobe for video processing.

## Project Structure

```
showgo/               # Main application package
├── __init__.py       # App factory (create_app)
├── main_bp.py        # Blueprint: slideshow viewer (/)
├── config_bp.py      # Blueprint: config UI (/config/*)
├── cli.py            # CLI commands via blueprint
├── config.py         # Config classes + default settings
├── extensions.py     # Flask extension instances (db)
├── models.py         # SQLAlchemy models (Setting, MediaFile)
├── utils.py          # Helper functions (DB init, thumbnails, ffmpeg)
├── errors.py         # Error handlers (404, 500, 413)
├── static/           # CSS, JS, placeholder images
└── templates/        # Jinja2 templates

run.py                # Dev server entry point
requirements.txt      # Python dependencies
Dockerfile            # Production container (Gunicorn on :5000)
```

## Running the Application

**Development server:**
```bash
flask --app run run
```
The app will be at `http://0.0.0.0:5000` or `http://127.0.0.1:5000`.

**Database initialization (optional but recommended):**
```bash
flask db init
```
Creates `instance/showgo.db` and populates default settings. The app will auto-create the DB on first run if it doesn't exist.

**Docker:**
```bash
docker build -t showgo .
docker run -p 5000:5000 showgo
```
Uses Gunicorn with 4 workers, binds to `0.0.0.0:5000` inside the container.

## Required External Dependencies

**ffmpeg and ffprobe must be in PATH:**
- Used for video thumbnail generation and codec validation
- On Windows: download from ffmpeg.org, extract, add `bin/` to system PATH
- On Linux: `sudo apt install ffmpeg`
- On macOS: `brew install ffmpeg`

Without ffmpeg/ffprobe, video uploads will fail codec validation and thumbnails won't generate.

## Configuration & Environment

**Environment variables (`.env` file at project root):**
```bash
SECRET_KEY='your_strong_random_secret_key'
```

The app loads `.env` from the project root via `showgo/config.py`. If `.env` is missing, the app will print a warning and fall back to a default SECRET_KEY (insecure for production).

## Access Control

**No authentication or authorization** is implemented. The configuration UI at `/config/*` is **publicly accessible**. This application is designed for:
- Local installations on trusted devices
- Closed/private networks
- Devices with physical access control

**Do not expose this application to the public internet without implementing additional authentication mechanisms** (e.g., reverse proxy with auth, VPN, firewall rules).

## Key Architectural Details

**Application factory pattern:**
The app is created via `create_app()` in `showgo/__init__.py`. Direct imports of `app` won't work; use `current_app` from Flask within request context.

**Blueprints:**
- `main_bp`: slideshow viewer, media serving, API endpoints (`/`, `/uploads/<filename>`, `/api/media`, etc.)
- `config_bp`: config UI (`/config/*`)
- `db_cli_bp`: CLI commands under `flask db <command>`

**Database:**
SQLite at `instance/showgo.db`. Two models:
- `Setting`: key-value pairs for all app config (slideshow duration, overlay text, widget settings, etc.)
- `MediaFile`: uploaded images/videos with metadata (filename, type, order, dimensions, duration)

Settings are cached in `app.config['SHOWGO_CONFIG_DB']` on startup and reloaded via `load_settings_from_db()`.

**Image processing:**
If the `max_resolution` setting is set (e.g., `1080p`, `4K`), uploaded images may be resized. 

**Video codec validation:**
Uploaded videos are checked via ffprobe for web-friendly codecs:
- Video: H.264, VP9, AV1
- Audio: AAC, Opus, MP3, Vorbis

Non-compliant videos are rejected with a message to re-encode.

**Folders auto-created on startup:**
- `instance/` (SQLite DB)
- `uploads/` (original media)
- `thumbnails/` (generated thumbnails)
- `showgo/static/assets/` (overlay logo)

## Testing & Verification

No test suite currently exists. Manual verification:
1. Start the dev server: `flask --app run run`
2. Navigate to `http://127.0.0.1:5000/config` (no authentication required)
3. Upload test images and videos
4. View slideshow at `/`

Check console logs for errors related to ffmpeg, Pillow, or database operations.

## Gotchas

**Flask CLI command:** `flask --app run run` (not `flask run` or `python run.py` for CLI commands)

**Database self-healing:** If tables are missing, `initialize_database()` attempts to recreate them. If the DB is corrupted, delete `instance/showgo.db` and restart to rebuild from defaults.

**Video thumbnails fail silently if ffmpeg is missing.** Check console for "ffmpeg command not found" errors.

**Image processing requires Pillow.** If Pillow is unavailable, thumbnails for images won't generate and resizing/WebP conversion will be skipped. The app logs "PIL_AVAILABLE: False" on startup.

**Overlay logo:** Uploaded via config UI, saved as `showgo/static/assets/overlay_logo.png`. Only PNG format supported.

**Media order:** Set to "sequential" or "random" in config. Sequential order is determined by `MediaFile.display_order` (auto-assigned on upload based on filename sort).

## Production Deployment

**Use Gunicorn (included in Dockerfile):**
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```
Note: This assumes a module named `app.py` with an `app` instance. The current repo uses `run.py` and app factory. Adjust Dockerfile CMD or create an `app.py` wrapper if needed.

**Dockerfile CMD already points to `app:app`.** If `app.py` doesn't exist at container runtime, Gunicorn will fail. The Dockerfile currently assumes `app.py` exists, but the repo has `run.py` instead. To fix:
- Either rename `run.py` to `app.py`, or
- Change Dockerfile CMD to reference the correct module (e.g., `showgo:create_app()` with a wrapper).

**MAX_CONTENT_LENGTH:** Set to 512MB in `config.py` to allow large video uploads. Adjust if needed.

## Additional Notes

**License:** CC BY-NC 4.0 (see LICENSE.md). Non-commercial use only.

**No CI/CD, linting, or formatting config** currently in the repo.

**No pre-commit hooks** or automated code quality checks.

**Widgets:** Clock widget for displaying current time. Widget state is stored in settings table.

**Burn-in prevention:** Optional pixel shift for static overlay elements to prevent screen burn-in on long-running displays.
