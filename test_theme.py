"""
Automated tests for Light & Dark Theme Feature
"""
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_theme_toggle_elements_present_in_html(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    
    # 1. Immediate FOUC prevention script in <head>
    assert "data-theme" in html
    assert "campusnet_theme" in html
    
    # 2. Theme toggle button in header-actions
    assert 'id="theme-toggle-btn"' in html
    assert 'class="theme-toggle-btn"' in html
    assert 'class="theme-switch-track"' in html
    assert 'id="theme-toggle-label"' in html
    assert 'Dark' in html

def test_static_theme_assets_serve_correctly(client):
    # CSS check
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    css = css_res.data.decode("utf-8")
    assert '[data-theme="light"]' in css
    assert '[data-theme="dark"]' in css
    assert '.theme-toggle-btn' in css
    assert '.theme-switch-thumb' in css

    # JS check
    js_res = client.get("/static/js/dashboard.js")
    assert js_res.status_code == 200
    js = js_res.data.decode("utf-8")
    assert "initTheme" in js
    assert "toggleTheme" in js
    assert "setTheme" in js
    assert "getChartThemeColors" in js
    assert "themeToggleBtn" in js
