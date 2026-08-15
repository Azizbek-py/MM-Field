import os
import re
import requests
import logging
from settings import BOT_TOKEN, SST_TOKEN, GROQ_TOKEN, SYSTEM_PROMPT
from groq import Groq
from dotenv import load_dotenv
import json
load_dotenv()

GROQ_TOKEN = os.getenv("GROQ_TOKEN")

client = Groq(api_key=GROQ_TOKEN)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def _extract_json_object(response: str) -> dict:
    if not isinstance(response, str):
        return response if isinstance(response, dict) else {}

    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    if not cleaned:
        return {}

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        logger.warning("Malformed AI JSON response received, attempting recovery")
        return {}

def stt(file_id: str) -> dict:
    url = 'https://uzbekvoice.ai/api/v1/stt'
    headers = {
        "Authorization": f"Bearer {SST_TOKEN}"
    }
    ret = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}")
    url1 = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{ret.json()['result']['file_path']}"
    voice = requests.get(url1)

    temp_path = f"{file_id}.ogg"
    with open(temp_path, "wb") as f:
        f.write(voice.content)

    file_size = os.path.getsize(temp_path)
    if file_size <= 0:
        logger.warning("STT audio file is empty")
    
    data = {
        "return_offsets": "true",
        "run_diarization": "false",
        "language": "uz",
        "model": "general",
        "blocking": "true",
    }

    try:
        with open(f"{file_id}.ogg", "rb") as f:
            files = {
                "file": ("audio.ogg", f),
            }
            response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        
        if response.status_code == 200:
            text = response.json()['result']['text']
            try:
                os.remove(temp_path)
            except FileNotFoundError:
                pass
            return text
        else:
            logger.error(f"STT Error {response.status_code}: {response.text}")
            try:
                os.remove(temp_path)
            except FileNotFoundError:
                pass
            return f"Request failed with status code {response.status_code}: {response.text}"
    except requests.exceptions.Timeout:
        logger.error("STT Timeout")
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass
        return "Request timed out. The API response took too long to arrive."
    except Exception as e:
        logger.error(f"STT Exception: {str(e)}")
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass
        return f"Error: {str(e)}"

def analyze_query2(user_text: str) -> dict:
    """
    Foydalanuvchi qidiruvini AI yordamida tahlil qiladi.

    Args:
        user_text (str): Foydalanuvchi yozgan matn

    Returns:
        dict: AI qaytargan JSON
    """

    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        temperature=1,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_text,
            }
        ],
    )

    response_text = completion.choices[0].message.content

    return _extract_json_object(response_text)