import traceback
import types
import telebot
import openai
import time
import tiktoken
import os
import json
import flask
import threading
import sys
from io import StringIO
from contextlib import redirect_stdout

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

mynames = ["@trololobot", "@кибердед", "trololo_bot",
           "кибердед", "кибердед,", "trololobot"]
# mynames = ["whentimecomesbot", "когдапридетвремя", "@whentimecomesbot", "когдапридетвремя,"]

port = os.environ.get("PORT", 8080)

tokenizer = tiktoken.get_encoding("cl100k_base")
max_history = 7500  # History will be truncated after this length

premium_secret = "49f3c50d-1fa1-45c8-9d4d-68fc1a65e6a7"

bot = telebot.TeleBot(TG_TOKEN)
openai.api_key = OPENAI_API_KEY
main_model = "gpt-4-0314"
cheap_model = "gpt-3.5-turbo"

premium_users = ["47173181"]

# Load history from file
users = {}
if os.path.exists("users.json"):
    with open("users.json", "r") as f:
        users = json.load(f)


def log(text):
    # Print to screen and log file
    print(text)
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
    if user_id not in premium_users:
        return [{"role": "system", "content": common_start}]
    else:
        return [{"role": "system", "content": f"""
Ты полезный ассистент с ИИ, который готов помочь своему пользователю.
Ты даешь короткие содержательные ответы, обычно не более 100 символов.
Если я попрошу тебя что-то сделать, что можно сделать с помощью программы на python, ты присылаешь мне код программы без объяснений.
Если программа должна возвращать какой-то результат, то выводи его с помощью print().
Затем я запущу этот код и скажу тебе результат, после чего ты сделаешь ответ из этого результата.
Если при выполнеии кода возникнет ошибка, я тебе её пришлю и ты исправишь код. Просто пришли мне исправленный код без пояснений.
Если ты увидишь, что результат выполнения кода не соответствует твоим ожиданиям, то просто пришли новую версию кода.
Если тебе нужна какая-то информация, то получай её из интернета с помощью python и обрабатывай с помощью кода.
Не используй код, который требует использование ключей для доступа к api"""}]


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
            exec(code)
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
        # log("Error executing code: " + error + "\n" + error_stack)
        # if len(error_stack) < 250:
        #     return error + "\n" + error_stack, False
        # else:
        return error, False


def _process_rq(user_id, rq, deep=0):
    try:
        user_id = str(user_id)
        user = _get_user(user_id)
        if not user.get(['premium']):
            return "Прошу прощения, но у бота закончились деньги :( Попробуйте позже."

        if deep >= 5:
            return "Слишком много вложенных попыток написать программу. Дальше страшно, попробуйте спросить что-то другое."

        # if last prompt time > 60 minutes ago - drop context
        # if time.time() - user['last_prompt_time'] > 60*60*24:
        #     user['last_prompt_time'] = 0
        #     user['history'] = _get_clear_history()

        if premium_secret in rq:
            user['premium'] = True
            return f"Вы были переключены на premium модель {main_model}."

        if rq and len(rq) > 0 and len(rq) < 3000:
            log(f">>> ({user_id}) {rq}")
            user['history'].append({"role": "user", "content": rq})

            prefix = ""
            if len(user['history']) > 20 and not (str(user_id) in premium_users or user.get('premium', False)) and user.get('limit', False) != True:
                user['limit'] = True
                prefix = "(Вы были переключены на экономичную модель gpt-3.5-turbo. Для переключения обратитесь к @Krestnikov) "
                log(f"User {user_id} was switched to cheap model!")
                if len(user['history']) > 50:
                    log(f"User {user_id} was banned!")
                    return "Извините, вы исчерпали лимит сообщений к боту."

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
            log(f"<<< ({user_id}) {ans}")

            user['history'].append({"role": "assistant", "content": ans})
            user['last_prompt_time'] = time.time()

            # Extract code from ```python <code> ```
            if "```python" in ans:
                ans = ans[ans.index("```python") + 9:]
                ans = ans[:ans.index("```")]
            ans = ans.strip()

            if ans.startswith("import ") or ans.startswith("from ") or ans.startswith("def ") or ans.startswith("class ") or ans.startswith("print") or ans.startswith("for"):
                ans, res = executeCode(ans, user)
                if res:
                    ans = "Я запустил код и получил результат: " + ans
                    return _process_rq(user_id, ans, deep + 1)
                else:
                    ans = "Я запустил код и получил ошибку: " + ans
                    return _process_rq(user_id, ans, deep + 1)
            else:
                return prefix + ans
        else:
            user['last_prompt_time'] = 0
            user['last_text'] = ''
            return "!!! Error! Please use simple short texts"
    except Exception as e:
        log(f"!!! Error: {e}")
        return "Error! Please try again later"


@bot.message_handler(commands=['secretclear'])
def send_welcome(message):
    user = _get_user(message.from_user.id)
    user['history'] = _get_clear_history()
    bot.reply_to(message, f"Started! (History cleared). Using model {main_model}")

@bot.message_handler(commands=['code'])
def get_code(message):
    user = _get_user(message.from_user.id)
    code = user.get('last_code', '')
    bot.reply_to(message, f"Для ответа на ваш вопрос я написал следующий код:\n{code}")


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
            if 'покажи код' in rq:
                get_code(message)
                return
            
            ans = _process_rq(user_id, rq)

            if answer_message:
                bot.reply_to(message, ans)
            else:
                bot.send_message(message.chat.id, ans)
            # Save users using utf-8 and beatur format
            with open("users.json", "w") as f:
                json.dump(users, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log(f"!!! Error: {e}")

# Hanle messages in group


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
        log(f"!!! Error: {e}")


@app.route("/<path:path>", methods=["GET", "POST"])
def proxy(path):
    # Check token
    if flask.request.args.get("token", None) != AUTH_TOKEN:
        return flask.jsonify({"error": "Invalid token"}), 403

    if flask.request.method == "GET":
        response = openai.Requestor.request(
            "get", path, params=flask.request.args)
    elif flask.request.method == "POST":
        response = openai.Requestor.request(
            "post", path, params=flask.request.form)
    return flask.jsonify(response)


@app.route("/completion", methods=["POST", "GET"])
def completion():
    # Check token
    try:
        # Check token in header
        if flask.request.headers.get("token", None) != AUTH_TOKEN:
            return flask.jsonify({"error": "Invalid token"}), 403

        data = flask.request.get_json()
        if not data:
            return flask.jsonify({"error": "No json data"}), 400

        prompt = data.get("prompt", None)
        if not prompt:
            return flask.jsonify({"error": "Prompt must be set"}), 400

        stop = data.get("stop", ['###'])
        engine = data.get("engine", "text-davinci-003")
        max_tokens = data.get("max_tokens", 150)
        temperature = data.get("temperature", 0.9)

        response = openai.Completion.create(
            engine=engine,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=1,
            best_of=1,
            stop=stop
        )
        return flask.jsonify(response)
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@app.route("/chatcompletion", methods=["POST", "GET"])
def chatcompletion():
    # Check token
    try:
        if flask.request.headers.get("token", None) != AUTH_TOKEN:
            return flask.jsonify({"error": "Invalid token"}), 403

        # Get json from body
        data = flask.request.get_json()
        if not data:
            return flask.jsonify({"error": "No json data"}), 400

        model = data.get("model", "gpt-3.5-turbo-0301")
        max_tokens = data.get("max_tokens", 150)
        temperature = data.get("temperature", 0.9)
        messages = data.get("messages", None)

        completion = openai.ChatCompletion.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        return flask.jsonify(completion)
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


# Start server
if __name__ == "__main__":
    # Run bot polling in thread
    bot_thread = threading.Thread(target=bot.polling)
    bot_thread.start()
    app.run(host="0.0.0.0", port=port)
