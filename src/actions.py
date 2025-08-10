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
from typing import Callable
import json
from jsonpath_ng import jsonpath, parse

client = OpenAI(
    api_key = os.getenv("GEMINI_API_KEY"),
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai/",
)

DEBUG = bool(os.getenv("DEBUG")) or False
if DEBUG: print("[+] Debug mode is enabled.")

MEMORY_FILE = "memory.json"

def write_memory(data): return json.dump(data, open(MEMORY_FILE, 'w'))
def read_memory(): return json.load(open(MEMORY_FILE))

if not os.path.exists(MEMORY_FILE):
    print("[+] Memory file does not exist. Initialising new session.")
    write_memory({})

class Jasper:
    def __init__(self, client: OpenAI, model: str = "gemini-2.5-flash", callback: Callable = None, overrides: dict = {}):
        self.client = client
        self.model = model
        self.callback = callback or (lambda *a, **k: None)
        
        self.sys_prompt = open("sys_prompt.md").read()

        self.prompt = Template(self.sys_prompt).render(
            system = platform.system(),
            version = platform.version(),
            release = platform.release(),
            is_admin = self._is_admin(),
            user = getpass.getuser(),
            device_name = platform.node(),
            memory = read_memory(),
        )

        self.overrides = overrides

        if overrides.get("sys_prompt"):
            self.prompt += "\n" + overrides["sys_prompt"]

        self.messages = [{
            "role": "system",
            "content": self.prompt
        }]

    def _is_admin(self):
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

    def _strip_codeblocks(self, text):
        # Remove all execute code blocks from the text
        pattern = r"```execute:[^\n]+\n.*?```"
        return re.sub(pattern, "", text, flags=re.DOTALL).strip()
    
    def _process_output(self, text):
        # Extract all ```execute:<lang> ... ``` blocks from the text
        pattern = r"```execute:([^\n]+)\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        return matches  # List of tuples: (lang, code)
    
    def _execute_code(self, command_tuple):
        lang, code = command_tuple
        if lang == "sh":
            self.callback({"state": "executing"})
            result = subprocess.run(code, shell=True, capture_output=True, text=True, timeout=10)
            self.callback({"state":"idle"})
            return result.stdout + result.stderr
        elif lang == "py":
            self.callback({"state": "executing"})
            try:
                result = subprocess.run(
                    [sys.executable, "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                self.callback({"state":"idle"})
                return result.stdout + result.stderr
            except Exception as e:
                self.callback({"state":"idle"})
                return f"Python exec error: {e}"
        elif lang == "search":
            res = "## Search Results"
            self.callback({"state":"searching"})
            results = googlesearch.search(code, advanced=True)
            self.callback({"state":"idle"})
            for result in results:
                res += f"\n### {result.title}\n{result.url}\n{result.description}"
            return res
        elif lang.startswith("memory"):
            command = lang.split(":")
            if len(command) > 3 or len(command) < 2:
                return "Invalid usage of memory tool. Refer to system prompt for usage guidelines."
            verb = command[1]
            if len(command) == 2 and verb == "fetch":
                return str(read_memory())
            elif verb == "fetch":
                path = command[2]
                path = parse(path)
                matches = path.find(read_memory())
                values = [match.value for match in matches]
                return str(values)
            elif verb == "store":
                if len(command) < 3:
                    return "Missing path for store command."
                path = command[2]
                mem = read_memory()

                def set_in_dict(data, path, value):
                    keys = path.split('.')
                    d = data
                    for key in keys[:-1]:
                        if key not in d or not isinstance(d[key], dict):
                            d[key] = {}
                        d = d[key]
                    d[keys[-1]] = value

                set_in_dict(mem, path, code.strip())
                write_memory(mem)
                return "Memory updated."
            
        elif self.overrides.get("execute") and self.overrides["execute"].get(lang):
            return self.overrides["execute"][lang](code)
        else:
            return f"Unknown execution language: {lang}"
        
    def send_message(self, message):
        self.messages.append({
            "role": "user",
            "content": message
        })
        self.callback({"state":"thinking"})
        res = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
        )
        self.callback({"state":"idle"})
        output = res.choices[0].message.content
        if DEBUG: print(output)
        self.messages.append({
            "role": "assistant",
            "content": output
        })
        commands = self._process_output(output)
        while commands:
            self.callback({"message": self._strip_codeblocks(output)})
            responses = "SYSTEM: Command Output:\n\n"
            for command in commands:
                try:
                    res = self._execute_code(command)
                except Exception as e:
                    res = f"Error executing: {e}"
                responses += res + "\n"
            responses += "All commands executed."
            if DEBUG: print(responses)
            
            self.messages.append({"role": "user", "content": responses})
            self.callback({"state":"thinking"})
            res = client.chat.completions.create(
                model=self.model,
                messages=self.messages,
            )
            self.callback({"state":"idle"})
            output = res.choices[0].message.content
            if DEBUG: print(output)
            commands = self._process_output(output)
        self.callback({"message": self._strip_codeblocks(output)})