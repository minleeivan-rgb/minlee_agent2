from typing import TypedDict, List, Dict, Any, Annotated
import operator
from datetime import datetime

class AgentState(TypedDict):
    """
    定義系統狀態 (State)
    包含排程、回饋迴圈與急單管理
    """
    # --- 基礎資訊 ---\n
    logs: Annotated[List[str], operator.add]
    image_path: str
    
    # --- 核心數據 ---\n
    # inventory_db: 產能資料庫 (UPH, 人力需求)\n
    inventory_db: Dict[str, Dict[str, int]]
    
    # orders: 目前的訂單佇列 (包含新單 + 未完成舊單)
    orders: List[Dict[str, Any]] 
    
    # rush_orders: 急單佇列 (優先權最高)
    rush_orders: List[Dict[str, Any]]
    
    # 【新增】工單清單 (從 orders 拆分出來的所有工序)
    all_jobs: List[Dict[str, Any]]
    
    # 【新增】產品到工序的映射表
    product_to_jobs: Dict[str, List[str]]
    
    # --- 每日回饋 (Feedback Loop) ---\n
    # daily_feedback: 紀錄每天的實際產出，用於修正剩餘數量\n
    # 格式: {"Day 1": {"T302": 5000}}
    daily_feedback: Dict[str, Dict[str, int]]
    
    # 【新增】上次排程完成的日期，用於計算當前是第幾天，以便進行追蹤
    last_schedule_date: str
    
    # 【新增】上次排程的結果，用於對比「應做」與「實作」
    last_schedule_results: List[Dict[str, Any]]

    # --- 輸出結果 ---\n
    # schedule_result: 排程結果 List
    schedule_result: List[Dict[str, Any]]
    
    # schedule_summary: 文字...
    schedule_summary: str
    
    # email_subject: 郵件標題
    email_subject: str
    
    # email_body: 郵件內文
    email_body: str