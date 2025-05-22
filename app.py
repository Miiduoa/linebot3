from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
import google.generativeai as genai
import requests
import json
import os

# LINE Bot 設定
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

# Google Gemini API 設定
GOOGLE_GEMINI_API_KEY = os.environ.get('GOOGLE_GEMINI_API_KEY')
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-pro')

# NewsAPI 設定
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
NEWS_API_ENDPOINT = 'https://newsapi.org/v2/top-headlines'

# The Movie Database (TMDb) API 設定
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
TMDB_API_BASE_URL = 'https://api.themoviedb.org/3'

# OpenWeatherMap API 設定
OPENWEATHERMAP_API_KEY = os.environ.get('OPENWEATHERMAP_API_KEY')
OPENWEATHERMAP_API_BASE_URL = 'https://api.openweathermap.org/data/2.5/weather'

app = Flask(__name__)

# 設定 LINE Messaging API 用戶端
configuration = Configuration(
    access_token=LINE_CHANNEL_ACCESS_TOKEN
)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)

# 設定 Webhook 處理器
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 簡單的上下文記憶體 (userID -> 對話歷史列表)
user_context = {}

def get_news(query):
    """使用 NewsAPI 查詢新聞"""
    params = {
        'q': query,
        'apiKey': NEWS_API_KEY,
        'language': 'zh-TW',  # 設定為繁體中文
        'pageSize': 3       # 限制回傳新聞數量
    }
    try:
        response = requests.get(NEWS_API_ENDPOINT, params=params)
        response.raise_for_status()  # 檢查請求是否成功
        data = response.json()
        if data['status'] == 'ok' and data['totalResults'] > 0:
            news_items = data['articles']
            news_list = []
            for item in news_items:
                title = item['title']
                url = item['url']
                news_list.append(f"標題：{title}\n連結：{url}\n")
            return "\n".join(news_list)
        else:
            return "抱歉，找不到相關新聞。"
    except requests.exceptions.RequestException as e:
        return f"查詢新聞時發生錯誤：{e}"
    except json.JSONDecodeError as e:
        return f"解析新聞資料時發生錯誤：{e}"

@app.route("/callback", methods=['POST'])
def callback():
    """LINE Bot 的 Webhook 接收端點"""
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(message_content_type='text')
def handle_message(event):
    """處理文字訊息"""
    user_id = event.source.user_id
    message_text = event.message.text

    # 取得或初始化使用者的對話歷史
    if user_id not in user_context:
        user_context[user_id] = []

    # 判斷是否為新聞查詢
    if "新聞" in message_text or "最新消息" in message_text:
        query = message_text.replace("新聞", "").replace("最新消息", "").strip()
        if query:
            news_result = get_news(query)
            reply = f"查詢「{query}」的新聞結果如下：\n\n{news_result}"
        else:
            reply = "請問你想查詢什麼關鍵字的新聞呢？"
        messages = [TextMessage(text=reply)]
    else:
        # 將使用者訊息加入對話歷史
        user_context[user_id].append({"role": "user", "parts": [message_text]})

        # 取得 Gemini 的回覆
        try:
            response = gemini_model.generate_content(user_context[user_id])
            gemini_reply = response.text
            user_context[user_id].append({"role": "model", "parts": [gemini_reply]})
            messages = [TextMessage(text=gemini_reply)]
        except Exception as e:
            reply = f"抱歉，Gemini 發生錯誤：{e}"
            messages = [TextMessage(text=reply)]

    # 回覆訊息給使用者
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=messages
        )
    )

@handler.add(message_content_type='group_join')
def handle_group_join(event):
    """處理機器人加入群組事件"""
    reply_message = TextMessage(text="大家好！很高興加入這個群組。請隨時吩咐我查詢新聞、天氣或電影資訊喔！")
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[reply_message]
        )
    )

# 在群組中接收訊息 (需要額外處理，這裡先留空)
@handler.add(message_content_type='text', message_source_type='group')
def handle_group_message(event):
    """處理群組中的文字訊息"""
    # TODO: 將群組訊息加入 Gemini 的上下文
    pass

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)