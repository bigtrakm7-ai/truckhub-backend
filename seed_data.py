"""Seed database with truck parts catalog data"""

CATEGORIES = [
    {"id": "cat-engine", "name": "Двигатель", "slug": "dvigatel", "description": "Запчасти для двигателя грузовиков"},
    {"id": "cat-transmission", "name": "Трансмиссия", "slug": "transmissiya", "description": "КПП, сцепление, карданный вал"},
    {"id": "cat-brakes", "name": "Тормозная система", "slug": "tormoznaya-sistema", "description": "Колодки, диски, суппорта, ABS"},
    {"id": "cat-suspension", "name": "Подвеска и ходовая", "slug": "podveska", "description": "Рессоры, амортизаторы, ступицы"},
    {"id": "cat-steering", "name": "Рулевое управление", "slug": "rulevoe", "description": "ГУР, рулевые тяги, наконечники"},
    {"id": "cat-electrical", "name": "Электрика", "slug": "elektrika", "description": "Стартеры, генераторы, датчики, проводка"},
    {"id": "cat-body", "name": "Кабина и кузов", "slug": "kabina-kuzov", "description": "Двери, зеркала, стёкла, обвес"},
    {"id": "cat-exhaust", "name": "Выхлопная система", "slug": "vykhlopnaya", "description": "Глушители, катализаторы, EGR, AdBlue"},
    {"id": "cat-fuel", "name": "Топливная система", "slug": "toplivnaya", "description": "ТНВД, форсунки, фильтры топлива"},
    {"id": "cat-cooling", "name": "Система охлаждения", "slug": "okhlazhdeniye", "description": "Радиаторы, термостаты, помпы, патрубки"},
    {"id": "cat-filters", "name": "Фильтры и масла", "slug": "filtry-masla", "description": "Масляные, воздушные, топливные фильтры, моторные масла"},
    {"id": "cat-lighting", "name": "Оптика и освещение", "slug": "optika", "description": "Фары, фонари, лампы, LED"},
]

BRANDS = [
    {"id": "brand-kamaz", "name": "КАМАЗ", "slug": "kamaz", "country": "Россия"},
    {"id": "brand-maz", "name": "МАЗ", "slug": "maz", "country": "Беларусь"},
    {"id": "brand-gaz", "name": "ГАЗ", "slug": "gaz", "country": "Россия"},
    {"id": "brand-ural", "name": "Урал", "slug": "ural", "country": "Россия"},
    {"id": "brand-volvo", "name": "Volvo", "slug": "volvo", "country": "Швеция"},
    {"id": "brand-scania", "name": "Scania", "slug": "scania", "country": "Швеция"},
    {"id": "brand-man", "name": "MAN", "slug": "man", "country": "Германия"},
    {"id": "brand-daf", "name": "DAF", "slug": "daf", "country": "Нидерланды"},
    {"id": "brand-mercedes", "name": "Mercedes-Benz", "slug": "mercedes", "country": "Германия"},
    {"id": "brand-iveco", "name": "Iveco", "slug": "iveco", "country": "Италия"},
    {"id": "brand-renault", "name": "Renault Trucks", "slug": "renault", "country": "Франция"},
    {"id": "brand-hino", "name": "Hino", "slug": "hino", "country": "Япония"},
    {"id": "brand-isuzu", "name": "Isuzu", "slug": "isuzu", "country": "Япония"},
    {"id": "brand-foton", "name": "Foton", "slug": "foton", "country": "Китай"},
    {"id": "brand-faw", "name": "FAW", "slug": "faw", "country": "Китай"},
    {"id": "brand-shacman", "name": "Shacman", "slug": "shacman", "country": "Китай"},
    {"id": "brand-dongfeng", "name": "Dongfeng", "slug": "dongfeng", "country": "Китай"},
]

SUPPLIERS = [
    {"id": "sup-1", "name": "АвтоТрак", "slug": "avtotrak", "city": "Москва", "rating": 4.8},
    {"id": "sup-2", "name": "ГрузЗапчасть", "slug": "gruzzapchast", "city": "Санкт-Петербург", "rating": 4.6},
    {"id": "sup-3", "name": "ТракПартс", "slug": "trakparts", "city": "Казань", "rating": 4.7},
    {"id": "sup-4", "name": "КамДеталь", "slug": "kamdetal", "city": "Набережные Челны", "rating": 4.9},
    {"id": "sup-5", "name": "ЕвроГруз", "slug": "eurogruz", "city": "Екатеринбург", "rating": 4.5},
]

PRODUCTS = [
    # Двигатель
    {"article": "740.1003010", "name": "Головка блока цилиндров КАМАЗ-740", "category_id": "cat-engine", "brand_id": "brand-kamaz", "price": 18500, "old_price": 22000, "stock_quantity": 12, "applicability": "КАМАЗ-740, КАМАЗ-5320, КАМАЗ-65115"},
    {"article": "236-1000102", "name": "Блок цилиндров ЯМЗ-236", "category_id": "cat-engine", "brand_id": "brand-maz", "price": 45000, "old_price": 52000, "stock_quantity": 5, "applicability": "МАЗ-5336, МАЗ-6303, Урал-4320"},
    {"article": "D12-420", "name": "Турбокомпрессор Volvo D12", "category_id": "cat-engine", "brand_id": "brand-volvo", "price": 67000, "old_price": 78000, "stock_quantity": 3, "applicability": "Volvo FH12, Volvo FM12"},
    {"article": "51.09100-7766", "name": "Поршневая группа MAN D2066", "category_id": "cat-engine", "brand_id": "brand-man", "price": 32000, "stock_quantity": 8, "applicability": "MAN TGA, MAN TGS, MAN TGX"},
    {"article": "1677742", "name": "Водяной насос (помпа) Scania DC12", "category_id": "cat-engine", "brand_id": "brand-scania", "price": 15800, "old_price": 19000, "stock_quantity": 15, "applicability": "Scania R-серия, Scania P-серия"},
    {"article": "5010550603", "name": "Прокладка ГБЦ Renault DXi", "category_id": "cat-engine", "brand_id": "brand-renault", "price": 4200, "stock_quantity": 25, "applicability": "Renault Premium, Renault Magnum"},
    {"article": "612600110848", "name": "Масляный насос Weichai WP10", "category_id": "cat-engine", "brand_id": "brand-shacman", "price": 12500, "old_price": 14500, "stock_quantity": 10, "applicability": "Shacman F3000, Shacman X3000"},
    
    # Трансмиссия
    {"article": "141.1701025", "name": "КПП КАМАЗ ZF-9S1310", "category_id": "cat-transmission", "brand_id": "brand-kamaz", "price": 185000, "old_price": 210000, "stock_quantity": 2, "applicability": "КАМАЗ-65115, КАМАЗ-6520, КАМАЗ-43118"},
    {"article": "3521-1601130", "name": "Диск сцепления МАЗ", "category_id": "cat-transmission", "brand_id": "brand-maz", "price": 8900, "stock_quantity": 20, "applicability": "МАЗ-5440, МАЗ-6430"},
    {"article": "85000517", "name": "Корзина сцепления Volvo", "category_id": "cat-transmission", "brand_id": "brand-volvo", "price": 34000, "old_price": 39000, "stock_quantity": 6, "applicability": "Volvo FH, Volvo FM"},
    {"article": "81.32003.6567", "name": "Синхронизатор КПП MAN ZF", "category_id": "cat-transmission", "brand_id": "brand-man", "price": 11500, "stock_quantity": 14, "applicability": "MAN TGA, MAN TGS"},
    {"article": "1749124", "name": "Кардан вал Scania", "category_id": "cat-transmission", "brand_id": "brand-scania", "price": 42000, "stock_quantity": 4, "applicability": "Scania R420, Scania R480"},
    
    # Тормозная система
    {"article": "53205-3501090", "name": "Колодки тормозные КАМАЗ (комплект)", "category_id": "cat-brakes", "brand_id": "brand-kamaz", "price": 3200, "stock_quantity": 50, "applicability": "КАМАЗ-5320, КАМАЗ-65115, КАМАЗ-6520"},
    {"article": "5440-3501105", "name": "Диск тормозной МАЗ", "category_id": "cat-brakes", "brand_id": "brand-maz", "price": 7800, "old_price": 9200, "stock_quantity": 18, "applicability": "МАЗ-5440, МАЗ-6430, МАЗ-5550"},
    {"article": "21225024", "name": "Суппорт тормозной Volvo", "category_id": "cat-brakes", "brand_id": "brand-volvo", "price": 28000, "stock_quantity": 7, "applicability": "Volvo FH, Volvo FM, Volvo FMX"},
    {"article": "81.50804.6693", "name": "Энергоаккумулятор MAN", "category_id": "cat-brakes", "brand_id": "brand-man", "price": 9500, "old_price": 11000, "stock_quantity": 22, "applicability": "MAN TGA, MAN TGS, MAN TGX"},
    {"article": "1928624", "name": "Кран тормозной Scania EBS", "category_id": "cat-brakes", "brand_id": "brand-scania", "price": 19500, "stock_quantity": 5, "applicability": "Scania R-серия, Scania G-серия"},
    {"article": "1689313", "name": "Тормозной барабан DAF", "category_id": "cat-brakes", "brand_id": "brand-daf", "price": 8200, "stock_quantity": 12, "applicability": "DAF XF95, DAF XF105, DAF CF"},
    
    # Подвеска и ходовая
    {"article": "65115-2902012", "name": "Рессора передняя КАМАЗ", "category_id": "cat-suspension", "brand_id": "brand-kamaz", "price": 12500, "old_price": 14800, "stock_quantity": 10, "applicability": "КАМАЗ-65115, КАМАЗ-65116"},
    {"article": "5440-2912012", "name": "Амортизатор задний МАЗ", "category_id": "cat-suspension", "brand_id": "brand-maz", "price": 5600, "stock_quantity": 30, "applicability": "МАЗ-5440, МАЗ-5550, МАЗ-6303"},
    {"article": "1075856", "name": "Пневморессора Volvo", "category_id": "cat-suspension", "brand_id": "brand-volvo", "price": 16500, "old_price": 19000, "stock_quantity": 9, "applicability": "Volvo FH, Volvo FM"},
    {"article": "81.43220.6061", "name": "Ступица передняя MAN", "category_id": "cat-suspension", "brand_id": "brand-man", "price": 21000, "stock_quantity": 6, "applicability": "MAN TGA, MAN TGS, MAN TGX"},
    {"article": "1782530", "name": "Подушка кабины Scania", "category_id": "cat-suspension", "brand_id": "brand-scania", "price": 7800, "stock_quantity": 18, "applicability": "Scania R-серия, Scania P-серия"},
    
    # Рулевое управление
    {"article": "4310-3400020", "name": "ГУР КАМАЗ (насос)", "category_id": "cat-steering", "brand_id": "brand-kamaz", "price": 14500, "old_price": 17000, "stock_quantity": 8, "applicability": "КАМАЗ-4310, КАМАЗ-65115, КАМАЗ-43118"},
    {"article": "1444728", "name": "Рулевая тяга Scania", "category_id": "cat-steering", "brand_id": "brand-scania", "price": 11200, "stock_quantity": 12, "applicability": "Scania R420, Scania R480, Scania R500"},
    {"article": "81.46711.6736", "name": "Рулевой механизм MAN", "category_id": "cat-steering", "brand_id": "brand-man", "price": 65000, "old_price": 72000, "stock_quantity": 3, "applicability": "MAN TGA, MAN TGS"},
    
    # Электрика
    {"article": "3708-3708010", "name": "Стартер КАМАЗ 24В", "category_id": "cat-electrical", "brand_id": "brand-kamaz", "price": 9800, "old_price": 12000, "stock_quantity": 15, "applicability": "КАМАЗ-740, КАМАЗ-5320, КАМАЗ-65115"},
    {"article": "1516325", "name": "Генератор Scania 28В 100А", "category_id": "cat-electrical", "brand_id": "brand-scania", "price": 24500, "stock_quantity": 7, "applicability": "Scania R-серия, Scania P-серия"},
    {"article": "81.25902.0488", "name": "Блок управления EDC MAN", "category_id": "cat-electrical", "brand_id": "brand-man", "price": 38000, "stock_quantity": 4, "applicability": "MAN TGA, MAN TGS, MAN TGX"},
    {"article": "20466317", "name": "Датчик давления масла Volvo", "category_id": "cat-electrical", "brand_id": "brand-volvo", "price": 3500, "stock_quantity": 35, "applicability": "Volvo FH12, Volvo FH16, Volvo FM"},
    
    # Кабина и кузов
    {"article": "5320-5301012", "name": "Дверь кабины КАМАЗ правая", "category_id": "cat-body", "brand_id": "brand-kamaz", "price": 22000, "old_price": 26000, "stock_quantity": 5, "applicability": "КАМАЗ-5320, КАМАЗ-65115"},
    {"article": "1723519", "name": "Зеркало заднего вида Scania с подогревом", "category_id": "cat-body", "brand_id": "brand-scania", "price": 18500, "stock_quantity": 8, "applicability": "Scania R-серия, Scania G-серия"},
    {"article": "81.63701.6684", "name": "Решётка радиатора MAN TGX", "category_id": "cat-body", "brand_id": "brand-man", "price": 32000, "stock_quantity": 3, "applicability": "MAN TGX"},
    {"article": "1362727", "name": "Бампер передний DAF XF", "category_id": "cat-body", "brand_id": "brand-daf", "price": 28000, "old_price": 33000, "stock_quantity": 4, "applicability": "DAF XF95, DAF XF105"},
    
    # Выхлопная система
    {"article": "740.1203010", "name": "Глушитель КАМАЗ", "category_id": "cat-exhaust", "brand_id": "brand-kamaz", "price": 8500, "stock_quantity": 12, "applicability": "КАМАЗ-5320, КАМАЗ-65115"},
    {"article": "1747245", "name": "Катализатор SCR Scania", "category_id": "cat-exhaust", "brand_id": "brand-scania", "price": 85000, "old_price": 95000, "stock_quantity": 2, "applicability": "Scania R-серия Euro 5/6"},
    {"article": "51.15201.0207", "name": "Турбина выхлопная MAN", "category_id": "cat-exhaust", "brand_id": "brand-man", "price": 52000, "stock_quantity": 3, "applicability": "MAN TGA, MAN TGS"},
    {"article": "7421708632", "name": "Бачок AdBlue Renault 60л", "category_id": "cat-exhaust", "brand_id": "brand-renault", "price": 14000, "stock_quantity": 9, "applicability": "Renault Premium, Renault Magnum"},
    
    # Топливная система
    {"article": "337-1111150", "name": "ТНВД КАМАЗ BOSCH", "category_id": "cat-fuel", "brand_id": "brand-kamaz", "price": 55000, "old_price": 62000, "stock_quantity": 4, "applicability": "КАМАЗ-740, КАМАЗ-65115"},
    {"article": "20440388", "name": "Форсунка Volvo D12 (комплект 6шт)", "category_id": "cat-fuel", "brand_id": "brand-volvo", "price": 78000, "stock_quantity": 5, "applicability": "Volvo FH12, Volvo FM12"},
    {"article": "51.10100.6125", "name": "Топливный насос подкачки MAN", "category_id": "cat-fuel", "brand_id": "brand-man", "price": 6800, "stock_quantity": 20, "applicability": "MAN TGA, MAN TGS, MAN TGX"},
    {"article": "1529522", "name": "Топливный фильтр-сепаратор Scania", "category_id": "cat-fuel", "brand_id": "brand-scania", "price": 4500, "stock_quantity": 40, "applicability": "Scania R-серия, Scania P-серия, Scania G-серия"},
    
    # Система охлаждения
    {"article": "5320-1301010", "name": "Радиатор охлаждения КАМАЗ", "category_id": "cat-cooling", "brand_id": "brand-kamaz", "price": 19500, "old_price": 23000, "stock_quantity": 7, "applicability": "КАМАЗ-5320, КАМАЗ-65115"},
    {"article": "1776026", "name": "Термостат Scania", "category_id": "cat-cooling", "brand_id": "brand-scania", "price": 5200, "stock_quantity": 22, "applicability": "Scania R-серия, Scania P-серия"},
    {"article": "81.06630.0164", "name": "Вентилятор охлаждения MAN с вискомуфтой", "category_id": "cat-cooling", "brand_id": "brand-man", "price": 45000, "stock_quantity": 3, "applicability": "MAN TGA, MAN TGS"},
    {"article": "8149941", "name": "Расширительный бачок Volvo", "category_id": "cat-cooling", "brand_id": "brand-volvo", "price": 6800, "old_price": 8000, "stock_quantity": 15, "applicability": "Volvo FH, Volvo FM, Volvo FMX"},
    
    # Фильтры и масла
    {"article": "740.1012010", "name": "Фильтр масляный КАМАЗ", "category_id": "cat-filters", "brand_id": "brand-kamaz", "price": 450, "stock_quantity": 100, "applicability": "КАМАЗ-740, КАМАЗ-5320, КАМАЗ-65115, КАМАЗ-6520"},
    {"article": "1421021", "name": "Фильтр воздушный Scania", "category_id": "cat-filters", "brand_id": "brand-scania", "price": 3200, "stock_quantity": 45, "applicability": "Scania R-серия, Scania P-серия, Scania G-серия"},
    {"article": "81.08405.0030", "name": "Фильтр салонный MAN TGX", "category_id": "cat-filters", "brand_id": "brand-man", "price": 2100, "stock_quantity": 30, "applicability": "MAN TGX, MAN TGS"},
    {"article": "21380475", "name": "Фильтр топливный Volvo", "category_id": "cat-filters", "brand_id": "brand-volvo", "price": 2800, "stock_quantity": 55, "applicability": "Volvo FH, Volvo FM, Volvo FMX"},
    {"article": "1433649", "name": "Фильтр масляный DAF", "category_id": "cat-filters", "brand_id": "brand-daf", "price": 1500, "stock_quantity": 60, "applicability": "DAF XF105, DAF CF"},
    
    # Оптика
    {"article": "5320-3711010", "name": "Фара КАМАЗ передняя LED", "category_id": "cat-lighting", "brand_id": "brand-kamaz", "price": 7500, "old_price": 9000, "stock_quantity": 20, "applicability": "КАМАЗ-5320, КАМАЗ-65115, КАМАЗ-6520"},
    {"article": "1730958", "name": "Фара головная Scania R-серия", "category_id": "cat-lighting", "brand_id": "brand-scania", "price": 35000, "stock_quantity": 5, "applicability": "Scania R-серия 2009+"},
    {"article": "81.25101.6451", "name": "Фонарь задний MAN", "category_id": "cat-lighting", "brand_id": "brand-man", "price": 8900, "stock_quantity": 14, "applicability": "MAN TGA, MAN TGS, MAN TGX"},
    {"article": "1684865", "name": "Противотуманная фара DAF", "category_id": "cat-lighting", "brand_id": "brand-daf", "price": 5200, "stock_quantity": 18, "applicability": "DAF XF95, DAF XF105, DAF CF"},
]
