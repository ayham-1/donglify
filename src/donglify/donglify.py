#!/bin/python3

from prompt_toolkit import prompt
from prompt_toolkit.completion import NestedCompleter
import os
import sys
import subprocess
import stat
import pathlib
import configparser
import signal

from termcolor import colored

from donglify.lib import *
from donglify.mkinitcpio import *
from donglify.grub import *
from donglify.isos import *

import importlib.metadata

version = importlib.metadata.version("donglify")


def dongle_init_partition(dev_name):
    print(colored(f"Acknowledge that the following procedure *will* destroy ALL data on '{dev_name}'\n"
                  "YOU WILL NOT BE ASKED AGAIN", 'red', attrs=["reverse", "blink", "bold"]))
    ack = input(
        "Acknowledge by writing the following in caps: DESTROY MY DONGLE\n")
    if ack != "DESTROY MY DONGLE":
        print("Stopping procedure by user command. No data was lost.")
        print("Farewell.")
        sys.exit(0)

    cmd = f'sudo parted {dev_name} mklabel gpt'
    execute(cmd, desc="set USB partition table as GPT")

    cmd = f'lsblk -n -oNAME,SIZE {dev_name}'
    dongle_size = str(subprocess.run(cmd, shell=True, capture_output=True) \
                      .stdout.decode('utf-8')).strip().split(' ')[1].replace("G", "")

    print("dongle has size: " + dongle_size + "GB")

    dongle_isos_size = int(0.5 * float(dongle_size) * 1024)
    dongle_persistent_size = int(0.5 * float(dongle_size) * 1024)

    print("recommended partition scheme: ")
    print("DONGLE_EFI partition: 256 MB")
    print("DONGLE_BOOT partition: 2048 MB")
    print("DONGLE_ISOs partition: " + str(dongle_isos_size) + " MB")
    print("DONGLE_PERSISTENT partition: " +
          str(dongle_persistent_size) + " MB")

    iso_size = input(
        "What would you like to have for ISO partition size in MB? [empty for same] ")
    persistent_size = input(
        "What would you like to have for persistent partition size in MB? [empty for same] ")

    if iso_size != "":
        dongle_isos_size = int(iso_size)
    if persistent_size != "":
        dongle_persistent_size = int(persistent_size)

    current_offset = 8
    parted = "parted -a optimal"
    cmd = f'{parted} {dev_name} mkpart "DONGLE_EFI" fat32 {str(current_offset)}MB 256MB'
    execute(cmd, desc="create efi partition on dongle", needed=True, ask=False)

    cmd = f'{parted} {dev_name} set 1 esp on'
    execute(cmd, desc="mark /efi as esp", needed=True, ask=False)

    current_offset += 256 + 8
    cmd = f'{parted} {dev_name} mkpart "DONGLE_BOOT" {str(current_offset)}MB {str(2048 + current_offset)}MB'
    execute(cmd, desc="create boot partition on dongle", needed=True, ask=False)

    cmd = f'{parted} {dev_name} set 2 boot on'
    execute(cmd, desc="mark /boot as boot", needed=True, ask=False)

    current_offset += 2048 + 8
    if iso_size != 0:
        cmd = f'{parted} {dev_name} mkpart "DONGLE_ISOs" {str(current_offset)}MB {str(dongle_isos_size + current_offset)}MB'
        execute(cmd, desc="create ISOs partition on dongle",
                needed=True, ask=False)
        current_offset += dongle_isos_size + 8

    if persistent_size != 0:
        cmd = f'{parted} {dev_name} mkpart "DONGLE_PERSISTENT" {str(current_offset)}MB 100%'
        execute(cmd, desc="create persistent partition on dongle",
                needed=True, ask=False)

    cmd = f'mkfs.vfat -n DONGLE_EFI  -F 32 {dev_name}1'
    execute(cmd, desc="format DONGLE_EFI as FAT16", needed=True, ask=False)

    cmd = f'cryptsetup luksFormat --type luks1 {dev_name}2'
    execute(cmd, desc="encrypt dongle's /boot partition, user will be asked for passphrase automatically",
            needed=True, ask=False)

    unlock_disk(f'{dev_name}2', "dongleboot")

    cmd = f'mkfs.ext4 /dev/mapper/dongleboot'
    execute(cmd, desc="format dongle's /boot partition as ext4",
            needed=True, ask=False)

    cmd = f'mkfs.ext4 {dev_name}3'
    execute(cmd, desc="format dongle's ISOs partition as ext4",
            needed=False, ask=False)

    cmd = f'cryptsetup luksFormat --type luks2 {dev_name}4'
    execute(cmd, desc="encrypt dongle's persistent partition, user will be asked for passphrase automatically",
            needed=False, ask=False)

    unlock_disk(f'{dev_name}4', "donglepersist")
    cmd = f'mkfs.ext4 /dev/mapper/donglepersist'
    execute(cmd, desc="format dongle's persistent partition",
            needed=False, ask=False)

    # find uuids and fill into /boot/dongle.ini
    DonglifyState.config["efi_uuid"] = get_uuid_by_dev(f'{dev_name}1')
    DonglifyState.config["locked_boot_uuid"] = get_uuid_by_dev(f'{dev_name}2')
    DonglifyState.config["unlocked_boot_uuid"] = get_uuid_by_dev(
        "/dev/mapper/dongleboot")
    DonglifyState.config["part_iso_uuid"] = get_uuid_by_dev(f'{dev_name}3')

    # grub-install
    dongle_mount_all()
    grub_encrypted_install()

    dongle_save_config()

    subprocess.run("lsblk -f", shell=True)
    good("dongle's partition initialization done")
    print("you are recommended to start adding system installs onto your dongle")
    sys.exit(0)


def dongle_add_current_system():
    print("Fill configs for current system:")

    name = input("install name, shown on GRUB: ")
    current_install = {}
    current_install["name"] = name
    current_install[DONGLE_INSTALL_KERNEL_NAME] = input(
        "kernel package name [linux/-hardened/-lts/..]: ")
    current_install[DONGLE_INSTALL_KERNEL_ARGS] = input(
        "kernel args [optional]: ")
    current_install[DONGLE_INSTALL_UCODE] = input(
        "microcode package to be installed [intel-ucode/amd-ucode]: ")
    current_install[DONGLE_INSTALL_CRYPTOKEYFILE] = input(
        "encryption key file to be loaded into initramfs [optional]: ")
    current_install[DONGLE_INSTALL_HOOKS_ADDED] = input(
        "hooks to be added to initramfs [optional]: ")
    current_install[DONGLE_INSTALL_KERNEL_VERSION] = subprocess.run("uname -r", shell=True, capture_output=True).stdout.decode('utf-8').strip()

    DonglifyState.installs_configs[name] = current_install
    dongle_save_config()

    print("adding current host system to donglify")
    dongle_umount_all()
    ensure_local_dirs_mountpoint_only()

    dongle_install_system(current_install)


def dongle_reinstall_system():
    name = select_dongle_install()
    if name == "":
        print("no available system configurations to reinstall")
        return

    current_install = DonglifyState.installs_configs[name]
    current_install["name"] = name

    dongle_install_system(current_install)


def dongle_install_system(current_install):
    dongle_mount_all()
    kernel_config_current_sys(current_install)
    grub_config_install()


def dongle_list_installs():
    if len(DonglifyState.installs_configs) == 0:
        print("no system installs on dongle")
        return

    print("listing registered installs on dongle")

    for name, config in DonglifyState.installs_configs.items():
        print()
        print(f'name: {name}')
        print(f'kernel_name: {config["kernel_name"]}')
        print(f'kernel_args: {config["kernel_args"]}')
        print(f'kernel_version: {config["kernel_version"]}')
        print(f'cryptokeyfile: {config["cryptokeyfile"]}')
        print(f'hooks_added: {config["hooks_added"]}')
        print(f'ucode: {config["ucode"]}')
        print()


def dongle_safe_update():
    name = select_dongle_install()
    if name == "":
        print("no available installs, try the 'add' command first")

    global current_install
    current_install = DonglifyState.installs_configs[name]
    current_install["name"] = name

    cmd = input("Entire your system's update command: ")
    dongle_mount_all()
    execute(cmd, "Runs user given system update command.", needed=True, ask=True)
    dongle_install_system(current_install)


donglify_iso_cmds = {
    "list": None,
    "add": None,
    "templates": None
}

donglify_cmds = {'mount': None, 'unmount': None, 'add': None,
                 'reinstall': None, 'update': None, 'status': None, 'list': None,
                 "iso": donglify_iso_cmds}


def main():
    print(f"Version: {version}")
    usage = f"Usage: donglify /dev/<name of usb>[index of encrypted dongleboot]\n" + \
        "       donglify init /dev/<name of usb>"

    if len(sys.argv) == 3 and "init" == sys.argv[1] and '/dev/' in sys.argv[2] and len(sys.argv[2]) == len('/dev/xyz'):
        dongle_init_partition(sys.argv[2])
    elif len(sys.argv) != 2 or not '/dev/' in sys.argv[1] or not len(sys.argv[1]) >= len('/dev/xyz0'):
        print(usage)
        sys.exit(1)

    def keyboard_interrupt_handler(x, y):
        print()
        print()
        print("Farewell, Traveller.")
        sys.exit(1)
    signal.signal(signal.SIGINT, keyboard_interrupt_handler)

    print("Welcome to donglify!")

    locate_and_load_config(sys.argv[1])

    try:
        while 1:
            print(colored("available commands: " +
                  ' '.join(donglify_cmds), 'dark_grey'))
            user_input = prompt("donglify> ", completer=NestedCompleter.from_nested_dict(
                donglify_cmds))
            if user_input == 'status':
                subprocess.run("lsblk", shell=True)
            elif user_input == 'list':
                dongle_list_installs()
            elif user_input == 'mount':
                dongle_mount_all()
                subprocess.run("lsblk", shell=True)
            elif user_input == 'unmount':
                dongle_umount_all()
                subprocess.run("lsblk", shell=True)
            elif user_input == 'add':
                dongle_add_current_system()
            elif user_input == 'reinstall':
                dongle_reinstall_system()
            elif user_input == 'update':
                dongle_safe_update()
            elif user_input == 'iso list':
                dongle_iso_list()
            elif 'iso add' in user_input:
                dongle_iso_add()
            elif user_input == 'iso templates':
                dongle_iso_list_templates()
            else:
                print(f'command {user_input} not recognized')
                print("Commands: " + " ".join(donglify_cmds))
    except (KeyboardInterrupt, EOFError):
        print()
        print("Farewell, Traveller.")
        sys.exit(0)
        pass


if __name__ == "__main__":
    main()

# NOTES WHILE WORKING ON THE PROJECT
# partitions:
#   label: DONGLE_EFI, 256 MiB FAT16
#   label: DONGLE_BOOT, 2048 MiB LUKS
#   label: DONGLE_ISOs, 32000 MiB EXT4
#   label: DONGLE_PERSISTENT, rest MiB LUKS
#
# mounting dongleboot and sdc1
#   grub-install --target=x86_64-efi --efi-directory=/efi --bootloader-id=GRUB --removable
#   configs to change:
#     kernel params:
#       cryptroot to point to /
#       cryptkey is still cryptkey=rootfs:/boot/crypto_keyfile.bin, because key would be in the initramfs
#     mkinitcpio:
#       FILES=(/boot/cryto_keyfile.bin)
#       add hooks: encrypt lvm2 fsck
#   pacman -S mkinitcpio linux-hardened intel-ucode
#   grub-mkconfig -o /boot/grub/grub.cfg
#
# msdos usb does not seem to work with LUKSv2
#
# allowing multiple archlinux installs on the same usb:
#   donglify should be able to handle detached luks headers, so switch to sd-encrypt if not yet done
#   /etc/mkinitcpio.conf: HOOKS=(...systemd...sd-encrypt)
#   /etc/default/grub: remove cryptdevice, cryptkey, maintain root= which is a pure kernel command
#   /etc/crypttab.initramfs: add required internal drive for root partition loading
#   mount all
#   pacman -S mkinitcpio linux-hardened intel-ucode
# for grub config:
#   it appears /etc/default/grub needs to have GRUB_ENABLE_CRYPTODISK and then run
#   grub-install so that grub knows to unlock dongleboot, however, for the config
#   in /boot/grub/grub.cfg, grub-mkconfig seems not to be adequate and custom configs from
#   grub.d/ need to concated into grub.cfg
#
#   theory: crytodisk is not needed in grub.cfg, as initramfs's sd-encrypt handles root decryption
#
#   install correct kernel image
#   rename kernel & initramfs image/fallback image
#
# having safe updates
#   get update command
#   ensure mount
#   run update command
#   run __kernel_config_current_sys()
#
# to check for loopback.cfg for an ISO:
# mount -o loop <iso> /mnt
# ls /mnt/boot/grub/ # <- should be in this directory as 'loopback.cfg'
#
# linux ISOs loopback.cfg status [done at 2024-01-04]:
#       - archlinux, and arch-based that don't deviate in their ISO builds
#       - grml64-full
#       - ParrotOS-security
#       - nixos-gnome
#       - [x] KaliOS
#       - [x] Fedora

# TODO: add donglepersist mounting
# TODO: package for makepkg
