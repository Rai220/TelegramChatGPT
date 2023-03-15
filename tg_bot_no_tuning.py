import telebot
import openai
import time
import tiktoken
import os

tokenizer = tiktoken.get_encoding("cl100k_base")

max_history = 3500 # Hstory will be truncated after this length

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Please set OPENAI_API_KEY environment variable")
    exit()

TG_TOKEN = os.getenv("TG_TOKEN")
if not TG_TOKEN:
    print("Please set TG_TOKEN environment variable")
    exit()

bot = telebot.TeleBot(TG_TOKEN)
openai.api_key = OPENAI_API_KEY
model = "gpt-3.5-turbo-0301"

users = {}

def _count_tokens(user):
    return sum([tokenizer.count_tokens(x['content']) for x in user['history']])


def _get_clear_history():
    current_date = time.strftime("%d.%m.%Y", time.localtime())
    return [{"role": "system", "content": f"Ты полезный ассистент с ИИ, который готов помочь своему пользователю. Ты даешь короткие содержательные ответы, обычно не более 100 символов. Сегодняшняя дата: {current_date}."}]


def _get_user(id):
    user = users.get(id, {'id': id, 'history': _get_clear_history(), 'last_prompt_time': 0})
    users[id] = user
    return user


def _process_rq(user_id, rq):
    user = _get_user(user_id)
    # if last prompt time > 60 minutes ago - drop context
    if time.time() - user['last_prompt_time'] > 60*60:
        last_text = ''
        user['last_prompt_time'] = 0
        user['history'] = _get_clear_history()

    if rq and len(rq) > 0 and len(rq) < 250:
        print(f">>> ({user_id}) {rq}")
        user['history'].append({"role": "user", "content": rq})
        while(_count_tokens(user) > max_history):
            user['history'].pop(0)

        completion = openai.ChatCompletion.create(
            model=model, messages=user['history'], temperature=0.7)
        ans = completion['choices'][0]['message']['content']
        print(f"<<< ({user_id}) {ans}")
        user['history'].append({"role": "user", "content": ans})
        user['last_prompt_time'] = time.time()
        return ans
    else:
        user['last_prompt_time'] = 0
        user['last_text'] = ''
        return "!!! Error! Please use simple short texts"


@bot.message_handler(commands=['start', 'help', 'clear'])
def send_welcome(message):
    user = _get_user(message.from_user.id)
    user['history'] = _get_clear_history()
    bot.reply_to(message, f"Started! (History cleared). Using model {model}")


@bot.message_handler(func=lambda message: True)
def process_message(message):
    user_id = message.from_user.id
    rq = message.text
    ans = _process_rq(user_id, rq)
    bot.send_message(message.chat.id, ans)


if __name__ == '__main__':
    bot.polling()
