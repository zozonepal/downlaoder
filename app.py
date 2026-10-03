import os
import tempfile
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import yt_dlp

app = Flask(__name__)

TEMP_DIR = tempfile.gettempdir()
COOKIES_PATH = os.path.join(os.path.dirname(__file__), 'cookies.txt')

def format_duration(seconds):
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

def get_ytdl_options(extra_opts=None):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'mweb']
            }
        }
    }
    if os.path.exists(COOKIES_PATH):
        opts['cookiefile'] = COOKIES_PATH

    if extra_opts:
        opts.update(extra_opts)
    return opts

# --- PWA Static File Routes ---
@app.route('/manifest.json')
def manifest():
    return send_from_directory('templates', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('.', 'sw.js')

# --- Main App Routes ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.json or {}
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'Please provide a valid YouTube URL.'}), 400

    ydl_opts = get_ytdl_options({'extract_flat': False})

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            video_options = [
                {'format_id': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best', 'resolution': '1080p Full HD', 'ext': 'mp4', 'label': '1080p Full HD (mp4)'},
                {'format_id': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best', 'resolution': '720p HD', 'ext': 'mp4', 'label': '720p HD (mp4)'},
                {'format_id': 'bestvideo[height<=360]+bestaudio/best[height<=360]/best', 'resolution': '360p SD', 'ext': 'mp4', 'label': '360p SD (mp4)'}
            ]

            audio_options = [
                {'format_id': 'bestaudio/best', 'resolution': '320kbps Audio', 'ext': 'mp3', 'label': '320kbps Audio (mp3)'},
                {'format_id': 'bestaudio[ext=m4a]/best', 'resolution': '128kbps AAC', 'ext': 'm4a', 'label': '128kbps AAC (m4a)'}
            ]

            return jsonify({
                'title': info.get('title', 'Unknown Title'),
                'uploader': info.get('uploader') or info.get('channel', 'Unknown Channel'),
                'thumbnail': info.get('thumbnail'),
                'duration': format_duration(info.get('duration')),
                'views': f"{info.get('view_count', 0):,}" if info.get('view_count') else 'N/A',
                'url': url,
                'video_formats': video_options,
                'audio_formats': audio_options
            })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch video details: {str(e)}'}), 500

@app.route('/api/download', methods=['POST'])
def download():
    data = request.json or {}
    url = data.get('url', '').strip()
    format_id = data.get('format_id', 'best')
    ext = data.get('ext', 'mp4')

    if not url:
        return jsonify({'error': 'Missing URL'}), 400

    output_template = os.path.join(TEMP_DIR, '%(title)s.%(ext)s')

    extra_opts = {
        'format': format_id,
        'outtmpl': output_template,
    }

    if ext == 'mp3':
        extra_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    ydl_opts = get_ytdl_options(extra_opts)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            if ext == 'mp3':
                filename = os.path.splitext(filename)[0] + '.mp3'

            if os.path.exists(filename):
                return send_file(filename, as_attachment=True)
            else:
                return jsonify({'error': 'File not found after download.'}), 500

    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

if __name__ == '__main__':
    print("🚀 Server started! Binding to all local network interfaces on port 5000.")
    app.run(host='0.0.0.0', port=5000, debug=True)