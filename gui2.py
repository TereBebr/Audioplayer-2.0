import flet as ft
import asyncio
import functools
import ui_utils
from pathlib import Path
from ui_utils import bg_ui_process
import os
import sqlite3
import time
tags = {"Название": "Выберите трек", "Автор": "", "Альбом": "", "Год": "", "Жанр": "",}
p = './music' #начальная папка
folder_items = ui_utils.fnew_path(p) #обработчик для начальной папки

import logging

logger = logging.getLogger(__name__)
#uicolor = ui_utils.rgba(255, 227, 185, 32) #argb по стандарту (255, 227, 185, 32) 
#bgcolor

import configparser
config = configparser.ConfigParser()
config.read('config.txt', encoding='utf-8')
# Конфиги =========
start_vol_val = config.getint('Main Settings', 'start_vol_val')
max_histlen = (config.getint('Main Settings', 'max_histlen') * -1) # Максимальная длина истории проигранных треков
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
# (размер обложки, размер названия, размер автора, расстояние между ними, отступы внутри ячейки, высота ячейки)
queue_border_radius = config.getint('UI queue_bar','queue_border_radius')
method_queue_settings = config.getint('UI queue_bar','method_queue_settings')
match method_queue_settings:
    case 0: 
        k_queue = config.getfloat('UI queue_bar','k_queue')
        queue_cell = ((46 * k_queue + 8.2), (12 * k_queue + 5.4), (12 * k_queue + 2.4), (4 * k_queue - 1.2), (15 * k_queue - 4), (76 * k_queue + 4.2))
    case 1:
        queue_cell_preset = config.getint('UI queue_bar','queue_cell_preset')
        match queue_cell_preset:
            case 0:
                queue_cell = (22, 9, 6, 0, 0.5, 27)
            case 1:
                queue_cell = (28, 11, 8, 0, 1, 33)
            case 2:
                queue_cell = (35, 13, 10, 2, 3, 48)
            case 3:
                queue_cell = (45, 15, 12, 2, 8, 60)
    case 2:
        queue_cell1 = config.getfloat('UI queue_bar','queue_cell1')
        queue_cell2 = config.getfloat('UI queue_bar','queue_cell2')
        queue_cell3 = config.getfloat('UI queue_bar','queue_cell3')
        queue_cell4 = config.getfloat('UI queue_bar','queue_cell4')
        queue_cell5 = config.getfloat('UI queue_bar','queue_cell5')
        queue_cell6 = config.getfloat('UI queue_bar','queue_cell6')
        queue_cell = []
        queue_cell.append(queue_cell1)
        queue_cell.append(queue_cell2)
        queue_cell.append(queue_cell3)
        queue_cell.append(queue_cell4)
        queue_cell.append(queue_cell5)
        queue_cell.append(queue_cell6)

track_border_radius = config.getint('UI track_bar','track_border_radius')
method_tracks_settings = config.getint('UI track_bar','method_tracks_settings')
match method_tracks_settings:
    case 0: 
        k_track = config.getfloat('UI track_bar','k_track')
        track_cell = ((46 * k_track + 8.2), (12 * k_track + 5.4), (12 * k_track + 2.4), (4 * k_track - 1.2), (15 * k_track - 4), (76 * k_track + 4.2))
    case 1:
        track_cell_preset = config.getint('UI track_bar','track_cell_preset')
        match track_cell_preset:
            case 0:
                track_cell = (22, 9, 6, 0, 0.5, 27)
            case 1:
                track_cell = (28, 11, 8, 0, 1, 33)
            case 2:
                track_cell = (35, 13, 10, 2, 3, 48)
            case 3:
                track_cell = (45, 15, 12, 2, 8, 60)
    case 2:
        track_cell1 = config.getfloat('UI track_bar','track_cell1')
        track_cell2 = config.getfloat('UI track_bar','track_cell2')
        track_cell3 = config.getfloat('UI track_bar','track_cell3')
        track_cell4 = config.getfloat('UI track_bar','track_cell4')
        track_cell5 = config.getfloat('UI track_bar','track_cell5')
        track_cell6 = config.getfloat('UI track_bar','track_cell6')
        track_cell = []
        track_cell.append(track_cell1)
        track_cell.append(track_cell2)
        track_cell.append(track_cell3)
        track_cell.append(track_cell4)
        track_cell.append(track_cell5)
        track_cell.append(track_cell6)

# k_queue = 0.7
# queue_cell = ((46 * k_queue + 8.2), (12 * k_queue + 5.4), (12 * k_queue + 2.4), (4 * k_queue - 1.2), (15 * k_queue - 4), (76 * k_queue + 4.2))
# k_tracks = 0.6
# playlist_tracks_cell = ((46 * k_playlist_tracks + 8.2), (12 * k_playlist_tracks + 5.4), (12 * k_playlist_tracks + 2.4), (4 * k_playlist_tracks - 1.2), (15 * k_playlist_tracks - 4), (76 * k_playlist_tracks + 4.2))


# ============================

playlist_id = 2


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

    async def on_files_dropped(path, insert_at):
        # path = e.path
        await asyncio.to_thread(ui_utils.add_queue, path, insert_at)
        rebuild_queue_ui()
    async def _on_add_to_queue_click(p, i, e=None):
        await on_files_dropped(p, insert_at=i)

    def show_albums_dialog(e, track_path):
        selected_albums = set()
        page = e.page

        # Обработчик изменения чекбокса
        def checkbox_changed(e, album_id):
            if e.control.value:
                selected_albums.add(album_id)
            else:
                selected_albums.discard(album_id)

        def close_dialog(e):
            dlg.open = False
            page.update()

        def save_selection(e):
            for alb in selected_albums:
                ui_utils.add_track_to_playlist(track_path, alb)
            logger.debug(f"Трек {track_path} добавлен в альбомы: {selected_albums}")
            close_dialog(e)
            playlist_ui(page, playlist_list, play_btn, alb)

        def get_playlists(e):
            con_app = sqlite3.connect('app.db')
            cursor = con_app.cursor()
            albums = []

            try:
                cursor.execute("SELECT id, name, cover_path FROM playlists")
                results = cursor.fetchall()
            
                for playlist_id, name, cover_path in results:
                    if playlist_id != 1:
                        a = {"id": playlist_id, "name": name, "img": cover_path}
                        albums.append(a)
                    
            except Exception as er:
                logger.error(f"Ошибка извлечения списка плейлистов {er}")
                close_dialog(e)
            finally:
                con_app.close()

            return albums

        # Сборка
        album_controls = []
        albums = get_playlists(e)
        for album in albums:
            fallback_cover = ft.Container(
                content=ft.Icon(ft.Icons.ALBUM, color=ft.Colors.WHITE, size=24),
                width=40,
                height=40,
                bgcolor=ft.Colors.BLUE_GREY_700,
                border_radius=5,
            )
            album_controls.append(
                ft.Row(
                    controls=[
                        fallback_cover,
                        ft.Text(album["name"], expand=True),
                        ft.Checkbox(
                            value=False, 
                            on_change=lambda e, a_id=album["id"]: checkbox_changed(e, a_id)
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                )
            )

        # Создаем диалог
        dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.LIBRARY_MUSIC),
                ft.Text("Выберите альбомы")
            ]),
            content=ft.Container(
                width=200,
                height=250,
                content=ft.Column(
                    controls=album_controls,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                )
            ),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(e)),
                ft.ElevatedButton("Сохранить", on_click=save_selection, bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def create_albums_dialog(page: ft.Page):
            def close_dialog(e):
                dlg.open = False
                page.update()

            def save_selection(e):
                playlist_name = name_input.value.strip() if name_input.value else ""
                cover_path = cover_input.value.strip() if cover_input.value else None
                if not playlist_name:
                    name_input.error_text = "Введите название"
                    page.update()
                    return
                create_playlist_sql(playlist_name, cover_path)
                update_albums_ui()
                logger.info(f"Альбом {playlist_name} успешно создан")
                close_dialog(e)

            def create_playlist_sql(playlist_name: str, cover_path=None):
                if cover_path is None:
                    cover_path = "storage/playlists_covers/default.png"
                con_app = sqlite3.connect('app.db')
                cursor = con_app.cursor()
                try:
                    cursor.execute("INSERT OR IGNORE INTO playlists (name, cover_path) VALUES (?, ?)",
                                (playlist_name, cover_path))
                    con_app.commit()
                except Exception as er:
                        con_app.rollback()
                        logger.error(f"Ошибка создания плейлиста: {er}")
                finally:
                    con_app.close()
                pass

            name_input = ft.TextField(label="Название плейлиста", expand=True)
            cover_input = ft.TextField(label="Путь к картинке (опционально)", expand=True)
            
            # Создаем диалог
            dlg = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.LIBRARY_MUSIC),
                    ft.Text("Создание альбома")
                ]),
                content=ft.Container(
                    width=250,
                    height=150,
                    content=ft.Column([
                        name_input, 
                        cover_input
                    ], spacing=10),
                ),
                actions=[
                    ft.TextButton("Отмена", on_click=lambda e: close_dialog(e)),
                    ft.ElevatedButton("Сохранить", on_click=save_selection, bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE)
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            page.overlay.append(dlg)
            dlg.open = True
            page.update()

    # Динамический проводник
    def rebuild_explorer(items, current_dir, is_search=False):
        if not is_search:
            explorer_tree.all_items = items
            explorer_tree.current_dir = current_dir
            # Очищаем поле поиска при переходе в новую папку
            if search_input.value != "":
                search_input.value = ""
                search_input.update()

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
        start_dir = Path(current_dir).resolve()
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

        if not items: # Если папка пустая или поиск ничего не нашел
            empty_text = "Ничего не найдено" if is_search else "Папка пуста"
            explorer_tree.controls.append(
                ft.Container(
                    content=ft.Text(empty_text, size=12, color="gray", italic=True),
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
                                ft.PopupMenuItem(content=ft.Text("Добавить в очередь"), on_click=functools.partial(_on_add_to_queue_click, full_item_path, None),),
                                ft.PopupMenuItem(content=ft.Text("Добавить в избранное"), on_click=lambda e, p=full_item_path: (
                                    ui_utils.add_track_to_playlist(p, 2),
                                    playlist_ui(page, playlist_list, play_btn, 2)
                                )),
                                ft.PopupMenuItem(content=ft.Text("Добавить в альбом"), on_click=lambda e, p=full_item_path: show_albums_dialog(e, p)),
                                ft.PopupMenuItem(content=ft.Text("Расположение файла"), on_click=lambda e, p=full_item_path: ui_utils.open_file_folder(e, p)),
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

    queue_list = ft.ListView(
        spacing=8,
        scroll=ft.ScrollMode.AUTO, 
        expand=True,
        # alignment=ft.MainAxisAlignment.START
    )

    def remove_played_tracks_ui(count):
        """Убирает первые `count` треков из UI без полного ребилда."""
        for _ in range(min(count, len(queue_list.controls))):
            queue_list.controls.pop(0)

        if queue_list.controls:
            new_first = queue_list.controls[0]
            container = new_first.content.content  # DragTarget -> Draggable -> Container
            container.border = ft.Border.all(2, ft.Colors.GREEN)
            container.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGH
            try:
                row_controls = container.content.controls
                column_control = row_controls[-1]
                title_text = column_control.controls[0]
                title_text.color = ft.Colors.GREEN
            except Exception:
                pass

        queue_list.update()
    
    def rebuild_queue_ui(idx=None):
        t0 = time.perf_counter()
        queue_list.controls.clear()
        def on_track_click(clicked_uid):
            con = sqlite3.connect('queue.db')
            cursor = con.cursor()
            path = None
            clicked_pos = None
            try:
                cursor.execute("SELECT id FROM queue WHERE uid = ?", (clicked_uid,))
                row = cursor.fetchone()
                if row is None:
                    return
                clicked_pos = row[0]
                if clicked_pos <= 0:
                    return

                cursor.execute("UPDATE queue SET id = id - ?", (clicked_pos,))
                cursor.execute("DELETE FROM queue WHERE id < ?", (max_histlen,))
                cursor.execute("SELECT path FROM queue WHERE id = 0")
                r = cursor.fetchone()
                path = r[0] if r else None
                con.commit()
            except Exception as ex:
                logger.error(f"Ошибка при обновлении очереди в БД: {ex}")
                con.rollback()
                return  # <-- явный выход при ошибке, ничего дальше не трогаем
            finally:
                con.close()

            if path is None:
                return
            ui_utils.load_track(page, path, play_btn, clicked_pos)
            # remove_played_tracks_ui(clicked_pos)

        con = sqlite3.connect('queue.db')
        cursor = con.cursor()
        # Сортируем строго по ID, чтобы 0 (играющий сейчас) был всегда наверху
        cursor.execute("SELECT id, uid, name, author, path, cov_bytes FROM queue WHERE id >= 0 ORDER BY id ASC")
        rows = cursor.fetchall()
        con.close()

        anim_config = ft.Animation(350, ft.AnimationCurve.EASE_OUT)
        for row in rows:
            track_id, track_uid, name, author, path, cov_bytes = row
            
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
                content=ft.ContextMenu(
                    content=ft.Row([
                        cover_img,
                        ft.Column([
                            ft.Text(name, size=queue_cell[1], weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN if is_playing else ft.Colors.ON_SURFACE),
                            ft.Text(author, size=queue_cell[2], color=ft.Colors.ON_SURFACE_VARIANT)
                        ], spacing=queue_cell[3])
                    ]),
                    secondary_items=[
                        ft.PopupMenuItem(content=ft.Text("Дублировать"), on_click=lambda e, uid=track_uid: (
                                ui_utils.dublicate_queue_track(uid),
                                rebuild_queue_ui(),
                            ),
                        ),
                        ft.PopupMenuItem(content=ft.Text("Добавить в избранное"), on_click=lambda e, p=path: (
                                ui_utils.add_track_to_playlist(p, 2),
                                playlist_ui(page, playlist_list, play_btn, 2)
                            ),
                        ),
                        ft.PopupMenuItem(content=ft.Text("Добавить в альбом"), on_click=lambda e, p=path: show_albums_dialog(e, p)),
                        ft.PopupMenuItem(content=ft.Text("Удалить из очереди"), on_click=lambda e, uid=track_uid: (
                            ui_utils.delete_track_from_queue(e, uid, play_btn),
                            rebuild_queue_ui(),
                        ),
                    ),
                    ft.PopupMenuItem(content=ft.Text("Расположение файла"), on_click=lambda e, p=path: ui_utils.open_file_folder(e, p)),
                    ft.PopupMenuItem(content=ft.Text("Открыть в файловой панели"), on_click=lambda e, p=path: ui_utils.open_file_in_player_explorer(e, p, rebuild_explorer)),
                    ]
                ),
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
                data=track_uid,
                on_click=lambda e: on_track_click(e.control.data)
            )

            # 2. Обработчик Drop (когда на этот элемент что-то бросают)
            async def on_accept(e):
                src_control = page.get_control(e.src_id) # Элемент, который тащим
                if src_control is None:
                    return
                
                src_data = src_control.data      # Это ID (int), путь (str) или словарь (dict)
                target_uid = e.control.data       # теперь uid, не позиция
                
                # ==========================================
                # ВЕТКА 1: Бросили файл/папку (СТРОКА)
                # ==========================================
                if isinstance(src_data, str):
                    con_q = sqlite3.connect('queue.db')
                    cur = con_q.cursor()
                    cur.execute("SELECT id FROM queue WHERE uid = ?", (target_uid,))
                    row = cur.fetchone()
                    con_q.close()
                    if row is None:
                        return
                    target_pos = row[0]

                    await on_files_dropped(src_data, insert_at=target_pos)

                    if target_pos == 0:
                        con_q = sqlite3.connect('queue.db')
                        cur = con_q.cursor()
                        cur.execute("SELECT path FROM queue WHERE id = 0")
                        new_track = cur.fetchone()
                        con_q.close()
                        if new_track:
                            ui_utils.load_track(page, new_track[0], play_btn, 0)
                    return

                # ==========================================
                # ВЕТКА 2: трек из плейлиста
                # ==========================================
                if isinstance(src_data, dict) and src_data.get("source") == "playlist":
                    name, author, path, cov_bytes = src_data["track_data"]

                    con_q = sqlite3.connect('queue.db')
                    cur = con_q.cursor()
                    try:
                        cur.execute("SELECT id FROM queue WHERE uid = ?", (target_uid,))
                        row = cur.fetchone()
                        if row is None:
                            con_q.close()
                            return
                        target_pos = row[0]

                        cur.execute("UPDATE queue SET id = id + 1 WHERE id >= ?", (target_pos,))
                        cur.execute("""
                            INSERT INTO queue (id, name, author, path, cov_bytes)
                            VALUES (?, ?, ?, ?, ?)
                        """, (target_pos, name, author, path, cov_bytes))
                        con_q.commit()

                        if target_pos == 0:
                            ui_utils.load_track(page, path, play_btn, 0)
                    except Exception as ex:
                        logger.error(f"Ошибка при вставке из плейлиста в очередь: {ex}")
                        con_q.rollback()
                    finally:
                        con_q.close()

                    rebuild_queue_ui()
                    return

                # ==========================================
                # ВЕТКА 3: реордер внутри очереди
                # ==========================================
                src_uid = src_data
                if src_uid == target_uid:
                    return

                con_queue = sqlite3.connect('queue.db')
                cursor = con_queue.cursor()
                try:
                    cursor.execute("SELECT uid, id FROM queue WHERE uid IN (?, ?)", (src_uid, target_uid))
                    pos_by_uid = dict(cursor.fetchall())
                    if src_uid not in pos_by_uid or target_uid not in pos_by_uid:
                        return  # один из треков уже пропал (например, был скипнут за это время)

                    src_pos = pos_by_uid[src_uid]
                    target_pos = pos_by_uid[target_uid]

                    if target_pos == 0:
                        cursor.execute("UPDATE queue SET id = -999 WHERE id = ?", (src_pos,))
                        cursor.execute("UPDATE queue SET id = id + 1 WHERE id >= 0 AND id < ?", (src_pos,))
                        cursor.execute("UPDATE queue SET id = 0 WHERE id = -999")
                    else:
                        cursor.execute("UPDATE queue SET id = -999 WHERE id = ?", (src_pos,))
                        cursor.execute("UPDATE queue SET id = ? WHERE id = ?", (src_pos, target_pos))
                        cursor.execute("UPDATE queue SET id = ? WHERE id = -999", (target_pos,))
                    con_queue.commit()

                    if src_pos == 0 or target_pos == 0:
                        cursor.execute("SELECT path FROM queue WHERE id = 0")
                        path_row = cursor.fetchone()
                        if path_row:
                            ui_utils.load_track(page, path_row[0], play_btn, 0)
                except Exception as ex:
                    logger.error(f"Ошибка БД при перетаскивании внутри очереди: {ex}")
                    con_queue.rollback()
                    return
                finally:
                    con_queue.close()

                # --- патчим UI по uid, не по позиции ---
                src_index = target_index = None
                for i, ctrl in enumerate(queue_list.controls):
                    if ctrl.data == src_uid:
                        src_index = i
                    elif ctrl.data == target_uid:
                        target_index = i

                if src_index is not None and target_index is not None:
                    if target_pos == 0:
                        moved = queue_list.controls.pop(src_index)
                        queue_list.controls.insert(0, moved)
                    else:
                        queue_list.controls[src_index], queue_list.controls[target_index] = \
                            queue_list.controls[target_index], queue_list.controls[src_index]
                    queue_list.update()

            # 3. Визуальный отклик при взаимодействии
            def on_will_accept(e):
                e.control.content.content.border = ft.Border.all(2, ft.Colors.BLUE_ACCENT)
                e.control.update()

            def on_leave(e):
                is_playing_now = bool(queue_list.controls) and queue_list.controls[0] is e.control
                border_col = ft.Colors.GREEN if is_playing_now else ft.Colors.TRANSPARENT
                e.control.content.content.border = ft.Border.all(2, border_col)
                e.control.update()

            # 4. Собираем матрешку: Target (зона дропа) -> Draggable (можно тащить) -> Container (внешний вид)
            drag_item = ft.DragTarget(
                group="queue_drag", # ВАЖНО: Общая группа с проводником
                data=track_uid, # Сохраняем target_id в данных таргета для on_leave
                on_accept=on_accept,
                on_will_accept=on_will_accept,
                on_leave=on_leave,
                content=ft.Draggable(
                    group="queue_drag",
                    data=track_uid, # Передаем ID при перетаскивании
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

        t1 = time.perf_counter()
        page.update()
        t2 = time.perf_counter()
        print(f"Построение контролов: {(t1-t0)*1000:.1f} мс, page.update(): {(t2-t1)*1000:.1f} мс")
    
    async def skip_track_with_animation(page, queue_list, remove_callback, idx):
        """
        Визуально уводит отыгравший трек влево и гасит его,
        плавно подсвечивает зелёным следующий трек,
        затем убирает элементы из UI.
        """
        if len(queue_list.controls) > 0:
            first_item = queue_list.controls[0]
            first_container = first_item.content.content

            first_container.opacity = 0
            first_container.offset = ft.Offset(-1, 0)
            first_container.border = ft.Border.all(0, ft.Colors.TRANSPARENT)

            if len(queue_list.controls) > 1:
                next_item = queue_list.controls[1]
                next_container = next_item.content.content
                try:
                    row_controls = next_container.content.controls
                    column_control = row_controls[-1]
                    title_text = column_control.controls[0]
                    if idx == 1:
                        title_text.color = ft.Colors.GREEN
                except Exception:
                    pass

            page.update()
            await asyncio.sleep(0.45)

        remove_callback(idx if idx else 1) #(idx if idx else 1)

    queue_panel = ft.Container(
        content=ft.Column(
            spacing=0,
            controls=[
            # ft.Text("Очередь воспроизведения", size=20, weight=ft.FontWeight.BOLD),
            ft.IconButton(
                height=40,
                icon=ft.Icon(ft.Icons.COMPARE_ARROWS,offset=ft.Offset(),color=adress_ButtonIconCol),
                on_click=lambda e: ui_utils.mix_queue(rebuild_queue_ui),
            ),
            ft.Divider(),
            queue_list
        ]),
        expand=True,
        padding=10,
        border_radius=RBOX_b_radius,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
    )
    page.run_task(skip_track_with_animation,page, queue_list, rebuild_queue_ui, 0)

    # ListView с простым режимом прокрутки
    path_row = ft.Row(
        controls=[path_text], # path_text остается твоим Text со spans
        #alignment=ft.MainAxisAlignment.END, # ПРИЖИМАЕМ К ПРАВОМУ КРАЮ
        scroll=ft.ScrollMode.HIDDEN,
        spacing=0,
        wrap=False
    )

    def handle_pick_folder(e): # изменить
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

    def perform_search(e):
        """Функция активного поиска"""
        query = e.control.value.lower().strip()

        all_items = getattr(explorer_tree, "all_items", [])
        current_dir = getattr(explorer_tree, "current_dir", "")
        
        if not query:
            # Если поиск пуст, показываем все элементы
            filtered_items = all_items
        else:
            filtered_items = [
                item for item in all_items 
                if query in item["name"].lower()
            ]
        rebuild_explorer(filtered_items, current_dir, is_search=bool(query))

    search_input = ft.TextField(
        hint_text="Поиск файлов...",
        border=ft.InputBorder.NONE,
        text_size=text_size,
        dense=True,
        content_padding=2,
        cursor_color="amber",
        on_change=perform_search # Вызов поиска при каждом изменении
    )

    search_bar = ft.Container(
        content=search_input,
        height=20,
        border=ft.Border.all(1, ft.Colors.with_opacity(search_barBorderOp, search_barBorderCol)),
        border_radius=search_bar_radius,
        padding=0, # Убрал padding, так как он есть внутри TextField
        bgcolor=ft.Colors.with_opacity(search_barBGOp, search_barBGCol),
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

    def rebuild_playlists_list():
        con_app = sqlite3.connect('app.db')
        cursor = con_app.cursor()

        try:
            cursor.execute("SELECT id, name, cover_path FROM playlists")
            results = cursor.fetchall()

            ids = []
            names = []
            covers = []
            for row in results:
                ids.append(row[0])
                names.append(row[1])
                covers.append(row[2])
            return ids, names, covers

        except sqlite3.OperationalError as e:
            logger.error(f"Ошибка БД: app #01")
            return [], [], []
        finally:
            con_app.close()
    playlist_ids, playlist_names, playlist_images = rebuild_playlists_list()

    playlist_list = ft.ListView(
        expand=True,
        spacing=5,
        padding=10,
        auto_scroll=False
    )

    def shift_playlist_track_db(playlist_id, old_pos, new_pos):
        """Меняет местами два трека в плейлисте (Swap)"""
        if old_pos == new_pos:
            return # Если бросили на то же самое место, ничего не делаем

        con = sqlite3.connect('app.db')
        cursor = con.cursor()
        try:
            # Шаг 1: Убираем перетаскиваемый трек во "временную" зону (-30)
            cursor.execute("""
                UPDATE playlist_tracks SET position = -30 
                WHERE playlist_id = ? AND position = ?
            """, (playlist_id, old_pos))

            # Шаг 2: Ставим трек, на который бросили, на старую позицию
            cursor.execute("""
                UPDATE playlist_tracks SET position = ? 
                WHERE playlist_id = ? AND position = ?
            """, (old_pos, playlist_id, new_pos))

            # Шаг 3: Ставим перетаскиваемый трек из временной зоны на новую позицию
            cursor.execute("""
                UPDATE playlist_tracks SET position = ? 
                WHERE playlist_id = ? AND position = -30
            """, (new_pos, playlist_id))

            con.commit()
        except Exception as e:
            logger.error(f"Ошибка при обмене позиций в плейлисте: {e}")
            con.rollback()
        finally:
            con.close()
    def playlist_ui(page: ft.Page, playlist_list: ft.ListView, play_btn_obj, playlist_id: int = 2):
        if playlist_id == 1:
            create_albums_dialog(page)
            con = sqlite3.connect("app.db")
            cursor = con.cursor()
            cursor.execute("SELECT id FROM playlists WHERE id = (SELECT MAX(id) FROM playlists)")
            r = cursor.fetchone()
            con.close()
            # print(r[0])
            playlist_ui(page, playlist_list, play_btn_obj, r[0])

        playlist_list.controls.clear()

        # --- 1. ЗАГРУЗКА ДАННЫХ ПЛЕЙЛИСТА ---
        con = sqlite3.connect('app.db')
        cursor = con.cursor()
        cursor.execute("""
            SELECT t.id, t.name, t.author, t.path, t.cov_bytes, pt.position
            FROM playlist_tracks pt 
            JOIN tracks t ON pt.track_id = t.id
            WHERE pt.playlist_id = ? 
            ORDER BY pt.position; 
        """, (playlist_id,))
        rows = cursor.fetchall()
        con.close()

        def on_track_double_click(e):
            t_id, t_name, t_author, t_path, t_cov = e.control.data 
            
            con_q = sqlite3.connect('queue.db')
            cursor = con_q.cursor()

            try:
                cursor.execute('DELETE FROM queue WHERE id = ?', (0,))
                cursor.execute("INSERT INTO queue (id, name, author, path, cov_bytes) VALUES (?, ?, ?, ?, ?)", 
                               (0, t_name if t_name else Path(t_path).name, t_author, str(t_path), t_cov))
            except Exception as ex:
                logger.error(f"Ошибка БД очереди: {ex}")
            finally:
                con_q.commit()
                con_q.close()
                
            ui_utils.load_track(e.page,t_path, play_btn_obj, 0)
            logger.debug(f"файл: {t_path}")
            rebuild_queue_ui()

        def on_accept(e):
            src_control = page.get_control(e.src_id)
            if src_control is None: return
            
            src_data = src_control.data      # Что тащим (словарь с данными)
            target_pos = e.control.data      # Куда бросаем (позиция)

            # Если тянем трек из этого же плейлиста
            if isinstance(src_data, dict) and src_data.get("source") == "playlist":
                src_pos = src_data["position"]
                if src_pos != target_pos:
                    # Вызываем вспомогательную функцию сдвига (написана ниже)
                    shift_playlist_track_db(playlist_id, src_pos, target_pos)
                    # Перерисовываем плейлист
                    playlist_ui(page, playlist_list, play_btn, playlist_id)
            
            # Сброс визуального выделения
            e.control.content.content.border = ft.Border.all(2, ft.Colors.TRANSPARENT)
            e.control.update()

        def on_will_accept(e):
            e.control.content.content.border = ft.Border.all(2, ft.Colors.BLUE_ACCENT)
            e.control.update()

        def on_leave(e):
            e.control.content.content.border = ft.Border.all(2, ft.Colors.TRANSPARENT)
            e.control.update()

        # --- 4. ОТРИСОВКА ИНТЕРФЕЙСА ---
        for row in rows:
            track_id, name, author, path, cov_bytes, position = row

            cover_img = ft.Icon(ft.Icons.MUSIC_NOTE, size=track_cell[0])
            if cov_bytes is not None:
                cover_img = ft.Image(src=cov_bytes, width=track_cell[0], height=track_cell[0])
            
            # Сам контент трека. Здесь вешаем on_double_click
            item_content = ft.Container(
                content=ft.Row([
                    cover_img,
                    ft.Column([
                        ft.Text(name, size=track_cell[1], weight=ft.FontWeight.BOLD),
                        ft.Text(author, size=track_cell[2], color=ft.Colors.ON_SURFACE_VARIANT)
                    ], spacing=track_cell[3])
                ]),
                padding=track_cell[4],
                border_radius=track_border_radius,
                border=ft.Border.all(2, ft.Colors.TRANSPARENT) # Невидимая рамка для on_will_accept
            )

            # Оборачиваем в GestureDetector для отслеживания двойного клика
            item_wrapper = ft.GestureDetector(
                on_double_tap=on_track_double_click,
                data=(track_id, name, author, path, cov_bytes),
                content=item_content
            )

            # Собираем Drag & Drop (Матрешка)
            drag_payload = {
                "source": "playlist", 
                "track_id": track_id, 
                "position": position,
                "track_data": (name, author, path, cov_bytes)
            }

            drag_item = ft.DragTarget(
                group="queue_drag", # ОБЩАЯ ГРУППА для плейлиста и очереди
                data=position,        # Таргет знает свою позицию
                on_accept=on_accept,
                on_will_accept=on_will_accept,
                on_leave=on_leave,
                content=ft.Draggable(
                    group="queue_drag",
                    data=drag_payload, # Передаем полный словарь, чтобы очередь поняла, что ей прилетело
                    content=ft.ContextMenu(
                        content=item_wrapper,
                        secondary_items=[
                            ft.PopupMenuItem(content=ft.Text("Добавить в очередь"), on_click=functools.partial(_on_add_to_queue_click, path, None),
                            ),
                            *([ft.PopupMenuItem(content=ft.Text("Добавить в избранное"), on_click=lambda e, p=path: (
                                ui_utils.add_track_to_playlist(p, 2),
                                playlist_ui(page, playlist_list, play_btn, 2),)),]
                                if playlist_id != 2
                                else []
                            ),
                            ft.PopupMenuItem(content=ft.Text("Добавить в альбом"), on_click=lambda e, p=path: show_albums_dialog(e, p)),
                            *([ft.PopupMenuItem(content=ft.Text("Удалить из избранного"), on_click=lambda e, id=track_id:(
                                ui_utils.delete_playlist_track(id, 2),
                                playlist_ui(page, playlist_list, play_btn, 2),)),]
                                if playlist_id == 2
                                else [
                                    ft.PopupMenuItem(content=ft.Text("Удалить из альбома")),
                                ]
                            ),
                            ft.PopupMenuItem(content=ft.Text("Расположение файла"), on_click=lambda e, p=path: ui_utils.open_file_folder(e, p)),
                            ft.PopupMenuItem(content=ft.Text("Открыть в файловой панели"), on_click=lambda e, p=path: ui_utils.open_file_in_player_explorer(e, p, rebuild_explorer)),
                        ]
                    ),
                    content_when_dragging=ft.Container(
                        content=ft.Text(f"Перемещение: {name}", size=track_cell[1]),
                        padding=track_cell[4],
                        bgcolor=ft.Colors.INVERSE_SURFACE,
                        border_radius=track_border_radius,
                        opacity=0.8
                    )
                )
            )
            playlist_list.controls.append(drag_item)
        logger.debug(f"Найдено строк в базе: {len(rows)}")
        logger.debug(f"Элементов в playlist_list.controls: {len(playlist_list.controls)}")
        playlist_list.update()

    page.update()

    rebuild_explorer(folder_items, p)

    albums_row = ft.Row(scroll=ft.ScrollMode.HIDDEN, spacing=2)
    def update_albums_ui():
        # Получаем свежие данные из БД
        p_ids, p_names, p_images = rebuild_playlists_list()
        
        # Очищаем старые элементы из строки
        albums_row.controls.clear()
        
        # Заполняем строку актуальными данными
        for p_id, name, img in zip(p_ids, p_names, p_images):
            albums_row.controls.append(
                ft.Container(
                    content=ft.Image(
                        src=img,
                        width=50,
                        height=50,
                        fit="cover"
                    ),
                    on_click=lambda e, p_id=p_id: playlist_ui(page, playlist_list, play_btn, p_id),
                    tooltip=name, 
                    border_radius=12,
                )
            )
        
        # Обновляем только саму строку (если она уже добавлена на страницу)
        # Если она еще не добавлена, игнорируем ошибку (или используем page.update())
        try:
            albums_row.update()
        except Exception:
            pass
    update_albums_ui()

    switch_playlists_WZ_view =ft.Container(
        bgcolor=ft.Colors.RED_900,
        expand=True,
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
                                        bgcolor=ft.Colors.RED_700,
                                        content=ft.Text("Название плейлиста", size=text_size + 4, weight=ft.FontWeight.BOLD, color="white", font_family="Arial", overflow=ft.TextOverflow.ELLIPSIS,)
                                    ),
                                    ft.Container(
                                        bgcolor=ft.Colors.RED_600,
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
                ft.Container( # строка с альбомами 
                    height=50,
                    bgcolor=ft.Colors.RED_900,
                    content=albums_row
                ),
                ft.Container( # рабочая зона
                        bgcolor=ft.Colors.RED_800,
                        content=playlist_list,
                        expand=True
                    ),
            ]
        )
    )
    switch_online_WZ_view = ft.Container()

    def on_change_WZ_view(e):
        switch_playlists_WZ_view.visible = (e.control.selected_index == 0)
        switch_online_WZ_view.visible = (e.control.selected_index == 1)
        # Обновляем оба контейнера (или их общего родителя)
        switch_playlists_WZ_view.update()
        switch_online_WZ_view.update()
    
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
                                    expand=5,

                                    #Стеклянный эффект
                                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE), # Полупрозрачный белый
                                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), # Тонкая рамка
                                    blur=ft.Blur(sigma_x=1.5, sigma_y=1.5, tile_mode=ft.BlurTileMode.CLAMP), # Размытие заднего плана

                                    content=ft.Column(
                                        spacing=0,
                                        controls=[
                                            ft.Container( # режимы - плейлиты/онлайн
                                                height=35,
                                                width=float('inf'),
                                                bgcolor=ft.Colors.RED_700,
                                                content=ft.CupertinoSlidingSegmentedButton(
                                                    selected_index=0,
                                                    expand=True,
                                                    proportional_width=True,
                                                    on_change= on_change_WZ_view,
                                                    controls=[
                                                        ft.Text("Свои плейлисты"),
                                                        ft.Text("Онлайн функции"),
                                                    ],
                                                )
                                            ),
                                            switch_playlists_WZ_view,
                                            switch_online_WZ_view,
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
    if playlist_ids:
        playlist_ui(page, playlist_list, play_btn, playlist_id=playlist_ids[1])
    else:
        playlist_ui(page, playlist_list, play_btn, playlist_id=2)

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
            page.run_task(skip_track_with_animation, page, queue_list, remove_played_tracks_ui, idx)
        # page.update()

    def on_playback_update(topic, message):
        curr_s = message.get("curr_sec", 0)
        total_s = message.get("total_sec", 0)

        # Обновляем максимальное значение слайдера (длину трека), если оно изменилось
        if total_s > 0 and main_slider.max != total_s:
            main_slider.max = total_s

        # Обновляем текущее значение слайдера
        main_slider.value = max(0.0, curr_s)
        main_slider.update()

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