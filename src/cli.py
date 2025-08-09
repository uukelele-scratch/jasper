import sys
import time
import threading

def spinner(message="Executing code..."):
    spinner_chars = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
    done = False

    def spin():
        i = 0
        while not done:
            sys.stdout.write(f'\r{spinner_chars[i % len(spinner_chars)]} {message}')
            sys.stdout.flush()
            i += 1
            time.sleep(0.1)
        # Clear line after done
        sys.stdout.write('\r' + ' ' * (len(message) + 2) + '\r')
        sys.stdout.flush()

    t = threading.Thread(target=spin)
    t.start()

    def stop():
        nonlocal done
        done = True
        t.join()

    return stop


from actions import Jasper, client

current_spinner = [None]

def callback(info: dict):
    if info.get("message"):
        print(info["message"])
    
    if info.get("state"):
        map = {
            "idle": None,
            "thinking": "Thinking...",
            "executing": "Executing code...",
            "searching": "Searching the web..."
        }
        text = map.get(info["state"])
        if info["state"] == "idle" and current_spinner[0]:
            current_spinner[0]()
            current_spinner[0] = None
        elif text:
            if current_spinner[0]:
                current_spinner[0]()
            current_spinner[0] = spinner(text)

jasper = Jasper(client, callback=callback)

while True:
    inp = input(">> ")
    jasper.send_message(inp)