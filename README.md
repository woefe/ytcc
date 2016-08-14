# ytcc - The YouTube channel checker

Command Line tool to keep track of your favourite YouTube channels without signing up for a Google account.

## Installation

<!--
### Ubuntu
```
sudo apt-get install python3-lxml python3-feedparser python3-setuptools mpv youtube-dl
git clone https://github.com/popeye123/ytcc.git
cd ytcc
sudo python3 setup.py install
sudo install -Dm644 zsh/_ytcc /usr/local/share/zsh/site-functions/_ytcc
```
-->

### openSUSE (Tumbleweed)
```
sudo zypper in python3-lxml python3-feedparser python3-setuptools mpv youtube-dl
git clone https://github.com/popeye123/ytcc.git
cd ytcc
sudo python3 setup.py install
sudo install -Dm644 zsh/_ytcc /usr/share/zsh/site-functions/_ytcc
```

### Arch Linux
```shell
yaourt -S ytcc
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

Listen to epic music
```shell
ytcc --add "Two Steps From Hell" https://www.youtube.com/channel/UC3swwxiALG5c0Tvom83tPGg --update
ytcc --search "thomas bergersen" --yes --list --watch --no-video
```

## Video quality settings
Quality settings can be adjusted via the youtube-dl config file. For more information see `man youtube-dl`.
It is now also possible to pass the quality settings via a mpv flag in ytcc's config file.

### Example (youtube-dl config)
Play videos in best audio and video quality but don't use a resolution higher than 1080p.
```shell
mkdir -p ~/.config/youtube-dl
echo "-f 'bestvideo[height<=?1080]+bestaudio/best'" >> ~/.config/youtube-dl/config
```
