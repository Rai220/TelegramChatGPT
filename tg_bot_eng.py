import telebot
import openai
import time

bot = telebot.TeleBot("<YOUR_TG_BOT_KEY_HERE>")
openai.api_key = "<YOUR_OPEN_API_KEY_HERE>"
model = "davinci:ft-personal:<YOUR_MODEL_HERE>"
stop_symbols = "###"

users = {}


def _get_user(id):
    user = users.get(id, {'id': id, 'last_text': '', 'last_prompt_time': 0})
    users[id] = user
    return user


def _process_rq(user_id, rq):
    user = _get_user(user_id)
    last_text = user['last_text']
    # if last prompt time > 10 minutes ago - drop context
    if time.time() - user['last_prompt_time'] > 600:
        last_text = ''
        user['last_prompt_time'] = 0
        user['last_text'] = ''

    if rq and len(rq) > 0 and len(rq) < 1000:
        print(f">>> ({user_id}) {rq}")

        # truncate to 1000 symbols from the end
        prompt = f"{last_text}Q: {rq} ->"[-1000:]
        print("Sending to OpenAI: " + prompt)
        completion = openai.Completion.create(
            engine=model, prompt=prompt, max_tokens=256, stop=[stop_symbols], temperature=0.7)
        eng_ans = completion['choices'][0]['text'].strip()
        if "->" in eng_ans:
            eng_ans = eng_ans.split("->")[0].strip()
        ans = eng_ans
        print(f"<<< ({user_id}) {ans}")
        user['last_text'] = prompt + " " + eng_ans + stop_symbols
        user['last_prompt_time'] = time.time()
        return ans
    else:
        user['last_prompt_time'] = 0
        user['last_text'] = ''
        return "!!! Error! Please use simple short texts"


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user = _get_user(message.from_user.id)
    user['last_prompt_time'] = 0
    user['last_text'] = ''
    bot.reply_to(message, f"Started! (History cleared). Using model {model}")


@bot.message_handler(func=lambda message: True)
def echo_all(message):
    user_id = message.from_user.id
    rq = message.text
    ans = _process_rq(user_id, rq)
    bot.send_message(message.chat.id, ans)


if __name__ == '__main__':
    bot.polling()
