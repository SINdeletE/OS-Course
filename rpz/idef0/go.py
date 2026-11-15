import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrow
import json
import math
import textwrap
import os
from matplotlib.patches import Arrow
from datetime import datetime
from zoneinfo import ZoneInfo

plt.rcParams.update({
    'pdf.fonttype': 42,
    'ps.fonttype': 42
})


A4_WIDTH = 8.27  # 210 mm
A4_HEIGHT = 11.69  # 297 mm

# Создаем фигуру размером A4


def draw_idef0_a0_diagram(data, filename='idef0_a0_diagram.png'):
    fig, ax = plt.subplots(figsize=(20, 16), constrained_layout=True)
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 16)
    ax.set_aspect('equal')
    ax.axis('off')

    # Параметры основного процесса
    process_height = 3.5
    process_width = process_height * 1.8
    process_center_x = 10
    process_center_y = 8
    process_left = process_center_x - process_width/2
    process_right = process_center_x + process_width/2
    process_bottom = process_center_y - process_height/2
    process_top = process_center_y + process_height/2

    # Основной процесс (прямоугольник)
    process_rect = patches.Rectangle((process_left, process_bottom),
                                     process_width, process_height,
                                     linewidth=4,
                                     edgecolor='black',
                                     facecolor='white',
                                     alpha=0.9)
    ax.add_patch(process_rect)

    # Текст процесса (тема ВКР)
    wrapped_tema = textwrap.fill(data['tema'], width=int(data.get('process_wrap', 30)))
    ax.text(process_center_x, process_center_y, wrapped_tema,
            ha='center', va='center',
            fontsize=16, weight='bold',
            linespacing=1.3)

    # Функция для умного переноса текста
    def smart_text_wrap(text_list, max_width=25):
        if max_width == 25:
            max_width = int(data.get("label_width", max_width))
        if not text_list:
            return ""

        # Фильтруем пустые строки и объединяем все элементы
        non_empty_texts = [str(text).strip()
                           for text in text_list if str(text).strip()]
        if not non_empty_texts:
            return ""

        combined_text = '\n'.join(non_empty_texts)

        # Разбиваем на строки с учетом переносов
        words = combined_text.replace('\n', ' ').split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            if len(test_line) <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        return '\n'.join(lines)

    # Функция для нахождения точки пересечения с прямоугольником

    def find_border_intersection(start_x, start_y, target_x, target_y, rect_left, rect_right, rect_bottom, rect_top):
        """Находит точку пересечения луча с прямоугольником"""
        dx = target_x - start_x
        dy = target_y - start_y

        if dx == 0 and dy == 0:
            return start_x, start_y

        # Параметры t для пересечения с каждой границей
        t_values = []

        # Левая граница
        if dx != 0:
            t_left = (rect_left - start_x) / dx
            if t_left >= 0:
                y = start_y + t_left * dy
                if rect_bottom <= y <= rect_top:
                    t_values.append((t_left, rect_left, y))

        # Правая граница
        if dx != 0:
            t_right = (rect_right - start_x) / dx
            if t_right >= 0:
                y = start_y + t_right * dy
                if rect_bottom <= y <= rect_top:
                    t_values.append((t_right, rect_right, y))

        # Нижняя граница
        if dy != 0:
            t_bottom = (rect_bottom - start_y) / dy
            if t_bottom >= 0:
                x = start_x + t_bottom * dx
                if rect_left <= x <= rect_right:
                    t_values.append((t_bottom, x, rect_bottom))

        # Верхняя граница
        if dy != 0:
            t_top = (rect_top - start_y) / dy
            if t_top >= 0:
                x = start_x + t_top * dx
                if rect_left <= x <= rect_right:
                    t_values.append((t_top, x, rect_top))

        # Выбираем ближайшее пересечение
        if t_values:
            t_values.sort(key=lambda x: x[0])  # Сортируем по t
            # Возвращаем x,y ближайшего пересечения
            return t_values[0][1], t_values[0][2]

        return start_x, start_y  # Нет пересечения

    # Функция для нахождения точки пересечения с эллипсом
    def find_ellipse_intersection(start_x, start_y, target_x, target_y, center_x, center_y, width, height):
        # Вектор направления от старта к цели
        dx = target_x - start_x
        dy = target_y - start_y

        # Параметрическое уравнение линии: x = start_x + t*dx, y = start_y + t*dy
        # Уравнение эллипса: ((x - center_x)/(width/2))^2 + ((y - center_y)/(height/2))^2 = 1

        # Приводим к системе координат эллипса
        a = width / 2
        b = height / 2

        # Смещаем координаты так, чтобы центр эллипса был в (0,0)
        x0 = start_x - center_x
        y0 = start_y - center_y

        # Решаем квадратное уравнение для t
        A = (dx*dx)/(a*a) + (dy*dy)/(b*b)
        B = 2*(x0*dx/(a*a) + y0*dy/(b*b))
        C = (x0*x0)/(a*a) + (y0*y0)/(b*b) - 1

        discriminant = B*B - 4*A*C

        if discriminant < 0:
            return start_x, start_y

        t1 = (-B + math.sqrt(discriminant)) / (2*A)
        t2 = (-B - math.sqrt(discriminant)) / (2*A)

        # Выбираем положительный t, который ближе к началу
        t = min(t1, t2) if t1 > 0 and t2 > 0 else max(t1, t2)

        if t > 0:
            intersect_x = start_x + t * dx
            intersect_y = start_y + t * dy
            return intersect_x, intersect_y
        else:
            return start_x, start_y

    # ВХОДЫ (слева)
    left_x = 2
    inputs = data['idef0-a0']['inputs']
    input_count = len(inputs)
    if input_count > 0:
        input_spacing = 12 / (input_count + 1)
        # os.environ['PATH'] = r'C:\\Program Files\\MiKTeX\\miktex\\bin\\x64;' + \
        #     os.environ['PATH']
        # plt.rcParams['text.usetex'] = True
        # plt.rcParams.update({"text.usetex": True,
        #                      "text.latex.preamble": r"""
        #     \usepackage[utf8]{inputenc}
        #     \usepackage[T2A]{fontenc}
        #     \usepackage[english, russian]{babel}
        #     """})
        for i, input_data in enumerate(inputs):
            y_pos = 2 + (i + 1) * input_spacing

            # Обрабатываем все поля входа
            # input_text = #smart_text_wrap(input_data)
            # print(input_data)
            input_text = smart_text_wrap(input_data)
            #input_text = r"\textbf{" + smart_text_wrap([input_data[0]]) + r"}"
            # input_text = smart_text_wrap([input_data[0]])
            # if len(input_data) > 1:
            #     input_text = input_text + " " + r"$" + input_data[1] + r"$"
            # if len(input_data) > 2:
            #     input_text = input_text + " " + \
            #         r"\textit{(" + input_data[2] + r")}"
            # input_text = smart_text_wrap([input_data[0]])
            # if len(input_data) > 1:
            #     input_text = input_text + " " + input_data[1]
            # if len(input_data) > 2:
            #     input_text = input_text + " " + input_data[2]
            # Эллипс входа
            ellipse_width, ellipse_height = 2.5, 1.4
            input_ellipse = patches.Ellipse((left_x, y_pos), ellipse_width, ellipse_height,
                                            facecolor='white',
                                            edgecolor='white',
                                            linewidth=2)
            ax.add_patch(input_ellipse)
            # print(input_text)
            # Текст входа
            ax.text(left_x, y_pos, input_text,
                    ha='center', va='center', fontsize=14, weight='bold')

            # Находим точку выхода из эллипса (правая граница)
            ellipse_exit_x, ellipse_exit_y = find_ellipse_intersection(
                left_x, y_pos,  # из центра эллипса
                process_center_x, process_center_y,  # к центру процесса
                left_x, y_pos, ellipse_width, ellipse_height
            )

            # Находим точку входа в прямоугольник процесса
            process_entry_x, process_entry_y = find_border_intersection(
                ellipse_exit_x, ellipse_exit_y,
                process_center_x, process_center_y,
                process_left, process_right, process_bottom, process_top
            )

            # Рисуем стрелку от границы эллипса до границы процесса
            ax.annotate('',
                        xy=(process_entry_x, process_entry_y),
                        xytext=(ellipse_exit_x, ellipse_exit_y),
                        arrowprops=dict(arrowstyle='->', lw=2, color='black',
                                        shrinkA=0, shrinkB=0))

    # ВЫХОДЫ (справа) - ПОЛНОСТЬЮ ПЕРЕПИСАНО!
    right_x = 18
    outputs = data['idef0-a0']['outputs']
    output_count = len(outputs)
    if output_count > 0:
        output_spacing = 12 / (output_count + 1)

        for i, output_data in enumerate(outputs):
            y_pos = 2 + (i + 1) * output_spacing

            # Обрабатываем все поля выхода
            output_text = smart_text_wrap(output_data)

            # Эллипс выхода
            ellipse_width, ellipse_height = 2.5, 1.4
            output_ellipse = patches.Ellipse((right_x, y_pos), ellipse_width, ellipse_height,
                                             facecolor='white',
                                             edgecolor='white',
                                             linewidth=2)
            ax.add_patch(output_ellipse)

            # Текст выхода
            ax.text(right_x, y_pos, output_text,
                    ha='center', va='center', fontsize=14, weight='bold')

            # Шаг 1: Находим точку ВЫХОДА из прямоугольника процесса
            # (от центра процесса к центру эллипса выхода)
            #print(process_center_x, process_center_y)
            #print(right_x, y_pos)

            process_exit_x, process_exit_y = find_border_intersection(
                process_center_x, process_center_y,  # ИЗ центра процесса
                right_x, y_pos,  # К центру эллипса
                process_left, process_right, process_bottom, process_top
            )
            #print(process_exit_x, process_exit_y)

            # Шаг 2: Находим точку ВХОДА в эллипс выхода
            # (от найденной точки на процессе к центру эллипса)
            ellipse_entry_x, ellipse_entry_y = find_ellipse_intersection(
                process_exit_x, process_exit_y,  # ИЗ точки на границе процесса
                right_x, y_pos,  # К центру эллипса
                right_x, y_pos, ellipse_width, ellipse_height
            )

            # Рисуем стрелку ОТ границы процесса ДО границы эллипса
            ax.annotate('',
                        # КОНЕЦ стрелки (граница эллипса)
                        xy=(ellipse_entry_x, ellipse_entry_y),
                        # НАЧАЛО стрелки (граница процесса)
                        xytext=(process_exit_x, process_exit_y),
                        arrowprops=dict(arrowstyle='->', lw=2, color='black',
                                        shrinkA=0, shrinkB=0))

    # УПРАВЛЕНИЯ (сверху)
    top_y = 14
    controls = data['idef0-a0']['controls']
    control_count = len(controls)
    if control_count > 0:
        control_spacing = 14 / (control_count + 1)

        for i, control_data in enumerate(controls):
            x_pos = 3 + (i + 1) * control_spacing

            # Обрабатываем все поля управления
            control_text = smart_text_wrap(control_data)

            # Шестиугольник управления
            hexagon_radius = 1.2
            hexagon = patches.RegularPolygon((x_pos, top_y), 6, radius=hexagon_radius,
                                             orientation=math.pi/6,
                                             facecolor='white',
                                             edgecolor='white',
                                             linewidth=2)
            ax.add_patch(hexagon)

            # Текст управления
            ax.text(x_pos, top_y, control_text,
                    ha='center', va='center', fontsize=12, weight='bold')

            # Находим точку выхода из шестиугольника (нижняя граница)
            start_x, start_y = x_pos, top_y - hexagon_radius * 0.9

            # Находим точку входа в прямоугольник процесса
            process_entry_x, process_entry_y = find_border_intersection(
                x_pos, top_y,  # от центра шестиугольника
                process_center_x, process_center_y,  # к центру процесса
                process_left, process_right, process_bottom, process_top
            )

            # Рисуем стрелку от границы шестиугольника до границы процесса
            ax.annotate('',
                        xy=(process_entry_x, process_entry_y),
                        xytext=(start_x, start_y),
                        arrowprops=dict(arrowstyle='->', lw=2, color='black',
                                        shrinkA=0, shrinkB=0))

    # МЕХАНИЗМЫ (снизу)
    bottom_y = 2
    mechanisms = data['idef0-a0']['mechanisms']
    mechanism_count = len(mechanisms)
    if mechanism_count > 0:
        mechanism_spacing = 14 / (mechanism_count + 1)

        for i, mechanism_data in enumerate(mechanisms):
            x_pos = 3 + (i + 1) * mechanism_spacing

            # Обрабатываем все поля механизма
            mechanism_text = smart_text_wrap(mechanism_data)

            # Прямоугольник механизма
            mechanism_width, mechanism_height = 2.8, 1.4
            mechanism_rect = patches.Rectangle((x_pos - mechanism_width/2, bottom_y - mechanism_height/2),
                                               mechanism_width, mechanism_height,
                                               linewidth=2,
                                               edgecolor='white',
                                               facecolor='white')
            ax.add_patch(mechanism_rect)

            # Текст механизма
            ax.text(x_pos, bottom_y, mechanism_text,
                    ha='center', va='center', fontsize=12, weight='bold')

            # Находим точку выхода из механизма (верхняя граница)
            start_x, start_y = x_pos, bottom_y + mechanism_height/2 * 0.9

            # Находим точку входа в прямоугольник процесса
            process_entry_x, process_entry_y = find_border_intersection(
                x_pos, bottom_y,  # от центра механизма
                process_center_x, process_center_y,  # к центру процесса
                process_left, process_right, process_bottom, process_top
            )

            # Рисуем стрелку от границы механизма до границы процесса
            ax.annotate('',
                        xy=(process_entry_x, process_entry_y),
                        xytext=(start_x, start_y),
                        arrowprops=dict(arrowstyle='->', lw=2, color='black',
                                        shrinkA=0, shrinkB=0))

    # КОММЕНТАРИИ (в самом низу, без стрелок)
    comments = data['idef0-a0']['comments']
    if comments:
        # Обрабатываем все комментарии и все их поля
        all_comment_texts = []
        for comment_group in comments:
            # Фильтруем пустые строки в каждой группе комментариев
            non_empty_comments = [str(text).strip()
                                  for text in comment_group if str(text).strip()]
            if non_empty_comments:
                all_comment_texts.extend(non_empty_comments)

        if all_comment_texts:
            # Объединяем все комментарии
            combined_comments = '\n'.join(all_comment_texts)
            wrapped_comments = smart_text_wrap(
                [combined_comments], max_width=50)

            # Размещаем комментарии внизу
            ax.text(process_center_x, 0.5, wrapped_comments,
                    ha='center', va='center', fontsize=14,
                    style='italic', color='darkblue',
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="lightyellow", alpha=0.8))

    # Заголовок
    moscow_tz = ZoneInfo('Europe/Moscow')
    now = datetime.now(moscow_tz)
    formatted = now.strftime("%d.%m.%Y %H:%M")
    plt.title(f'Метамодель. Сгенерировано {formatted}\nТема: {data["tema"]}',
              fontsize=18, pad=25, weight='bold')

    # Статус утверждения
    # f"Руководитель одобрил тему ВКР: {data['Руководитель одобрил тему ВКР']}\n
    status_text = f"Руководитель одобрил ФПЗ: {data['Руководитель одобрил ФПЗ']}"
    ax.text(process_center_x, 15.2, status_text,
            ha='center', va='center', fontsize=14,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.7))

    # Optional font scale keeps diagram labels readable in the printed report.
    font_scale = float(data.get('font_scale', 1.0))
    for label in ax.texts:
        label.set_fontsize(label.get_fontsize() * font_scale)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.show()
    print(f"Диаграмма сохранена как {filename}")


# Загрузка данных и создание диаграммы
try:
    with open('fpz.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Проверяем тип диаграммы
    if data.get('type') == 'idef0-a0':
        draw_idef0_a0_diagram(data, 'idef0_a0_diagram.pdf')
        draw_idef0_a0_diagram(data, 'idef0_a0_diagram_preview.png')
    else:
        print("Неверный тип диаграммы в JSON")

except FileNotFoundError:
    print("Файл fpz.json не найден")
except json.JSONDecodeError:
    print("Ошибка чтения JSON файла")
except KeyError as e:
    print(f"Отсутствует обязательный ключ в JSON: {e}")
