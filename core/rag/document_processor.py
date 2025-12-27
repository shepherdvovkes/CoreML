"""
Обработчик документов для RAG с использованием LangChain loaders и splitters
"""
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger
from config import settings

# LangChain imports
try:
    from langchain_community.document_loaders import (
        PyPDFLoader,
        Docx2txtLoader,
        UnstructuredExcelLoader,
        TextLoader,
    )
    from langchain_text_splitters import RecursiveCharacterTextSplitter, CharacterTextSplitter
    from langchain_core.documents import Document as LangChainDocument
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LangChain not fully available: {e}. Falling back to basic implementations.")
    LANGCHAIN_AVAILABLE = False
    LangChainDocument = None
    # Fallback imports для обратной совместимости
    try:
        import PyPDF2
        from docx import Document
        import openpyxl
    except ImportError:
        pass


class DocumentProcessor:
    """Класс для обработки различных типов документов с использованием LangChain"""
    
    def __init__(self):
        """Инициализация процессора документов"""
        # Инициализация text splitter из LangChain
        if LANGCHAIN_AVAILABLE:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.rag_chunk_size,
                chunk_overlap=settings.rag_chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
        else:
            self.text_splitter = None
    
    @staticmethod
    def _load_with_langchain(file_path: str) -> Optional[str]:
        """Загрузка документа с использованием LangChain loaders"""
        if not LANGCHAIN_AVAILABLE:
            return None
        
        try:
            file_ext = Path(file_path).suffix.lower()
            loader = None
            
            if file_ext == '.pdf':
                loader = PyPDFLoader(file_path)
            elif file_ext == '.docx':
                loader = Docx2txtLoader(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                loader = UnstructuredExcelLoader(file_path)
            elif file_ext == '.txt':
                loader = TextLoader(file_path, encoding='utf-8')
            else:
                return None
            
            # Загрузка документов
            documents = loader.load()
            
            # Объединение всех страниц/частей в один текст
            text = "\n\n".join([doc.page_content for doc in documents])
            return text
            
        except Exception as e:
            logger.error(f"Error loading document with LangChain {file_path}: {e}")
            return None
    
    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """Извлечение текста из PDF (с fallback на PyPDF2)"""
        # Пробуем LangChain loader
        text = DocumentProcessor._load_with_langchain(file_path)
        if text is not None:
            return text
        
        # Fallback на старую реализацию
        if not LANGCHAIN_AVAILABLE:
            try:
                text = ""
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                return text
            except Exception as e:
                logger.error(f"Error extracting text from PDF {file_path}: {e}")
                return ""
        return ""
    
    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        """Извлечение текста из DOCX (с fallback на python-docx)"""
        # Пробуем LangChain loader
        text = DocumentProcessor._load_with_langchain(file_path)
        if text is not None:
            return text
        
        # Fallback на старую реализацию
        if not LANGCHAIN_AVAILABLE:
            try:
                doc = Document(file_path)
                text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
                return text
            except Exception as e:
                logger.error(f"Error extracting text from DOCX {file_path}: {e}")
                return ""
        return ""
    
    @staticmethod
    def extract_text_from_xlsx(file_path: str) -> str:
        """Извлечение текста из XLSX (с fallback на openpyxl)"""
        # Пробуем LangChain loader
        text = DocumentProcessor._load_with_langchain(file_path)
        if text is not None:
            return text
        
        # Fallback на старую реализацию
        if not LANGCHAIN_AVAILABLE:
            try:
                workbook = openpyxl.load_workbook(file_path)
                text = ""
                for sheet in workbook.worksheets:
                    for row in sheet.iter_rows(values_only=True):
                        text += " ".join([str(cell) if cell else "" for cell in row]) + "\n"
                return text
            except Exception as e:
                logger.error(f"Error extracting text from XLSX {file_path}: {e}")
                return ""
        return ""
    
    @staticmethod
    def extract_text_from_txt(file_path: str) -> str:
        """Извлечение текста из TXT"""
        # Пробуем LangChain loader
        text = DocumentProcessor._load_with_langchain(file_path)
        if text is not None:
            return text
        
        # Fallback на старую реализацию
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error reading TXT file {file_path}: {e}")
            return ""
    
    @classmethod
    def process_document(cls, file_path: str) -> str:
        """Обработка документа любого поддерживаемого типа"""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            return cls.extract_text_from_pdf(file_path)
        elif file_ext == '.docx':
            return cls.extract_text_from_docx(file_path)
        elif file_ext == '.xlsx' or file_ext == '.xls':
            return cls.extract_text_from_xlsx(file_path)
        elif file_ext == '.txt':
            return cls.extract_text_from_txt(file_path)
        else:
            logger.warning(f"Unsupported file type: {file_ext}")
            return ""
    
    def chunk_text(self, text: str, chunk_size: int = None, chunk_overlap: int = None) -> List[str]:
        """Разбиение текста на чанки с использованием LangChain text splitter"""
        # Используем LangChain text splitter если доступен
        if self.text_splitter and LANGCHAIN_AVAILABLE:
            # Обновляем параметры если переданы
            if chunk_size is not None or chunk_overlap is not None:
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size or settings.rag_chunk_size,
                    chunk_overlap=chunk_overlap or settings.rag_chunk_overlap,
                    length_function=len,
                    separators=["\n\n", "\n", " ", ""]
                )
            else:
                splitter = self.text_splitter
            
            # Создаем временный документ для splitter
            doc = LangChainDocument(page_content=text)
            chunks = splitter.split_documents([doc])
            return [chunk.page_content for chunk in chunks]
        
        # Fallback на старую реализацию
        chunk_size = chunk_size or settings.rag_chunk_size
        chunk_overlap = chunk_overlap or settings.rag_chunk_overlap
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - chunk_overlap
        
        return chunks

