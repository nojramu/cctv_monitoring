# CCTV Monitoring Documentation

This folder contains a motion-detection CCTV script for Raspberry Pi that:

1. Captures live frames from a Pi camera.
2. Detects motion by comparing consecutive frames.
3. Saves a snapshot when motion is detected.
4. Sends the snapshot to Telegram.
5. Keeps snapshot storage under a fixed limit.

## Project Files

- `cctv_snapshot.py`: Main application loop (camera capture, motion detection, snapshot saving, Telegram alert trigger).
- `telegram_notify.py`: Telegram API helper functions (send message, send photo, load `.env` settings).
- `rpicam_commands`: Quick reference notes for Raspberry Pi camera CLI utilities.
- `.env` (expected, not committed): Local environment values used by Telegram integration.

## How the Main Script Works (`cctv_snapshot.py`)

### 1. Configuration constants

At the top of the file, constants define behavior:

- `SNAPSHOT_DIR`: Folder where images are saved.
- `MAX_SNAPSHOTS`: Maximum number of snapshots kept.
- `PIXEL_DIFF_THRESHOLD`: Per-pixel brightness difference required to count as "changed".
- `MIN_CHANGED_PIXELS`: Number of changed pixels required to classify a frame pair as motion.
- `COOLDOWN_SECONDS`: Minimum wait between saved snapshots.
- `FRAME_SIZE`, `TARGET_FPS`: Camera capture settings.
- `WARMUP_RETRIES`, `WARMUP_DELAY_SECONDS`: Startup retries for first valid frame.

These values are the main tuning knobs for sensitivity and performance.

### 2. Camera initialization

- `open_picamera2()` creates a `Picamera2` object, configures preview stream format (`RGB888`), applies target frame rate, starts camera, and waits briefly.
- `open_camera_source()` calls initialization and then ensures an initial frame can be captured (`get_initial_frame`).

If no startup frame is obtained, the script raises an error and exits safely.

### 3. Frame acquisition and preprocessing

- `read_frame(picam)` gets one frame from camera.
- `frame_to_gray(frame)` downsamples by taking every second pixel in both dimensions (`frame[::2, ::2]`) to reduce processing cost.
- It then converts RGB to grayscale (luma) using:

	`gray = 0.299*R + 0.587*G + 0.114*B`

This grayscale representation is used for motion comparison.

### 4. Motion detection logic

- `motion_detected(frame_a, frame_b)` converts both frames to grayscale.
- Computes absolute per-pixel difference.
- Counts pixels where difference is at least `PIXEL_DIFF_THRESHOLD`.
- Returns `True` if count is at least `MIN_CHANGED_PIXELS`.

In short:

- A pixel is "changed" if brightness change is large enough.
- Motion is detected if enough pixels changed.

### 5. Snapshot save and retention

- `save_snapshot(picam, folder_name)` creates a timestamped filename like `snapshot_YYYYMMDD_HHMMSS.jpg`.
- Captures image directly from camera to file.
- Calls `prune_old_snapshots()`.

`prune_old_snapshots(folder_name, max_snapshots)`:

- Scans `.jpg`, `.jpeg`, `.png` files.
- Sorts by modification time (oldest first).
- Deletes oldest files if count exceeds `MAX_SNAPSHOTS`.

This prevents storage growth over time.

### 6. Main loop behavior

`main()` performs:

1. Ensure snapshot folder exists.
2. Initial pruning pass.
3. Open camera and read initial frame.
4. Start loop:
	 - Read current frame.
	 - Compare previous frame (`frame_a`) with current (`frame_b`).
	 - If motion is detected and cooldown has elapsed:
		 - Save snapshot.
		 - Send Telegram motion alert with snapshot.
		 - Update last saved timestamp.
	 - Move `frame_b` into `frame_a` for next iteration.

The loop exits on `Ctrl+C` (handled by `KeyboardInterrupt`) and always stops the camera in `finally` via `release_sources()`.

## Telegram Integration (`telegram_notify.py`)

### 1. Environment loading

- `ENV_FILE` points to a local `.env` file in this folder.
- `_load_env_file(file_path)` loads simple `KEY=VALUE` lines into `os.environ` if keys are not already set.

Required keys:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### 2. Sending text messages

- `send_telegram_message(message)` calls Telegram Bot API `sendMessage` endpoint.
- Uses `parse_mode="Markdown"`.

### 3. Sending images

- `send_telegram_photo(image_path, caption=None)` validates file exists.
- Calls Telegram Bot API `sendPhoto` endpoint with multipart upload.
- Optionally sends caption in Markdown.

### 4. Motion alert wrapper

- `send_motion_alert(image_path)` builds caption with current time and sends photo.
- This is what `cctv_snapshot.py` calls after saving motion snapshots.

## End-to-End Runtime Flow

1. Camera captures frames continuously.
2. Script compares previous and current frame.
3. If threshold conditions indicate motion:
	 - Save image.
	 - Enforce max snapshot count.
	 - Send image to Telegram chat.
4. Continue monitoring.

## Setup Requirements

## Hardware

- Raspberry Pi (tested context suggests Pi 5).
- Compatible Pi camera module.
- Mounted storage path used by `SNAPSHOT_DIR` (currently `/media/noj/EC8E-7D64/snapshots`).

## Python packages

Install dependencies in your active environment:

```bash
pip install numpy requests picamera2
```

## Telegram `.env` example

Create `.env` in this folder:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCDEF_your_bot_token
TELEGRAM_CHAT_ID=123456789
```

## Run

From this folder:

```bash
python cctv_snapshot.py
```

Stop with `Ctrl+C`.

## Tuning Guide

- Too many false alerts:
	- Increase `PIXEL_DIFF_THRESHOLD`.
	- Increase `MIN_CHANGED_PIXELS`.
	- Increase `COOLDOWN_SECONDS`.
- Missing real motion:
	- Decrease `PIXEL_DIFF_THRESHOLD`.
	- Decrease `MIN_CHANGED_PIXELS`.
- High CPU usage:
	- Lower `FRAME_SIZE`.
	- Lower `TARGET_FPS`.

## `rpicam_commands` Notes

The `rpicam_commands` file is a quick command cheat sheet for checking camera availability and testing capture outside Python, such as:

- `rpicam-hello --list-cameras`
- `rpicam-hello -t 0`
- `rpicam-still`, `rpicam-vid`, `rpicam-jpeg`, `rpicam-raw`

Use these commands to validate camera hardware/driver status if Python capture fails.
