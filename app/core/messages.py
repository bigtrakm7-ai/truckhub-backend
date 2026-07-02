"""Сообщения API на русском языке."""


class Msg:
    # Аутентификация
    CREDENTIALS_INVALID = "Не удалось проверить учётные данные"
    INACTIVE_USER = "Пользователь деактивирован"
    EMAIL_ALREADY_REGISTERED = "Электронная почта уже зарегистрирована"
    PHONE_ALREADY_REGISTERED = "Номер телефона уже зарегистрирован"
    INVALID_ROLE = "Недопустимое значение роли"
    INCORRECT_CREDENTIALS = "Неверная электронная почта или пароль"
    ACCOUNT_NOT_FOUND = "Аккаунт с такой почтой не найден. Пожалуйста, зарегистрируйтесь."
    INVALID_RESET = "Неверная электронная почта или код сброса"
    RESET_NOT_REQUESTED = "Код сброса не запрашивался или истёк"
    INVALID_RESET_CODE = "Неверный код сброса"
    RESET_CODE_EXPIRED = "Срок действия кода сброса истёк"
    RESET_CODE_SENT = "Если указанная почта существует, код сброса будет отправлен"
    PASSWORD_RESET_SUCCESS = "Пароль успешно изменён"
    INSUFFICIENT_PERMISSIONS = "Недостаточно прав для выполнения действия"
    ADMIN_ACCESS_REQUIRED = "Требуется доступ администратора"

    # Товары и каталог
    PRODUCT_NOT_FOUND = "Товар не найден"
    PRODUCTS_NOT_FOUND = "Товары не найдены"
    SECTION_NOT_FOUND = "Раздел не найден"
    PRODUCT_ARTICLE_EXISTS = "Товар с таким артикулом уже существует"
    NO_PRODUCT_IDS = "Не указаны идентификаторы товаров"
    NO_UPDATE_FIELDS = "Не указаны поля для обновления"
    PRODUCT_ARCHIVED = "Товар архивирован"

    # Заказы
    ORDER_NOT_FOUND = "Заказ не найден"
    NOT_YOUR_ORDER = "Это не ваш заказ"
    SHIPMENT_NOT_FOUND = "Отправление не найдено"
    SHIPMENT_ITEM_NOT_FOUND = "Позиция отправления не найдена"
    INVALID_STATUS = "Недопустимый статус"
    CART_ITEM_NOT_FOUND = "Позиция не найдена в корзине"
    CART_EMPTY = "Корзина пуста"

    # Гараж
    VEHICLE_VIN_EXISTS = "Транспортное средство с таким VIN уже существует"
    VEHICLE_NOT_FOUND = "Транспортное средство не найдено"
    VEHICLE_DELETED = "Транспортное средство удалено"
    DEFAULT_VEHICLE_SET = "Транспортное средство по умолчанию установлено"

    # B2B
    INN_REQUIRED_CREDIT = "Для заявки на кредит необходимо указать ИНН"
    INN_REQUIRED_DEFERRAL = "Для отсрочки платежа необходимо указать ИНН"
    INN_REQUIRED_QUOTE = "Для запроса коммерческого предложения необходимо указать ИНН"
    QUOTE_ITEMS_REQUIRED = "Необходимо указать хотя бы одну позицию"
    QUOTE_ITEM_QTY_POSITIVE = "Количество позиции должно быть больше нуля"
    QUOTE_NOT_FOUND = "Запрос коммерческого предложения не найден"
    NOT_YOUR_QUOTE = "Это не ваш запрос коммерческого предложения"

    # Поставщик
    PARSING_ERROR = "Ошибка разбора файла"
    FILENAME_REQUIRED = "Необходимо указать имя файла"
    CSV_ONLY = "Сейчас поддерживается только CSV"
    CSV_URL_REQUIRED = "Ссылка должна вести на CSV-файл"
    CSV_DOWNLOAD_FAILED = "Не удалось скачать CSV по ссылке"
    INSUFFICIENT_BALANCE = "Недостаточно средств на балансе"
    WITHDRAW_SUBMITTED = "Заявка на вывод средств отправлена"
    STATUS_UPDATED = "Статус обновлён"

    # Поддержка
    TICKET_NOT_FOUND = "Обращение не найдено"
    ASSIGNEE_MUST_BE_MANAGER = "Исполнитель должен быть менеджером или администратором"
    TICKET_ALREADY_CLOSED = "Обращение уже закрыто или решено"

    # Интеграция
    CSV_XML_ONLY = "Поддерживаются только форматы CSV и XML"
    DELIVERY_PROVIDER_UNAVAILABLE = "Служба доставки недоступна"
    NOTIFICATION_PROVIDER_UNAVAILABLE = "Сервис уведомлений недоступен"
    IMPORT_COMPLETED = "Импорт завершён"
    PRODUCTS_SYNCED = "Товары синхронизированы"

    # Сервис
    INVALID_BOOKING_STATUS = "Недопустимый статус записи"
    PARTNER_NOT_FOUND = "Партнёр не найден"
    SLOT_NOT_FOUND = "Слот не найден"
    SLOT_ALREADY_BOOKED = "Слот уже забронирован"
    BOOKING_NOT_FOUND = "Запись не найдена"
    INVALID_BOOKING_TRANSITION = "Недопустимый переход статуса записи"
    BOOKING_STATUS_UPDATED = "Статус записи обновлён"
    SLOTS_CREATED = "Слоты созданы"

    # Чат
    CONVERSATION_NOT_FOUND = "Беседа не найдена"
    ACCESS_DENIED = "Нет доступа"

    # Администрирование
    VERIFICATION_NOT_FOUND = "Верификация не найдена"
    VERIFICATION_APPROVED = "Верификация одобрена"
    VERIFICATION_REJECTED = "Верификация отклонена"
    COMMISSION_RULE_NOT_FOUND = "Правило комиссии не найдено"
    BANNER_NOT_FOUND = "Баннер не найден"
    DISPUTE_NOT_FOUND = "Спор не найден"
    DISPUTE_RESOLVED = "Спор решён"
    INN_ADDED_TO_STOP_LIST = "ИНН добавлен в стоп-лист"
    INN_REMOVED_FROM_STOP_LIST = "ИНН удалён из стоп-листа"
    INN_NOT_IN_STOP_LIST = "ИНН не найден в стоп-листе"

    # Возвраты
    RETURN_NOT_FOUND = "Заявка на возврат не найдена"
    RETURN_STATUS_UPDATED = "Статус возврата обновлён"
    TRACKING_UPDATED = "Трек-номер обновлён"

    # Корзина
    ITEM_ADDED_TO_CART = "Товар добавлен в корзину"
    CART_UPDATED = "Корзина обновлена"
    ITEM_REMOVED_FROM_CART = "Товар удалён из корзины"
    CART_CLEARED = "Корзина очищена"

    # Подписка
    SUBSCRIPTION_REQUIRED = "Для этой функции требуется подписка {tier} или выше"

    # Безопасность
    RATE_LIMIT_EXCEEDED = "Превышен лимит запросов. Повторите попытку позже."

    # Валидация
    WEIGHT_VOLUME_NUMBERS = "Поля weight_kg и volume_m3 должны быть числами"
    UNSUPPORTED_PROVIDER = "Неподдерживаемый провайдер"
    CITIES_REQUIRED = "Необходимо указать города отправления и назначения"
    INVALID_WEIGHT_VOLUME = "Недопустимые значения веса или объёма"
    UNSUPPORTED_CHANNEL = "Неподдерживаемый канал уведомлений"
    RECIPIENT_REQUIRED = "Необходимо указать получателя"
    MESSAGE_REQUIRED = "Необходимо указать текст сообщения"
    FILE_TYPE_NOT_ALLOWED = "Тип файла .{ext} не поддерживается. Допустимые: {allowed}"

    @staticmethod
    def registration_failed(reason: str) -> str:
        return f"Ошибка регистрации: {reason}"

    @staticmethod
    def product_not_found_id(product_id: str) -> str:
        return f"Товар не найден: {product_id}"

    @staticmethod
    def invalid_status_valid(valid: str) -> str:
        return f"Недопустимый статус. Допустимые: {valid}"

    @staticmethod
    def invalid_category_valid(valid: str) -> str:
        return f"Недопустимая категория. Допустимые: {valid}"

    @staticmethod
    def invalid_priority_valid(valid: str) -> str:
        return f"Недопустимый приоритет. Допустимые: {valid}"

    @staticmethod
    def parsing_error_detail(exc: Exception) -> str:
        return f"{Msg.PARSING_ERROR}: {exc}"

    @staticmethod
    def csv_download_error(error: str | None) -> str:
        return f"{Msg.CSV_DOWNLOAD_FAILED}: {error or 'неизвестная ошибка'}"

    @staticmethod
    def order_status_changed(order_number: str, status: str) -> str:
        return f"Заказ {order_number}: статус изменён на {status}"

    @staticmethod
    def return_status_changed(return_id: str, status: str) -> str:
        return f"Возврат {return_id}: статус изменён на {status}"

    @staticmethod
    def credit_request_submitted(amount: float) -> str:
        return f"Заявка на {amount} ₽ отправлена"

    @staticmethod
    def slots_created(count: int) -> str:
        return f"Создано слотов: {count}"

    @staticmethod
    def products_synced(count: int) -> str:
        return f"Синхронизировано товаров: {count}"

    @staticmethod
    def already_seeded(count: int) -> str:
        return f"База уже заполнена: {count} товаров"

    @staticmethod
    def seed_completed(products: int, categories: int, brands: int) -> str:
        return f"Добавлено: {products} товаров, {categories} категорий, {brands} брендов"

    @staticmethod
    def subscription_required(tier: str) -> str:
        return Msg.SUBSCRIPTION_REQUIRED.format(tier=tier)
