import gspread
import configparser
import json
from datetime import datetime
from typing import List, Dict, Any
from oauth2client.service_account import ServiceAccountCredentials
from collections import defaultdict

# 讀取設定檔
config = configparser.ConfigParser()
try:
    # 嘗試讀取多個路徑以確保兼容性
    read_files = config.read(['config.ini', 'agent/config.ini', '../config.ini'])
    if not read_files:
        raise FileNotFoundError
except:
    print("❌ 錯誤: 無法載入 config.ini，請檢查檔案路徑。")
    config.add_section('GOOGLE')
    config['GOOGLE']['SHEET_NAME'] = 'default_sheet'

# 設定 Sheets 名稱
SHEET_NAME = config['GOOGLE'].get('SHEET_NAME', '資料夾v1')
ORDERS_SHEET_NAME = 'Orders'
RUSH_ORDERS_SHEET_NAME = 'RushOrders'
SYSTEM_DATA_SHEET_NAME = 'SystemData'
READ_ORDERS_SHEET_NAME = config['GOOGLE'].get('READ_ORDERS_SHEET_NAME', 'read_packing_sheet')
SCHEDULE_WRITE_SHEET_NAME = config['GOOGLE'].get('SCHEDULE_WRITE_SHEET_NAME', 'percentage(daily_scheldue)')

class GoogleSheetsDB:
    """處理 Google Sheets 資料庫的讀取和寫入操作。"""
    def __init__(self):
        self.sheet = None
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                config['GOOGLE']['CREDENTIALS_JSON'], scope
            )
            client = gspread.authorize(creds)
            self.sheet = client.open(SHEET_NAME)
            
            # 初始化所有工作表物件
            self.orders_ws = self._get_worksheet(ORDERS_SHEET_NAME)
            self.rush_orders_ws = self._get_worksheet(RUSH_ORDERS_SHEET_NAME)
            self.system_data_ws = self._get_worksheet(SYSTEM_DATA_SHEET_NAME)
            self.read_orders_ws = self._get_worksheet(READ_ORDERS_SHEET_NAME)
            self.schedule_write_ws = self._get_worksheet(SCHEDULE_WRITE_SHEET_NAME)
            self.percent_ws = self._get_worksheet('percent')  # 【新增】實際產量追蹤表
            
            print(f"✅ Google Sheets DB 連線成功: '{SHEET_NAME}'")
            
        except Exception as e:
            print(f"❌ Google Sheets 連線或讀取錯誤: {e}")
            raise # 拋出錯誤，讓 main.py 捕捉並處理

    def _get_worksheet(self, name):
        """取得或建立工作表。"""
        if not self.sheet: return None
        try:
            return self.sheet.worksheet(name)
        except gspread.WorksheetNotFound:
            print(f"⚠️ 工作表 '{name}' 不存在，正在建立...")
            ws = self.sheet.add_worksheet(title=name, rows="100", cols="20")
            
            # 依據工作表名稱設定標頭
            if name == READ_ORDERS_SHEET_NAME:
                # 完整欄位: order_id, priority, customer_name, product_name, quantity, pending, Order_Date, status
                ws.append_row(['order_id', 'priority', 'customer_name', 'product_name', 'quantity', 'pending', 'Order_Date', 'status']) 
            elif name == SCHEDULE_WRITE_SHEET_NAME:
                # percentage(daily_schedule) 工作表標頭
                headers = ['Day', 'order_id', 'Product', 'Raw_Product_Name', 'Headcount', 'Actual_Hours', 'plan_to', 'Output', 'Complete_Percent', 'Idle_People', 'Status', 'Note', 'priority']
                ws.append_row(headers)
            elif name == ORDERS_SHEET_NAME:
                 ws.append_row(['order_id', 'product', 'qty', 'qty_remaining', 'is_rush', 'due_date', 'raw_packing_sheet', 'date_created'])  # 【修改】加入 order_id
            elif name == RUSH_ORDERS_SHEET_NAME:
                 ws.append_row(['order_id', 'product', 'qty', 'is_rush', 'qty_total', 'qty_remaining'])  # 【修改】加入 order_id
            elif name == SYSTEM_DATA_SHEET_NAME:
                 ws.append_row(['key', 'value'])
            elif name == 'percent':
                 # 【新增】實際產量追蹤表
                 ws.append_row(['Day', 'order_id', 'Product', 'Raw_Product_Name', 'Planned_Output', 'Actual_Output', 'Total_Order_Qty', 'Actual_Complete_Percent', 'Report_Date'])
            return ws

    def _load_data(self, ws) -> List[Dict[str, Any]]:
        """通用數據載入函式。"""
        if not ws: return []
        try:
            if ws.row_count > 1:
                data = ws.get_all_records()
                # 嘗試將數值型別的欄位轉換
                for record in data:
                    for key in ['qty', 'qty_remaining', 'qty_total', 'quantity']: # 新增 'quantity' 支援 read_packing_sheet
                        if key in record and record[key]:
                            try:
                                record[key] = int(str(record[key]).replace(',', '').strip())
                            except ValueError:
                                pass 
                return data
            return []
        except Exception as e:
            print(f"❌ 載入工作表 '{ws.title}' 數據錯誤: {e}")
            return []

    # --- 核心載入函式 ---
    def load_orders(self) -> List[Dict[str, Any]]:
        return self._load_data(self.orders_ws)

    def load_rush_orders(self) -> List[Dict[str, Any]]:
        return self._load_data(self.rush_orders_ws)
    
    def load_system_data(self) -> Dict[str, Any]:
        data = self._load_data(self.system_data_ws)
        result = {}
        for item in data:
            if 'key' in item and 'value' in item:
                try:
                    result[item['key']] = json.loads(item['value'])
                except json.JSONDecodeError:
                    result[item['key']] = item['value'] 
        return result

    def save_system_data(self, key: str, value: Any):
        """儲存系統資料到 SystemData 工作表（key-value 格式）"""
        if not self.system_data_ws:
            print("⚠️ SystemData 工作表不存在，無法儲存。")
            return
        
        try:
            # 1. 將 value 轉換為 JSON 字串（如果是 dict 或 list）
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, ensure_ascii=False)
            else:
                value_str = str(value)
            
            # 2. 讀取現有資料
            all_data = self.system_data_ws.get_all_values()
            
            # 3. 查找是否已有相同的 key
            key_row_index = None
            for idx, row in enumerate(all_data):
                if len(row) > 0 and row[0] == key:
                    key_row_index = idx + 1  # gspread 的行號從 1 開始
                    break
            
            # 4. 更新或新增
            if key_row_index:
                # 更新現有的 key
                self.system_data_ws.update_cell(key_row_index, 2, value_str)  # 第 2 欄是 value
                print(f"✅ 已更新 SystemData: {key}")
            else:
                # 新增新的 key-value
                self.system_data_ws.append_row([key, value_str])
                print(f"✅ 已新增 SystemData: {key}")
                
        except Exception as e:
            print(f"❌ 儲存 SystemData 錯誤: {e}")


    def load_new_orders_from_sheet(self) -> List[Dict[str, Any]]:
        """從 'read_packing_sheet' 讀取新的訂單數據。"""
        print(f"\n🔄 正在從 '{READ_ORDERS_SHEET_NAME}' 讀取新的訂單數據...")
        
        if not self.read_orders_ws:
            print("⚠️ 找不到讀取工作表，跳過訂單讀取。")
            return []
        
        # 1. 讀取所有資料（包含標頭）
        try:
            all_data = self.read_orders_ws.get_all_values()
            if len(all_data) <= 1:
                print("⚠️ 工作表為空或只有標頭，沒有訂單數據。")
                return []
        except Exception as e:
            print(f"❌ 讀取工作表失敗: {e}")
            return []
        
        # 2. 取得標頭並建立欄位索引
        headers = all_data[0]
        try:
            col_order_id = headers.index('order_id')  # 【新增】讀取 order_id
            col_product_name = headers.index('product_name')
            col_quantity = headers.index('quantity')
            col_pending = headers.index('pending')
            col_order_date = headers.index('Order_Date')
            col_priority = headers.index('priority')
            col_status = headers.index('status')
        except ValueError as e:
            print(f"❌ 找不到必要欄位: {e}")
            return []
        
        # 3. 解析每一行資料（從第 2 行開始，跳過標頭）
        parsed_orders = []
        rows_to_update = []  # 記錄需要更新 status 的行號
        
        for row_idx, row in enumerate(all_data[1:], start=2):  # Excel 的行號從 1 開始，標頭是第 1 行
            # 檢查 status 是否為空
            status_value = row[col_status].strip() if col_status < len(row) else ""
            
            if status_value:  # 如果 status 不是空的，跳過這一行
                continue
            
            try:
                # 讀取各欄位
                order_id = row[col_order_id].strip() if col_order_id < len(row) else ""  # 【新增】讀取 order_id
                product_name = row[col_product_name].strip().upper() if col_product_name < len(row) else ""
                quantity_str = row[col_quantity].strip() if col_quantity < len(row) else "0"
                pending_str = row[col_pending].strip() if col_pending < len(row) else "0"
                order_date = row[col_order_date].strip() if col_order_date < len(row) else datetime.now().strftime('%Y-%m-%d')
                priority = row[col_priority].strip().lower() if col_priority < len(row) else "normal"
                
                # 處理數值：移除 "PCS"、逗號等文字
                def parse_quantity(qty_str):
                    """將 "10000 PCS" 或 "10000PCS" 轉換為整數 10000"""
                    qty_str = qty_str.upper().replace('PCS', '').replace(',', '').strip()
                    try:
                        return int(qty_str)
                    except ValueError:
                        return 0
                
                qty_total = parse_quantity(quantity_str)
                qty_remaining = parse_quantity(pending_str)
                
                # 判斷是否為急單
                is_rush = (priority == "rush")
                
                # 驗證資料有效性
                if not product_name or qty_remaining <= 0:
                    continue
                
                # 加入解析結果
                parsed_orders.append({
                    "order_id": order_id,        # 【新增】訂單編號
                    "product": product_name,
                    "qty": qty_total,           # 總訂單量
                    "qty_total": qty_total,      # 總訂單量（用於進度條計算）
                    "qty_remaining": qty_remaining,  # 待排產數量（pending 欄位）
                    "due_date": order_date,
                    "is_rush": is_rush,
                    "raw_data": json.dumps({
                        "order_id": order_id,
                        "product_name": product_name,
                        "quantity": quantity_str,
                        "pending": pending_str,
                        "Order_Date": order_date,
                        "priority": priority
                    }, ensure_ascii=False)
                })
                
                # 記錄這一行需要更新 status
                rows_to_update.append(row_idx)
                
            except Exception as e:
                print(f"⚠️ 解析第 {row_idx} 行時發生錯誤: {e}")
                continue
        
        # 4. 更新已讀取行的 status 為 "已排程"
        if rows_to_update:
            try:
                # 準備批量更新的儲存格範圍
                cell_list = []
                for row_idx in rows_to_update:
                    # H 欄是 status（第 8 欄）
                    cell = self.read_orders_ws.cell(row_idx, col_status + 1)  # gspread 的欄位索引從 1 開始
                    cell.value = "已排程"
                    cell_list.append(cell)
                
                # 批量更新
                self.read_orders_ws.update_cells(cell_list)
                print(f"✅ 成功讀取 {len(parsed_orders)} 筆新訂單，並更新 status 為「已排程」。")
                
            except Exception as e:
                print(f"⚠️ 更新 status 時發生錯誤: {e}")
        else:
            print("ℹ️ 沒有找到 status 為空的新訂單。")
        
        return parsed_orders

    # --- 核心儲存函式 ---
    def save_orders(self, current_orders: List[Dict[str, Any]], rush_orders: List[Dict[str, Any]]):
        """將當前訂單與急單儲存到 Google Sheets"""
        if not self.sheet: return

        # 1. 儲存 Orders (常規訂單)
        if self.orders_ws:
            headers = ['order_id', 'product', 'qty', 'qty_remaining', 'is_rush', 'due_date', 'raw_packing_sheet', 'date_created']  # 【新增】order_id
            data_to_save = []
            for order in current_orders:
                 data_to_save.append([order.get(h) for h in headers])

            self.orders_ws.clear()
            self.orders_ws.append_row(headers)
            if data_to_save:
                self.orders_ws.append_rows(data_to_save)
            print(f"✅ 成功儲存 {len(current_orders)} 筆訂單到 '{ORDERS_SHEET_NAME}' 工作表。")

        # 2. 儲存 RushOrders (急單)
        if self.rush_orders_ws:
            headers = ['order_id', 'product', 'qty', 'is_rush', 'qty_total', 'qty_remaining']  # 【新增】order_id
            data_to_save = []
            for order in rush_orders:
                 data_to_save.append([order.get(h) for h in headers])

            self.rush_orders_ws.clear()
            self.rush_orders_ws.append_row(headers)
            if data_to_save:
                self.rush_orders_ws.append_rows(data_to_save)
            print(f"✅ 成功儲存 {len(rush_orders)} 筆急單到 '{RUSH_ORDERS_SHEET_NAME}' 工作表。")

    def save_schedule_results(self, schedule_result: list):
        """將排程結果寫入使用者指定的寫入工作表。"""
        if not schedule_result or not self.schedule_write_ws: return
            
        print(f"\n💾 正在將排程結果寫入 '{SCHEDULE_WRITE_SHEET_NAME}'...")
        
        # 1. 清空舊數據
        self.schedule_write_ws.clear()
        
        # 2. 準備數據 (確保順序和欄位一致)
        # 【修改】保持原有欄位，不再加入 Actual_Output、Total_Order_Qty、Actual_Complete_Percent
        headers = ['Day', 'order_id', 'Product', 'Raw_Product_Name', 'Headcount', 'Actual_Hours', 'plan_to', 'Output', 'Complete_Percent', 'Idle_People', 'Status', 'Note', 'priority']
        self.schedule_write_ws.append_row(headers)
        
        records = []
        for task in schedule_result:
            records.append([
                task.get('Day', ''),
                task.get('order_id', ''),
                task.get('Product', ''),
                task.get('Raw_Product_Name', ''),
                task.get('Headcount', ''),
                task.get('Actual_Hours', ''),
                task.get('plan_to', ''),       
                task.get('Output', ''),
                task.get('Complete_Percent', ''),
                task.get('Idle_People', ''),    
                task.get('Status', ''),
                task.get('Note', ''),
                task.get('priority', ''),
            ])

        # 3. 批量寫入
        if records:
            self.schedule_write_ws.append_rows(records)
            print(f"✅ 成功寫入 {len(records)} 筆排程記錄到 '{SCHEDULE_WRITE_SHEET_NAME}'。")
        else:
            print("⚠️ 排程結果為空，未進行寫入。")

    def load_schedule_results(self) -> List[Dict[str, Any]]:
        """從 percentage(daily_schedule) 工作表讀取排程結果"""
        if not self.schedule_write_ws:
            print("⚠️ 找不到排程結果工作表。")
            return []
        
        try:
            data = self._load_data(self.schedule_write_ws)
            
            # 【修改】如果沒有 Raw_Product_Name 欄位，則從 Product 欄位提取
            for record in data:
                if not record.get('Raw_Product_Name'):
                    product_str = str(record.get('Product', ''))
                    # 移除 ✅ ☑️ 💡 等符號
                    raw_product = product_str.replace("✅ ", "").replace("☑️ ", "").replace("💡 ", "").strip()
                    record['Raw_Product_Name'] = raw_product
            
            print(f"✅ 成功從 '{SCHEDULE_WRITE_SHEET_NAME}' 讀取 {len(data)} 筆排程記錄。")
            return data
        except Exception as e:
            print(f"❌ 讀取排程結果失敗: {e}")
            return []
    
    def update_actual_outputs(self, actual_output_by_task: dict, days_to_report: int, schedule_data: list, current_orders: list, rush_orders: list):
        """將實際產量資料寫入 percent 工作表"""
        if not self.percent_ws:
            print("⚠️ 找不到 percent 工作表。")
            return
        
        try:
            from datetime import datetime
            
            print(f"📝 準備將實際產量資料寫入 percent 工作表...")
            print(f"📊 待寫入的工序數量: {len(actual_output_by_task)}")
            
            # 準備寫入的資料
            records = []
            for task_name, data in actual_output_by_task.items():
                # 從 schedule_data 中找出對應的工序資料
                matching_tasks = [
                    task for task in schedule_data 
                    if task.get('Product', '').replace("✅ ", "").replace("☑️ ", "").replace("💡 ", "").strip() == task_name
                ]
                
                if not matching_tasks:
                    continue
                
                task_info = matching_tasks[0]
                actual_qty = data['actual']
                product_name = data['product']
                
                # 從 current_orders 或 rush_orders 中取得總訂單量
                order = next((o for o in current_orders if o.get('product') == product_name), None)
                if not order:
                    order = next((o for o in rush_orders if o.get('product') == product_name), None)
                
                total_order_qty = order.get('qty', 0) if order else 0
                
                # 計算完成百分比
                try:
                    if total_order_qty > 0:
                        percent = round((actual_qty / total_order_qty) * 100, 1)
                    else:
                        percent = 0
                except (ValueError, TypeError):
                    percent = 0
                
                # 準備記錄
                records.append([
                    task_info.get('Day', ''),
                    task_info.get('order_id', ''),
                    task_name,
                    product_name,
                    task_info.get('Output', ''),
                    actual_qty,
                    total_order_qty,
                    f"{percent}%",
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ])
            
            # 批量寫入
            if records:
                self.percent_ws.append_rows(records)
                print(f"✅ 成功寫入 {len(records)} 筆實際產量記錄到 percent 工作表。")
            else:
                print("⚠️ 沒有需要寫入的資料。")
                
        except Exception as e:
            print(f"❌ 寫入實際產量失敗: {e}")
            import traceback
            traceback.print_exc()