from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent, JoinEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
import google.generativeai as genai
import requests
import json
import os

# 從環境變數獲取敏感信息，如果沒有則使用默認值（僅用於本地開發）
# LINE Bot 設定
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', 'G5/Jatw/Mm7gpHjRnVG89Mxp+6QWXINk4mGkga8o3g9TRa96NXiOed5ylkNZjuUtGHXFKCV46xX1t73PZkYdjlqIFoJHe0XiPUP4EyRy/jwJ6sqRtXivrQNA0WH+DK9pLUKg/ybSZ1mvGywuK8upBAdB04t89/1O/w1cDnyilFU=')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', 'ff89f01585f2b68301b8f8911174cd87')

# Google Gemini API 設定
GOOGLE_GEMINI_API_KEY = os.environ.get('GOOGLE_GEMINI_API_KEY', 'AlzaSyBWCitsjkm7DPe_aREubKIZjqmgXafVKNE')
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-pro')

# NewsAPI 設定
NEWS_API_KEY = os.environ.get('NEWS_API_KEY', '5807e3e70bd2424584afdfc6e932108b')
NEWS_API_ENDPOINT = 'https://newsapi.org/v2/top-headlines'

# The Movie Database (TMDb) API 設定
TMDB_API_KEY = os.environ.get('TMDB_API_KEY', 'eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIyMzI4YmU1YzdhNDA1OTczZDdjMjA0NDlkYmVkOTg4OCIsIm5iZiI6MS43NDYwNzg5MDI5MTgwMDAyZSs5LCJzdWIiOiI2ODEzMGNiNjgyODI5Y2NhNzExZmJkNDkiLCJzY29wZXMiOlsiYXBpX3JlYWQiXSwidmVyc2lvbjoxfQ.FQlIdfWlf4E0Tw9sYRF7txbWymAby77KnHjTVNFSpdM')
TMDB_API_BASE_URL = 'https://api.themoviedb.org/3'

# OpenWeatherMap API 設定
OPENWEATHERMAP_API_KEY = os.environ.get('OPENWEATHERMAP_API_KEY', 'CWA-C80C73F3-7042-4D8D-A88A-D39DD2CFF841')
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

def get_weather(city):
    """使用 OpenWeatherMap API 查詢天氣"""
    params = {
        'q': city,
        'appid': OPENWEATHERMAP_API_KEY,
        'units': 'metric',  # 使用攝氏溫度
        'lang': 'zh_tw'     # 使用繁體中文
    }
    try:
        response = requests.get(OPENWEATHERMAP_API_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        city_name = data['name']
        weather_desc = data['weather'][0]['description']
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        humidity = data['main']['humidity']
        wind_speed = data['wind']['speed']
        
        weather_info = (
            f"{city_name}天氣資訊：\n"
            f"• 天氣狀況：{weather_desc}\n"
            f"• 目前溫度：{temp}°C\n"
            f"• 體感溫度：{feels_like}°C\n"
            f"• 濕度：{humidity}%\n"
            f"• 風速：{wind_speed} m/s"
        )
        return weather_info
    except requests.exceptions.RequestException as e:
        return f"查詢天氣時發生錯誤：{e}"
    except KeyError:
        return "抱歉，找不到該城市的天氣資訊。請確認城市名稱是否正確。"
    except json.JSONDecodeError as e:
        return f"解析天氣資料時發生錯誤：{e}"

def search_movies(query):
    """使用 TMDb API 查詢電影資訊"""
    headers = {
        'Authorization': f'Bearer {TMDB_API_KEY}',
        'accept': 'application/json'
    }
    
    params = {
        'query': query,
        'language': 'zh-TW',
        'page': 1
    }
    
    try:
        response = requests.get(f"{TMDB_API_BASE_URL}/search/movie", headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data['total_results'] > 0:
            movies = data['results'][:3]  # 只取前三部電影
            results = []
            
            for movie in movies:
                title = movie['title']
                release_date = movie.get('release_date', '未知')
                overview = movie.get('overview', '無簡介')
                rating = movie.get('vote_average', 0)
                
                movie_info = (
                    f"電影：{title}\n"
                    f"上映日期：{release_date}\n"
                    f"評分：{rating}/10\n"
                    f"簡介：{overview[:100]}{'...' if len(overview) > 100 else ''}\n"
                )
                results.append(movie_info)
            
            return "\n".join(results)
        else:
            return f"抱歉，找不到與「{query}」相關的電影。"
    except requests.exceptions.RequestException as e:
        return f"查詢電影時發生錯誤：{e}"
    except json.JSONDecodeError as e:
        return f"解析電影資料時發生錯誤：{e}"

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

@handler.add(MessageEvent, message=TextMessageContent)
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
    
    # 判斷是否為天氣查詢
    elif "天氣" in message_text:
        city = message_text.replace("天氣", "").strip()
        if city:
            weather_result = get_weather(city)
            reply = weather_result
        else:
            reply = "請問你想查詢哪個城市的天氣呢？例如：「台北天氣」"
        messages = [TextMessage(text=reply)]
    
    # 判斷是否為電影查詢
    elif "電影" in message_text:
        query = message_text.replace("電影", "").strip()
        if query:
            movie_result = search_movies(query)
            reply = f"查詢「{query}」的電影結果如下：\n\n{movie_result}"
        else:
            reply = "請問你想查詢什麼電影呢？例如：「復仇者電影」"
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

@handler.add(JoinEvent)
def handle_group_join(event):
    """處理機器人加入群組事件"""
    reply_message = TextMessage(text="大家好！很高興加入這個群組。請隨時吩咐我查詢新聞、天氣或電影資訊喔！")
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[reply_message]
        )
    )

# 在群組中接收訊息
@handler.add(MessageEvent, message=TextMessageContent)
def handle_group_message(event):
    """處理群組中的文字訊息"""
    if not hasattr(event.source, 'group_id'):
        return  # 跳過非群組訊息

    group_id = event.source.group_id
    user_id = event.source.user_id
    message_text = event.message.text
    
    # 只處理以特定前綴開頭的訊息，避免機器人回應所有群組訊息
    if message_text.startswith('@機器人') or message_text.startswith('@bot'):
        # 移除前綴
        query = message_text.replace('@機器人', '').replace('@bot', '').strip()
        
        # 判斷查詢類型並處理
        if "新聞" in query:
            search_term = query.replace("新聞", "").strip()
            if search_term:
                result = get_news(search_term)
                reply = f"查詢「{search_term}」的新聞結果如下：\n\n{result}"
            else:
                reply = "請問你想查詢什麼關鍵字的新聞呢？"
        
        elif "天氣" in query:
            city = query.replace("天氣", "").strip()
            if city:
                result = get_weather(city)
                reply = result
            else:
                reply = "請問你想查詢哪個城市的天氣呢？"
        
        elif "電影" in query:
            search_term = query.replace("電影", "").strip()
            if search_term:
                result = search_movies(search_term)
                reply = f"查詢「{search_term}」的電影結果如下：\n\n{result}"
            else:
                reply = "請問你想查詢什麼電影呢？"
        
        else:
            # 使用 Gemini 處理其他查詢
            try:
                gemini_context = [{"role": "user", "parts": [query]}]
                response = gemini_model.generate_content(gemini_context)
                reply = response.text
            except Exception as e:
                reply = f"抱歉，Gemini 發生錯誤：{e}"
        
        # 回覆訊息給群組
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

if __name__ == "__main__":
    # 本地開發使用 debug 模式，生產環境中不使用
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)