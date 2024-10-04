# donglify

The majority of Linux systems have a severe security threat. These installs are
susceptable to data theft if the install disk is stolen. ArchLinux offers LUKS
as an encryption method to protect the root & data partitions. Even then, the
majority of these installs omit the encryption of the `/boot` or `/efi`
partitions. This script helps automate the configuration of encrypted `/boot`.
And provides a solution in replacement of the `/efi` partition, which usually
can not be encrypted, by having it be present on a USB DONGLE.

## Installation

```sh
pipx install donglify
```

## Usage

To use donglify, you will need to install the initial configurations onto a
USB, which can be done as follows:

```sh
donglify init /dev/sd[a,b,c]
```

This command creates the following partitions on your USB.

- `/efi`, 512 MB, holds the EFI stub which the BIOS of a system to boot the
  USB.
- `/boot`, 2GB, holds the kernels of the donglified systems, AND the
  `dongle.ini` configuration file.
- `dongleisos`, size is set by the user, used to hold the ISOs which are
  available in the GRUB menu on USB boot, currently only `loopback.cfg` ISOs
  can be used.
- `donglepersist`, size is set by the user, an encrypted LUKS partition that
  can be used by the user to store personal data.

In order to enter the interactive donglify prompt:

```sh
donglify /dev/sd[a,b,c][2]
```

The argument should be the donglified USB `/boot` partition.

## Interactive Commands

donglify uses an interactive CLI interface to conduct its business. This is
currently the only support, future support for automated installs could be
added.

### cmd: add

Adds host system configuration to the donglified USB. This configuration is
automatically generation to the host system installed once established.

```sh
donglify> add
```

You will be prompted for configuration options.

You will need to add unlock root LUKS entry in
[/etc/crypttab.initramfs](https://wiki.archlinux.org/title/dm-crypt/System_configuration#crypto),
otherwise the initial ramdisk won't ask to unlock your root partition on your
added system. There you can also tell it about your keyfile location if you
choose to do so.

```sh
[~] $ sudo cat /etc/crypttab.initramfs 
cryptssd UUID=<your UUID here> /boot/crypto_keyfile.bin
crypthdd UUID=<your UUID here> /boot/crypto_keyfile.bin
```

### cmd: mount

```sh
donglify> mount
```

Mounts all donglified USB except for `donglepersist`.

### cmd: unmount

```sh
donglify> unmount
```

Unmounts all partitions that `mount` mounted.

### cmd: list

```sh
donglify> list
```

Lists all installed systems on the USB.
