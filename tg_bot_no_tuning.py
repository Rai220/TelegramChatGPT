import telebot
import openai
import time

bot = telebot.TeleBot("<YOUR_TG_BOT_KEY_HERE>")
openai.api_key = "<YOUR_OPEN_API_KEY_HERE>"
model = "gpt-3.5-turbo-0301"

users = {}

def _get_clear_history():
    return [{"role": "system", "content": "Ты полезный ассистент с ИИ, который готов помочь своему пользователю."}]

def _get_user(id):
    user = users.get(id, {'id': id, 'history': _get_clear_history(), 'last_prompt_time': 0})
    users[id] = user
    return user


def _process_rq(user_id, rq):
    user = _get_user(user_id)
    # if last prompt time > 10 minutes ago - drop context
    if time.time() - user['last_prompt_time'] > 600:
        last_text = ''
        user['last_prompt_time'] = 0
        user['history'] = _get_clear_history()

    if rq and len(rq) > 0 and len(rq) < 250:
        print(f">>> ({user_id}) {rq}")
        user['history'].append({"role": "user", "content": rq})
        completion = openai.ChatCompletion.create(
            engine=model, temperature=0.7)
        ans = completion['choices'][0]['message']['content']
        print(f"<<< ({user_id}) {ans}")
        user['history'].append({"role": "user", "content": ans})
        user['last_prompt_time'] = time.time()
        return ans
    else:
        user['last_prompt_time'] = 0
        user['last_text'] = ''
        return "!!! Error! Please use simple short texts"


@bot.message_handler(commands=['start', 'help'])
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
