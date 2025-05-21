# LINE 聊天機器人

這是一個功能豐富的 LINE 聊天機器人，使用 Flask 作為後端框架。機器人能夠回應個人聊天和群組訊息，提供智能對話和各種資訊查詢功能。

## 功能特色

1. **智能對話**：使用 Google Gemini AI 模型進行對話，能夠理解並回應各種問題
2. **新聞查詢**：查詢最新新聞資訊（例如：「台灣新聞」或「蘋果新聞」）
3. **天氣查詢**：查詢全球各地天氣狀況（例如：「台北天氣」或「東京天氣」）
4. **電影資訊**：查詢電影的評分、上映日期和簡介（例如：「復仇者電影」或「哈利波特電影」）
5. **群組聊天支援**：在群組中使用 `@機器人` 或 `@bot` 前綴來觸發機器人

## 使用方法

### 個人聊天

直接向機器人發送訊息即可。常用指令：

- 一般對話：直接輸入任何問題或話題
- 新聞查詢：輸入「關鍵字 新聞」（例如：「台灣新聞」）
- 天氣查詢：輸入「城市名稱 天氣」（例如：「台北天氣」）
- 電影資訊：輸入「電影名稱 電影」（例如：「蜘蛛人電影」）

### 群組聊天

在群組中，機器人不會回應所有訊息，需要使用前綴呼叫：

- 使用 `@機器人` 或 `@bot` 開頭，後面接上指令（例如：「@機器人 台北天氣」）

## 本地開發

### 前置需求

- Python 3.8 或更高版本
- LINE 開發者帳號和機器人頻道設定
- 以下 API 金鑰：
  - LINE Messaging API
  - Google Gemini API
  - NewsAPI
  - OpenWeatherMap API
  - TMDb API

### 安裝步驟

1. 安裝相依套件：

```bash
pip install -r requirements.txt
```

2. 更新 `app.py` 中的 API 金鑰或設定環境變數：

```python
# 環境變數
LINE_CHANNEL_ACCESS_TOKEN = '你的 LINE Channel Access Token'
LINE_CHANNEL_SECRET = '你的 LINE Channel Secret'
GOOGLE_GEMINI_API_KEY = '你的 Google Gemini API 金鑰'
NEWS_API_KEY = '你的 NewsAPI 金鑰'
OPENWEATHERMAP_API_KEY = '你的 OpenWeatherMap API 金鑰'
TMDB_API_KEY = '你的 TMDb API 金鑰'
```

3. 啟動應用程式：

```bash
python app.py
```

4. 使用 ngrok 或其他工具暴露本地伺服器（用於開發測試）：

```bash
ngrok http 5000
```

5. 將得到的 HTTPS URL 設定為 LINE 機器人的 Webhook URL：
   - 例如：`https://your-ngrok-url.ngrok.io/callback`

## 部署到 Render

### 部署步驟

1. 創建 [Render](https://render.com/) 帳號並登入。

2. 點擊 Dashboard 中的 "New" 按鈕，選擇 "Web Service"。

3. 連接您的 GitHub 倉庫或直接上傳程式碼。

4. 填寫部署信息：
   - **Name**: 自訂服務名稱（例如：line-bot）
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

5. 在 "Environment Variables" 區域添加以下環境變數：
   ```
   LINE_CHANNEL_ACCESS_TOKEN=你的LINE訪問令牌
   LINE_CHANNEL_SECRET=你的LINE頻道密鑰
   GOOGLE_GEMINI_API_KEY=你的Google Gemini密鑰
   NEWS_API_KEY=你的NewsAPI密鑰
   OPENWEATHERMAP_API_KEY=你的OpenWeatherMap密鑰
   TMDB_API_KEY=你的TMDb密鑰
   ```

6. 選擇適合您的方案，例如免費方案。

7. 點擊 "Create Web Service" 開始部署。

8. 部署完成後，Render 會提供一個域名（例如：`https://your-app-name.onrender.com`）。

9. 將這個域名加上 `/callback` 路徑（例如：`https://your-app-name.onrender.com/callback`）設定為 LINE 機器人的 Webhook URL。

### 自動部署

如果您想設定自動部署，只需將 `render.yaml` 文件添加到您的 GitHub 倉庫根目錄，然後在 Render 上創建一個連接到該倉庫的 Blueprint。每次推送代碼時，Render 將自動重新部署您的應用。

## 生產環境考量

部署到生產環境時，請注意：

1. 總是使用環境變數來存儲敏感信息，而非硬編碼在程式中
2. 移除 `debug=True` 設定（已在 Render 版本中處理）
3. 實作適當的錯誤處理和記錄機制
4. 考慮實施速率限制和緩存機制，以避免超出 API 配額

## 注意事項

- API 金鑰應保密，不應公開分享或提交到版本控制系統
- 遵守各 API 服務的使用條款和限制
- 檢查 API 的免費配額，並適當管理使用量以避免意外收費 