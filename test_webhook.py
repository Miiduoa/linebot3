import requests
import json
import time
import argparse
import hmac
import hashlib
import base64

def test_line_webhook(webhook_url, channel_secret):
    """測試 LINE Webhook 連接和簽名驗證"""
    print(f"測試 Webhook URL: {webhook_url}")
    
    # 構建一個標準的 LINE 文字消息事件
    test_event = {
        "destination": "xxxxxxxxxx",
        "events": [
            {
                "type": "message",
                "message": {
                    "type": "text",
                    "id": "12345678901234",
                    "text": "這是測試訊息"
                },
                "timestamp": int(time.time() * 1000),
                "source": {
                    "type": "user",
                    "userId": "Udeadbeefdeadbeefdeadbeefdeadbeef"
                },
                "replyToken": "deadbeefdeadbeefdeadbeefdeadbeef",
                "mode": "active"
            }
        ]
    }
    
    # 轉換為 JSON 字符串
    body = json.dumps(test_event)
    
    # 生成 X-Line-Signature 頭部
    signature = generate_line_signature(body, channel_secret)
    
    # 設置請求頭
    headers = {
        'Content-Type': 'application/json',
        'X-Line-Signature': signature
    }
    
    # 發送請求
    print("\n發送測試請求...")
    try:
        response = requests.post(webhook_url, headers=headers, data=body)
        print(f"狀態碼: {response.status_code}")
        print(f"回應內容: {response.text}")
        
        if response.status_code == 200:
            print("\n✓ 測試成功！您的 webhook 已正確接收並驗證請求。")
            print("請檢查伺服器日誌以確認是否正確處理了訊息。")
        else:
            print("\n✗ 測試失敗。您的 webhook 返回了非 200 狀態碼。")
            print("請檢查伺服器日誌以獲取更多詳情。")
    except Exception as e:
        print(f"\n✗ 連接錯誤: {e}")
        print("請檢查 webhook URL 是否正確且可訪問。")

def generate_line_signature(body, channel_secret):
    """生成 LINE 簽名"""
    hash = hmac.new(channel_secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
    signature = base64.b64encode(hash).decode('utf-8')
    return signature

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='測試 LINE Webhook 連接')
    parser.add_argument('--url', required=True, help='完整的 webhook URL，例如: https://your-app.onrender.com/callback')
    parser.add_argument('--secret', required=True, help='LINE 頻道密鑰')
    
    args = parser.parse_args()
    test_line_webhook(args.url, args.secret) 