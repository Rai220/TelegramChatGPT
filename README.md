# TelegramChatGPT
Personal telegram chat-bot based on OpenAI GPT-3 finetuning.

This code from article: https://habr.com/ru/post/712534/ (Transfering our points of view to a chat bot based on GPT-3)

# Setup
1. Install requirements
```
pip install -r requirements.txt
```
2. Get OpenAI API key from your account
3. Setup yout OpenAI key
```
export OPENAI_API_KEY=<YOUR_KEY>
```
4. Fill your dataset with your answers in `dataset.txt`
5. Validate your dataset
```
openai tools fine_tunes.prepare_data -f dataset.jsonl -q
```
6. Fine-tune your model and get unique model name
```
openai api fine_tunes.create -t dataset.jsonl -m davinci --suffix "<YOUR_MODEL_NAME>"
```
7. Create Telegram bot using BotFather
8. Update tg_bot.py with your bot token, OpenAI Token and model name.
9. Run!
For english version:
```
python tg_bot_eng.py
```
For russian version:
```
python tg_bot_rus.py
```

# Free chat with GPT-3.5
```
OPENAI_API_KEY=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 TG_TOKEN=372106098:AAFEYFFfNuZlrAW84GBkE5mrrcxBUqeygtQpython tg_bot_no_tuning.py
```