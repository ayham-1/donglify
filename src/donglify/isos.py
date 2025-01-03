import os
import pathlib

from donglify.lib import *
from donglify.grub import *

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

from donglify.config import *

def dongle_iso_list():
    if len(DonglifyState.isos.items()) == 0:
        print("no isos are added to dongle")
        return

    for name, iso in DonglifyState.isos.items():
        print()
        print(f'name: {name}')
        print(f'file_name: {iso.file_name}')
        print(f'loopback_cfg_location: {iso.loopback_cfg_location}')


def dongle_iso_add():
    dest = "/mnt/iso"
    mount(DonglifyState.config.part_iso_uuid, dest)
    isos = os.listdir(dest)

    name = input("Name of the system to be added: ")

    iso: DongleISO = DongleISOValidator.validate_python({
        "file_name": prompt(
            "Filename of the iso on ISOs partition (must be in root of ISOs partition): ",
            completer=WordCompleter(isos)),
        "loopback_cfg_location": input(
            "loopback.cfg location in ISO [/boot/grub/loopback.cfg]: ") or "/boot/grub/loopback.cfg"
    })

    DonglifyState.isos[name] = iso

    grub_config_install()
    DonglifyState.write()


def dongle_iso_list_templates():
    print("available iso grub configuration templates: ")
    subprocess.run("ls grub.d/isos/", shell=True)
