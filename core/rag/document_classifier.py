"""
Классификатор типов документов
"""
import re
from typing import Dict, Any, Optional
from loguru import logger


class DocumentClassifier:
    """Класс для определения типа документа"""
    
    # Паттерны для определения типов документов
    DOCUMENT_PATTERNS = {
        "contract": {
            "keywords": [
                "договор", "контракт", "соглашение", "договір", "контракт",
                "стороны", "сторона", "исполнитель", "заказчик", "подрядчик",
                "предмет договора", "предмет договору", "условия договора",
                "срок действия", "термін дії", "расторжение", "розірвання"
            ],
            "phrases": [
                "договор о", "договор на", "договор между", "договір про",
                "заключили настоящий договор", "уклали цей договір",
                "настоящий договор", "цей договір"
            ]
        },
        "court_case": {
            "keywords": [
                "суд", "судова", "справа", "рішення", "постановление",
                "постанова", "приговор", "вирок", "истец", "позивач",
                "ответчик", "відповідач", "судья", "суддя", "судопроизводство",
                "судочинство", "исковое заявление", "позовна заява"
            ],
            "phrases": [
                "судебное дело", "судова справа", "дело №", "справа №",
                "решение суда", "рішення суду", "постановление суда",
                "постанова суду"
            ]
        },
        "invoice": {
            "keywords": [
                "счет", "рахунок", "invoice", "накладная", "накладна",
                "квитанция", "квитанція", "чек", "чек", "чек-лист",
                "сумма к оплате", "сума до оплати", "итого", "підсумок"
            ],
            "phrases": [
                "счет на оплату", "рахунок на оплату", "выставить счет",
                "виставити рахунок", "к оплате", "до оплати"
            ]
        },
        "certificate": {
            "keywords": [
                "справка", "довідка", "свидетельство", "свідоцтво",
                "сертификат", "сертифікат", "удостоверение", "посвідчення"
            ],
            "phrases": [
                "выдана справка", "видана довідка", "настоящая справка",
                "ця довідка"
            ]
        },
        "act": {
            "keywords": [
                "акт", "акт", "приемки", "приймання", "выполненных работ",
                "виконаних робіт", "оказанных услуг", "наданих послуг"
            ],
            "phrases": [
                "акт выполненных работ", "акт виконаних робіт",
                "акт оказанных услуг", "акт наданих послуг",
                "акт приема-передачи", "акт прийому-передачі"
            ]
        },
        "power_of_attorney": {
            "keywords": [
                "доверенность", "довіреність", "уполномочиваю", "повноважу",
                "представитель", "представник", "доверитель", "довіритель"
            ],
            "phrases": [
                "настоящая доверенность", "ця довіреність",
                "доверяю право", "довіряю право"
            ]
        }
    }
    
    @staticmethod
    def detect_document_type(text: str, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Определение типа документа на основе текста и имени файла
        
        Args:
            text: Текст документа
            filename: Имя файла (опционально)
            
        Returns:
            Словарь с типом документа и уверенностью
        """
        if not text:
            return {"type": "unknown", "confidence": 0.0}
        
        text_lower = text.lower()
        filename_lower = filename.lower() if filename else ""
        
        scores = {}
        
        # Проверяем каждый тип документа
        for doc_type, patterns in DocumentClassifier.DOCUMENT_PATTERNS.items():
            score = 0.0
            
            # Проверяем ключевые слова
            for keyword in patterns["keywords"]:
                if keyword in text_lower:
                    score += 1.0
                if keyword in filename_lower:
                    score += 0.5
            
            # Проверяем фразы (более важные)
            for phrase in patterns["phrases"]:
                if phrase in text_lower:
                    score += 2.0
            
            scores[doc_type] = score
        
        # Определяем тип с наибольшим счетом
        if not scores or max(scores.values()) == 0:
            return {"type": "unknown", "confidence": 0.0}
        
        max_type = max(scores, key=scores.get)
        max_score = scores[max_type]
        
        # Нормализуем уверенность (0.0 - 1.0)
        total_score = sum(scores.values())
        confidence = min(max_score / max(total_score, 1.0), 1.0)
        
        # Если уверенность слишком низкая, считаем неизвестным
        if confidence < 0.3:
            return {"type": "unknown", "confidence": confidence}
        
        return {
            "type": max_type,
            "confidence": confidence,
            "all_scores": scores
        }
    
    @staticmethod
    def get_suggested_actions(doc_type: str, query: Optional[str] = None) -> list:
        """
        Получение предложенных действий на основе типа документа
        
        Args:
            doc_type: Тип документа
            query: Запрос пользователя (опционально)
            
        Returns:
            Список предложенных действий
        """
        actions_map = {
            "contract": [
                {"id": "analyze_contract", "label": "Проанализировать договор", "type": "action"},
                {"id": "check_terms", "label": "Проверить условия договора", "type": "action"},
                {"id": "find_risks", "label": "Найти риски в договоре", "type": "action"},
                {"id": "summarize", "label": "Краткое содержание договора", "type": "action"}
            ],
            "court_case": [
                {"id": "analyze_case", "label": "Проанализировать судебное дело", "type": "action"},
                {"id": "find_similar", "label": "Найти похожие дела", "type": "action"},
                {"id": "summarize_decision", "label": "Краткое содержание решения", "type": "action"},
                {"id": "check_appeal", "label": "Проверить возможность обжалования", "type": "action"}
            ],
            "invoice": [
                {"id": "check_invoice", "label": "Проверить счет", "type": "action"},
                {"id": "extract_data", "label": "Извлечь данные из счета", "type": "action"},
                {"id": "verify_amount", "label": "Проверить сумму", "type": "action"}
            ],
            "certificate": [
                {"id": "verify_certificate", "label": "Проверить справку", "type": "action"},
                {"id": "extract_info", "label": "Извлечь информацию", "type": "action"}
            ],
            "act": [
                {"id": "check_act", "label": "Проверить акт", "type": "action"},
                {"id": "verify_works", "label": "Проверить выполненные работы", "type": "action"}
            ],
            "power_of_attorney": [
                {"id": "analyze_power", "label": "Проанализировать доверенность", "type": "action"},
                {"id": "check_authority", "label": "Проверить полномочия", "type": "action"},
                {"id": "verify_validity", "label": "Проверить срок действия", "type": "action"}
            ],
            "unknown": [
                {"id": "analyze_document", "label": "Проанализировать документ", "type": "action"},
                {"id": "summarize", "label": "Краткое содержание", "type": "action"},
                {"id": "extract_key_info", "label": "Извлечь ключевую информацию", "type": "action"}
            ]
        }
        
        return actions_map.get(doc_type, actions_map["unknown"])

