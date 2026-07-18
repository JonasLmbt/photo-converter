"""Static configuration: supported file types and GUI theme."""

# --- Supported file extensions (lowercase, with leading dot) ---
RAW_EXTENSIONS       = {'.nef', '.raf', '.dng', '.cr2', '.arw', '.orf', '.pef', '.srw', '.rw2', '.erf', '.mrw', '.dcr'}
HEIC_EXTENSIONS      = {'.heic', '.heif', '.avif'}
OTHER_IMG_EXTENSIONS = {'.png', '.bmp', '.tiff', '.tif', '.webp'}
JPG_EXTENSIONS       = {'.jpg', '.jpeg'}
MP4_EXTENSIONS       = {'.mp4', '.m4v'}
VIDEO_CONV_EXTENSIONS= {'.mov', '.avi', '.mkv', '.wmv', '.3gp', '.flv', '.webm'}
ALL_SUPPORTED        = (RAW_EXTENSIONS | HEIC_EXTENSIONS | OTHER_IMG_EXTENSIONS |
                        JPG_EXTENSIONS | MP4_EXTENSIONS | VIDEO_CONV_EXTENSIONS)

# --- GUI theme (dark) ---
DARK_BG   = '#1c1c1e'
PANEL_BG  = '#2c2c2e'
FIELD_BG  = '#3a3a3c'
FIELD_HI  = '#4a4a4c'
TEXT_FG   = '#f5f5f7'
MUTED_FG  = '#8e8e93'
ACCENT    = '#0a84ff'
ACCENT_HI = '#0060df'
SUCCESS   = '#30d158'
ERROR_CLR = '#ff453a'
WARN_CLR  = '#ffd60a'
FONT_MAIN = ('Segoe UI', 10)
FONT_MONO = ('Consolas', 9)
