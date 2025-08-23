# TuneCatcher - A CS50P Final Project

#### Video Demo:  <https://youtu.be/ZkCMgWbOu40?si=Oss7U0nKH8lD2MDc>

## Description

TuneCatcher is a robust and user-friendly command-line application for downloading high-quality audio and video content from YouTube. Developed as a final project for Harvard's CS50P, it is built entirely in Python and leverages industry-standard libraries to provide a reliable, efficient, and ad-free experience, bypassing the need for untrustworthy online converters.

The application operates in two distinct modes: a high-quality audio downloader saving to the modern **M4A (AAC)** format, and a high-definition video downloader that preserves the original, untouched quality by saving to the flexible **MKV** container. It features a clean, interactive interface that allows users to seamlessly switch between modes, select quality preferences, and handle entire playlists with ease. The project's core design philosophy is to combine powerful, reliable backend functionality with a simple and intuitive user experience.

---

## Features

*   **Reliable Core:** Powered by the `yt-dlp` library, which is updated almost daily to ensure compatibility with YouTube's latest changes and avoid the common `HTTP 400` errors that plague other downloaders.
*   **Automatic Dependency Management:** Uniquely uses the `moviepy` library to automatically download and manage the essential **FFmpeg** dependency. This provides a seamless "library-only" setup experience for the user, removing the significant hurdle of manual installation.
*   **Dual-Mode Operation:** Instantly toggle between downloading high-quality **M4A Audio** or high-definition **MKV Video** with a single command.
*   **Full Playlist Support:** The script intelligently detects playlist URLs and allows the user to download a specific number of items or the entire list.
*   **Quality Selection:** Users can set their preferred maximum video quality (from 360p up to 1080p).
*   **Automatic File Organization:** Downloaded files are automatically sorted into `Downloads/Audio` and `Downloads/Video` subfolders to keep your media library tidy.
*   **Custom ASCII Art Banner:** Features a unique and professional-looking startup screen to give the application a distinct identity.
*   **Interactive Command Menu:** A clean, colorful, and easy-to-use interface for changing settings on the fly without restarting the program.

---

## Installation and Usage

### Prerequisites
*   Python 3.8 or newer.

### Setup
1.  **Clone the Repository:**
    ```bash
    git clone <your-github-repository-url>
    cd tunecatcher
    ```

2.  **Set up a Virtual Environment (Recommended):**
    ```bash
    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    py -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    All required libraries are listed in `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```

### Running the Application
1.  Execute the main script from the project's root directory:
    ```bash
    python project.py
    ```
2.  **First-Run Note:** The `moviepy` library may automatically download a copy of FFmpeg if it is not found on your system. This is expected behavior and only happens once.
3.  **How to Use:**
    *   To download, simply paste a YouTube URL and press `Enter`.
    *   To change settings, enter a command number (e.g., `1`) and press `Enter`.

---

## File Descriptions

*   **`project.py`**: This is the main executable file that contains the core logic of the application. It includes:
    *   A `main` function that serves as the entry point.
    *   Three standalone, testable functions (`toggle_mode`, `validate_quality_choice`, `build_ydl_options`) as required by the CS50P specification.
    *   The main `TuneCatcher` class, which encapsulates the application's state, main loop, and user interface logic.

*   **`test_project.py`**: This file contains the unit tests for the three required custom functions in `project.py`. These tests are written for the `pytest` framework and verify the correctness of the core logic in isolation, ensuring that mode toggling, quality validation, and downloader configuration work as expected.

*   **`requirements.txt`**: A standard Python project file that lists all the pip-installable libraries the project depends on (`yt-dlp`, `moviepy`, `colorama`, `pytest`).

---

## Design Rationale

The development of TuneCatcher involved several key design decisions to meet the project's goals of reliability, quality, and user-friendliness.

1.  **Core Libraries (`yt-dlp` and `moviepy`):** Early in development, I considered using `pytube`. However, testing revealed its susceptibility to breaking changes from YouTube. I therefore chose **`yt-dlp`** for its superior reliability and frequent updates. The biggest challenge for any media tool is the dependency on FFmpeg. To create a seamless user experience, I chose to integrate **`moviepy`** not for its video editing capabilities, but for its brilliant automatic FFmpeg management, which downloads the binary if it's missing. This combination provides the power of `yt-dlp` and FFmpeg with the simplicity of a standard Python library installation.

2.  **Project Structure (Hybrid Approach):** To meet the CS50P requirements, the project uses a hybrid structure. The main application state and user interaction loop are managed within an object-oriented `TuneCatcher` class. This encapsulates the logic cleanly. However, key "pure" logic—functions that take an input and produce an output without side effects—were extracted into standalone functions (`toggle_mode`, etc.). This allows for clean, isolated unit testing with `pytest` while keeping the main application code well-organized.

3.  **File Format Choices (M4A and MKV):** A deliberate decision was made to avoid older formats.
    *   For audio, **M4A (AAC)** was chosen over MP3 because it provides noticeably better audio quality at a smaller file size and is now universally compatible with all modern devices.
    *   For video, **MKV** was chosen over MP4. YouTube's highest quality streams use modern codecs (like VP9 and Opus) that are not officially supported by the older MP4 standard. Merging these streams into an MKV container is the most reliable method and preserves the absolute original quality without any lossy re-encoding, which would occur if converting to a compatible MP4. This prioritizes quality and speed.