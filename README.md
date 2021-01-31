# nwg-panel
I have been using sway since 2019 and find it the most comfortable working environment, but... 
Have you ever missed all the graphical bells and whistles in your panel, we used to have in tint2? I did. 
Finally, I decided to try to code my own panel, including best features from my two favourites: Waybar 
and Tint2. 

**Development status is alpha: errors are expected, breaking changes may, and probably will occur.**

I don't plan on many built-in modules. Basis system controls are available in the Controls module, 
and whatever else you may need, there's an Executor for that.

![gh.png](https://scrot.cloud/images/2021/02/01/gh.png)

## Modules - as for today

### Controls

Panel widget with a GNOME-like popup window, including sliders, some system info, user-defined rows 
and customizable menu (top right);

### SwayTaskbar 

Shows tasks from a selected or all outputs, with the program icon and name; allows switching between them,
toggle the container layout (`tabbed stacking splitv splith`) with the mouse scroller, move to workspaces,
toggle floating and kill with the right-click menu (bottom left);

### CustomButton 

Simple Gtk.Button with an icon, and a command assigned to it (top left corner);

### SwayWorkspaces

Not really necessary set of textual buttons to switch between workspaces (not in the picture);

### Clock

Just a label to show the `date` command output in the format of your choice (top center);

### Playerctl

Set of buttons, and a label to control mpris media player with the 
[Playerctl utility](https://github.com/altdesktop/playerctl) (top left);

### Executor 

Last but not least: the Executor module displays an icon, and a label on the basis of a script 
output, in user-defined intervals (bottom right, and the weather executor next to the clock).
