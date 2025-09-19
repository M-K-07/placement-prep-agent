import os
import random
import requests
import asyncio
from dotenv import load_dotenv
from telegram import Bot
from telegram.ext import Application
import json

# === Load environment variables ===
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

TOPICS = [
    "Operating Systems",
    "DBMS",
    "Computer Networks",
    "OOPs Concepts",
    "Algorithms",
    "Python Programming",
    "Data Structures",
    "JavaScript Programming",
    "Software Engineering",
]

def get_question_answer():
    topic = random.choice(TOPICS)
    prompt = f"""
    You are an experienced placement preparation assistant.  
    Generate **one interview question** from the topic: {topic}.  

    - Write the **answer in 4-6 sentences**, simple and clear, so that someone reading it can **understand the concept fully**.  
    - Use **easy language**, as if explaining to a student preparing for an interview.  
    - Include **one reference link** for further reading.  
    - Format exactly like this:
    Topic: <Topic Name>
    
    Q: <question>  
    
    A: <answer>  
    
    Reference: <link>
    - Do not add any extra information or greetings.
    """

    
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": "deepseek/deepseek-chat-v3.1:free",
            "messages": [{"role": "user", "content": prompt}],
        })
    )

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    else:
        return f"⚠️ Error from OpenRouter: {response.text}"

async def send_daily_question():
    qa = get_question_answer()
    application = Application.builder().token(BOT_TOKEN).build()
    await application.bot.send_message(chat_id=CHAT_ID, text=qa)

if __name__ == "__main__":
    asyncio.run(send_daily_question())
