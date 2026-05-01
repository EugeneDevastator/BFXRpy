# uidemo.py - Simple demo to test UI components

import pyray as rl
import ui_components as ui

SCREEN_W = 1000
SCREEN_H = 700

def main():
    rl.init_window(SCREEN_W, SCREEN_H, "UI Components Demo")
    rl.set_target_fps(60)

    checkbox_checked = False
    slider_val = 0.5
    blend_t = 0.5
    editor = ui.TextEditor()
    editor.set_text("Type here...\nSecond line\nThird line\n\nUse arrow keys to move.\nClick to position cursor.")

    while not rl.window_should_close():
        rl.begin_drawing()
        rl.clear_background(rl.Color(240, 240, 240, 255))

        # Test button
        if ui.button(50, 50, 120, 40, "Click Me", rl.BLUE):
            print("Button clicked!")

        # Test checkbox
        checkbox_checked = ui.checkbox(50, 110, 24, "Enable", checkbox_checked)

        # Test horizontal slider
        slider_val = ui.hslider(50, 160, 200, 10, slider_val, "Volume")

        # Test blend slider
        blend_t, released = ui.blend_slider(50, 200, 40, 300, blend_t)
        if released:
            print("Blend slider released at %.2f" % blend_t)

        # Test text editor
        editor.update()
        editor.draw(300, 50, 400, 400)

        # Display values
        rl.draw_text("Checkbox: " + str(checkbox_checked), 50, 210, 20, rl.BLACK)
        rl.draw_text("Slider: %.2f" % slider_val, 50, 240, 20, rl.BLACK)
        rl.draw_text("Blend: %.2f" % blend_t, 50, 270, 20, rl.BLACK)
        rl.draw_text("Text Editor (click to activate):", 300, 30, 20, rl.BLACK)

        rl.end_drawing()

    rl.close_window()

if __name__ == "__main__":
    main()
