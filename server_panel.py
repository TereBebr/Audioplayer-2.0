"""«Отладочный режим» сервера — отдельный экран поверх плеера (page.views).

ТЗ: docs/TZ_server_panel.md. Этап 1 — состояние сервера и буфер сети VLC.
Точка входа — open_server_panel(page), её вызывает кнопка в gui2.py.

Сеть — только через asyncio.to_thread внутри async-обработчиков: так ожидание
ответа Pi не держит интерфейс, а контролы обновляются из цикла событий Flet,
а не из постороннего потока (оттуда изменения до клиента не доходят).
"""
import asyncio
import configparser
import datetime
import logging
import time

import flet as ft

import sources
import ui_utils

logger = logging.getLogger(__name__)

ROUTE = "/server"
STATUS_REFRESH_SEC = 5   # как часто обновлять «Состояние», пока экран открыт

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
server_sliderThumbCol = config.get('UI server', 'server_sliderThumbCol', fallback=config.get('UI Settings', 'sliderThumbCol', fallback='indigo800')) # Ползунок буфера
server_buttonBGCol = config.get('UI server', 'server_buttonBGCol', fallback=config.get('UI Settings', 'buttonBGCol', fallback='blue')) # Фон кнопок
server_buttonTextCol = config.get('UI server', 'server_buttonTextCol', fallback=config.get('UI Settings', 'buttonTextCol', fallback='white')) # Текст кнопок


def _text(value="", col=None, **kw):
    return ft.Text(value, size=server_textSize, color=col or server_textCol, **kw)


def _button(text, on_click, icon=None):
    return ft.Button(
        content=text, icon=icon, on_click=on_click,
        bgcolor=server_buttonBGCol, color=server_buttonTextCol,
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


def _error_text(err):
    """Исключение источника — в строку для экрана."""
    if not sources.SRV_ENABLED:
        return "Сервер выключен в config.txt ([Server] enabled)"
    return str(err) or err.__class__.__name__


def open_server_panel(page: ft.Page):
    """Открыть экран поверх плеера. Повторный вызов, пока экран открыт, ничего не делает."""
    if any(v.route == ROUTE for v in page.views):
        return

    alive = [True]   # экран открыт; фоновое обновление «Состояния» по нему останавливается

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
        info_row("Связь", "online"),
        info_row("Треков в библиотеке", "tracks"),
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

    async def refresh_status(e=None):
        info, rtt = await asyncio.to_thread(probe)
        if not alive[0]:
            return
        set_value("url", sources.SRV_BASE_URL or "не задан")
        set_value("token", "задан" if sources.SRV_TOKEN else "не задан (сервер должен быть открыт)")
        if info is None:
            reason = _error_text(None) if not sources.SRV_ENABLED else "нет ответа (подробности в логе плеера)"
            set_value("online", reason, server_errCol)
            for key in ("tracks", "scan", "last_scan", "last_error", "version"):
                set_value(key, "—", server_labelCol)
        else:
            set_value("online", f"онлайн, ответ за {rtt:.0f} мс", server_okCol)
            set_value("tracks", f"{info.get('tracks', '?')}")
            if info.get("scan_running"):
                set_value("scan", f"идёт: {info.get('scan_progress') or '…'}")
            else:
                set_value("scan", "не идёт")
            set_value("last_scan", _ago(info.get("last_scan")))
            err = info.get("last_error")
            set_value("last_error", err or "нет", server_errCol if err else None)
            set_value("version", f"{info.get('server version', '?')} (FastAPI {info.get('fastapi version', '?')})")
        try:
            page.update()
        except (RuntimeError, AssertionError):
            pass

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
        if alive[0]:
            page.update()

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

    # ======================= Экран =======================

    def close(e=None):
        alive[0] = False
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
        controls=[
            ft.Column(
                [ft.ResponsiveRow([status_card, caching_card], spacing=16, run_spacing=16)],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
        ],
    )

    page.on_view_pop = on_view_pop
    page.views.append(view)
    page.update()
    page.run_task(refresh_status)
    page.run_task(status_loop)
