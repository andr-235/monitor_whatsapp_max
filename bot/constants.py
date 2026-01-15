"""Пользовательские сообщения бота и значения по умолчанию для команд."""

START_MESSAGE = (
    "Добро пожаловать!\n"
    "Команды:\n"
    "/recent [N] - показать последние сообщения (по умолчанию 10)\n"
    "/add_keyword <слово> - добавить ключевое слово\n"
    "/remove_keyword <слово> - удалить ключевое слово\n"
    "/list_keywords - список ваших ключевых слов\n"
    "/search - поиск сообщений по вашим ключевым словам"
)

RECENT_USAGE = "Использование: /recent [N]"
ADD_KEYWORD_USAGE = "Использование: /add_keyword <слово>"
REMOVE_KEYWORD_USAGE = "Использование: /remove_keyword <слово>"
NO_KEYWORDS_MESSAGE = "Ключевые слова не заданы. Используйте /add_keyword <слово>."
NO_RESULTS_MESSAGE = "Сообщения не найдены."
DB_ERROR_MESSAGE = "База данных временно недоступна. Попробуйте позже."
KEYWORD_ADDED_MESSAGE = "Ключевое слово добавлено."
KEYWORD_EXISTS_MESSAGE = "Ключевое слово уже существует."
KEYWORD_REMOVED_MESSAGE = "Ключевое слово удалено."
KEYWORD_NOT_FOUND_MESSAGE = "Ключевое слово не найдено."
KEYWORDS_LIST_HEADER = "Ключевые слова:"
