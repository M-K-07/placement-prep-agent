import os
import random
import requests
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import json
import psycopg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from rapidfuzz import fuzz
# === Load environment variables ===
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
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

DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg.connect(DATABASE_URL, autocommit=True)


with conn.cursor() as cur:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        chat_id BIGINT UNIQUE NOT NULL,
        subscribed BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS content (
        id SERIAL PRIMARY KEY,
        user_id INT REFERENCES users(id),
        topic TEXT NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        reference TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    


def subscribe_user(chat_id):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO users (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO UPDATE SET subscribed = TRUE;", (chat_id,))
        
def unsubscribe_user(chat_id):
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET subscribed = FALSE WHERE chat_id = %s;", (chat_id,))

def get_subscribed_users():
    with conn.cursor() as cur:
        cur.execute("SELECT id,chat_id FROM users WHERE subscribed = TRUE;")
        return cur.fetchall()

def save_content(user_id, topic, question, answer, reference):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO content (user_id, topic, question, answer, reference)
            VALUES (%s, %s, %s, %s, %s);
        """, (user_id, topic, question, answer, reference))
        
SIMILARITY_THRESHOLD = 85  


def has_user_received_question(user_id, new_question):
    with conn.cursor() as cur:
        cur.execute("SELECT question FROM content WHERE user_id = %s;", (user_id,))
        past_questions = [row[0] for row in cur.fetchall()]

    new_q_norm = new_question.lower().strip()
    for past_q in past_questions:
        past_q_norm = past_q.lower().strip()

        if new_q_norm == past_q_norm:
            return True

        score = fuzz.token_set_ratio(new_q_norm, past_q_norm)
        if score >= SIMILARITY_THRESHOLD:
            print(f"⚠️ Similar question detected ({score}%): {new_question} ~ {past_q}")
            return True

    return False
    
def get_question_answer(topic):
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
            "model": "openai/gpt-oss-20b:free",
            "messages": [{"role": "user", "content": prompt}],
        })
    )

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    else:
        return f"⚠️ Error from OpenRouter: {response.text}"

async def subscribe(update:Update,context:ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribe_user(chat_id)
    await context.bot.send_message(chat_id=chat_id, text="✅ You have subscribed to PrepAI!")

async def unsubscribe(update:Update,context:ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    unsubscribe_user(chat_id)
    await context.bot.send_message(chat_id=chat_id, text="❌ You have unsubscribed from PrepAI.")
    
async def send_daily_question(application):
    users=get_subscribed_users()
    for user_id,chat_id in users:
        topic=random.choice(TOPICS)
        for _ in range(3):
            content= get_question_answer(topic)
            print(content)
            if content:
                question_part=content.split('\n\n')[1]
                question=question_part.split('Q: ')[1].strip()
                if not has_user_received_question(user_id,question):
                    break
        else:
            continue
        splits=content.split('\n\n')
        answer_part=splits[2]
        answer=answer_part.split('A: ')[1].strip()
        reference_part=splits[3]
        reference=reference_part.split('Reference: ')[1].strip()
        save_content(user_id,topic,question,answer,reference)
        
        try:
            await application.bot.send_message(chat_id=chat_id, text=content)
        except Exception as e:
            print(f"Failed to send message to {chat_id}: {e}")

if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    # application.run_polling()
    asyncio.run(send_daily_question(application))
