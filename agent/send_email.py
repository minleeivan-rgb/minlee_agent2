import smtplib
import configparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def send_alert(subject, body):
    # --- 1. 智慧尋找 config.ini ---
    # 取得目前這個檔案 (send_email.py) 的資料夾路徑 -> agent/
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 推算 config.ini 應該在上一層資料夾 -> MINLEE_AGENT/config.ini
    config_path = os.path.join(current_dir, '..', 'config.ini')
    
    # 確保路徑是標準格式
    config_path = os.path.abspath(config_path)

    config = configparser.ConfigParser()
    # 嘗試讀取
    read_files = config.read(config_path, encoding='utf-8')
    
    # 如果讀不到，嘗試直接讀當前目錄 (備案)
    if not read_files:
        read_files = config.read('config.ini', encoding='utf-8')

    # 如果還是讀不到，報錯並結束
    if not read_files:
        print(f"❌ Email 模組錯誤：找不到 config.ini！")
        print(f"   嘗試過的路徑: {config_path} 或 ./config.ini")
        return

    # --- 2. 讀取設定與發送 ---
    try:
        sender = config['EMAIL']['SENDER']
        password = config['EMAIL']['PASSWORD']
        receiver = config['EMAIL']['RECEIVER']
        
        # 建立郵件物件
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = receiver
        msg['Subject'] = f"🏭 MINLEE_AGENT: {subject}"
        
        msg.attach(MIMEText(body, 'plain'))
        
        # 使用 Gmail SMTP (SSL)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print("📧 Email 發送成功！")

    except KeyError as e:
        print(f"❌ Email 發送失敗: config.ini 缺少欄位 {e}")
    except smtplib.SMTPAuthenticationError:
        print("❌ Email 登入失敗: 帳號或應用程式密碼錯誤。")
    except Exception as e:
        print(f"❌ Email 發送失敗 (未預期錯誤): {e}")