import flet as ft
import ui_utils
from pathlib import Path
from ui_utils import bg_ui_process
import os
import sqlite3
import time
tags = {"Название": "Выберите трек", "Автор": "", "Альбом": "", "Год": "", "Жанр": "",}
p = './music' #начальная папка
folder_items = ui_utils.fnew_path(p) #обработчик для начальной папки

#uicolor = ui_utils.rgba(255, 227, 185, 32) #argb по стандарту (255, 227, 185, 32) 
#bgcolor

import configparser
config = configparser.ConfigParser()
config.read('config.txt', encoding='utf-8')
# Конфиги =========
start_vol_val = config.getint('Main Settings', 'start_vol_val')
# =================

config.read('ui_config.txt', encoding='utf-8')

radius = config.getint('UI Settings', 'radius') # закругление картинки c: 8
text_size = config.getint('UI Settings', 'text_size') # рекомендуемое значение 13

# Конфиги UBOX =========
UBOX_b_radius = config.getint('UBOX Settings', 'b_radius') #закругление UBOX ui рамки c: 20

# Конфиги LBOX =========
LBOX_b_radius = config.getint('LBOX Settings', 'b_radius') #закругление LBOX ui рамки c: 20

# Конфиги CBOX =========
CBOX_b_radius = config.getint('CBOX Settings', 'b_radius') #закругление CBOX ui рамки c: 20

# Конфиги RBOX =========
RBOX_b_radius = config.getint('RBOX Settings', 'b_radius') #закругление RBOX ui рамки c: 20

# Конфиги DBOX =========
DBOX_b_radius = config.getint('DBOX Settings', 'b_radius') #закругление DBOX ui рамки c: 20

# Конфиги adress_bar =========
adress_barBGCol = config.get('UI adress_bar', 'adress_barBGCol') # Цвет фона строки
adress_barBGOp = config.getfloat('UI adress_bar','adress_barBGOp') # Прозрачность фона строки
adress_barBorderCol = config.get('UI adress_bar','adress_barBorderCol') # Цвет рамки (обводки) строки
adress_barBorderOp = config.getfloat('UI adress_bar','adress_barBorderOp') # Прозрачность рамки строки
#Конфиги adress_button =======
adress_ButtonIconCol = config.get('UI adress_button','adress_ButtonIconCol') # Цвет иконки кнопки выбора файла справа от строки
adress_ButtonBGCol = config.get('UI adress_button','adress_ButtonBGCol') # Цвет фона кнопки выбора файла справа от строки
adress_Button_BCol = config.get('UI adress_button','adress_Button_BCol') # Цвет рамки (обводки) кнопки выбора файла справа от строки
adress_Button_BTol = config.getfloat('UI adress_button','adress_Button_BTol') # Толщина рамки (обводки) кнопки выбора файла справа от строки
adress_Button_Radius = config.getfloat('UI adress_button','adress_Button_Radius') # Сила скругления углов кнопки выбора файла справа от строки
#Конфиги search_bar ==========
search_barBGCol = config.get('UI search_bar', 'search_barBGCol') # Цвет фона строки поиска
search_barBGOp = config.getfloat('UI search_bar','search_barBGOp') # Прозрачность фона строки поиска
search_barBorderCol = config.get('UI search_bar','search_barBorderCol') # Цвет рамки (обводки) строки поиска
search_barBorderOp = config.getfloat('UI search_bar','search_barBorderOp') # Прозрачность рамки строки поиска
search_bar_radius = config.getint('UI search_bar','search_bar_radius') # Сила скругления углов строки поиска
# ==== queue_cell presets: ===
queue_border_radius = 8
#queue_cell = (45, 15, 12, 2, 8, 60) #настройки для ячейки очереди (размер обложки, размер названия, размер автора, расстояние между ними, отступы внутри ячейки, высота ячейки)
#queue_cell = (35, 13, 10, 2, 3, 48)
#queue_cell = (28, 11, 8, 0, 1, 33)
#queue_cell = (22, 9, 6, 0, 0.5, 27)
k = 0.7
queue_cell = ((46 * k + 8.2), (12 * k + 5.4), (12 * k + 2.4), (4 * k - 1.2), (15 * k - 4), (76 * k + 4.2))
# ============================


def App(page: ft.Page):
    page.title = "App"
    page.assets_dir = "assets"

    explorer_tree = ft.ListView(
        expand=True,
        spacing=10,
    )

    play_btn=ft.Image(
    src="assets/icons/play_ico_inac.png",
    width=45,          
    height=45,         
    fit="contain",
    )

    # Динамический проводник
    def rebuild_explorer(items, current_dir):
        explorer_tree.controls.clear()
        current_dir = Path(current_dir).resolve()

        # --- АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ АДРЕСНОЙ СТРОКИ ПРИ СМЕНЕ ПАПКИ ---
        path_text.spans = build_breadcrumbs(str(current_dir))

        try:        
            if path_text.page: path_text.update()
        except RuntimeError:
            pass
        # ----------------------------------------------------------------
        current_dir = Path(current_dir).resolve()
        start_dir = Path(p).resolve()
        current_path = Path(items[0]["path"]).parent if items else None

        explorer_tree.controls.append( #Верхняя кнопка
                ft.GestureDetector(
                    data=str(current_dir.parent),
                    on_double_tap=lambda e: ui_utils.on_item_click(e, rebuild_explorer, play_btn),
                    mouse_cursor=ft.MouseCursor.CLICK,
                    content=ft.Row([
                ft.Icon(ft.Icons.ARROW_UPWARD, size=16, color="amber"),
                ft.Text("...", size=12, color="amber"),
                    ])
                )
        )

        if not items: #если папка пустая
            explorer_tree.controls.append(
                ft.Container(
                    content=ft.Text("Папка пуста", size=12, color="gray", italic=True),
                    padding=10
                )
            )
        else: #Элементы
            for item in items:
                full_item_path = str(Path(item["path"]))
                explorer_tree.controls.append(
                    ft.Draggable(
                        group="queue_drag",
                        data=item["path"], 
                        content=ft.ContextMenu(
                            secondary_items=[
                                ft.PopupMenuItem(content=ft.Text("Добавить в очередь"), on_click=lambda e, p=full_item_path: (
                                    ui_utils.add_queue(p), 
                                    rebuild_queue_ui()
                                )),
                                ft.PopupMenuItem(content=ft.Text("Добавить в избранное"), on_click=lambda e, p=full_item_path: (
                                    ui_utils.add_favorite(p), 
                                    # rebuild_favorite_ui()
                                )),
                                ft.PopupMenuItem(content=ft.Text("Добавить в альбрм"), on_click=lambda e, p=full_item_path: (
                                    # ui_utils.add_playlist(p), 
                                    # rebuild_playlist_ui()
                                )),
                            ],
                        content=ft.GestureDetector(
                            data=item["path"],
                            on_double_tap=lambda e: ui_utils.on_item_click(e, rebuild_explorer, play_btn),
                            mouse_cursor=ft.MouseCursor.CLICK,
                            content=ft.Row([
                                ft.Icon(
                                    ft.Icons.FOLDER if item["type"] == "folder" else ft.Icons.AUDIOTRACK,
                                    size=16
                                ),
                                ft.Text(item["name"], size=12, overflow=ft.TextOverflow.ELLIPSIS),
                            ])
                            )
                        ),
                        content_when_dragging=ft.Container(
                            content=ft.Text(f"Перемещение: {item['name']}", size=10, overflow=ft.TextOverflow.ELLIPSIS),
                            padding=10,
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, 
                            border_radius=5,
                            width=180,
                        )
                    )
                )
        page.update()

    def build_breadcrumbs(path):
        normalized_path = path.replace("\\", "/")
        segments = normalized_path.split("/")
        segments = [s for s in segments if s]
        spans = []
        
        is_windows = ":" in normalized_path
        
        for i, segment in enumerate(segments):
            # Корректная сборка путей для Windows и Linux
            if is_windows:
                sub_path = segments[0] + "/" + "/".join(segments[1:i+1])
            else:
                sub_path = "/" + "/".join(segments[:i+1])
            sub_path = str(Path(sub_path).resolve())

            # Замораживаем sub_path через дефолтный аргумент лямбды (p=sub_path)
            spans.append(
                ft.TextSpan(
                    text=segment,
                    style=ft.TextStyle(
                        color=ft.Colors.BLUE, 
                        decoration=ft.TextDecoration.UNDERLINE,
                        size=text_size  # Синхронизируем с твоим конфигом
                    ),
                    on_click=lambda e, p=sub_path: ui_utils.on_segment_click(e, p, rebuild_explorer)
                )
            )

            if i < len(segments) - 1:
                spans.append(
                    ft.TextSpan(
                        text=" / ", 
                        style=ft.TextStyle(color=ft.Colors.GREY_400, size=text_size)
                    )
                )
                
        return spans
    path_text = ft.Text(spans=build_breadcrumbs(p), no_wrap=True)

    queue_list = ft.Column(
        spacing=8,
        scroll=ft.ScrollMode.AUTO, 
        expand=True,
        alignment=ft.MainAxisAlignment.START
    )
    
    def rebuild_queue_ui():
        queue_list.controls.clear()
        def on_track_click(clicked_id):
            if clicked_id == 0:
                return # Трек уже играет
            con = sqlite3.connect('queue.db')
            cursor = con.cursor()
            try:
                cursor.execute("UPDATE queue SET id = id - ?", (clicked_id,))
                cursor.execute("SELECT path FROM queue WHERE id = 0")
                r = cursor.fetchone()
                path = r[0] if r else None
                con.commit()
            except Exception as ex:
                print(f"Ошибка при обновлении очереди в БД: {ex}")
                con.rollback()
            finally:
                con.close()
            
            ui_utils.load_track(page, path, play_btn, clicked_id)
            rebuild_queue_ui()

        con = sqlite3.connect('queue.db')
        cursor = con.cursor()
        # Сортируем строго по ID, чтобы 0 (играющий сейчас) был всегда наверху
        cursor.execute("SELECT id, name, author, path, cov_bytes FROM queue WHERE id >= 0 ORDER BY id ASC")
        rows = cursor.fetchall()
        con.close()

        anim_config = ft.Animation(350, ft.AnimationCurve.EASE_OUT)
        for row in rows:
            track_id, name, author, path, cov_bytes = row
            
            # 1. Визуальное оформление играющего трека (id == 0)
            is_playing = (track_id == 0)
            border_color = ft.Colors.GREEN if is_playing else ft.Colors.TRANSPARENT
            bg_color = ft.Colors.SURFACE_CONTAINER_HIGHEST if not is_playing else ft.Colors.SURFACE_CONTAINER_HIGH

            # Попытка декодировать обложку (если она есть)
            cover_img = ft.Icon(ft.Icons.MUSIC_NOTE, size=queue_cell[0])
            if cov_bytes is not None:
                cover_img = ft.Image(src=cov_bytes, width=queue_cell[0], height=queue_cell[0])
                pass
            
            item_content = ft.Container(
                content=ft.Row([
                    cover_img,
                    ft.Column([
                        ft.Text(name, size=queue_cell[1], weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN if is_playing else ft.Colors.ON_SURFACE),
                        ft.Text(author, size=queue_cell[2], color=ft.Colors.ON_SURFACE_VARIANT)
                    ], spacing=queue_cell[3])
                ]),
                padding=queue_cell[4],
                border=ft.Border.all(2, border_color),
                border_radius=queue_border_radius,
                bgcolor=bg_color,
                # --- ДОБАВЛЯЕМ ДЛЯ АНИМАЦИИ ---
                height=queue_cell[5],  # Фиксированная высота важна, чтобы Flet знал от чего "схлопывать"
                opacity=1.0, # Явно указываем стартовую непрозрачность
                offset=ft.Offset(0, 0), # Явно указываем стартовую позицию (на месте)
                animate=anim_config,
                animate_opacity=anim_config,
                animate_offset=anim_config,   # <--- Включаем анимацию сдвига
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                data=track_id, # Сохраняем ID прямо в контейнер
                on_click=lambda e: on_track_click(e.control.data)
            )

            # 2. Обработчик Drop (когда на этот элемент что-то бросают)
            def on_accept(e):
                src_control = page.get_control(e.src_id) # Элемент, который тащим
                if src_control is None:
                    return
                src_data = src_control.data      # Это либо ID трека (int), либо путь (str)
                target_id = e.control.data # Если бросили сами на себя — ничего не делаем
                if isinstance(src_data, str):
                    # Вызываем обновленную функцию добавления, указывая куда вставить
                    ui_utils.add_queue(src_data, insert_at=target_id)
                    
                    # Если папку/файл бросили прямо на место играющего трека (id 0),
                    # имеет смысл сразу запустить первый трек из этой папки
                    if target_id == 0:
                        con_q = sqlite3.connect('queue.db')
                        cur = con_q.cursor()
                        cur.execute("SELECT path FROM queue WHERE id = 0")
                        new_track = cur.fetchone()
                        con_q.close()
                        if new_track:
                            ui_utils.load_track(page, new_track[0], play_btn, 0)
                            
                    # Полностью перерисовываем очередь (БД уже обновилась)
                    rebuild_queue_ui()
                    return # Прерываем функцию, чтобы не сработала логика ниже


                src_id = src_control.data                # ID перетаскиваемого трека
                if src_id == target_id:
                    return

                # --- 2. ОБНОВЛЕНИЕ БАЗЫ ДАННЫХ (ГИБРИДНАЯ ЛОГИКА) ---
                con_queue = sqlite3.connect('queue.db')
                cursor = con_queue.cursor()
                try:
                    if target_id == 0:
                        # ВЕТКА А: Бросили на 0 место (Вставка со сдвигом вниз)
                        cursor.execute("UPDATE queue SET id = -999 WHERE id = ?", (src_id,))
                        # Сдвигаем все треки от 0 до бывшего места перетаскиваемого трека на +1
                        cursor.execute("UPDATE queue SET id = id + 1 WHERE id >= 0 AND id < ?", (src_id,))
                        cursor.execute("UPDATE queue SET id = 0 WHERE id = -999")
                        con_queue.commit()

                        # Запускаем трек, так как он стал нулевым
                        cursor.execute("SELECT path FROM queue WHERE id = 0")
                        path_row = cursor.fetchone()
                        if path_row:
                            ui_utils.load_track(page, path_row[0], play_btn, 0)

                    else:
                        # ВЕТКА Б: Бросили на любое другое место (Обычный Swap)
                        cursor.execute("UPDATE queue SET id = -999 WHERE id = ?", (src_id,))
                        cursor.execute("UPDATE queue SET id = ? WHERE id = ?", (src_id, target_id))
                        cursor.execute("UPDATE queue SET id = ? WHERE id = -999", (target_id,))
                        con_queue.commit()

                        # Если мы утащили сам нулевой трек вниз, на его место (0) встал другой трек
                        # Его тоже нужно включить
                        if src_id == 0:
                            cursor.execute("SELECT path FROM queue WHERE id = 0")
                            path_row = cursor.fetchone()
                            if path_row:
                                ui_utils.load_track(page, path_row[0], play_btn, 0)

                except Exception as ex:
                    print(f"Ошибка БД при перетаскивании: {ex}")
                    con_queue.rollback()
                    return # Прерываем UI-обновление при ошибке
                finally:
                    con_queue.close()

                # --- 3. ОБНОВЛЕНИЕ ИНТЕРФЕЙСА ---
                src_index = None
                target_index = None

                for i, ctrl in enumerate(queue_list.controls):
                    if ctrl.data == src_id:
                        src_index = i
                    elif ctrl.data == target_id:
                        target_index = i

                if src_index is not None and target_index is not None:
                    
                    if target_id == 0:
                        # ВЕТКА А (UI): Вырезаем элемент и вставляем в начало списка
                        moved_control = queue_list.controls.pop(src_index)
                        queue_list.controls.insert(0, moved_control)
                    else:
                        # ВЕТКА Б (UI): Меняем элементы местами 1 к 1
                        queue_list.controls[src_index], queue_list.controls[target_index] = \
                            queue_list.controls[target_index], queue_list.controls[src_index]

                    # --- 4. ОБНОВЛЕНИЕ СКРЫТЫХ ID И ВИЗУАЛА ---
                    for i, ctrl in enumerate(queue_list.controls):
                        ctrl.data = i                  # Обновляем ID для DragTarget
                        ctrl.content.data = i          # Обновляем ID для вложенного Draggable
                        ctrl.content.content.data = i  # Обновляем ID для клика

                        # Применяем зеленое выделение только к нулевому треку
                        is_playing = (i == 0)
                        border_color = ft.Colors.GREEN if is_playing else ft.Colors.TRANSPARENT
                        bg_color = ft.Colors.SURFACE_CONTAINER_HIGHEST if not is_playing else ft.Colors.SURFACE_CONTAINER_HIGH
                        
                        ctrl.content.content.border = ft.Border.all(2, border_color)
                        ctrl.content.content.bgcolor = bg_color
                    
                    queue_list.update()

            # 3. Визуальный отклик при взаимодействии
            def on_will_accept(e):
                e.control.content.content.border = ft.Border.all(2, ft.Colors.BLUE_ACCENT)
                e.control.update()

            def on_leave(e):
                is_playing_now = (e.control.data == 0)
                border_col = ft.Colors.GREEN if is_playing_now else ft.Colors.TRANSPARENT
                e.control.content.content.border = ft.Border.all(2, border_col)
                e.control.update()

            # 4. Собираем матрешку: Target (зона дропа) -> Draggable (можно тащить) -> Container (внешний вид)
            drag_item = ft.DragTarget(
                group="queue_drag", # ВАЖНО: Общая группа с проводником
                data=track_id, # Сохраняем target_id в данных таргета для on_leave
                on_accept=on_accept,
                on_will_accept=on_will_accept,
                on_leave=on_leave,
                content=ft.Draggable(
                    group="queue_drag",
                    data=track_id, # Передаем ID при перетаскивании
                    content=item_content,
                    content_when_dragging=ft.Container(
                        content=ft.Text(f"Перемещение: {name}", size=queue_cell[1]),
                        padding=queue_cell[4],
                        expand=True,
                        bgcolor=ft.Colors.INVERSE_SURFACE,
                        border_radius=queue_border_radius,
                        opacity=0.8
                    )
                )
            )
            queue_list.controls.append(drag_item)
        page.update()
    def skip_track_with_animation(page, queue_list, rebuild_callback, idx):
        """
        Визуально уводит отыгравший трек влево и гасит его,
        плавно подсвечивает зелёным следующий трек,
        смещает очередь вверх и затем обновляет UI.
        """
        if len(queue_list.controls) > 0:
            # 1. Берем ПЕРВЫЙ элемент и анимируем его (уводим влево)
            first_item = queue_list.controls[0]
            first_container = first_item.content.content
            
            first_container.opacity = 0
            first_container.offset = ft.Offset(-1, 0)
            first_container.border = ft.Border.all(0, ft.Colors.TRANSPARENT)

            # 2. Если есть СЛЕДУЮЩИЙ элемент, заранее красим его в активный
            if len(queue_list.controls) > 1:
                next_item = queue_list.controls[1]
                next_container = next_item.content.content
                # next_container.border = ft.Border.all(2, ft.Colors.GREEN)
                # next_container.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGH
                try:
                    row_controls = next_container.content.controls
                    column_control = row_controls[-1] 
                    title_text = column_control.controls[0] 
                    if idx == 1:
                        title_text.color = ft.Colors.GREEN
                except Exception:
                    pass
            # Запускаем анимацию на фронтенде
            page.update()
            time.sleep(0.45)
        rebuild_callback()

    queue_panel = ft.Container(
        content=ft.Column([
            ft.Text("Очередь воспроизведения", size=20, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            queue_list
        ]),
        expand=True,
        padding=10,
        border_radius=RBOX_b_radius,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
    )
    skip_track_with_animation(page, queue_list, rebuild_queue_ui, 0)

    # ListView с простым режимом прокрутки
    path_row = ft.Row(
        controls=[path_text], # path_text остается твоим Text со spans
        #alignment=ft.MainAxisAlignment.END, # ПРИЖИМАЕМ К ПРАВОМУ КРАЮ
        scroll=ft.ScrollMode.HIDDEN,
        spacing=0,
        wrap=False
    )

    def handle_pick_folder(e):
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True) 

        directory_path = filedialog.askdirectory(title="Выберите папку с музыкой")
        root.destroy()

        if directory_path:
            ui_utils.on_dialog_result(directory_path, rebuild_explorer)

    address_bar = ft.Container(
        content=path_row,
        height=30,
        border=ft.Border.all(1, ft.Colors.with_opacity(adress_barBorderOp, adress_barBorderCol)),
        border_radius=8,
        padding=5,
        bgcolor=ft.Colors.with_opacity(adress_barBGOp, adress_barBGCol), # цвет SURFACE_CONTAINER_HIGHEST
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )

    search_bar = ft.Container(
        #content = ,
        height=35,
        border=ft.Border.all(1, ft.Colors.with_opacity(search_barBorderOp, search_barBorderCol)),
        border_radius=search_bar_radius,
        padding=5,
        bgcolor=ft.Colors.with_opacity(search_barBGOp, search_barBGCol), # цвет SURFACE_CONTAINER_HIGHEST
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )
    # Объявления объектов -----

    track_title = ft.Text(tags["Название"] if tags["Название"] else Path(p).name, size=text_size + 2, color="white", font_family="Arial", overflow=ft.TextOverflow.ELLIPSIS,)
    track_artist = ft.Text(tags["Автор"] if tags["Автор"] else "Исполнитель", size=text_size, color="gray", font_family="Arial", overflow=ft.TextOverflow.ELLIPSIS,)
    track_album = ft.Text(tags["Альбом"] if tags["Альбом"] else "Альбом", size=text_size, color="gray", font_family="Arial", overflow=ft.TextOverflow.ELLIPSIS,)
    track_year = ft.Text(tags["Год"] if tags["Год"] else "Год", size=text_size, color="gray", font_family="Arial", overflow=ft.TextOverflow.ELLIPSIS,)

    start_time_label = ft.Text("00:00", size=text_size, color="white", font_family="Arial")
    end_time_label = ft.Text("00:00", size=text_size, color="white", font_family="Arial")
    
    main_slider = ft.Slider( 
        #expand=3,
        thumb_color=ft.Colors.INDIGO_800,
        min=0, 
        max=100,
        value=0, 
        on_change=lambda e: ui_utils.slider_on_dragging(e,start_time_label),   
        on_change_end=lambda e: ui_utils.slider_event(e, start_time_label),
    )

    vol_label = ft.Text(str(start_vol_val), size=text_size, color="white", font_family="Arial")

    track_cover = ft.Image(
        src="https://flet.dev/img/logo.svg",
        width=150,
        height=150,
        border_radius=ft.BorderRadius.all(radius),
    )

    def rebuild_playlists():
        con_app = sqlite3.connect('app.db')
        cursor = con_app.cursor()

        try:
            cursor.execute("SELECT name, cover_path FROM playlists")        
            results = cursor.fetchall()
            
            names = []
            covers = []        
            for row in results:
                names.append(row[0])
                covers.append(row[1])
            return names, covers
        
        except sqlite3.OperationalError as e:
            print(f"Ошибка БД: app #01")
            return []
        finally:
            con_app.close()

    playlist_names, playlist_images = rebuild_playlists()

    rebuild_explorer(folder_items, p)
    # UI ------------------------
    page.add(
        ft.Container( #задний фон
            expand=True, 
            image=ft.DecorationImage( #фоновая картинка
                # src="assets/textures/BG.jpg",
                fit="cover"
            ),

            content = ft.SafeArea(
                expand=True,
                content=ft.Column(
                    spacing=10,
                    expand=True,
                    controls=[
                        # UBOX
                        ft.Row(
                            controls=[
                                ft.Container(
                                height=50,
                                bgcolor=ft.Colors.RED,
                                border_radius=UBOX_b_radius,
                                padding=5,
                                expand=1,
                                content=ft.Row(
                                    controls=[
                                        ft.Button(content="button1"),
                                        ft.Button(content="button2"),
                                        ft.Button(content="button3"),
                                        ft.Button(content="button4", disabled=True),
                                        ]
                                    )
                                )
                            ]
                        ),
                        # CRBOXES---
                        ft.Row(
                            spacing=10,
                            expand=True,
                            controls=[
                                ft.Container( # LBOX (Левая панель / Проводник)
                                    border_radius=LBOX_b_radius, 
                                    padding=5,
                                    expand=2,

                                    image=ft.DecorationImage( #тема - картинка
                                        src="assets/textures/LBOX.jpg",  # Путь к картинке (локальный или URL)
                                        fit="cover",                     # Растянуть, чтобы заполнить весь контейнер
                                        opacity=0.8                      # Можно настроить прозрачность самой текстуры
                                    ),

                                    content=ft.Column(
                                        spacing=5,
                                        controls=[
                                            ft.Row( # Полоска пути
                                                spacing=3,
                                                controls=[
                                                    ft.Container( # Индикатор пути
                                                        height=33,
                                                        content = address_bar,
                                                        expand=True
                                                    ),
                                                    ft.IconButton( # кнопка выбора папки
                                                        height=33,
                                                        icon=ft.Icon(
                                                            ft.Icons.FOLDER_ROUNDED,
                                                            offset=ft.Offset(0, -0.15),
                                                            color=adress_ButtonIconCol,
                                                        ),                                                        
                                                        style=ft.ButtonStyle(
                                                            bgcolor=adress_ButtonBGCol,
                                                            side=ft.BorderSide(adress_Button_BTol, adress_Button_BCol),
                                                            shape=ft.RoundedRectangleBorder(radius=adress_Button_Radius)
                                                        ),
                                                        on_click = handle_pick_folder
                                                    )
                                                ]
                                            ),
                                            search_bar, # Поиск
                                            explorer_tree  # динамический проводник
                                        ]
                                    )
                                ),               
                                ft.Container( #CBOX
                                    border_radius=CBOX_b_radius, 
                                    padding=5, 
                                    expand=5,

                                    #Стеклянный эффект
                                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE), # Полупрозрачный белый
                                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), # Тонкая рамка
                                    blur=ft.Blur(sigma_x=1.5, sigma_y=1.5, tile_mode=ft.BlurTileMode.CLAMP), # Размытие заднего плана

                                    content=ft.Column(
                                        spacing = 5,
                                        controls=[
                                            ft.Container( # Верхняя строка - название плейлиста, картинка и кнопка play
                                                # expand=3,
                                                height=100,
                                                bgcolor=ft.Colors.RED_800,
                                                content=ft.Row(
                                                    #expand=True,
                                                    #spacing=10,
                                                    controls=[
                                                        ft.Container(
                                                            height=100,
                                                            width=100,
                                                            bgcolor=ft.Colors.BLACK
                                                        ),
                                                        ft.Column(
                                                            expand=4,
                                                            spacing=3,
                                                            controls=[
                                                                ft.Container(
                                                                    bgcolor=ft.Colors.RED_900,
                                                                    content=ft.Text("Название плейлиста", size=text_size + 4, weight=ft.FontWeight.BOLD, color="white", font_family="Arial", overflow=ft.TextOverflow.ELLIPSIS,)
                                                                ),
                                                                ft.Container(
                                                                    bgcolor=ft.Colors.RED_900,
                                                                    content=ft.Text("Текст", size=text_size - 2, weight=ft.FontWeight.BOLD, color="white", font_family="Arial", overflow=ft.TextOverflow.ELLIPSIS,),
                                                                )
                                                            ]
                                                        ),
                                                        ft.Container( #кнопка play
                                                            expand=1,
                                                            content = ft.Image(
                                                                src="assets/icons/play_ico_inac.png",
                                                                width=30,
                                                                height=30,
                                                                fit="contain",
                                                            ),
                                                            alignment=ft.Alignment.BOTTOM_RIGHT,
                                                            shape = ft.BoxShape.CIRCLE,
                                                            animate=200,
                                                            scale=1.0,  # Изначальный размер (100%)
                                                            animate_scale=ft.Animation(100, ft.AnimationCurve.EASE_OUT), # Анимация сжатия за 100мс

                                                            # on_hover=ui_utils.change_color,
                                                            # on_click = lambda e: ui_utils.playpause_btn_ev(e, play_btn),
                                                        ),
                                                    ]
                                                )
                                            ),
                                            ft.Container(
                                                height=50,
                                                bgcolor=ft.Colors.RED_900,
                                                content=ft.Row(
                                                    scroll=ft.ScrollMode.HIDDEN,
                                                    spacing=2,
                                                    controls=[
                                                        ft.Container(
                                                            content=ft.Image(
                                                                src=i,
                                                                width=50,
                                                                height=50,
                                                                fit="cover"
                                                            ),
                                                            on_click=lambda e, : print(f"Выбран альбом: {j}"),
                                                            # ink=True, # Включает анимацию нажатия
                                                            border_radius=5,
                                                        ) for i in playlist_images for j in playlist_names
                                                    ]
                                                )
                                            ),
                                            ft.Container( # рабочая зона
                                                expand=True,
                                                bgcolor=ft.Colors.RED_800,
                                            ),
                                        ]
                                    )
                                ),
                                
                                ft.Container( #RBOX
                                    #bgcolor=ft.Colors.RED_800, 
                                    border_radius=RBOX_b_radius, 
                                    padding=5, 
                                    expand=2,
                                    
                                    gradient=ft.LinearGradient( # Градиент
                                        begin=ft.Alignment(-1, -1),  # [-1, -1] левый верхний угол
                                        end=ft.Alignment(1, 1),      # [1, 1] правый нижний угол
                                        colors=["#DCDF25", "#7F18DF"]
                                    ),

                                    content = queue_panel
                                )
                            ]
                        ),
                        # DBOX
                        ft.Row(
                            controls=[
                                ft.Container(
                                height=150,
                                bgcolor=ft.Colors.RED, 
                                expand=1,
                                border_radius=DBOX_b_radius, 
                                content=ft.Row(
                                    spacing=10, # Расстояние между элементами внутри
                                    controls=[
                                        track_cover,
                                        ft.Container( # коробка со столбцом метаданных
                                            height=150,
                                            #width=300,
                                            bgcolor=ft.Colors.RED_800,
                                            expand=4, #1/4
                                            content=ft.Column( # Метаданные трека (Название -> Исполнитель -> Альбом -> Год)
                                                expand=True,
                                                spacing=15,
                                                alignment=ft.MainAxisAlignment.CENTER,
                                                controls=[
                                                    track_title,
                                                    track_artist,
                                                    track_album,
                                                    track_year,
                                                ]
                                            )
                                        ),
                                        ft.Container( # коробка start_time_label
                                            expand=1,
                                            height=150,
                                            width=80,
                                            bgcolor=ft.Colors.RED_800,
                                            content=ft.Row(
                                                alignment=ft.MainAxisAlignment.END,
                                                controls=[
                                                    start_time_label
                                                ]
                                            )
                                        ),
                                        ft.Container( # коробка главного столбца управления
                                            height=150,
                                            bgcolor=ft.Colors.RED_800, 
                                            expand=6, #2/4
                                            content=ft.Column( #главный столбец управления
                                                spacing=2,
                                                alignment=ft.MainAxisAlignment.CENTER,
                                                controls=[
                                                    ft.Container( # кнопки кправления
                                                        #expand=2,
                                                        bgcolor=ft.Colors.RED_900, 
                                                        alignment=ft.Alignment.BOTTOM_CENTER,
                                                        content=ft.Row(
                                                            alignment=ft.MainAxisAlignment.CENTER,
                                                            controls=[
                                                            ft.Button(content="<", on_click = lambda e: ui_utils.play_next_or_pred(e, False, play_btn)),

                                                            ft.Container( #play/pause
                                                                content = play_btn,
                                                                shape = ft.BoxShape.CIRCLE,
                                                                animate=200,
                                                                scale=1.0,  # Изначальный размер (100%)
                                                                animate_scale=ft.Animation(100, ft.AnimationCurve.EASE_OUT), # Анимация сжатия за 100мс

                                                                on_hover=ui_utils.change_color,
                                                                on_click = lambda e: ui_utils.playpause_btn_ev(e, play_btn),
                                                            ),
                                                            ft.Button(content=">", on_click = lambda e: ui_utils.play_next_or_pred(e, True, play_btn)),
                                                            ]
                                                        )
                                                    ),
                                                    main_slider
                                                ]
                                            )
                                        ),
                                        ft.Container( # коробка end_time_label
                                            expand=1,
                                            height=150,
                                            width=80,
                                            bgcolor=ft.Colors.RED_800,
                                            content=ft.Row( 
                                                alignment=ft.MainAxisAlignment.START,
                                                controls=[
                                                    end_time_label
                                                ]
                                            )
                                        ),
                                        ft.Container( # коробка заглушка2
                                            height=150,
                                            bgcolor=ft.Colors.RED_800, 
                                            expand=4, #1/4
                                            content=ft.Column(
                                                spacing=5,
                                                controls=[
                                                    ft.Container(
                                                        bgcolor=ft.Colors.RED_900, 
                                                        expand=4,
                                                    ),
                                                    ft.Container(
                                                        bgcolor=ft.Colors.RED_900, 
                                                        expand=3,
                                                        content=ft.Row(
                                                            spacing=0,
                                                            controls=[
                                                                ft.Container(
                                                                    padding=0,
                                                                    expand=6,
                                                                    content=ft.Slider(
                                                                        thumb_color=ft.Colors.INDIGO_800,
                                                                        min=0,
                                                                        max=100,
                                                                        value=start_vol_val,
                                                                        on_change_end=lambda e: ui_utils.vol_slider_event(e,vol_label)
                                                                    ),
                                                                ),
                                                                ft.Container(
                                                                    bgcolor=ft.Colors.RED_900,
                                                                    expand=1,
                                                                    content = vol_label
                                                                )
                                                            ]
                                                        )
                                                    ),
                                                    ft.Container(
                                                        bgcolor=ft.Colors.RED_900, 
                                                        expand=4,
                                                    )
                                                ]
                                            )
                                        ),
                                        ft.Container( # коробка заглушка3
                                            height=150,
                                            width=150,
                                            bgcolor=ft.Colors.RED_800,
                                            content=ft.Column(
                                                spacing=15,
                                                alignment=ft.MainAxisAlignment.CENTER,
                                                controls=[]
                                            )
                                        ),
                                    ]
                                )
                                )
                            ]
                        )
                    ]
                )
            )
        )
    )
    def on_tags_changed(topic, message):
        track_title.value = message.get("Название", "Неизвестно")
        track_artist.value = message.get("Автор", "Неизвестный исполнитель")
        track_album.value = message.get("Альбом", "")
        track_year.value = message.get("Год", "")
        idx = message.get("idx", 0)
        
        if message.get("cover", ""): track_cover.src = message.get("cover", "") 
        else: track_cover.src = "https://flet.dev/img/logo.svg"
        if idx == -2: #-2 для случая, когда трек загружается первым, чтобы не дергать анимацию
            rebuild_queue_ui()
        else:
            skip_track_with_animation(page, queue_list, rebuild_queue_ui, idx)

        page.update()

    def on_playback_update(topic, message):
        curr_s = message.get("curr_sec", 0)
        total_s = message.get("total_sec", 0)

        # Обновляем максимальное значение слайдера (длину трека), если оно изменилось
        if total_s > 0 and main_slider.max != total_s:
            main_slider.max = total_s

        # Обновляем текущее значение слайдера
        main_slider.value = curr_s

        # Форматируем секунды в mm:ss
        start_time_label.value = f"{curr_s // 60:02d}:{curr_s % 60:02d}"
        end_time_label.value = f"{total_s // 60:02d}:{total_s % 60:02d}"

        # Обновляем только эти 3 компонента, чтобы не перерисовывать весь UI
        main_slider.update()
        start_time_label.update()
        end_time_label.update()

    # Регистрация подписчиков по топикам
    page.pubsub.subscribe_topic("tags_update", on_tags_changed)
    page.pubsub.subscribe_topic("playback_update", on_playback_update)

    ui_utils.bg_ui_process(page, play_btn)


ft.app(target=App, assets_dir="assets")

#threading.Thread(target=ui_utils.update_ui, daemon=True).start()
#CupertinoSlidingSegmentedButton
