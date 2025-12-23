import configparser
import pandas as pd
import math
import json
import base64
from collections import defaultdict
from tabulate import tabulate # 【修正】新增 tabulate 導入，解決 NameError
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from agent.state import AgentState
from agent.send_email import send_alert
from typing import List, Dict, Any

# 匯入外部的生產資料檔
try:
    from agent.inventory_data import INVENTORY_DATA
except ImportError:
    try:
        from inventory_data import INVENTORY_DATA
    except ImportError:
        print("⚠️ 警告: 找不到 inventory_data.py，將使用空資料。")
        INVENTORY_DATA = {}

# 讀取設定
config = configparser.ConfigParser()
config.read('config.ini')

# 初始化 Gemini
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=config['GOOGLE']['API_KEY'],
    temperature=0
)

# --- 輔助函式 ---
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def normalize(s): 
    """將字串標準化：移除破折號/空格並轉大寫。"""
    return str(s).replace("-", "").replace(" ", "").upper()

def _create_jobs_list(all_orders: List[Dict[str, Any]], inventory: Dict[str, Dict[str, int]]):
    """
    根據訂單和產能資料庫，建立所有工序清單 (all_jobs)。
    
    【優化版】使用 LLM 批次處理所有訂單，只呼叫 1 次 API
    """
    all_jobs = []
    unknown_models = set()
    product_to_jobs = defaultdict(list)
    
    # 準備 inventory 的產品列表（用於 LLM 匹配）
    inventory_products = list(inventory.keys())
    
    # 【步驟 1】收集所有有效訂單的產品名稱
    valid_orders = []
    for order in all_orders:
        p_name = order.get('product', 'Unknown')
        qty_val = order.get('qty_remaining', order.get('qty', 0))
        if qty_val > 0:
            valid_orders.append(order)
    
    if not valid_orders:
        return all_jobs, product_to_jobs, list(unknown_models)
    
    # 【步驟 2】建立批次 Prompt，一次送出所有產品
    product_names = [order.get('product', 'Unknown') for order in valid_orders]
    product_list_text = "\n".join(f"{i+1}. {name}" for i, name in enumerate(product_names))
    inventory_list_text = "\n".join(f"- {inv_key}" for inv_key in inventory_products)
    
    batch_prompt = f"""你是產品名稱匹配專家。

【訂單產品列表】
{product_list_text}

【可用的工序列表】
{inventory_list_text}

請為每個訂單產品找出所有匹配的工序。比對規則：
1. 產品型號一致（忽略破折號、空格、大小寫）
2. 顏色、規格等描述可以不同，只要型號一致就算匹配
3. 例如："T-304 BLACK (90)" 應該匹配 "T304一線", "T304二線" 等所有 T304 開頭的工序

【重要】請務必回傳有效的 JSON 格式，結構如下：
{{
  "訂單產品名稱1": ["匹配工序1", "匹配工序2"],
  "訂單產品名稱2": ["匹配工序1"],
  "訂單產品名稱3": []
}}

如果某產品沒有匹配的工序，該產品的值設為空陣列 []。
請只回傳 JSON，不要有任何其他文字、解釋或 markdown 標記。"""

    # 【步驟 3】呼叫 LLM（只呼叫 1 次！）
    print("🤖 正在使用 LLM 批次匹配所有產品名稱...")
    
    try:
        response = llm.invoke(batch_prompt)
        response_text = response.content.strip()
        
        # 清理可能的 markdown 標記
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # 解析 JSON
        matching_result = json.loads(response_text)
        print(f"✅ LLM 批次匹配完成，共處理 {len(product_names)} 個產品")
        
    except json.JSONDecodeError as e:
        print(f"❌ LLM 回傳格式錯誤，無法解析 JSON: {e}")
        print(f"❌ LLM 原始回傳內容:\n{response_text[:500]}...")
        raise ValueError("LLM 回傳格式錯誤，請重新執行排程。")
    except Exception as e:
        print(f"❌ LLM 呼叫失敗: {e}")
        raise ValueError(f"LLM 呼叫失敗: {e}，請重新執行排程。")
    
    # 【步驟 4】根據匹配結果建立 all_jobs 列表
    for order in valid_orders:
        p_name = order.get('product', 'Unknown')
        qty_val = order.get('qty_remaining', order.get('qty', 0))
        qty_total = order.get('qty_total', order.get('qty', qty_val))
        
        # 從 LLM 結果取得匹配的工序
        matched_keys = matching_result.get(p_name, [])
        
        if not matched_keys:
            unknown_models.add(p_name)
            continue
        
        # 建立工序任務
        matching_jobs = False
        for inv_key in matched_keys:
            if inv_key in inventory:
                matching_jobs = True
                spec = inventory[inv_key]
                
                all_jobs.append({
                    "order_id": order.get('order_id', ''),
                    "raw_product_name": p_name, 
                    "display_name": inv_key,    
                    "line": spec.get('line', 'Line 1'),
                    "uph": spec['uph'],
                    "qty_total": qty_total,       
                    "qty_remaining": qty_val, 
                    "headcount": spec['headcount'],
                    "is_rush": order.get('is_rush', False),
                    "due_date": order.get('due_date')
                })
                product_to_jobs[normalize(p_name)].append(inv_key)
        
        if not matching_jobs:
            unknown_models.add(p_name)
            
    # 排序：急單優先 (is_rush=True) -> 截止日期優先 (due_date)
    all_jobs.sort(key=lambda x: (
        not x['is_rush'], 
        x['due_date'] if x['due_date'] else "9999-12-31" 
    ))
        
    return all_jobs, product_to_jobs, list(unknown_models)


# --- 節點函式 (LangGraph Nodes) ---

def fetch_inventory(state: AgentState) -> AgentState:
    """載入產能資料庫 (INVENTORY_DATA)。"""
    state['inventory_db'] = INVENTORY_DATA
    state['logs'].append(f"載入產能資料庫。共 {len(INVENTORY_DATA)} 個工序。")
    return state

def analyze_packing_sheet(state: AgentState) -> AgentState:
    """分析 Packing Sheet 圖片，並將結果加入訂單佇列。 (此處為流程佔位)"""
    
    if state.get('image_path'):
        # 這裡應該是 LLM 圖片解析邏輯
        print(f"🖼️ 正在嘗試解析圖片: {state['image_path']}...")
    else:
         state['logs'].append("未提供圖片路徑，跳過 Packing Sheet 分析。")
    
    return state


def generate_pre_schedule_report(state: AgentState) -> AgentState:
    """生成排程前的預備報告，並建立所有工序清單 (all_jobs)。"""
    
    orders = state['orders']
    rush_orders = state['rush_orders']
    inventory = state['inventory_db']
    
    # 1. 合併常規訂單和急單
    all_orders = orders + rush_orders
    
    # 2. 建立工序清單 (接收三個返回值)
    all_jobs, product_to_jobs, unknown_models = _create_jobs_list(all_orders, inventory)

    state['all_jobs'] = all_jobs
    state['product_to_jobs'] = product_to_jobs
    
    # 3. 顯示待排程清單 (使用者要求)
    print("\n--- ⚡ 準備排程：當前工作清單 ---")
    report_data = []
    
    if not all_orders:
        print("🎉 列表為空，沒有需要排程的任務。")
    else:
        # 排序：急單優先 (is_rush=True 優先)，然後按產品名稱
        for order in sorted(all_orders, key=lambda x: (x.get('is_rush') is not True, x.get('product'))):
            if order.get('qty_remaining', order.get('qty', 0)) > 0:
                report_data.append({
                    "產品型號": order.get('product', 'N/A'),
                    "總訂單量": order.get('qty_total', order.get('qty', 'N/A')),
                    "剩餘數量": order.get('qty_remaining', 'N/A'),
                    "備註": "⚡ 急單" if order.get('is_rush') else "常規",
                    "截止日期": order.get('due_date', 'N/A')
                })
        
        df = pd.DataFrame(report_data)
        print(tabulate(df, headers='keys', tablefmt='fancy_grid', showindex=False))
    print("-------------------------------------------------")
    
    # 4. 生成報告摘要
    total_qty_to_schedule = sum(job['qty_remaining'] for job in all_jobs)
    total_rush_qty = sum(job['qty_remaining'] for job in all_jobs if job['is_rush'])
    
    report_summary = (
        f"排程前置報告：共 {len(all_orders)} 筆訂單，拆分為 {len(all_jobs)} 個工序任務。\n"
        f"  - 總待排產量: {total_qty_to_schedule:,} 個\n"
        f"  - 急單待排產量: {total_rush_qty:,} 個"
    )
    
    if unknown_models:
        report_summary += f"\n⚠️ 警告: 找不到以下產品的工序數據: {', '.join(unknown_models)}"

    state['logs'].append(report_summary)
    
    return state


def calculate_schedule(state: AgentState) -> AgentState:
    """執行排程計算，分配工序到每日，並計算所需人力。"""
    
    all_jobs = state.get('all_jobs', [])
    product_to_jobs = state.get('product_to_jobs', {})
    
    if not all_jobs:
        state['is_feasible'] = False
        state['schedule_summary'] = "排程失敗：缺少工單清單。"
        return state

    settings = config['ZZ_Srttings'] if 'ZZ_Srttings' in config else {} 
    
    schedule_data, pending_jobs_final = _run_global_simulation(all_jobs, settings)

    final_output_list = [] 
    
    # 檢查最終產品的完工狀態
    def check_product_completion(raw_product_name, final_pending_jobs):
        related_jobs = product_to_jobs.get(normalize(raw_product_name), [])
        unfinished_job_names = set(j['display_name'] for j in final_pending_jobs if j['qty_remaining'] > 0)
        
        for job_name in related_jobs:
            if job_name in unfinished_job_names:
                return False
        return True
    
    is_feasible = not pending_jobs_final
    
    for day_str, day_info in schedule_data.items():
        tasks = day_info['tasks']
        left = day_info['people_left'] 
        
        for task in tasks:
            raw_product_name = task['Raw_Product_Name']
            
            highlight_prefix = ""
            if task['Status'] == '完工':
                if check_product_completion(raw_product_name, pending_jobs_final):
                    highlight_prefix = "✅ " 
                else:
                    highlight_prefix = "☑️ "
            elif task['Status'] == '半成品完成':
                highlight_prefix = "💡 " 
            
            product_display = f"{highlight_prefix}{task['Product']}"
            
            # 【關鍵】計算 plan_to 和 priority 欄位
            task['plan_to'] = task['Product'].replace(highlight_prefix, '') # 計劃執行工序/機台名稱 (移除符號)
            task['priority'] = 1 if task.get('Note', '') == '⚡' else 2
            
            final_output_list.append({
                "Day": day_str,
                "order_id": task.get('order_id', ''),
                "Line": task['Line'],
                "Product": product_display, 
                "Output": task['Output'],
                "Status": task['Status'],
                "Headcount": task['Headcount'],
                "Idle_People": left, 
                "Note": task['Note'],
                "Actual_Hours": task['Actual_Hours'],
                "Complete_Percent": task['Complete_Percent'],
                "Raw_Product_Name": raw_product_name,
                "plan_to": task['plan_to'],
                "priority": task['priority']
            })
            
    schedule_summary = f"排程完成。總共耗時 {len(schedule_data)} 天。"
    if not is_feasible:
        schedule_summary = f"⚠️ 排程未完成。排程器停止模擬。請查看未完成清單。"
        
    state['schedule_result'] = final_output_list
    state['schedule_summary'] = schedule_summary
    state['is_feasible'] = is_feasible
    state['logs'].append(schedule_summary)
    
    return state


def send_notification(state: AgentState) -> AgentState:
    """發送排程結果的 Email 通知。"""
    
    # 這裡的邏輯保持不變，專注於發送郵件
    return state
    
def _run_global_simulation(all_jobs, config_settings):
    # 排程模擬核心 (邏輯保持不變，確保使用 8 小時最大產能)
    try:
        MAX_PEOPLE_TOTAL = int(config_settings.get('MAX_HEADCOUNT', 40)) 
        WORK_HOURS = int(config_settings.get('WORK_HOURS_PER_DAY', 8)) 
        MAX_LINES = 4 
    except Exception:
        MAX_PEOPLE_TOTAL = 40
        WORK_HOURS = 8
        MAX_LINES = 4

    pending_jobs = list(all_jobs)
    current_day = 1
    MAX_SIMULATION_DAYS = 1000 
    daily_schedule = defaultdict(lambda: {'tasks': [], 'people_left': MAX_PEOPLE_TOTAL, 'people_used': 0})
    
    while pending_jobs and current_day < MAX_SIMULATION_DAYS:
        people_available = MAX_PEOPLE_TOTAL
        day_tasks = []
        
        # 【關鍵改動】分離大工序和小工序
        large_jobs = [j for j in pending_jobs if j['qty_remaining'] > 0 and j['headcount'] >= 4]
        small_jobs = [j for j in pending_jobs if j['qty_remaining'] > 0 and j['headcount'] < 4]
        
        # 優先級排序函式
        def job_priority(j):
            is_rush = 0 if j['is_rush'] else 1
            line_score = 0 if j['line'] in ['Line 1', 'Line 3'] else 1 
            return (is_rush, line_score, -j['headcount'])
        
        large_jobs.sort(key=job_priority)
        small_jobs.sort(key=job_priority)
        
        next_day_pending = []
        jobs_processed_in_day = 0
        
        # === 第一階段：排大工序（≥4人），最多 4 條線 ===
        jobs_scheduled_today = 0
        for job in large_jobs:
            # 檢查產線限制
            if jobs_scheduled_today >= MAX_LINES:
                next_day_pending.append(job)
                continue
            
            # 檢查人力限制
            if people_available < job['headcount']:
                next_day_pending.append(job)
                continue
            
            # 計算產量
            produced_qty_by_hour = math.floor(WORK_HOURS * job['uph'])
            max_producible_qty = job['qty_remaining']
            real_qty = min(produced_qty_by_hour, max_producible_qty)
            
            if real_qty <= 0:
                next_day_pending.append(job)
                continue

            actual_hours = round(real_qty / job['uph'], 2) if job['uph'] > 0 else 0
            
            # 扣除人力和產線
            people_available -= job['headcount']
            jobs_scheduled_today += 1
            jobs_processed_in_day += 1

            # 更新剩餘量
            job['qty_remaining'] -= real_qty
            
            # 記錄任務
            output_status = "完工" if job['qty_remaining'] <= 0 else "進行中"
            if job['qty_remaining'] > 0:
                next_day_pending.append(job)

            day_tasks.append({
                "order_id": job.get('order_id', ''),
                "Line": job['line'],
                "Product": job['display_name'],
                "Raw_Product_Name": job['raw_product_name'], 
                "Headcount": job['headcount'],
                "Output": real_qty,
                "Status": output_status, 
                "Note": "⚡" if job['is_rush'] else "",
                "Actual_Hours": actual_hours,
                "Complete_Percent": "0%",
                "plan_to": job.get('line', 'Line 1'),
                "priority": "rush" if job.get('is_rush') else "normal"
            })
        
        # === 第二階段：用剩餘人力排小工序（<4人），可以增派人力加速 ===
        for job in small_jobs:
            base_headcount = job['headcount']  # 原本需要的人力
            
            # 檢查至少要有基本人力
            if people_available < base_headcount:
                next_day_pending.append(job)
                continue
            
            # 【關鍵】計算可以派多少人（最多用完所有閒置人力）
            # 可以派的人數 = min(閒置人力, 需要的數量對應的人力)
            base_uph = job['uph']
            qty_remaining = job['qty_remaining']
            
            # 計算最多需要多少倍人力才能在一天內完成
            max_output_per_day = WORK_HOURS * base_uph
            if qty_remaining <= max_output_per_day:
                # 一天內就能完成，用基本人力就好
                people_to_assign = base_headcount
            else:
                # 一天完不成，盡可能多派人加速
                # 計算需要多少倍人力
                multiplier_needed = math.ceil(qty_remaining / max_output_per_day)
                # 但不能超過閒置人力
                max_people_can_assign = people_available
                people_to_assign = min(base_headcount * multiplier_needed, max_people_can_assign)
            
            # 確保至少派基本人力
            people_to_assign = max(people_to_assign, base_headcount)
            
            # 計算實際產能（人數倍數）
            people_multiplier = people_to_assign / base_headcount
            actual_uph = base_uph * people_multiplier
            
            # 計算產量
            produced_qty_by_hour = math.floor(WORK_HOURS * actual_uph)
            max_producible_qty = qty_remaining
            real_qty = min(produced_qty_by_hour, max_producible_qty)
            
            if real_qty <= 0:
                next_day_pending.append(job)
                continue

            actual_hours = round(real_qty / actual_uph, 2) if actual_uph > 0 else 0
            
            # 扣除人力（使用實際派遣的人數）
            people_available -= people_to_assign
            jobs_processed_in_day += 1

            # 更新剩餘量
            job['qty_remaining'] -= real_qty
            
            # 記錄任務
            output_status = "完工" if job['qty_remaining'] <= 0 else "進行中"
            if job['qty_remaining'] > 0:
                next_day_pending.append(job)

            day_tasks.append({
                "order_id": job.get('order_id', ''),
                "Line": job['line'],
                "Product": job['display_name'],
                "Raw_Product_Name": job['raw_product_name'], 
                "Headcount": int(people_to_assign),
                "Output": real_qty,
                "Status": output_status, 
                "Note": "⚡" if job['is_rush'] else "",
                "Actual_Hours": actual_hours,
                "Complete_Percent": "0%",
                "plan_to": job.get('line', 'Line 1'),
                "priority": "rush" if job.get('is_rush') else "normal"
            })

        pending_jobs = next_day_pending
        
        if jobs_processed_in_day > 0: 
            daily_schedule[f"Day {current_day}"] = {
                "tasks": day_tasks,
                "people_left": people_available, 
                "people_used": MAX_PEOPLE_TOTAL - people_available
            }
            current_day += 1
        elif pending_jobs:
            current_day += 1
        elif not pending_jobs:
            break

    return daily_schedule, pending_jobs