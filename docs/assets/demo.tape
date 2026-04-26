# VHS tape — animated demo for the README hero.
# Render with:  vhs docs/assets/demo.tape
# Output:       docs/assets/demo.gif
#
# All visible content is produced by demo.py so the recording stays clean
# (no shell prompts, no typed commands).

Output docs/assets/demo.gif

Set Theme "nord"
Set FontSize 14
Set Width 880
Set Height 480
Set Padding 24
Set Framerate 24
Set TypingSpeed 1ms
Set Shell "bash"

Hide
Type "clear && python3 docs/assets/demo.py"
Enter
Show
Sleep 16s
