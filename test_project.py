import pytest
from project import toggle_mode, validate_quality_choice, build_ydl_options

def test_toggle_mode():
    """
    Tests the toggle_mode function to ensure it correctly switches
    between 'audio' and 'video'.
    """
    assert toggle_mode('audio') == 'video'
    assert toggle_mode('video') == 'audio'
    # Test with unexpected input, though our app logic prevents this
    assert toggle_mode('random') == 'audio'

def test_validate_quality_choice():
    """
    Tests the validate_quality_choice function with valid inputs,
    invalid inputs (out of range), and non-digit inputs.
    """
    qualities = ['1080p', '720p', '480p']
    
    # Valid choices
    assert validate_quality_choice('1', qualities) == '1080p'
    assert validate_quality_choice('3', qualities) == '480p'
    
    # Invalid choices
    assert validate_quality_choice('0', qualities) is None  # Out of range (low)
    assert validate_quality_choice('4', qualities) is None  # Out of range (high)
    assert validate_quality_choice('abc', qualities) is None # Not a digit
    assert validate_quality_choice('-1', qualities) is None # Not a valid digit for this logic

def test_build_ydl_options():
    """
    Tests the build_ydl_options function to ensure it correctly
    constructs the yt-dlp options dictionary for both audio and video modes.
    """
    # Test for audio mode
    audio_opts = build_ydl_options('audio', '1080p', '/path/to/ffmpeg', '/path/to/output')
    assert audio_opts['format'] == 'bestaudio/best'
    assert audio_opts['postprocessors'][0]['preferredcodec'] == 'm4a'
    assert audio_opts['ffmpeg_location'] == '/path/to/ffmpeg'
    assert 'merge_output_format' not in audio_opts

    # Test for video mode
    video_opts = build_ydl_options('video', '720p', '/path/to/ffmpeg', '/path/to/output')
    assert video_opts['format'] == 'bestvideo[height<=720]+bestaudio/best'
    assert video_opts['merge_output_format'] == 'mkv'
    assert 'postprocessors' not in video_opts

# It's good practice to add a main block to run pytest from the command line
if __name__ == "__main__":
    pytest.main()