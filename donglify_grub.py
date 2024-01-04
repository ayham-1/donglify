import shutil
import pathlib

from donglify_lib import *


def grub_encrypted_install():
    # this function should be run without any installed linux kernels
    # this function assumes all mounts are correct

    shutil.move("/etc/default/grub", "/etc/default/grub.bak")

    with open("templates/defaultgrub", "r") as defaultgrub:
        template = defaultgrub.read()
        pathlib.Path("/etc/default/grub").write_text(template)

    cmd = f'grub-install --target=x86_64-efi --efi-directory=/efi --bootloader-id=GRUB --removable'
    execute(cmd, desc="install grub into dongle", needed=True, ask=True)

    shutil.move("/etc/default/grub.bak", "/etc/default/grub")


def grub_config_install():
    # this function assumes that all monuts are correct
    # this function configures grub to recognize the installed systems on the dongle

    grubcfg = ""

    with open("grub.d/header.cfg", "r") as template:
        grubcfg += template.read()

    for name, config in DonglifyState.installs_configs.items():

        with open("grub.d/system.cfg", "r") as template:
            grubcfg += template.read().replace("{name}", name).replace(
                "{kernel_args}", config["kernel_args"])

    for name, iso in DonglifyState.isos.items():

        with open("grub.d/isos/loopback.cfg", "r") as template:
            grubcfg += template.read().replace("{name}", name.replace("iso.", '')) \
                .replace("{file_name}", iso["file_name"]) \
                .replace("{loopback_cfg_location}", iso["loopback_cfg_location"])

    pathlib.Path("/boot/grub/grub.cfg").write_text(grubcfg)
    shutil.copy("unicode.pf2", "/boot/grub/unicode.pf2")
    good("grub.cfg has been written")


if __name__ == "__main__":
    print("this script is not to be meant run alone, use main script")
    sys.exit(1)
