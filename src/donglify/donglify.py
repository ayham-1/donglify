#!/bin/python3

from prompt_toolkit import prompt
from prompt_toolkit.completion import NestedCompleter
import sys
import subprocess
import signal

from termcolor import colored

from donglify.lib import *
from donglify.mkinitcpio import *
from donglify.grub import *
from donglify.isos import *
from donglify.config import *


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
    execute(cmd, desc="create efi partition on dongle")

    cmd = f'{parted} {dev_name} set 1 esp on'
    execute(cmd, desc="mark /efi as esp")

    current_offset += 256 + 8
    cmd = f'{parted} {dev_name} mkpart "DONGLE_BOOT" {str(current_offset)}MB {str(2048 + current_offset)}MB'
    execute(cmd, desc="create boot partition on dongle")

    cmd = f'{parted} {dev_name} set 2 boot on'
    execute(cmd, desc="mark /boot as boot")

    current_offset += 2048 + 8
    if iso_size != 0:
        cmd = f'{parted} {dev_name} mkpart "DONGLE_ISOs" {str(current_offset)}MB {str(dongle_isos_size + current_offset)}MB'
        execute(cmd, desc="create ISOs partition on dongle")
        current_offset += dongle_isos_size + 8

    if persistent_size != 0:
        cmd = f'{parted} {dev_name} mkpart "DONGLE_PERSISTENT" {str(current_offset)}MB 100%'
        execute(cmd, desc="create persistent partition on dongle")

    cmd = f'mkfs.vfat -n DONGLE_EFI  -F 32 {dev_name}1'
    execute(cmd, desc="format DONGLE_EFI as FAT16")

    cmd = f'cryptsetup luksFormat --type luks1 {dev_name}2'
    execute(cmd, desc="encrypt dongle's /boot partition, user will be asked for passphrase automatically")

    unlock_disk(f'{dev_name}2', "dongleboot")

    cmd = f'mkfs.ext4 /dev/mapper/dongleboot'
    execute(cmd, desc="format dongle's /boot partition as ext4")

    cmd = f'mkfs.ext4 {dev_name}3'
    execute(cmd, desc="format dongle's ISOs partition as ext4")

    cmd = f'cryptsetup luksFormat --type luks2 {dev_name}4'
    execute(cmd, desc="encrypt dongle's persistent partition, user will be asked for passphrase automatically")

    unlock_disk(f'{dev_name}4', "donglepersist")
    cmd = f'mkfs.ext4 /dev/mapper/donglepersist'
    execute(cmd, desc="format dongle's persistent partition")

    # find uuids and fill into /boot/dongle.ini
    data = {
        "config": {
            "version": DonglifyState.LATEST_VERSION,
            "efi_uuid": get_uuid_by_dev(f'{dev_name}1'),
            "locked_boot_uuid": get_uuid_by_dev(f'{dev_name}2'),
            "unlocked_boot_uuid": get_uuid_by_dev("/dev/mapper/dongleboot"),
            "part_iso_uuid": get_uuid_by_dev(f'{dev_name}3'),
        },
        "installs": {},
        "isos": {}
    }
    DonglifyState.init(data)

    # grub-install
    dongle_mount_all()
    grub_encrypted_install()

    DonglifyState.write()

    subprocess.run("lsblk -f", shell=True)
    good("dongle's partition initialization done")
    tell("you are recommended to start adding system installs onto your dongle")
    sys.exit(0)


def dongle_add_current_system():
    print("Fill configs for current system:")

    name = input("install name, shown on GRUB: ")
    current_install: DongleInstall = DongleInstallValidator.validate_python({
        "kernel_name": input("kernel package name [linux/-hardened/-lts/..]: "),
        "kernel_args": input("kernel args [optional]: "),
        "ucode": input("microcode package to be installed [intel-ucode/amd-ucode]: "),
        "cryptokeyfile": input("encryption key file to be loaded into initramfs [optional]: "),
        "hooks_added": input("hooks to be added to initramfs [optional]: "),
        "kernel_version": subprocess.run("uname -r", shell=True, capture_output=True).stdout.decode('utf-8').strip()
    })

    DonglifyState.installs[name] = current_install
    DonglifyState.write()

    tell("adding current host system to donglify")
    dongle_umount_all()
    ensure_local_dirs_mountpoint_only()

    dongle_install_system(name)


def dongle_reinstall_system():
    name = select_dongle_install()
    if name == "":
        bad("no available system configurations to reinstall")
        return

    dongle_install_system(name)


def dongle_install_system(current_install_name: str):
    dongle_mount_all()
    kernel_config_current_sys(current_install_name)
    grub_config_install()


def dongle_list_installs():
    if len(DonglifyState.installs) == 0:
        bad("no system installs on dongle")
        return

    tell("listing registered installs on dongle")

    for name, config in DonglifyState.installs.items():
        print()
        print(f'name: {name}')
        print(f'kernel_name: {config.kernel_name}')
        print(f'kernel_args: {config.kernel_args}')
        print(f'kernel_version: {config.kernel_version}')
        print(f'cryptokeyfile: {config.cryptokeyfile}')
        print(f'hooks_added: {config.hooks_added}')
        print(f'ucode: {config.ucode}')


def select_dongle_install():
    names = list(DonglifyState.installs.keys())

    if len(names) == 0:
        return ""

    print("Select from available dongle install names:\n\t" +
          colored(' '.join(names), 'green'))

    return prompt("select> ", completer=WordCompleter(names, ignore_case=False))



def dongle_safe_update():
    name = select_dongle_install()
    if name == "":
        bad("no available installs, try the 'add' command first")

    cmd = input("Enter your system's update command: ")
    dongle_mount_all()
    execute(cmd, "Runs user given system update command.")
    dongle_install_system(name)

def dongle_mount_all():
    mount(DonglifyState.config.efi_uuid, "/efi")
    unlock(DonglifyState.config.locked_boot_uuid, "dongleboot")
    mount(DonglifyState.config.unlocked_boot_uuid, "/boot")
    mount(DonglifyState.config.part_iso_uuid, "/mnt/iso")
    good("mounted all necessarily points from donglified usb")

donglify_iso_cmds = {
    "list": None,
    "add": None,
    "templates": None
}

donglify_cmds = {'mount': None, 'unmount': None, 'add': None,
                 'reinstall': None, 'update': None, 'status': None, 'list': None,
                 "iso": donglify_iso_cmds}


def main():
    import importlib.metadata
    version = importlib.metadata.version("donglify")
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

    try:
        DonglifyState.locate_and_load_config(sys.argv[1])
        dongle_mount_all()
        while 1:
            print(colored("available commands: " +
                  ' '.join(donglify_cmds), 'dark_grey'))
            user_input = prompt("donglify> ", completer=NestedCompleter.from_nested_dict(donglify_cmds))
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
            elif user_input == 'iso': 
                print(colored("available iso commands: " +
                  ' '.join(donglify_iso_cmds), 'dark_grey'))
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
