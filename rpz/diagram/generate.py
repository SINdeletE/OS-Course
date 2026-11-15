#!/usr/bin/env python3
"""Create compact GraphML flowcharts using copies of the supplied yEd styles."""
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
G = "http://graphml.graphdrawing.org/xmlns"
Y = "http://www.yworks.com/xml/graphml"
NS = {"g": G, "y": Y}
ET.register_namespace("", G)
ET.register_namespace("y", Y)
ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
template = ET.parse(ROOT / "insert_store_transaction.graphml").getroot()
prototypes = {}
for node in template.findall("g:graph/g:node", NS):
    generic = node.find("g:data/y:GenericNode", NS)
    if generic is not None:
        prototypes.setdefault(generic.get("configuration").rsplit(".", 1)[-1], node)
edge_prototype = next(edge for edge in template.findall("g:graph/g:edge", NS)
                      if edge.find("g:data/y:PolyLineEdge/y:EdgeLabel", NS) is not None
                      and edge.find("g:data/y:PolyLineEdge/y:EdgeLabel", NS).text == "Нет")


def chart(filename, title, nodes, edges):
    document = deepcopy(template)
    graph = document.find("g:graph", NS)
    for child in list(graph):
        graph.remove(child)
    ET.SubElement(graph, f"{{{G}}}data", {"key": "d0"}).text = title
    positions = {}
    for identifier, kind, text, cx, cy in nodes:
        node = deepcopy(prototypes[kind])
        node.set("id", identifier)
        geometry = node.find("g:data/y:GenericNode/y:Geometry", NS)
        width, height = float(geometry.get("width")), float(geometry.get("height"))
        geometry.set("x", str(cx - width / 2))
        geometry.set("y", str(cy - height / 2))
        label = node.find("g:data/y:GenericNode/y:NodeLabel", NS)
        label.text = text
        lines = text.splitlines()
        label_width = min(width - 8, max(len(line) for line in lines) * 6.2 + 4)
        label_height = len(lines) * 14.2 + 4
        for name, value in (("width", label_width), ("height", label_height),
                            ("x", (width - label_width) / 2), ("y", (height - label_height) / 2)):
            label.set(name, str(value))
        graph.append(node)
        positions[identifier] = (cx, cy)
    for number, (source, target, label_text, waypoints) in enumerate(edges):
        edge = deepcopy(edge_prototype)
        edge.set("id", "e%d" % number)
        edge.set("source", source)
        edge.set("target", target)
        polyline = edge.find("g:data/y:PolyLineEdge", NS)
        path = polyline.find("y:Path", NS)
        for child in list(path):
            path.remove(child)
        for name in ("sx", "sy", "tx", "ty"):
            path.set(name, "0.0")
        for x, y in waypoints:
            ET.SubElement(path, f"{{{Y}}}Point", {"x": str(x), "y": str(y)})
        polyline.find("y:Arrows", NS).set("target", "standard")
        label = polyline.find("y:EdgeLabel", NS)
        if label_text:
            label.text = label_text
            label.set("width", str(len(label_text) * 6.2 + 4))
            label.set("height", "18.1328125")
            sx, sy = positions[source]
            first_x, first_y = waypoints[0] if waypoints else positions[target]
            label.set("x", str((first_x - sx) / 2 + 6))
            label.set("y", str((first_y - sy) / 2 + 6))
            model = label.find("y:ModelParameter/y:SmartEdgeLabelModelParameter", NS)
            model.set("distance", "10.0")
            model.set("ratio", "0.5")
        else:
            polyline.remove(label)
        graph.append(edge)
    ET.indent(document, space="  ")
    ET.ElementTree(document).write(ROOT / filename, encoding="UTF-8", xml_declaration=True)


def main():
    chart("probe.graphml", "Подключение интерфейса и подготовка устройства ввода", [
        ("n0", "terminator", "Начало probe", 300, 40),
        ("n1", "decision", "Основной\nинтерфейс?", 300, 150),
        ("n2", "process", "Занять интерфейс\nбез опроса", 590, 150),
        ("n3", "predefinedProcess", "Найти конечную\nточку ввода", 300, 280),
        ("n4", "decision", "Параметры\nдопустимы?", 300, 400),
        ("n5", "predefinedProcess", "Подготовить мышь\nи запустить URB", 300, 530),
        ("n6", "decision", "Подключение\nуспешно?", 300, 660),
        ("n7", "process", "Освободить\nресурсы", 590, 660),
        ("n8", "terminator", "Успех", 300, 800),
        ("n9", "terminator", "Ошибка", 590, 800),
    ], [
        ("n0", "n1", "", []), ("n1", "n3", "Да", []), ("n1", "n2", "Нет", []),
        ("n2", "n8", "", [(760, 150), (760, 740), (300, 740)]),
        ("n3", "n4", "", []), ("n4", "n5", "Да", []),
        ("n4", "n9", "Нет", [(700, 400), (700, 800)]),
        ("n5", "n6", "", []), ("n6", "n8", "Да", []),
        ("n6", "n7", "Нет", []), ("n7", "n9", "", []),
    ])
    chart("complete.graphml", "Обработка завершения USB-запроса", [
        ("n0", "terminator", "Завершение URB", 300, 40),
        ("n1", "decision", "Приём\nразрешён?", 300, 150),
        ("n2", "decision", "Статус\nравен нулю?", 300, 280),
        ("n3", "predefinedProcess", "Обработать\nкорректный отчёт", 300, 410),
        ("n4", "predefinedProcess", "Повторно\nотправить URB", 300, 800),
        ("n5", "decision", "Отмена\nзапроса?", 590, 280),
        ("n6", "process", "Остановить ввод;\nотпустить кнопки", 590, 410),
        ("n7", "decision", "Ошибка\nEPIPE?", 590, 540),
        ("n8", "predefinedProcess", "Поставить задачу\nвосстановления", 590, 670),
        ("n9", "process", "Записать\nпредупреждение", 590, 800),
        ("n10", "terminator", "Выход", 300, 930),
    ], [
        ("n0", "n1", "", []), ("n1", "n2", "Да", []),
        ("n1", "n10", "Нет", [(130, 150), (130, 930)]),
        ("n2", "n3", "Да", []), ("n2", "n5", "Нет", []), ("n3", "n4", "", []),
        ("n5", "n6", "Да", []), ("n5", "n7", "Нет", [(750, 280), (750, 490), (590, 490)]),
        ("n6", "n10", "", [(800, 410), (800, 990), (300, 990)]),
        ("n7", "n8", "Да", []), ("n7", "n9", "Нет", [(750, 540), (750, 800)]),
        ("n8", "n10", "", [(690, 670), (690, 910), (430, 910), (430, 930)]),
        ("n9", "n4", "", []), ("n4", "n10", "", []),
    ])
    chart("decode.graphml", "Преобразование отчёта стилуса в события мыши", [
        ("n0", "terminator", "Начало decode", 300, 40),
        ("n1", "decision", "Формат\nдопустим?", 300, 150),
        ("n2", "decision", "Перо в зоне\nсчитывания?", 300, 280),
        ("n3", "process", "Прочитать\nкоординаты X, Y", 300, 410),
        ("n4", "decision", "Координаты\nдопустимы?", 300, 540),
        ("n5", "decision", "Есть предыдущий\nотсчёт?", 300, 670),
        ("n6", "process", "Вычислить сдвиги\nи остатки деления", 300, 800),
        ("n7", "process", "Сохранить X, Y;\nзадать кнопки", 300, 930),
        ("n8", "terminator", "Отчёт принят", 300, 1060),
        ("n9", "terminator", "Игнорировать", 590, 150),
        ("n10", "process", "Сбросить отсчёт;\nобнулить события", 590, 280),
    ], [
        ("n0", "n1", "", []), ("n1", "n9", "Нет", []), ("n1", "n2", "Да", []),
        ("n2", "n3", "Да", []), ("n2", "n10", "Нет", []),
        ("n10", "n8", "", [(800, 280), (800, 1120), (300, 1120)]),
        ("n3", "n4", "", []), ("n4", "n5", "Да", []),
        ("n4", "n9", "Нет", [(720, 540), (720, 150)]),
        ("n5", "n6", "Да", []), ("n5", "n7", "Нет", [(130, 670), (130, 930)]),
        ("n6", "n7", "", []), ("n7", "n8", "", []),
    ])
    chart("stop.graphml", "Согласованная остановка приёма", [
        ("n0", "terminator", "Начало stop", 300, 40),
        ("n1", "process", "Захватить lock;\nrunning = false", 300, 160),
        ("n2", "process", "Освободить\nблокировку", 300, 290),
        ("n3", "predefinedProcess", "Дождаться URB:\nusb_kill_urb", 300, 420),
        ("n4", "predefinedProcess", "Дождаться work:\ncancel_work_sync", 300, 550),
        ("n5", "predefinedProcess", "Сбросить отсчёт;\nотпустить кнопки", 300, 680),
        ("n6", "terminator", "Выход", 300, 810),
    ], [("n%d" % i, "n%d" % (i + 1), "", []) for i in range(6)])
    chart("recovery.graphml", "Восстановление конечной точки", [
        ("n0", "terminator", "Начало work", 300, 40),
        ("n1", "predefinedProcess", "Сбросить halt:\nusb_clear_halt", 300, 170),
        ("n2", "process", "Захватить\nблокировку", 300, 300),
        ("n3", "decision", "Приём\nразрешён?", 300, 430),
        ("n4", "decision", "Halt снят\nуспешно?", 300, 560),
        ("n5", "predefinedProcess", "Повторно\nотправить URB", 300, 690),
        ("n6", "process", "Остановить ввод;\nкнопки = 0; журнал", 590, 690),
        ("n7", "process", "Освободить\nблокировку", 300, 820),
        ("n8", "terminator", "Выход", 300, 950),
    ], [
        ("n0", "n1", "", []), ("n1", "n2", "", []), ("n2", "n3", "", []),
        ("n3", "n4", "Да", []), ("n3", "n7", "Нет", [(130, 430), (130, 820)]),
        ("n4", "n5", "Да", []), ("n4", "n6", "Нет", [(590, 560)]),
        ("n5", "n7", "", []), ("n6", "n7", "", [(590, 820)]), ("n7", "n8", "", []),
    ])
    chart("binding.graphml", "Перепривязка интерфейсов с откатом", [
        ("n0", "terminator", "Начало bind", 300, 40),
        ("n1", "process", "Найти интерфейсы;\nпрочитать привязки", 300, 170),
        ("n2", "decision", "Есть следующий\nинтерфейс?", 300, 300),
        ("n3", "process", "Сохранить прежний\nдрайвер в файл", 300, 430),
        ("n4", "predefinedProcess", "Отключить драйвер;\nпривязать модуль", 300, 560),
        ("n5", "decision", "Привязка\nуспешна?", 300, 690),
        ("n6", "process", "Перейти\nк следующему", 300, 820),
        ("n7", "predefinedProcess", "Восстановить\nпрежние привязки", 590, 690),
        ("n8", "terminator", "Успех", 590, 300),
        ("n9", "terminator", "Ошибка", 590, 820),
    ], [
        ("n0", "n1", "", []), ("n1", "n2", "", []), ("n2", "n3", "Да", []),
        ("n2", "n8", "Нет", []), ("n3", "n4", "", []), ("n4", "n5", "", []),
        ("n5", "n6", "Да", []), ("n5", "n7", "Нет", []),
        ("n6", "n2", "", [(130, 820), (130, 300)]), ("n7", "n9", "", []),
    ])


if __name__ == "__main__":
    main()
