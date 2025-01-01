import shutil
import pathlib

from donglify.lib import *
from donglify.config import *

class DongleGrub:
    @staticmethod
    def encrypted_install():
        shutil.move("/etc/default/grub", "/etc/default/grub.bak")
    
        template = get_asset_data("templates/defaultgrub").decode('utf-8')
        pathlib.Path("/etc/default/grub").write_text(template)
    
        cmd = f'grub-install --target=x86_64-efi --efi-directory=/efi --bootloader-id=GRUB --removable'
        execute(cmd, desc="install grub into dongle")
    
        shutil.move("/etc/default/grub.bak", "/etc/default/grub")

    @staticmethod
    def config_install():
        grubcfg = get_asset_data("grub.d/header.cfg").decode('utf-8')
    
        for name, config in DonglifyState.installs.items():
            template = get_asset_data("grub.d/system.cfg").decode('utf-8')
            template_line = template.replace("{name}", name.replace("iso.", ''))
            template_line = template_line.replace("{kernel_args}", config.kernel_args)
            template_line = template_line.replace("{kernel_version}", config.kernel_version)
    
            grubcfg += template_line
    
        for name, iso in DonglifyState.isos.items():
            template = get_asset_data("grub.d/isos/loopback.cfg").decode('utf-8')
            template_line = template.replace("{name}", name.replace("iso.", ''))
            template_line = template_line.replace("{file_name}", iso.file_name)
            template_line = template_line.replace("{loopback_cfg_location}", iso.loopback_cfg_location)
            grubcfg += template_line
        
        pathlib.Path("/boot/grub/grub.cfg").write_text(grubcfg)
    
        unicodepf2 = get_asset_data("unicode.pf2")
        with open("/boot/grub/unicode.pf2", "wb") as f:
            f.write(unicodepf2)
    
        good("grub.cfg has been written")
