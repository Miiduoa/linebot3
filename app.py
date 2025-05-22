from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent, JoinEvent, FollowEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
import google.generativeai as genai
import requests
import json
import os
import logging
import traceback
import time
import linebot

# 配置詳細的日誌
logging.basicConfig(
    level=logging.DEBUG,  # 更改為 DEBUG 級別以獲取更多詳細資訊
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 從環境變數獲取敏感信息，如果沒有則使用默認值（僅用於本地開發）
# LINE Bot 設定
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', 'G5/Jatw/Mm7gpHjRnVG89Mxp+6QWXINk4mGkga8o3g9TRa96NXiOed5ylkNZjuUtGHXFKCV46xX1t73PZkYdjlqIFoJHe0XiPUP4EyRy/jwJ6sqRtXivrQNA0WH+DK9pLUKg/ybSZ1mvGywuK8upBAdB04t89/1O/w1cDnyilFU=')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', 'ff89f01585f2b68301b8f8911174cd87')

# Google Gemini API 設定
GOOGLE_GEMINI_API_KEY = os.environ.get('GOOGLE_GEMINI_API_KEY', 'AIzaSyBWCitsjkm7DPe_aREubKIZjqmgXafVKNE')
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

# 設定 LINE Messaging API 用戶端 - 全局配置對象
logger.info(f"使用的 LINE Channel Access Token: {LINE_CHANNEL_ACCESS_TOKEN[:10]}...{LINE_CHANNEL_ACCESS_TOKEN[-10:]}")
configuration = Configuration(
    access_token=LINE_CHANNEL_ACCESS_TOKEN
)

# 設定 Webhook 處理器
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 簡單的上下文記憶體 (userID -> 對話歷史列表)
user_context = {}

# 添加根路由和健康檢查
@app.route('/', methods=['GET'])
def index():
    return '歡迎使用 LINE 聊天機器人！服務正常運行中。'

@app.route("/health", methods=['GET'])
def health():
    return {"status": "ok"}, 200

@app.route("/test", methods=['GET'])
def test():
    """簡單的測試路由，幫助檢查應用是否正常運行以及依賴項是否正確安裝"""
    try:
        # 測試 LINE Bot SDK
        handler_test = WebhookHandler("test_secret")
        line_config = Configuration(access_token="test_token")
        api_client = ApiClient(line_config)
        
        # 測試 Gemini API
        genai_status = "可用" if GOOGLE_GEMINI_API_KEY.startswith("AIza") else "金鑰格式不正確"
        
        return {
            "status": "線上",
            "flask": "正常",
            "line_bot_sdk": "已加載",
            "gemini_api": genai_status,
            "python_version": os.sys.version,
            "environment": "production" if not app.debug else "development"
        }, 200
        
    except Exception as e:
        return {
            "status": "錯誤",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, 500

@app.route("/send_test", methods=['GET'])
def send_test():
    """測試直接發送訊息給指定用戶 ID"""
    try:
        user_id = request.args.get('user_id')
        message = request.args.get('message', '這是一條測試訊息')
        
        if not user_id:
            return {"error": "缺少 user_id 參數"}, 400
            
        logger.info(f"嘗試直接發送測試訊息給用戶 {user_id}: {message}")
        
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            from linebot.v3.messaging import PushMessageRequest
            
            response = line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=message)]
                )
            )
            
        return {
            "status": "成功",
            "message": f"訊息已發送給用戶 {user_id}"
        }, 200
        
    except Exception as e:
        logger.error(f"發送測試訊息時發生錯誤: {e}")
        logger.error(traceback.format_exc())
        
        return {
            "status": "錯誤",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, 500

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
        logger.error(f"查詢新聞時發生錯誤：{e}")
        return f"查詢新聞時發生錯誤：{e}"
    except json.JSONDecodeError as e:
        logger.error(f"解析新聞資料時發生錯誤：{e}")
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
        logger.error(f"查詢天氣時發生錯誤：{e}")
        return f"查詢天氣時發生錯誤：{e}"
    except KeyError:
        logger.error(f"找不到該城市的天氣資訊")
        return "抱歉，找不到該城市的天氣資訊。請確認城市名稱是否正確。"
    except json.JSONDecodeError as e:
        logger.error(f"解析天氣資料時發生錯誤：{e}")
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
        logger.error(f"查詢電影時發生錯誤：{e}")
        return f"查詢電影時發生錯誤：{e}"
    except json.JSONDecodeError as e:
        logger.error(f"解析電影資料時發生錯誤：{e}")
        return f"解析電影資料時發生錯誤：{e}"

def send_reply(reply_token, messages, max_retries=3):
    """發送回覆訊息，具有重試機制"""
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logger.info(f"嘗試發送回覆，第 {retry_count + 1} 次嘗試")
            logger.debug(f"回覆令牌: {reply_token}")
            logger.debug(f"訊息內容: {messages}")
            
            # 根據官方範例的正確用法
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                response = line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=messages
                    )
                )
            
            logger.info(f"成功回覆訊息")
            return True
            
        except linebot.v3.messaging.ApiException as e:
            # 處理 LINE API 的特定錯誤
            logger.error(f"LINE API 錯誤 (狀態碼: {e.status}): {e.reason}")
            
            # 嘗試取得詳細的錯誤訊息
            try:
                error_detail = json.loads(e.body)
                logger.error(f"錯誤細節: {error_detail}")
            except:
                logger.error(f"無法解析錯誤詳情: {e.body}")
                
            # 檢查是否為令牌相關問題（過期或已使用）
            if e.status == 400 and "Invalid reply token" in str(e.body):
                logger.error("無效的回覆令牌 - 可能已過期或已被使用")
                return False
                
            # 對於其他錯誤，繼續重試
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)  # 1秒後重試
                
        except Exception as e:
            logger.error(f"回覆訊息時發生一般錯誤: {e}")
            logger.error(traceback.format_exc())
            
            # 等待一段時間後重試
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)  # 1秒後重試
    
    logger.error(f"在 {max_retries} 次嘗試後無法發送回覆")
    return False

@app.route("/callback", methods=['POST'])
def callback():
    """LINE Bot 的 Webhook 接收端點"""
    # 記錄請求數據以進行調試
    logger.info(f"收到 Webhook 請求，headers: {request.headers}")
    
    try:
        signature = request.headers['X-Line-Signature']
    except KeyError:
        logger.error("缺少 X-Line-Signature 頭部")
        return "缺少簽名", 400

    # get request body as text
    body = request.get_data(as_text=True)
    logger.info(f"Request body: {body}")

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("無效的簽名")
        abort(400)
    except Exception as e:
        logger.error(f"處理 webhook 時發生錯誤: {e}")
        logger.error(traceback.format_exc())
        abort(500)

    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """處理文字訊息"""
    logger.info(f"處理訊息事件: {event}")
    
    user_id = event.source.user_id
    message_text = event.message.text
    reply_token = event.reply_token
    
    logger.info(f"從用戶 {user_id} 收到消息: {message_text}")
    logger.info(f"回覆令牌: {reply_token}")

    # 直接回覆測試訊息
    if message_text.lower() == "ping":
        logger.info("收到 ping 測試訊息，立即回覆")
        result = send_reply(reply_token, [TextMessage(text="pong! 我在這裡！")])
        if result:
            logger.info("測試訊息回覆成功")
        else:
            logger.error("測試訊息回覆失敗")
        return

    # 取得或初始化使用者的對話歷史
    if user_id not in user_context:
        user_context[user_id] = []

    # 判斷是否為新聞查詢
    if "新聞" in message_text or "最新消息" in message_text:
        query = message_text.replace("新聞", "").replace("最新消息", "").strip()
        if query:
            logger.info(f"開始查詢新聞關鍵字: {query}")
            news_result = get_news(query)
            reply = f"查詢「{query}」的新聞結果如下：\n\n{news_result}"
        else:
            reply = "請問你想查詢什麼關鍵字的新聞呢？"
        messages = [TextMessage(text=reply)]
    
    # 判斷是否為天氣查詢
    elif "天氣" in message_text:
        city = message_text.replace("天氣", "").strip()
        if city:
            logger.info(f"開始查詢城市天氣: {city}")
            weather_result = get_weather(city)
            reply = weather_result
        else:
            reply = "請問你想查詢哪個城市的天氣呢？例如：「台北天氣」"
        messages = [TextMessage(text=reply)]
    
    # 判斷是否為電影查詢
    elif "電影" in message_text:
        query = message_text.replace("電影", "").strip()
        if query:
            logger.info(f"開始查詢電影: {query}")
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
            logger.info("開始與 Gemini 模型對話")
            response = gemini_model.generate_content(user_context[user_id])
            gemini_reply = response.text
            logger.info(f"從 Gemini 收到回覆: {gemini_reply[:100]}...")
            user_context[user_id].append({"role": "model", "parts": [gemini_reply]})
            messages = [TextMessage(text=gemini_reply)]
        except Exception as e:
            logger.error(f"Gemini 發生錯誤：{e}")
            logger.error(traceback.format_exc())
            reply = f"抱歉，Gemini 發生錯誤：{str(e)[:100]}"
            messages = [TextMessage(text=reply)]

    # 回覆訊息給使用者
    logger.info(f"準備回覆訊息: {str(messages)[:200]}")
    result = send_reply(reply_token, messages)
    if result:
        logger.info("成功回覆訊息")
    else:
        logger.error("回覆訊息失敗")

@handler.add(JoinEvent)
def handle_group_join(event):
    """處理機器人加入群組事件"""
    logger.info(f"處理群組加入事件: {event}")
    reply_token = event.reply_token
    reply_message = TextMessage(text="大家好！很高興加入這個群組。請隨時吩咐我查詢新聞、天氣或電影資訊喔！")
    
    result = send_reply(reply_token, [reply_message])
    if result:
        logger.info("成功回覆加入群組訊息")
    else:
        logger.error("回覆加入群組訊息失敗")

@handler.add(FollowEvent)
def handle_follow(event):
    """處理加好友事件"""
    logger.info(f"處理加好友事件: {event}")
    reply_token = event.reply_token
    user_id = event.source.user_id
    logger.info(f"用戶 {user_id} 已將機器人加為好友或解除封鎖")

    # 發送歡迎訊息
    welcome_message = TextMessage(text="感謝您加我為好友！您可以問我新聞、天氣或電影資訊，也可以直接跟我聊天喔！")
    result = send_reply(reply_token, [welcome_message])
    if result:
        logger.info("成功發送歡迎訊息")
    else:
        logger.error("發送歡迎訊息失敗")

@handler.default()
def default_handler(event):
    """處理所有未被明確處理的事件"""
    logger.info(f"收到未處理的事件: {event}")
    # 可以選擇性地回覆一個通用訊息，或是不做任何事
    # reply_token = event.reply_token
    # if reply_token:
    #     send_reply(reply_token, [TextMessage(text="抱歉，我不太明白您的意思。")])
    pass

# 在群組中接收訊息
@handler.add(MessageEvent, message=TextMessageContent)
def handle_group_message(event):
    """處理群組中的文字訊息"""
    if not hasattr(event.source, 'group_id'):
        return  # 跳過非群組訊息

    logger.info(f"處理群組訊息事件: {event}")
    
    group_id = event.source.group_id
    user_id = event.source.user_id
    message_text = event.message.text
    reply_token = event.reply_token
    
    # 只處理以特定前綴開頭的訊息，避免機器人回應所有群組訊息
    if message_text.startswith('@機器人') or message_text.startswith('@bot'):
        # 移除前綴
        query = message_text.replace('@機器人', '').replace('@bot', '').strip()
        logger.info(f"從群組用戶 {user_id} 收到有效指令: {query}")
        
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
                logger.error(f"Gemini 發生錯誤：{e}")
                logger.error(traceback.format_exc())
                reply = f"抱歉，Gemini 發生錯誤：{str(e)[:100]}"
        
        # 回覆訊息給群組
        logger.info(f"準備回覆群組訊息: {reply[:100]}...")
        result = send_reply(reply_token, [TextMessage(text=reply)])
        if result:
            logger.info("成功回覆群組訊息")
        else:
            logger.error("回覆群組訊息失敗")

if __name__ == "__main__":
    # 本地開發使用 debug 模式，生產環境中不使用
    port = int(os.environ.get('PORT', 8080))  # 使用 8080 作為默認端口
    app.run(host='0.0.0.0', port=port, debug=False)