# nwg-panel

This application is a part of the [nwg-shell](https://github.com/nwg-piotr/nwg-shell) project.

I have been using sway since 2019 and find it the most comfortable working environment, but... 
Have you ever missed all the graphical bells and whistles in your panel, we used to have in tint2? It happens to me. 
That's why I decided to try to code a GTK-based panel, including best features from my two favourites: 
[Waybar](https://github.com/Alexays/Waybar) and [tint2](https://gitlab.com/o9000/tint2). Many thanks to Developers
and Contributors of the both projects!

There are 12 modules available at the moment, and I don't plan on many more. Basis system controls are available in the 
Controls module, and whatever else you may need, 
[there's an executor for that](https://github.com/nwg-piotr/nwg-panel/wiki/Some-useful-executors).

![v015.png](https://raw.githubusercontent.com/nwg-piotr/nwg-shell/main/images/nwg-shell/nwg-panel1.png)

[![Packaging status](https://repology.org/badge/vertical-allrepos/nwg-panel.svg)](https://repology.org/project/nwg-panel/versions)

## Modules

### Controls

Panel widget with a popup window, including sliders, some system info, user-defined rows 
and customizable menu *(top right in the picture)*.

### SwayNC

Provides integration of the Eric Reider's [Sway Notification Center](https://github.com/ErikReider/SwayNotificationCenter).

### Tray

Supports SNI based system tray.

### Clock

Just a label to show the `date` command output in the format of your choice *(top center)*.

### Playerctl

Set of buttons, and a label to control mpris media player with the 
[Playerctl utility](https://github.com/altdesktop/playerctl) *(top left)*.

### SwayTaskbar 

Shows tasks from a selected or all outputs, with the program icon and name; allows switching between them,
toggle the container layout (`tabbed stacking splitv splith`) with the mouse scroller, move to workspaces,
toggle floating and kill with the right-click menu *(bottom left)*;

### SwayWorkspaces

Set of textual buttons to switch between workspaces, and a label to see the current task icon and title.

### Scratchpad

Displays clickable icons representing windows moved to the sway scratchpad;

### DWL Tags

The DwlTags module displays tags (free, occupied, selected), layout and the active window name from the dwl Wayland 
compositor. The `nwg-dwl-interface` command provides dwl -> panel communication. It also executes the autostart script, 
if found.

### Executor 

The Executor module displays an icon, and a label on the basis of a script output, in user-defined intervals.

### CustomButton 

Simple Gtk.Button with an icon, and a command assigned to it *(top left corner)*;

### MenuStart

Allows defining settings for the Menu Start plugin.

See [Wiki](https://github.com/nwg-piotr/nwg-panel/wiki) for more information. You'll also find some useful
executor examples there.
