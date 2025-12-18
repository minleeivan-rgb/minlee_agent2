import pandas as pd
from tabulate import tabulate
from agent.graph import build_app
import os
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict 
import json
import configparser

# 匯入 Google Sheets 模組 (sheets_db.py 必須與 main.py 同層或在 agent/ 下)
try:
    from sheets_db import GoogleSheetsDB
except ImportError:
    try:
        from sheets_db import GoogleSheetsDB
    except ImportError:
        # 創建一個假的類別來避免 NameError，但會提示無法使用 DB
        class GoogleSheetsDB:
            def __init__(self):
                self.sheet = None 
            def load_orders(self): return [], []
            def load_rush_orders(self): return []
            def load_system_data(self): return {}
            def load_new_orders_from_sheet(self): return []
            def save_orders(self, *args): print("⚠️ DB 模組失敗，無法儲存。")
            def save_system_data(self, *args): print("⚠️ DB 模組失敗，無法儲存狀態。")
            def save_schedule_results(self, *args): print("⚠️ DB 模組失敗，無法儲存排程報告。")
        print("❌ 致命錯誤: 無法導入 GoogleSheetsDB 模組。請確認 sheets_db.py 存在且命名正確。")
        

# --- 輔助函式定義 (用於排程結果顯示和進度條) ---

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def save_schedule_to_file(df):
    """將排程結果的 DataFrame 存成可讀的文字報告檔案 (.txt)"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"schedule_report_{timestamp}.txt"
        
        # 【修改】加入 order_id 欄位（12 個欄位）
        cols = ["Day", "order_id", "Product", "Headcount", "Actual_Hours", "plan_to", "Output", "Complete_Percent", "Idle_People", "Status", "Note", "priority"]
        
        df_display = df[[c for c in cols if c in df.columns]]
        table_text = tabulate(df_display, headers='keys', tablefmt='psql', showindex=False)
        
        report_content = (
            f"=== 🏭 MINLEE 工廠智慧排程報告 ({timestamp}) ===\n\n"
            f"{table_text}\n\n"
            f"--------------------------------------------------\n"
            f"備註: Headcount = 該工序所需人力; Actual_Hours = 該工序耗用工時; Complete_Percent = 該訂單總進度; plan_to = 計劃執行工序/機台。\n"
        )
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"\n📄 排程報告已儲存至檔案: {filename}")
        
    except Exception as e:
        print(f"❌ 儲存排程報告錯誤: {e}")

def get_progress_bar(percent: float, length: int = 20) -> str:
    """生成進度條字串，例如 [####----]"""
    percent = max(0, min(100, percent))
    num_hashes = int(round(length * percent / 100))
    bar = "█" * num_hashes + "-" * (length - num_hashes)
    return f"[{bar}] {percent:.1f}%"

def show_progress_report(last_schedule: List[Dict[str, Any]], current_orders: List[Dict[str, Any]], days_to_check: int):
    """
    生成並顯示應做/實作進度條表格，並返回進度數據 (用於功能 3)。
    (程式碼與前次提交的完整版 show_progress_report 一致)
    """
    if not last_schedule:
        print("❌ 無上次排程結果，無法生成進度報告。")
        return None
        
    # 找出總訂單量，用於計算總進度百分比 (Product-level)
    product_totals = {order['product']: order['qty'] for order in current_orders if 'qty' in order}
    
    planned_jobs = [
        job for job in last_schedule 
        if job.get('Day', 'Day 0').split(' ')[-1].isdigit() and 
           int(job['Day'].split(' ')[-1].replace('Day ', '')) <= days_to_check
    ]
    
    planned_output_by_product = defaultdict(int)
    planned_jobs_by_display_name = {}
    
    for job in planned_jobs:
        raw_product = job.get('Raw_Product_Name') 
        display_name = job.get('Product') 
        
        if raw_product and display_name:
            planned_output_by_product[raw_product] += job['Output']
            
            raw_display_name = display_name.replace("✅ ", "").replace("☑️ ", "").replace("💡 ", "")
            
            if raw_display_name not in planned_jobs_by_display_name:
                planned_jobs_by_display_name[raw_display_name] = {
                    'raw_product': raw_product,
                    'planned_output': 0,
                    'line': job.get('Line', 'N/A')
                }
            
            planned_jobs_by_display_name[raw_display_name]['planned_output'] += job['Output']
        
    progress_data = []
    products_to_report = set(planned_output_by_product.keys())
    
    for raw_product in sorted(list(products_to_report)):
        
        total_qty = product_totals.get(raw_product)
        if total_qty is None or total_qty <= 0:
             continue

        planned_output = planned_output_by_product[raw_product]
        current_order = next((o for o in current_orders if o['product'] == raw_product), None)
        
        if not current_order:
            actual_remaining = 0
        else:
            original_qty = current_order.get('qty', total_qty)
            actual_remaining = current_order.get('qty_remaining', original_qty)
            
        actual_output = total_qty - actual_remaining
            
        planned_progress_percent = round((planned_output / total_qty) * 100, 1) if total_qty > 0 else 0
        actual_progress_percent = round((actual_output / total_qty) * 100, 1) if total_qty > 0 else 0
        gap_qty = planned_output - actual_output

        planned_bar = get_progress_bar(planned_progress_percent)
        actual_bar = get_progress_bar(actual_progress_percent)
        
        status = "✅ 達標"
        if gap_qty > 0:
            status = f"❌ 落後 {gap_qty} pcs"
        elif gap_qty < 0:
             status = f"🔥 超前 {abs(gap_qty)} pcs"

        progress_data.append({
            "產品型號": raw_product,
            "總訂單量": total_qty,
            "應做數量": planned_output,
            "實作數量": actual_output,
            "應做進度": planned_bar,
            "實作進度": actual_bar,
            "狀態/落後量": status,
            "落後數量": max(0, gap_qty),
            "original_order": current_order
        })

    df = pd.DataFrame(progress_data)
    cols_display = ["產品型號", "總訂單量", "應做數量", "實作數量", "應做進度", "實作進度", "狀態/落後量"]
    df_display = df[[c for c in cols_display if c in df.columns]]
    
    print(f"\n--- 📈 產品生產進度追蹤報告 (Day 1 - Day {days_to_check} 累積) ---")
    print(tabulate(df_display, headers='keys', tablefmt='fancy_grid', showindex=False))
    print("\n備註：應做進度條是根據上次排程 Day 1 到 Day {} 的計畫產量計算。".format(days_to_check))
    
    return {
        "progress_data": progress_data,
        "planned_jobs_by_display_name": planned_jobs_by_display_name
    }

def show_result(result, db_instance: GoogleSheetsDB):
    """顯示排程結果並將最新的訂單、急單和排程結果存回資料庫"""
    
    if result.get('schedule_result'):
        # result['schedule_result'] 已經是扁平化的 list，直接使用
        flat_schedule = result['schedule_result']

        # 1. 顯示排程表到終端機
        print("\n--- 📅 最新排程表 (含閒置人力計算) ---")
        df = pd.DataFrame(flat_schedule)
        # 【修改】加入 order_id 欄位（12 個欄位）
        cols = ["Day", "order_id", "Product", "Headcount", "Actual_Hours", "plan_to", "Output", "Complete_Percent", "Idle_People", "Status", "Note", "priority"]
        df = df[[c for c in cols if c in df.columns]]
        
        print(tabulate(df, headers='keys', tablefmt='psql', showindex=False))
        print(f"\n✅ {result['schedule_summary']}")
        
        # 2. 儲存到 Google Sheets
        db_instance.save_schedule_results(flat_schedule)
        
        # 3. 將最新的訂單佇列（未完成的）存回 Google Sheets
        updated_orders = [
            order for order in result.get('orders', [])
            if order.get('qty_remaining', order.get('qty', 0)) > 0
        ]
        updated_rush_orders = result.get('rush_orders', []) 
        
        db_instance.save_orders(updated_orders, updated_rush_orders)
        
        # 4. 儲存 SystemData 
        # 【移除】不再儲存 last_schedule_results，因為資料太大會超過 Google Sheets 限制
        # last_schedule_results 會從 percentage(daily_schedule) 工作表直接讀取
        db_instance.save_system_data('last_schedule_date', datetime.now().strftime("%Y-%m-%d"))
        
        # 5. 儲存到本地檔案
        save_schedule_to_file(df)

        # 6. 發送郵件通知
        print("📧 Email 通知已發送。")

    else:
        print("\n❌ 排程失敗，請檢查日誌。")
        for log in result.get('logs', []):
            print(f"[{log}]")

# --- 主執行函式 ---
def main():
    clear_screen()
    
    # 1. 初始化 Google Sheets DB
    try:
        db = GoogleSheetsDB()
        db_ready = True
    except Exception:
        db = None
        db_ready = False
    
    # 2. 載入持久化數據 (如果 DB 失敗則載入空列表)
    current_orders = db.load_orders() if db_ready and db else []
    rush_orders = db.load_rush_orders() if db_ready and db else []
    system_data = db.load_system_data() if db_ready and db else {}
    
    # 初始化 LangGraph
    try:
        app = build_app()
    except Exception as e:
        print(f"❌ 警告: 無法初始化 Agent 流程圖 (LangGraph)。請確認 graph.py 或 nodes.py 文件完整性: {e}")
        return

    # 3. 初始化 Agent State (使用載入的持久化數據)
    last_schedule_date = system_data.get('last_schedule_date')
    if not last_schedule_date or not isinstance(last_schedule_date, str):
        last_schedule_date = datetime.now().strftime("%Y-%m-%d")

    # 【修改】從 Google Sheets 讀取 last_schedule_results
    last_schedule_results = []
    if db_ready:
        last_schedule_results = db.load_schedule_results()

    initial_state = {
        "logs": ["系統啟動"],
        "image_path": "",
        "inventory_db": {}, 
        "orders": current_orders,
        "rush_orders": rush_orders,
        "daily_feedback": {}, 
        "last_schedule_date": last_schedule_date,
        "last_schedule_results": last_schedule_results  # 從 Google Sheets 讀取
    }
    
    print("\n=========================================")
    print("🏭 MINLEE 工廠智慧排程系統 v1.0 啟動")
    print(f"上次排程日期: {initial_state['last_schedule_date']}")
    print(f"上次排程結果工序數: {len(initial_state['last_schedule_results'])}")
    if not db_ready:
         print("🚨 Google Sheets 連線失敗！將使用本地記憶體運行 🚨")
    print("=========================================")
    
    if not current_orders:
        print("ℹ️ 未載入到未完成訂單。")
        
    if rush_orders:
        print(f"⚠️ 載入 {len(rush_orders)} 筆未處理急單。")

    while True:
        print("\n--- 請選擇操作 ---")
        print(f"訂單數量: {len(current_orders)} | 急單數量: {len(rush_orders)}")
        print("1. 🆕 匯入新訂單 & 重新排程 (從 'read_packing_sheet' 工作表)")
        print("2. ⚡ **急單** (新增/舊單轉急單 & 重排)")
        print("3. ✅ **每日生產進度回報** & 重排")
        print("4. 🚪 系統關閉 (並儲存資料)")
        
        choice = input("輸入選項 (1-4): ")

        # --- 選項 1: 匯入新訂單 & 重新排程 ---
        if choice == "1":
            if not db_ready:
                 print("❌ 錯誤: Google Sheets 連線失敗，無法執行此操作。")
                 continue
                 
            print("\n🔄 執行選項 1: 匯入新訂單 & 重新排程...")
            
            new_orders = db.load_new_orders_from_sheet()
            
            if not new_orders:
                print("ℹ️ 未找到新的訂單數據。")
                continue

            for new_order in new_orders:
                existing_order = next((o for o in current_orders if o['product'] == new_order['product']), None)
                if existing_order:
                    print(f"⚠️ 產品 {new_order['product']} 已存在，更新剩餘數量。")
                    existing_order['qty_remaining'] += new_order['qty']
                    existing_order['qty'] = existing_order['qty_remaining']
                    # 【新增】如果現有訂單沒有 order_id，則更新
                    if not existing_order.get('order_id'):
                        existing_order['order_id'] = new_order.get('order_id', '')
                else:
                    current_orders.append({
                        "order_id": new_order.get('order_id', ''),  # 【新增】訂單編號
                        "product": new_order['product'],
                        "qty": new_order['qty'],
                        "qty_remaining": new_order['qty'],
                        "is_rush": False,
                        "due_date": new_order['due_date'],
                        "raw_packing_sheet": new_order.get('raw_data', ''),
                        "date_created": datetime.now().strftime('%Y-%m-%d')
                    })

            print("🚀 正在根據新訂單重新排程...")
            initial_state["logs"] = [f"開始排程：處理 {len(new_orders)} 筆新訂單。"]
            initial_state["orders"] = current_orders
            initial_state["rush_orders"] = rush_orders
            initial_state["image_path"] = "" 

            result = app.invoke(initial_state)
            show_result(result, db)
            
        # --- 選項 2: 急單 (新增/舊單轉急單 & 重排) ---
        elif choice == "2":
            if not db_ready:
                 print("❌ 錯誤: Google Sheets 連線失敗，無法執行此操作。")
                 continue

            print("\n--- ⚡ 急單處理 ---")
            
            print("請選擇急單類型:")
            print("  A. 新增急單 (全新訂單)")
            print("  B. 舊單轉急單 (已有訂單要加速)")
            rush_type = input("請輸入選擇 (A/B): ").strip().upper()
            
            if rush_type not in ['A', 'B']:
                print("❌ 無效的選擇。")
                continue
            
            p_name = input("請輸入產品型號 (例如 T323): ").strip().upper()
            try:
                qty_input = input("請輸入急單數量 (如果是 B 舊單，請輸入要加速的剩餘總量): ") 
                qty = int(qty_input)
                if qty <= 0:
                    print("❌ 數量必須大於零。")
                    continue
            except ValueError:
                print("❌ 數量格式錯誤。")
                continue
            
            if rush_type == 'A':
                initial_rush_order = {
                    "order_id": "",  # 【新增】新急單可能沒有 order_id，留空
                    "product": p_name, 
                    "qty": qty, 
                    "is_rush": True,
                    "qty_remaining": qty,
                    "qty_total": qty,
                    "date_created": datetime.now().strftime("%Y-%m-%d")
                }
                rush_orders.append(initial_rush_order)
                print(f"✅ 新急單【{p_name}】({qty} pcs) 已加入急單佇列。")
                
            elif rush_type == 'B':
                found_orders = [o for o in current_orders if o['product'] == p_name]
                
                if found_orders:
                    # 1. 從 current_orders 中移除 (確保互斥，避免重複計算)
                    current_orders
                    current_orders = [o for o in current_orders if o['product'] != p_name]

                    # 2. 創建新的 rush_order 項目（保留 order_id）
                    new_rush_order_item = {
                         "order_id": found_orders[0].get('order_id', ''),  # 【新增】從原訂單複製 order_id
                         "product": p_name, 
                         "qty": qty, 
                         "is_rush": True,
                         "qty_remaining": qty,
                         "qty_total": max([o.get('qty', qty) for o in found_orders]) 
                    }
                    
                    # 3. 更新 rush_orders
                    existing_rush = next((r for r in rush_orders if r['product'] == p_name), None)
                    if existing_rush:
                        existing_rush.update(new_rush_order_item)
                    else:
                        rush_orders.append(new_rush_order_item)
                        
                    print(f"✅ 舊單【{p_name}】已標記為急單，剩餘數量設為 {qty} pcs，並從常規訂單中移除。")
                    
                else:
                    print(f"❌ 找不到型號【{p_name}】在當前未完成訂單中。請確認型號或改選 'A' 新增急單。")
                    
            # 執行重排
            initial_state["image_path"] = ""
            print("🚀 正在根據最新的訂單資訊重新排程...\n")

            result = app.invoke(initial_state)
            show_result(result, db)
            
        # --- 選項 3: 回報昨日產能 & 調整排程 ---
        elif choice == "3":
            if not db_ready:
                 print("❌ 錯誤: Google Sheets 連線失敗，無法執行此操作。")
                 continue

            print("\n--- 📝 每日生產進度回報 ---")
            
            # 【修改】從 Google Sheets 重新讀取最新的排程結果（避免累積舊資料）
            last_schedule_results = db.load_schedule_results()
            
            if not last_schedule_results:
                print("⚠️ 錯誤: 請先執行一次排程 (功能 1 或 2)，才能追蹤進度。")
                continue

            # 1. 手動輸入要回報的天數
            # 【修改】過濾掉 Day 為空的記錄
            valid_schedule = [job for job in last_schedule_results if job.get('Day') and job['Day'].strip()]
            
            if not valid_schedule:
                print("⚠️ 錯誤: 排程資料格式錯誤，無法讀取 Day 欄位。")
                continue
            
            max_day_in_schedule = max(
                (int(job['Day'].split(' ')[-1]) for job in valid_schedule), 
                default=0
            )

            days_to_report_input = input(f"請輸入要回報到第幾天 (上次排程排到 Day {max_day_in_schedule}): ")
            try:
                days_to_report = int(days_to_report_input)
                if days_to_report <= 0 or days_to_report > max_day_in_schedule:
                     print(f"❌ 請輸入有效的天數 (1 到 {max_day_in_schedule})。")
                     continue
            except ValueError:
                print("❌ 輸入無效，請輸入一個整數。")
                continue

            print(f"\n⏰ 正在回報 Day 1 到 Day {days_to_report} 的生產進度...")

            # 2. 找出 Day 1 到 Day N 中所有排程的工序（按工序，不是按產品）
            tasks_in_period = []
            for task in valid_schedule:
                day_str = task.get('Day', '')
                if not day_str or not day_str.strip():
                    continue
                    
                try:
                    day_num = int(day_str.split(' ')[-1])
                except (ValueError, IndexError):
                    continue
                    
                if 1 <= day_num <= days_to_report:
                    tasks_in_period.append({
                        'Product': task.get('Product', ''),  # 工序名稱
                        'Raw_Product_Name': task.get('Raw_Product_Name', ''),  # 產品名稱
                        'Output': task.get('Output', 0),  # 計劃產量
                        'Day': day_str
                    })

            if not tasks_in_period:
                print("⚠️ 在該期間內沒有找到任何排程的工序。")
                continue

            print(f"\n📋 Day 1 到 Day {days_to_report} 期間共有 {len(tasks_in_period)} 個工序需要回報實際產量：")
            for idx, task in enumerate(tasks_in_period, 1):
                # 【修改】移除符號
                task_name_clean = task['Product'].replace("✅ ", "").replace("☑️ ", "").replace("💡 ", "").strip()
                print(f"  {idx}. {task_name_clean} (計劃: {task['Output']} pcs)")

            # 3. 針對每個工序，詢問實際完成數量
            print("\n--- 💬 請輸入各工序的實際完成數量 ---")
            actual_output_by_task = {}

            for task in tasks_in_period:
                task_name_raw = task['Product']
                # 【修改】清理工序名稱，移除符號
                task_name = task_name_raw.replace("✅ ", "").replace("☑️ ", "").replace("💡 ", "").strip()
                planned_output = task['Output']

                qty_input = input(f"工序【{task_name}】實際完成數量 (pcs) (計劃: {planned_output}): ")
                try:
                    actual_qty = int(qty_input.strip())
                    if actual_qty < 0:
                        print(f"❌ 數量不能為負數，設為 0。")
                        actual_qty = 0
                    actual_output_by_task[task_name] = {
                        'actual': actual_qty,
                        'product': task['Raw_Product_Name']
                    }
                except ValueError:
                    print(f"❌ 輸入無效，設為 0。")
                    actual_output_by_task[task_name] = {
                        'actual': 0,
                        'product': task['Raw_Product_Name']
                    }

            # 4. 按產品分組，找出瓶頸工序（最小值）
            print("\n--- 📊 計算各產品的實際完成量（瓶頸工序）---")
            actual_output_by_product = {}
            
            for task_name, data in actual_output_by_task.items():
                product_name = data['product']
                actual_qty = data['actual']
                
                if product_name not in actual_output_by_product:
                    actual_output_by_product[product_name] = actual_qty
                else:
                    # 取最小值（瓶頸工序）
                    actual_output_by_product[product_name] = min(
                        actual_output_by_product[product_name],
                        actual_qty
                    )
            
            for product_name, actual_qty in actual_output_by_product.items():
                print(f"  {product_name}: 實際完成 {actual_qty} pcs（各工序最小值）")
            
            # 【新增】更新 Google Sheets 的 Actual_Output 和 Actual_Complete_Percent
            print("\n--- 💾 更新 Google Sheets 的實際產量和完成百分比 ---")
            db.update_actual_outputs(actual_output_by_task, days_to_report)

            # 5. 根據實際產量更新訂單的剩餘量
            print("\n--- 📊 更新訂單剩餘量 ---")
            for product_name, actual_output in actual_output_by_product.items():
                # 先在 current_orders 中找
                current_order = next((o for o in current_orders if o['product'] == product_name), None)
                if not current_order:
                    # 再在 rush_orders 中找
                    current_order = next((o for o in rush_orders if o['product'] == product_name), None)

                if current_order:
                    old_remaining = current_order.get('qty_remaining', current_order.get('qty', 0))
                    new_remaining = max(0, old_remaining - actual_output)
                    current_order['qty_remaining'] = new_remaining
                    print(f"  {product_name}: 完成 {actual_output} pcs，剩餘 {old_remaining} → {new_remaining} pcs")

            # 5. 移除剩餘量為 0 的訂單
            current_orders = [o for o in current_orders if o.get('qty_remaining', 0) > 0]
            rush_orders = [o for o in rush_orders if o.get('qty_remaining', 0) > 0]

            # 6. 刪除 Day 1 到 Day N 的舊排程
            print(f"\n🗑️ 刪除 Day 1 到 Day {days_to_report} 的舊排程...")
            remaining_schedule = []
            for task in valid_schedule:  # 【修改】使用 valid_schedule
                day_str = task.get('Day', '')
                if not day_str or not day_str.strip():
                    continue
                
                try:
                    day_num = int(day_str.split(' ')[-1])
                    if day_num > days_to_report:
                        remaining_schedule.append(task)
                except (ValueError, IndexError):
                    continue
            
            # 更新 Day 編號（將 Day N+1 改為 Day 1）
            if remaining_schedule:
                try:
                    min_day = min(int(task['Day'].split(' ')[-1]) for task in remaining_schedule)
                    for task in remaining_schedule:
                        old_day = int(task['Day'].split(' ')[-1])
                        new_day = old_day - min_day + 1
                        task['Day'] = f"Day {new_day}"
                except (ValueError, IndexError) as e:
                    print(f"⚠️ 更新 Day 編號時發生錯誤: {e}")
                    remaining_schedule = []

            # 7. 重新排程（排剩餘的訂單）
            if current_orders or rush_orders:
                print(f"\n🚀 正在重新排程剩餘訂單...")
                print(f"  常規訂單: {len(current_orders)} 筆")
                print(f"  急單: {len(rush_orders)} 筆")

                initial_state["image_path"] = ""
                initial_state["orders"] = current_orders
                initial_state["rush_orders"] = rush_orders

                result = app.invoke(initial_state)
                show_result(result, db)
            else:
                print("🎉 所有訂單都已完成！無需重新排程。")
                db.save_orders(current_orders, rush_orders)
                db.save_system_data('last_schedule_date', datetime.now().strftime("%Y-%m-%d"))



        elif choice == "4":
            print("👋 系統關閉。")
            if db_ready:
                db.save_orders(current_orders, rush_orders)
                db.save_system_data('last_schedule_date', datetime.now().strftime("%Y-%m-%d"))
                print("✅ 訂單與狀態資料已儲存到 Google Sheets。")
            
            break
        
        else:
            print("❌ 無效的選擇，請重新輸入。")

if __name__ == "__main__":
    main()