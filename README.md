<img src="https://github.com/nwg-piotr/nwg-panel/assets/20579136/36327f89-05b8-420d-998a-8f5f7d385545" width="90" style="margin-right:10px" align=left alt="nwg-shell logo">
<H1>nwg-panel</H1><br>

This application is a part of the [nwg-shell](https://nwg-piotr.github.io/nwg-shell) project.

**Nwg-panel** is a GTK3-based panel for [sway](https://github.com/swaywm/sway) and [Hyprland](https://github.com/hyprwm/Hyprland) 
Wayland compositors. The panel is equipped with a graphical configuration program that frees the user from the need to 
manually edit configuration files.

<img src="https://github.com/nwg-piotr/nwg-panel/assets/20579136/09866188-6819-4dfb-99df-40af53be859b" width=640><br>

<img src="https://github.com/nwg-piotr/nwg-panel/assets/20579136/1aeb8990-f355-4ba9-80e3-9aa2a46730ca" width=640><br>

Currently, we have a dozen of modules, and we don't plan on many more. Many minor tasks that users request a module for,
may be easily done with [executors](https://github.com/nwg-piotr/nwg-panel/wiki/modules:-Executor).

- **Controls module**: basis system controls like brightness slider, volume slider (w/ per-app sliders), battery 
level w/ low level notification, system processes viewer, user-defined custom items, user-defined drop-down menu 
(which is the power menu by default)
- **Brightness slider**: a separate brightness slider for use per monitor; features backlight via ddcutil.
- **Clock**: system clock w/ a calendar popup built in
- **Custom button**: a user-defined graphical/textual button you could bind an action to. By default, we use one as the 
application launcher button
- **DWL tags**: deprecated and no longer supported; will be deleted in the future
- **Executor**: a useful module that executes user-provided code and displays the output in the panel as an icon and 
text; see Wiki for more info
- **Sway taskbar & Hyprland taskbar**: highly customizable modules to display a label with an icon for every running 
window, together with some more info (workspace number, split orientation on sway, X-widows marker); right click opens 
a menu that allows to move windows between workspaces, toggle floating and fullscreen, and also close windows.
- **Sway & Hyprland workspaces**: display labels to navigate between workspaces with a marker for non-empty ones; next
to the labels there's a field with currently focused window details
- **Menu Start**: module provides integration of the XGD-style [nwg-menu](https://github.com/nwg-piotr/nwg-menu)
- **Openweather**: displays weather forcast from OpenWeatherMap and weather alerts from weatherbit.io for given locations.
- **Playerctl**: displays an icon and a label of the currently played tune, together with back / play-pause / forward 
buttons
- **Scratchpad**: displays info on current scratchpad content and allows to open scratchpad windows 
- **SwayMode**: a simple indicator of a sway mode other than "default"
- **Tray**: SNI system tray module

## Installation

[![Packaging status](https://repology.org/badge/vertical-allrepos/nwg-panel.svg)](https://repology.org/project/nwg-panel/versions)

If nwg-panel has not yet been packaged for your Linux distribution, you may install it by cloning this repository
and running the `install.sh` script.

See [Wiki](https://github.com/nwg-piotr/nwg-panel/wiki) for more information. You'll also find some useful executor examples there.
