import os
import time
from datetime import datetime
import numpy as np
from picamera2 import Picamera2
from telegram_notify import send_motion_alert


# Output directory for captured motion snapshots.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_DIR = "/media/noj/EC8E-7D64/snapshots"

# Maximum number of snapshots to keep in the folder.
# Oldest images are deleted when this limit is exceeded.
MAX_SNAPSHOTS = 1000

# Pixel difference threshold (0-255) for motion detection.
# Lower = more sensitive, Higher = less sensitive.
# Increase if detecting too much noise, decrease if missing motion.
PIXEL_DIFF_THRESHOLD = 15

# Minimum number of changed pixels to trigger motion capture.
# Lower = more sensitive, Higher = requires more movement.
# Typical range: 1000-15000 depending on frame size and scene.
MIN_CHANGED_PIXELS = 3000

# Minimum seconds between consecutive snapshot saves.
# Prevents flooding the folder with rapid captures during continuous motion.
COOLDOWN_SECONDS = 3

# Camera frame resolution (width, height).
# Options: (640, 480), (1280, 720), (1920, 1080), (2304, 1296), (3840, 2160), (4608, 2592)
# Higher = better quality but slower processing and more memory.
FRAME_SIZE = (1920, 1080)

# Target frames per second for camera capture.
TARGET_FPS = 20

# Number of retry attempts to get the initial frame on camera startup.
WARMUP_RETRIES = 20

# Delay in seconds between warmup retry attempts.
WARMUP_DELAY_SECONDS = 0.1


def open_picamera2():
	"""Open Raspberry Pi camera via Picamera2 and return camera object."""
	cam = Picamera2()
	config = cam.create_preview_configuration(
		main={"size": FRAME_SIZE, "format": "RGB888"},
		controls={"FrameRate": TARGET_FPS},
	)
	cam.configure(config)
	cam.start()
	time.sleep(0.5)
	return cam


def ensure_snapshot_dir(path):
	if not os.path.exists(path):
		os.makedirs(path)
		print(f"Created folder: {path}")


def prune_old_snapshots(folder_name, max_snapshots):
	image_files = []
	for name in os.listdir(folder_name):
		file_path = os.path.join(folder_name, name)
		if not os.path.isfile(file_path):
			continue
		lower_name = name.lower()
		if lower_name.endswith(".jpg") or lower_name.endswith(".jpeg") or lower_name.endswith(".png"):
			image_files.append(file_path)

	if len(image_files) <= max_snapshots:
		return 0

	image_files.sort(key=os.path.getmtime)
	files_to_remove = len(image_files) - max_snapshots
	removed_count = 0
	for file_path in image_files[:files_to_remove]:
		try:
			os.remove(file_path)
			removed_count += 1
		except OSError as e:
			print(f"Warning: could not remove {file_path}: {e}")

	if removed_count > 0:
		print(f"Pruned {removed_count} old snapshot(s).")

	return removed_count


def read_frame(picam):
	frame = picam.capture_array()
	return frame is not None, frame


def get_initial_frame(picam):
	for _ in range(WARMUP_RETRIES):
		ret, frame = read_frame(picam)
		if ret:
			return True, frame
		time.sleep(WARMUP_DELAY_SECONDS)
	return False, None


def open_camera_source():
	picam = open_picamera2()
	ret, frame = get_initial_frame(picam)
	if not ret:
		raise RuntimeError("Failed to read initial frame from Picamera2")
	return picam, frame


def frame_to_gray(frame):
	# Picamera2 RGB888 frame -> luma grayscale using standard RGB weights.
	frame_small = frame[::2, ::2]
	r = frame_small[:, :, 0].astype(np.float32)
	g = frame_small[:, :, 1].astype(np.float32)
	b = frame_small[:, :, 2].astype(np.float32)
	gray = 0.299 * r + 0.587 * g + 0.114 * b
	return gray.astype(np.uint8)


def motion_detected(frame_a, frame_b):
	gray_a = frame_to_gray(frame_a).astype(np.int16)
	gray_b = frame_to_gray(frame_b).astype(np.int16)

	diff = np.abs(gray_b - gray_a)
	changed_pixels = np.count_nonzero(diff >= PIXEL_DIFF_THRESHOLD)
	return changed_pixels >= MIN_CHANGED_PIXELS


def save_snapshot(picam, folder_name):
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	filename = os.path.join(folder_name, f"snapshot_{timestamp}.jpg")
	picam.capture_file(filename)
	prune_old_snapshots(folder_name, MAX_SNAPSHOTS)
	print(f"Motion detected. Image saved to: {filename}")
	return filename


def release_sources(picam):
	if picam is not None:
		picam.stop()


def main():
	ensure_snapshot_dir(SNAPSHOT_DIR)
	prune_old_snapshots(SNAPSHOT_DIR, MAX_SNAPSHOTS)

	picam = None
	try:
		picam, frame_a = open_camera_source()
		last_saved_time = 0.0

		print("Motion detection started (Press Ctrl+C to stop)...")
		while True:
			ret, frame_b = read_frame(picam)
			if not ret:
				print("Warning: failed to read frame, skipping...")
				continue

			if motion_detected(frame_a, frame_b):
				now = time.time()
				if now - last_saved_time >= COOLDOWN_SECONDS:
					snapshot_path = save_snapshot(picam, SNAPSHOT_DIR)
					if snapshot_path:
						send_motion_alert(snapshot_path)
					last_saved_time = now

			frame_a = frame_b

	except KeyboardInterrupt:
		print("\nCapture stopped by user.")
	except Exception as e:
		print(f"Error: {e}")
	finally:
		release_sources(picam)


if __name__ == "__main__":
	main()
