# 生產參數設定檔
# 程式會讀取這裡的 INVENTORY_DATA
# 格式: "唯一識別碼": {"uph": 產能, "headcount": 人力, "line": "Line 1" 或 "Line 2" 或 "Line 3"}

INVENTORY_DATA = {
    # ================= Line 1 (一線 - 優先生產) =================
    "G400一線": {"uph": 800, "headcount": 8, "line": "Line 1"},
    "T304一線": {"uph": 850, "headcount": 4, "line": "Line 1"},
    "T305一線": {"uph": 850, "headcount": 4, "line": "Line 1"},
    "HT325一線": {"uph": 1000, "headcount": 6, "line": "Line 1"},
    "HT325一線踩塑膠把手一線": {"uph": 1000, "headcount": 5, "line": "Line 1"},
    "HT325一線放鎖舌鎖仁一線": {"uph": 900, "headcount": 3, "line": "Line 1"},
    "HT505一線": {"uph": 1000, "headcount": 6, "line": "Line 1"},
    "HT505踩塑膠把手一線": {"uph": 1000, "headcount": 5, "line": "Line 1"},
    "HT505放鎖舌鎖仁一線": {"uph": 900, "headcount": 3, "line": "Line 1"},
    "L100/L101/L102一線": {"uph": 950, "headcount": 6, "line": "Line 1"},
    
    # 這裡拆分 L201 的數據
    "L201一線": {"uph": 800, "headcount": 5, "line": "Line 1"},
    
    "L203": {"uph": 1000, "headcount": 7, "line": "Line 1"}, # 未標示線別，預設一線
    "L205P一線_A": {"uph": 450, "headcount": 5, "line": "Line 1"}, 
    "L205P一線_B": {"uph": 850, "headcount": 8, "line": "Line 1"},
    
    "L502一線": {"uph": 900, "headcount": 6, "line": "Line 1"},
    
    # L503 系列
    "L503/L503E/L503GB 一線": {"uph": 450, "headcount": 17, "line": "Line 1"},

    "L604一線": {"uph": 900, "headcount": 6, "line": "Line 1"},
    
    "L8001s 一線": {"uph": 500, "headcount": 5, "line": "Line 1"},
    "T302一線": {"uph": 400, "headcount": 6, "line": "Line 1"},
    "T309一線": {"uph": 800, "headcount": 6, "line": "Line 1"},
    "T323一線": {"uph": 900, "headcount": 7, "line": "Line 1"},
    "T500一線": {"uph": 900, "headcount": 7, "line": "Line 1"},
    "TW300/TW500一線": {"uph": 900, "headcount": 6, "line": "Line 1"},
    "TW501一線": {"uph": 900, "headcount": 5, "line": "Line 1"},
    
    "BP12一線": {"uph": 550, "headcount": 6, "line": "Line 1"},
    "BP15一線": {"uph": 350, "headcount": 4, "line": "Line 1"},
    "BP15RV一線": {"uph": 350, "headcount": 4, "line": "Line 1"},
    
    "BP27-2短一線": {"uph": 300, "headcount": 3, "line": "Line 1"},
    "小折疊一線": {"uph": 400, "headcount": 2, "line": "Line 1"},
    "SLH一線": {"uph": 800, "headcount": 6, "line": "Line 1"},

    # ================= Line 3 (三線 - 優先生產) =================
    "L200 3線": {"uph": 900, "headcount": 6, "line": "Line 3"},
    "L205P 三線 挑": {"uph": 1000, "headcount": 6, "line": "Line 3"},
    "TW501三線": {"uph": 900, "headcount": 13, "line": "Line 3"},
    "BP12三線": {"uph": 600, "headcount": 6, "line": "Line 3"},
    "LCI SLAM LATCH三線": {"uph": 650, "headcount": 8, "line": "Line 3"},
    "BP26 & BP26D三線": {"uph": 500, "headcount": 6, "line": "Line 3"},
    "SLH三線": {"uph": 500, "headcount": 11, "line": "Line 3"},

    # ================= Line 2 (二線 - 最後生產/組裝) =================
    "G400二線": {"uph": 800, "headcount": 11, "line": "Line 2"},
    "T304二線": {"uph": 800, "headcount": 8, "line": "Line 2"},
    "T305二線": {"uph": 800, "headcount": 9, "line": "Line 2"},
    "HT325一線組裝二線": {"uph": 900, "headcount": 9, "line": "Line 2"},
    "HT505組裝二線": {"uph": 900, "headcount": 13, "line": "Line 2"},
    "L100/L101/L102二線": {"uph": 900, "headcount": 13, "line": "Line 2"},
    "L201二線": {"uph": 900, "headcount": 10, "line": "Line 2"},
    "L502二線": {"uph": 900, "headcount": 11, "line": "Line 2"},
    
    "L604 分1、2號": {"uph": 1333, "headcount": 6, "line": "Line 2"}, 
    "L604二線 (原一線11人)": {"uph": 900, "headcount": 11, "line": "Line 2"},
    
    "T309二線": {"uph": 700, "headcount": 11, "line": "Line 2"},
    "T323二線": {"uph": 900, "headcount": 14, "line": "Line 2"},
    "T500二線": {"uph": 1000, "headcount": 11, "line": "Line 2"},
    
    "E-LATCH 60137二線": {"uph": 900, "headcount": 8, "line": "Line 2"},
    "E-LATCH 踩把手": {"uph": 1000, "headcount": 1, "line": "Line 2"},
    "E-LATCH 二線": {"uph": 900, "headcount": 14, "line": "Line 2"},
    
    "MSB二線通孔": {"uph": 600, "headcount": 1, "line": "Line 2"},
    "MSB二線": {"uph": 500, "headcount": 12, "line": "Line 2"},
    
    "BP8電池蓋": {"uph": 900, "headcount": 11, "line": "Line 2"},
    
   
    "BP8二線_A": {"uph": 600, "headcount": 6, "line": "Line 2"},
    "BP8二線_B": {"uph": 550, "headcount": 6, "line": "Line 2"},
    
    
   
    "BP12電池蓋": {"uph": 900, "headcount": 11, "line": "Line 2"},
    
    "BP15二線": {"uph": 500, "headcount": 13, "line": "Line 2"},
    "BP15RV二線": {"uph": 500, "headcount": 14, "line": "Line 2"},
    
    "LCI SLAM LATCH二線": {"uph": 600, "headcount": 13, "line": "Line 2"},
    "BP26 & BP26D二線": {"uph": 400, "headcount": 13, "line": "Line 2"},
    "BP27-2短二線": {"uph": 450, "headcount": 14, "line": "Line 2"},
    "BP27-4長二線": {"uph": 450, "headcount": 14, "line": "Line 2"},
    "SC二線": {"uph": 250, "headcount": 13, "line": "Line 2"},
    "大折疊 二線": {"uph": 400, "headcount": 8, "line": "Line 2"},
    "小折疊二線": {"uph": 400, "headcount": 13, "line": "Line 2"},
    "SLH二線": {"uph": 450, "headcount": 15, "line": "Line 2"},

    # ================= 其他 / 通用 (歸類為一線或獨立) =================
    "BP22": {"uph": 400, "headcount": 22, "line": "Line 1"},
    "LCI SLAM LATCH 檢查裝": {"uph": 1600, "headcount": 4, "line": "Line 1"},
    "BP27 另件包": {"uph": 900, "headcount": 5, "line": "Line 1"},
    "大折疊 前置作業": {"uph": 400, "headcount": 2, "line": "Line 1"},
    "SCI CAM LOCK BARB": {"uph": 1100, "headcount": 10, "line": "Line 1"},
    "TWIST CAM迴轉鎖": {"uph": 325, "headcount": 13, "line": "Line 1"},
    "BP8裝": {"uph": 200, "headcount": 1, "line": "Line 2"},
    "BP8牛角點紅漆": {"uph": 200, "headcount": 1, "line": "Line 2"},
    "BP12牛角點紅漆": {"uph": 200, "headcount": 1, "line": "Line 2"},
    "BP12裝": {"uph": 200, "headcount": 1, "line": "Line 2"},
    "L503/L503E/L503GB 檢查面蓋": {"uph": 1000, "headcount": 1, "line": "Line 1"},
    "L503/L503E/L503GB 蓋日期": {"uph": 700, "headcount": 1, "line": "Line 1"},
    "HT505洗塑膠一線": {"uph": 3000, "headcount": 1, "line": "Line 1"},
    "HT325一線洗塑膠一線": {"uph": 3000, "headcount": 1, "line": "Line 1"}

}