# ytcc
![Build and test](https://github.com/woefe/ytcc/workflows/Build%20and%20test/badge.svg)

Command line tool to keep track of your favorite playlists on YouTube and many other places.

## Installation
```shell script
pip install ytcc
```
Alternative installation methods are described in the [documentation](https://github.com/woefe/ytcc/tree/master/doc/install.md).

## Usage

Add "subscriptions".
```shell script
# Any playlist supported by yt-dlp (or youtube-dl)
ytcc subscribe "Jupiter Broadcasting" "https://www.youtube.com/c/JupiterBroadcasting/videos"
ytcc subscribe "NCS: House" "https://www.youtube.com/playlist?list=PLRBp0Fe2GpgmsW46rJyudVFlY6IYjFBIK"
ytcc subscribe "Neus" "https://soundcloud.com/neus/tracks"

# RSS feed podcasts
ytcc subscribe "LINUX Unplugged" "https://linuxunplugged.com/rss"
ytcc subscribe "Darknet Diaries" "https://feeds.megaphone.fm/darknetdiaries"
```

Import subscriptions from [Google Takeout](https://takeout.google.com/).
*Hint*: When requesting a takeout make sure to select only the YouTube data, otherwise the takeout might take quite long to complete.
```shell script
ytcc import ~/Downloads/Takeout/Youtube/subscriptions/subscriptions.csv
```

Fetch metadata of new videos.
```shell script
ytcc update
```

List unwatched videos.
```shell script
ytcc list
```

List playlist content in JSON format.
```shell script
ytcc --output json list --playlist "NCS: House" --since 2020-07-07 --watched --unwatched
```

List all videos as RSS feed.
```shell script
ytcc --output rss list --watched --unwatched
```

Start the interactive terminal interface.
```shell script
ytcc tui
```

Mark all videos of a playlist as watched without playing them.
```shell script
ytcc ls -p "Jupiter Broadcasting" | ytcc mark
```

Listen to some music without limitations.
```shell script
ytcc ls -p "NCS: House" | ytcc play --audio-only
```

**Alternative terminal interface with thumbnail support.**
Requires [fzf](https://github.com/junegunn/fzf) version 0.23.1 or newer, optionally [curl](https://curl.se/) and either [ueberzug](https://github.com/seebye/ueberzug) or [kitty](https://sw.kovidgoyal.net/kitty/).
The script is automatically installed on most platforms during installation of ytcc.
If it's not installed, you can download it from [here](https://github.com/woefe/ytcc/tree/master/scripts/ytccf.sh).
```shell script
ytccf.sh

# Show help and key bindings
ytccf.sh --help
```

## Configuration
Ytcc searches for a configuration file at following locations:

1. The file given with `-c` or `--config` options
2. `~/.ytcc.conf`
3. `$XDG_CONFIG_HOME/ytcc/ytcc.conf` or `~/.config/ytcc/ytcc.conf`
4. `/etc/ytcc/ytcc.conf`

If no config file is found in these locations, a default config file is created at `$XDG_CONFIG_HOME/ytcc/ytcc.conf` or `~/.config/ytcc/ytcc.conf`

### Example config

```ini
[ytcc]

# Directory where downloads are saved, when --path is not given
download_dir = ~/Downloads

# Downloads videos to subdirectories by playlist name. If a video is on multiple playlists, ytcc
# will download the video only to one subdirectory and symlink it to the other subdirectories.
download_subdirs = on

# Parameters passed to mpv. Adjusting these might break video playback in ytcc!
mpv_flags = --ytdl --ytdl-format=bestvideo[height<=?1080]+bestaudio/best

# Defines the order of video listings.
# Possible options: id, url, title, description, publish_date, watched, duration, extractor_hash,
# playlists. Every option must be suffixed with :desc or :asc for descending or ascending sort.
order_by = playlists:asc, publish_date:desc

# Default attributes shown in video listings.
# Some ytcc commands allow overriding the default set here in the config.
video_attrs = id, title, publish_date, duration, playlists

# Default attributes shown in playlist/subscription listings.
# Some ytcc commands allow overriding the default set here in the config.
playlist_attrs = name, url, reverse, tags

# Path where the database is stored.
# Can be used to sync the database between multiple machines.
db_path = ~/.local/share/ytcc/ytcc.db

# The format of used to print dates
date_format = %Y-%m-%d

# Default failure threshold before a video is ignored.
# When a video could not be updated repeatedly, it will be ignored by ytcc after `max_update_fail`
# attempts. This setting can be overridden with the --max-fail commandline parameter.
max_update_fail = 5

# Default update backlog.
# The update command will only check the first `max_update_backlog` videos of a playlist to improve
# performance. This setting can be overridden with the --max-backlog commandline parameter.
max_update_backlog = 20

# Ignore videos that have an age limit higher than the one specified here.
age_limit = 0


# Prompt and table colors. Supports 256 colors. Hence, values between 0-255 are allowed.
# See https://en.wikipedia.org/wiki/ANSI_escape_code#8-bit for the color codes.
[theme]
prompt_download_audio = 2
prompt_download_video = 4
prompt_play_audio = 2
prompt_play_video = 4
prompt_mark_watched = 1
table_alternate_background = 245
plain_label_text = 244


[tui]
# The characters to use for selecting videos in interactive mode.
alphabet = sdfervghnuiojkl

# Default action of interactive mode.
# Possible options: play_video, play_audio, mark_watched, download_audio, download_video
default_action = play_video


[youtube_dl]
# Format (see FORMAT SELECTION in yt-dlp manpage). Make sure to use a video format here, if you
# want to be able to download videos.
format = bestvideo[height<=?1080]+bestaudio/best

# Output template (see OUTPUT TEMPLATE in yt-dlp manpage).
# Note that the output template will be prefixed with the `download_dir` directory and the name of
# the playlist if `download_sub_dir` is enabled.
output_template = %(title)s.%(ext)s

# If a merge is required according to format selection, merge to the given container format.
# One of mkv, mp4, ogg, webm, flv
merge_output_format = mkv

# Limit download speed to the given bytes/second. Set 0 for no limit.
# E.g. limit to one megabyte per second
#ratelimit = 1000000
ratelimit = 0

# Set number of retries before giving up on a download.
# Set 0 for no retries.
retries = 0

# Subtitles for videos.
# If enabled and available, automatic and manual subtitles for selected languages are embedded in
# the video.
#subtitles = en,de
subtitles = off

# Embed the youtube thumbnail in audio downloads.
# Transforms the resulting file to m4a, if enabled.
thumbnail = on

# Skips livestreams in download command.
skip_live_stream = true

# Don't download videos longer than 'max_duration' seconds.
# 0 disables the limit.
max_duration = 9000

# Restrict filenames to only ASCII characters and avoid "&" and spaces in filenames.
restrict_filenames = off
```

### mpv configuration
Ytcc uses [mpv](https://mpv.io) to play videos.
You can configure mpv to integrate nicely with ytcc.
Specifics are documented [here](https://github.com/woefe/ytcc/tree/master/doc/mpv.md).


## Reporting issues
Create a new issue on the [GitHub issue tracker](https://github.com/woefe/ytcc/issues/new).
Describe the issue as detailed as possible and please use the issue templates, if possible!
**Important**: do not forget to include the output of `ytcc bug-report` in bug reports.
It also might help a lot to run ytcc with the `--loglevel debug` option and include the output in your report.

## Development
We recommend developing inside a virtualenv.

1. Set up a [virtualenv](https://virtualenv.pypa.io/en/latest/)
2. Install development dependencies: `pip install -r devrequirements.txt`

Run the following commands before every pull request and fix the warnings or errors they produce.
```shell script
mypy ytcc
pytest
pylint ytcc
pydocstyle ytcc
```
