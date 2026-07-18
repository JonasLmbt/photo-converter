#!/usr/bin/env python3
"""Entry point for the Photo Converter GUI.

Run directly with:  python main.py
"""

from photo_converter.gui import PhotoConverterApp


def main():
    PhotoConverterApp().mainloop()


if __name__ == '__main__':
    main()
