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

text_size = config.getint('UI Settings', 'text_size') # рекомендуемое значение 13
b_radius = config.getint('UI Settings', 'b_radius') #закругление ui c: 20
radius = config.getint('UI Settings', 'radius') # закругление картинки c: 8

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
                        data=item["path"], 
                        content=ft.ContextMenu( # ТЕПЕРЬ МЕНЮ ЕСТЬ И У ФАЙЛОВ!
                            secondary_items=[
                                ft.PopupMenuItem(content=ft.Text("Добавить в очередь"), on_click=lambda e, p=full_item_path: (
                                    ui_utils.add_queue(p), 
                                    rebuild_queue_ui()
                                )),
                                ft.PopupMenuItem(content=ft.Text("Вставить"), on_click=lambda _: print("Вставляем...")),
                                ft.PopupMenuItem(content=ft.Text("Удалить"), on_click=lambda _: print("Удаляем...")),
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
                on_click=lambda e, t_id=track_id: on_track_click(t_id)
            )

            # 2. Обработчик Drop (когда на этот элемент что-то бросают)
            # def on_accept(e, target_id=track_id):
            #     # Получаем перетаскиваемый объект по его src_id
            #     src_control = page.get_control(e.src_id)
            #     src_data = src_control.data 
                
            #     # Если data - это путь (строка), значит притащили из проводника
            #     if isinstance(src_data, str): 
            #         insert_into_queue_db(src_data, target_id)
                
            #     # Если data - это ID (число), значит двигаем внутри очереди
            #     elif isinstance(src_data, int): 
            #         reorder_queue_db(src_data, target_id)
                    
            #     # Перестраиваем UI после изменения БД
            #     rebuild_queue_ui(page, queue_container)

            # 3. Визуальный отклик при взаимодействии
            def on_will_accept(e):
                #e.control.content.content.border = ft.Border.all(2, ft.Colors.BLUE)
                e.control.update()

            def on_leave(e):
                # Возвращаем стандартную рамку
                # border_col = ft.Colors.GREEN if e.control.data == 0 else ft.Colors.TRANSPARENT
                # e.control.content.content.border = ft.Border.all(2, border_col)
                e.control.update()

            # 4. Собираем матрешку: Target (зона дропа) -> Draggable (можно тащить) -> Container (внешний вид)
            drag_item = ft.DragTarget(
                group="queue_drag", # ВАЖНО: Общая группа с проводником
                data=track_id, # Сохраняем target_id в данных таргета для on_leave
                #on_accept=on_accept,
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
            #ft.Text("Очередь воспроизведения", size=20, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            queue_list
        ]),
        expand=True,
        padding=10,
        border_radius=b_radius,
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
        expand=3,
        thumb_color=ft.Colors.INDIGO_800,
        min=0, 
        max=100,
        value=0, 
        on_change=lambda e: ui_utils.slider_on_dragging(e,start_time_label),   
        on_change_end=lambda e: ui_utils.slider_event(e, start_time_label),
    )

    track_cover = ft.Image(
    src="https://flet.dev/img/logo.svg",
    width=150,
    height=150,
    border_radius=ft.BorderRadius.all(radius),
    )

    rebuild_explorer(folder_items, p)
    # UI ------------------------
    page.add(
        ft.Container( #задний фон
            expand=True, 
            image=ft.DecorationImage( #фоновая картинка
                #src="assets/textures/BG.jpg",
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
                                height=100,
                                bgcolor=ft.Colors.RED,
                                border_radius=b_radius,
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
                                    border_radius=b_radius, 
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
                                    border_radius=b_radius, 
                                    padding=5, 
                                    expand=5,

                                    #Стеклянный эффект
                                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE), # Полупрозрачный белый
                                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), # Тонкая рамка
                                    blur=ft.Blur(sigma_x=1.5, sigma_y=1.5, tile_mode=ft.BlurTileMode.CLAMP), # Размытие заднего плана

                                    #content=ft.ElevatedButton(content=ft.Text("Нажми меня"), on_click=lambda e: print("Кнопка нажата!"))
                                ),
                                
                                ft.Container( #RBOX
                                    #bgcolor=ft.Colors.RED_800, 
                                    border_radius=b_radius, 
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
                                border_radius=b_radius, 
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
                                                        expand=2,
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
                                                spacing=15,
                                                alignment=ft.MainAxisAlignment.CENTER,
                                                controls=[
                                                    ft.Text("кнопки", size=text_size, color="white"),
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
