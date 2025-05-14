from flask import Flask, request, send_file, render_template_string
from werkzeug.utils import secure_filename
import os
import subprocess
import uuid
import socket

app = Flask(__name__)
UPLOAD_FOLDER = './uploads'
CONVERTED_FOLDER = './converted'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template_string(open('WAvideo.html').read())

@app.route('/convert', methods=['POST'])
def convert_video():
    file = request.files['video']
    if not file:
        return 'No file uploaded.', 400

    filename = secure_filename(file.filename)
    unique_id = uuid.uuid4().hex
    input_path = os.path.join(UPLOAD_FOLDER, unique_id + '_' + filename)

    base_filename = os.path.splitext(filename)[0][:30].replace(' ', '_')
    custom_filename = request.form.get('customFilename', '').strip()
    if custom_filename:
        base_filename = secure_filename(custom_filename[:30])

    file.save(input_path)

    # Generate three preview thumbnails
    thumb_paths = []
    for i, timecode in enumerate(["00:00:01", "00:00:02", "00:00:03"]):
        thumb_path = os.path.join(CONVERTED_FOLDER, f'{base_filename}_thumb{i+1}.jpg')
        thumb_paths.append(f'/converted/{os.path.basename(thumb_path)}')
        subprocess.run([
            'ffmpeg', '-i', input_path, '-ss', timecode, '-vframes', '1', thumb_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    audio_only = request.form.get('audioOnly') == 'true'
    output_format = request.form.get('format', 'mp4')
    bitrate = request.form.get('bitrate', '192k')
    extract_subtitles = request.form.get('extractSubtitles') == 'true'
    make_gif = request.form.get('makeGif') == 'true'
    trim_start = request.form.get('trimStart') or None
    trim_end = request.form.get('trimEnd') or None

    trim_args = []
    if trim_start:
        trim_args.extend(['-ss', trim_start])
    if trim_end:
        trim_args.extend(['-to', trim_end])

    if audio_only or output_format in ['mp3', 'aac', 'ogg', 'wav', 'flac']:
        output_path = os.path.join(CONVERTED_FOLDER, f'{base_filename}_{output_format}_converted.{output_format}')
        acodec_map = {
            'mp3': 'libmp3lame',
            'aac': 'aac',
            'ogg': 'libvorbis',
            'flac': 'flac',
            'wav': 'pcm_s16le'
        }
        codec = acodec_map.get(output_format, 'aac')
        ffmpeg_cmd = [
            'ffmpeg', *trim_args, '-i', input_path,
            '-vn', '-acodec', codec, '-b:a', bitrate,
            output_path
        ]
    elif make_gif:
        output_path = os.path.join(CONVERTED_FOLDER, f'{base_filename}_converted.gif')
        ffmpeg_cmd = [
            'ffmpeg', *trim_args, '-i', input_path,
            '-vf', 'fps=10,scale=320:-1:flags=lanczos',
            '-loop', '0',
            output_path
        ]
        thumb_path = os.path.join(CONVERTED_FOLDER, f'{base_filename}_thumb.jpg')
        subprocess.run([
            'ffmpeg', '-i', input_path, '-ss', '00:00:01', '-vframes', '1', thumb_path
        ], check=True)
    else:
        output_path = os.path.join(CONVERTED_FOLDER, f'{base_filename}_{output_format}_converted.mp4')
        ffmpeg_cmd = [
            'ffmpeg', *trim_args, '-i', input_path,
            '-vf', 'scale=480:-2',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
            '-c:a', 'aac', '-b:a', '128k'
        ]
        if extract_subtitles:
            ffmpeg_cmd += ['-scodec', 'copy']
        ffmpeg_cmd.append(output_path)

    subprocess.run(ffmpeg_cmd, check=True)

    if os.name == 'posix':
        subprocess.Popen(['open', CONVERTED_FOLDER])

    def get_video_info(filepath):
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                 'stream=width,height,codec_name', '-of', 'default=noprint_wrappers=1', filepath],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            info = dict(line.split('=') for line in result.stdout.strip().split('\n') if '=' in line)
            return info
        except Exception:
            return {}

    stats = get_video_info(output_path)
    stats.update({
        "status": "success",
        "filename": os.path.basename(output_path),
        "format": output_format,
        "size": os.path.getsize(output_path),
    })
    stats['thumbnails'] = thumb_paths
    return stats

@app.route('/local-ip')
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return {'ip': IP}


from flask import send_from_directory

@app.route('/converted/<path:filename>')
def serve_converted_file(filename):
    return send_from_directory(CONVERTED_FOLDER, filename)


# --- BEGIN: /rip-youtube endpoint ---
@app.route('/rip-youtube', methods=['POST'])
def rip_youtube():
    data = request.get_json()
    url = data.get('url')
    auto_convert = data.get('autoConvert', False)

    if not url:
        return 'Missing URL', 400

    unique_id = uuid.uuid4().hex
    download_path = os.path.join(UPLOAD_FOLDER, f'{unique_id}.%(ext)s')
    final_file = ''

    # Run yt-dlp to download
    try:
        result = subprocess.run([
            'yt-dlp', '-o', download_path, '-f', 'bestaudio+best', '--merge-output-format', 'mp4', url
        ], capture_output=True, text=True, check=True)
        
        # Parse resulting filename
        for line in result.stdout.splitlines():
            if '[ExtractAudio]' in line or '[download]' in line:
                potential = line.split()[-1]
                if potential.endswith(('.mp4', '.mkv', '.webm', '.mp3', '.m4a')):
                    final_file = potential if os.path.exists(potential) else ''
        
        # Fallback: guess from yt-dlp template
        if not final_file:
            guessed = download_path.replace('%(ext)s', 'mp4')
            if os.path.exists(guessed):
                final_file = guessed

        if not final_file:
            return 'Failed to locate downloaded file.', 500

    except subprocess.CalledProcessError as e:
        return f'Error downloading: {e.stderr}', 500

    if not auto_convert:
        return {'status': 'success', 'filename': os.path.basename(final_file)}

    # Emulate form upload for conversion
    from werkzeug.datastructures import FileStorage
    with open(final_file, 'rb') as f:
        fs = FileStorage(stream=f, filename=os.path.basename(final_file))
        # Reuse the conversion logic
        with app.test_request_context(method='POST', data={'video': fs}):
            request.files = {'video': fs}
            return convert_video()
# --- END: /rip-youtube endpoint ---

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5051)
