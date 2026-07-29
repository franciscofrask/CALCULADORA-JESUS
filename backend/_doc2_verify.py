# -*- coding: utf-8 -*-
"""Verifica por codigo (sin imagenes) que ciertos overlays/estados inciertos se abren."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
BASE="http://localhost:3000"

def vis(page, sel, t=2500):
    try: return page.locator(sel).first.is_visible(timeout=t)
    except Exception: return False

def has_text(page, txt, t=2500):
    try: return page.get_by_text(txt, exact=False).first.is_visible(timeout=t)
    except Exception: return False

with sync_playwright() as p:
    b=p.chromium.launch(headless=True); pg=b.new_context(viewport={"width":1400,"height":1000}).new_page()
    pg.set_default_timeout(12000)
    def login(e,w):
        pg.goto(f"{BASE}/auth")
        try: pg.evaluate("()=>localStorage.clear()")
        except Exception: pass
        pg.goto(f"{BASE}/auth"); pg.wait_for_timeout(700)
        pg.get_by_placeholder("Email").fill(e); pg.get_by_placeholder("Contraseña").fill(w)
        pg.get_by_role("button",name="Entrar").click(); pg.wait_for_timeout(2600)

    login("clientedemo@test.com","demo123")
    pg.goto(f"{BASE}/dashboard/nutrition"); pg.wait_for_timeout(2500)
    try: pg.locator('[data-testid="start-intro-btn"]').first.click(timeout=3000)
    except Exception:
        try: pg.locator('[data-testid="close-intro-btn"]').first.click(timeout=2000)
        except Exception: pass
    pg.wait_for_timeout(800)
    # preferencias
    try: pg.locator('[data-testid="open-preferences-btn"]').first.click(timeout=4000)
    except Exception: pass
    pg.wait_for_timeout(1000)
    print("PREFERENCIAS abre:", vis(pg,'[data-testid="save-preferences-btn"]') or has_text(pg,"preferencias"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(600)
    # calendario
    try: pg.locator('[data-testid="open-calendar-btn"]').first.click(timeout=4000)
    except Exception: pass
    pg.wait_for_timeout(1000)
    print("CALENDARIO abre:", vis(pg,'[data-testid="diet-calendar-modal"]') or vis(pg,'[data-testid^="cal-day-"]'))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(600)
    # copiar dieta
    try: pg.get_by_role("button",name="Copiar",exact=False).first.click(timeout=4000)
    except Exception: pass
    pg.wait_for_timeout(900)
    print("COPIAR DIETA abre:", vis(pg,'[data-testid="copy-date-input"]') or vis(pg,'[data-testid="copy-diet-modal"]'))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    # chatbot
    pg.goto(f"{BASE}/dashboard/chatbot"); pg.wait_for_timeout(1500)
    try: pg.get_by_role("button",name="Empezar",exact=False).first.click(timeout=4000)
    except Exception: pass
    pg.wait_for_timeout(2000)
    for lbl in ("Hoy","Entrenamiento"):
        try: pg.get_by_role("button",name=lbl,exact=False).first.click(timeout=3000); pg.wait_for_timeout(1800)
        except Exception: pass
    txt=""
    try: txt=pg.locator('[data-testid="chatbot-heading"]').first.inner_text(timeout=2000)
    except Exception: pass
    print("CHATBOT avanzo (input visible):", vis(pg,'[data-testid="chat-input"]'), "| burbujas:", pg.locator(".rounded-2xl, [class*=bubble]").count())

    login("francisco@test.com","demo123")
    pg.goto(f"{BASE}/admin/clients/20e8b4c4-98d1-43bc-ad74-06df9ddc8c94"); pg.wait_for_timeout(2200)
    try: pg.locator('[data-testid="tab-menus"]').first.click(timeout=3000); pg.wait_for_timeout(800)
    except Exception: pass
    for tid,v in (("menufinder-P","160"),("menufinder-H","250"),("menufinder-G","70")):
        try: pg.locator(f'[data-testid="{tid}"]').first.fill(v)
        except Exception: pass
    try: pg.locator('[data-testid="menufinder-buscar"]').first.click(timeout=3000)
    except Exception: pass
    pg.wait_for_timeout(2500)
    print("MENU-FINDER resultados:", pg.locator('[data-testid^="menufinder-result-"]').count())
    pg.goto(f"{BASE}/admin/messages"); pg.wait_for_timeout(1800)
    print("ADMIN conversaciones:", pg.locator('[data-testid^="conv-"]').count())
    b.close()
