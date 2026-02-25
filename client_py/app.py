# ============================================================
# Postock (FINAL)
# ------------------------------------------------------------
# Windows 트레이 상주 주식 모니터링 프로그램
#
#  주요 기능
# - 한국(KR) / 미국(US) 주식 시세 조회 (Provider 모듈 사용)
# - 트레이 아이콘 + 미니 주가 창 (항상 위 / 드래그 이동 / 투명도)
# - 설정 창: 종목 추가/삭제/활성 + 순서 드래그 + 투명도 조절
# - 장중( KR 또는 US ) 10초, 장외 30초 갱신
# - 시리얼 라이선스: 최초 실행 시 트라이얼 자동 발급, 만료 시 종료
#
#  라이선스 흐름
# - 최초 실행: POST /activate/trial → serial + expire_at 발급, config 저장
# - 이후 실행: 로컬 expire_at 비교 → 만료 시 즉시 종료
# - 운영 중:  1시간마다 로컬 만료 여부 재확인
#
#  스레드 구조
# - tkinter : UI 메인 스레드
# - pystray : 내부 스레드
# - worker  : 백그라운드(주기 갱신)
# - executor: 네트워크 작업 병렬
#
# ------------------------------------------------------------
# 의존:
# - providers.py : QuoteProviderKR, QuoteProviderUS (get_quote, get_name)
# - tickers/loader.py : search_kr (오프라인 kr.json 검색)
# ============================================================

import os
import sys
import json
import time
import random
import queue
import winreg
import threading
import logging
import hashlib
import uuid
from logging.handlers import TimedRotatingFileHandler
from dataclasses import dataclass, asdict
from datetime import datetime, time as dtime
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import pystray
import pytz
from PIL import Image

from providers import QuoteProviderKR, QuoteProviderUS
from tickers.loader import search_kr, get_kr_name

# =========================================================
# 기본 경로/로그
# =========================================================
APP_NAME = "Postock"
BASE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "app.log")
os.makedirs(BASE_DIR, exist_ok=True)

# 라이선스 서버 URL (환경변수로 오버라이드 가능)
LICENSE_SERVER_URL = os.environ.get("POSTOCK_LICENSE_SERVER", "http://localhost:8080")

# 운영 중 라이선스 재확인 주기 (초)
LICENSE_CHECK_INTERVAL = 3600

KST = pytz.timezone("Asia/Seoul")
ET = pytz.timezone("US/Eastern")

handler = TimedRotatingFileHandler(
    LOG_PATH,
    when="midnight",
    backupCount=5,
    encoding="utf-8"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[handler],
)

# =========================================================
# 알림(기본 OFF)
# =========================================================
try:
    from win11toast import toast as _toast

    def notify(title: str, msg: str):
        _toast(title, msg, duration="short")

except Exception:

    def notify(title: str, msg: str):
        pass


# =========================================================
# 자동실행 등록
# =========================================================
def set_startup(enable: bool):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = APP_NAME
    exe_path = sys.executable

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enable:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass


# =========================================================
# 라이선스
# =========================================================
def generate_device_id() -> str:
    """MAC 주소 + 호스트명 + 사용자명을 조합한 기기 고유 해시 생성."""
    import platform
    parts = [
        str(uuid.getnode()),
        platform.node(),
        os.environ.get("USERNAME", ""),
        os.environ.get("COMPUTERNAME", ""),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


class LicenseManager:
    """
    시리얼 라이선스 관리.
    - 시세 요청은 providers.py(직접 스크래핑)가 담당.
    - 서버는 최초 트라이얼 발급(/activate/trial)에만 사용.
    - 이후 만료 여부는 로컬 expire_at으로 판단.
    """

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.serial = ""
        self.device_id = ""
        self.expire_at = ""   # ISO UTC 문자열
        self.plan = ""
        self._session = requests.Session()
        self._expiry_notified = False  # 만료 임박 알림 세션당 1회

    # ----------------------------------------------------------
    def load_from_config(self, cfg: "AppConfig"):
        self.serial = cfg.serial or ""
        self.device_id = cfg.device_id or ""
        self.expire_at = cfg.expire_at or ""
        self.plan = cfg.plan or ""

    def save_to_config(self, cfg: "AppConfig"):
        cfg.serial = self.serial
        cfg.device_id = self.device_id
        cfg.expire_at = self.expire_at
        cfg.plan = self.plan

    # ----------------------------------------------------------
    def is_expired(self) -> bool:
        """로컬 expire_at으로 만료 여부 확인 (서버 호출 없음)."""
        if not self.expire_at:
            return False
        try:
            expire = datetime.fromisoformat(self.expire_at)
            if expire.tzinfo is None:
                expire = pytz.utc.localize(expire)
            return datetime.now(pytz.utc) > expire
        except Exception:
            return False

    def days_left(self) -> Optional[int]:
        if not self.expire_at:
            return None
        try:
            expire = datetime.fromisoformat(self.expire_at)
            if expire.tzinfo is None:
                expire = pytz.utc.localize(expire)
            delta = expire - datetime.now(pytz.utc)
            return max(0, delta.days)
        except Exception:
            return None

    # ----------------------------------------------------------
    def activate_trial(self) -> bool:
        """
        서버에서 트라이얼 시리얼 발급.
        기기당 1회, 재실행 시 기존 시리얼 재사용.
        """
        try:
            resp = self._session.post(
                f"{self.server_url}/activate/trial",
                headers={"X-Device": self.device_id},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                self.serial = data.get("serial", "")
                self.expire_at = data.get("expire_at", "")
                self.plan = data.get("plan", "trial")
                logging.info(
                    "License: activated serial=%s plan=%s expire=%s",
                    self.serial, self.plan, self.expire_at,
                )
                return bool(self.serial)
            logging.warning("License: activate_trial HTTP %s", resp.status_code)
        except Exception as e:
            logging.warning("License: activate_trial failed: %s", e)
        return False

    # ----------------------------------------------------------
    def check_expiry_notify(self):
        """만료 3일 이내 시 알림 (세션당 1회)."""
        if self._expiry_notified:
            return
        days = self.days_left()
        if days is not None and days <= 3:
            notify(
                "라이선스 만료 예정",
                f"무료 체험 기간이 {days}일 후 만료됩니다.",
            )
            self._expiry_notified = True


# =========================================================
# 설정/데이터 구조
# =========================================================
@dataclass
class WatchItem:
    code: str
    name: str = ""
    market: str = "KR"  # "KR" / "US"
    enabled: bool = True
    notify: bool = False  # 디폴트 OFF


@dataclass
class AppConfig:
    watchlist: List[WatchItem] = None
    price_window_pos: Optional[dict] = None
    price_alpha_idle: float = 0.65
    notify_threshold_pct: float = 1.5
    serial: str = ""      # 라이선스 시리얼
    device_id: str = ""   # 기기 해시
    expire_at: str = ""   # ISO UTC 만료일시
    plan: str = ""        # trial / free / pro / enterprise

    @staticmethod
    def default():
        return AppConfig(
            watchlist=[
                WatchItem("005930", "삼성전자", "KR", True, False),
                WatchItem("000660", "SK하이닉스", "KR", True, False),
            ],
            price_window_pos=None,
            price_alpha_idle=0.65,
            notify_threshold_pct=1.5,
        )


def load_config() -> AppConfig:
    if not os.path.exists(CONFIG_PATH):
        cfg = AppConfig.default()
        save_config(cfg)
        return cfg

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)

        wl: List[WatchItem] = []
        for w in raw.get("watchlist", []) or []:
            wl.append(
                WatchItem(
                    code=str(w.get("code", "")).strip(),
                    name=str(w.get("name", "")).strip(),
                    market=str(w.get("market", "KR")).strip() or "KR",
                    enabled=bool(w.get("enabled", True)),
                    notify=bool(w.get("notify", False)),
                )
            )

        return AppConfig(
            watchlist=[x for x in wl if x.code],
            price_window_pos=raw.get("price_window_pos"),
            price_alpha_idle=float(raw.get("price_alpha_idle", 0.65)),
            notify_threshold_pct=float(raw.get("notify_threshold_pct", 1.5)),
            serial=str(raw.get("serial", "")),
            device_id=str(raw.get("device_id", "")),
            expire_at=str(raw.get("expire_at", "")),
            plan=str(raw.get("plan", "")),
        )
    except Exception as e:
        logging.exception("config load failed: %s", e)
        cfg = AppConfig.default()
        save_config(cfg)
        return cfg

_config_save_lock = threading.Lock()

def save_config(cfg: AppConfig):
    with _config_save_lock:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "watchlist": [asdict(w) for w in (cfg.watchlist or [])],
                    "price_window_pos": cfg.price_window_pos,
                    "price_alpha_idle": cfg.price_alpha_idle,
                    "notify_threshold_pct": cfg.notify_threshold_pct,
                    "serial": cfg.serial,
                    "device_id": cfg.device_id,
                    "expire_at": cfg.expire_at,
                    "plan": cfg.plan,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


# =========================================================
# 장중 판단 (휴일 무시, 주말만 처리)
# =========================================================
def is_market_open(market: str, now: datetime | None = None) -> bool:
    """
    market: "KR" | "US"
    """
    if market == "KR":
        tz = KST
        start_t = dtime(9, 00)
        end_t = dtime(15, 30)
    elif market == "US":
        tz = ET
        start_t = dtime(9, 20)
        end_t = dtime(16, 10)
    else:
        return False

    if now is None:
        now = datetime.now(tz)
    else:
        if now.tzinfo is None:
            now = tz.localize(now)
        else:
            now = now.astimezone(tz)

    if now.weekday() >= 5:
        return False

    return start_t <= now.time() <= end_t


# =========================================================
# 트레이 아이콘 이미지
# =========================================================
def resource_path(rel_path: str) -> str:
    """
    PyInstaller 대응 리소스 경로
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.abspath("."), rel_path)

# =========================================================
# 메인 앱
# =========================================================
class StockTrayApp:
    MIN_REFRESH_KR_OPEN = 10
    MIN_REFRESH_KR_CLOSE = 20

    MIN_REFRESH_US_OPEN = 10
    MIN_REFRESH_US_CLOSE = 60
    TICK_SEC = 1.0

    def __init__(self):
        self.cfg = load_config()
        if self.cfg.watchlist is None:
            self.cfg.watchlist = []

        # ---- 라이선스 초기화 ----
        self.license = LicenseManager(LICENSE_SERVER_URL)
        self.license.load_from_config(self.cfg)

        # 기기 ID 최초 생성
        if not self.license.device_id:
            self.license.device_id = generate_device_id()
            self.license.save_to_config(self.cfg)
            save_config(self.cfg)

        self._license_error: Optional[str] = None
        self._serial_expired = False

        if self.license.serial:
            # 기존 시리얼 → 로컬 만료 확인
            if self.license.is_expired():
                self._serial_expired = True
        else:
            # 시리얼 없음 → 트라이얼 발급 시도
            ok = self.license.activate_trial()
            if ok:
                self.license.save_to_config(self.cfg)
                save_config(self.cfg)
            else:
                self._license_error = (
                    "서버에 연결하여 라이선스를 활성화하지 못했습니다.\n"
                    "인터넷 연결 및 서버 상태를 확인하고 다시 시도해 주세요.\n\n"
                    f"서버: {LICENSE_SERVER_URL}"
                )
        # ---- 라이선스 초기화 끝 ----

        # 운영 중 라이선스 재확인 타이머
        self._last_license_check = time.time()

        # providers
        self.provider_kr = QuoteProviderKR()
        self.provider_us = QuoteProviderUS()

        # cache: key=(market, code) -> dict
        self.cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.cache_lock = threading.Lock()

        # refresh serialize lock (worker + manual refresh 충돌 방지)
        self.refresh_lock = threading.Lock()

        # tk bridge queue: str 또는 tuple(command, ...)
        self.tk_queue: "queue.Queue[Any]" = queue.Queue()

        self.running = True

        self._rr_index = 0

        # 네트워크 전용 풀
        self.executor = ThreadPoolExecutor(max_workers=6)

        # windows
        self._settings_win = None
        self._price_win = None

        # 주가창 숨김 상태
        self.price_hidden = False

        # alpha
        self.price_alpha_active = 1.0
        self.price_alpha_idle = float(getattr(self.cfg, "price_alpha_idle", 0.65))

        # notify bucket
        self.last_bucket: Dict[Tuple[str, str], int] = {}

        # 초기 캐시 / 이름 비어있으면 백그라운드로 이름 채우기
        for w in self.cfg.watchlist:
            with self.cache_lock:
                self.cache[(w.market, w.code)] = {"status": "loading", "ts": ""}

            if not w.name:
                self._async_resolve_name(w.market, w.code)

        save_config(self.cfg)

        # tray icon/menu
        tray_icon_path = resource_path("tray.ico")
        tray_image = Image.open(tray_icon_path)
        self.icon = pystray.Icon(APP_NAME, tray_image, APP_NAME, self._build_menu())

        # worker thread
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)

    def get_provider(self, market: str):
        return self.provider_us if market == "US" else self.provider_kr

    # -----------------------------------------------------
    # 라이선스 다이얼로그 (tk 초기화 후 호출)
    # -----------------------------------------------------
    def _show_expired_and_quit(self):
        from tkinter import messagebox
        expire_str = ""
        if self.license.expire_at:
            try:
                expire_str = f"\n만료일: {self.license.expire_at[:10]}"
            except Exception:
                pass
        messagebox.showerror(
            "라이선스 만료",
            f"사용 기간이 만료되었습니다.{expire_str}\n\n"
            "계속 사용하시려면 라이선스를 갱신해 주세요.",
        )
        self._quit()

    def _show_license_error_and_quit(self, msg: str):
        from tkinter import messagebox
        messagebox.showerror("라이선스 오류", msg)
        self._quit()

    # -----------------------------------------------------
    # Tray menu
    # -----------------------------------------------------
    def _toggle_price_window(self):
        if not self._price_win or not self._price_win.winfo_exists():
            self.price_hidden = False
            self.tk_queue.put("OPEN_PRICE_WINDOW")
            return

        if self.price_hidden:
            self.price_hidden = False
            self._price_win.deiconify()
            try:
                self._price_win.lift()
                self._price_win.focus_force()
            except Exception:
                pass
        else:
            self.price_hidden = True
            self._price_win.withdraw()

        self.tk_queue.put("REFRESH_MENU")

    def _build_menu(self):
        def toggle_price(*_):
            self.tk_queue.put("TOGGLE_PRICE")

        label = "보이기" if self.price_hidden else "감추기"
        items = [
            pystray.MenuItem(label, toggle_price, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("설정", lambda *_: self.tk_queue.put("OPEN_SETTINGS")),
            pystray.MenuItem("종료", lambda *_: self.tk_queue.put("QUIT")),
        ]
        return pystray.Menu(*items)

    # -----------------------------------------------------
    # 시간표시
    # -----------------------------------------------------
    def _make_ts(self, w: WatchItem, now_dt: datetime) -> str:
        return now_dt.strftime("%H:%M:%S") if is_market_open(w.market, now_dt) else "CLOSE"

    # -----------------------------------------------------
    # 백그라운드: 이름 조회 (UI 멈춤 방지 핵심)
    # -----------------------------------------------------
    def _async_resolve_name(self, market: str, code: str):

        def job():
            try:
                if market == "KR":
                    nm = get_kr_name(code)
                else:
                    provider = self.get_provider(market)
                    nm = provider.get_name(code)

            except Exception as e:
                nm = code

            self.tk_queue.put(("UPDATE_WATCH_NAME", market, code, nm or code))

        self.executor.submit(job)

    # -----------------------------------------------------
    # worker loop
    # -----------------------------------------------------
    def _worker_loop(self):
        logging.info("WORKER: advanced scheduler started")

        while self.running:

            # 주기적 라이선스 만료 확인
            now_ts = time.time()
            if now_ts - self._last_license_check >= LICENSE_CHECK_INTERVAL:
                self._last_license_check = now_ts
                if self.license.is_expired():
                    logging.warning("License: expired detected in worker loop")
                    self.running = False
                    self.tk_queue.put("SERIAL_EXPIRED")
                    return
                self.license.check_expiry_notify()

            watchlist = [w for w in self.cfg.watchlist if w.enabled]
            if not watchlist:
                time.sleep(self.TICK_SEC)
                continue

            now = time.time()
            dt_now = datetime.now(pytz.utc)

            candidate = None
            oldest_due = None

            with self.cache_lock:
                for w in watchlist:

                    key = (w.market, w.code)
                    entry = self.cache.get(key, {})
                    last_ts = entry.get("rev")

                    if w.market == "KR":
                        interval = (
                            self.MIN_REFRESH_KR_OPEN
                            if is_market_open("KR", dt_now)
                            else self.MIN_REFRESH_KR_CLOSE
                        )
                    else:
                        interval = (
                            self.MIN_REFRESH_US_OPEN
                            if is_market_open("US", dt_now)
                            else self.MIN_REFRESH_US_CLOSE
                        )

                    if last_ts is None:
                        candidate = w
                        break

                    due_time = last_ts + interval

                    if now >= due_time:
                        if oldest_due is None or last_ts < oldest_due:
                            oldest_due = last_ts
                            candidate = w

            if candidate:
                self.executor.submit(self._refresh_one, candidate)

            base = self.TICK_SEC
            jitter = random.uniform(-0.2, 0.3)
            time.sleep(max(0.1, base + jitter))

    # -----------------------------------------------------
    # refresh all (네트워크/병렬)
    # -----------------------------------------------------
    def _refresh_all(self):
        # worker/수동 refresh 겹치면 서로 꼬일 수 있으니 serialize
        if not self.refresh_lock.acquire(blocking=False):
            return
        try:
            now_dt = datetime.now()

            watchlist = [w for w in (self.cfg.watchlist or []) if w.enabled]
            if not watchlist:
                return

            # 1) loading 표기
            with self.cache_lock:
                for w in watchlist:
                    self.cache[(w.market, w.code)] = {
                        "status": "loading",
                        "ts": self._make_ts(w, now_dt),
                    }

            # 2) 병렬 조회
            futures = {}
            for w in watchlist:
                provider = self.get_provider(w.market)
                if w.market == "KR":
                    fut = self.executor.submit(provider.get_quote, w.code, datetime.now())
                else:
                    fut = self.executor.submit(provider.get_quote, w.code)
                futures[fut] = w

                logging.info(
                    "REFRESH %s %s provider=%s",
                    w.market,
                    w.code,
                    provider.__class__.__name__,
                )

            # 3) 결과 수집
            for fut in as_completed(futures):
                w = futures[fut]
                ts = self._make_ts(w, datetime.now())

                try:
                    q = fut.result(timeout=15)
                except Exception:
                    q = None

                if q:
                    price, prev_close, vol = q

                    if price and prev_close != 0:
                        pct = (price - prev_close) / prev_close * 100.0
                    else:
                        pct = 0.0
                    with self.cache_lock:
                        self.cache[(w.market, w.code)] = {
                            "status": "ok",
                            "price": price,
                            "prev_close": prev_close,
                            "volume": vol,
                            "ts": ts,
                            "rev": time.time(),
                        }
                    self._maybe_notify(w, price, pct)
                else:
                    with self.cache_lock:
                        self.cache[(w.market, w.code)] = {"status": "error", "ts": ts, "rev": time.time(),}

            # 4) UI/메뉴 갱신 트리거
            self.tk_queue.put("REFRESH_MENU")

        finally:
            try:
                self.refresh_lock.release()
            except Exception:
                pass

    # -----------------------------------------------------
    # refresh one
    # -----------------------------------------------------
    def _refresh_one(self, w: WatchItem):
        now_dt = datetime.now()

        # loading 표시
        with self.cache_lock:
            self.cache[(w.market, w.code)] = {
                "status": "loading",
                "ts": self._make_ts(w, now_dt),
            }

        provider = self.get_provider(w.market)

        try:
            if w.market == "KR":
                q = provider.get_quote(w.code, now_dt)
            else:
                q = provider.get_quote(w.code)
        except Exception:
            q = None

        ts = self._make_ts(w, datetime.now())

        if q:
            price, prev_close, vol = q

            if prev_close and prev_close != 0:
                pct = (price - prev_close) / prev_close * 100.0
            else:
                pct = 0.0
            with self.cache_lock:
                self.cache[(w.market, w.code)] = {
                    "status": "ok",
                    "price": price,
                    "prev_close": prev_close,
                    "volume": vol,
                    "ts": ts,
                    "rev": time.time(),
                }
        else:
            with self.cache_lock:
                self.cache[(w.market, w.code)] = {
                    "status": "error",
                    "ts": ts,
                    "rev": time.time(),
                }

        self.tk_queue.put("REFRESH_MENU")

    # -----------------------------------------------------
    # notify
    # -----------------------------------------------------
    def _maybe_notify(self, w: WatchItem, price, pct: float):
        if not w.notify:
            return
        thr = float(self.cfg.notify_threshold_pct)
        if abs(pct) < thr:
            return

        bucket = int(abs(pct) // thr)
        key = (w.market, w.code)
        if self.last_bucket.get(key) == bucket:
            return

        self.last_bucket[key] = bucket
        sign = "+" if pct >= 0 else ""
        if w.market == "US":
            notify("주가 알림", f"{w.name} {price:,.2f} ({sign}{pct:.2f}%)")
        else:
            notify("주가 알림", f"{w.name} {int(price):,}원 ({sign}{pct:.2f}%)")

    # -----------------------------------------------------
    # tkinter main thread queue processor
    # -----------------------------------------------------
    def _process_tk(self):
        try:
            while True:
                cmd = self.tk_queue.get_nowait()

                # tuple command 처리
                if isinstance(cmd, tuple):
                    op = cmd[0]

                    if op == "UPDATE_WATCH_NAME":
                        _, market, code, nm = cmd
                        updated = False
                        for w in self.cfg.watchlist:
                            if w.market == market and w.code == code:
                                if not w.name or w.name == w.code:
                                    w.name = nm
                                    updated = True
                                break
                        if updated:
                            save_config(self.cfg)
                            self.tk_queue.put("REFRESH_MENU")
                    continue

                # string command 처리
                if cmd == "SERIAL_EXPIRED":
                    self._show_expired_and_quit()

                elif cmd == "OPEN_SETTINGS":
                    self._open_settings()

                elif cmd == "OPEN_PRICE_WINDOW":
                    self._open_price_window()

                elif cmd == "REFRESH_MENU":
                    try:
                        self.icon.menu = self._build_menu()
                        self.icon.update_menu()
                    except Exception:
                        pass

                elif cmd == "TOGGLE_PRICE":
                    self._toggle_price_window()

                elif cmd == "REFRESH_NOW":
                    self.executor.submit(self._refresh_all)

                elif cmd == "QUIT":
                    self._quit()

        except queue.Empty:
            pass
        except Exception as e:
            logging.exception("TK: _process_tk error: %s", e)

        self.tk_root.after(100, self._process_tk)

    # -----------------------------------------------------
    # 주가창
    # -----------------------------------------------------
    def _open_price_window(self):
        import tkinter as tk
        from tkinter import ttk

        # 이미 열려 있으면 복원
        if self._price_win and self._price_win.winfo_exists():
            if self.price_hidden:
                self.price_hidden = False
                self._price_win.deiconify()
            try:
                self._price_win.lift()
                self._price_win.attributes("-topmost", True)
                self._price_win.after(50, lambda: self._price_win.attributes("-topmost", False))
                self._price_win.focus_force()
            except Exception:
                pass
            self.tk_queue.put("REFRESH_MENU")
            return

        win = tk.Toplevel(self.tk_root)
        self._price_win = win

        win.overrideredirect(True)
        win.resizable(False, False)
        win.attributes("-alpha", self.price_alpha_idle)

        frm = ttk.Frame(win, padding=(6, 4))
        frm.pack(fill="both", expand=True)

        dragging = False
        drag = {"dx": 0, "dy": 0}
        save_after_id = None

        def save_pos_debounced(x, y):
            nonlocal save_after_id
            if save_after_id:
                try:
                    win.after_cancel(save_after_id)
                except Exception:
                    pass

            def do_save():
                sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
                ww, wh = win.winfo_width(), win.winfo_height()
                xx = max(0, min(int(x), sw - ww))
                yy = max(0, min(int(y), sh - wh))
                self.cfg.price_window_pos = {"x": xx, "y": yy}
                save_config(self.cfg)

            save_after_id = win.after(300, do_save)

        def on_press(e):
            nonlocal dragging
            dragging = True
            drag["dx"] = e.x_root - win.winfo_x()
            drag["dy"] = e.y_root - win.winfo_y()
            win.attributes("-topmost", True)
            win.attributes("-alpha", self.price_alpha_active)
            win.lift()

        def on_motion(e):
            if not dragging or not (e.state & 0x100):
                return
            x = e.x_root - drag["dx"]
            y = e.y_root - drag["dy"]
            win.geometry(f"+{x}+{y}")
            save_pos_debounced(x, y)

        def on_release(_):
            nonlocal dragging
            dragging = False
            win.attributes("-topmost", False)

        def on_enter(_):
            win.attributes("-topmost", True)
            win.attributes("-alpha", self.price_alpha_active)
            win.lift()

        def on_leave(_):
            if dragging:
                return
            win.attributes("-topmost", False)
            win.attributes("-alpha", self.price_alpha_idle)

        # -----------------------------
        # body
        # -----------------------------
        body = ttk.Frame(frm)
        body.pack(fill="both", expand=True)

        row_widgets: List[Dict[str, Any]] = []
        last_codes: List[Tuple[str, str]] = []

        def rebuild_rows():
            nonlocal row_widgets, last_codes

            for c in body.winfo_children():
                c.destroy()
            row_widgets.clear()

            watchlist = [w for w in self.cfg.watchlist if w.enabled]
            last_codes = [(w.market, w.code) for w in watchlist]

            for r, w in enumerate(watchlist, start=0):
                name_lbl = ttk.Label(body, text=w.name or w.code, width=14)
                price_lbl = ttk.Label(body, text="-", anchor="e", width=10)
                diff_lbl = ttk.Label(body, text="-", anchor="e", width=8)
                pct_lbl = ttk.Label(body, text="-", anchor="e", width=7)
                vol_lbl = ttk.Label(body, text="-", anchor="e", width=10)

                name_lbl.grid(row=r, column=0, sticky="w", padx=(2, 6))
                price_lbl.grid(row=r, column=1, sticky="e", padx=6)
                diff_lbl.grid(row=r, column=2, sticky="e", padx=6)
                pct_lbl.grid(row=r, column=3, sticky="e", padx=6)
                vol_lbl.grid(row=r, column=4, sticky="e", padx=6)

                row_widgets.append({
                    "market": w.market,
                    "code": w.code,
                    "price_lbl": price_lbl,
                    "diff_lbl": diff_lbl,
                    "pct_lbl": pct_lbl,
                    "vol_lbl": vol_lbl,
                })

                # 드래그/우클릭 동일 동작
                for widget in (name_lbl, price_lbl, diff_lbl, pct_lbl, vol_lbl):
                    widget.bind("<ButtonPress-1>", on_press, add="+")
                    widget.bind("<B1-Motion>", on_motion, add="+")
                    widget.bind("<ButtonRelease-1>", on_release, add="+")
                    widget.bind("<Enter>", on_enter, add="+")
                    widget.bind("<Leave>", on_leave, add="+")
                    widget.bind("<Button-3>", lambda e: self.tk_queue.put("OPEN_SETTINGS"), add="+")

        def refresh_rows():
            if not win.winfo_exists():
                return

            # 종목 구조 변경 감지
            current_codes = [(w.market, w.code) for w in self.cfg.watchlist if w.enabled]
            if current_codes != last_codes:
                rebuild_rows()

            for row in row_widgets:
                key = (row["market"], row["code"])

                with self.cache_lock:
                    st = self.cache.get(key, {})

                price = st.get("price")
                prev_close  = st.get("prev_close")
                vol   = st.get("volume")

                if price is None:
                    continue

                # diff 계산
                diff = price - prev_close

                if price and prev_close != 0:
                    pct = (price - prev_close) / prev_close * 100.0
                else:
                    pct = 0.0

                # 색상
                fg = "#c00000" if pct > 0 else "#0040c0" if pct < 0 else "black"

                # PRICE / DIFF
                if row["market"] == "US":
                    row["price_lbl"].config(text=f"{price:,.2f}", foreground=fg)
                    row["diff_lbl"].config(text=f"{diff:+.2f}", foreground=fg)
                else:
                    row["price_lbl"].config(text=f"{int(price):,}", foreground=fg)
                    row["diff_lbl"].config(text=f"{int(diff):+,d}", foreground=fg)

                row["pct_lbl"].config(text=f"{pct:+.2f}%", foreground=fg)

                if vol is not None:
                    row["vol_lbl"].config(text=f"{vol:,}")

            win.after(500, refresh_rows)

        # 바깥 영역 바인딩
        for wdg in (win, frm, body):
            wdg.bind("<Enter>", on_enter)
            wdg.bind("<Leave>", on_leave)
            wdg.bind("<ButtonPress-1>", on_press)
            wdg.bind("<B1-Motion>", on_motion)
            wdg.bind("<ButtonRelease-1>", on_release)
            wdg.bind("<Button-3>", lambda e: self.tk_queue.put("OPEN_SETTINGS"))

        # 반드시 호출
        rebuild_rows()
        refresh_rows()

        # 위치 복원/중앙 배치
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = win.winfo_width(), win.winfo_height()

        pos = getattr(self.cfg, "price_window_pos", None)
        if isinstance(pos, dict) and "x" in pos and "y" in pos:
            x = max(0, min(int(pos["x"]), sw - ww))
            y = max(0, min(int(pos["y"]), sh - wh))
        else:
            x = (sw - ww) // 2
            y = (sh - wh) // 2

        win.geometry(f"+{x}+{y}")

        # 표시/포커스
        win.deiconify()
        win.lift()
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))
        self.tk_queue.put("REFRESH_MENU")


    # -----------------------------------------------------
    # 설정창
    # -----------------------------------------------------
    def _open_settings(self):
        import tkinter as tk
        from tkinter import ttk, messagebox, simpledialog

        if self._settings_win is not None and self._settings_win.winfo_exists():
            self._settings_win.deiconify()
            self._settings_win.lift()
            self._settings_win.focus_force()
            return

        win = tk.Toplevel(self.tk_root)
        self._settings_win = win
        win.title("종목 설정")
        win.geometry("540x620")
        win.resizable(False, False)

        # 중앙 배치 (처음부터 한 번만)
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = win.winfo_width(), win.winfo_height()
        x = (sw - ww) // 2
        y = (sh - wh) // 2 - 40
        win.geometry(f"{ww}x{wh}+{x}+{y}")

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="감시 종목", font=("맑은 고딕", 11, "bold")).pack(anchor="w")

        list_frame = ttk.Frame(frm)
        list_frame.pack(fill="x", pady=8)

        scroll = ttk.Scrollbar(list_frame, orient="vertical")
        lb = tk.Listbox(list_frame, height=14, yscrollcommand=scroll.set)
        scroll.config(command=lb.yview)
        lb.pack(side="left", fill="x", expand=True)
        scroll.pack(side="right", fill="y")

        # 순서 드래그
        drag_index = {"from": None}

        def on_lb_button_down(event):
            drag_index["from"] = lb.nearest(event.y)

        def on_lb_motion(event):
            if drag_index["from"] is None:
                return
            to = lb.nearest(event.y)
            if to < 0 or to == drag_index["from"]:
                return
            wl = self.cfg.watchlist
            wl[drag_index["from"]], wl[to] = wl[to], wl[drag_index["from"]]
            drag_index["from"] = to
            save_config(self.cfg)
            refresh_list()
            self.tk_queue.put("REFRESH_MENU")

        def on_lb_button_up(_):
            drag_index["from"] = None

        lb.bind("<Button-1>", on_lb_button_down)
        lb.bind("<B1-Motion>", on_lb_motion)
        lb.bind("<ButtonRelease-1>", on_lb_button_up)

        # 투명도
        ttk.Separator(frm).pack(fill="x", pady=(12, 8))
        alpha_frame = ttk.Frame(frm)
        alpha_frame.pack(fill="x")

        ttk.Label(alpha_frame, text="화면밝기").pack(anchor="w")
        alpha_var = tk.DoubleVar(value=self.price_alpha_idle * 100)
        alpha_label = ttk.Label(alpha_frame, text=f"{int(alpha_var.get())}%")
        alpha_label.pack(anchor="e")

        def on_alpha_change(v):
            a = float(v) / 100.0
            alpha_label.config(text=f"{int(float(v))}%")
            if self._price_win and self._price_win.winfo_exists():
                try:
                    self._price_win.attributes("-alpha", a)
                except Exception:
                    pass
            self.price_alpha_idle = a
            self.cfg.price_alpha_idle = a

        def on_alpha_release(_):
            save_config(self.cfg)

        scale = ttk.Scale(
            alpha_frame,
            from_=1,
            to=100,
            orient="horizontal",
            variable=alpha_var,
            command=on_alpha_change,
        )
        scale.pack(fill="x", pady=4)
        scale.bind("<ButtonRelease-1>", on_alpha_release)

        # 라이선스 정보
        ttk.Separator(frm).pack(fill="x", pady=(12, 4))
        lic_frame = ttk.Frame(frm)
        lic_frame.pack(fill="x", pady=(0, 4))
        plan_text = self.license.plan or "-"
        days = self.license.days_left()
        if days is not None:
            expire_text = f"만료까지 {days}일"
        elif self.license.expire_at:
            expire_text = f"만료: {self.license.expire_at[:10]}"
        else:
            expire_text = "무기한"
        ttk.Label(
            lic_frame,
            text=f"라이선스: {plan_text}  |  {expire_text}",
            foreground="gray",
        ).pack(anchor="w")

        # 리스트 갱신
        def refresh_list():
            lb.delete(0, tk.END)

            for idx, w in enumerate(self.cfg.watchlist):
                flag = ""
                nm = w.name or w.code

                lb.insert(tk.END, f"{flag} {nm} ({w.code})")

                if not w.enabled:
                    lb.itemconfig(idx, fg="gray")

        # ---- 종목 추가(코드)
        def add_by_code():
            if len(self.cfg.watchlist) >= 30:
                messagebox.showwarning("제한", "감시 종목은 최대 30개까지 추가할 수 있습니다.")
                return

            code = simpledialog.askstring(
                "종목 추가",
                "종목코드를 입력하세요\n(한국: 6자리 숫자 / 미국: AAPL, MSFT 등)",
                parent=win,
            )
            if not code:
                return

            code = code.strip().upper()

            if code.isdigit() and len(code) == 6:
                market = "KR"
            elif code.isalpha():
                market = "US"
            else:
                messagebox.showerror(
                    "오류",
                    "종목코드 형식이 올바르지 않습니다.\n한국: 6자리 숫자\n미국: 영문 티커(AAPL)",
                    parent=win,
                )
                return

            if any(x.code == code and x.market == market for x in self.cfg.watchlist):
                messagebox.showinfo("안내", "이미 추가된 종목입니다.", parent=win)
                return

            wi = WatchItem(code=code, name=code, market=market, enabled=True, notify=False)
            self.cfg.watchlist.append(wi)

            with self.cache_lock:
                self.cache[(market, code)] = {"status": "loading", "ts": ""}

            save_config(self.cfg)
            refresh_list()

            self._async_resolve_name(market, code)

            self.tk_queue.put("REFRESH_MENU")
            self.executor.submit(self._refresh_all)

        # ---- 종목 검색(한국명)
        def search_by_name():
            if len(self.cfg.watchlist) >= 30:
                messagebox.showwarning("제한", "감시 종목은 최대 30개까지 추가할 수 있습니다.")
                return

            q = simpledialog.askstring("종목명 검색 (한국)", "종목명 일부를 입력:", parent=win)
            if not q:
                return

            results = search_kr(q.strip(), limit=50)
            if not results:
                messagebox.showinfo(
                    "검색 결과",
                    "일치하는 종목이 없습니다.\n\n※ 일부 종목은 종목코드로 직접 추가해 주세요.",
                    parent=win,
                )
                return

            top = tk.Toplevel(win)
            top.title("검색 결과 (한국)")
            top.geometry("460x360")
            top.resizable(False, False)

            lb2 = tk.Listbox(top, height=15)
            lb2.pack(fill="both", expand=True, padx=10, pady=10)

            for nm, c in results:
                lb2.insert(tk.END, f"{nm} ({c})")

            def add_selected():
                sel = lb2.curselection()
                if not sel:
                    return
                nm, c = results[sel[0]]

                if any(x.code == c and x.market == "KR" for x in self.cfg.watchlist):
                    messagebox.showinfo("안내", "이미 추가된 종목입니다.", parent=top)
                    return

                wi = WatchItem(code=c, name=nm, market="KR", enabled=True, notify=False)
                self.cfg.watchlist.append(wi)
                with self.cache_lock:
                    self.cache[("KR", c)] = {"status": "loading", "ts": ""}

                save_config(self.cfg)
                refresh_list()
                self.tk_queue.put("REFRESH_MENU")
                self.executor.submit(self._refresh_all)
                top.destroy()

            ttk.Button(top, text="선택 종목 추가", command=add_selected).pack(pady=8)
            top.transient(win)
            top.grab_set()
            top.focus_force()

        # ---- 삭제/토글
        def remove_selected():
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            w = self.cfg.watchlist[idx]
            if messagebox.askyesno("삭제", f"{w.name}({w.code}) 삭제할까요?", parent=win):
                self.cfg.watchlist.pop(idx)
                with self.cache_lock:
                    self.cache.pop((w.market, w.code), None)
                save_config(self.cfg)
                refresh_list()
                self.tk_queue.put("REFRESH_MENU")

        def toggle_enabled():
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            self.cfg.watchlist[idx].enabled = not self.cfg.watchlist[idx].enabled
            save_config(self.cfg)
            refresh_list()
            self.tk_queue.put("REFRESH_MENU")
            self.executor.submit(self._refresh_all)

        # 자동 실행
        startup_var = tk.BooleanVar()

        def load_startup():
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"
                ) as key:
                    winreg.QueryValueEx(key, APP_NAME)
                    startup_var.set(True)
            except FileNotFoundError:
                startup_var.set(False)

        def toggle_startup():
            set_startup(startup_var.get())

        load_startup()
        ttk.Checkbutton(frm, text="Windows 시작 시 자동 실행", variable=startup_var, command=toggle_startup).pack(
            anchor="w", pady=6
        )

        # 버튼
        btnrow = ttk.Frame(frm)
        btnrow.pack(fill="x", pady=6)

        ttk.Button(btnrow, text="코드로 추가 (KR/US)", command=add_by_code).pack(side="left")
        ttk.Button(btnrow, text="종목명으로 추가 (KR)", command=search_by_name).pack(side="left", padx=6)
        ttk.Button(btnrow, text="삭제", command=remove_selected).pack(side="left", padx=6)
        ttk.Button(btnrow, text="활성/비활성", command=toggle_enabled).pack(side="left", padx=6)

        ttk.Button(frm, text="닫기", command=win.destroy).pack(anchor="e", pady=8)

        refresh_list()

        # 포커스/가시성
        win.update_idletasks()
        win.deiconify()
        win.lift()
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))
        win.focus_force()

    # -----------------------------------------------------
    # 종료 (트레이 종료 안 먹는 문제 방지)
    # -----------------------------------------------------
    def _quit(self):
        logging.info("APP: quitting")
        self.running = False

        # executor 종료
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

        # tray icon stop
        try:
            self.icon.stop()
        except Exception:
            pass

        # tk 종료는 반드시 메인스레드에서
        try:
            self.tk_root.after(0, self.tk_root.quit)
            self.tk_root.after(0, self.tk_root.destroy)
        except Exception:
            pass

        # exe에서 남는 경우 최후 수단
        try:
            os._exit(0)
        except Exception:
            pass

    # -----------------------------------------------------
    # run
    # -----------------------------------------------------
    def run(self):
        import tkinter as tk
        from PIL import Image, ImageTk

        self.tk_root = tk.Tk()
        self.tk_root.withdraw()

        # 🔥 아이콘 설정 추가
        icon_path = resource_path("icon.ico")
        try:
            img = ImageTk.PhotoImage(Image.open(icon_path))
            self.tk_root.iconphoto(True, img)
            self._tk_icon_img = img  # ← GC 방지 (중요)
        except Exception as e:
            logging.exception("icon load failed: %s", e)

        # 라이선스 오류가 있으면 즉시 알림 후 종료
        if self._serial_expired:
            self.tk_root.after(100, self._show_expired_and_quit)
            self.tk_root.mainloop()
            return

        if self._license_error:
            self.tk_root.after(100, lambda: self._show_license_error_and_quit(self._license_error))
            self.tk_root.mainloop()
            return

        # tray
        self.icon.run_detached()

        # tk queue pump
        self.tk_root.after(100, self._process_tk)

        # 주가창 즉시
        self.tk_root.after(300, self._open_price_window)

        # 시작 시 1회 갱신
        self.tk_root.after(500, lambda: self.executor.submit(self._refresh_all))

        # worker 시작
        self.tk_root.after(800, self.worker.start)

        self.tk_root.mainloop()
