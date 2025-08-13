from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, InternalServerError
import os
import platform
import sys
import getpass
from jinja2 import Template
from dotenv import load_dotenv; load_dotenv()
from google import genai
from google.genai import types
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
        pattern = r"
