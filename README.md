# TelegramChatGPT
Personal telegram chat-bot based on OpenAI GPT-3 finetuning.

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
```
python tg_bot.py
```
