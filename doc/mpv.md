# mpv configuration for ytcc

Ytcc does not mark a video as watched if mpv exits with a non-zero status code.
You can use that together with mpv's "watch later" feature to resume videos.

You need following lines in `~/.config/mpv/input.conf`:
```
q quit 0
Ctrl+c quit 1
Shift+q quit-watch-later 1
```

The config above results in following behavior:

- Pressing `q` quits mpv and marks the video as watched.
- Pressing `Q` quits mpv and stores the current playback position.
    Ytcc does not mark the video as watched.
    Playing the video again will resume at the previous position.
- Pressing `Ctrl+c` does not mark the video as watched and doesn't save the resume timestamp.
    The video will play from the beginning the next time it is started by ytcc.
