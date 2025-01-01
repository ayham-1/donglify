import sys
import subprocess

from termcolor import colored

from donglify.lib import *
from donglify.config import *
from donglify.grub import *

class DonglePartitions:
    @staticmethod
    def init_device(dev_name):
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
        DonglePartitions.mount_all()
        DongleGrub.encrypted_install()
    
        DonglifyState.write()
    
        subprocess.run("lsblk -f", shell=True)
        good("dongle's partition initialization done")
        tell("you are recommended to start adding system installs onto your dongle")
        sys.exit(0)


    @staticmethod
    def mount_all():
        mount(DonglifyState.config.efi_uuid, "/efi")
        unlock(DonglifyState.config.locked_boot_uuid, "dongleboot")
        mount(DonglifyState.config.unlocked_boot_uuid, "/boot")
        mount(DonglifyState.config.part_iso_uuid, "/mnt/iso")
        good("mounted all necessarily points from donglified usb")
    
    
