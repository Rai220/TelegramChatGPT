import requests
import json
import os

import urllib3
from bs4 import BeautifulSoup
import trafilatura

# Channel to send messages to all
CHANNEL_ID = -925069924

bot = None

def get_text_from_url(url):
    downloaded = trafilatura.fetch_url(url)
    res = trafilatura.extract(downloaded)
    print(f"Text downloaded from {url}:/n{res}")
    return res

def send_message_to_all(text):
    bot.send_message(chat_id=CHANNEL_ID, text=text)
