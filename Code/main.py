import board
import busio
import time
import digitalio
from adafruit_ds3231 import DS3231

# I2C for RTC (SDA=GPIO18, SCL=GPIO19)
i2c = busio.I2C(scl=board.GP19, sda=board.GP18)
rtc = DS3231(i2c)

# 74HC595 shift registers for 8 7-segment displays
# SCK=GPIO0 (clock), DIO=GPIO1 (data), RCK=GPIO2 (latch)
sck = digitalio.DigitalInOut(board.GP0)
sck.direction = digitalio.Direction.OUTPUT

dio = digitalio.DigitalInOut(board.GP1)
dio.direction = digitalio.Direction.OUTPUT

rck = digitalio.DigitalInOut(board.GP2)
rck.direction = digitalio.Direction.OUTPUT

# 7-segment display patterns (common cathode, DP on bit 7)
SEGMENTS = {
    0: 0b00111111,  # 0
    1: 0b00000110,  # 1
    2: 0b01011011,  # 2
    3: 0b01001111,  # 3
    4: 0b01100110,  # 4
    5: 0b01101101,  # 5
    6: 0b01111101,  # 6
    7: 0b00000111,  # 7
    8: 0b01111111,  # 8
    9: 0b01101111,  # 9
    10: 0b00000000  # blank
}

# Pushbuttons (GPIO16 and GPIO17, pulled to GND)
button_left = digitalio.DigitalInOut(board.GP16)
button_left.direction = digitalio.Direction.INPUT
button_left.pull = digitalio.Pull.UP

button_right = digitalio.DigitalInOut(board.GP17)
button_right.direction = digitalio.Direction.INPUT
button_right.pull = digitalio.Pull.UP

# Timer state (in seconds)
time_remaining = 0
setting_mode = False
blink_state = False
blink_time = 0
display_buffer = [10, 10, 10, 10, 10, 10, 10, 10]

def shift_out_byte(byte):
    """Shift out 8 bits to 74HC595"""
    for i in range(8):
        dio.value = (byte >> (7 - i)) & 1
        time.sleep(0.00005)
        sck.value = 1
        time.sleep(0.00005)
        sck.value = 0

def latch():
    """Latch data into output registers"""
    rck.value = 1
    time.sleep(0.0001)
    rck.value = 0

def shift_out_bytes(bytes_list):
    """Shift out multiple bytes (for chaining 74HC595s)"""
    for byte in reversed(bytes_list):  # Reverse for correct bit order
        shift_out_byte(byte)
    latch()

def seconds_to_display(seconds):
    """Convert seconds to day:hour:minute:second format"""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return days, hours, minutes, secs

def update_display(days, hours, minutes, secs):
    """Update display buffer with DD:HH:MM:SS"""
    global display_buffer
    display_buffer = [
        days // 10,
        days % 10,
        hours // 10,
        hours % 10,
        minutes // 10,
        minutes % 10,
        secs // 10,
        secs % 10
    ]

def render_display():
    """Send display buffer to 74HC595s"""
    segments = [SEGMENTS.get(d, SEGMENTS[10]) for d in display_buffer]
    shift_out_bytes(segments)

def display_blink():
    """Blink display when timer reaches 0"""
    global blink_state, blink_time
    current_time = time.monotonic()
    if current_time - blink_time > 0.5:
        blink_state = not blink_state
        blink_time = current_time
        if blink_state:
            display_buffer[:] = [10] * 8
        else:
            update_display(0, 0, 0, 0)
    render_display()

def check_both_buttons_held():
    """Check if both buttons are held down"""
    return not button_left.value and not button_right.value

# Main loop
last_second_update = time.monotonic()
left_pressed = False
right_pressed = False
button_held_time = 0

while True:
    current_time = time.monotonic()
    both_held = check_both_buttons_held()
    
    # Enter/exit setting mode
    if both_held and not setting_mode:
        setting_mode = True
        button_held_time = current_time
    elif setting_mode and not both_held:
        setting_mode = False
    
    if setting_mode:
        # In setting mode - adjust time with button presses
        if not button_left.value and not left_pressed:
            # Left button: add hour
            left_pressed = True
            time_remaining = min(time_remaining + 3600, 9999999)
            print(f"Timer: {time_remaining}s (+1h)")
            time.sleep(0.1)
        elif button_left.value:
            left_pressed = False
        
        if not button_right.value and not right_pressed:
            # Right button: add minute (reset seconds), or add day if held
            right_pressed = True
            hold_duration = current_time - button_held_time
            if hold_duration > 1.0:
                # Long hold: add day
                time_remaining = min(time_remaining + 86400, 9999999)
                print(f"Timer: {time_remaining}s (+1d)")
            else:
                # Short press: add minute, reset seconds
                time_remaining = (time_remaining // 60 + 1) * 60
                time_remaining = min(time_remaining, 9999999)
                print(f"Timer: {time_remaining}s (+1m)")
            time.sleep(0.1)
        elif button_right.value:
            right_pressed = False
        
        # Display time being set
        days, hours, minutes, secs = seconds_to_display(time_remaining)
        update_display(days, hours, minutes, secs)
        render_display()
    
    else:
        # Normal countdown mode
        if current_time - last_second_update >= 1.0:
            if time_remaining > 0:
                time_remaining -= 1
            last_second_update = current_time
        
        # Display countdown or blink
        if time_remaining > 0:
            days, hours, minutes, secs = seconds_to_display(time_remaining)
            update_display(days, hours, minutes, secs)
            render_display()
        else:
            display_blink()
