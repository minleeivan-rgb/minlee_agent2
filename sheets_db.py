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
            print(f"❌ Google Sheets 連線失敗: {e}")
            raise

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
                ws.append_row(['order_id', 'priority', 'customer_name', 'product_name', 'quantity', 'pending', 'Order_Date', 'status'])
            elif name == SCHEDULE_WRITE_SHEET_NAME:
                headers = ['Day', 'order_id', 'Product', 'Raw_Product_Name', 'Headcount', 'Actual_Hours', 'plan_to', 'Output', 'Complete_Percent', 'Idle_People', 'Status', 'Note', 'priority']
                ws.append_row(headers)
            elif name == ORDERS_SHEET_NAME:
                ws.append_row(['order_id', 'product', 'qty', 'qty_remaining', 'is_rush', 'due_date', 'raw_packing_sheet', 'date_created'])
            elif name == RUSH_ORDERS_SHEET_NAME:
                ws.append_row(['order_id', 'product', 'qty', 'is_rush', 'qty_total', 'qty_remaining'])
            elif name == SYSTEM_DATA_SHEET_NAME:
                ws.append_row(['key', 'value'])
            elif name == 'percent':
                ws.append_row(['Day', 'order_id', 'Product', 'Raw_Product_Name', 'Planned_Output', 'Actual_Output', 'Total_Order_Qty', 'Actual_Complete_Percent', 'Report_Date'])
            return ws

    def _load_data(self, ws) -> List[Dict[str, Any]]:
        """通用數據載入函式。"""
        if not ws: return []
        try:
            if ws.row_count > 1:
                data = ws.get_all_records()
                for record in data:
                    for key in ['qty', 'qty_remaining', 'qty_total', 'quantity']:
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

    def load_orders(self) -> List[Dict[str, Any]]:
        return self._load_data(self.orders_ws)

    def load_rush_orders(self) -> List[Dict[str, Any]]:
        return self._load_data(self.rush_orders_ws)
    
    def load_system_data(self) -> Dict[str, Any]:
        """載入系統資料"""
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
        """儲存系統資料"""
        if not self.system_data_ws:
            return
        
        try:
            # 讀取現有資料
            all_data = self.system_data_ws.get_all_values()
            headers = all_data[0] if all_data else ['key', 'value']
            
            # 轉換為字典
            existing_data = {}
            for row in all_data[1:]:
                if len(row) >= 2:
                    existing_data[row[0]] = row[1]
            
            # 更新或新增
            value_str = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
            existing_data[key] = value_str
            
            # 寫回
            self.system_data_ws.clear()
            self.system_data_ws.append_row(headers)
            for k, v in existing_data.items():
                self.system_data_ws.append_row([k, v])
                
        except Exception as e:
            print(f"❌ 儲存系統資料失敗: {e}")

    def load_new_orders_from_sheet(self) -> List[Dict[str, Any]]:
        """從 read_packing_sheet 工作表讀取新訂單"""
        if not self.read_orders_ws:
            print("⚠️ 找不到訂單讀取工作表。")
            return []

        try:
            all_data = self.read_orders_ws.get_all_values()
            if len(all_data) <= 1:
                print("⚠️ read_packing_sheet 工作表為空或只有標頭。")
                return []

            headers = all_data[0]
            
            # 找到各欄位的索引
            try:
                col_order_id = headers.index('order_id')
                col_priority = headers.index('priority')
                col_customer = headers.index('customer_name')
                col_product = headers.index('product_name')
                col_quantity = headers.index('quantity')
                col_pending = headers.index('pending')
                col_order_date = headers.index('Order_Date')
                col_status = headers.index('status')
            except ValueError as e:
                print(f"❌ 找不到必要欄位: {e}")
                return []

            parsed_orders = []
            rows_to_update = []

            for row_idx, row in enumerate(all_data[1:], start=2):
                if len(row) < max(col_order_id, col_priority, col_customer, col_product, col_quantity, col_pending, col_order_date, col_status) + 1:
                    continue

                status = row[col_status].strip() if col_status < len(row) else ''
                if status == '已排程':
                    continue

                order_id = row[col_order_id].strip()
                priority = row[col_priority].strip().lower()
                customer_name = row[col_customer].strip()
                product_name = row[col_product].strip()
                quantity_str = row[col_quantity].strip()
                pending_str = row[col_pending].strip()
                order_date = row[col_order_date].strip()

                # 解析數量
                quantity_str = quantity_str.upper().replace('PCS', '').replace(',', '').strip()
                pending_str = pending_str.upper().replace('PCS', '').replace(',', '').strip()

                try:
                    qty_total = int(quantity_str) if quantity_str else 0
                    qty_pending = int(pending_str) if pending_str else qty_total
                except ValueError:
                    print(f"⚠️ 第 {row_idx} 行數量格式錯誤，跳過。")
                    continue

                if qty_pending <= 0:
                    continue

                is_rush = (priority == 'rush')

                raw_data_dict = {
                    "order_id": order_id,
                    "product_name": product_name,
                    "quantity": f"{qty_total} PCS",
                    "pending": f"{qty_pending} PCS",
                    "Order_Date": order_date
                }
                raw_data_json = json.dumps(raw_data_dict, ensure_ascii=False)

                parsed_orders.append({
                    "order_id": order_id,
                    "product": product_name,
                    "qty": qty_pending,
                    "qty_remaining": qty_pending,
                    "is_rush": is_rush,
                    "due_date": order_date,
                    "raw_data": raw_data_json
                })

                rows_to_update.append((row_idx, col_status))

            # 更新 status 欄位為 "已排程"
            if rows_to_update:
                cells_to_update = []
                for row_idx, col_idx in rows_to_update:
                    cell = self.read_orders_ws.cell(row_idx, col_idx + 1)
                    cell.value = '已排程'
                    cells_to_update.append(cell)
                
                self.read_orders_ws.update_cells(cells_to_update)
                print(f"✅ 已更新 {len(cells_to_update)} 筆訂單狀態為「已排程」。")

            print(f"✅ 成功讀取 {len(parsed_orders)} 筆新訂單。")
            return parsed_orders

        except Exception as e:
            print(f"❌ 讀取訂單失敗: {e}")
            return []

    def save_orders(self, orders: List[Dict[str, Any]], rush_orders: List[Dict[str, Any]]):
        """儲存訂單到 Orders 和 RushOrders 工作表"""
        if not self.orders_ws or not self.rush_orders_ws:
            print("⚠️ 無法儲存訂單，工作表不存在。")
            return

        try:
            # 清空並重新寫入 Orders
            self.orders_ws.clear()
            headers = ['order_id', 'product', 'qty', 'qty_remaining', 'is_rush', 'due_date', 'raw_packing_sheet', 'date_created']
            self.orders_ws.append_row(headers)
            
            if orders:
                rows = []
                for o in orders:
                    rows.append([
                        o.get('order_id', ''),
                        o['product'],
                        o['qty'],
                        o['qty_remaining'],
                        o.get('is_rush', False),
                        o.get('due_date', ''),
                        o.get('raw_packing_sheet', ''),
                        o.get('date_created', '')
                    ])
                self.orders_ws.append_rows(rows)
                print(f"✅ 成功儲存 {len(rows)} 筆訂單到 'Orders' 工作表。")

            # 清空並重新寫入 RushOrders
            self.rush_orders_ws.clear()
            headers = ['order_id', 'product', 'qty', 'is_rush', 'qty_total', 'qty_remaining']
            self.rush_orders_ws.append_row(headers)
            
            if rush_orders:
                rows = []
                for o in rush_orders:
                    rows.append([
                        o.get('order_id', ''),
                        o['product'],
                        o['qty'],
                        o.get('is_rush', True),
                        o.get('qty_total', o['qty']),
                        o.get('qty_remaining', o['qty'])
                    ])
                self.rush_orders_ws.append_rows(rows)
                print(f"✅ 成功儲存 {len(rows)} 筆急單到 'RushOrders' 工作表。")

        except Exception as e:
            print(f"❌ 儲存訂單失敗: {e}")

    def save_schedule_results(self, schedule_result: List[Dict[str, Any]]):
        """儲存排程結果到 percentage(daily_schedule) 工作表"""
        if not self.schedule_write_ws:
            print("⚠️ 無法儲存排程結果，工作表不存在。")
            return

        try:
            # 清空並重新寫入
            self.schedule_write_ws.clear()
            
            # percentage(daily_schedule) 保持 13 個欄位
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

            if records:
                self.schedule_write_ws.append_rows(records)
                print(f"✅ 成功寫入 {len(records)} 筆排程記錄到 '{SCHEDULE_WRITE_SHEET_NAME}'。")
            else:
                print("⚠️ 排程結果為空，未進行寫入。")

        except Exception as e:
            print(f"❌ 儲存排程結果失敗: {e}")

    def load_schedule_results(self) -> List[Dict[str, Any]]:
        """從 percentage(daily_schedule) 工作表讀取排程結果"""
        if not self.schedule_write_ws:
            print("⚠️ 找不到排程結果工作表。")
            return []
        
        try:
            data = self._load_data(self.schedule_write_ws)
            
            # 如果沒有 Raw_Product_Name 欄位，則從 Product 欄位提取
            for record in data:
                if not record.get('Raw_Product_Name'):
                    product_str = str(record.get('Product', ''))
                    raw_product = product_str.replace("✅ ", "").replace("☑️ ", "").replace("💡 ", "").strip()
                    record['Raw_Product_Name'] = raw_product
            
            print(f"✅ 成功從 '{SCHEDULE_WRITE_SHEET_NAME}' 讀取 {len(data)} 筆排程記錄。")
            return data
        except Exception as e:
            print(f"❌ 讀取排程結果失敗: {e}")
            return []

    def save_percent_data(self, actual_output_by_task: dict, days_to_report: int, schedule_data: list, current_orders: list, rush_orders: list):
        """將實際產量資料寫入 percent 工作表
        
        Args:
            actual_output_by_task: {工序名稱: {'actual': 實際產量, 'product': 產品名稱}}
            days_to_report: 要回報的天數
            schedule_data: 排程資料列表
            current_orders: 當前訂單列表
            rush_orders: 急單列表
        """
        if not self.percent_ws:
            print("⚠️ 找不到 percent 工作表。")
            return
        
        try:
            from datetime import datetime
            
            print(f"📝 準備將實際產量資料寫入 percent 工作表...")
            print(f"📊 待寫入的工序數量: {len(actual_output_by_task)}")
            
            # 【新增】清空工作表並重建標題（確保欄位位置正確）
            self.percent_ws.clear()
            self.percent_ws.append_row(['Day', 'order_id', 'Product', 'Raw_Product_Name', 'Planned_Output', 'Actual_Output', 'Total_Order_Qty', 'Actual_Complete_Percent', 'Report_Date'])
            
            # 準備寫入的資料
            records = []
            for task_name, data in actual_output_by_task.items():
                # 【修改】找出所有匹配的工序（可能在多天出現）
                matching_tasks = [
                    task for task in schedule_data 
                    if task.get('Product', '').replace("✅ ", "").replace("☑️ ", "").replace("💡 ", "").strip() == task_name
                    and task.get('Day')  # 確保有 Day 欄位
                ]
                
                if not matching_tasks:
                    print(f"⚠️ 找不到工序 {task_name} 的排程資料")
                    continue
                
                # 【修改】過濾出在報告天數範圍內的工序，並找出最大天數
                tasks_in_range = []
                max_day_num = 0
                for task in matching_tasks:
                    day_str = task.get('Day', 'Day 0')
                    try:
                        day_num = int(day_str.replace('Day ', ''))
                        if day_num <= days_to_report:
                            tasks_in_range.append(task)
                            max_day_num = max(max_day_num, day_num)
                    except:
                        continue
                
                if not tasks_in_range:
                    continue
                
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
                
                # 【修改】計算所有天數的總計劃產量
                total_planned_output = sum(task.get('Output', 0) for task in tasks_in_range)
                
                # 【修改】只記錄最後一天的數據，但計劃產量是所有天數的累計
                last_day_task = next((t for t in tasks_in_range if t.get('Day') == f'Day {max_day_num}'), tasks_in_range[0])
                
                records.append([
                    f'Day {max_day_num}',  # 記錄到最後一天
                    last_day_task.get('order_id', ''),
                    task_name,
                    product_name,
                    total_planned_output,  # 累計的計劃產量
                    actual_qty,  # 累計的實際產量
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