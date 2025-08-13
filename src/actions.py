from google.api_core.exceptions import ResourceExhausted
import os
import platform
import sys
import getpass
from jinja2 import Template
from dotenv import load_dotenv; load_dotenv()
from google import genai
from google.genai import types, errors
import re
import subprocess
import threading
import time
import googlesearch
from typing import Callable
import json
from jsonpath_ng import jsonpath, parse
from base64 import b64encode

client = genai.Client(
    api_key = os.getenv("GEMINI_API_KEY"),
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
    def __init__(self, client: genai.Client, model: str = "gemini-2.5-flash", callback: Callable = None, overrides: dict = {}):
        self.client = client
        self.model = os.getenv("GEMINI_MODEL") or model
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

        self.messages = []

        self.generation_config = types.GenerateContentConfig(
            system_instruction=self.prompt
        )

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
        elif lang.startswith("analyse"):
            _, mimetype = lang.split(":")
            mimetype = mimetype.strip().lower()
            filepath = code.strip()
            if mimetype == "text/plain":
                return f"File: {filepath}\n\n{open(filepath).read()}"
            data = open(filepath, 'rb').read()
            filepart = types.Part.from_bytes(
                data=data,
                mime_type=mimetype,
            )
            contents = types.Content(
                role = "user",
                parts = [
                    filepart,
                    types.Part(text = f"File: {filepath}\nMimetype: {mimetype}")
                ]
            )
            self.messages.append(contents)
            return "The file has been attached for you to work with."
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
        

    def _generate_content_with_retries(self, contents):
        while True:
            try:
                res = self.client.models.generate_content(
                    model = self.model,
                    contents = contents,
                    config = self.generation_config,
                )
                return res
            except errors.ClientError as e:
                if e.status_code == 429 and "RESOURCE_EXHAUSTED" in str(e):
                    print("API rate limited. Waiting 60 seconds before retrying...")
                    import time # Ensure time is imported here if not global
                    time.sleep(60) # Wait for 1 minute
                else:
                    raise # Re-raise other client errors
            except Exception as e:
                print(f"An unexpected error occurred during content generation: {e}")
                raise # Re-raise other unexpected errors

    def send_message(self, message):
        self.messages.append(types.Content(
            role = "user",
            parts = [
                types.Part(text = message)
            ],
        ))
        self.callback({"state":"thinking"})
        res = self._generate_content_with_retries(self.messages)
        self.callback({"state":"idle"})
        output = res.text
        if DEBUG: print(output)
        self.messages.append(types.Content(
            role = "model",
            parts = [
                types.Part(text = output)
            ],
        ))
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
            responses += "All commands executed. Remember that the user cannot see this output and cannot see your command(s) either, so you must explain it to them if necessary."
            if DEBUG: print(responses)
            
            self.messages.append(types.Content(role="user", parts=[types.Part(text=responses)]))
            self.callback({"state":"thinking"})
            max_retries = 3
                    for attempt in range(max_retries):
                        try:
            res = self.client.models.generate_content(
                                model=self.model,
                                contents=self.messages,
                                config=self.generation_config,
                            )
                            self.callback({"state":"idle"})
                            break # If successful, break out of the retry loop
                        except google.genai.errors.ClientError as e:
                            if e.status_code == 429 and "RESOURCE_EXHAUSTED" in str(e):
                                wait_time = 60 # Default wait time in seconds
                                # print(f"[!] Rate limit exceeded. Waiting {wait_time} seconds before retrying... (Attempt {attempt + 1}/{max_retries})") # Removed print, handled by callback
                                self.callback({"message": f"Rate limit exceeded. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})"})
                                time.sleep(wait_time)
                            else:
                                self.callback({"state":"idle"})
                                raise e # Re-raise other ClientErrors
                        except Exception as e:
                            self.callback({"state":"idle"})
                            raise e # Catch any other unexpected errors
                    else:
                        self.callback({"state":"idle"})
                        raise Exception("Failed to generate content after multiple retries due to rate limiting.")
            output = res.text
            if DEBUG: print(output)
            commands = self._process_output(output)
        self.callback({"message": self._strip_codeblocks(output)})