import os
from setuptools import setup, find_packages


def read(f_name):
    return open(os.path.join(os.path.dirname(__file__), f_name)).read()


setup(
    name='nwg-panel',
    version='0.10.6',
    description='GTK3-based panel for sway and Hyprland Wayland compositors',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "": ["config/*", "icons_dark/*", "icons_light/*", "icons_color/*", "langs/*", "executors/*", "local/*",
             "modules/sni_system_tray/org.kde.StatusNotifierItem.xml"]
    },
    url='https://github.com/nwg-piotr/nwg-panel',
    license='MIT',
    author='Piotr Miller',
    author_email='nwg.piotr@gmail.com',
    python_requires='>=3.4.0',
    install_requires=['pygobject'],
    entry_points={
        'gui_scripts': [
            'nwg-panel = nwg_panel.main:main',
            'nwg-panel-config = nwg_panel.config:main',
            'nwg-dwl-interface = nwg_panel.dwl_interface:main',
            'nwg-processes = nwg_panel.processes:main'
        ]
    }
)
