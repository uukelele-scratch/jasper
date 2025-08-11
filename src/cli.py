import sys
import time
import threading
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import print_formatted_text

def spinner(message="Executing code..."):
    spinner_chars = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
    done = False

    def spin():
        i = 0
        while not done:
            sys.stdout.write(f'\r\033[33m{spinner_chars[i % len(spinner_chars)]} {message}\033\033[0m')
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
        with patch_stdout(): # Ensure print works correctly with prompt_toolkit
            print(info["message"])
    
    if info.get("state"):
        map = {
            "idle": None,
            "thinking": "Thinking...",
            "executing": "Executing code...",
            "searching": "Searching the web...",
            "analysing": "Analysing files...",
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

# Initialize PromptSession outside the loop
session = PromptSession()

while True:
    # Use prompt_toolkit for input with placeholder text and patch stdout
    with patch_stdout():
        inp = session.prompt(">> ", placeholder=HTML('<ansigray>Type a message or \'/help\' for options.</ansigray>'))
    
    # Only send message if input is not empty after stripping whitespace
    if inp.strip() == "":
        continue # Skip empty input

    if inp.startswith('/'):
        command = inp[1:].strip() # Get command without the leading slash
        if command == "help":
            with patch_stdout():
                print("Available commands:")
                print("  /help   - Display this help message.")
                print("  /clear  - Clear the conversation history.")
                print("  /exit   - Exit the application.")
        elif command == "clear":
            jasper.messages = [] # Clear the message history
            with patch_stdout():
                print("Conversation history cleared.")
        elif command == "exit":
            with patch_stdout():
                print("Exiting application. Goodbye!")
            sys.exit(0) # Exit the script
        else:
            with patch_stdout():
                print_formatted_text(HTML(f'<ansired>Command not found: \'{inp}\'. Type \'/help\' for a list of commands.</ansired>'))
    else:
        jasper.send_message(inp)
