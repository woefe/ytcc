# ytcc - The YouTube channel checker

Command Line tool to keep track of your favourite YouTube channels without signing up for a Google account.

## Installation

### Ubuntu
```
sudo apt-get install youtube-dl mpv python-lxml python-feedparser
git clone https://github.com/popeye123/ytcc.git
cd ytcc
sudo ./setup.py install
```

### openSUSE (Tumbleweed)
```
sudo zypper in python3-lxml python3-feedparser python3-setuptools mpv youtube-dl
git clone https://github.com/popeye123/ytcc.git
cd ytcc
sudo python3 setup.py install
```

### Arch Linux
```
yaourt -S ytcc
```

## Usage

Check for new videos and play them.
```
ytcc
```

Check for new videos and play them without asking you anything.
```
ytcc -y
```

"Subscribe" to a channel.
```
ytcc -a "Jupiter Broadcasting" https://www.youtube.com/user/jupiterbroadcasting
```

Check for new videos, print a list of new videos and play them.
```
ytcc -ulw
```
