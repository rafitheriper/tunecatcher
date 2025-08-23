import os
import sys
import time
from colorama import init, Fore, Style
import yt_dlp
from moviepy.config import FFMPEG_BINARY

# Initialize colorama here, as it's used by top-level functions
init(autoreset=True)

# --- Constants ---
SAVE_FOLDER = "Downloads"
VIDEO_QUALITIES = ['1080p', '720p', '480p', '360p']
ASCII_ART = r"""
$$$$$$$$\                             $$$$$$\             $$\               $$\                           
\__$$  __|                           $$  __$$\            $$ |              $$ |                          
   $$ |$$\   $$\ $$$$$$$\   $$$$$$\  $$ /  \__| $$$$$$\ $$$$$$\    $$$$$$$\ $$$$$$$\   $$$$$$\   $$$$$$\  
   $$ |$$ |  $$ |$$  __$$\ $$  __$$\ $$ |       \____$$\\_$$  _|  $$  _____|$$  __$$\ $$  __$$\ $$  __$$\ 
   $$ |$$ |  $$ |$$ |  $$ |$$$$$$$$ |$$ |       $$$$$$$ | $$ |    $$ /      $$ |  $$ |$$$$$$$$ |$$ |  \__|
   $$ |$$ |  $$ |$$ |  $$ |$$   ____|$$ |  $$\ $$  __$$ | $$ |$$\ $$ |      $$ |  $$ |$$   ____|$$ |      
   $$ |\$$$$$$  |$$ |  $$ |\$$$$$$$\ \$$$$$$  |\$$$$$$$ | \$$$$  |\$$$$$$$\ $$ |  $$ |\$$$$$$$\ $$ |      
   \__| \______/ \__|  \__| \_______| \______/  \_______|  \____/  \_______|\__|  \__| \_______|\__|      
"""

def main():
    """
    Main function to run the TuneCatcher application.
    Initializes the app, checks for dependencies, and starts the main loop.
    """
    # Create an instance of our application class
    app = TuneCatcher()
    app.run()

# =============================================================================
# || CS50P Required Custom Functions (for testing)                         ||
# =============================================================================

def toggle_mode(current_mode):
    """
    Switches the download mode between 'audio' and 'video'.
    This is a pure function, easy to test.
    """
    if current_mode == 'audio':
        return 'video'
    else:
        return 'audio'

def validate_quality_choice(choice, qualities):
    """
    Validates if the user's choice for video quality is valid.
    Returns the chosen quality string if valid, otherwise None.
    """
    if choice.isdigit():
        index = int(choice) - 1
        if 0 <= index < len(qualities):
            return qualities[index]
    return None

def build_ydl_options(mode, video_quality, ffmpeg_path, output_dir):
    """
    Constructs the core options dictionary for yt-dlp based on settings.
    This function contains the main logic for configuring the downloader.
    """
    # Base options required for all downloads
    options = {
        'ignoreerrors': True,
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'ffmpeg_location': ffmpeg_path,
    }

    if mode == 'audio':
        options.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'}],
        })
    else:  # Video mode
        quality_res = video_quality.replace('p', '')
        options.update({
            'format': f'bestvideo[height<={quality_res}]+bestaudio/best',
            'merge_output_format': 'mkv',
        })
    
    return options

# =============================================================================
# || Main Application Class                                                ||
# =============================================================================

class TuneCatcher:
    """Encapsulates the application state and main loop."""
    def __init__(self):
        self.base_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
        self.mode = 'audio'
        self.video_quality = '1080p'
        self.playlist_count = '10'
        self.ffmpeg_path = None

    def run(self):
        """Initializes FFmpeg and starts the main interactive loop."""
        try:
            print(f"{Fore.YELLOW}Initializing... Checking for FFmpeg.")
            self.ffmpeg_path = FFMPEG_BINARY
            if not self.ffmpeg_path:
                raise RuntimeError("Moviepy could not find or automatically download FFmpeg.")
            print(f"{Fore.GREEN}FFmpeg is ready.")
            time.sleep(1)
        except Exception as e:
            print(f"\n{Fore.RED}{Style.BRIGHT}CRITICAL ERROR: {e}")
            input("Press Enter to exit...")
            return

        while True:
            self._display_header()
            user_input = input(f"{Fore.CYAN}Paste URL or command:\n> ").strip()

            if user_input.lower() in ['exit', 'q', 'quit']:
                print(f"{Fore.CYAN}Goodbye!")
                break
            elif user_input.isdigit():
                self._handle_command(user_input)
            elif user_input.startswith('http'):
                self._download_content(user_input)
                input(f"\n{Fore.WHITE}Press Enter to continue...")
            else:
                print(f"\n{Fore.RED}Invalid input.")
                time.sleep(1)

    def _display_header(self):
        """Clears the screen and shows the current settings."""
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Fore.CYAN}{Style.BRIGHT}{ASCII_ART}")
        
        mode_display = "M4A Audio" if self.mode == 'audio' else "MKV Video"
        quality_info = "High Quality" if self.mode == 'audio' else f"Max: {self.video_quality}"
        
        print(f"{Fore.WHITE}Mode: {Fore.GREEN}{mode_display} {Style.DIM}| {Fore.GREEN}{quality_info}")
        print(f"{Fore.WHITE}Output: {Fore.GREEN}{SAVE_FOLDER} {Style.DIM}| Playlist: {Fore.GREEN}{self.playlist_count}")
        print(f"{Style.DIM}{'=' * 80}")
        print(f"{Fore.YELLOW}[1] Toggle Mode [2] Video Quality [3] Playlist Count")

    def _handle_command(self, command):
        """Processes user commands to change settings."""
        if command == '1':
            # Use the testable, standalone function
            self.mode = toggle_mode(self.mode)
            print(f"{Fore.GREEN}>> Mode: {self.mode.upper()}")
        elif command == '2':
            self._change_video_quality()
        elif command == '3':
            self._change_playlist_count()
        else:
            print(f"{Fore.RED}Invalid command.")
        time.sleep(1)

    def _change_video_quality(self):
        """Prompts user to change the video quality setting."""
        print(f"\n{Fore.CYAN}Video Quality:")
        for i, q in enumerate(VIDEO_QUALITIES, 1):
            print(f"  [{i}] {q}")
        choice = input(f"{Fore.YELLOW}> ").strip()
        # Use the testable, standalone function
        validated_quality = validate_quality_choice(choice, VIDEO_QUALITIES)
        if validated_quality:
            self.video_quality = validated_quality
            print(f"{Fore.GREEN}>> Set to {self.video_quality}")
        else:
            print(f"{Fore.RED}Invalid choice.")

    def _change_playlist_count(self):
        """Prompts user to change the playlist count setting."""
        count = input(f"\n{Fore.CYAN}Playlist items ('5' or 'all'): ").strip().lower()
        if (count.isdigit() and int(count) > 0) or count == 'all':
            self.playlist_count = count
            print(f"{Fore.GREEN}>> Set to {count}")
        else:
            print(f"{Fore.RED}Invalid input.")

    def _download_content(self, url):
        """Handles the entire download process for a given URL."""
        print(f"\n{'=' * 15} DOWNLOAD {'=' * 15}")
        base_output_dir = os.path.join(self.base_dir, SAVE_FOLDER)
        os.makedirs(base_output_dir, exist_ok=True)
        subfolder = "Audio" if self.mode == 'audio' else "Video"
        output_dir = os.path.join(base_output_dir, subfolder)
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # Use the testable, standalone function to get the base options
            options = build_ydl_options(self.mode, self.video_quality, self.ffmpeg_path, output_dir)
            
            # Add other options that are harder to test (involve user input/state)
            if "list=" in url:
                options.update(self._get_playlist_options())

            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])
                print(f"\n{Fore.GREEN}{Style.BRIGHT}✓ Complete! Files in: {output_dir}")
                
        except Exception as e:
            print(f"\n{Fore.RED}{Style.BRIGHT}✗ Error: {str(e)}")

    def _get_playlist_options(self):
        """Gets user input for playlist download range."""
        print(f"\n{Fore.YELLOW}Playlist detected.")
        choice = input(f"Items to download (default {self.playlist_count}): ").strip().lower() or self.playlist_count
        
        if choice == 'all':
            print(f"{Fore.CYAN}>> Downloading all items")
            return {}
        else:
            final_count = choice if choice.isdigit() and int(choice) > 0 else self.playlist_count
            print(f"{Fore.CYAN}>> Downloading first {final_count} items")
            return {'playlist_items': f"1-{final_count}"}

if __name__ == "__main__":
    main()