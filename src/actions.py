import os
import platform
import sys
import getpass
from jinja2 import Template
from dotenv import load_dotenv; load_dotenv()
from openai import OpenAI
import re
import subprocess
import threading
import time
import googlesearch

client = OpenAI(
    api_key = os.getenv("GEMINI_API_KEY"),
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai/",
)

MODEL = "gemini-2.5-flash"

def is_admin():
    try:
        # Windows
        if os.name == 'nt':
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        # Unix-like
        else:
            return os.geteuid() == 0
    except AttributeError:
        # os.geteuid() not available on some platforms
        return False
    
sys_prompt = """
You are Jasper, an AI assistant. You have full operating control over the computer you are being run on.

INFO:

- System: {{ system }}
- Version: {{ version }}
- Release: {{ release }}

- Admin Access: {{ is_admin }}

- Current User: {{ user }}
- Device Name: {{ device_name }}

INSTRUCTIONS:

To assist the user, you have the ability to perform actions on the computer.
To do this, you may use:

- Shell Scripts
- Python Code
- Mouse/Keyboard input (via pyautogui)
- Network Requests (via requests)

You can also get creative with platform specific tools. For example, if you are on Windows and the user asks to change their wallpaper, you can use ctypes to do so.
Alternatively, if you are on Linux, you can execute shell commands to do many things.
Also, if you want to execute Python code but a library is not installed, you can simply use shell commands to `pip install` it.

To run code, you will wrap code within custom markdown codeblocks.
To execute a shell command:

```execute:sh
echo "Hello!"
```
(This can be just a single command, or a multiline script)

To execute a single line in a terminal environment (you can use things like `cd` here):
```execute:cmd
cd ~/
```


Or, to execute Python code:

```execute:py
print("Hello!")
```

Whenever you execute a command, you will receive the process output as well as exit code, so that you can decide on what to do next.
You should only execute one piece of code at a time, so that you can use the previous output to decide whether you should continue or change.
For safety, the timeout for all code execution is limited to 10 seconds.
The user can see neither your commands being sent nor the command output; it is up to you to explain the command output to the user.

You should think outside the box when being asked to do something that you initially perceive as impossible.
For instance, if the user asks you to close the Settings window, instead of saying that your current tools do not allow you to do so, you should come up with a solution.
In this scenario, a solution would be to use shell to `pip install pygetwindow`, then execute a python snippet that uses pygetwindow to close the window.

For web search, you can also use this:

```execute:search
query
```
"""

prompt = Template(sys_prompt).render(
    system = platform.system(),
    version = platform.version(),
    release = platform.release(),
    is_admin = is_admin(),
    user = getpass.getuser(),
    device_name = platform.node(),
)


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

def strip_codeblocks(text):
    # Remove all execute code blocks from the text
    pattern = r"```execute:\w+\n.*?```"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()


def process_output(text):
    # Extract all ```execute:<lang> ... ``` blocks from the text
    pattern = r"```execute:(\w+)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return matches  # List of tuples: (lang, code)

def execute_code(command_tuple):
    lang, code = command_tuple
    if lang == "sh":
        result = subprocess.run(code, shell=True, capture_output=True, text=True)
        return result.stdout + result.stderr
    elif lang == "py":
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout + result.stderr
        except Exception as e:
            return f"Python exec error: {e}"
    elif lang == "cmd":
        result = subprocess.run(code, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout + result.stderr
    elif lang == "search":
        res = "## Search Results"
        results = googlesearch.search(code, advanced=True)
        for result in results:
             res += f"\n### {result.title}\n{result.url}\n{result.description}"
        return res
    else:
        return f"Unknown execution language: {lang}"

chat_history = [{
    "role": "system",
    "content": prompt
}]

while True:
    inp = input(">> ")
    chat_history.append({
        "role": "user",
        "content": inp
    })
    res = client.chat.completions.create(
        model=MODEL,
        messages=chat_history,
    )
    output = res.choices[0].message.content
    chat_history.append({
        "role": "assistant",
        "content": output
    })

    commands = process_output(output)
    while commands:
        print(strip_codeblocks(output))
        responses = "SYSTEM: Command Output:\n\n"
        for command in commands:
            stop_spinner = spinner()
            try:
                res = execute_code(command)
            finally:
                stop_spinner()
            responses += res + "\n"
        responses += "All commands executed."
        
        chat_history.append({"role": "user", "content": responses})
        res = client.chat.completions.create(
            model=MODEL,
            messages=chat_history,
        )
        output = res.choices[0].message.content
        commands = process_output(output)
    print(strip_codeblocks(output))
    