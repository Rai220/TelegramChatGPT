import telebot
import openai
import time
import tiktoken
import os
import json
import flask
import threading

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

port = os.environ.get("PORT", 8080)

tokenizer = tiktoken.get_encoding("cl100k_base")
max_history = 7500 # History will be truncated after this length

bot = telebot.TeleBot(TG_TOKEN)
openai.api_key = OPENAI_API_KEY
model = "gpt-4-0314"

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
        text = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime()) + " " + text
        print(text, file=f)

def _count_tokens(user):
    return sum([len(tokenizer.encode(x['content'])) for x in user['history']])


def _get_clear_history():
    current_date = time.strftime("%d.%m.%Y", time.localtime())
    return [{"role": "system", "content": f"Ты полезный ассистент с ИИ, который готов помочь своему пользователю. Ты даешь короткие содержательные ответы, обычно не более 100 символов. Сегодняшняя дата: {current_date}."}]


def _get_user(id):
    user = users.get(id, {'id': id, 'history': _get_clear_history(), 'last_prompt_time': 0})
    users[id] = user
    return user


def _process_rq(user_id, rq):
    try:
        user = _get_user(user_id)
        # if last prompt time > 60 minutes ago - drop context
        # if time.time() - user['last_prompt_time'] > 60*60*24:
        #     user['last_prompt_time'] = 0
        #     user['history'] = _get_clear_history()

        if rq and len(rq) > 0 and len(rq) < 250:
            log(f">>> ({user_id}) {rq}")
            user['history'].append({"role": "user", "content": rq})
            # Truncate history but save first prompt
            while(_count_tokens(user) > max_history):
                user['history'].pop(1)

            completion = openai.ChatCompletion.create(
                model=model, messages=user['history'], temperature=0.7)
            ans = completion['choices'][0]['message']['content']
            log(f"<<< ({user_id}) {ans}")
            user['history'].append({"role": "user", "content": ans})
            user['last_prompt_time'] = time.time()
            return ans
        else:
            user['last_prompt_time'] = 0
            user['last_text'] = ''
            return "!!! Error! Please use simple short texts"
    except Exception as e:
        log(f"!!! Error: {e}")
        return "Error! Please try again later"


@bot.message_handler(commands=['start', 'help', 'clear'])
def send_welcome(message):
    user = _get_user(message.from_user.id)
    user['history'] = _get_clear_history()
    bot.reply_to(message, f"Started! (History cleared). Using model {model}")


@bot.message_handler(func=lambda message: True)
def process_message(message):
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
        response = openai.Requestor.request("get", path, params=flask.request.args)
    elif flask.request.method == "POST":
        response = openai.Requestor.request("post", path, params=flask.request.form)
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
        if flask.request.args.get("token", None) != token:
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