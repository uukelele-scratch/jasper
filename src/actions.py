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

client = OpenAI(
    api_key = os.getenv("GEMINI_API_KEY"),
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai/",
)

DEBUG = bool(os.getenv("DEBUG")) or False

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
        pattern = r"```execute:\w+\n.*?```"
        return re.sub(pattern, "", text, flags=re.DOTALL).strip()
    
    def _process_output(self, text):
        # Extract all ```execute:<lang> ... ``` blocks from the text
        pattern = r"```execute:(\w+)\n(.*?)```"
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
                finally:
                    pass
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