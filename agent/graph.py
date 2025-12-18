from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    fetch_inventory, 
    analyze_packing_sheet, 
    generate_pre_schedule_report, # 【新增】前置報告節點
    calculate_schedule,
    send_notification
)

def build_app():
    # 1. 初始化圖
    workflow = StateGraph(AgentState)
    
    # 2. 加入節點
    workflow.add_node("read_inventory", fetch_inventory)
    workflow.add_node("read_packing_list", analyze_packing_sheet)
    workflow.add_node("pre_schedule_report", generate_pre_schedule_report) # 【新增】報告節點
    workflow.add_node("scheduler", calculate_schedule)
    workflow.add_node("notify", send_notification)
    
    # 3. 定義路徑
    # 流程: 讀產能 -> 讀圖片(如果有的話) -> 【新報告】 -> 排程 -> 發信 -> 結束
    workflow.set_entry_point("read_inventory")
    workflow.add_edge("read_inventory", "read_packing_list")
    workflow.add_edge("read_packing_list", "pre_schedule_report") # 【修正】新增流程
    workflow.add_edge("pre_schedule_report", "scheduler") # 【修正】新增流程
    workflow.add_edge("scheduler", "notify")
    workflow.add_edge("notify", END)
    
    return workflow.compile()