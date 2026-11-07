"""«Отладочный режим» сервера — отдельный экран поверх плеера (page.views).

ТЗ: docs/TZ_server_panel.md. Вкладки: «Сервер» (состояние, буфер сети VLC),
«Файлы» (папки сервера, загрузка, скачивание, удаление), «Операции» (свои загрузки
и их откат). Внизу — полоса идущей передачи, видна на любой вкладке.
Точка входа — open_server_panel(page), её вызывает кнопка в gui2.py.

Сеть — только через asyncio.to_thread внутри async-обработчиков: так ожидание
ответа Pi не держит интерфейс, а контролы обновляются из цикла событий Flet,
а не из постороннего потока (оттуда изменения до клиента не доходят).
Передачи файлов идут в своём потоке (transfers.py), прогресс приходит через pubsub.
"""
import asyncio
import configparser
import datetime
import logging
import time

import flet as ft

import sources
import transfers
import ui_utils

logger = logging.getLogger(__name__)

ROUTE = "/server"
STATUS_REFRESH_SEC = 5   # как часто обновлять «Состояние», пока экран открыт
PROGRESS_TOPIC = "transfer_progress"
PREVIEW_MAX_ROWS = 400   # строк в списке предпросмотра; остальное — «…и ещё N»

config = configparser.ConfigParser()
config.read('ui_config.txt', encoding='utf-8')

# Конфиги [UI server] ==========
# fallback — общие цвета из [UI Settings], чтобы экран без своей секции выглядел как плеер
_textCol = config.get('UI Settings', 'textCol', fallback='white')
_textSecondaryCol = config.get('UI Settings', 'textSecondaryCol', fallback='gray')
server_BGCol = config.get('UI server', 'server_BGCol', fallback='') or None # Фон экрана; пусто — как у плеера
server_appbarBGCol = config.get('UI server', 'server_appbarBGCol', fallback='') or None # Фон верхней полосы с заголовком; пусто — по теме
server_cardBGCol = config.get('UI server', 'server_cardBGCol', fallback='surfacecontainer') # Фон карточек разделов
server_cardBorderCol = config.get('UI server', 'server_cardBorderCol', fallback='outlinevariant') # Рамка карточек
server_cardRadius = config.getint('UI server', 'server_cardRadius', fallback=12) # Скругление карточек
server_titleSize = config.getint('UI server', 'server_titleSize', fallback=16) # Размер заголовков разделов
server_textSize = config.getint('UI server', 'server_textSize', fallback=config.getint('UI Settings', 'text_size', fallback=13)) # Размер текста
server_textCol = config.get('UI server', 'server_textCol', fallback=_textCol) # Основной текст и значения
server_labelCol = config.get('UI server', 'server_labelCol', fallback=_textSecondaryCol) # Подписи слева от значений, пояснения
server_okCol = config.get('UI server', 'server_okCol', fallback='green') # «онлайн», «сохранено»
server_errCol = config.get('UI server', 'server_errCol', fallback='redaccent') # Ошибки
server_warnCol = config.get('UI server', 'server_warnCol', fallback='orange') # Конфликты имён в предпросмотре загрузки
server_sliderThumbCol = config.get('UI server', 'server_sliderThumbCol', fallback=config.get('UI Settings', 'sliderThumbCol', fallback='indigo800')) # Ползунок буфера
server_buttonBGCol = config.get('UI server', 'server_buttonBGCol', fallback=config.get('UI Settings', 'buttonBGCol', fallback='blue')) # Фон кнопок
server_buttonTextCol = config.get('UI server', 'server_buttonTextCol', fallback=config.get('UI Settings', 'buttonTextCol', fallback='white')) # Текст кнопок
server_tabIndicatorCol = (config.get('UI server', 'server_tabIndicatorCol', fallback='') or server_buttonBGCol) # Полоска под выбранной вкладкой
server_iconCol = config.get('UI server', 'server_iconCol', fallback=server_labelCol) # Значки папок и файлов в списке
server_progressCol = (config.get('UI server', 'server_progressCol', fallback='') or server_buttonBGCol) # Полоса прогресса передачи
server_progressBGCol = (config.get('UI server', 'server_progressBGCol', fallback='') or server_cardBGCol) # Фон панели передачи внизу экрана
server_rowHeight = config.getint('UI server', 'server_rowHeight', fallback=40) # Высота строки в списке файлов


def _text(value="", col=None, **kw):
    return ft.Text(value, size=server_textSize, color=col or server_textCol, **kw)


def _button(text, on_click, icon=None, bgcolor=None):
    return ft.Button(
        content=text, icon=icon, on_click=on_click,
        bgcolor=bgcolor or server_buttonBGCol, color=server_buttonTextCol,
    )


def _card(title, controls, col=None):
    return ft.Container(
        col=col,
        content=ft.Column(
            [ft.Text(title, size=server_titleSize, weight=ft.FontWeight.BOLD, color=server_textCol), *controls],
            spacing=10,
        ),
        padding=16,
        bgcolor=server_cardBGCol,
        border=ft.Border.all(1, server_cardBorderCol),
        border_radius=server_cardRadius,
    )


def _ago(ts):
    """Время последнего сканирования: «05.11 14:32 (3 ч назад)»."""
    if not ts:
        return "не было"
    when = datetime.datetime.fromtimestamp(ts)
    sec = int(time.time() - ts)
    if sec < 3600:
        ago = f"{max(sec // 60, 0)} мин назад"
    elif sec < 86400:
        ago = f"{sec // 3600} ч назад"
    else:
        ago = f"{sec // 86400} дн назад"
    return f"{when:%d.%m %H:%M} ({ago})"


def _size(n):
    if n is None:
        return "?"
    for unit, k in (("ГБ", 1 << 30), ("МБ", 1 << 20), ("КБ", 1 << 10)):
        if n >= k:
            return f"{n / k:.1f} {unit}" if n < 10 * k else f"{n / k:.0f} {unit}"
    return f"{n} Б"


def _duration(sec):
    sec = int(sec)
    if sec < 60:
        return f"{sec} с"
    if sec < 3600:
        return f"{sec // 60} мин"
    return f"{sec // 3600} ч {sec % 3600 // 60} мин"


def _error_text(err):
    """Исключение источника — в строку для экрана."""
    if not sources.SRV_ENABLED:
        return "Сервер выключен в config.txt ([Server] enabled)"
    return str(err) or err.__class__.__name__


_picker = None


def _get_picker():
    """Один FilePicker на приложение: это сервис страницы, а не контрол экрана."""
    global _picker
    if _picker is None:
        _picker = ft.FilePicker()
    return _picker


def open_server_panel(page: ft.Page):
    """Открыть экран поверх плеера. Повторный вызов, пока экран открыт, ничего не делает."""
    if any(v.route == ROUTE for v in page.views):
        return

    alive = [True]   # экран открыт; фоновые обновления по нему останавливаются
    me = {"name": None, "admin": False, "known": False}   # кто я на сервере (GET /server/me)
    picker = _get_picker()

    def safe_update():
        if alive[0]:
            try:
                page.update()
            except (RuntimeError, AssertionError):
                pass

    def show_message(title, lines, col=None):
        dlg = ft.AlertDialog(
            title=ft.Text(title),
            # длинный отчёт — с прокруткой и фиксированной высотой, короткий — по содержимому
            content=ft.Container(
                width=560,
                height=420 if len(lines) > 14 else None,
                content=ft.Column([_text(l, col, selectable=True) for l in lines], tight=True,
                                  scroll=ft.ScrollMode.AUTO if len(lines) > 14 else None),
            ),
            actions=[ft.TextButton("Закрыть", on_click=lambda e: page.pop_dialog())],
        )
        page.show_dialog(dlg)

    def confirm(title, text, ok_text, on_ok, danger=False):
        async def ok(e):
            page.pop_dialog()
            await on_ok()

        page.show_dialog(ft.AlertDialog(
            title=ft.Text(title),
            content=_text(text),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                _button(ok_text, ok, bgcolor=server_errCol if danger else None),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    # ======================= Состояние =======================

    values = {}   # ключ -> Text со значением

    def info_row(label, key):
        values[key] = _text("…", selectable=True)
        return ft.Row([
            ft.Container(_text(label, server_labelCol), width=190),
            ft.Container(values[key], expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.START)

    status_rows = [
        info_row("Адрес", "url"),
        info_row("Токен", "token"),
        info_row("Вы", "me"),
        info_row("Связь", "online"),
        info_row("Треков в библиотеке", "tracks"),
        info_row("Место на диске", "disk"),
        info_row("Сканирование", "scan"),
        info_row("Последнее сканирование", "last_scan"),
        info_row("Ошибка сканирования", "last_error"),
        info_row("Версия сервера", "version"),
    ]
    status_msg = _text("", server_labelCol)

    def set_value(key, text, col=None):
        values[key].value = text
        values[key].color = col or server_textCol

    def probe():
        """ping в обход фонового опроса (probe=True внутри ping): экран должен
        показывать, что сервер ответил сейчас, а не 60 секунд назад."""
        t0 = time.perf_counter()
        info = sources.REMOTE.ping()
        return info, (time.perf_counter() - t0) * 1000

    def show_me():
        if not me["known"]:
            set_value("me", "—", server_labelCol)
        elif me["name"] is None:
            set_value("me", "сервер без токенов: удаление выключено", server_labelCol)
        else:
            set_value("me", f"{me['name']} ({'администратор' if me['admin'] else 'пользователь'})")

    async def load_me():
        try:
            info = await asyncio.to_thread(sources.REMOTE.me)
            me.update(name=info.get("name"), admin=bool(info.get("admin")), known=True)
        except sources.RemoteNotFound:
            me.update(name=None, admin=False, known=False)
            files_msg.value = "Сервер старой версии: нужен server 0.2 (обновите код на Pi)"
            files_msg.color = server_errCol
        except sources.RemoteUnavailable:
            return
        show_me()
        update_files_actions()
        ops_all.visible = me["admin"]
        safe_update()

    async def refresh_status(e=None):
        info, rtt = await asyncio.to_thread(probe)
        if not alive[0]:
            return
        set_value("url", sources.SRV_BASE_URL or "не задан")
        set_value("token", "задан" if sources.SRV_TOKEN else "не задан (сервер должен быть открыт)")
        show_me()
        if info is None:
            reason = _error_text(None) if not sources.SRV_ENABLED else "нет ответа (подробности в логе плеера)"
            set_value("online", reason, server_errCol)
            for key in ("tracks", "disk", "scan", "last_scan", "last_error", "version"):
                set_value(key, "—", server_labelCol)
        else:
            if not me["known"]:
                page.run_task(load_me)
            set_value("online", f"онлайн, ответ за {rtt:.0f} мс", server_okCol)
            set_value("tracks", f"{info.get('tracks', '?')}")
            if info.get("disk_total"):
                set_value("disk", f"свободно {_size(info['disk_free'])} из {_size(info['disk_total'])}")
            else:
                set_value("disk", "неизвестно (сервер старой версии или диск не смонтирован)", server_labelCol)
            if info.get("scan_running"):
                set_value("scan", f"идёт: {info.get('scan_progress') or '…'}")
            else:
                set_value("scan", "не идёт")
            set_value("last_scan", _ago(info.get("last_scan")))
            err = info.get("last_error")
            set_value("last_error", err or "нет", server_errCol if err else None)
            set_value("version", f"{info.get('server version', '?')} (FastAPI {info.get('fastapi version', '?')})")
        safe_update()

    async def on_rescan(e):
        status_msg.value, status_msg.color = "Запускаю…", server_labelCol
        page.update()
        try:
            result = await asyncio.to_thread(sources.REMOTE.rescan)
            status_msg.value = "Сканирование запущено" if result == "started" else "Сканирование уже идёт"
            status_msg.color = server_okCol
        except (sources.RemoteUnavailable, sources.RemoteNotFound) as err:
            status_msg.value, status_msg.color = f"Не удалось: {_error_text(err)}", server_errCol
        await refresh_status()

    async def status_loop():
        while alive[0]:
            await asyncio.sleep(STATUS_REFRESH_SEC)
            if alive[0]:
                await refresh_status()

    status_card = _card("Состояние", [
        *status_rows,
        ft.Row([
            _button("Обновить", refresh_status, ft.Icons.REFRESH),
            _button("Пересканировать", on_rescan, ft.Icons.MANAGE_SEARCH),
        ], wrap=True),
        status_msg,
    ], col={"md": 6})

    # ======================= Буфер сети =======================

    def clamp(ms):
        return int(min(sources.CACHING_MAX, max(sources.CACHING_MIN, ms)))

    caching_value = _text(f"{clamp(sources.SRV_CACHING)} мс", weight=ft.FontWeight.BOLD)
    caching_current = _text(f"Сейчас: {sources.SRV_CACHING} мс", server_labelCol)

    def on_slide(e):
        caching_value.value = f"{int(e.control.value)} мс"
        caching_value.update()

    caching_slider = ft.Slider(
        min=sources.CACHING_MIN, max=sources.CACHING_MAX,
        divisions=(sources.CACHING_MAX - sources.CACHING_MIN) // 100,
        value=clamp(sources.SRV_CACHING), label="{value} мс",
        thumb_color=server_sliderThumbCol, expand=True,
        on_change=on_slide,
    )
    measure_ring = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
    measure_text = _text("", server_labelCol, selectable=True)
    caching_msg = _text("")

    async def on_measure(e):
        measure_btn.disabled = True
        measure_ring.visible = True
        measure_text.value, measure_text.color = "Замеряю: 5 запросов и первые 2 МБ трека…", server_labelCol
        page.update()
        uri = ui_utils.current_uri if sources.is_remote(ui_utils.current_uri) else None
        try:
            m = await asyncio.to_thread(sources.REMOTE.measure_link, uri)
            rec = sources.recommend_caching(m)
            bitrate = f"{m['bitrate_kbps']} кбит/с" if m["bitrate_kbps"] else "битрейт неизвестен"
            measure_text.value = (
                f"Ответ сервера: в среднем {m['rtt_avg']:.0f} мс, худший {m['rtt_max']:.0f} мс\n"
                f"Скорость: {m['speed_kbps'] / 1000:.1f} Мбит/с — трек «{m['track']}», {bitrate}\n"
                f"Рекомендация: {rec} мс (выставлено на ползунке, сохраняется кнопкой «Применить»)")
            measure_text.color = server_textCol
            caching_slider.value = rec
            caching_value.value = f"{rec} мс"
        except (sources.RemoteUnavailable, sources.RemoteNotFound) as err:
            measure_text.value, measure_text.color = f"Замер не удался: {_error_text(err)}", server_errCol
        except Exception as err:
            logger.exception("замер связи")
            measure_text.value, measure_text.color = f"Замер не удался: {err}", server_errCol
        measure_btn.disabled = False
        measure_ring.visible = False
        safe_update()

    async def on_apply(e):
        ms = int(caching_slider.value)
        try:
            await asyncio.to_thread(sources.set_network_caching, ms)
            caching_msg.value = f"Сохранено: {ms} мс. Действует со следующего трека"
            caching_msg.color = server_okCol
            caching_current.value = f"Сейчас: {ms} мс"
        except OSError as err:
            caching_msg.value, caching_msg.color = f"Не удалось записать config.txt: {err}", server_errCol
        page.update()

    measure_btn = _button("Подобрать", on_measure, ft.Icons.SPEED)

    caching_card = _card("Буфер сети (network_caching)", [
        _text("Сколько звука VLC накапливает, прежде чем начать играть серверный трек. "
              "Меньше — быстрее старт и перемотка, больше — меньше обрывов на плохой связи.",
              server_labelCol),
        ft.Row([caching_slider, ft.Container(caching_value, width=80)]),
        caching_current,
        ft.Row([
            measure_btn,
            _button("Применить", on_apply, ft.Icons.CHECK),
            measure_ring,
        ], wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        measure_text,
        caching_msg,
    ], col={"md": 6})

    server_tab = ft.Column(
        [ft.ResponsiveRow([status_card, caching_card], spacing=16, run_spacing=16)],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    # ======================= Файлы =======================
    # Уровень открытой папки решает, что загружается (§3): корень — папка исполнителя,
    # исполнитель — папка альбома, альбом — файлы или папка, которая сливается в альбом.

    cur = [""]                 # открытая папка сервера (rel), "" — корень
    load_seq = [0]             # ответ на старый клик по папке не перерисовывает новую
    crumbs_row = ft.Row(wrap=True, spacing=0)
    files_hint = _text("", server_labelCol)
    files_msg = _text("")
    files_ring = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
    files_list = ft.ListView(expand=True, spacing=0)

    LEVEL_HINTS = {
        0: "Здесь — папки исполнителей. Загрузка: выберите на ПК папку исполнителя с альбомами внутри.",
        1: "Здесь — альбомы. Загрузка: выберите на ПК папку альбома; подпапки CD1, CD2 сольются в альбом.",
        2: "Здесь — треки и картинки альбома. Загрузка: файлы или папка, её содержимое ляжет в этот альбом.",
    }

    def level():
        return transfers.upload_level(cur[0])

    async def on_upload_folder(e):
        await start_upload_flow(folder=True)

    async def on_upload_files(e):
        await start_upload_flow(folder=False)

    async def on_download_here(e):
        name = cur[0].rsplit("/", 1)[-1]
        await start_download(cur[0], True, 0, name)

    async def on_delete_here(e):
        await ask_delete(cur[0], True)

    async def on_refresh_dir(e):
        await load_dir(cur[0])

    up_folder_btn = _button("Загрузить папку", on_upload_folder, ft.Icons.DRIVE_FOLDER_UPLOAD)
    up_files_btn = _button("Загрузить файлы", on_upload_files, ft.Icons.UPLOAD_FILE)
    down_btn = _button("Скачать папку", on_download_here, ft.Icons.DOWNLOAD)
    del_btn = _button("Удалить папку", on_delete_here, ft.Icons.DELETE_OUTLINE, bgcolor=server_errCol)

    def update_files_actions():
        lv = level()
        up_folder_btn.content = {0: "Загрузить исполнителя", 1: "Загрузить альбом"}.get(lv, "Загрузить папку")
        up_folder_btn.disabled = lv > 2
        up_files_btn.visible = lv == 2
        down_btn.visible = lv >= 1
        del_btn.visible = lv >= 1 and me["admin"]
        files_hint.value = LEVEL_HINTS.get(lv, "Глубже альбома загружать нельзя: строго Исполнитель/Альбом/трек.")

    def go(rel):
        files_msg.value = ""   # сообщение относится к прошлой папке
        page.run_task(load_dir, rel)

    def build_crumbs():
        parts = [p for p in cur[0].split("/") if p]
        items = [("Корень", "")] + [(p, "/".join(parts[:i + 1])) for i, p in enumerate(parts)]
        ctrls = []
        for i, (label, rel) in enumerate(items):
            if i:
                ctrls.append(_text("›", server_labelCol))
            last = i == len(items) - 1
            ctrls.append(ft.TextButton(
                content=_text(label, server_textCol if last else server_labelCol,
                              weight=ft.FontWeight.BOLD if last else None),
                on_click=(lambda e, r=rel: go(r)), disabled=last,
            ))
        crumbs_row.controls = ctrls

    def file_row(icon, name, size_text, on_open=None, on_download=None, on_delete=None):
        actions = []
        if on_download:
            actions.append(ft.IconButton(ft.Icons.DOWNLOAD, icon_size=18, tooltip="Скачать",
                                         on_click=on_download, icon_color=server_iconCol))
        if on_delete and me["admin"]:
            actions.append(ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=18, tooltip="Удалить",
                                         on_click=on_delete, icon_color=server_errCol))
        return ft.Container(
            height=server_rowHeight,
            padding=ft.Padding.symmetric(horizontal=8),
            on_click=on_open,
            border_radius=6,
            content=ft.Row([
                ft.Icon(icon, size=18, color=server_iconCol),
                ft.Container(_text(name, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS), expand=True),
                _text(size_text, server_labelCol),
                *actions,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    async def load_dir(rel):
        load_seq[0] += 1
        seq = load_seq[0]
        files_ring.visible = True
        safe_update()
        try:
            data = await asyncio.to_thread(sources.REMOTE.ls, rel)
        except (sources.RemoteUnavailable, sources.RemoteNotFound) as err:
            if seq != load_seq[0]:
                return
            files_ring.visible = False
            if isinstance(err, sources.RemoteNotFound) and rel:
                files_msg.value, files_msg.color = "Папки больше нет — открыт корень", server_errCol
                await load_dir("")
                return
            files_msg.value, files_msg.color = f"Не загрузить список: {_error_text(err)}", server_errCol
            safe_update()
            return
        if seq != load_seq[0] or not alive[0]:
            return
        cur[0] = rel
        rows = []
        for d in data["dirs"]:
            rows.append(file_row(
                ft.Icons.FOLDER, d["name"], "",
                on_open=lambda e, p=d["path"]: go(p),
                on_download=lambda e, p=d["path"], n=d["name"]: page.run_task(start_download, p, True, 0, n),
                on_delete=lambda e, p=d["path"]: page.run_task(ask_delete, p, True),
            ))
        for f in data["files"]:
            rows.append(file_row(
                ft.Icons.AUDIO_FILE if f["kind"] == "audio" else ft.Icons.IMAGE, f["name"], _size(f["size"]),
                on_download=lambda e, f=f: page.run_task(start_download, f["path"], False, f["size"], f["name"]),
                on_delete=lambda e, p=f["path"]: page.run_task(ask_delete, p, False),
            ))
        if not rows:
            rows.append(ft.Container(_text("Папка пуста", server_labelCol), padding=8))
        files_list.controls = rows
        files_ring.visible = False
        build_crumbs()
        update_files_actions()
        safe_update()

    # ---- загрузка ----

    async def start_upload_flow(folder: bool):
        if transfers.busy():
            files_msg.value, files_msg.color = "Дождитесь окончания текущей передачи", server_errCol
            safe_update()
            return
        dest = cur[0]
        lv = level()
        if folder:
            title = {0: "Папка исполнителя", 1: "Папка альбома"}.get(lv, "Папка для альбома")
            path = await picker.get_directory_path(dialog_title=title)
            if not path:
                return
            args = {"folder": path}
        else:
            picked = await picker.pick_files(
                dialog_title="Треки и картинки альбома", allow_multiple=True,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=[x.lstrip(".") for x in sorted(transfers.AUDIO_EXT | transfers.IMAGE_EXT)])
            paths = [f.path for f in picked or [] if f.path]
            if not paths:
                return
            args = {"files": paths}
        files_ring.visible = True
        files_msg.value, files_msg.color = "Готовлю список…", server_labelCol
        safe_update()

        def build():
            scope = transfers.existing_scope(dest, args.get("folder"))
            existing = transfers.fetch_existing(scope) if scope else set()
            return transfers.plan_upload(dest, existing=existing, **args)

        try:
            plan = await asyncio.to_thread(build)
        except (sources.RemoteUnavailable, sources.RemoteNotFound) as err:
            files_ring.visible = False
            files_msg.value, files_msg.color = f"Не получить список с сервера: {_error_text(err)}", server_errCol
            safe_update()
            return
        files_ring.visible = False
        files_msg.value = ""
        show_preview(plan)

    def show_preview(plan: transfers.Plan):
        where = f"«{plan.dest}»" if plan.dest else "корень"
        picks = [0] * len(plan.conflicts)
        summary = _text("", weight=ft.FontWeight.BOLD)
        go_btn = _button("Загрузить", None, ft.Icons.UPLOAD)

        def strip(rel):
            return rel[len(plan.dest) + 1:] if plan.dest else rel

        def recount():
            items = plan.chosen(picks)
            summary.value = f"Загрузится {len(items)} файлов, {_size(sum(i.size for i in items))}"
            go_btn.content = f"Загрузить {len(items)}"
            go_btn.disabled = not items

        body = []
        if plan.error:
            body.append(_text(plan.error, server_errCol))
        else:
            body.append(summary)
        if plan.conflicts:
            body.append(_text("Одинаковые имена после слияния дисков — выберите, какой файл оставить:",
                              server_warnCol, weight=ft.FontWeight.BOLD))
            for gi, group in enumerate(plan.conflicts):
                def on_pick(e, gi=gi):
                    picks[gi] = None if e.control.value == "none" else int(e.control.value)
                    recount()
                    go_btn.update()
                    summary.update()

                body.append(ft.Column([
                    _text(strip(group[0].rel), server_warnCol),
                    ft.RadioGroup(value="0", on_change=on_pick, content=ft.Column([
                        *[ft.Radio(value=str(i), label=f"{it.shown}  ({_size(it.size)})")
                          for i, it in enumerate(group)],
                        ft.Radio(value="none", label="не загружать"),
                    ], spacing=0)),
                ], spacing=2))
        if plan.items:
            body.append(_text(f"Без вопросов ({len(plan.items)}):", weight=ft.FontWeight.BOLD))
            items = sorted(plan.items, key=lambda i: i.rel.lower())
            for it in items[:PREVIEW_MAX_ROWS]:
                body.append(_text(f"✔ {strip(it.rel)}   {_size(it.size)}"))
            if len(items) > PREVIEW_MAX_ROWS:
                body.append(_text(f"…и ещё {len(items) - PREVIEW_MAX_ROWS}", server_labelCol))
        if plan.skipped:
            body.append(_text(f"Пропущено ({len(plan.skipped)}):", weight=ft.FontWeight.BOLD))
            for shown, why in plan.skipped[:PREVIEW_MAX_ROWS]:
                body.append(_text(f"✖ {shown} — {why}", server_labelCol))
            if len(plan.skipped) > PREVIEW_MAX_ROWS:
                body.append(_text(f"…и ещё {len(plan.skipped) - PREVIEW_MAX_ROWS}", server_labelCol))

        async def do_upload(e):
            items = plan.chosen(picks)
            page.pop_dialog()
            run_transfer("upload", f"Загрузка в {where}", lambda t: t.start_upload(plan.dest, items))

        go_btn.on_click = do_upload
        recount()
        actions = [ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog())]
        if not plan.error:
            actions.append(go_btn)
        page.show_dialog(ft.AlertDialog(
            title=ft.Text(f"Загрузка в {where}"),
            content=ft.Container(width=680, height=480,
                                 content=ft.Column(body, scroll=ft.ScrollMode.AUTO, spacing=4)),
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    # ---- скачивание, удаление ----

    async def start_download(rel, is_dir, size, name):
        if transfers.busy():
            files_msg.value, files_msg.color = "Дождитесь окончания текущей передачи", server_errCol
            safe_update()
            return
        local = await picker.get_directory_path(
            dialog_title="Куда скачать (структура Исполнитель/Альбом сохранится)")
        if not local:
            return
        run_transfer("download", f"Скачивание «{name}» → {local}",
                     lambda t: t.start_download(rel, is_dir, size, local))

    async def ask_delete(rel, is_dir):
        name = rel.rsplit("/", 1)[-1]
        if not is_dir:
            confirm("Удалить файл?", f"«{rel}» будет удалён с сервера. Это нельзя отменить.",
                    "Удалить", lambda: do_delete(rel), danger=True)
            return
        files_ring.visible = True
        safe_update()
        try:
            listed = await asyncio.to_thread(sources.REMOTE.list_files, rel)
        except (sources.RemoteUnavailable, sources.RemoteNotFound) as err:
            files_ring.visible = False
            files_msg.value, files_msg.color = f"Не удалось: {_error_text(err)}", server_errCol
            safe_update()
            return
        files_ring.visible = False
        safe_update()
        total = sum(f["size"] for f in listed)
        confirm(f"Удалить папку «{name}»?",
                f"С сервера будет удалена папка «{rel}» целиком: {len(listed)} файлов, {_size(total)}. "
                "Это нельзя отменить.",
                "Удалить", lambda: do_delete(rel), danger=True)

    async def do_delete(rel):
        try:
            r = await asyncio.to_thread(sources.REMOTE.delete, rel)
            files_msg.value, files_msg.color = f"Удалено: {r['deleted']} (файлов: {r['files']})", server_okCol
        except (sources.RemoteUnavailable, sources.RemoteNotFound) as err:
            files_msg.value, files_msg.color = f"Не удалось удалить: {_error_text(err)}", server_errCol
        # удалили открытую папку — подняться к ближайшей живой
        target = cur[0]
        while target and (target == rel or target.startswith(rel + "/")):
            target = target.rsplit("/", 1)[0] if "/" in target else ""
        await load_dir(target)

    files_tab = ft.Column([
        crumbs_row,
        ft.Row([up_folder_btn, up_files_btn, down_btn, del_btn,
                ft.IconButton(ft.Icons.REFRESH, tooltip="Обновить", on_click=on_refresh_dir),
                files_ring], wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        files_hint,
        files_msg,
        ft.Divider(height=1, color=server_cardBorderCol),
        files_list,
    ], expand=True, spacing=8)

    # ======================= Операции =======================

    ops_list = ft.ListView(expand=True, spacing=6)
    ops_msg = _text("", server_labelCol)

    async def on_ops_all(e):
        await load_ops()

    ops_all = ft.Checkbox(label="Все пользователи", value=False, visible=False, on_change=on_ops_all)

    async def on_refresh_ops(e):
        await load_ops()

    async def load_ops():
        try:
            ops = await asyncio.to_thread(sources.REMOTE.ops, not ops_all.value)
        except (sources.RemoteUnavailable, sources.RemoteNotFound) as err:
            ops_msg.value, ops_msg.color = f"Не загрузить список: {_error_text(err)}", server_errCol
            safe_update()
            return
        if not alive[0]:
            return
        ops_msg.value, ops_msg.color = ("Загрузок пока не было" if not ops else
                                        "Откат удаляет только файлы, которые с загрузки никто не менял."), server_labelCol
        rows = []
        for op in ops:
            when = datetime.datetime.fromtimestamp(op["created"]).strftime("%d.%m %H:%M")
            who = f"{op['who'] or 'аноним'} · " if ops_all.value else ""
            if op["present"] == 0:
                state, col = "откачена" if op["undone"] else "файлов уже нет", server_labelCol
            elif op["undone"]:
                state, col = f"откачена частично, на сервере {op['present']}", server_warnCol
            elif op["present"] < op["files"]:
                state, col = f"на сервере {op['present']} из {op['files']}", server_textCol
            else:
                state, col = "на сервере", server_okCol
            undo_btn = _button("Откатить", lambda e, op=op: ask_undo(op), ft.Icons.UNDO)
            undo_btn.visible = op["present"] > 0
            rows.append(ft.Container(
                padding=12, bgcolor=server_cardBGCol, border_radius=server_cardRadius,
                border=ft.Border.all(1, server_cardBorderCol),
                content=ft.Row([
                    ft.Column([
                        _text(f"{when} · {who}{op['folder'] or '/'}", weight=ft.FontWeight.BOLD),
                        _text(f"{op['files']} файлов, {_size(op['bytes'])} · {state}", col),
                    ], spacing=2, expand=True),
                    undo_btn,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ))
        ops_list.controls = rows
        safe_update()

    def ask_undo(op):
        confirm("Откатить загрузку?",
                f"С сервера будут удалены файлы этой загрузки ({op['present']} шт.) из «{op['folder']}». "
                "Изменённые после загрузки файлы останутся.",
                "Откатить", lambda: do_undo(op["op_id"]), danger=True)

    async def do_undo(op_id):
        try:
            r = await asyncio.to_thread(sources.REMOTE.undo, op_id)
        except (sources.RemoteUnavailable, sources.RemoteNotFound) as err:
            show_message("Откат не удался", [_error_text(err)], server_errCol)
            return
        lines = [f"Удалено файлов: {len(r['removed'])}"]
        if r["skipped"]:
            lines.append(f"Не тронуто: {len(r['skipped'])}")
            lines += [f"  {s['path']} — {s['reason']}" for s in r["skipped"]]
        show_message("Откат выполнен", lines)
        await load_ops()
        await load_dir(cur[0])

    ops_tab = ft.Column([
        ft.Row([_button("Обновить", on_refresh_ops, ft.Icons.REFRESH), ops_all],
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ops_msg,
        ops_list,
    ], expand=True, spacing=8)

    # ======================= Полоса передачи =======================

    bar_icon = ft.Icon(ft.Icons.UPLOAD, color=server_iconCol)
    bar_title = _text("", weight=ft.FontWeight.BOLD, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)
    bar_detail = _text("", server_labelCol, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)
    bar_progress = ft.ProgressBar(value=0, color=server_progressCol, bgcolor=server_cardBorderCol)
    last_snap = [None]

    def on_cancel(e):
        if transfers.current is not None:
            transfers.current.cancel.set()
            bar_cancel.disabled = True
            bar_detail.value = "Отменяю…"
            safe_update()

    def on_undo_last(e):
        snap = last_snap[0]
        if snap and snap.op_id:
            confirm("Откатить эту загрузку?",
                    f"Будут удалены загруженные файлы ({snap.ok} шт.).",
                    "Откатить", lambda: do_undo(snap.op_id), danger=True)

    def on_details(e):
        snap = last_snap[0]
        if not snap:
            return
        lines = [f"Готово: {snap.ok}"]
        if snap.message:
            lines.append(snap.message)
        if snap.failed:
            lines.append(f"Ошибки ({len(snap.failed)}):")
            lines += [f"  {f} — {why}" for f, why in snap.failed]
        if snap.skipped:
            lines.append(f"Пропущено ({len(snap.skipped)}):")
            lines += [f"  {f} — {why}" for f, why in snap.skipped]
        show_message(snap.title, lines)

    def on_hide(e):
        bar.visible = False
        safe_update()

    bar_cancel = ft.TextButton("Отмена", on_click=on_cancel)
    bar_undo = ft.TextButton("Откатить загруженное", on_click=on_undo_last)
    bar_more = ft.TextButton("Подробнее", on_click=on_details)
    bar_hide = ft.IconButton(ft.Icons.CLOSE, tooltip="Скрыть", on_click=on_hide, icon_size=18)

    bar = ft.Container(
        visible=False,
        padding=12,
        bgcolor=server_progressBGCol,
        border=ft.Border.all(1, server_cardBorderCol),
        border_radius=server_cardRadius,
        content=ft.Column([
            ft.Row([bar_icon, ft.Container(bar_title, expand=True), bar_cancel, bar_undo, bar_more, bar_hide],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bar_progress,
            bar_detail,
        ], spacing=6),
    )

    def show_snapshot(s: transfers.Snapshot):
        last_snap[0] = s
        bar.visible = True
        bar_icon.icon = ft.Icons.UPLOAD if s.kind == "upload" else ft.Icons.DOWNLOAD
        running = s.state == "running"
        bar_progress.value = (s.done_bytes / s.total_bytes) if s.total_bytes else (None if running else 1)
        if running:
            left = (s.total_bytes - s.done_bytes) / s.speed if s.speed > 0 else 0
            bar_title.value = f"{s.title}: {s.index}/{s.total} — {s.file.rsplit('/', 1)[-1]}"
            bar_detail.value = (f"{_size(s.done_bytes)} из {_size(s.total_bytes)} · {_size(s.speed)}/с"
                                + (f" · осталось ~{_duration(left)}" if left else ""))
        else:
            word = {"done": "готово", "cancelled": "отменено", "stopped": "остановлено"}[s.state]
            bar_title.value = f"{s.title}: {word}"
            parts = [f"успешно {s.ok}"]
            if s.skipped:
                parts.append(f"пропущено {len(s.skipped)}")
            if s.failed:
                parts.append(f"ошибок {len(s.failed)}")
            bar_detail.value = ", ".join(parts) + (f" · {s.message}" if s.message else "")
        bar_cancel.visible = running
        bar_cancel.disabled = False if running else bar_cancel.disabled
        bar_undo.visible = (not running and s.kind == "upload" and s.ok > 0
                            and s.state in ("cancelled", "stopped") and bool(s.op_id))
        bar_more.visible = not running and bool(s.skipped or s.failed or s.message)
        bar_hide.visible = not running

    def on_progress(topic, s):
        if not alive[0]:
            return
        show_snapshot(s)
        if s.state != "running":
            page.run_task(load_dir, cur[0])
            if s.kind == "upload":
                page.run_task(load_ops)
        safe_update()

    def run_transfer(kind, title, start):
        t = transfers.Transfer(kind, title, lambda snap: page.pubsub.send_all_on_topic(PROGRESS_TOPIC, snap))
        transfers.current = t
        bar_cancel.disabled = False
        show_snapshot(t.snap)
        safe_update()
        start(t)

    # ======================= Экран =======================

    tabs = ft.Tabs(
        length=3,
        selected_index=0,
        expand=True,
        content=ft.Column(expand=True, controls=[
            ft.TabBar(
                scrollable=False,
                indicator_color=server_tabIndicatorCol,
                label_color=server_textCol,
                unselected_label_color=server_labelCol,
                divider_color=server_cardBorderCol,
                tabs=[ft.Tab(label="Сервер"), ft.Tab(label="Файлы"), ft.Tab(label="Операции")],
            ),
            ft.TabBarView(expand=True, controls=[
                ft.Container(server_tab, padding=ft.Padding.only(top=12)),
                ft.Container(files_tab, padding=ft.Padding.only(top=12)),
                ft.Container(ops_tab, padding=ft.Padding.only(top=12)),
            ]),
        ]),
    )

    def close(e=None):
        alive[0] = False
        page.pubsub.unsubscribe_topic(PROGRESS_TOPIC)
        if view in page.views:
            page.views.remove(view)
        page.on_view_pop = prev_on_view_pop
        page.update()

    prev_on_view_pop = page.on_view_pop

    def on_view_pop(e):
        # системный «назад» (Esc, жест) для нашего экрана; чужие — прежнему обработчику
        if e.view is view:
            close()
        elif prev_on_view_pop:
            prev_on_view_pop(e)

    view = ft.View(
        route=ROUTE,
        bgcolor=server_BGCol,
        padding=16,
        appbar=ft.AppBar(
            leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=close, tooltip="Назад к плееру"),
            title=ft.Text("Отладочный режим", color=server_textCol),
            bgcolor=server_appbarBGCol,
        ),
        controls=[ft.Column([tabs, bar], expand=True, spacing=12)],
    )

    page.pubsub.subscribe_topic(PROGRESS_TOPIC, on_progress)
    page.on_view_pop = on_view_pop
    page.views.append(view)
    update_files_actions()
    build_crumbs()
    # передача, начатая до прошлого закрытия экрана, ещё идёт или закончилась — показать её
    if transfers.current is not None:
        show_snapshot(transfers.current.snap)
    page.update()
    page.run_task(refresh_status)
    page.run_task(status_loop)
    page.run_task(load_me)
    page.run_task(load_dir, "")
    page.run_task(load_ops)
