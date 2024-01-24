import shutil
import pathlib

from donglify.lib import *


def grub_encrypted_install():
    # this function should be run without any installed linux kernels
    # this function assumes all mounts are correct

    shutil.move("/etc/default/grub", "/etc/default/grub.bak")

    template = get_asset_data("templates/defaulgrub").decode('utf-8')
    pathlib.Path("/etc/default/grub").write_text(template)

    cmd = f'grub-install --target=x86_64-efi --efi-directory=/efi --bootloader-id=GRUB --removable'
    execute(cmd, desc="install grub into dongle", needed=True, ask=True)

    shutil.move("/etc/default/grub.bak", "/etc/default/grub")


def grub_config_install():
    # this function assumes that all mounts are correct
    # this function configures grub to recognize the installed systems on the dongle

    grubcfg = get_asset_data("grub.d/header.cfg").decode('utf-8')

    for name, config in DonglifyState.installs_configs.items():
        template = get_asset_data("grub.d/system.cfg").decode('utf-8')
        grubcfg += template.replace("{name}", name).replace(
            "{kernel_args}", config["kernel_args"])

    for name, iso in DonglifyState.isos.items():
        template = get_asset_data("grub.d/isos/loopback.cfg").decode('utf-8')
        grubcfg += template.replace("{name}", name.replace("iso.", '')) \
        .replace("{file_name}", iso["file_name"]) \
        .replace("{loopback_cfg_location}", iso["loopback_cfg_location"])

    pathlib.Path("/boot/grub/grub.cfg").write_text(grubcfg)

    unicodepf2 = get_asset_data("unicode.pf2")
    with open("/boot/grub/unicode.pf2", "wb") as f:
        f.write(unicodepf2)

    #shutil.copy("assets/unicode.pf2", "/boot/grub/unicode.pf2")
    good("grub.cfg has been written")
