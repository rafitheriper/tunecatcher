#!/usr/bin/env python3
"""
TuneCatcher v1.9
A modern, professional video and audio downloader application.

This application provides a user-friendly GUI for downloading videos and audio
from various platforms using yt-dlp as the backend. Features include playlist
support, multiple formats, quality selection, and download history.

Dependencies:
    - customtkinter: Modern GUI framework
    - yt-dlp: Video/audio extraction library
    - moviepy: Video processing (optional)
    - PIL (Pillow): Image processing
    - requests: HTTP requests for thumbnails

Author: TuneCatcher Development Team
License: MIT
"""

import os
import sys
import threading
import json
import subprocess
import time
import shutil
import webbrowser
from io import BytesIO
from collections import deque
from typing import Dict, List, Optional, Any, Callable

# Third-party imports
import customtkinter as ctk
from customtkinter import filedialog
import yt_dlp
import requests
from PIL import Image
from yt_dlp.utils import DownloadError

# Optional moviepy import for FFmpeg detection
try:
    from moviepy.config import FFMPEG_BINARY
except (ImportError, ModuleNotFoundError):
    FFMPEG_BINARY = None


# =====================================================
# CONSTANTS AND CONFIGURATION
# =====================================================

# Supported browsers for cookie extraction
SUPPORTED_BROWSERS = ['none', 'chrome', 'firefox', 'edge', 'brave', 'opera']

# Available output formats
AUDIO_FORMATS = ['m4a', 'mp3', 'wav', 'flac']
VIDEO_FORMATS = ['mkv', 'mp4']
VIDEO_RESOLUTIONS = ['720p', '480p', '360p']

# Application information
ABOUT_TEXT = """TuneCatcher v1.9
A modern downloader for video and audio.
Built with Python, customtkinter, and yt-dlp.

Features:
- Download videos and audio from multiple platforms
- Playlist support with selective downloading
- Multiple format and quality options
- Browser cookie integration for private content
- Download history tracking
- Modern, customizable interface
"""

# Filename template presets for output files
FILENAME_PRESETS = {
    "Title [ID]": "%(title)s [%(id)s]",
    "Title": "%(title)s",
    "Uploader - Title": "%(uploader)s - %(title)s",
    "Uploader - Title [ID]": "%(uploader)s - %(title)s [%(id)s]",
    "Custom...": "custom"
}

# Default application settings
DEFAULT_SETTINGS = {
    'mode': 'audio',
    'video_quality': '720p',
    'cookie_browser': 'none',
    'audio_format': 'mp3',
    'video_format': 'mp4',
    'appearance_mode': 'System',
    'save_path': '',  # Will be set to Downloads folder relative to executable
    'history': [],
    'playlist_limit': '50',
    'filename_preset': 'Title [ID]',
    'filename_template_custom': '%(title)s'
}


# =====================================================
# PLAYLIST SELECTION WINDOW CLASS
# =====================================================

class PlaylistSelectionWindow(ctk.CTkToplevel):
    """
    A modal window for selecting specific items from a playlist before downloading.
    
    This window fetches playlist information asynchronously and presents
    checkboxes for each item, allowing users to select which items to download.
    """
    
    def __init__(self, master: 'TuneCatcher', playlist_url: str):
        """
        Initialize the playlist selection window.
        
        Args:
            master: The parent TuneCatcher application instance
            playlist_url: URL of the playlist to process
        """
        super().__init__(master)
        self.master_app = master
        self.playlist_url = playlist_url
        self.checkboxes: List[tuple] = []  # List of (checkbox_widget, url) tuples
        
        # Configure window properties
        self.title("Select Playlist Items")
        self.geometry("600x400")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Show loading message
        loading_label = ctk.CTkLabel(self, text="Fetching playlist, please wait...")
        loading_label.pack(pady=20)
        
        # Start playlist fetch in background thread
        self.after(200, self._start_playlist_fetch)
        
        # Configure window behavior
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()  # Make window modal
    
    def _start_playlist_fetch(self) -> None:
        """Start the playlist fetching process in a separate thread."""
        fetch_thread = threading.Thread(
            target=self._fetch_playlist_data,
            args=(self.playlist_url,),
            daemon=True
        )
        fetch_thread.start()
    
    def _fetch_playlist_data(self, url: str) -> None:
        """
        Fetch playlist data from the given URL.
        
        Args:
            url: Playlist URL to fetch data from
        """
        try:
            # Get playlist limit from settings
            limit = self.master_app.settings['playlist_limit']
            
            # Configure yt-dlp options for playlist extraction
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,  # Only extract metadata, don't download
                'playlistend': int(limit) if limit.isdigit() else None
            }
            
            # Extract playlist information
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            # Update UI on main thread
            entries = info.get('entries', [])
            self.after(0, self._populate_playlist_ui, entries)
            
        except Exception as e:
            # Handle errors on main thread
            error_msg = f"Error fetching playlist: {e}"
            self.after(0, lambda: (
                self.master_app.update_status(error_msg),
                self.destroy()
            ))
    
    def _populate_playlist_ui(self, entries: List[Dict]) -> None:
        """
        Populate the UI with playlist entries.
        
        Args:
            entries: List of playlist entry dictionaries
        """
        # Clear existing widgets
        for widget in self.winfo_children():
            widget.destroy()
        
        # Create control buttons frame
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # Select/Deselect all buttons
        select_all_btn = ctk.CTkButton(
            controls_frame,
            text="Select All",
            command=self._select_all_items
        )
        select_all_btn.pack(side="left", padx=5)
        
        deselect_all_btn = ctk.CTkButton(
            controls_frame,
            text="Deselect All",
            command=self._deselect_all_items
        )
        deselect_all_btn.pack(side="left", padx=5)
        
        # Create scrollable frame for playlist items
        scroll_frame = ctk.CTkScrollableFrame(
            self,
            label_text=f"Showing first {len(entries)} items"
        )
        scroll_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        # Add checkbox for each playlist entry
        for entry in entries:
            if not entry:  # Skip empty entries
                continue
                
            title = entry.get('title', 'Unknown Title')
            url = entry.get('url')
            
            checkbox = ctk.CTkCheckBox(scroll_frame, text=title)
            checkbox.pack(fill="x", padx=10, pady=2, anchor="w")
            
            self.checkboxes.append((checkbox, url))
        
        # Download selected button
        download_btn = ctk.CTkButton(
            self,
            text="Download Selected",
            command=self._download_selected_items,
            height=35
        )
        download_btn.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
    
    def _select_all_items(self) -> None:
        """Select all playlist items."""
        for checkbox, _ in self.checkboxes:
            checkbox.select()
    
    def _deselect_all_items(self) -> None:
        """Deselect all playlist items."""
        for checkbox, _ in self.checkboxes:
            checkbox.deselect()
    
    def _download_selected_items(self) -> None:
        """Start downloading selected playlist items."""
        # Get URLs of selected items
        selected_urls = [
            url for checkbox, url in self.checkboxes
            if checkbox.get() == 1 and url
        ]
        
        if selected_urls:
            # Start batch download in background thread
            download_thread = threading.Thread(
                target=self.master_app.download_batch,
                args=(selected_urls,),
                daemon=True
            )
            download_thread.start()
        
        # Close the selection window
        self.destroy()


# =====================================================
# MAIN APPLICATION CLASS
# =====================================================

class TuneCatcher(ctk.CTk):
    """
    Main application class for TuneCatcher.
    
    This class manages the GUI, settings, and coordinates all downloading operations.
    It provides a modern interface for downloading videos and audio from various
    platforms with extensive customization options.
    """
    
    def __init__(self, ffmpeg_path: Optional[str]):
        """
        Initialize the TuneCatcher application.
        
        Args:
            ffmpeg_path: Path to FFmpeg executable, or None if not found
        """
        super().__init__()
        
        # Store FFmpeg path for later use
        self.ffmpeg_path = ffmpeg_path
        
        # Initialize application paths
        self._setup_application_paths()
        
        # Load or create application settings
        self._load_application_settings()
        
        # Initialize threading components for preview updates
        self.preview_thread: Optional[threading.Thread] = None
        self.preview_thread_stop_event = threading.Event()
        
        # Track last download path for folder opening
        self.last_download_path: Optional[str] = None
        
        # Configure main window
        self._configure_main_window()
        
        # Create and setup GUI components
        self._create_user_interface()
        
        # Load download history
        self._populate_history_display()
    
    def _setup_application_paths(self) -> None:
        """Setup base directory and configuration file paths."""
        # Determine base directory (handles both script and executable)
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            self.base_dir = os.path.dirname(sys.executable)
        else:
            # Running as script
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Configuration file path
        self.config_file = os.path.join(self.base_dir, 'tunecatcher_config.json')
    
    def _load_application_settings(self) -> None:
        """Load application settings from config file or use defaults."""
        # Start with default settings
        self.settings = DEFAULT_SETTINGS.copy()
        
        # Set default save path if not specified
        if not self.settings['save_path']:
            self.settings['save_path'] = os.path.join(self.base_dir, "Downloads")
        
        # Try to load existing settings
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                saved_settings = json.load(f)
                self.settings.update(saved_settings)
        except (FileNotFoundError, json.JSONDecodeError):
            # Config file doesn't exist or is corrupted, use defaults
            pass
    
    def _configure_main_window(self) -> None:
        """Configure main window properties and appearance."""
        self.title("TuneCatcher")
        self.geometry("750x660")
        self.grid_columnconfigure(0, weight=1)
        
        # Apply saved appearance mode
        ctk.set_appearance_mode(self.settings['appearance_mode'])
    
    def _create_user_interface(self) -> None:
        """Create and setup all GUI components."""
        # Create main tab view
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        
        # Create individual tabs
        self._create_downloader_tab()
        self._create_history_tab()
        self._create_settings_tab()
        self._create_about_tab()
        
        # Apply current settings to UI
        self._apply_current_settings()
    
    def _create_downloader_tab(self) -> None:
        """Create the main downloader tab with all download controls."""
        downloader_tab = self.tab_view.add("Downloader")
        downloader_tab.grid_columnconfigure(0, weight=1)
        
        # URL input section
        self._create_url_input_section(downloader_tab)
        
        # Preview section
        self._create_preview_section(downloader_tab)
        
        # Download button
        self._create_download_button(downloader_tab)
        
        # Progress bar
        self._create_progress_bar(downloader_tab)
        
        # Download options
        self._create_download_options(downloader_tab)
        
        # Save path selection
        self._create_path_selection(downloader_tab)
        
        # Status section
        self._create_status_section(downloader_tab)
    
    def _create_url_input_section(self, parent) -> None:
        """Create URL input field."""
        url_frame = ctk.CTkFrame(parent)
        url_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        url_frame.grid_columnconfigure(0, weight=1)
        
        self.url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="Paste a URL or Playlist..."
        )
        self.url_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # Bind event for live preview updates
        self.url_entry.bind("<KeyRelease>", self._trigger_preview_update)
    
    def _create_preview_section(self, parent) -> None:
        """Create preview section for video/audio information."""
        preview_frame = ctk.CTkFrame(parent)
        preview_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        preview_frame.grid_columnconfigure(1, weight=1)
        
        # Thumbnail display
        self.thumbnail_label = ctk.CTkLabel(preview_frame, text="")
        self.thumbnail_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10)
        
        # Title display
        self.title_label = ctk.CTkLabel(
            preview_frame,
            text="Title...",
            anchor="w",
            font=ctk.CTkFont(weight="bold")
        )
        self.title_label.grid(row=0, column=1, padx=10, pady=(10, 0), sticky="ew")
        
        # Uploader display
        self.uploader_label = ctk.CTkLabel(
            preview_frame,
            text="Uploader...",
            anchor="w"
        )
        self.uploader_label.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="new")
    
    def _create_download_button(self, parent) -> None:
        """Create main download button."""
        self.download_now_button = ctk.CTkButton(
            parent,
            text="Download",
            command=self._handle_download_action,
            height=40
        )
        self.download_now_button.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
    
    def _create_progress_bar(self, parent) -> None:
        """Create progress bar for download status."""
        self.progress_bar = ctk.CTkProgressBar(parent)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")
    
    def _create_download_options(self, parent) -> None:
        """Create download options (format, quality, mode selection)."""
        options_frame = ctk.CTkFrame(parent)
        options_frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        
        # Mode selection (Audio/Video)
        self.mode_segmented_button = ctk.CTkSegmentedButton(
            options_frame,
            values=["Audio", "Video"],
            command=self._on_mode_change
        )
        self.mode_segmented_button.pack(side="left", padx=10, pady=10)
        
        # Audio format options
        self._create_audio_options(options_frame)
        
        # Video format options
        self._create_video_options(options_frame)
    
    def _create_audio_options(self, parent) -> None:
        """Create audio-specific download options."""
        self.audio_options_frame = ctk.CTkFrame(parent)
        
        ctk.CTkLabel(self.audio_options_frame, text="Audio Format:").pack(
            side="left", padx=(10, 5)
        )
        
        self.audio_format_menu = ctk.CTkOptionMenu(
            self.audio_options_frame,
            values=AUDIO_FORMATS,
            command=self._on_format_change
        )
        self.audio_format_menu.pack(side="left", padx=(0, 10))
    
    def _create_video_options(self, parent) -> None:
        """Create video-specific download options."""
        self.video_options_frame = ctk.CTkFrame(parent)
        
        # Video format selection
        ctk.CTkLabel(self.video_options_frame, text="Video Format:").pack(
            side="left", padx=(10, 5)
        )
        
        self.video_format_menu = ctk.CTkOptionMenu(
            self.video_options_frame,
            values=VIDEO_FORMATS,
            command=self._on_format_change
        )
        self.video_format_menu.pack(side="left", padx=(0, 10))
        
        # Resolution selection
        ctk.CTkLabel(self.video_options_frame, text="Resolution:").pack(
            side="left", padx=(10, 5)
        )
        
        self.resolution_menu = ctk.CTkOptionMenu(
            self.video_options_frame,
            values=VIDEO_RESOLUTIONS,
            command=self._on_resolution_change
        )
        self.resolution_menu.pack(side="left", padx=(0, 10))
    
    def _create_path_selection(self, parent) -> None:
        """Create save path selection interface."""
        path_frame = ctk.CTkFrame(parent)
        path_frame.grid(row=5, column=0, padx=10, pady=10, sticky="ew")
        path_frame.grid_columnconfigure(0, weight=1)
        
        # Display current save path (truncated if too long)
        current_path = self.settings['save_path']
        if len(current_path) <= 60:
            path_display = current_path
        else:
            path_display = f"...{current_path[-57:]}"
        
        self.path_label = ctk.CTkLabel(
            path_frame,
            text=f"Save To: {path_display}",
            anchor="w"
        )
        self.path_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # Browse button
        browse_button = ctk.CTkButton(
            path_frame,
            text="Browse...",
            command=self._select_save_path
        )
        browse_button.grid(row=0, column=1, padx=10, pady=10)
    
    def _create_status_section(self, parent) -> None:
        """Create status display and folder open button."""
        status_frame = ctk.CTkFrame(parent)
        status_frame.grid(row=6, column=0, padx=10, pady=20, sticky="sew")
        parent.grid_rowconfigure(6, weight=1)
        status_frame.grid_columnconfigure(0, weight=1)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready",
            anchor="w"
        )
        self.status_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        
        # Open folder button (initially hidden)
        self.open_folder_button = ctk.CTkButton(
            status_frame,
            text="Open Download Folder",
            command=lambda: self._open_folder(self.last_download_path)
        )
    
    def _create_history_tab(self) -> None:
        """Create download history tab."""
        history_tab = self.tab_view.add("History")
        history_tab.grid_columnconfigure(0, weight=1)
        history_tab.grid_rowconfigure(1, weight=1)
        
        # History header with clear button
        history_top_frame = ctk.CTkFrame(history_tab)
        history_top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        history_top_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            history_top_frame,
            text="Download History",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, sticky="w")
        
        ctk.CTkButton(
            history_top_frame,
            text="Clear History",
            command=self._clear_download_history
        ).grid(row=0, column=1, sticky="e")
        
        # Scrollable history list
        self.history_scroll_frame = ctk.CTkScrollableFrame(history_tab)
        self.history_scroll_frame.grid(
            row=1, column=0, padx=10, pady=(0, 10), sticky="nsew"
        )
    
    def _create_settings_tab(self) -> None:
        """Create application settings tab."""
        settings_tab = self.tab_view.add("Settings")
        settings_tab.grid_columnconfigure(0, weight=1)
        
        # Appearance mode setting
        self._create_appearance_setting(settings_tab)
        
        # Cookie browser setting
        self._create_cookie_setting(settings_tab)
        
        # Playlist limit setting
        self._create_playlist_setting(settings_tab)
        
        # Filename format setting
        self._create_filename_setting(settings_tab)
    
    def _create_appearance_setting(self, parent) -> None:
        """Create appearance mode selection."""
        appearance_frame = ctk.CTkFrame(parent)
        appearance_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(appearance_frame, text="Appearance Mode:").pack(
            side="left", padx=10, pady=10
        )
        
        appearance_menu = ctk.CTkOptionMenu(
            appearance_frame,
            values=['System', 'Light', 'Dark'],
            command=self._on_appearance_change
        )
        appearance_menu.pack(side="left", padx=10, pady=10)
    
    def _create_cookie_setting(self, parent) -> None:
        """Create browser cookie selection."""
        cookie_frame = ctk.CTkFrame(parent)
        cookie_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(cookie_frame, text="Use Login Cookies From:").pack(
            side="left", padx=10, pady=10
        )
        
        cookie_menu = ctk.CTkOptionMenu(
            cookie_frame,
            values=[browser.capitalize() for browser in SUPPORTED_BROWSERS],
            command=self._on_cookie_browser_change
        )
        cookie_menu.pack(side="left", padx=10, pady=10)
    
    def _create_playlist_setting(self, parent) -> None:
        """Create playlist limit setting."""
        playlist_frame = ctk.CTkFrame(parent)
        playlist_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(
            playlist_frame,
            text="Playlist items to fetch ('all' for no limit):"
        ).pack(side="left", padx=10, pady=10)
        
        self.playlist_limit_entry = ctk.CTkEntry(playlist_frame, width=60)
        self.playlist_limit_entry.pack(side="left", padx=10, pady=10)
        self.playlist_limit_entry.bind("<KeyRelease>", self._on_playlist_limit_change)
    
    def _create_filename_setting(self, parent) -> None:
        """Create filename format setting."""
        filename_frame = ctk.CTkFrame(parent)
        filename_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        filename_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(filename_frame, text="Filename Format:").grid(
            row=0, column=0, padx=10, pady=10
        )
        
        self.filename_menu = ctk.CTkOptionMenu(
            filename_frame,
            values=list(FILENAME_PRESETS.keys()),
            command=self._on_filename_preset_change
        )
        self.filename_menu.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        # Custom filename entry (initially hidden)
        self.filename_entry = ctk.CTkEntry(filename_frame)
        self.filename_entry.bind("<KeyRelease>", self._on_filename_template_change)
    
    def _create_about_tab(self) -> None:
        """Create about/information tab."""
        about_tab = self.tab_view.add("About")
        about_tab.grid_columnconfigure(0, weight=1)
        about_tab.grid_rowconfigure(0, weight=1)
        
        # Scrollable about frame
        about_frame = ctk.CTkScrollableFrame(about_tab)
        about_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        
        # Application title
        lines = ABOUT_TEXT.strip().split('\n')
        title_text = f"{lines[0]}"
        ctk.CTkLabel(
            about_frame,
            text=title_text,
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(10, 5), padx=10, anchor="w")
        
        # Application description
        description_text = "\n".join(lines[1:])
        ctk.CTkLabel(
            about_frame,
            text=description_text,
            wraplength=600,
            justify="left"
        ).pack(pady=5, padx=10, anchor="w", fill="x")
    
    def _apply_current_settings(self) -> None:
        """Apply current settings to UI elements."""
        # Set mode
        self.mode_segmented_button.set(self.settings['mode'].capitalize())
        self._on_mode_change(self.settings['mode'])
        
        # Set formats
        self.audio_format_menu.set(self.settings['audio_format'])
        self.video_format_menu.set(self.settings['video_format'])
        self.resolution_menu.set(self.settings['video_quality'])
        
        # Set playlist limit
        self.playlist_limit_entry.insert(0, self.settings['playlist_limit'])
        
        # Set filename preset
        self.filename_menu.set(self.settings['filename_preset'])
        self.filename_entry.insert(0, self.settings['filename_template_custom'])
        self._on_filename_preset_change(self.settings['filename_preset'])
    
    # =====================================================
    # SETTINGS MANAGEMENT METHODS
    # =====================================================
    
    def save_settings(self) -> None:
        """Save current settings to configuration file."""
        # Limit history to last 20 items
        self.settings['history'] = self.settings['history'][-20:]
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except IOError as e:
            self.update_status(f"Failed to save settings: {e}")
    
    # =====================================================
    # EVENT HANDLERS
    # =====================================================
    
    def _on_mode_change(self, new_mode: str) -> None:
        """Handle download mode change (Audio/Video)."""
        self.settings['mode'] = new_mode.lower()
        self.save_settings()
        
        # Show/hide appropriate options
        if self.settings['mode'] == 'video':
            self.audio_options_frame.pack_forget()
            self.video_options_frame.pack(side="left", padx=10, pady=10)
        else:
            self.video_options_frame.pack_forget()
            self.audio_options_frame.pack(side="left", padx=10, pady=10)
        
        self.update_status(f"Mode set to {new_mode}")
    
    def _on_format_change(self, new_format: str) -> None:
        """Handle format selection change."""
        if self.settings['mode'] == 'video':
            self.settings['video_format'] = new_format
            format_type = "video"
        else:
            self.settings['audio_format'] = new_format
            format_type = "audio"
        
        self.save_settings()
        self.update_status(f"Default {format_type} format set to {new_format.upper()}")
    
    def _on_resolution_change(self, new_resolution: str) -> None:
        """Handle video resolution change."""
        self.settings['video_quality'] = new_resolution
        self.save_settings()
        self.update_status(f"Default resolution set to {new_resolution}")
    
    def _on_playlist_limit_change(self, event=None) -> None:
        """Handle playlist limit setting change."""
        value = self.playlist_limit_entry.get().lower()
        
        if value.isdigit() or value == "all":
            self.settings['playlist_limit'] = value
            self.save_settings()
            self.update_status(f"Playlist fetch limit set to {value}")
    
    def _on_filename_preset_change(self, new_preset: str) -> None:
        """Handle filename preset change."""
        self.settings['filename_preset'] = new_preset
        self.save_settings()
        
        # Show/hide custom entry field
        if new_preset == "Custom...":
            self.filename_entry.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="ew")
        else:
            self.filename_entry.grid_forget()
        
        self.update_status(f"Filename format set to: {new_preset}")
    
    def _on_filename_template_change(self, event=None) -> None:
        """Handle custom filename template change."""
        self.settings['filename_template_custom'] = self.filename_entry.get()
        self.save_settings()
    
    def _on_appearance_change(self, new_mode: str) -> None:
        """Handle appearance mode change."""
        self.settings['appearance_mode'] = new_mode
        ctk.set_appearance_mode(new_mode)
        self.save_settings()
    
    def _on_cookie_browser_change(self, new_browser: str) -> None:
        """Handle cookie browser selection change."""
        self.settings['cookie_browser'] = new_browser.lower()
        self.save_settings()
        self.update_status(f"Using cookies from: {new_browser}")
    
    # =====================================================
    # FILE AND FOLDER OPERATIONS
    # =====================================================
    
    def _select_save_path(self) -> None:
        """Open folder selection dialog for download location."""
        new_path = filedialog.askdirectory(initialdir=self.settings['save_path'])
        
        if new_path:
            self.settings['save_path'] = new_path
            self.save_settings()
            
            # Update path display (truncate if too long)
            if len(new_path) <= 60:
                path_display = new_path
            else:
                path_display = f"...{new_path[-57:]}"
            
            self.path_label.configure(text=f"Save To: {path_display}")
            self.update_status("Save location updated")
    
    def _open_file(self, file_path: Optional[str]) -> None:
        """Open a file in the default system application."""
        if file_path and os.path.exists(file_path):
            self._open_folder(os.path.dirname(file_path))
        else:
            self.update_status(f"File not found: {file_path}")
    
    def _open_folder(self, folder_path: Optional[str]) -> None:
        """Open a folder in the system file manager."""
        if not folder_path:
            return
        
        try:
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", folder_path])
            else:
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            self.update_status(f"Error opening folder: {e}")
    
    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to system clipboard."""
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_status("URL copied to clipboard!")
    
    # =====================================================
    # DOWNLOAD HISTORY MANAGEMENT
    # =====================================================
    
    def _clear_download_history(self) -> None:
        """Clear all download history after confirmation."""
        # Import messagebox here to avoid issues with main imports
        import tkinter.messagebox as messagebox
        
        if messagebox.askyesno(
            "Confirm Clear History",
            "Are you sure you want to permanently delete all download history?"
        ):
            self.settings['history'].clear()
            self.save_settings()
            self._populate_history_display()
            self.update_status("History cleared.")
    
    def _populate_history_display(self) -> None:
        """Populate the history tab with download history items."""
        # Clear existing history items
        for widget in self.history_scroll_frame.winfo_children():
            widget.destroy()
        
        if not self.settings['history']:
            # Show empty state
            empty_label = ctk.CTkLabel(
                self.history_scroll_frame,
                text="No downloads yet."
            )
            empty_label.pack(pady=20)
            return
        
        # Create history item for each download
        for item in self.settings['history']:
            self._create_history_item(item)
    
    def _create_history_item(self, item: Dict[str, Any]) -> None:
        """
        Create a single history item widget.
        
        Args:
            item: Dictionary containing download information
        """
        # Create frame for this history item
        item_frame = ctk.CTkFrame(self.history_scroll_frame)
        item_frame.pack(fill="x", padx=5, pady=5)
        item_frame.grid_columnconfigure(0, weight=1)
        
        # Item title
        title = item.get('title', 'Unknown')
        title_label = ctk.CTkLabel(item_frame, text=title, anchor="w")
        title_label.grid(row=0, column=0, padx=10, sticky="ew")
        
        # Open file button
        open_button = ctk.CTkButton(
            item_frame,
            text="Open",
            width=80,
            command=lambda path=item.get('file_path'): self._open_file(path)
        )
        open_button.grid(row=0, column=1, padx=5)
        
        # Copy URL button
        copy_button = ctk.CTkButton(
            item_frame,
            text="Copy URL",
            width=100,
            command=lambda url=item.get('url'): self._copy_to_clipboard(url)
        )
        copy_button.grid(row=0, column=2, padx=5)
    
    # =====================================================
    # DOWNLOAD OPERATIONS
    # =====================================================
    
    def _handle_download_action(self) -> None:
        """Handle the main download button click."""
        url = self.url_entry.get().strip()
        
        if not url or not url.startswith("http"):
            self.update_status("Please enter a valid URL.")
            return
        
        # Check if this is a playlist URL
        if "list=" in url or "/playlist?" in url:
            # Open playlist selection window
            PlaylistSelectionWindow(self, url)
        else:
            # Single video/audio download
            download_thread = threading.Thread(
                target=self.download_batch,
                args=([url],),
                daemon=True
            )
            download_thread.start()
    
    def download_batch(self, urls: List[str]) -> None:
        """
        Download multiple URLs in sequence.
        
        Args:
            urls: List of URLs to download
        """
        for url in urls:
            # Prepare download job
            job = {
                'url': url,
                'format': (self.settings['video_format'] 
                          if self.settings['mode'] == 'video' 
                          else self.settings['audio_format']),
                'mode': self.settings['mode'],
                'quality': self.settings['video_quality']
            }
            
            # Execute download
            self._download_content(job)
            
            # Small delay between downloads to prevent overwhelming the server
            time.sleep(1)
    
    def _download_content(self, job: Dict[str, Any]) -> None:
        """
        Download content based on job specification.
        
        Args:
            job: Dictionary containing download parameters
        """
        success = False
        
        try:
            # Update UI to show download in progress
            self.after(0, self._set_download_in_progress)
            
            # Create output directory
            subfolder = "Audio" if job['mode'] == 'audio' else "Video"
            output_dir = os.path.join(self.settings['save_path'], subfolder)
            os.makedirs(output_dir, exist_ok=True)
            
            # Store for folder opening later
            self.last_download_path = output_dir
            
            # Build yt-dlp options
            ydl_options = self._build_ydl_options(output_dir, job)
            
            # Perform download
            with yt_dlp.YoutubeDL(ydl_options) as ydl:
                # First, extract info without downloading
                info = ydl.extract_info(job['url'], download=False, process=False)
                
                # Then perform the actual download
                success = ydl.download([job['url']]) == 0
            
            if success:
                # Build expected output path
                expected_path = os.path.join(output_dir, ydl.prepare_filename(info))
                file_extension = f".{job['format']}"
                final_path = expected_path.rsplit('.', 1)[0] + file_extension
                
                # Add to download history
                history_item = {
                    'title': info.get('title', 'Unknown'),
                    'url': job['url'],
                    'file_path': final_path
                }
                self.settings['history'].insert(0, history_item)
                self.save_settings()
                
                # Update status
                title_truncated = info.get('title', '')[:40]
                self.update_status(f"✓ Download Successful: {title_truncated}")
            else:
                url_truncated = job['url'][:50]
                self.update_status(f"Finished with errors: {url_truncated}")
        
        except DownloadError as e:
            error_msg = "✗ Download Error: Check URL or update yt-dlp"
            self.after(0, self.update_status, error_msg)
        
        except Exception as e:
            error_msg = f"✗ An unexpected error occurred: {str(e)}"
            self.after(0, self.update_status, error_msg)
        
        finally:
            # Reset UI state
            self.after(0, self._on_download_finished, success)
    
    def _build_ydl_options(self, output_dir: str, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build yt-dlp options dictionary based on job parameters.
        
        Args:
            output_dir: Directory to save downloads
            job: Job specification dictionary
            
        Returns:
            Dictionary of yt-dlp options
        """
        # Determine filename template
        if self.settings['filename_preset'] != 'Custom...':
            template = FILENAME_PRESETS.get(self.settings['filename_preset'])
        else:
            template = self.settings['filename_template_custom']
        
        # Base options
        options = {
            'ignoreerrors': True,
            'outtmpl': os.path.join(output_dir, f"{template}.%(ext)s"),
            'progress_hooks': [self._progress_hook],
            'noprogress': True,
            'ffmpeg_location': self.ffmpeg_path
        }
        
        # Add browser cookies if specified
        if self.settings['cookie_browser'] != 'none':
            options['cookiesfrombrowser'] = (self.settings['cookie_browser'], None)
        
        # Configure format-specific options
        if job['mode'] == 'audio':
            options.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': job['format']
                }]
            })
        else:
            # Video mode
            quality_number = job['quality'].replace('p', '')
            format_selector = f"bestvideo[height<={quality_number}]+bestaudio/best"
            
            options.update({
                'format': format_selector,
                'merge_output_format': job['format']
            })
        
        return options
    
    def _set_download_in_progress(self) -> None:
        """Update UI to show download in progress."""
        self.download_now_button.configure(state="disabled", text="Downloading...")
        self.open_folder_button.grid_forget()
    
    def _on_download_finished(self, success: bool) -> None:
        """
        Handle download completion.
        
        Args:
            success: Whether the download was successful
        """
        # Reset download button
        self.download_now_button.configure(state="normal", text="Download")
        self.progress_bar.set(0)
        
        if success:
            # Refresh history display
            self._populate_history_display()
            
            # Show folder open button
            self.open_folder_button.grid(
                row=0, column=0, columnspan=2,
                padx=10, pady=(10, 5), sticky="ew"
            )
    
    # =====================================================
    # PREVIEW AND METADATA OPERATIONS
    # =====================================================
    
    def _trigger_preview_update(self, event=None) -> None:
        """Trigger preview update when URL changes."""
        # Stop existing preview thread if running
        if self.preview_thread and self.preview_thread.is_alive():
            self.preview_thread_stop_event.set()
        
        url = self.url_entry.get().strip()
        
        if url and url.startswith("http"):
            # Start new preview thread
            self.preview_thread_stop_event.clear()
            self.preview_thread = threading.Thread(
                target=self._update_preview_thread,
                args=(url, self.preview_thread_stop_event.is_set),
                daemon=True
            )
            self.preview_thread.start()
    
    def _update_preview_thread(self, url: str, stop_check: Callable[[], bool]) -> None:
        """
        Update preview information in background thread.
        
        Args:
            url: URL to fetch preview for
            stop_check: Function to check if thread should stop
        """
        # Show loading state
        self.after(0, self._set_preview_data, "loading", None)
        
        # Fetch metadata
        info = self._fetch_metadata(url, stop_check)
        thumbnail_image = None
        
        # Stop if thread was cancelled
        if stop_check() or not info:
            self.after(0, self._set_preview_data, None, None)
            return
        
        # Fetch thumbnail if available
        thumbnail_url = info.get('thumbnail_url')
        if thumbnail_url:
            try:
                response = requests.get(thumbnail_url, timeout=10)
                response.raise_for_status()
                
                if not stop_check():
                    # Create thumbnail image
                    thumbnail_image = ctk.CTkImage(
                        light_image=Image.open(BytesIO(response.content)),
                        size=(160, 90)
                    )
            except requests.RequestException:
                # Thumbnail fetch failed, continue without it
                pass
        
        # Update UI if thread wasn't cancelled
        if not stop_check():
            self.after(0, self._set_preview_data, info, thumbnail_image)
    
    def _set_preview_data(self, info: Any, image: Optional[Any]) -> None:
        """
        Update preview display with fetched data.
        
        Args:
            info: Video/audio information or "loading" string
            image: Thumbnail image or None
        """
        if info == "loading":
            # Show loading state
            self.title_label.configure(text="Fetching...")
            self.uploader_label.configure(text="")
            self.thumbnail_label.configure(image=None, text="")
        elif info:
            # Show fetched information
            self.title_label.configure(text=info['title'])
            self.uploader_label.configure(text=info['uploader'])
            self.thumbnail_label.configure(image=image, text="")
        else:
            # Show error state
            self.title_label.configure(text="Invalid URL or video not found")
            self.uploader_label.configure(text="")
            self.thumbnail_label.configure(image=None, text="")
    
    def _fetch_metadata(self, url: str, stop_check: Callable[[], bool]) -> Optional[Dict[str, str]]:
        """
        Fetch metadata for a given URL.
        
        Args:
            url: URL to fetch metadata for
            stop_check: Function to check if operation should be cancelled
            
        Returns:
            Dictionary with title, uploader, and thumbnail_url, or None if failed
        """
        try:
            ydl_options = {
                'quiet': True,
                'extract_flat': 'in_playlist',
                'forcejson': True
            }
            
            with yt_dlp.YoutubeDL(ydl_options) as ydl:
                info = ydl.extract_info(url, download=False)
            
            # Check if operation was cancelled
            if stop_check():
                return None
            
            return {
                'title': info.get('title', 'No Title'),
                'uploader': info.get('uploader', 'N/A'),
                'thumbnail_url': info.get('thumbnail')
            }
            
        except Exception:
            return None
    
    # =====================================================
    # PROGRESS AND STATUS MANAGEMENT
    # =====================================================
    
    def _progress_hook(self, progress_data: Dict[str, Any]) -> None:
        """
        Handle download progress updates from yt-dlp.
        
        Args:
            progress_data: Progress information from yt-dlp
        """
        if progress_data['status'] == 'downloading':
            # Calculate progress percentage
            total_bytes = (progress_data.get('total_bytes') or 
                          progress_data.get('total_bytes_estimate', 0))
            
            if total_bytes > 0:
                downloaded = progress_data['downloaded_bytes']
                progress_percent = downloaded / total_bytes
                
                # Format status information
                percent_str = progress_data.get('_percent_str', '0.0%').strip()
                
                speed = progress_data.get('speed')
                if speed:
                    speed_str = f"{speed / 1024**2:.2f} MB/s"
                else:
                    speed_str = "..."
                
                eta_seconds = progress_data.get('eta')
                eta_str = self._format_time(eta_seconds)
                
                status_text = f"Downloading... {percent_str}  |  {speed_str}  |  ETA: {eta_str}"
                
                # Update UI on main thread
                self.after(0, self._update_progress_display, progress_percent, status_text)
        
        elif progress_data['status'] == 'finished':
            # Download finished, now processing
            self.after(0, self._update_progress_display, 1.0, "Processing...")
    
    @staticmethod
    def _format_time(seconds: Optional[float]) -> str:
        """
        Format time in seconds to MM:SS format.
        
        Args:
            seconds: Time in seconds, or None
            
        Returns:
            Formatted time string
        """
        if seconds is None:
            return "??:??"
        
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def _update_progress_display(self, progress: float, status_text: str) -> None:
        """
        Update progress bar and status text.
        
        Args:
            progress: Progress value between 0.0 and 1.0
            status_text: Status text to display
        """
        self.progress_bar.set(progress)
        self.status_label.configure(text=status_text)
    
    def update_status(self, status_text: str) -> None:
        """
        Update status label text.
        
        Args:
            status_text: Text to display in status label
        """
        self.status_label.configure(text=status_text)
    
    # =====================================================
    # APPLICATION LIFECYCLE
    # =====================================================
    
    def on_closing(self) -> None:
        """Handle application closing."""
        # Stop any running preview threads
        if self.preview_thread and self.preview_thread.is_alive():
            self.preview_thread_stop_event.set()
        
        # Save settings before closing
        self.save_settings()
        
        # Destroy the application
        self.destroy()


# =====================================================
# FFMPEG SETUP AND MAIN ENTRY POINT
# =====================================================

def setup_ffmpeg() -> Optional[str]:
    """
    Setup FFmpeg for the application.
    
    This function attempts to find FFmpeg in various locations and can
    optionally download it if not found.
    
    Returns:
        Path to FFmpeg executable, or None if not found
    """
    # First, try to find FFmpeg in system PATH
    ffmpeg_path = shutil.which("ffmpeg")
    
    if ffmpeg_path:
        print(f"Found FFmpeg in system PATH: {ffmpeg_path}")
        return ffmpeg_path
    
    # Check if moviepy has FFmpeg configured
    if FFMPEG_BINARY and os.path.exists(FFMPEG_BINARY):
        print(f"Using FFmpeg from moviepy: {FFMPEG_BINARY}")
        return FFMPEG_BINARY
    
    # Attempt automatic download via imageio
    print("FFmpeg not found. Attempting automatic download via imageio...")
    
    try:
        from imageio.plugins.ffmpeg import download
        download()
        
        # Try to find FFmpeg again after download
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path and FFMPEG_BINARY and os.path.exists(FFMPEG_BINARY):
            ffmpeg_path = FFMPEG_BINARY
        
        if ffmpeg_path:
            print("FFmpeg downloaded and configured successfully.")
            return ffmpeg_path
        
    except Exception as e:
        print(f"Automatic FFmpeg download failed: {e}")
    
    return None


def show_ffmpeg_error() -> None:
    """Show error dialog when FFmpeg is not available."""
    import tkinter
    from tkinter import messagebox
    
    root = tkinter.Tk()
    root.withdraw()
    
    error_message = (
        "FFmpeg could not be found or downloaded.\n\n"
        "FFmpeg is required for audio/video processing.\n"
        "Please install FFmpeg manually and ensure it's in your system's PATH.\n\n"
        "The application will now close."
    )
    
    messagebox.showerror("Critical Dependency Missing", error_message)
    root.destroy()


def main() -> None:
    """Main application entry point."""
    print("TuneCatcher v1.9 - Starting application...")
    
    # Setup FFmpeg
    ffmpeg_path = setup_ffmpeg()
    
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        print(f"Using FFmpeg: {ffmpeg_path}")
        
        # Create and run the application
        app = TuneCatcher(ffmpeg_path)
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        
        print("Application initialized successfully. Starting GUI...")
        app.mainloop()
        
    else:
        print("ERROR: FFmpeg not available. Cannot start application.")
        show_ffmpeg_error()


if __name__ == "__main__":
    main()
