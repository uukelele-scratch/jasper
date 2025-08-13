import sys
import time
import threading
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import print_formatted_text
from google.genai.errors import ClientError # Import ClientError

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


from google.genai import errors
import google.genai.errors
from actions import Jasper, client
import google.genai.errors
import google.genai.errors

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
        try:
        try:
        try:
            jasper.send_message(inp)
        except google.genai.errors.ClientError as e:
            if e.status_code == 429 and "RESOURCE_EXHAUSTED" in str(e):
                with patch_stdout():
                    print_formatted_text(HTML(
                        '<ansiyellow>It looks like you\'ve hit your API quota for the Gemini model. '
                        'Please wait a minute or two and try again, or check your Google Cloud project\'s '
                        'billing and quota settings if this issue persists. '
                        'More info: https://ai.google.dev/gemini-api/docs/rate-limits</ansiyellow>'
                    ))
            else:
                with patch_stdout():
                    print_formatted_text(HTML(f'<ansired>An unexpected API error occurred: {e}</ansired>'))
        except Exception as e:
            with patch_stdout():
                print_formatted_text(HTML(f'<ansired>An unexpected error occurred: {e}</ansired>'))
        except errors.ClientError as e:
            with patch_stdout():
                print_formatted_text(HTML(f'<ansired>An API error occurred: {e.message}. Please try again later or check your API quota.</ansired>'))
                if e.response and e.response.json():
                    error_details = e.response.json().get('error', {}).get('message', 'No additional details.')
                    print_formatted_text(HTML(f'<ansired>Details: {error_details}</ansired>'))
        except Exception as e:
            with patch_stdout():
                print_formatted_text(HTML(f'<ansired>An unexpected error occurred: {e}</ansired>'))
        except ClientError as e:
            with patch_stdout():
                if e.status_code == 429:
                    print_formatted_text(HTML('<ansired>API Quota Exceeded: You have made too many requests. Please wait a moment and try again, or check your Google Gemini API plan for more details.</ansired>'))
                else:
                    print_formatted_text(HTML(f'<ansired>An API error occurred: {e.message}</ansired>'))
        except Exception as e:
            with patch_stdout():
                print_formatted_text(HTML(f'<ansired>An unexpected error occurred: {e}</ansired>'))
