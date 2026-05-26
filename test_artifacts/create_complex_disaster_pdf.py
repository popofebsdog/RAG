from __future__ import annotations

from pathlib import Path
import textwrap

import fitz


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "complex_disaster_rag_test.pdf"
FONT = Path("/Library/Fonts/Arial Unicode.ttf")
if not FONT.exists():
    FONT = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")


def new_page(doc: fitz.Document) -> fitz.Page:
    page = doc.new_page(width=595, height=842)
    page.insert_font(fontname="ArialUnicode", fontfile=str(FONT))
    return page


def draw_wrapped_text(
    page: fitz.Page,
    text: str,
    x: float,
    y: float,
    width_chars: int = 44,
    fontsize: int = 10,
    line_gap: float = 14,
    color: tuple[float, float, float] = (0.10, 0.12, 0.16),
) -> float:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            y += line_gap * 0.5
            continue
        for wrapped in textwrap.wrap(line, width=width_chars, break_long_words=False):
            page.insert_text(
                (x, y),
                wrapped,
                fontsize=fontsize,
                fontname="ArialUnicode",
                color=color,
            )
            y += line_gap
    return y


def heading(page: fitz.Page, text: str, y: float, size: int = 18) -> float:
    page.insert_text((42, y), text, fontsize=size, fontname="ArialUnicode", color=(0.05, 0.14, 0.26))
    return y + size + 12


def subheading(page: fitz.Page, text: str, y: float) -> float:
    page.draw_rect(fitz.Rect(38, y - 13, 554, y + 6), color=(0.76, 0.83, 0.91), fill=(0.91, 0.95, 0.98))
    page.insert_text((42, y), text, fontsize=12, fontname="ArialUnicode", color=(0.08, 0.18, 0.32))
    return y + 22


def draw_table(page: fitz.Page, rows: list[list[str]], x: float, y: float, widths: list[float]) -> float:
    row_h = 24
    for r, row in enumerate(rows):
        fill = (0.94, 0.97, 1.0) if r == 0 else (1, 1, 1)
        yy = y + r * row_h
        xx = x
        for c, value in enumerate(row):
            rect = fitz.Rect(xx, yy, xx + widths[c], yy + row_h)
            page.draw_rect(rect, color=(0.68, 0.74, 0.82), fill=fill)
            page.insert_text(
                (xx + 4, yy + 16),
                value,
                fontsize=8.5,
                fontname="ArialUnicode",
                color=(0.12, 0.15, 0.20),
            )
            xx += widths[c]
    return y + len(rows) * row_h + 18


def add_page_number(page: fitz.Page, n: int) -> None:
    page.insert_text((520, 812), f"p.{n}", fontsize=9, fontname="ArialUnicode", color=(0.40, 0.44, 0.50))


def build_pdf() -> None:
    doc = fitz.open()

    page = new_page(doc)
    y = heading(page, "台灣山坡地崩塌複合災害調查報告 RAG 測試版", 54, 19)
    y = draw_wrapped_text(
        page,
        "本文件為系統測試用 PDF，內容刻意包含多災種、跨段因果鏈、矛盾數值、時間序列、表格資料與人工節點可引用句。"
        "目標是測試 agentic chunking、MoR 災害路由、手動 node 入庫、relation 權重、向量檢索與異常偵測是否能同時運作。",
        42,
        y,
        width_chars=42,
        fontsize=10,
    )
    y = subheading(page, "一、摘要與事件背景", y + 14)
    y = draw_wrapped_text(
        page,
        """2025 年 8 月 14 日至 8 月 16 日，測試流域 A 受連續豪雨與上游堰塞湖短時洩降影響，坡面含水量快速升高。
第一階段以邊坡淺層滑動為主，第二階段則出現土石流堵塞排水箱涵，造成局部淹水。
調查隊初判：雨量是崩塌最直接觸發因子，地層破碎帶與道路開挖則提供了失穩前提。
本案不是單一災害，而是「降雨 -> 邊坡崩塌 -> 河道阻塞 -> 淹水回水 -> 二次沖刷」的複合災害鏈。""",
        42,
        y,
    )
    y = subheading(page, "二、重要觀察句與可建立的關係", y + 10)
    y = draw_wrapped_text(
        page,
        """觀察 1：累積雨量超過 420 mm 後，坡腳地下水位在 3 小時內上升 1.8 m。
觀察 2：坡腳地下水位上升導致有效應力下降，進而降低剪力強度。
觀察 3：道路排水溝於 K2+350 處堵塞，使地表逕流集中到既有裂縫。
觀察 4：既有裂縫擴張後，右岸滑動面從 2.1 m 深處發展至 4.7 m 深處。
建議人工 relation：累積雨量 -> 地下水位上升，地下水位上升 -> 剪力強度下降，排水堵塞 -> 逕流集中，逕流集中 -> 裂縫擴張，裂縫擴張 -> 深層滑動。""",
        42,
        y,
    )
    add_page_number(page, 1)

    page = new_page(doc)
    y = heading(page, "三、監測資料與矛盾紀錄", 54)
    y = draw_wrapped_text(
        page,
        "下表混合了雨量、位移、孔隙水壓與道路巡查資料。系統應能將各列視為可檢索證據，而不是只把表格切碎成失去語意的片段。",
        42,
        y,
        width_chars=44,
    )
    rows = [
        ["時間", "24h雨量", "累積雨量", "位移速率", "備註"],
        ["08/14 08:00", "88 mm", "126 mm", "1.2 mm/hr", "裂縫未擴大"],
        ["08/14 20:00", "162 mm", "318 mm", "4.8 mm/hr", "坡腳滲水"],
        ["08/15 08:00", "214 mm", "462 mm", "18.6 mm/hr", "排水溝堵塞"],
        ["08/15 14:00", "37 mm", "701 mm", "3.1 mm/hr", "數值疑似異常"],
        ["08/16 08:00", "96 mm", "558 mm", "22.4 mm/hr", "右岸滑動"],
    ]
    y = draw_table(page, rows, 42, y + 6, [88, 82, 90, 92, 154])
    y = subheading(page, "四、異常資料說明", y)
    y = draw_wrapped_text(
        page,
        """資料表中 08/15 14:00 的累積雨量記錄為 701 mm，但相鄰雨量站 R-03 同時段為 486 mm，雷達估計亦僅為 492 mm。
若以 08/16 08:00 的累積雨量 558 mm 回推，701 mm 明顯不符合時間序列遞增與空間一致性。
因此 701 mm 應被標記為高風險異常值，可能原因包括人工輸入錯誤、雨量筒阻塞後瞬間傾倒、或資料匯入時欄位錯置。
然而，位移速率在 08/16 仍達 22.4 mm/hr，不能因雨量異常而否定崩塌風險。""",
        42,
        y,
    )
    y = subheading(page, "五、矛盾文字與驗證需求", y + 8)
    y = draw_wrapped_text(
        page,
        """巡查紀錄 A 表示：K2+350 排水溝在 08/15 08:00 已完全堵塞。
承包商日誌 B 表示：同一位置排水溝在 08/15 09:30 仍可排水，且未見土砂堆積。
空拍照片 C 顯示：08/15 10:10 下游箱涵入口已有漂流木與土砂堆積。
這三段資料需要 evidence evaluator 判斷時間、位置與觀察角度，不能直接合併成單一事實。""",
        42,
        y,
    )
    add_page_number(page, 2)

    page = new_page(doc)
    y = heading(page, "六、多災種分類與 MoR 檢索提示", 54)
    y = draw_wrapped_text(
        page,
        """地震類：本案前 14 天內無規模 5 以上地震，微震活動不足以單獨解釋滑動。
洪水類：河道阻塞後，左岸低窪聚落水位於 2 小時內上升 0.65 m，屬於回水淹水而非外水漫溢。
崩塌類：降雨、地下水位、裂縫與位移速率形成清楚因果鏈，應為主要檢索領域。
海嘯類：無海嘯、潮位或近岸波浪證據，若 query 提到 tsunami 應低權重路由。
土石流類：坡面崩塌物進入支流後形成短延時高濃度流，與箱涵堵塞有直接關係。""",
        42,
        y,
    )
    y = subheading(page, "七、建議測試 Query", y + 12)
    y = draw_wrapped_text(
        page,
        """Q1：造成右岸深層滑動的主要因果鏈是什麼？
Q2：08/15 14:00 的累積雨量是否異常，應如何解釋？
Q3：排水溝堵塞與下游淹水之間有什麼關係？
Q4：本案應該路由到 earthquake、flood、landslide、tsunami 哪些資料庫？
Q5：巡查紀錄與承包商日誌是否互相矛盾？需要哪些 evidence 驗證？""",
        42,
        y,
    )
    y = subheading(page, "八、人工 Node 建議", y + 12)
    y = draw_wrapped_text(
        page,
        """node-a：累積雨量超過門檻後，坡腳地下水位上升並造成有效應力下降。
node-b：排水溝堵塞使地表逕流集中到既有裂縫。
node-c：裂縫擴張導致滑動面從淺層發展至深層。
node-d：701 mm 累積雨量與鄰近測站及後續時間序列不一致，應標記為異常。
node-e：河道阻塞引發回水淹水，但不是外水漫溢。""",
        42,
        y,
    )
    add_page_number(page, 3)

    doc.set_metadata(
        {
            "title": "Complex Disaster RAG Test PDF",
            "author": "Codex",
            "subject": "RAG chunking, MoR, graph relation and anomaly validation",
            "keywords": "RAG, landslide, flood, anomaly, MoR",
        }
    )
    doc.save(OUTPUT)
    doc.close()
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
