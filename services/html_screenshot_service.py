"""
Сервис для создания скриншотов HTML и отправки в Vision API для OCR
"""
import os
import sys
import asyncio
import tempfile
import importlib.util
from pathlib import Path
from typing import Optional, Dict, Any
from io import BytesIO

# Убеждаемся, что python-multipart установлен
try:
    import multipart
except ImportError:
    print("WARNING: python-multipart not found, installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-multipart"])
    import multipart

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page
import httpx

# Добавляем путь к корню проекта для импорта модулей
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    # Пробуем импортировать из корня проекта
    from core.rag.vision_client import VisionAPIClient
    from config import settings
except ImportError:
    try:
        # Пробуем импортировать напрямую (для Docker)
        import importlib.util
        vision_client_path = project_root / "core" / "rag" / "vision_client.py"
        config_path = project_root / "config.py"
        
        if vision_client_path.exists() and config_path.exists():
            spec_vision = importlib.util.spec_from_file_location("vision_client", vision_client_path)
            vision_client_module = importlib.util.module_from_spec(spec_vision)
            spec_vision.loader.exec_module(vision_client_module)
            VisionAPIClient = vision_client_module.VisionAPIClient
            
            spec_config = importlib.util.spec_from_file_location("config", config_path)
            config_module = importlib.util.module_from_spec(spec_config)
            spec_config.loader.exec_module(config_module)
            settings = config_module.settings
        else:
            raise ImportError("Config files not found")
    except Exception as e:
        logger.error(f"Failed to import modules: {e}")
        logger.warning("Running in standalone mode without config")
        settings = None
        VisionAPIClient = None

app = FastAPI(title="HTML Screenshot Service", version="1.0.0")

# Глобальные переменные для браузера
_browser: Optional[Browser] = None
_playwright = None


class HTMLScreenshotRequest(BaseModel):
    """Модель запроса для создания скриншота HTML"""
    html_content: Optional[str] = None
    html_url: Optional[str] = None
    viewport_width: int = 1920
    viewport_height: int = 1080
    wait_time: int = 1000  # Время ожидания после загрузки страницы (мс)
    full_page: bool = True  # Делать скриншот всей страницы или только видимой области
    language_hints: Optional[list] = None


class ScreenshotResponse(BaseModel):
    """Модель ответа с результатом скриншота"""
    success: bool
    screenshot_size: Optional[int] = None
    text: Optional[str] = None
    error: Optional[str] = None


async def init_browser():
    """Инициализация браузера Playwright"""
    global _browser, _playwright
    
    if _browser is None:
        logger.info("Initializing Playwright browser...")
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
            ]
        )
        logger.info("Browser initialized successfully")
    
    return _browser


async def close_browser():
    """Закрытие браузера Playwright"""
    global _browser, _playwright
    
    if _browser:
        logger.info("Closing browser...")
        await _browser.close()
        _browser = None
    
    if _playwright:
        await _playwright.stop()
        _playwright = None


async def create_screenshot_from_html(
    html_content: str,
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    wait_time: int = 1000,
    full_page: bool = True
) -> bytes:
    """
    Создание скриншота из HTML контента
    
    Args:
        html_content: HTML контент для рендеринга
        viewport_width: Ширина viewport
        viewport_height: Высота viewport
        wait_time: Время ожидания после загрузки (мс)
        full_page: Делать скриншот всей страницы
        
    Returns:
        Байты изображения PNG
    """
    browser = await init_browser()
    
    # Создаем временный HTML файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp_file:
        tmp_file.write(html_content)
        tmp_file_path = tmp_file.name
    
    try:
        # Создаем новую страницу
        page = await browser.new_page(
            viewport={'width': viewport_width, 'height': viewport_height}
        )
        
        try:
            # Загружаем HTML файл
            file_url = f"file://{tmp_file_path}"
            await page.goto(file_url, wait_until='networkidle', timeout=30000)
            
            # Ждем указанное время для полной загрузки
            if wait_time > 0:
                await page.wait_for_timeout(wait_time)
            
            # Делаем скриншот
            screenshot_bytes = await page.screenshot(
                type='png',
                full_page=full_page,
                timeout=30000
            )
            
            logger.info(f"Screenshot created: {len(screenshot_bytes)} bytes")
            return screenshot_bytes
            
        finally:
            await page.close()
            
    finally:
        # Удаляем временный файл
        try:
            os.unlink(tmp_file_path)
        except Exception as e:
            logger.warning(f"Failed to delete temp file {tmp_file_path}: {e}")


async def create_screenshot_from_url(
    url: str,
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    wait_time: int = 1000,
    full_page: bool = True
) -> bytes:
    """
    Создание скриншота из URL
    
    Args:
        url: URL для загрузки
        viewport_width: Ширина viewport
        viewport_height: Высота viewport
        wait_time: Время ожидания после загрузки (мс)
        full_page: Делать скриншот всей страницы
        
    Returns:
        Байты изображения PNG
    """
    browser = await init_browser()
    page = await browser.new_page(
        viewport={'width': viewport_width, 'height': viewport_height}
    )
    
    try:
        # Загружаем URL
        await page.goto(url, wait_until='networkidle', timeout=30000)
        
        # Ждем указанное время для полной загрузки
        if wait_time > 0:
            await page.wait_for_timeout(wait_time)
        
        # Делаем скриншот
        screenshot_bytes = await page.screenshot(
            type='png',
            full_page=full_page,
            timeout=30000
        )
        
        logger.info(f"Screenshot created from URL: {len(screenshot_bytes)} bytes")
        return screenshot_bytes
        
    finally:
        await page.close()


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    logger.info("Starting HTML Screenshot Service...")
    await init_browser()
    logger.info("Service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при остановке"""
    logger.info("Shutting down HTML Screenshot Service...")
    await close_browser()
    logger.info("Service stopped")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "html-screenshot-service",
        "browser_initialized": _browser is not None,
        "vision_api_available": VisionAPIClient is not None and settings and bool(settings.vision_api_key) if settings else False
    }


@app.post("/screenshot", response_model=ScreenshotResponse)
async def create_screenshot(
    request: HTMLScreenshotRequest
):
    """
    Создание скриншота из HTML и отправка в Vision API для OCR
    
    Args:
        request: Запрос с HTML контентом или URL
        
    Returns:
        Результат с извлеченным текстом
    """
    try:
        # Проверяем, что есть либо HTML контент, либо URL
        if not request.html_content and not request.html_url:
            raise HTTPException(
                status_code=400,
                detail="Either html_content or html_url must be provided"
            )
        
        # Создаем скриншот
        if request.html_content:
            logger.info("Creating screenshot from HTML content...")
            screenshot_bytes = await create_screenshot_from_html(
                html_content=request.html_content,
                viewport_width=request.viewport_width,
                viewport_height=request.viewport_height,
                wait_time=request.wait_time,
                full_page=request.full_page
            )
        else:
            logger.info(f"Creating screenshot from URL: {request.html_url}")
            screenshot_bytes = await create_screenshot_from_url(
                url=request.html_url,
                viewport_width=request.viewport_width,
                viewport_height=request.viewport_height,
                wait_time=request.wait_time,
                full_page=request.full_page
            )
        
        # Отправляем в Vision API для OCR
        text = None
        if VisionAPIClient and settings and settings.vision_api_key:
            logger.info("Sending screenshot to Vision API for OCR...")
            vision_client = VisionAPIClient()
            
            if vision_client.is_available():
                try:
                    text = await vision_client.extract_text_from_image(
                        image_data=screenshot_bytes,
                        filename="screenshot.png",
                        language_hints=request.language_hints
                    )
                    logger.info(f"Text extracted via Vision API: {len(text) if text else 0} characters")
                except Exception as e:
                    logger.error(f"Error extracting text via Vision API: {e}")
                    # Не возвращаем ошибку, просто не извлекаем текст
            else:
                logger.warning("Vision API is not available (no API key)")
        else:
            logger.warning("Vision API client is not available")
        
        return ScreenshotResponse(
            success=True,
            screenshot_size=len(screenshot_bytes),
            text=text
        )
        
    except Exception as e:
        logger.error(f"Error creating screenshot: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return ScreenshotResponse(
            success=False,
            error=str(e)
        )


@app.post("/screenshot/upload", response_model=ScreenshotResponse)
async def create_screenshot_from_file(
    file: UploadFile = File(...),
    viewport_width: int = Form(1920),
    viewport_height: int = Form(1080),
    wait_time: int = Form(1000),
    full_page: bool = Form(True),
    language_hints: Optional[str] = Form(None)
):
    """
    Создание скриншота из загруженного HTML файла
    
    Args:
        file: HTML файл
        viewport_width: Ширина viewport
        viewport_height: Высота viewport
        wait_time: Время ожидания после загрузки (мс)
        full_page: Делать скриншот всей страницы
        language_hints: Подсказки по языкам (через запятую)
        
    Returns:
        Результат с извлеченным текстом
    """
    try:
        # Читаем HTML контент из файла
        html_content = await file.read()
        
        # Определяем кодировку
        encoding = 'utf-8'
        try:
            html_text = html_content.decode(encoding)
        except UnicodeDecodeError:
            # Пробуем другие кодировки
            for enc in ['windows-1251', 'iso-8859-1', 'cp1252']:
                try:
                    html_text = html_content.decode(enc)
                    encoding = enc
                    logger.info(f"Detected encoding: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to decode HTML file. Unsupported encoding."
                )
        
        # Парсим language hints
        hints = None
        if language_hints:
            hints = [h.strip() for h in language_hints.split(',')]
        
        # Создаем скриншот
        logger.info(f"Creating screenshot from uploaded file: {file.filename}")
        screenshot_bytes = await create_screenshot_from_html(
            html_content=html_text,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            wait_time=wait_time,
            full_page=full_page
        )
        
        # Отправляем в Vision API для OCR
        text = None
        if VisionAPIClient and settings and settings.vision_api_key:
            logger.info("Sending screenshot to Vision API for OCR...")
            vision_client = VisionAPIClient()
            
            if vision_client.is_available():
                try:
                    text = await vision_client.extract_text_from_image(
                        image_data=screenshot_bytes,
                        filename="screenshot.png",
                        language_hints=hints
                    )
                    logger.info(f"Text extracted via Vision API: {len(text) if text else 0} characters")
                except Exception as e:
                    logger.error(f"Error extracting text via Vision API: {e}")
        else:
            logger.warning("Vision API client is not available")
        
        return ScreenshotResponse(
            success=True,
            screenshot_size=len(screenshot_bytes),
            text=text
        )
        
    except Exception as e:
        logger.error(f"Error processing uploaded file: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return ScreenshotResponse(
            success=False,
            error=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3015"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting HTML Screenshot Service on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")

