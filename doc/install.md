# Installation

## From PyPi
Get [pipx](https://pipx.pypa.io/latest/installation/), then run:
```shell script
pipx install ytcc
```

## Arch Linux
Install [ytcc](https://aur.archlinux.org/packages/ytcc/) or [ytcc-git](https://aur.archlinux.org/packages/ytcc-git/) from the AUR.

## Debian / Ubuntu
```shell script
apt install ytcc
```

## NixOS
```shell script
nix-env -iA nixos.ytcc
```

## Void Linux
Install the [ytcc](https://voidlinux.org/packages/?arch=x86_64&q=ytcc) package.

## Gentoo
Note: this is maintained by [@EmRowlands](https://github.com/EmRowlands),
please report installation errors to the erowl-overlay issue tracker before the
main ytcc tracker.

Add the `erowl-overlay` using `eselect-repository` (or layman):

```
eselect repository add erowl-overlay git https://gitlab.com/EmRowlands/erowl-overlay.git
```

Install `net-misc/ytcc`. Currently (October 2020), ytcc v1 is stable and ytcc
v2 betas are `~arch`. A 9999 ebuild is also available.
