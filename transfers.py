"""Загрузка музыки на сервер и скачивание с него — для экрана «Отладочный режим».

ТЗ: docs/TZ_server_panel.md §3, §5. Без Flet: экран (server_panel.py) получает
отсюда план загрузки и снимки прогресса, а сам показывает их.

- plan_upload: что из выбранного на ПК куда ляжет на сервере, что пропущено и почему,
  какие файлы после слияния CD1/CD2 получили одно имя (выбирает пользователь);
- Transfer: одна передача в фоновом потоке, файлы по одному, отмена — threading.Event.

Правила структуры — копия server/uploads.py (у плеера и сервера разные сборки).
Сервер проверяет их ещё раз, так что расхождение даст 400, а не кашу на диске.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import sources

logger = logging.getLogger(__name__)

# ---- правила §3: копия server/uploads.py, менять обе ----

AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".mp4"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
COVERS_DIR = "covers"
_BAD_CHARS = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
_SKIP_DIRS = {"covers", "lost+found", "$recycle.bin", "system volume information", ".cache"}
MAX_NAME = 200

CHUNK = 256 * 1024
PROGRESS_EVERY = 0.2   # с, не чаще — снимок прогресса в UI
MAX_FAILS_IN_ROW = 3   # столько ошибок связи подряд — передача останавливается


def file_kind(name: str) -> str | None:
    ext = os.path.splitext(name)[1].lower()
    if ext in AUDIO_EXT:
        return "audio"
    if ext in IMAGE_EXT:
        return "image"
    return None


def name_error(name: str) -> str | None:
    """Почему имя нельзя положить на сервер, или None."""
    if not name or name in (".", ".."):
        return "пустое имя"
    if len(name) > MAX_NAME:
        return f"имя длиннее {MAX_NAME} символов"
    if name.startswith("."):
        return "имя начинается с точки"
    if name[-1] in ". ":
        return "точка или пробел в конце имени"
    if set(name) & _BAD_CHARS:
        return "недопустимые символы в имени"
    if os.path.splitext(name)[0].lower() in _RESERVED:
        return "зарезервированное имя Windows"
    return None


def upload_level(dest: str) -> int:
    """Глубина открытой папки сервера: 0 — корень, 1 — исполнитель, 2 — альбом."""
    return len([p for p in dest.split("/") if p])


# ---- план загрузки ----

@dataclass
class Item:
    src: str     # локальный путь
    rel: str     # путь на сервере
    size: int
    shown: str   # как показать источник: путь от выбранной папки


@dataclass
class Plan:
    dest: str                                       # открытая папка сервера
    items: list[Item] = field(default_factory=list)            # без вопросов
    conflicts: list[list[Item]] = field(default_factory=list)  # одно имя на сервере — выбрать один
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (что, почему)
    error: str | None = None                        # загрузка целиком невозможна

    def chosen(self, picks: list[int | None]) -> list[Item]:
        """Итоговый список: items + по одному из каждого конфликта (None — ни одного)."""
        out = list(self.items)
        for group, i in zip(self.conflicts, picks):
            if i is not None:
                out.append(group[i])
        out.sort(key=lambda it: it.rel.lower())
        return out


def _album_files(plan: Plan, album: list[str], src_dir: Path, label: str):
    """Содержимое одной локальной папки альбома → файлы альбома на сервере.
    Аудио из любых подпапок (CD1, CD2) — в сам альбом, картинки из подпапок — в covers/."""
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        sub = Path(root).relative_to(src_dir).parts
        for name in sorted(files):
            _map_file(plan, album, Path(root) / name, sub, "/".join((label, *sub, name)))


def _map_file(plan: Plan, album: list[str], path: Path, sub: tuple, shown: str):
    kind = file_kind(path.name)
    if kind is None:
        plan.skipped.append((shown, "тип файла не переносится"))
        return
    err = name_error(path.name)
    if err:
        plan.skipped.append((shown, err))
        return
    in_covers = any(p.lower() == COVERS_DIR for p in sub)
    if kind == "audio":
        if in_covers:
            plan.skipped.append((shown, "трек в папке covers"))
            return
        rel = "/".join((*album, path.name))
    else:
        rel = "/".join((*album, path.name)) if not sub else "/".join((*album, COVERS_DIR, path.name))
    try:
        size = path.stat().st_size
    except OSError as e:
        plan.skipped.append((shown, f"не прочитать: {e}"))
        return
    plan.items.append(Item(str(path), rel, size, shown))


def _check_folder_names(plan: Plan, names: list[str]) -> bool:
    for n in names:
        err = name_error(n)
        if err:
            plan.error = f"Папка «{n}»: {err}"
            return False
        if n.lower() in _SKIP_DIRS:
            plan.error = f"Папка «{n}» не может быть исполнителем или альбомом"
            return False
    return True


def plan_upload(dest: str, folder: str | None = None, files: list[str] | None = None,
                existing: set[str] | None = None) -> Plan:
    """Раскладка выбранного на ПК по правилам §3.

    dest — открытая папка сервера. На уровне корня folder — папка исполнителя,
    на уровне исполнителя — папка альбома, на уровне альбома — files или folder,
    содержимое которой сливается в альбом. existing — rel_path файлов, уже лежащих
    на сервере (регистр не важен)."""
    plan = Plan(dest=dest)
    parts = [p for p in dest.split("/") if p]
    level = len(parts)
    if level > 2:
        plan.error = "Загружать можно только в корень, в папку исполнителя или альбома"
        return plan

    if level == 2:
        if files:
            for f in files:
                p = Path(f)
                _map_file(plan, parts, p, (), p.name)
        elif folder:
            src = Path(folder)
            _album_files(plan, parts, src, src.name)
    elif folder:
        src = Path(folder)
        if level == 1:
            album = [parts[0], src.name]
            if not _check_folder_names(plan, [src.name]):
                return plan
            _album_files(plan, album, src, src.name)
        else:
            if not _check_folder_names(plan, [src.name]):
                return plan
            try:
                entries = sorted(os.scandir(src), key=lambda e: e.name.lower())
            except OSError as e:
                plan.error = f"Не открыть папку: {e}"
                return plan
            for e in entries:
                if e.name.startswith("."):
                    continue
                if e.is_dir():
                    if not _check_folder_names(plan, [e.name]):
                        plan.skipped.append((f"{src.name}/{e.name}/", plan.error))
                        plan.error = None
                        continue
                    _album_files(plan, [src.name, e.name], Path(e.path), f"{src.name}/{e.name}")
                else:
                    plan.skipped.append((f"{src.name}/{e.name}", "файл вне альбома: нужно Исполнитель/Альбом/трек"))

    # одно имя на сервере у нескольких файлов (CD1/01.flac и CD2/01.flac) — конфликт
    by_rel: dict[str, list[Item]] = {}
    for it in plan.items:
        by_rel.setdefault(it.rel.lower(), []).append(it)
    existing = {e.lower() for e in (existing or ())}
    plan.items = []
    for key, group in by_rel.items():
        if key in existing:
            for it in group:
                plan.skipped.append((it.shown, "уже есть на сервере"))
        elif len(group) > 1:
            plan.conflicts.append(group)
        else:
            plan.items.append(group[0])
    if not plan.items and not plan.conflicts and not plan.error:
        plan.error = "Нечего загружать"
    return plan


def existing_scope(dest: str, folder: str | None) -> str:
    """Какую папку сервера спросить про уже лежащие файлы: туда ляжет всё загружаемое."""
    parts = [p for p in dest.split("/") if p]
    if len(parts) < 2 and folder:
        parts.append(Path(folder).name)
    return "/".join(parts)


def fetch_existing(scope: str) -> set[str]:
    try:
        return {f["rel_path"] for f in sources.REMOTE.list_files(scope)}
    except sources.RemoteNotFound:
        return set()   # такой папки ещё нет


# ---- передача ----

class Cancelled(Exception):
    pass


class _Body:
    """Файл для requests: read() кусками с проверкой отмены, __len__ — для Content-Length."""

    def __init__(self, path, size, cancel: threading.Event, on_bytes):
        self._f = open(path, "rb")
        self._size = size
        self._cancel = cancel
        self._on_bytes = on_bytes

    def __len__(self):
        return self._size

    def read(self, n=-1):
        if self._cancel.is_set():
            raise Cancelled()
        chunk = self._f.read(n if n and n > 0 else CHUNK)
        self._on_bytes(len(chunk))
        return chunk

    def close(self):
        self._f.close()


@dataclass
class Snapshot:
    """Что показать в полосе прогресса. Отдаётся в UI целиком, без ссылок на поток."""
    kind: str               # upload | download
    title: str
    state: str              # running | done | cancelled | stopped
    file: str = ""
    index: int = 0          # номер текущего файла, с 1
    total: int = 0
    done_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0      # байт/с
    ok: int = 0
    skipped: list = field(default_factory=list)   # (файл, почему)
    failed: list = field(default_factory=list)
    op_id: str | None = None
    message: str = ""


class Transfer:
    """Одна передача в фоновом потоке. notify(snapshot) зовётся из этого потока —
    экран переправляет снимок в цикл событий через pubsub."""

    def __init__(self, kind, title, notify):
        self.cancel = threading.Event()
        self.snap = Snapshot(kind=kind, title=title, state="running")
        self._notify = notify
        self._last = 0.0
        self._t0 = time.monotonic()

    def _emit(self, force=False):
        now = time.monotonic()
        if not force and now - self._last < PROGRESS_EVERY:
            return
        self._last = now
        s = self.snap
        s.speed = s.done_bytes / max(now - self._t0, 1e-3)
        try:
            self._notify(Snapshot(**{**s.__dict__, "skipped": list(s.skipped), "failed": list(s.failed)}))
        except Exception:
            logger.exception("transfer notify")

    def _add_bytes(self, n):
        self.snap.done_bytes += n
        self._emit()

    def _finish(self, state, message=""):
        self.snap.state = state
        self.snap.message = message
        self._emit(force=True)
        logger.info("%s «%s»: %s, ок %d, пропущено %d, ошибок %d %s", self.snap.kind, self.snap.title,
                    state, self.snap.ok, len(self.snap.skipped), len(self.snap.failed), message)

    # ---- загрузка ----

    def start_upload(self, dest: str, items: list[Item]):
        s = self.snap
        s.total = len(items)
        s.total_bytes = sum(it.size for it in items)
        threading.Thread(target=self._upload, args=(dest, items), daemon=True).start()

    def _upload(self, dest, items):
        s = self.snap
        try:
            # в списке операций — куда грузили; из корня — имя исполнителя
            s.op_id = sources.REMOTE.start_op(dest or items[0].rel.split("/", 1)[0])
        except (sources.RemoteUnavailable, sources.RemoteNotFound) as e:
            self._finish("stopped", f"Не начать загрузку: {e}")
            return
        fails = 0
        for i, it in enumerate(items, 1):
            if self.cancel.is_set():
                break
            s.index, s.file = i, it.rel
            self._emit(force=True)
            before = s.done_bytes
            body = None
            try:
                body = _Body(it.src, it.size, self.cancel, self._add_bytes)
                r = sources.REMOTE.upload_file(it.rel, s.op_id, body)
            except Cancelled:
                # read() бросил посреди отправки: соединение рвётся, сервер удаляет .part
                s.done_bytes = before
                break
            except OSError as e:   # локальный файл не открылся или не читается
                s.failed.append((it.rel, f"не прочитать на ПК: {e}"))
                s.done_bytes = before + it.size
                continue
            except (sources.RemoteUnavailable, sources.RemoteNotFound) as e:
                s.done_bytes = before
                if self.cancel.is_set():
                    break
                s.failed.append((it.rel, str(e)))
                fails += 1
                if fails >= MAX_FAILS_IN_ROW:
                    self._finish("stopped", "Сервер не отвечает — загрузка остановлена")
                    return
                continue
            finally:
                if body is not None:
                    body.close()
            fails = 0
            s.done_bytes = before + it.size
            if r.status_code == 200:
                s.ok += 1
            elif r.status_code == 409:
                s.skipped.append((it.rel, "уже есть на сервере"))
            else:
                s.failed.append((it.rel, sources._detail(r) or f"ответ {r.status_code}"))
                if r.status_code in (410, 507):   # операция откачена / место кончилось — дальше бессмысленно
                    self._finish("stopped", "На сервере закончилось место" if r.status_code == 507
                                 else "Операция уже откачена")
                    return
        self._finish("cancelled" if self.cancel.is_set() else "done")

    # ---- скачивание ----

    def start_download(self, rel: str, is_dir: bool, size: int, local_dir: str):
        threading.Thread(target=self._download, args=(rel, is_dir, size, local_dir), daemon=True).start()

    def _download(self, rel, is_dir, size, local_dir):
        s = self.snap
        try:
            files = sources.REMOTE.list_files(rel) if is_dir else [{"rel_path": rel, "size": size}]
        except (sources.RemoteUnavailable, sources.RemoteNotFound) as e:
            self._finish("stopped", f"Не получить список файлов: {e}")
            return
        base = Path(local_dir)
        todo = []
        for f in files:
            target = base.joinpath(*f["rel_path"].split("/"))
            if target.exists():
                s.skipped.append((f["rel_path"], "уже есть на ПК"))
            else:
                todo.append((f, target))
        s.total = len(todo)
        s.total_bytes = sum(f["size"] for f, _ in todo)
        fails = 0
        for i, (f, target) in enumerate(todo, 1):
            if self.cancel.is_set():
                break
            s.index, s.file = i, f["rel_path"]
            self._emit(force=True)
            before = s.done_bytes
            part = target.with_name(target.name + ".part")
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                r = sources.REMOTE.download_file(f["rel_path"])
                try:
                    with open(part, "wb") as out:
                        for chunk in r.iter_content(CHUNK):
                            if self.cancel.is_set():
                                raise Cancelled()
                            out.write(chunk)
                            self._add_bytes(len(chunk))
                finally:
                    r.close()
                os.replace(part, target)
                s.ok += 1
                fails = 0
            except Cancelled:
                part.unlink(missing_ok=True)
                s.done_bytes = before
                break
            except (sources.RemoteUnavailable, sources.RemoteNotFound, OSError,
                    sources.requests.RequestException) as e:
                part.unlink(missing_ok=True)
                s.done_bytes = before
                s.failed.append((f["rel_path"], str(e)))
                if isinstance(e, sources.RemoteUnavailable):
                    fails += 1
                    if fails >= MAX_FAILS_IN_ROW:
                        self._finish("stopped", "Сервер не отвечает — скачивание остановлено")
                        return
        self._finish("cancelled" if self.cancel.is_set() else "done")


# Идущая передача: одна на всё приложение. Экран можно закрыть и открыть снова —
# передача продолжается и снова видна в полосе прогресса.
current: Transfer | None = None


def busy() -> bool:
    return current is not None and current.snap.state == "running"
