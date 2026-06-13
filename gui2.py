import flet as ft
import ui_utils
from pathlib import Path
from ui_utils import bg_ui_process
import os


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

# text_size=12 # рекомендуемое значение 13
# b_radius = 10 #закругление c: 20
# radius = 8 #закругление картинки c: 8

#Конфиги adress_bar ======
adress_barBGCol = config.get('UI adress_bar', 'adress_barBGCol') # Цвет фона строки
adress_barBGOp = config.getfloat('UI adress_bar','adress_barBGOp') # Прозрачность фона строки
adress_barBorderCol = config.get('UI adress_bar','adress_barBorderCol') # Цвет рамки (обводки) строки
adress_barBorderOp = config.getfloat('UI adress_bar','adress_barBorderOp') # Прозрачность рамки строки
adress_ButtonIconCol = config.get('UI adress_bar','adress_ButtonIconCol') # Цвет иконки кнопки выбора файла справа от строки
adress_ButtonBGCol = config.get('UI adress_bar','adress_ButtonBGCol') # Цвет фона кнопки выбора файла справа от строки
adress_Button_BCol = config.get('UI adress_bar','adress_Button_BCol') # Цвет рамки (обводки) кнопки выбора файла справа от строки
adress_Button_BTol = config.getfloat('UI adress_bar','adress_Button_BTol') # Толщина рамки (обводки) кнопки выбора файла справа от строки
adress_Button_Radius = config.getfloat('UI adress_bar','adress_Button_Radius') # Сила скругления углов кнопки выбора файла справа от строки
# ========================

#--

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
                                ft.PopupMenuItem(content=ft.Text("Добавить в очередь"), on_click=lambda e, p=full_item_path: ui_utils.add_queue(p)),
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
                                            ft.Container( # Поиск
                                                bgcolor=ft.Colors.BLACK,
                                                height=40,
                                                #content = ,
                                            ),
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

                                    #content = ft.
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
        
        if message.get("cover", ""): track_cover.src = message.get("cover", "") 
        else: track_cover.src = "https://flet.dev/img/logo.svg"

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
