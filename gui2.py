import flet as ft
import asyncio
import functools
import ui_utils
from pathlib import Path
from ui_utils import bg_ui_process
import os
import math
import sqlite3
from contextlib import closing
import time
tags = {"Название": "Выберите трек", "Автор": "", "Альбом": "", "Год": "", "Жанр": "",}

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
p = config.get('Main Settings', 'start_path', fallback='./music') # Начальная папка
folder_items = ui_utils.fnew_path(p) # Oбработчик для начальной папки
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
playlist_name = "Избранное"
playlist_desk = ""
playlist_cover_path = ""


class VirtualList:
    """Оконный ("виртуальный") рендер длинного списка в прокручиваемом ft.Column.

    В контейнере одновременно живут только ячейки видимой области плюс буфер
    сверху и снизу. Место остальных занимают две пустые распорки, поэтому
    и высота полосы прокрутки, и позиция скролла остаются ровно такими же,
    как если бы список был отрисован целиком.

    Смысл: Flet при каждом update() сериализует и отправляет во Flutter все
    контролы списка — вместе с байтами обложек. На 500 треках это ~1 с на
    перерисовку. Окно из ~30 ячеек делает стоимость перерисовки постоянной
    и не зависящей от длины очереди/плейлиста.

    Контейнер обязан быть ft.Column со scroll, а не ft.ListView: ListView
    выравнивает детей по общему item extent, из-за чего распорка на 27000px
    занимает столько же, сколько обычная ячейка, и max_scroll_extent врёт
    (проверено — ListView даёт 4332 там, где Column даёт честные 2862).

    Требование к ячейке: её высота — ровно cell_height, а вертикальный зазор
    задаётся нижним margin ячейки, а не spacing у контейнера (spacing
    принудительно ставится в 0). Тогда шаг строки всегда cell_height + gap,
    и арифметика распорок точная.

    count_rows()              -> сколько всего строк
    fetch_rows(offset, limit) -> строки окна (SQL с LIMIT/OFFSET)
    build_row(index, row)     -> контрол ячейки
    """

    # сколько строк рендерим, пока не знаем реальную высоту области
    ROWS_UNTIL_MEASURED = 25

    # На сколько строк видимая область должна подойти к краю окна, чтобы
    # запустить перерисовку. Без этого запаса окно пересчитывалось бы на
    # каждую прокрученную строку: сам по себе update() стоит ~70 мс почти
    # независимо от числа ячеек, так что экономить надо на числе update-ов,
    # а не на размере окна.
    EDGE_ROWS = 5

    def __init__(self, list_view, cell_height, gap, count_rows, fetch_rows, build_row,
                 buffer_rows=14, scroll_interval=100):
        assert isinstance(list_view, ft.Column), "VirtualList работает только с ft.Column (см. докстроку)"
        self.box = list_view
        self.pitch = cell_height + gap
        self.gap = gap
        self.count_rows = count_rows
        self.fetch_rows = fetch_rows
        self.build_row = build_row
        self.buffer = buffer_rows

        self.total = 0
        self.start = 0
        self.end = 0
        self._offset = 0.0
        self._viewport = 0.0

        self.box.spacing = 0
        self.box.scroll_interval = scroll_interval
        self.box.on_scroll = self._on_scroll
        self.box.on_size_change = self._on_resize

    # --- служебное -------------------------------------------------------

    def cell_margin(self):
        """Отступ, который ячейка обязана повесить на себя вместо spacing."""
        return ft.Margin.only(bottom=self.gap)

    def _spacer(self, rows):
        return ft.Container(height=rows * self.pitch)

    def _window_for(self, offset, viewport):
        if self.total <= 0:
            return 0, 0
        if viewport > 0:
            visible = math.ceil(viewport / self.pitch) + 1
        else:
            visible = self.ROWS_UNTIL_MEASURED
        start = max(0, int(offset // self.pitch) - self.buffer)
        end = min(self.total, start + visible + 2 * self.buffer)
        # у конца списка окно упирается в total — подтягиваем начало обратно,
        # иначе на последнем экране рендерится меньше строк, чем помещается
        start = max(0, min(start, end - (visible + 2 * self.buffer)))
        return start, end

    def _safe_update(self):
        try:
            if self.box.page:
                self.box.update()
        except (AssertionError, RuntimeError) as ex:
            logger.debug(f"VirtualList: update пропущен ({ex})")

    # --- публичное -------------------------------------------------------

    def render(self, update=True):
        """Перерисовывает текущее окно."""
        t0 = time.perf_counter()
        controls = []
        if self.start > 0:
            controls.append(self._spacer(self.start))

        if self.end > self.start:
            rows = self.fetch_rows(self.start, self.end - self.start)
            for i, row in enumerate(rows):
                controls.append(self.build_row(self.start + i, row))

        tail = self.total - self.end
        if tail > 0:
            controls.append(self._spacer(tail))

        self.box.controls[:] = controls
        if update:
            self._safe_update()
        logger.debug(f"VirtualList: окно {self.start}-{self.end} из {self.total}, "
                     f"область {self._viewport:.0f}px, {(time.perf_counter()-t0)*1000:.1f} мс")

    def refresh(self, to_top=False, update=True):
        """Перечитывает количество строк и перерисовывает окно.

        to_top=True — сбросить окно в начало (например, при смене плейлиста).
        """
        self.total = self.count_rows()
        if to_top:
            self._offset = 0.0
        # если список укоротился, текущая позиция могла оказаться за концом
        max_offset = max(0.0, self.total * self.pitch - self._viewport)
        self._offset = min(self._offset, max_offset)
        self.start, self.end = self._window_for(self._offset, self._viewport)
        self.render(update=update)

    def scrolled(self):
        """Список реально прокручен вниз (а не стоит в начале)."""
        return self._offset > 0

    def rendered_row(self, index):
        """Контрол строки index, если она сейчас в окне, иначе None."""
        if not (self.start <= index < self.end):
            return None
        pos = index - self.start + (1 if self.start > 0 else 0)
        if 0 <= pos < len(self.box.controls):
            return self.box.controls[pos]
        return None

    # --- события ---------------------------------------------------------

    def _window_is_stale(self):
        """Видимая область подошла к краю отрисованного окна?"""
        first = int(self._offset // self.pitch)
        last = int((self._offset + self._viewport) // self.pitch)
        # сверху: окно можно расширить, только если выше есть неотрисованные строки
        if self.start > 0 and first - self.start < self.EDGE_ROWS:
            return True
        if self.end < self.total and self.end - last < self.EDGE_ROWS:
            return True
        return False

    def _reflow(self, force=False):
        if not force and not self._window_is_stale():
            return
        start, end = self._window_for(self._offset, self._viewport)
        if (start, end) != (self.start, self.end):
            self.start, self.end = start, end
            self.render()

    def _on_scroll(self, e):
        if e.pixels is None:
            return
        self._offset = max(0.0, e.pixels)
        if e.viewport_dimension:
            self._viewport = e.viewport_dimension
        self._reflow()

    def _on_resize(self, e):
        if not e.height or e.height == self._viewport:
            return
        self._viewport = e.height
        # размер области поменялся — окно пересчитываем безусловно
        self._reflow(force=True)


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

    def open_dialog(page, dlg):
        """Показывает диалог через штатный механизм Flet 0.85.

        Не через page.overlay: положенный в overlay диалог рисуется, но не
        попадает в стек диалогов страницы, и закрыть его потом нельзя —
        dlg.open = False на него уже не действует. show_dialog кладёт диалог
        в page._dialogs и сам убирает его оттуда после закрытия.
        """
        page.show_dialog(dlg)

    def close_dialog(page, dlg=None):
        """Закрывает верхний открытый диалог (он у нас всегда один)."""
        page.pop_dialog()

    def show_albums_dialog(e, track_path):
        selected_albums = set()
        page = e.page

        # Обработчик изменения чекбокса
        def checkbox_changed(e, album_id):
            if e.control.value:
                selected_albums.add(album_id)
            else:
                selected_albums.discard(album_id)

        def save_selection(e):
            close_dialog(page, dlg)  # сначала закрыть, потом перестраивать UI
            if not selected_albums:
                return
            for alb in selected_albums:
                ui_utils.add_track_to_playlist(track_path, alb)
            logger.debug(f"Трек {track_path} добавлен в альбомы: {selected_albums}")
            # если добавляли в открытый сейчас плейлист — обновляем рабочую зону
            if current_playlist["id"] in selected_albums:
                playlist_ui(page, playlist_list, play_btn, current_playlist["id"])

        def get_playlists():
            albums = []
            for pl_id, name, cover_path in ui_utils.db_query_all('app.db', "SELECT id, name, cover_path FROM playlists"):
                if pl_id != 1:
                    albums.append({"id": pl_id, "name": name, "img": cover_path})
            return albums

        # Сборка
        album_controls = []
        albums = get_playlists()
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
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(page, dlg)),
                ft.ElevatedButton("Сохранить", on_click=save_selection, bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        open_dialog(page, dlg)

    def create_albums_dialog(page: ft.Page):
            def save_selection(e):
                new_name = name_input.value.strip() if name_input.value else ""
                cover_path = cover_input.value.strip() if cover_input.value else None
                if not new_name:
                    name_input.error_text = "Введите название"
                    page.update()
                    return
                new_id = create_playlist_sql(new_name, cover_path)
                if new_id is None:
                    # name в playlists объявлен UNIQUE: раньше INSERT OR IGNORE
                    # молча ничего не делал, а в лог писалось "успешно создан"
                    name_input.error_text = "Плейлист с таким именем уже есть"
                    page.update()
                    return
                # Закрываем до перестройки списков: если оставить закрытие
                # напоследок, любая ошибка в update_albums_ui/playlist_ui
                # оставит диалог висеть на экране
                close_dialog(page, dlg)
                logger.info(f"Альбом {new_name} успешно создан (#{new_id})")
                update_albums_ui()
                open_new_playlist(new_id)

            def open_new_playlist(new_id):
                global playlist_name, playlist_desk, playlist_cover_path, playlist_id
                r = ui_utils.db_query_one('app.db', "SELECT id, name, desk, cover_path FROM playlists WHERE id = ?", (new_id,))
                if r:
                    playlist_id = r[0]
                    playlist_name = r[1]
                    playlist_desk = r[2]
                    playlist_cover_path = r[3]
                playlist_ui(page, playlist_list, play_btn, playlist_id)

            def create_playlist_sql(new_name: str, cover_path=None):
                """Создаёт плейлист. Возвращает его id или None, если имя занято."""
                if not cover_path:
                    cover_path = "storage/playlists_covers/default.png"
                try:
                    with closing(sqlite3.connect('app.db', timeout=10.0)) as con_app:
                        with con_app:
                            cur = con_app.execute("INSERT INTO playlists (name, cover_path) VALUES (?, ?)",
                                                  (new_name, cover_path))
                            return cur.lastrowid
                except sqlite3.IntegrityError:
                    logger.error(f"Плейлист с именем '{new_name}' уже существует")
                    return None
                except sqlite3.Error as er:
                    logger.error(f"Ошибка создания плейлиста: {er}")
                    return None

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
                    ft.TextButton("Отмена", on_click=lambda e: close_dialog(page, dlg)),
                    ft.ElevatedButton("Сохранить", on_click=save_selection, bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE)
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            open_dialog(page, dlg)

    def change_albums_dialog(page: ft.Page, pl_id, pl_name, pl_cover_path):
        def save_selection(e, p_id):
            new_name = name_input.value.strip() if name_input.value else ""
            # Пустое поле обложки означает "оставить как было", а не "сбросить
            # на default.png": раньше переименование затирало обложку плейлиста
            new_cover = cover_input.value.strip() if cover_input.value else ""
            if not new_name:
                name_input.error_text = "Введите название"
                page.update()
                return
            if not change_playlist_sql(p_id, new_name, new_cover or pl_cover_path):
                name_input.error_text = "Плейлист с таким именем уже есть"
                page.update()
                return
            close_dialog(page, dlg)  # сначала закрыть, потом перестраивать UI
            logger.info(f"Альбом {new_name} успешно изменен")
            update_albums_ui()

        def change_playlist_sql(id, new_name: str, cover_path=None):
            """Обновляет плейлист. False — имя занято или ошибка БД."""
            if not cover_path:
                cover_path = "storage/playlists_covers/default.png"
            try:
                with closing(sqlite3.connect('app.db', timeout=10.0)) as con_app:
                    with con_app:
                        con_app.execute("UPDATE playlists SET name = ?, cover_path = ? WHERE id = ?",
                                        (new_name, cover_path, id))
                return True
            except sqlite3.IntegrityError:
                logger.error(f"Плейлист с именем '{new_name}' уже существует")
                return False
            except sqlite3.Error as er:
                logger.error(f"Ошибка изменения плейлиста: {er}")
                return False

        # value, а не label: label это только подсказка, поле оставалось пустым
        name_input = ft.TextField(label="Название плейлиста", value=pl_name, expand=True)
        cover_input = ft.TextField(label="Путь к картинке (опционально)", value=pl_cover_path or "", expand=True)
        
        # Создаем диалог
        dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.LIBRARY_MUSIC),
                ft.Text(f"Изменение альбома №{pl_id}")
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
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(page, dlg)),
                ft.ElevatedButton("Сохранить", on_click=lambda e: save_selection(e, p_id=pl_id), bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        open_dialog(page, dlg)

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

    QUEUE_GAP = 8  # вертикальный зазор между ячейками очереди

    # Column, а не ListView: только Column честно учитывает высоту распорок
    # виртуального списка (см. VirtualList)
    queue_list = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    queue_anim = ft.Animation(350, ft.AnimationCurve.EASE_OUT)

    def queue_cell_title(container):
        """Достаёт Text с названием трека из ячейки очереди.

        Разметка ячейки: Container -> ContextMenu -> Row -> [обложка, Column]
        -> Column.controls[0] это название. Вынесено в одно место, чтобы
        добавление очередной обёртки ломалось заметно, а не молча.
        """
        try:
            row = container.content.content   # Container -> ContextMenu -> Row
            column_control = row.controls[-1]
            return column_control.controls[0]
        except (AttributeError, IndexError) as ex:
            logger.debug(f"Не удалось найти название трека в ячейке очереди: {ex}")
            return None

    def remove_played_tracks_ui(count):
        """Убирает отыгравшие треки из UI.

        При оконном рендере патчить controls вручную незачем: перерисовка
        окна из ~30 ячеек дешевле и не рассинхронизируется с БД.
        """
        queue_vlist.refresh()

    def delete_from_queue(e, uid):
        """Удаление трека из очереди с корректным обновлением UI.

        Если удаляли играющий трек, ui_utils переключается на следующий и
        присылает tags_update — очередь перерисует уже подписчик. Свой
        rebuild_queue_ui() тут привёл бы к гонке с анимацией скипа:
        она отработала бы по уже перестроенному списку и убрала лишний элемент.
        """
        advanced = ui_utils.delete_track_from_queue(e, uid, play_btn)
        if not advanced:
            rebuild_queue_ui()

    # --- данные очереди для оконного рендера ---
    # Сортируем строго по ID, чтобы 0 (играющий сейчас) был всегда наверху

    def queue_count():
        r = ui_utils.db_query_one('queue.db', "SELECT COUNT(*) FROM queue WHERE id >= 0")
        return r[0] if r else 0

    def queue_fetch(offset, limit):
        return ui_utils.db_query_all('queue.db',
            """SELECT id, uid, name, author, path, cov_bytes FROM queue
               WHERE id >= 0 ORDER BY id ASC LIMIT ? OFFSET ?""", (limit, offset))

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

    # Обработчик Drop (когда на ячейку очереди что-то бросают).
    # Определён один раз, а не на каждую ячейку: адресат берётся из e.control.data
    async def queue_on_accept(e):
        src_control = page.get_control(e.src_id) # Элемент, который тащим
        if src_control is None:
            return

        src_data = src_control.data      # Это ID (int), путь (str) или словарь (dict)
        target_uid = e.control.data       # теперь uid, не позиция

        # ==========================================
        # ВЕТКА 1: Бросили файл/папку (СТРОКА)
        # ==========================================
        if isinstance(src_data, str):
            row = ui_utils.db_query_one('queue.db', "SELECT id FROM queue WHERE uid = ?", (target_uid,))
            if row is None:
                return
            target_pos = row[0]

            await on_files_dropped(src_data, insert_at=target_pos)

            if target_pos == 0:
                new_track = ui_utils.db_query_one('queue.db', "SELECT path FROM queue WHERE id = 0")
                if new_track:
                    ui_utils.load_track(page, new_track[0], play_btn, -2)
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
                    return
                target_pos = row[0]

                cur.execute("UPDATE queue SET id = id + 1 WHERE id >= ?", (target_pos,))
                cur.execute("""
                    INSERT INTO queue (id, name, author, path, cov_bytes)
                    VALUES (?, ?, ?, ?, ?)
                """, (target_pos, name, author, path, cov_bytes))
                con_q.commit()

            except Exception as ex:
                logger.error(f"Ошибка при вставке из плейлиста в очередь: {ex}")
                con_q.rollback()
                return
            finally:
                con_q.close()

            if target_pos == 0:
                ui_utils.load_track(page, path, play_btn, -2)
            else:
                rebuild_queue_ui()
            return

        # ==========================================
        # ВЕТКА 2.5: весь плейлист целиком (с album-карточки)
        # ==========================================
        if isinstance(src_data, dict) and src_data.get("source") == "playlist_full":
            src_playlist_id = src_data["playlist_id"]

            tracks_to_add = ui_utils.db_query_all('app.db', """
                SELECT t.name, t.author, t.path, t.cov_bytes
                FROM playlist_tracks pt
                JOIN tracks t ON pt.track_id = t.id
                WHERE pt.playlist_id = ?
                ORDER BY pt.position
            """, (src_playlist_id,))

            if not tracks_to_add:
                return  # пустой плейлист — вставлять нечего

            con_q = sqlite3.connect('queue.db')
            cur = con_q.cursor()
            target_pos = None
            try:
                cur.execute("SELECT id FROM queue WHERE uid = ?", (target_uid,))
                row = cur.fetchone()
                if row is None:
                    return
                target_pos = row[0]

                n = len(tracks_to_add)
                # освобождаем n мест начиная с target_pos
                cur.execute("UPDATE queue SET id = id + ? WHERE id >= ?", (n, target_pos))

                for offset, (t_name, t_author, t_path, t_cov) in enumerate(tracks_to_add):
                    cur.execute("""
                        INSERT INTO queue (id, name, author, path, cov_bytes)
                        VALUES (?, ?, ?, ?, ?)
                    """, (target_pos + offset, t_name, t_author, t_path, t_cov))

                con_q.commit()
            except Exception as ex:
                logger.error(f"Ошибка при вставке плейлиста в очередь: {ex}")
                con_q.rollback()
                return
            finally:
                con_q.close()

            if target_pos == 0:
                first_path = tracks_to_add[0][2]
                ui_utils.load_track(page, first_path, play_btn, -2)
            else:
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
                cursor.execute("UPDATE queue SET id = -9999 WHERE id = ?", (src_pos,))
                cursor.execute("UPDATE queue SET id = id + 1 WHERE id >= 0 AND id < ?", (src_pos,))
                cursor.execute("UPDATE queue SET id = 0 WHERE id = -9999")
            else:
                cursor.execute("UPDATE queue SET id = -9999 WHERE id = ?", (src_pos,))
                cursor.execute("UPDATE queue SET id = ? WHERE id = ?", (src_pos, target_pos))
                cursor.execute("UPDATE queue SET id = ? WHERE id = -9999", (target_pos,))
            con_queue.commit()

            if src_pos == 0 or target_pos == 0:
                cursor.execute("SELECT path FROM queue WHERE id = 0")
                path_row = cursor.fetchone()
                if path_row:
                    ui_utils.load_track(page, path_row[0], play_btn, -2)
        except Exception as ex:
            logger.error(f"Ошибка БД при перетаскивании внутри очереди: {ex}")
            con_queue.rollback()
            return
        finally:
            con_queue.close()

        # Раньше здесь вручную переставлялись контролы в queue_list; при оконном
        # рендере проще и надёжнее перерисовать окно
        rebuild_queue_ui()

    def make_queue_drop_handlers(container, is_playing):
        """Подсветка ячейки очереди при наведении перетаскиваемого объекта."""
        def _on_will_accept(e):
            container.border = ft.Border.all(2, ft.Colors.BLUE_ACCENT)
            container.update()

        def _on_leave(e):
            border_col = ft.Colors.GREEN if is_playing else ft.Colors.TRANSPARENT
            container.border = ft.Border.all(2, border_col)
            container.update()

        return _on_will_accept, _on_leave

    def build_queue_cell(index, row):
        track_id, track_uid, name, author, path, cov_bytes = row

        # 1. Визуальное оформление играющего трека (id == 0)
        is_playing = (track_id == 0)
        border_color = ft.Colors.GREEN if is_playing else ft.Colors.TRANSPARENT
        bg_color = ft.Colors.SURFACE_CONTAINER_HIGHEST if not is_playing else ft.Colors.SURFACE_CONTAINER_HIGH

        # Попытка декодировать обложку (если она есть)
        cover_img = ft.Icon(ft.Icons.MUSIC_NOTE, size=queue_cell[0])
        if cov_bytes is not None:
            cover_img = ft.Image(src=cov_bytes, width=queue_cell[0], height=queue_cell[0])

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
                    ft.PopupMenuItem(content=ft.Text("Удалить из очереди"), on_click=lambda e, uid=track_uid: delete_from_queue(e, uid)),
                    ft.PopupMenuItem(content=ft.Text("Расположение файла"), on_click=lambda e, p=path: ui_utils.open_file_folder(e, p)),
                    ft.PopupMenuItem(content=ft.Text("Открыть в файловой панели"), on_click=lambda e, p=path: ui_utils.open_file_in_player_explorer(e, p, rebuild_explorer)),
                ]
            ),
            padding=queue_cell[4],
            border=ft.Border.all(2, border_color),
            border_radius=queue_border_radius,
            bgcolor=bg_color,
            # --- ДОБАВЛЯЕМ ДЛЯ АНИМАЦИИ ---
            height=queue_cell[5],  # Фиксированная высота важна и для анимации, и для расчёта окна
            margin=queue_vlist.cell_margin(), # зазор вместо ListView.spacing (см. VirtualList)
            opacity=1.0, # Явно указываем стартовую непрозрачность
            offset=ft.Offset(0, 0), # Явно указываем стартовую позицию (на месте)
            animate=queue_anim,
            animate_opacity=queue_anim,
            animate_offset=queue_anim,   # <--- Включаем анимацию сдвига
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            data=track_uid,
            on_click=lambda e: on_track_click(e.control.data)
        )

        on_will_accept, on_leave = make_queue_drop_handlers(item_content, is_playing)

        # Собираем матрешку: Target (зона дропа) -> Draggable (можно тащить) -> Container (внешний вид)
        return ft.DragTarget(
            group="queue_drag", # ВАЖНО: Общая группа с проводником
            data=track_uid, # Сохраняем target_id в данных таргета для on_leave
            on_accept=queue_on_accept,
            on_will_accept=on_will_accept,
            on_leave=on_leave,
            content=ft.Draggable(
                group="queue_drag",
                data=track_uid, # Передаем ID при перетаскивании
                content=item_content,
                content_when_dragging=ft.Container(
                    content=ft.Text(f"Перемещение: {name}", size=queue_cell[1]),
                    padding=queue_cell[4],
                    height=queue_cell[5],
                    margin=queue_vlist.cell_margin(),
                    bgcolor=ft.Colors.INVERSE_SURFACE,
                    border_radius=queue_border_radius,
                    opacity=0.8
                )
            )
        )

    queue_vlist = VirtualList(
        queue_list,
        cell_height=queue_cell[5],
        gap=QUEUE_GAP,
        count_rows=queue_count,
        fetch_rows=queue_fetch,
        build_row=build_queue_cell,
    )

    def rebuild_queue_ui(idx=None):
        t0 = time.perf_counter()
        queue_vlist.refresh()
        logger.debug(f"Очередь: окно {queue_vlist.start}-{queue_vlist.end} из {queue_vlist.total} "
                     f"за {(time.perf_counter()-t0)*1000:.1f} мс")

    async def skip_track_with_animation(page, queue_list, remove_callback, idx):
        """
        Визуально уводит отыгравший трек влево и гасит его,
        плавно подсвечивает зелёным следующий трек,
        затем убирает элементы из UI.
        """
        # Анимация имеет смысл, только если верх списка сейчас на экране:
        # при прокрутке вниз первый контрол — это распорка, а не ячейка
        first_item = queue_vlist.rendered_row(0)
        if first_item is not None:
            first_container = first_item.content.content

            first_container.opacity = 0
            first_container.offset = ft.Offset(-1, 0)
            first_container.border = ft.Border.all(0, ft.Colors.TRANSPARENT)

            next_item = queue_vlist.rendered_row(1)
            if next_item is not None and idx == 1:
                title_text = queue_cell_title(next_item.content.content)
                if title_text is not None:
                    title_text.color = ft.Colors.GREEN

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
        results = ui_utils.db_query_all('app.db', "SELECT id, name, cover_path FROM playlists")
        ids = []
        names = []
        covers = []
        for row in results:
            ids.append(row[0])
            names.append(row[1])
            covers.append(row[2])
        return ids, names, covers
    playlist_ids, playlist_names, playlist_images = rebuild_playlists_list()

    PLAYLIST_GAP = 5  # вертикальный зазор между треками в рабочей зоне

    # Column, а не ListView — по той же причине, что и очередь (см. VirtualList).
    # padding у Column нет, он перенесён на контейнер рабочей зоны.
    playlist_list = ft.Column(
        expand=True,
        auto_scroll=False,
        scroll=ft.ScrollMode.AUTO,  # без режима прокрутки не приходит on_scroll
    )

    # Плейлист, открытый в рабочей зоне сейчас. Замыкания оконного рендера
    # читают id отсюда, поэтому их не нужно пересоздавать при смене плейлиста.
    current_playlist = {"id": 2}

    playlist_title_text = ft.Text("", size=text_size + 4, weight=ft.FontWeight.BOLD, color="white", font_family="Arial", overflow=ft.TextOverflow.ELLIPSIS)
    playlist_desc_text = ft.Text("", size=text_size - 2, weight=ft.FontWeight.BOLD, color="white", font_family="Arial", overflow=ft.TextOverflow.ELLIPSIS)

    playlist_data = ft.Container(
        height=100,
        # bgcolor=ft.Colors.RED_800,
        content=ft.Row(
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
                            # bgcolor=ft.Colors.RED_700, 
                            content=playlist_title_text
                        ),
                        ft.Container(
                            # bgcolor=ft.Colors.RED_600, 
                            content=playlist_desc_text
                        ),
                    ]
                ),
                ft.Container( # кнопка play
                    expand=1,
                    content=ft.Image(
                        src="assets/icons/play_ico_inac.png",
                        width=30,
                        height=30,
                        fit="contain",
                    ),
                    alignment=ft.Alignment.BOTTOM_RIGHT,
                    shape=ft.BoxShape.CIRCLE,
                    animate=200,
                    scale=1.0,
                    animate_scale=ft.Animation(100, ft.AnimationCurve.EASE_OUT),
                ),
            ]
        )
    )

    def update_playlist_data(title: str, desc: str, cover_path: str):
        playlist_title_text.value = title
        playlist_desc_text.value = desc
        playlist_data.update()

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
    # --- данные рабочей зоны для оконного рендера ---

    async def scroll_list_to_top(lv):
        """scroll_to в Flet 0.85 — корутина. Ошибку глушим: это косметика,
        и уронить из-за неё обновление списка нельзя."""
        try:
            await lv.scroll_to(offset=0, duration=0)
        except Exception as ex:
            logger.debug(f"Не удалось прокрутить список наверх: {ex}")

    def playlist_count():
        r = ui_utils.db_query_one('app.db',
            "SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = ?", (current_playlist["id"],))
        return r[0] if r else 0

    def playlist_fetch(offset, limit):
        return ui_utils.db_query_all('app.db', """
            SELECT t.id, t.name, t.author, t.path, t.cov_bytes, pt.position
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            WHERE pt.playlist_id = ?
            ORDER BY pt.position
            LIMIT ? OFFSET ?
        """, (current_playlist["id"], limit, offset))

    def on_track_double_click(e):
        t_id, t_name, t_author, t_path, t_cov = e.control.data

        try:
            with closing(sqlite3.connect('queue.db', timeout=10.0)) as con_q:
                # commit был в finally и срабатывал даже после ошибки —
                # теперь транзакция откатывается, если вставка не прошла
                with con_q:
                    con_q.execute('DELETE FROM queue WHERE id = ?', (0,))
                    con_q.execute("INSERT INTO queue (id, name, author, path, cov_bytes) VALUES (?, ?, ?, ?, ?)",
                                  (0, t_name if t_name else Path(t_path).name, t_author, str(t_path), t_cov))
        except sqlite3.Error as ex:
            logger.error(f"Ошибка БД очереди: {ex}")
            return

        ui_utils.load_track(e.page, t_path, play_btn, -2)
        logger.debug(f"файл: {t_path}")

    def make_drop_handlers(container):
        """Обработчики drop'а, привязанные к Container конкретной строки.

        Раньше рамка искалась как e.control.content.content, но там лежит
        ContextMenu, а не Container: присваивание проходило молча и
        подсветки не было вообще.
        """
        def _on_accept(e):
            # Снимаем подсветку до возможного ребилда: после playlist_ui()
            # этот контрол уже не в дереве и update() по нему упадёт
            container.border = ft.Border.all(2, ft.Colors.TRANSPARENT)
            container.update()

            src_control = page.get_control(e.src_id)
            if src_control is None: return

            src_data = src_control.data      # Что тащим (словарь с данными)
            target_pos = e.control.data      # Куда бросаем (позиция)

            # Если тянем трек из этого же плейлиста
            if isinstance(src_data, dict) and src_data.get("source") == "playlist":
                src_pos = src_data["position"]
                if src_pos != target_pos:
                    pl_id = current_playlist["id"]
                    # Вызываем вспомогательную функцию сдвига (написана выше)
                    shift_playlist_track_db(pl_id, src_pos, target_pos)
                    # Перерисовываем плейлист
                    playlist_ui(page, playlist_list, play_btn, pl_id)

        def _on_will_accept(e):
            container.border = ft.Border.all(2, ft.Colors.BLUE_ACCENT)
            container.update()

        def _on_leave(e):
            container.border = ft.Border.all(2, ft.Colors.TRANSPARENT)
            container.update()

        return _on_accept, _on_will_accept, _on_leave

    def build_playlist_cell(index, row):
        track_id, name, author, path, cov_bytes, position = row
        playlist_idl = current_playlist["id"]

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
            border=ft.Border.all(2, ft.Colors.TRANSPARENT), # Невидимая рамка для on_will_accept
            height=track_cell[5],                  # фиксированная высота — основа расчёта окна
            margin=playlist_vlist.cell_margin(),   # зазор вместо ListView.spacing
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

        on_accept, on_will_accept, on_leave = make_drop_handlers(item_content)

        return ft.DragTarget(
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
                            if playlist_idl != 2
                            else []
                        ),
                        ft.PopupMenuItem(content=ft.Text("Добавить в альбом"), on_click=lambda e, p=path: show_albums_dialog(e, p)),
                        # Удаление из текущего плейлиста. Раньше вариант "Удалить
                        # из альбома" был вообще без on_click, и из обычного
                        # плейлиста трек убрать было нельзя
                        ft.PopupMenuItem(
                            content=ft.Text("Удалить из избранного" if playlist_idl == 2 else "Удалить из альбома"),
                            on_click=lambda e, tid=track_id, pid=playlist_idl: (
                                ui_utils.delete_playlist_track(tid, pid),
                                playlist_ui(page, playlist_list, play_btn, pid),
                            ),
                        ),
                        ft.PopupMenuItem(content=ft.Text("Расположение файла"), on_click=lambda e, p=path: ui_utils.open_file_folder(e, p)),
                        ft.PopupMenuItem(content=ft.Text("Открыть в файловой панели"), on_click=lambda e, p=path: ui_utils.open_file_in_player_explorer(e, p, rebuild_explorer)),
                    ]
                ),
                content_when_dragging=ft.Container(
                    content=ft.Text(f"Перемещение: {name}", size=track_cell[1]),
                    padding=track_cell[4],
                    height=track_cell[5],
                    margin=playlist_vlist.cell_margin(),
                    bgcolor=ft.Colors.INVERSE_SURFACE,
                    border_radius=track_border_radius,
                    opacity=0.8
                )
            )
        )

    playlist_vlist = VirtualList(
        playlist_list,
        cell_height=track_cell[5],
        gap=PLAYLIST_GAP,
        count_rows=playlist_count,
        fetch_rows=playlist_fetch,
        build_row=build_playlist_cell,
    )

    def playlist_ui(page: ft.Page, playlist_list: ft.Column, play_btn_obj, playlist_idl: int = 2):
        global playlist_id, playlist_name, playlist_desk, playlist_cover_path
        if playlist_idl == 1:
            create_albums_dialog(page)
            return
        if playlist_idl != playlist_id:
            r = ui_utils.db_query_one('app.db', "SELECT name, desk, cover_path FROM playlists WHERE id = ?", (playlist_idl,))
            if r:
                playlist_id = playlist_idl
                playlist_name = r[0]
                playlist_desk = r[1]
                playlist_cover_path = r[2]
        update_playlist_data(playlist_name, playlist_desk, playlist_cover_path)

        # Сменили плейлист — прокрутку сбрасываем наверх, иначе (перерисовка
        # того же плейлиста после drag&drop или удаления) остаёмся на месте
        switched = (playlist_idl != current_playlist["id"])
        current_playlist["id"] = playlist_idl
        # Дёргать scroll_to, когда список и так в начале, не надо: на ещё не
        # подключившемся клиенте вызов висит до таймаута и рвёт канал обновлений
        need_scroll_top = switched and playlist_vlist.scrolled() and bool(playlist_list.page)

        t0 = time.perf_counter()
        playlist_vlist.refresh(to_top=switched)
        if need_scroll_top:
            page.run_task(scroll_list_to_top, playlist_list)
        logger.debug(f"Плейлист #{playlist_idl}: окно {playlist_vlist.start}-{playlist_vlist.end} "
                     f"из {playlist_vlist.total} за {(time.perf_counter()-t0)*1000:.1f} мс")

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
            # Именно на этом Container лежит рамка — её и подсвечиваем при drag.
            # Раньше подсветка вешалась на GestureDetector-обёртку: присваивание
            # проходило без ошибки, но ничего не рисовало.
            card_border = ft.Container(
                content=ft.Image(
                    src=img,
                    width=50,
                    height=50,
                    fit="cover"
                ),
                tooltip=name,
                border_radius=12,
                border=ft.Border.all(2, ft.Colors.TRANSPARENT),
            )

            card = ft.GestureDetector(
                on_tap=lambda e, pid=p_id: playlist_ui(page, playlist_list, play_btn, pid),
                content=card_border
                )

            if p_id == 2:
                context_menu = ft.ContextMenu(
                    secondary_items=[
                        ft.PopupMenuItem(content=ft.Text("Добавить в очередь"), on_click=lambda e, id=p_id: (ui_utils.add_playlist_to_queue(id), rebuild_queue_ui()),),
                    ],
                    content=card
                )
            elif p_id >2:
                context_menu = ft.ContextMenu(
                    secondary_items=[
                        ft.PopupMenuItem(content=ft.Text("Добавить в очередь"), on_click=lambda e, id=p_id: (ui_utils.add_playlist_to_queue(id), rebuild_queue_ui()),),
                        ft.PopupMenuItem(content=ft.Text("Редактировать плейлист"), on_click=lambda e, id=p_id, n=name, i=img: change_albums_dialog(page, id, n, i),),
                        ft.PopupMenuItem(content=ft.Text("Удалить плейлист"), on_click=lambda e, id=p_id: (ui_utils.delete_playlist(id), update_albums_ui(),
                            playlist_ui(page, playlist_list, play_btn, 2) if playlist_id == id else None),),
                    ],
                    content=card
                )
            else:
                context_menu = card

            draggable_card = ft.Draggable(
                group="queue_drag",
                data={"source": "playlist_full", "playlist_id": p_id, "name": name},
                content=context_menu,
                content_when_dragging=ft.Container(
                    content=ft.Text(f"Плейлист: {name}", size=12),
                    padding=8,
                    bgcolor=ft.Colors.INVERSE_SURFACE,
                    border_radius=12,
                    opacity=0.8
                )
            )

        # --- Приём drop'а ---
            if p_id >= 2:
                def on_album_will_accept(e, container=card_border):
                    container.border = ft.Border.all(2, ft.Colors.BLUE_ACCENT)
                    container.update()

                def on_album_leave(e, container=card_border):
                    container.border = ft.Border.all(2, ft.Colors.TRANSPARENT)
                    container.update()

                def on_album_accept(e, target_playlist_id=p_id, container=card_border):
                    src_control = page.get_control(e.src_id)
                    if src_control is None:
                        return
                    src_data = src_control.data

                    path_to_add = None

                    if isinstance(src_data, str):
                        # трек/папка из проводника
                        path_to_add = src_data

                    elif isinstance(src_data, dict) and src_data.get("source") == "playlist":
                        # одиночный трек, перетащенный из карточки плейлиста
                        path_to_add = src_data["track_data"][2]

                    elif isinstance(src_data, int):
                        # трек из очереди (там Draggable.data = track_uid)
                        row = ui_utils.db_query_one('queue.db', "SELECT path FROM queue WHERE uid = ?", (src_data,))
                        if row:
                            path_to_add = row[0]

                    # dict source == "playlist_full" (кинули целый плейлист) — игнорируем

                    container.border = ft.Border.all(2, ft.Colors.TRANSPARENT)
                    container.update()

                    if path_to_add is None:
                        return

                    ui_utils.add_track_to_playlist(path_to_add, target_playlist_id)  # insert_at=None -> в конец

                    if playlist_id == target_playlist_id:
                        playlist_ui(page, playlist_list, play_btn, target_playlist_id)

                item = ft.DragTarget(
                    group="queue_drag",
                    data=p_id,
                    on_accept=on_album_accept,
                    on_will_accept=on_album_will_accept,
                    on_leave=on_album_leave,
                    content=draggable_card
                )
            else:
                item = draggable_card
        
            albums_row.controls.append(item)
        # Обновляем только саму строку (если она уже добавлена на страницу)
        # Если она еще не добавлена, игнорируем ошибку (или используем page.update())
        try:
            albums_row.update()
        except Exception:
            pass
    update_albums_ui()

    switch_playlists_WZ_view = ft.Container(
        # bgcolor=ft.Colors.RED_900,
        expand=True,
        content=ft.Column(
            spacing = 5,
            controls=[
                playlist_data,
                ft.Container( # строка с альбомами 
                    height=50,
                    # bgcolor=ft.Colors.RED_900,
                    content=albums_row
                ),
                ft.Container( # рабочая зона
                        # bgcolor=ft.Colors.RED_800,
                        content=playlist_list,
                        padding=10, # был padding самого списка, у Column его нет
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
                                # bgcolor=ft.Colors.RED,
                                border_radius=UBOX_b_radius,
                                
                                #Стеклянный эффект
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE), # Полупрозрачный белый
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), # Тонкая рамка
                                blur=ft.Blur(sigma_x=1.5, sigma_y=1.5, tile_mode=ft.BlurTileMode.CLAMP), # Размытие заднего плана

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

                                    # image=ft.DecorationImage( #тема - картинка
                                    #     src="assets/textures/LBOX.jpg",  # Путь к картинке (локальный или URL)
                                    #     fit="cover",                     # Растянуть, чтобы заполнить весь контейнер
                                    #     opacity=0.8                      # Можно настроить прозрачность самой текстуры
                                    # ),
                                    #Стеклянный эффект
                                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE), # Полупрозрачный белый
                                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), # Тонкая рамка
                                    blur=ft.Blur(sigma_x=1.5, sigma_y=1.5, tile_mode=ft.BlurTileMode.CLAMP), # Размытие заднего плана

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
                                                # bgcolor=ft.Colors.RED_700,
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
                                    #Стеклянный эффект
                                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE), # Полупрозрачный белый
                                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), # Тонкая рамка
                                    blur=ft.Blur(sigma_x=1.5, sigma_y=1.5, tile_mode=ft.BlurTileMode.CLAMP), # Размытие заднего плана
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
                                # bgcolor=ft.Colors.RED, 
                                expand=1,
                                border_radius=DBOX_b_radius,

                                #Стеклянный эффект
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE), # Полупрозрачный белый
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), # Тонкая рамка
                                blur=ft.Blur(sigma_x=1.5, sigma_y=1.5, tile_mode=ft.BlurTileMode.CLAMP), # Размытие заднего плана
                                 
                                content=ft.Row(
                                    spacing=10, # Расстояние между элементами внутри
                                    controls=[
                                        track_cover,
                                        ft.Container( # коробка со столбцом метаданных
                                            height=150,
                                            #width=300,
                                            # bgcolor=ft.Colors.RED_800,
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
                                            # bgcolor=ft.Colors.RED_800,
                                            content=ft.Row(
                                                alignment=ft.MainAxisAlignment.END,
                                                controls=[
                                                    start_time_label
                                                ]
                                            )
                                        ),
                                        ft.Container( # коробка главного столбца управления
                                            height=150,
                                            # bgcolor=ft.Colors.RED_800, 
                                            expand=6, #2/4
                                            content=ft.Column( #главный столбец управления
                                                spacing=2,
                                                alignment=ft.MainAxisAlignment.CENTER,
                                                controls=[
                                                    ft.Container( # кнопки кправления
                                                        #expand=2,
                                                        # bgcolor=ft.Colors.RED_900, 
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
                                            # bgcolor=ft.Colors.RED_800,
                                            content=ft.Row( 
                                                alignment=ft.MainAxisAlignment.START,
                                                controls=[
                                                    end_time_label
                                                ]
                                            )
                                        ),
                                        ft.Container( # коробка заглушка2
                                            height=150,
                                            # bgcolor=ft.Colors.RED_800, 
                                            expand=4, #1/4
                                            content=ft.Column(
                                                spacing=5,
                                                controls=[
                                                    ft.Container(
                                                        # bgcolor=ft.Colors.RED_900, 
                                                        expand=4,
                                                    ),
                                                    ft.Container(
                                                        # bgcolor=ft.Colors.RED_900, 
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
                                                                    # bgcolor=ft.Colors.RED_900,
                                                                    expand=1,
                                                                    content = vol_label
                                                                )
                                                            ]
                                                        )
                                                    ),
                                                    ft.Container(
                                                        # bgcolor=ft.Colors.RED_900, 
                                                        expand=4,
                                                    )
                                                ]
                                            )
                                        ),
                                        ft.Container( # коробка заглушка3
                                            height=150,
                                            width=150,
                                            # bgcolor=ft.Colors.RED_800,
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
    playlist_ui(page, playlist_list, play_btn, playlist_idl=2)

    def on_tags_changed(topic, message):
        track_title.value = message.get("Название", "Неизвестно")
        track_artist.value = message.get("Автор", "Неизвестный исполнитель")
        track_album.value = message.get("Альбом", "")
        track_year.value = message.get("Год", "")
        idx = message.get("idx", 0)
        
        if message.get("cover", ""): track_cover.src = message.get("cover", "")
        else: track_cover.src = "https://flet.dev/img/logo.svg"

        # Обновляем DBOX явно. Раньше это происходило побочно: rebuild_queue_ui
        # заканчивался page.update(). Теперь очередь обновляет только свой
        # контейнер, и без этой строки метаданные меняются лишь тогда, когда
        # page.update() случайно сделает кто-то ещё (например анимация скипа).
        page.update()

        if idx == -2: #-2 для случая, когда трек загружается первым, чтобы не дергать анимацию
            rebuild_queue_ui()
        else:
            page.run_task(skip_track_with_animation, page, queue_list, remove_played_tracks_ui, idx)

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