import os, sys, threading, json, subprocess, time, shutil, webbrowser
from io import BytesIO
from collections import deque
import customtkinter as ctk
from customtkinter import filedialog
import yt_dlp, requests
from PIL import Image
from yt_dlp.utils import DownloadError

try:
    from moviepy.config import FFMPEG_BINARY
except (ImportError, ModuleNotFoundError):
    FFMPEG_BINARY = None

# --- Constants ---
SUPPORTED_BROWSERS = ['none', 'chrome', 'firefox', 'edge', 'brave', 'opera']
AUDIO_FORMATS = ['m4a', 'mp3', 'wav', 'flac']
VIDEO_FORMATS = ['mkv', 'mp4']
VIDEO_RESOLUTIONS = ['720p', '480p', '360p']
ABOUT_TEXT = "TuneCatcher v1.9\nA modern downloader for video and audio.\nBuilt with Python, customtkinter, and yt-dlp."
FILENAME_PRESETS = {
    "Title [ID]": "%(title)s [%(id)s]",
    "Title": "%(title)s",
    "Uploader - Title": "%(uploader)s - %(title)s",
    "Uploader - Title [ID]": "%(uploader)s - %(title)s [%(id)s]",
    "Custom...": "custom"
}

class PlaylistSelectionWindow(ctk.CTkToplevel):
    def __init__(self, master, playlist_url):
        super().__init__(master); self.master_app = master; self.title("Select Playlist Items"); self.geometry("600x400")
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1); self.checkboxes = []
        ctk.CTkLabel(self, text="Fetching playlist, please wait...").pack(pady=20); self.after(200, lambda: threading.Thread(target=self.fetch_and_populate, args=(playlist_url,), daemon=True).start())
        self.protocol("WM_DELETE_WINDOW", self.destroy); self.grab_set()
    def fetch_and_populate(self, url):
        try:
            limit = self.master_app.settings['playlist_limit']
            ydl_opts = {'quiet': True, 'extract_flat': True, 'playlistend': int(limit) if limit.isdigit() else None}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: info = ydl.extract_info(url, download=False)
            self.after(0, self.populate_ui, info.get('entries', []))
        except Exception as e: self.after(0, lambda: (self.master_app.update_status(f"Error fetching playlist: {e}"), self.destroy()))
    def populate_ui(self, entries):
        for w in self.winfo_children(): w.destroy()
        controls_frame = ctk.CTkFrame(self); controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(controls_frame, text="Select All", command=lambda: [cb.select() for cb, url in self.checkboxes]).pack(side="left", padx=5); ctk.CTkButton(controls_frame, text="Deselect All", command=lambda: [cb.deselect() for cb, url in self.checkboxes]).pack(side="left", padx=5)
        scroll_frame = ctk.CTkScrollableFrame(self, label_text=f"Showing first {len(entries)} items"); scroll_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        for entry in entries:
            if not entry: continue
            cb = ctk.CTkCheckBox(scroll_frame, text=entry.get('title', 'Unknown Title')); cb.pack(fill="x", padx=10, pady=2, anchor="w"); self.checkboxes.append((cb, entry.get('url')))
        ctk.CTkButton(self, text="Download Selected", command=self.download_selected, height=35).grid(row=2, column=0, padx=10, pady=10, sticky="ew")
    def download_selected(self):
        urls_to_download = [url for cb, url in self.checkboxes if cb.get() == 1 and url]
        if urls_to_download: threading.Thread(target=self.master_app.download_batch, args=(urls_to_download,), daemon=True).start()
        self.destroy()

class TuneCatcher(ctk.CTk):
    def __init__(self, ffmpeg_path):
        super().__init__()
        self.ffmpeg_path = ffmpeg_path
        self.base_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)); self.config_file = os.path.join(self.base_dir, 'tunecatcher_config.json')
        self.settings = {'mode': 'audio', 'video_quality': '720p', 'cookie_browser': 'none', 'audio_format': 'mp3', 'video_format': 'mp4', 
                         'appearance_mode': 'System', 'save_path': os.path.join(self.base_dir, "Downloads"), 'history': [], 'playlist_limit': '50',
                         'filename_preset': 'Title [ID]', 'filename_template_custom': '%(title)s'}
        try:
            with open(self.config_file, 'r') as f: self.settings.update(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError): pass
        
        self.preview_thread = None; self.preview_thread_stop_event = threading.Event()
        self.title("TuneCatcher"); self.geometry("750x660"); self.grid_columnconfigure(0, weight=1); ctk.set_appearance_mode(self.settings['appearance_mode']); self.create_widgets(); self.populate_history_tab()

    def save_settings(self):
        self.settings['history'] = self.settings['history'][-20:]
        with open(self.config_file, 'w') as f: json.dump(self.settings, f, indent=4)

    def create_widgets(self):
        self.tab_view = ctk.CTkTabview(self); self.tab_view.grid(row=0, column=0, padx=20, pady=20, sticky="nsew"); self.grid_rowconfigure(0, weight=1)
        downloader_tab, history_tab, settings_tab, about_tab = self.tab_view.add("Downloader"), self.tab_view.add("History"), self.tab_view.add("Settings"), self.tab_view.add("About"); downloader_tab.grid_columnconfigure(0, weight=1)
        url_frame = ctk.CTkFrame(downloader_tab); url_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew"); url_frame.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(url_frame, placeholder_text="Paste a URL or Playlist..."); self.url_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew"); self.url_entry.bind("<KeyRelease>", self.trigger_preview_update)
        preview_frame = ctk.CTkFrame(downloader_tab); preview_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew"); preview_frame.grid_columnconfigure(1, weight=1)
        self.thumbnail_label = ctk.CTkLabel(preview_frame, text=""); self.thumbnail_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10); self.title_label = ctk.CTkLabel(preview_frame, text="Title...", anchor="w", font=ctk.CTkFont(weight="bold")); self.title_label.grid(row=0, column=1, padx=10, pady=(10, 0), sticky="ew"); self.uploader_label = ctk.CTkLabel(preview_frame, text="Uploader...", anchor="w"); self.uploader_label.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="new")
        self.download_now_button = ctk.CTkButton(downloader_tab, text="Download", command=self.handle_url_action, height=40); self.download_now_button.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.progress_bar = ctk.CTkProgressBar(downloader_tab); self.progress_bar.set(0); self.progress_bar.grid(row=3, column=0, padx=10, pady=(0,10), sticky="ew")
        options_frame = ctk.CTkFrame(downloader_tab); options_frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        self.mode_segmented_button = ctk.CTkSegmentedButton(options_frame, values=["Audio", "Video"], command=self.on_mode_change); self.mode_segmented_button.set(self.settings['mode'].capitalize()); self.mode_segmented_button.pack(side="left", padx=10, pady=10)
        self.audio_options_frame = ctk.CTkFrame(options_frame); ctk.CTkLabel(self.audio_options_frame, text="Audio Format:").pack(side="left", padx=(10,5)); self.audio_format_menu = ctk.CTkOptionMenu(self.audio_options_frame, values=AUDIO_FORMATS, command=self.on_format_change); self.audio_format_menu.set(self.settings['audio_format']); self.audio_format_menu.pack(side="left", padx=(0,10))
        self.video_options_frame = ctk.CTkFrame(options_frame); ctk.CTkLabel(self.video_options_frame, text="Video Format:").pack(side="left", padx=(10,5)); self.video_format_menu = ctk.CTkOptionMenu(self.video_options_frame, values=VIDEO_FORMATS, command=self.on_format_change); self.video_format_menu.set(self.settings['video_format']); self.video_format_menu.pack(side="left", padx=(0,10)); ctk.CTkLabel(self.video_options_frame, text="Resolution:").pack(side="left", padx=(10,5)); self.resolution_menu = ctk.CTkOptionMenu(self.video_options_frame, values=VIDEO_RESOLUTIONS, command=self.on_resolution_change); self.resolution_menu.set(self.settings['video_quality']); self.resolution_menu.pack(side="left", padx=(0,10))
        path_frame = ctk.CTkFrame(downloader_tab); path_frame.grid(row=5, column=0, padx=10, pady=10, sticky="ew"); path_frame.grid_columnconfigure(0, weight=1); p = self.settings['save_path']; p_display = p if len(p) <= 60 else f"...{p[-57:]}"; self.path_label = ctk.CTkLabel(path_frame, text=f"Save To: {p_display}", anchor="w"); self.path_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew"); ctk.CTkButton(path_frame, text="Browse...", command=self.select_save_path).grid(row=0, column=1, padx=10, pady=10)
        status_frame = ctk.CTkFrame(downloader_tab); status_frame.grid(row=6, column=0, padx=10, pady=20, sticky="sew"); downloader_tab.grid_rowconfigure(6, weight=1); status_frame.grid_columnconfigure(0, weight=1); self.status_label = ctk.CTkLabel(status_frame, text="Ready", anchor="w"); self.status_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew"); self.open_folder_button = ctk.CTkButton(status_frame, text="Open Download Folder", command=lambda: self.open_folder(self.last_download_path))
        
        history_tab.grid_columnconfigure(0, weight=1); history_tab.grid_rowconfigure(1, weight=1); history_top_frame = ctk.CTkFrame(history_tab); history_top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew"); history_top_frame.grid_columnconfigure(0, weight=1); ctk.CTkLabel(history_top_frame, text="Download History", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w"); ctk.CTkButton(history_top_frame, text="Clear History", command=self.clear_history).grid(row=0, column=1, sticky="e")
        self.history_scroll_frame = ctk.CTkScrollableFrame(history_tab); self.history_scroll_frame.grid(row=1, column=0, padx=10, pady=(0,10), sticky="nsew")
        
        settings_tab.grid_columnconfigure(0, weight=1); appearance_frame = ctk.CTkFrame(settings_tab); appearance_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew"); ctk.CTkLabel(appearance_frame, text="Appearance Mode:").pack(side="left", padx=10, pady=10); appearance_menu = ctk.CTkOptionMenu(appearance_frame, values=['System', 'Light', 'Dark'], command=self.on_appearance_change); appearance_menu.set(self.settings['appearance_mode']); appearance_menu.pack(side="left", padx=10, pady=10); cookie_frame = ctk.CTkFrame(settings_tab); cookie_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew"); ctk.CTkLabel(cookie_frame, text="Use Login Cookies From:").pack(side="left", padx=10, pady=10); cookie_menu = ctk.CTkOptionMenu(cookie_frame, values=[b.capitalize() for b in SUPPORTED_BROWSERS], command=self.on_cookie_browser_change); cookie_menu.set(self.settings['cookie_browser'].capitalize()); cookie_menu.pack(side="left", padx=10, pady=10); 
        playlist_frame = ctk.CTkFrame(settings_tab); playlist_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew"); ctk.CTkLabel(playlist_frame, text="Playlist items to fetch ('all' for no limit):").pack(side="left", padx=10, pady=10); self.playlist_limit_entry = ctk.CTkEntry(playlist_frame, width=60); self.playlist_limit_entry.insert(0, self.settings['playlist_limit']); self.playlist_limit_entry.pack(side="left", padx=10, pady=10); self.playlist_limit_entry.bind("<KeyRelease>", self.on_playlist_limit_change)
        filename_frame = ctk.CTkFrame(settings_tab); filename_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew"); filename_frame.grid_columnconfigure(1, weight=1); ctk.CTkLabel(filename_frame, text="Filename Format:").grid(row=0, column=0, padx=10, pady=10); self.filename_menu = ctk.CTkOptionMenu(filename_frame, values=list(FILENAME_PRESETS.keys()), command=self.on_filename_preset_change); self.filename_menu.set(self.settings['filename_preset']); self.filename_menu.grid(row=0, column=1, padx=10, pady=10, sticky="ew"); 
        self.filename_entry = ctk.CTkEntry(filename_frame); self.filename_entry.insert(0, self.settings['filename_template_custom']); self.filename_entry.bind("<KeyRelease>", self.on_filename_template_change)

        about_tab.grid_columnconfigure(0, weight=1); about_tab.grid_rowconfigure(0, weight=1); about_frame = ctk.CTkScrollableFrame(about_tab); about_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew"); ctk.CTkLabel(about_frame, text=f"{ABOUT_TEXT.splitlines()[1]} v{ABOUT_TEXT.splitlines()[2]}", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 5), padx=10, anchor="w"); ctk.CTkLabel(about_frame, text="\n".join(ABOUT_TEXT.splitlines()[4:]), wraplength=600, justify="left").pack(pady=5, padx=10, anchor="w", fill="x")
        self.on_mode_change(self.settings['mode']); self.on_filename_preset_change(self.settings['filename_preset'])

    def clear_history(self):
        if messagebox.askyesno("Confirm Clear History", "Are you sure you want to permanently delete all download history?"):
            self.settings['history'].clear(); self.save_settings(); self.populate_history_tab(); self.update_status("History cleared.")
    def populate_history_tab(self):
        for w in self.history_scroll_frame.winfo_children(): w.destroy()
        if not self.settings['history']: ctk.CTkLabel(self.history_scroll_frame, text="No downloads yet.").pack(pady=20); return
        for item in self.settings['history']: f = ctk.CTkFrame(self.history_scroll_frame); f.pack(fill="x", padx=5, pady=5); f.grid_columnconfigure(0, weight=1); ctk.CTkLabel(f, text=item.get('title', 'Unknown'), anchor="w").grid(row=0, column=0, padx=10, sticky="ew"); ctk.CTkButton(f, text="Open", width=80, command=lambda p=item.get('file_path'): self.open_file(p)).grid(row=0, column=1, padx=5); ctk.CTkButton(f, text="Copy URL", width=100, command=lambda u=item.get('url'): self.copy_to_clipboard(u)).grid(row=0, column=2, padx=5)
    def on_mode_change(self, new_mode):
        self.settings['mode'] = new_mode.lower(); self.save_settings()
        if self.settings['mode'] == 'video': self.audio_options_frame.pack_forget(); self.video_options_frame.pack(side="left", padx=10, pady=10)
        else: self.video_options_frame.pack_forget(); self.audio_options_frame.pack(side="left", padx=10, pady=10)
        self.update_status(f"Mode set to {new_mode}")
    def on_format_change(self, new_format): key = 'video_format' if self.settings['mode'] == 'video' else 'audio_format'; self.settings[key] = new_format; self.save_settings(); self.update_status(f"Default {key.split('_')[0]} format set to {new_format.upper()}")
    def on_resolution_change(self, new_res): self.settings['video_quality'] = new_res; self.save_settings(); self.update_status(f"Default resolution set to {new_res}")
    def on_playlist_limit_change(self, event=None):
        value = self.playlist_limit_entry.get().lower()
        if value.isdigit() or value == "all": self.settings['playlist_limit'] = value; self.save_settings(); self.update_status(f"Playlist fetch limit set to {value}")
    def on_filename_preset_change(self, new_preset):
        self.settings['filename_preset'] = new_preset; self.save_settings()
        if new_preset == "Custom...": self.filename_entry.grid(row=1, column=1, padx=10, pady=(0,10), sticky="ew")
        else: self.filename_entry.grid_forget()
        self.update_status(f"Filename format set to: {new_preset}")
    def on_filename_template_change(self, event=None): self.settings['filename_template_custom'] = self.filename_entry.get(); self.save_settings()
    def on_appearance_change(self, new_mode): self.settings['appearance_mode'] = new_mode; ctk.set_appearance_mode(new_mode); self.save_settings()
    def on_cookie_browser_change(self, new_browser): self.settings['cookie_browser'] = new_browser.lower(); self.save_settings(); self.update_status(f"Using cookies from: {new_browser}")
    def select_save_path(self):
        new_path = filedialog.askdirectory(initialdir=self.settings['save_path'])
        if new_path: self.settings['save_path'] = new_path; self.save_settings(); p_display = new_path if len(new_path) <= 60 else f"...{new_path[-57:]}"; self.path_label.configure(text=f"Save To: {p_display}"); self.update_status(f"Save location set")
    def handle_url_action(self):
        url = self.url_entry.get()
        if not (url and url.startswith("http")): self.update_status("Please enter a valid URL."); return
        if "list=" in url or "/playlist?" in url: PlaylistSelectionWindow(self, url)
        else: threading.Thread(target=self.download_batch, args=([url],), daemon=True).start()
    def download_batch(self, urls):
        for url in urls:
            mode = self.settings['mode']; fmt = self.settings['video_format'] if mode == 'video' else self.settings['audio_format']; quality = self.settings['video_quality']
            job = {'url': url, 'format': fmt, 'mode': mode, 'quality': quality}; self.download_content(job); time.sleep(1)
    def trigger_preview_update(self, event=None):
        if self.preview_thread and self.preview_thread.is_alive(): self.preview_thread_stop_event.set()
        url = self.url_entry.get(); self.preview_thread_stop_event.clear(); self.preview_thread = threading.Thread(target=self._update_preview_thread, args=(url, self.preview_thread_stop_event.is_set), daemon=True); self.preview_thread.start() if url and url.startswith("http") else None
    def _update_preview_thread(self, url, stop_check):
        self.after(0, self._set_preview_data, "loading", None); info = self.fetch_metadata(url, stop_check); image = None
        if stop_check() or not info: self.after(0, self._set_preview_data, None, None); return
        if info.get('thumbnail_url'):
            try: response = requests.get(info['thumbnail_url']); response.raise_for_status(); image = ctk.CTkImage(light_image=Image.open(BytesIO(response.content)), size=(160, 90)) if not stop_check() else None
            except requests.RequestException: pass
        if not stop_check(): self.after(0, self._set_preview_data, info, image)
    def _set_preview_data(self, info, image):
        if info == "loading": self.title_label.configure(text="Fetching..."); self.uploader_label.configure(text=""); self.thumbnail_label.configure(image=None)
        elif info: self.title_label.configure(text=info['title']); self.uploader_label.configure(text=info['uploader']); self.thumbnail_label.configure(image=image, text="")
        else: self.title_label.configure(text="Invalid URL or video not found"); self.uploader_label.configure(text=""); self.thumbnail_label.configure(image=None, text="")
    def download_content(self, job):
        success = False
        try:
            self.after(0, lambda: (self.download_now_button.configure(state="disabled", text="Downloading..."), self.open_folder_button.grid_forget()))
            subfolder = "Audio" if job['mode'] == 'audio' else "Video"; output_dir = os.path.join(self.settings['save_path'], subfolder); os.makedirs(output_dir, exist_ok=True); self.last_download_path = output_dir
            opts = self.build_ydl_options(output_dir, job)
            with yt_dlp.YoutubeDL(opts) as ydl: info = ydl.extract_info(job['url'], download=False, process=False); success = ydl.download([job['url']]) == 0
            if success:
                path = os.path.join(output_dir, ydl.prepare_filename(info)); ext = f".{job['format']}"; path = path.rsplit('.', 1)[0] + ext
                self.settings['history'].insert(0, {'title': info.get('title', 'Unknown'), 'url': job['url'], 'file_path': path}); self.save_settings(); self.update_status(f"✓ Download Successful: {info.get('title', '')[:40]}")
            else: self.update_status(f"Finished with errors: {job['url'][:50]}")
        except DownloadError as e: self.after(0, self.update_status, f"✗ Download Error: Check URL or update yt-dlp")
        except Exception: self.after(0, self.update_status, "✗ An unexpected error occurred")
        finally: self.after(0, self.on_download_finished, success)
    def fetch_metadata(self, url, stop_check):
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': 'in_playlist', 'forcejson': True}) as ydl: info = ydl.extract_info(url, download=False); return None if stop_check() else {'title': info.get('title', 'No Title'), 'uploader': info.get('uploader', 'N/A'), 'thumbnail_url': info.get('thumbnail')}
        except Exception: return None
    def build_ydl_options(self, output_dir, job):
        template_str = FILENAME_PRESETS.get(self.settings['filename_preset']) if self.settings['filename_preset'] != 'Custom...' else self.settings['filename_template_custom']
        opts = {'ignoreerrors': True, 'outtmpl': os.path.join(output_dir, f"{template_str}.%(ext)s"), 'progress_hooks': [self._progress_hook], 'noprogress': True, 'ffmpeg_location': self.ffmpeg_path};
        if self.settings['cookie_browser'] != 'none': opts['cookiesfrombrowser'] = (self.settings['cookie_browser'], None)
        if job['mode'] == 'audio':
            opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': job['format']}]})
        else:
            quality_str = job['quality'].replace('p', '')
            opts.update({'format': f"bestvideo[height<={quality_str}]+bestaudio/best", 'merge_output_format': job['format']})
        return opts
    @staticmethod
    def format_time(seconds):
        if seconds is None: return "??:??"; mins, secs = divmod(int(seconds), 60); return f"{mins:02d}:{secs:02d}"
    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total > 0:
                percent_str = d.get('_percent_str', '0.0%').strip(); speed = d.get('speed'); speed_str = f"{speed / 1024**2:.2f} MB/s" if speed else "..."; eta_str = self.format_time(d.get('eta'))
                status_text = f"Downloading... {percent_str}  |  {speed_str}  |  ETA: {eta_str}"; self.after(0, self.update_progress, d['downloaded_bytes'] / total, status_text)
        elif d['status'] == 'finished': self.after(0, self.update_progress, 1.0, "Processing...")
    def on_download_finished(self, success):
        self.download_now_button.configure(state="normal", text="Download"); self.progress_bar.set(0)
        if success: self.populate_history_tab(); self.open_folder_button.grid(row=0, column=0, columnspan=2, padx=10, pady=(10,5), sticky="ew")
    def open_file(self, path): (self.open_folder(os.path.dirname(path))) if path and os.path.exists(path) else self.update_status(f"File not found: {path}")
    def open_folder(self, path):
        if not path: return
        try:
            if sys.platform == "win32": os.startfile(path)
            elif sys.platform == "darwin": subprocess.run(["open", path])
            else: subprocess.run(["xdg-open", path])
        except Exception as e: self.update_status(f"Error opening folder: {e}")
    def copy_to_clipboard(self, text): self.clipboard_clear(); self.clipboard_append(text); self.update_status("URL copied!")
    def update_progress(self, v, t): self.progress_bar.set(v); self.status_label.configure(text=t)
    def update_status(self, t): self.status_label.configure(text=t)
    def on_close(self): self.destroy()

if __name__ == "__main__":
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path and FFMPEG_BINARY and os.path.exists(FFMPEG_BINARY):
        ffmpeg_path = FFMPEG_BINARY
    if not ffmpeg_path:
        print("FFmpeg not found. Attempting one-time automatic download via imageio...")
        try:
            from imageio.plugins.ffmpeg import download
            download()
            ffmpeg_path = shutil.which("ffmpeg") or (FFMPEG_BINARY if FFMPEG_BINARY and os.path.exists(FFMPEG_BINARY) else None)
            print("FFmpeg downloaded successfully.")
        except Exception as e:
            print(f"Automatic FFmpeg download failed: {e}"); ffmpeg_path = None
    
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        print(f"Using FFmpeg found at: {ffmpeg_path}")
        app = TuneCatcher(ffmpeg_path)
        app.protocol("WM_DELETE_WINDOW", app.on_close)
        app.mainloop()
    else:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk(); root.withdraw()
        messagebox.showerror("Critical Dependency Missing", "FFmpeg could not be found or downloaded.\nPlease install FFmpeg manually and ensure it's in your system's PATH.\nThe application will now close.")
