import json
import os
import time
import traceback
from contextlib import redirect_stdout
from io import StringIO

import flask
import openai
import telebot
import tiktoken

import gpt_utils
import random
import uuid


# Proxy server for accessing OpenAI API
app = flask.Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Please set OPENAI_API_KEY environment variable")
    exit()

TG_TOKEN = os.getenv("TG_TOKEN")
if not TG_TOKEN:
    print("Please set TG_TOKEN environment variable")
    exit()

AUTH_TOKEN = os.environ.get("AUTH_TOKEN", None)
if not AUTH_TOKEN:
    raise ValueError("AUTH_TOKEN must be set")

# Generate random secret
PREMIUM_SECRET = os.environ.get(
    "PREMIUM_SECRET", uuid.uuid4())
print(f"Bot secret: {PREMIUM_SECRET}")

mynames = ["@trololobot", "@кибердед", "trololo_bot",
           "кибердед", "кибердед,", "trololobot"]
# mynames = ["whentimecomesbot", "когдапридетвремя", "@whentimecomesbot",
#           "когдапридетвремя,", "времяпришло", "времяпришло,"]

port = os.environ.get("PORT", 8080)

tokenizer = tiktoken.get_encoding("cl100k_base")
max_history = 7500  # History will be truncated after this length

bot = telebot.TeleBot(TG_TOKEN)
openai.api_key = OPENAI_API_KEY
main_model = "gpt-4-0314"
cheap_model = "gpt-3.5-turbo"

# Load chats history from file
users = {}
if os.path.exists("users.json"):
    with open("users.json", "r") as f:
        users = json.load(f)


# log with optional exception
def _log(text, e=None):
    # Print to screen and log file
    print(text)
    if e and isinstance(e, Exception):
        print(traceback.format_exc())
    with open("log.txt", "a") as f:
        # Add date to text
        text = time.strftime("%d.%m.%Y %H:%M:%S",
                             time.localtime()) + " " + text
        print(text, file=f)


def _count_tokens(user):
    return sum([len(tokenizer.encode(x['content'])) for x in user['history']])


def _get_clear_history(user_id):
    current_date = time.strftime("%d.%m.%Y", time.localtime())
    common_start = f"""Ты полезный ассистент с ИИ, который готов помочь своему пользователю. Ты даешь короткие содержательные ответы, обычно не более 100 символов. Сегодняшняя дата: {current_date}."""
    # if user_id not in premium_users:
    #     return [{"role": "system", "content": common_start}]
    # else:
    return [{"role": "system", "content": f"""
Ты полезный ассистент с ИИ, который готов помочь своему пользователю.
Ты даешь короткие содержательные ответы, обычно не более 100 символов.
Если я попрошу тебя что-то сделать, что можно сделать с помощью программы на python, ты присылаешь мне код программы без объяснений.
Если программа должна возвращать какой-то результат, то выводи его с помощью print.
Затем я запущу этот код и скажу тебе результат, после чего ты сделаешь ответ из этого результата.
Если при выполнеии кода возникнет ошибка, я тебе её пришлю и ты исправишь код. Просто пришли мне исправленный код без пояснений.
Если ты увидишь, что результат выполнения кода не соответствует твоим ожиданиям, то просто пришли новую версию кода.
Если тебе нужна какая-то информация, то получай её из интернета с помощью python и обрабатывай с помощью кода.
Не используй код, который требует использование ключей для доступа к api.
Для написания кода используй специальную библиотеку, которая называется gpt_utils. Она содержит следующие функции:
gpt_utils.send_message_to_all(text) - отправляет сообщение всем пользователям
Используй библиотеку yfinance для доступа к ценам акций
Для работы с вопросами о погоде используй python_weather"""}]


def _get_user(id):
    id = str(id)
    user = users.get(
        id, {'id': id, 'history': _get_clear_history(id), 'last_prompt_time': 0})
    users[id] = user
    return user


def executeCode(code, user):
    try:
        print("Executing code:\n" + code)
        user['last_code'] = code

        f = StringIO()
        with redirect_stdout(f):
            exec(code, globals())
        res = f.getvalue()
        # If res - array - join
        if isinstance(res, list):
            res = "\n".join(res)

        print("Code execution result: " + res.strip())

        return res, True
    except Exception as e:
        # Get exception message and stacktrace
        error = "".join(traceback.format_exception_only(e)).strip()
        error_stack = traceback.format_exc()
        return error, False


def _is_python_code(ans):
    ans = str(ans)
    if ans.startswith("gpt_utils"):
        return True
    if ans.startswith("import ") or ans.startswith("from ") or ans.startswith("def ") or ans.startswith("class ") or ans.startswith("print") or ans.startswith("for"):
        return True
    if "print" in ans or " = " in ans:
        return True
    # This also looks like python code
    # if (ans.split(" ")[0].isalpha() or ans.split(".")[0].isalpha() or ans.split("=")[0].isalpha()) or "print(" in ans:
    #     return True
    return False


def _process_rq(user_id, rq, deep=0):
    try:
        user_id = str(user_id)
        user = _get_user(user_id)
        if PREMIUM_SECRET in rq:
            user['premium'] = True
            return f"Вы были переключены на premium модель {main_model}."

        if not user.get('premium', None):
            _log(f"User {user_id} is not premium and run out of money.")
            return "Прошу прощения, но у бота закончились деньги :( Попробуйте позже или скажите код для премиум-доступа."

        if deep >= 5:
            return "Слишком много вложенных попыток написать программу. Дальше страшно, попробуйте спросить что-то другое."

        # Drop history if user is inactive for 1 hour
        if time.time() - user['last_prompt_time'] > 60*60:
            user['last_prompt_time'] = 0
            user['history'] = _get_clear_history(user_id)

        if rq and len(rq) > 0 and len(rq) < 3000:
            _log(f">>> ({user_id}) {rq}")
            user['history'].append({"role": "user", "content": rq})

            prefix = ""
            # if len(user['history']) > 20 and not (user.get('premium', False)) and user.get('limit', False) != True:
            #     user['limit'] = True
            #     prefix = "(Вы были переключены на экономичную модель gpt-3.5-turbo. Для переключения обратитесь к @Krestnikov) "
            #     log(f"User {user_id} was switched to cheap model!")
            #     if len(user['history']) > 50:
            #         log(f"User {user_id} was banned!")
            #         return "Извините, вы исчерпали лимит сообщений к боту."

            # Truncate history but save first prompt
            max = max_history
            model = main_model
            if user.get('limit', False):
                max = 3500
                model = cheap_model

            while (_count_tokens(user) > max):
                user['history'].pop(1)

            completion = openai.ChatCompletion.create(
                model=model, messages=user['history'], temperature=0.7)
            ans = completion['choices'][0]['message']['content']
            _log(f"<<< ({user_id}) {ans}")

            user['history'].append({"role": "assistant", "content": ans})
            user['last_prompt_time'] = time.time()

            # Extract code from ```python <code> ```
            if "```python" in ans:
                ans = ans[ans.index("```python") + 9:]
                ans = ans[:ans.index("```")]
            ans = ans.strip()

            if _is_python_code(ans):
                ans, res = executeCode(ans, user)
                if res:
                    # Код завершился без ошибок
                    if ans == None or ans == "":
                        return None
                    ans = "Я запустил код и получил результат: " + ans
                    return _process_rq(user_id, ans, deep + 1)
                else:
                    ans = "Я запустил код и получил ошибку: " + ans + \
                        ". Попробуй исправить код и пришли его снова целиком. Не пиши ничего кроме кода."
                    return _process_rq(user_id, ans, deep + 1)
            else:
                return prefix + ans
        else:
            user['last_prompt_time'] = 0
            user['last_text'] = ''
            return "Error! Please use simple short texts"
    except openai.error.RateLimitError as limitE:
        _log(f"Error: {limitE}", limitE)
        return "OpenAI пишет, что мы вышли за rete limit :( Придется попробовать позже."
    except Exception as e:
        _log(f"!!! Error: {e}", e)
        return "Error! Please try again later"


@bot.message_handler(commands=['clear'])
def send_welcome(message):
    user_id = str(message.from_user.id)
    user = _get_user(user_id)
    user['history'] = _get_clear_history(user_id)
    bot.reply_to(
        message, f"Started! (History cleared). Using model {main_model}")


@bot.message_handler(commands=['code'])
def get_code(message):
    user = _get_user(message.from_user.id)
    code = user.get('last_code', '')
    bot.reply_to(
        message, f"Для ответа на ваш вопрос я написал следующий код:\n{code}")


@bot.message_handler(func=lambda message: True)
def process_message(message):
    try:
        user_id = str(message.from_user.id)
        rq = ""
        answer_message = False
        if message.content_type != 'text':
            return
        if message.chat.type == 'group' or message.chat.type == 'supergroup':
            rq = str(message.text)
            # Check if calling me or if it answer on my message
            if rq.split()[0].lower() in mynames:
                rq = rq[len(rq.split()[0]):].strip()
                answer_message = True
            elif (message.reply_to_message and message.reply_to_message.from_user.username.lower() in mynames):
                answer_message = True
            else:
                return
        elif message.chat.type == 'private':
            rq = str(message.text)
        else:
            return

        if len(rq) > 0:
            if 'покажи код' in rq.lower():
                get_code(message)
                return

            ans = _process_rq(user_id, rq)
            if ans == None or ans == "":
                return

            if answer_message:
                bot.reply_to(message, ans)
            else:
                bot.send_message(message.chat.id, ans)
            # Save users using utf-8 and beatur format
            with open("users.json", "w") as f:
                json.dump(users, f, indent=4, ensure_ascii=False)
    except Exception as e:
        _log(f"!!! Error: {e}", e)


@bot.message_handler(content_types=['text'], func=lambda message: message.chat.type == 'group')
def process_group_message(message):
    try:
        user_id = str(message.from_user.id)
        rq = str(message.text)
        ans = _process_rq(user_id, rq)
        bot.send_message(message.chat.id, ans)
        # Save users using utf-8 and beatur format
        with open("users.json", "w") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
    except Exception as e:
        _log(f"!!! Error: {e}", e)


if __name__ == "__main__":
    gpt_utils.bot = bot
    bot.polling()
