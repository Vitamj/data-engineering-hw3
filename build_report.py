from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageBreak,
                               PageTemplate, Paragraph, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "results" / "evidence.json").read_text(encoding="utf-8"))
OUT = ROOT / "report" / "report.pdf"

pdfmetrics.registerFont(TTFont("ArialUnicode", "/Library/Fonts/Arial Unicode.ttf"))
pdfmetrics.registerFont(TTFont("Georgia", "/System/Library/Fonts/Supplemental/Georgia.ttf"))
pdfmetrics.registerFont(TTFont("Georgia-Bold", "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"))
INK = colors.HexColor("#493842")
PLUM = colors.HexColor("#704D62")
ROSE = colors.HexColor("#B77487")
PAPER = colors.HexColor("#FFFCFA")
BLUSH = colors.HexColor("#F5E8EC")
LILAC = colors.HexColor("#EEEAF4")
SAGE = colors.HexColor("#E8EFE8")
GRID = colors.HexColor("#E4D4DA")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleRu", fontName="Georgia", fontSize=21, leading=27,
                          textColor=PLUM, spaceAfter=7))
styles.add(ParagraphStyle(name="HeadingRu", fontName="Georgia-Bold", fontSize=12.5, leading=16,
                          textColor=ROSE, spaceBefore=14, spaceAfter=7))
styles.add(ParagraphStyle(name="BodyRu", fontName="ArialUnicode", fontSize=8.9, leading=13,
                          textColor=INK, spaceAfter=7))
styles.add(ParagraphStyle(name="SmallRu", fontName="ArialUnicode", fontSize=7.7, leading=10.8,
                          textColor=PLUM, spaceAfter=5))
styles.add(ParagraphStyle(name="CellRu", fontName="ArialUnicode", fontSize=7.4, leading=10,
                          textColor=INK))
styles.add(ParagraphStyle(name="CoverKicker", fontName="Georgia-Bold", fontSize=12, leading=17,
                          alignment=TA_CENTER, textColor=ROSE, spaceAfter=9))
styles.add(ParagraphStyle(name="CoverTitle", fontName="Georgia", fontSize=28, leading=35,
                          alignment=TA_CENTER, textColor=PLUM, spaceAfter=9))
styles.add(ParagraphStyle(name="CoverSub", fontName="ArialUnicode", fontSize=11, leading=16,
                          alignment=TA_CENTER, textColor=INK))
styles.add(ParagraphStyle(name="CoverName", fontName="Georgia", fontSize=17, leading=23,
                          alignment=TA_CENTER, textColor=PLUM))
styles.add(ParagraphStyle(name="CoverMeta", fontName="ArialUnicode", fontSize=10, leading=15,
                          alignment=TA_CENTER, textColor=INK))
styles.add(ParagraphStyle(name="CoverLabel", fontName="Georgia-Bold", fontSize=9.5, leading=13,
                          alignment=TA_CENTER, textColor=ROSE))


def para(value, style="BodyRu"):
    return Paragraph(str(value), styles[style])


def table(headers, rows, widths):
    cells = [[para(h, "CellRu") for h in headers]]
    cells += [[para("—" if value is None else value, "CellRu") for value in row] for row in rows]
    item = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    item.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUSH),
        ("TEXTCOLOR", (0, 0), (-1, 0), PLUM),
        ("FONTNAME", (0, 0), (-1, 0), "Georgia-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, LILAC]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("BOX", (0, 0), (-1, -1), 0.7, GRID),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]))
    return item


def page_art(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setFillColor(BLUSH)
    canvas.rect(0, A4[1] - 4 * mm, A4[0], 4 * mm, fill=1, stroke=0)
    canvas.setFillColor(ROSE)
    canvas.roundRect(18 * mm, A4[1] - 4 * mm, 28 * mm, 4 * mm, 2 * mm, fill=1, stroke=0)
    if doc.page == 1:
        canvas.setFillColor(LILAC)
        canvas.circle(A4[0] - 25 * mm, A4[1] - 31 * mm, 16 * mm, fill=1, stroke=0)
        canvas.setFillColor(BLUSH)
        canvas.circle(A4[0] - 40 * mm, A4[1] - 38 * mm, 11 * mm, fill=1, stroke=0)
        canvas.setFillColor(SAGE)
        canvas.circle(A4[0] - 15 * mm, A4[1] - 48 * mm, 8 * mm, fill=1, stroke=0)
    canvas.restoreState()


def fmt(n):
    return f"{n:,.0f}".replace(",", " ")


def salary_rows(size, positive):
    records = [r for r in DATA["salary"][str(size)] if r["n"] >= 2]
    records.sort(key=lambda r: r["delta_rub"], reverse=positive)
    selected = [r for r in records if (r["delta_rub"] > 0 if positive else r["delta_rub"] < 0)][:3]
    return [[" + ".join(r["skills"]), str(r["n"]), r["anchor"],
             fmt(r["anchor_median_rub"]), fmt(r["median_rub"]),
             ("+" if r["delta_rub"] > 0 else "") + fmt(r["delta_rub"])] for r in selected]


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=18 * mm, bottomMargin=15 * mm)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates(PageTemplate(id="report", frames=[frame], onPage=page_art))
    story = []
    story.append(Spacer(1, 43 * mm))
    story.append(para("ИНЖЕНЕРИЯ ДАННЫХ", "CoverKicker"))
    story.append(Spacer(1, 5 * mm))
    story.append(para("Анализ IT-вакансий:<br/>Go-разработчик", "CoverTitle"))
    story.append(para("Домашнее задание 3 · вариант 7", "CoverSub"))
    story.append(Spacer(1, 35 * mm))
    story.append(para("Выполнила", "CoverLabel"))
    story.append(Spacer(1, 2 * mm))
    story.append(para("Вита-Виктория Гиалтсо-Мижа", "CoverName"))
    story.append(Spacer(1, 3 * mm))
    story.append(para("Группа j3313<br/>ИСУ 466703", "CoverMeta"))
    story.append(PageBreak())
    story.append(para("Анализ IT-вакансий: Go-разработчик", "TitleRu"))
    run_date = datetime.now().strftime("%d.%m.%Y")
    story.append(para(f"Инженерия данных, домашнее задание 3. Индивидуальный вариант 7: «Программист, разработчик на Go». Фактический запуск {run_date}.", "BodyRu"))
    story.append(para("Источник и границы данных", "HeadingRu"))
    story.append(para("Исходный архив <b>hh.zip</b> из учебного чата содержит 10 000 JSON-файлов вакансий. SHA-256: <font size='7'>%s</font>. В каждом объекте есть название, регион, список ключевых навыков и необязательная зарплата. Скрипт prepare.py преобразовал данные в JSONL без изменения смысла полей." % "c45f6ad4ad3c6ec65f3a823e33bd04da1c7f2d264a1f22d14b4206730a3381b3"))
    story.append(para("Вариант отбирается по отдельному слову <b>Go</b> или <b>Golang</b> в названии вакансии. Это явное условие записано отдельно в Python-мэппере и в SQL DuckDB. Отобрано <b>%s</b> вакансии, у <b>%s</b> есть навыки, лишь у <b>%s</b> указана зарплата в рублях." % (DATA["mapreduce_meta"]["vacancies"], DATA["mapreduce_meta"]["with_skills"], DATA["mapreduce_meta"]["rub_salary"])))
    story.append(para("Хранилище и доказательство загрузки", "HeadingRu"))
    inp=DATA["input"]
    story.append(table(["Объект RustFS", "Размер", "PUT", "HEAD", "ETag совпал"],
                       [["s3://hh-lake/raw/vacancies.jsonl", fmt(inp["local_bytes"])+" байт", str(inp["upload"]["status"]), str(inp["head"]["status"]), "да" if inp["upload"]["etag"]==inp["head"]["etag"] else "нет"]],
                       [70*mm,33*mm,16*mm,18*mm,37*mm]))
    story.append(Spacer(1,5*mm))
    story.append(para("Результаты собственной MapReduce записаны обратно в hh-lake/results/go/skills_1.json, skills_2.json и skills_3.json; для каждого выполнен HEAD 200 после PUT 200. Код и полный машинный вывод находятся в results/evidence.json.", "SmallRu"))
    story.append(para("Методы и сверка", "HeadingRu"))
    story.append(para("MapReduce читает S3-поток чанками по 1 МиБ, собирает полные строки JSONL на границах чанков и передает их двум процессам-мэпперам. Мэппер нормализует навыки (trim, lower, удаление дубликатов), строит сочетания C(k,1), C(k,2), C(k,3); reducer суммирует Counter. DuckDB через httpfs читает <b>тот же S3-объект</b>, самостоятельно фильтрует названия и считает сочетания тремя SQL-запросами с UNNEST. Сравнены полные словари ключ→частота; расхождений нет."))
    rows=[]
    for size in (1,2,3):
        value=DATA["counts"][str(size)]
        rows.append([str(size),fmt(value["unique_combinations"]),fmt(value["total_occurrences"]),
                     " + ".join(value["top10"][0]["skills"]), str(value["top10"][0]["n"]), "да"])
    story.append(table(["Размер", "Уникальных", "Всего вхождений", "Частейший набор", "Частота", "SQL=MR"],rows,
                       [18*mm,28*mm,33*mm,58*mm,19*mm,18*mm]))
    story.append(para("Число вхождений растёт 601 → 2 382 → 9 106, поскольку одна вакансия с k различными навыками даёт k одиночных навыков, k(k−1)/2 пар и k(k−1)(k−2)/6 троек. Это не рост числа вакансий.", "SmallRu"))
    story.append(PageBreak())
    story.append(para("Время и память", "TitleRu"))
    story.append(para("Три последовательных запуска каждого алгоритма на одном входном объекте. Время - wall-clock для подсчёта; peak RSS - пиковая суммарная память процесса и его дочерних процессов, опрос каждые 5 мс. Прогрев кеша и рост памяти процесса DuckDB между попытками влияют на цифры; выводы о скорости относятся к этой машине и этому малому набору.", "BodyRu"))
    perf=[]
    for method,label in (("mapreduce","Свой MapReduce"),("duckdb","DuckDB SQL")):
        for i,r in enumerate(DATA["profiles"][method],1):
            perf.append([label,str(i),f"{r['seconds']:.4f}",f"{r['peak_rss_mb']:.2f}"])
    story.append(table(["Метод", "Запуск", "Время, с", "Пик RSS, МБ"],perf,[68*mm,26*mm,39*mm,41*mm]))
    m=statistics.median(x["seconds"] for x in DATA["profiles"]["mapreduce"])
    q=statistics.median(x["seconds"] for x in DATA["profiles"]["duckdb"])
    story.append(para("Медианное время: MapReduce %.4f с, DuckDB %.4f с (DuckDB быстрее примерно в %.1f раза). Пользовательская реализация создаёт два Python-процесса, что объясняет больший суммарный RSS на этом объёме." % (m,q,m/q)))
    story.append(para("Три региона", "HeadingRu"))
    story.append(para("Выбраны три региона с наибольшим числом Go-вакансий: Москва, Санкт-Петербург и Нижний Новгород. Регион вакансии взят из area.name. Медианы ниже используют только опубликованные RUR-зарплаты.", "BodyRu"))
    story.append(table(["Регион", "Вакансий", "С зарплатой", "Медиана, руб."],
                       [[r["region"],str(r["vacancies"]),str(r["salary_rows"]),fmt(r["median_rub"]) if r["median_rub"] is not None else "—"] for r in DATA["regional"]["basic"]],
                       [70*mm,31*mm,36*mm,37*mm]))
    story.append(Spacer(1,4*mm))
    region_rows=[]
    for region in DATA["regional"]["regions"]:
        skills=[x for x in DATA["regional"]["top_skills"] if x["region"]==region]
        pair=DATA["regional"]["top_combinations"]["2"][region][0]
        triple=DATA["regional"]["top_combinations"]["3"][region][0]
        region_rows.append([region,", ".join(f"{x['skill']} ({x['n']})" for x in skills[:3]),
                            " + ".join(pair["skills"])+f" ({pair['n']})",
                            " + ".join(triple["skills"])+f" ({triple['n']})"])
    story.append(table(["Регион", "Топ-3 навыка", "Топ-пара", "Топ-тройка"],region_rows,
                       [37*mm,45*mm,46*mm,46*mm]))
    story.append(para("В Москве 67 вакансий против 29 в Санкт-Петербурге и 7 в Нижнем Новгороде. Golang и PostgreSQL часто встречаются в обеих столицах. У двух последних регионов зарплатных записей только 2 и 1, поэтому сравнение их медиан нельзя считать устойчивым.", "SmallRu"))
    story.append(PageBreak())
    story.append(para("Навыки и опубликованная зарплата", "TitleRu"))
    story.append(para("Берём только RUR-вакансии с хотя бы одной указанной границей зарплаты; используем середину диапазона либо единственную границу. Для сочетания сравниваем его медиану с медианой самого частого одиночного навыка из него (частота считается внутри зарплатной подвыборки). Разница описывает ассоциацию, а не причинное влияние навыка. В таблицах показаны группы минимум с двумя вакансиями; сам исходный набор - лишь 13 зарплатных записей.", "BodyRu"))
    for size in (2,3):
        for positive,title in ((True,"Связаны с более высокой медианой"),(False,"Связаны с более низкой медианой")):
            story.append(para(f"{title}: {'пары' if size==2 else 'тройки'}", "HeadingRu"))
            rows=salary_rows(size,positive)
            story.append(table(["Сочетание", "n", "База", "База, руб.", "Группа, руб.", "Разн., руб."],rows,
                               [62*mm,10*mm,30*mm,24*mm,25*mm,23*mm]))
    story.append(para("Ограничения", "HeadingRu"))
    story.append(para("Сочетания Go и Golang сохранены как разные исходные теги: такая пара часто означает два написания одного языка, а не две компетенции. В исходном архиве часть зарплат указана gross, часть net; конверсия не проводилась. Единичные опубликованные зарплаты вне Москвы особенно ненадёжны. Наблюдаемые отклонения медиан нельзя трактовать как эффект обучения навыку или переносить на весь рынок труда.", "BodyRu"))
    story.append(para("Повторяемость", "HeadingRu"))
    story.append(para("Команды запуска и конфигурация - в README.md; исходный архив проверяется SHA-256. Подробные JSON-результаты, полный протокол трёх профилей и контрольные числа - в results/evidence.json. Объекты результатов загружены в бакет hh-lake, HEAD-проверки всех четырёх объектов получили HTTP 200.", "BodyRu"))
    story.append(PageBreak())
    story.append(para("Подтверждение в RustFS", "TitleRu"))
    story.append(para("Снимки сделаны в локальной консоли после загрузки исходного JSONL и трёх результатов MapReduce в бакет hh-lake.", "BodyRu"))
    story.append(para("Исходные данные в raw/", "SmallRu"))
    pic = Image(str(ROOT / "report" / "rustfs-source.png"), width=160 * mm, height=160 * mm * 1000 / 1440)
    pic.hAlign = "CENTER"
    story.append(pic)
    story.append(PageBreak())
    story.append(para("Сохранённые результаты MapReduce", "HeadingRu"))
    story.append(para("Три объекта навыков, пар и троек в results/go/.", "SmallRu"))
    pic = Image(str(ROOT / "report" / "rustfs-results.png"), width=160 * mm, height=160 * mm * 1000 / 1440)
    pic.hAlign = "CENTER"
    story.append(pic)
    doc.build(story)
    print(OUT)


if __name__=="__main__": main()
