# ytcc
![Build and test](https://github.com/woefe/ytcc/workflows/Build%20and%20test/badge.svg)

Command line tool to keep track of your favorite playlists on YouTube and many other places.

**Version 2.0.0 is out!**
Read [the migration guide](https://github.com/woefe/ytcc/tree/master/doc/migrate.md) before upgrading to 2.0.0 or later!
If you are looking for older versions, check the [Release](https://github.com/woefe/ytcc/releases) page and the [v1 branch](https://github.com/woefe/ytcc/tree/v1).


## Installation
```shell script
pip install ytcc
```
Alternative installation methods are described in the [documentation](https://github.com/woefe/ytcc/tree/master/doc/install.md).

## Migrating from version 1
See the [migration guide](https://github.com/woefe/ytcc/tree/master/doc/migrate.md)

## Usage

"Subscribe" to playlists.
```shell script
ytcc subscribe "Jupiter Broadcasting" "https://www.youtube.com/c/JupiterBroadcasting/videos"
ytcc subscribe "NCS: House" "https://www.youtube.com/playlist?list=PLRBp0Fe2GpgmsW46rJyudVFlY6IYjFBIK"
```

Import subscriptions from Google Takeout.
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

1. `$XDG_CONFIG_HOME/ytcc/ytcc.conf`
2. `~/.config/ytcc/ytcc.conf`
3. `~/.ytcc.conf`

If no config file is found in these three locations, a default config file is created at `~/.config/ytcc/ytcc.conf`.

### Example config

```ini
[ytcc]

# Directory where downloads are saved, when --path is not given
download_dir = ~/Downloads

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


[tui]
# The characters to use for selecting videos in interactive mode.
alphabet = sdfervghnuiojkl

# Default action of interactive mode.
# Possible options: play_video, play_audio, mark_watched, download_audio, download_video
default_action = play_video


[youtube_dl]
# Format (see FORMAT SELECTION in youtube-dl manpage). Make sure to use a video format here, if you
# want to be able to download videos.
format = bestvideo[height<=?1080]+bestaudio/best

# Output template (see OUTPUT TEMPLATE in youtube-dl manpage).
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

<!--
## Translations
Ytcc uses the GNU gettext utilities to manage localization.

### Managing locales
Create a new locale with `msginit`. The example below creates a new locale for Polish.
```bash
cd po
msginit --locale pl
```

Every time the PO template is changed, the locales have to be updated with `msgmerge`.
```bash
cd po
msgmerge --update de.po ytcc.pot
```

Every time a PO file is created or updated, new strings have to be translated. There are multiple tools available, see
the [GNU gettext manual](https://www.gnu.org/software/gettext/manual/gettext.html#Editing). I prefer GTranslator, e.g:

```bash
cd po
gtranslator de.po
```

### Updating the PO tempate
```bash
xgettext --output=po/ytcc.pot \
    --language=Python \
    --from-code=utf-8 \
    --copyright-holder="Wolfgang Popp" \
    --package-name="ytcc" \
    --package-version=$(python -c "import ytcc; print(ytcc.__version__)") \
    ytcc/{cli,arguments}.py
```
-->
