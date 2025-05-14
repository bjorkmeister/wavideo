# WAvideo

**WAvideo** is a sleek, self-hosted web application for converting video and audio files into WhatsApp-friendly formats, GIFs, and audio-only versions. It also includes YouTube ripping functionality, real-time progress tracking, and preset profiles.

![screenshot](screenshot.png) <!-- Optional screenshot -->

## 🚀 Features

- 🎥 Drag & drop video conversion interface
- 🎧 Audio-only extraction (MP3, AAC, OGG, etc.)
- 🎞 GIF creation with frame trimming
- 📥 YouTube ripper (with `yt-dlp`)
- 🧠 Preset profiles (WhatsApp, Instagram, Audio, GIF)
- 🎯 Trimming support: start & end time
- 📈 Real-time progress bar with ETA
- 📸 Generates preview thumbnails from output
- 🌙 Dark mode toggle
- 📱 QR code for local network sharing

---

## ⚙ Requirements

- Python 3.8+
- `ffmpeg` installed and in system PATH
- `yt-dlp` installed (via pip or brew)

Install dependencies:

```bash
pip install -r requirements.txt
