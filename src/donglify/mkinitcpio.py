import pathlib

from donglify.lib import *


def kernel_config_current_sys(current_install):
    template = get_asset_data("templates/mkinitcpio.conf").decode('utf-8')
    template = template.replace(
        "$CRYPTO_KEYFILE", current_install["cryptokeyfile"])
    template = template.replace(
        "$HOOKS_ADDED", current_install["hooks_added"])
    pathlib.Path("/etc/mkinitcpio.conf").write_text(template)
    print("wrote /etc/mkinitcpio.conf")
    
    KERNEL_NAME = current_install['kernel_name']
    UCODE_NAME = current_install['ucode']
    cmd = f'pacman -S --noconfirm {KERNEL_NAME} {UCODE_NAME} mkinitcpio'
    execute(cmd, desc=f'install the kernel, microcode, and mkinitcpio',
            needed=True, ask=True)

    cmd = 'rm /boot/*fallback*'
    execute(cmd, desc=f'remove kernel fallback images', needed=True, ask=True)

    # rename the newly installed images
    new_kernel_image_path = f'/boot/vmlinuz-{current_install["name"]}'
    new_initramfs_image_path = f'/boot/initramfs-{current_install["name"]}.img'
    new_ucode_image_path = f'/boot/{UCODE_NAME}-{current_install["name"]}.img'

    cmd = f"mv -f /boot/vmlinuz-{KERNEL_NAME} {new_kernel_image_path}"
    execute(cmd, desc=f'rename linux kernel image', needed=True, ask=True)
    cmd = f"mv -f /boot/initramfs-{KERNEL_NAME}.img {new_initramfs_image_path}"
    execute(cmd, desc=f'rename initramfs image', needed=True, ask=True)
    cmd = f"mv -f /boot/{UCODE_NAME}.img {new_ucode_image_path}"
    execute(cmd, desc=f'rename microcode image', needed=True, ask=True)

    DonglifyState.installs_configs[current_install["name"]][DONGLE_INSTALL_KERNEL_VERSION] = subprocess.run(f"""pacman -Qi {KERNEL_NAME} | grep -Po '^Version\s*: \K.+'""", shell=True, capture_output=True).stdout.decode('utf-8').strip()
    dongle_save_config()

    good("kernel & initramfs should be correctly positioned in /boot for detection by 'grub-mkconfig' now")
