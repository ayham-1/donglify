import os
import sys
import subprocess

from termcolor import colored
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

import logging
logger = logging.getLogger("donglify")
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def good(msg):
    logger.info(colored(msg, "green"))

def bad(msg):
    logger.error(colored(msg, "red"))

def tell(msg):
    logger.info(colored(msg, attrs=["bold"]))

def does_user_accept():
    answer = str(prompt("[yes/no] > "))
    if answer.upper() == "YES":
        return True
    return False

def disk_exists(path):
    return os.path.exists(path)

def execute(cmd, desc=""):
    logger.info(colored("executing: ", "green", attrs=["bold"]) + colored(cmd, "yellow", attrs=["bold"]) +
        colored(f' # {desc}', "dark_grey"))

    proc = subprocess.run(cmd, shell=True)
    if 0 != proc.returncode:
        print(
            colored(f'command failed with returncode {proc.returncode}', 'red'))
        sys.exit(proc.returncode)

    return proc.returncode


import pkgutil
def get_asset_data(name):
    data = pkgutil.get_data(__name__, "assets/" + name)
    if data is None:
        raise Exception("could not find assets/" + name)
    return data

def unlock(uuid, cryptname):
    if not disk_exists(f'/dev/mapper/{cryptname}'):
        cmd = f'cryptsetup open /dev/disk/by-uuid/{uuid} {cryptname}'
        execute(cmd, desc=f'Unlock UUID={uuid} partition and name it as {cryptname}')


def unlock_disk(disk, cryptname):
    if not disk_exists(f'/dev/mapper/{cryptname}'):
        cmd = f'cryptsetup open {disk} {cryptname}'
        execute(cmd, desc=f'Unlock disk {disk} partition and name it as {cryptname}')


def lock(luksname):
    if disk_exists(f'/dev/mapper/{luksname}'):
        cmd = f'cryptsetup close {luksname}'
        execute(cmd, desc=f'Lock the dongle\'s {luksname} parition')


def mount(uuid, dest):
    os.makedirs(dest, exist_ok=True)

    if not os.path.ismount(f'{dest}'):
        cmd = f'mount UUID={uuid} {dest}'
        execute(cmd, desc=f'mount dongle\'s partition UUID={uuid} to {dest}')


def mount_mapper(mapper_name, dest):
    if not os.path.ismount(f'{dest}'):
        cmd = f'mount /dev/mapper/{mapper_name} {dest}'
        execute(cmd, desc=f'mount dongle\'s partition mapper name {mapper_name} to {dest}')


def umount(mntpnt):
    if os.path.ismount(f'{mntpnt}'):
        cmd = f'umount {mntpnt}'
        execute(cmd, desc=f'un-mount dongle\'s {mntpnt}')


def ensure_local_dirs_mountpoint_only():
    if not os.path.ismount("/efi") and not os.path.ismount("/boot"):
        cmd = 'chattr +i /efi'
        execute(cmd, desc=f'make host /efi only a mountpoint')
        cmd = 'chattr +i /boot'
        execute(cmd, desc=f'make host /efi only a mountpoint')


def get_uuid_by_dev(dev_name):
    cmd = f'lsblk -n -oNAME,UUID {dev_name} --raw'
    return subprocess.run(cmd, shell=True, capture_output=True).stdout.decode("utf-8") \
        .strip().split('\n')[0].split(' ')[-1].strip()

def dongle_umount_all():
    umount("/efi")
    umount("/boot")
    umount("/mnt/iso")
    lock("dongleboot")
    lock("donglepersist")

    good("system mounts are now clean, safe to remove dongle")
