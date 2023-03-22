import requests
import json
import os

import urllib3
from bs4 import BeautifulSoup
import trafilatura
from simplegmail import Gmail

# Channel to send messages to all
CHANNEL_ID = -925069924

bot = None
# gmail = Gmail()

import yfinance

def send_message_to_all(text):
    bot.send_message(chat_id=CHANNEL_ID, text=text)


# def send_email(to, subj, text):
#     gmail = Gmail()  # will open a browser window to ask you to log in and authenticate

#     params = {
#         "to": to,
#         "sender": "rai220@gmail.com",
#         "subject": subj,
#         "msg_html": f"<p>{text}</p>",
#         "msg_plain": "text",
#         "signature": True  # use my account signature
#     }
#     message = gmail.send_message(**params)
