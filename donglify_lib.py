import os
import sys
import subprocess
import pathlib
import configparser

from termcolor import colored
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

DONGLE_EFI_UUID = "efi_uuid"
DONGLE_LOCKED_BOOT_UUID = "locked_boot_uuid"
DONGLE_UNLOCKED_BOOT_UUID = "unlocked_boot_uuid"

DONGLE_INSTALL_KERNEL_NAME = "kernel_name"
DONGLE_INSTALL_KERNEL_ARGS = "kernel_args"
DONGLE_INSTALL_CRYPTOKEYFILE = "cryptokeyfile"
DONGLE_INSTALL_HOOKS_ADDED = "hooks_added"
DONGLE_INSTALL_UCODE = "ucode"


class DonglifyState(object):
    state_ask_cmd = False

    config = {}
    installs_configs = {}


def good(msg):
    print(colored(msg, "green"))


def does_user_accept():
    answer = str(prompt("[yes/no] > "))
    if "YES" != answer.capitalize():
        return True
    return False


def disk_exists(path):
    return os.path.exists(path)


def execute(cmd, desc="", ask=False, needed=True, dry_run=False):
    if not DonglifyState.state_ask_cmd:
        ask = False

    assert (ask and desc != "") or not ask
    if ask:
        print()
        print("You are about to execute the following command as {}:".format(
            colored("SUDO", "yellow", attrs=["blink"])))
        print()
        print(colored(cmd, "red", attrs=["reverse", "blink", "bold"]))
        print()
        print("Is command needed? " + ("Yes" if needed else "No"))
        print("Is command ran as dry-run? " + ("Yes" if dry_run else "No"))
        print("Command Description: " + desc)
        print()
        print("Do you accept after review?")
        if not does_user_accept():
            print("Not executing by command of user")
            if needed:
                print("This was a needed command, refusing to continue.\nFarewell.")
                sys.exit(1)
            return
    else:
        print(colored("executing: ", "green", attrs=["bold"]) + colored(cmd, "yellow", attrs=["bold"]) +
              colored(f' # {desc}', "dark_grey"))

    proc = subprocess.run(cmd, shell=True)
    if 0 != proc.returncode:
        print(f'command failed with returncode {proc.returncode}')
        sys.exit(proc.returncode)

    return proc.returncode


def locate_and_load_config(dev_name):
    print("attempting to locate dongle.ini")

    unlock_disk(dev_name, "dongleboot")
    mount_mapper("dongleboot", "/boot")

    if not pathlib.Path("/boot/dongle.ini").exists():
        print(colored(
            "/boot/dongle.ini does not exist, choose another device partition or run dongle init", "red"))
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read("/boot/dongle.ini")

    DonglifyState.config = config["dongle"]

    for key in config.sections():
        if key == "dongle":
            continue

        DonglifyState.installs_configs[key] = config[key]

    print(colored("Please review that this is the correct dongle config contents and that there are no alterations from"
                  " previous access.", "yellow"))
    print()
    config.write(sys.stdout, space_around_delimiters=True)

    print("Looks good?")
    if not does_user_accept():
        print("dongle.ini has been rejected by user command.")
        sys.exit(1)

    dongle_mount_all()


def dongle_save_config():
    # assumes all mounts are right and just writes config into /boot/dongle.ini
    config = configparser.ConfigParser()
    config.read_dict({"dongle": DonglifyState.config})

    for name, install_config in DonglifyState.installs_configs.items():
        config.read_dict({name: install_config})

    with open("/boot/dongle.ini", 'w') as f:
        config.write(f, space_around_delimiters=True)


def unlock(uuid, cryptname):
    if not disk_exists(f'/dev/mapper/{cryptname}'):
        cmd = f'cryptsetup open /dev/disk/by-uuid/{uuid} {cryptname}'
        execute(
            cmd, desc=f'Unlock UUID={uuid} partition and name it as {cryptname}', needed=True, ask=True)


def unlock_disk(disk, cryptname):
    if not disk_exists(f'/dev/mapper/{cryptname}'):
        cmd = f'cryptsetup open {disk} {cryptname}'
        execute(
            cmd, desc=f'Unlock disk {disk} partition and name it as {cryptname}', needed=True, ask=True)


def lock(luksname):
    if disk_exists(f'/dev/mapper/{luksname}'):
        cmd = f'cryptsetup close {luksname}'
        execute(
            cmd, desc=f'Lock the dongle\'s {luksname} parition', needed=True, ask=True)


def mount(uuid, dest):
    if not os.path.ismount(f'{dest}'):
        cmd = f'mount UUID={uuid} {dest}'
        execute(
            cmd, desc=f'mount dongle\'s partition UUID={uuid} to {dest}', needed=True, ask=True)


def mount_mapper(mapper_name, dest):
    if not os.path.ismount(f'{dest}'):
        cmd = f'mount /dev/mapper/{mapper_name} {dest}'
        execute(
            cmd, desc=f'mount dongle\'s partition mapper name {mapper_name} to {dest}', needed=True, ask=True)


def umount(mntpnt):
    if os.path.ismount(f'{mntpnt}'):
        cmd = f'umount {mntpnt}'
        execute(
            cmd, desc=f'un-mount dongle\'s {mntpnt}', needed=True, ask=True)


def ensure_local_dirs_mountpoint_only():
    if not os.path.ismount("/efi") and not os.path.ismount("/boot"):
        cmd = 'chattr +i /efi'
        execute(cmd, desc=f'make host /efi only a mountpoint',
                needed=False, ask=True)
        cmd = 'chattr +i /boot'
        execute(cmd, desc=f'make host /efi only a mountpoint',
                needed=False, ask=True)


def get_uuid_by_dev(dev_name):
    cmd = f'lsblk -n -oNAME,UUID {dev_name} --raw'
    return subprocess.run(cmd, shell=True, capture_output=True).stdout.decode("utf-8") \
        .strip().split('\n')[0].split(' ')[-1].strip()


def select_dongle_install():
    names = DonglifyState.installs_configs.keys()

    if len(names) == 0:
        return ""

    print("Select from available dongle install names:\n\t" +
          colored(' '.join(names), 'green'))

    return prompt("select> ", completer=WordCompleter(names, ignore_case=False))


def dongle_mount_all():
    mount(DonglifyState.config["efi_uuid"], "/efi")
    unlock(DonglifyState.config["locked_boot_uuid"], "dongleboot")
    mount(DonglifyState.config["unlocked_boot_uuid"], "/boot")
    good("mounted all necessarily points from donglified usb")


def dongle_umount_all():
    umount("/efi")
    umount("/boot")
    lock("dongleboot")
    lock("donglepersist")

    good("system mounts are now clean, safe to remove dongle")


if __name__ == "__main__":
    print("this script is not to be meant run alone, use main script")
    sys.exit(1)
