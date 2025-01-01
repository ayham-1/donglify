#!/bin/python3

from prompt_toolkit import prompt
from prompt_toolkit.completion import NestedCompleter
import sys
import subprocess
import signal

from termcolor import colored

from donglify.lib import *
from donglify.boot import *
from donglify.grub import *
from donglify.isos import *
from donglify.config import *
from donglify.partition import *

# TODO: do real cleanup

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
    DonglePartitions.mount_all()
    DonglifyBoot.configure_sys(current_install_name)
    DongleGrub.config_install()


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
    DonglePartitions.mount_all()
    execute(cmd, "Runs user given system update command.")
    dongle_install_system(name)

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
        DonglePartitions.init_device(sys.argv[2])
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
        DonglePartitions.mount_all()
        while 1:
            print(colored("available commands: " +
                  ' '.join(donglify_cmds), 'dark_grey'))
            user_input = prompt("donglify> ", completer=NestedCompleter.from_nested_dict(donglify_cmds))
            if user_input == 'status':
                subprocess.run("lsblk", shell=True)
            elif user_input == 'list':
                dongle_list_installs()
            elif user_input == 'mount':
                DonglePartitions.mount_all()
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


if __name__ == "__main__":
    main()
