import pathlib

from donglify.lib import *

from donglify.config import *

class DonglifyBoot:
    @staticmethod
    def setup_mkinitcpio_config(name: str):
        print(name)
        current_install = DonglifyState.installs[name]
    
        template = get_asset_data("templates/mkinitcpio.conf").decode('utf-8')
        template = template.replace(
            "$CRYPTO_KEYFILE", current_install.cryptokeyfile)
        template = template.replace(
            "$HOOKS_ADDED", current_install.hooks_added)
        pathlib.Path("/etc/mkinitcpio.conf").write_text(template)
        good("wrote /etc/mkinitcpio.conf")
    
        hook = get_asset_data("sd-sulogin.initramfs.hook").decode('utf-8')
        pathlib.Path("/etc/initcpio/install/sd-sulogin").write_text(hook)
        good("wrote /etc/initcpio/install/sd-sulogin")
    
        shadow = get_asset_data("shadow.initramfs").decode('utf-8')
        pathlib.Path("/etc/shadow.initramfs").write_text(shadow)
        good("wrote /etc/shadow.initramfs")

    @staticmethod 
    def configure_sys(current_install_name: str):
        DonglifyBoot.setup_mkinitcpio_config(current_install_name)
            
        current_install = DonglifyState.installs[current_install_name]
        KERNEL_NAME = current_install.kernel_name
        UCODE_NAME = current_install.ucode
        cmd = f'pacman -S --noconfirm {KERNEL_NAME} {UCODE_NAME} mkinitcpio'
        execute(cmd, desc=f'install the kernel, microcode, and mkinitcpio')
    
        cmd = 'rm /boot/*fallback*'
        execute(cmd, desc=f'remove kernel fallback images')
    
        # rename the newly installed images
        new_kernel_image_path = f'/boot/vmlinuz-{current_install_name}'
        new_initramfs_image_path = f'/boot/initramfs-{current_install_name}.img'
        new_ucode_image_path = f'/boot/{UCODE_NAME}-{current_install_name}.img'
    
        cmd = f"mv -f /boot/vmlinuz-{KERNEL_NAME} {new_kernel_image_path}"
        execute(cmd, desc=f'rename linux kernel image')
        cmd = f"mv -f /boot/initramfs-{KERNEL_NAME}.img {new_initramfs_image_path}"
        execute(cmd, desc=f'rename initramfs image')
        cmd = f"mv -f /boot/{UCODE_NAME}.img {new_ucode_image_path}"
        execute(cmd, desc=f'rename microcode image')
    
        DonglifyState.installs[current_install_name].kernel_version =  \
            subprocess.run(f"pacman -Q {KERNEL_NAME}", 
                           shell=True, capture_output=True).stdout.decode('utf-8').strip().split(" ")[1]
        DonglifyState.write()
    
        good("kernel & initramfs should be correctly positioned in /boot for detection by 'grub-mkconfig' now")
    
        #clean_mkinitcpio_config(current_install)
