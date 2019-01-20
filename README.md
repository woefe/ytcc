# ytcc - The YouTube channel checker

Command Line tool to keep track of your favourite YouTube channels without signing up for a Google account.


## Installation
### Arch Linux
Install [ytcc](https://aur.archlinux.org/packages/ytcc/) from the AUR.

### Void Linux
Install package `ytcc`.

### Other distros
Ytcc requires python 3.6 or later. Install dependencies: `python3-lxml`, `python3-feedparser`, `python3-setuptools`,
`mpv`, `youtube-dl`, `gettext`.

```bash
git clone https://github.com/woefe/ytcc.git
cd ytcc
sudo python3 setup.py install
sudo install -Dm644 zsh/_ytcc /usr/share/zsh/site-functions/_ytcc
```


## Usage

Check for new videos and play them.
```shell
ytcc
```

Check for new videos and play them without asking you anything.
```shell
ytcc -y
```

"Subscribe" to a channel.
```shell
ytcc -a "Jupiter Broadcasting" https://www.youtube.com/user/jupiterbroadcasting
```

Import subscriptions from YouTube's subscription manager export.
```shell
ytcc --import-from ~/Downloads/subscription_manager
```

Check for new videos, print a list of new videos and play them.
```shell
ytcc -ulw
```

Download all videos from a channel that were published in July.
```shell
ytcc -f "Jupiter Broadcasting" --download --since 07-01 --to 07-31 --include-watched
```

Download only the audio track of "LINUX Unplugged" episodes
```shell
ytcc --search "channel:jupiter title:unplugged" --download --no-video
```
Note that the `--search` option only searches ytcc's database and not youtube.com.

Mark all videos of a channel as watched.
```shell
ytcc -f "Jupiter Broadcasting" -m
```

Search for Playthroughs, Let's Plays, ...
```shell
ytcc --search "title:*play*" -l
```

Listen to some music without limitations.
```shell
ytcc --add "NCS" https://www.youtube.com/user/NoCopyrightSounds --update
ytcc --disable-interactive --list --watch --no-video --include-watched --channel-filter NCS
```


## Configuration
Ytcc searches for a configuration file at following locations:

1. `$XDG_CONFIG_HOME/ytcc/ytcc.conf`
2. `~/.config/ytcc/ytcc.conf`
3. `~/.ytcc.conf`

If no config file is found in these three locations, a default config file is created at `~/.config/ytcc/ytcc.conf`.

### Example config

```conf
# General options
[YTCC]
# Path to file where database is stored. Can be used to sync the database between multiple machines ;)
dbpath = ~/.local/share/ytcc/ytcc.db

# Directory where downloads are saved, when --path is not given
downloaddir = ~/Downloads

# Parameters passed to mpv. Adjusting these might break ytcc!
mpvflags = --really-quiet --ytdl --ytdl-format=bestvideo[height<=?1080]+bestaudio/best


# Alternative interactive mode. Select videos with short tags instead of playing them in a pre-defined
# order
[quickselect]
# Enables or disables quickselect mode.
enabled = yes

# Plays the selected video instantly, if disabled. Otherwise it shows the interactive prompt
ask = yes

# The character to use for the quickselect tags.
alphabet = sdfervghnuiojkl


# Options for downloads
[youtube-dl]
# Format (see FORMAT SELECTION in youtube-dl manpage). Make sure to use a video format here, if you
# want to be able to download videos.
format = bestvideo[height<=?1080]+bestaudio/best

# Output template (see OUTPUT TEMPLATE in youtube-dl manpage)
outputtemplate = %(title)s.%(ext)s

# Loglevel options: quiet, normal, verbose
loglevel = normal

# Limit download speed to the given bytes/second. Set 0 for no limit.
# E.g. limit to one megabyte per second
#ratelimit = 1000000
ratelimit = 0

# Set number of retries before giving up on a download. Use `inf` for indefinitely many retries.
retries = 0

# Subtitles for videos. If enabled and available, automatic and manual subtitles for selected
# languages are embedded in the video.
#subtitles = en,de
subtitles = off

# Embed the youtube thumbnail in audio downloads. Transforms the resulting file to m4a, if
# enabled.
thumbnail = on

# Skips livestreams in download mode
skiplivestream = yes


# Columns printed by --list option, if --columns is not given as well.
[TableFormat]
id = on
date = off
channel = on
title = on
url = off
watched = off
```


## Reporting issues
Create a new issue on the [github issue tracker](https://github.com/woefe/ytcc/issues/new). Describe the issue as
detailed as possible. **Important**: do not forget to include the output of `ytcc --bug-report-info` in bug reports.


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
