import json
import re
import pdfplumber

def is_bold(font_name):
    if not font_name: return False
    name = font_name.lower()
    return "bold" in name or "bld" in name or "black" in name or "heavy" in name

def clean_text(text):
    # Прибираємо зайві пробіли
    return re.sub(r'\s+', ' ', text).strip()

def parse_pdf(filename):
    questions = []
    
    # Тимчасові змінні для збору даних
    raw_lines = []
    
    print(f"Відкриваю файл: {filename}")
    
    with pdfplumber.open(filename) as pdf:
        for i, page in enumerate(pdf.pages):
            # 1. ОБРІЗКА (CROP)
            # Відрізаємо 65 пікселів зверху і 65 знизу, щоб викинути колонтитули
            width = page.width
            height = page.height
            
            # Перевірка на пусту сторінку
            if height < 150: continue
            
            try:
                # Область: (x0, top, x1, bottom)
                cropped = page.crop((0, 65, width, height - 65))
            except ValueError:
                continue # Якщо сторінка дивного розміру, пропускаємо

            # Витягуємо слова з інформацією про шрифт
            words = cropped.extract_words(keep_blank_chars=True, extra_attrs=["fontname"])
            
            # Сортуємо слова (зверху вниз, зліва направо)
            words.sort(key=lambda w: (int(w['top']), w['x0']))
            
            if not words: continue

            # Групуємо слова в рядки
            line_buffer = []
            last_top = words[0]['top']
            
            current_line_text = []
            bold_chars = 0
            total_chars = 0

            for w in words:
                # Якщо це новий рядок (відступ по вертикалі > 4 пікселів)
                if abs(w['top'] - last_top) > 4:
                    # Зберігаємо попередній рядок
                    text_str = " ".join([wb['text'] for wb in current_line_text])
                    is_line_bold = (bold_chars / total_chars) > 0.5 if total_chars > 0 else False
                    
                    if text_str.strip():
                        raw_lines.append({"text": text_str, "is_bold": is_line_bold})
                    
                    # Скидаємо буфер
                    current_line_text = []
                    bold_chars = 0
                    total_chars = 0
                    last_top = w['top']
                
                current_line_text.append(w)
                total_chars += len(w['text'])
                if is_bold(w['fontname']):
                    bold_chars += len(w['text'])
            
            # Додаємо останній рядок сторінки
            if current_line_text:
                text_str = " ".join([wb['text'] for wb in current_line_text])
                is_line_bold = (bold_chars / total_chars) > 0.5 if total_chars > 0 else False
                if text_str.strip():
                    raw_lines.append({"text": text_str, "is_bold": is_line_bold})

    print(f"Зчитано {len(raw_lines)} рядків тексту. Починаю обробку...")

    # 2. ОБРОБКА РЯДКІВ (СКЛЕЮВАННЯ ТА РОЗБІР)
    current_q = None
    
    for line_obj in raw_lines:
        line = line_obj["text"].strip()
        is_bold_flag = line_obj["is_bold"]
        
        # Фільтр сміття
        if not line: continue
        if line.isdigit(): continue # Просто цифра
        if "міністерство" in line.lower(): continue
        if "кафедра" in line.lower(): continue
        if "сторінка" in line.lower(): continue
        
        # Перевіряємо, чи це початок нового питання: "1. Текст", "25. Текст"
        # Регулярка: початок рядка, цифри, крапка, пробіл
        match_q = re.match(r'^(\d+)\.\s+(.*)', line)
        
        if match_q:
            # Зберігаємо попереднє питання перед початком нового
            if current_q:
                # Перевірка: чи є правильна відповідь? Якщо ні - ставимо першу.
                if current_q['c'] == -1 and current_q['opts']:
                    current_q['c'] = 0
                questions.append(current_q)
            
            # Створюємо нове питання
            current_q = {
                "id": int(match_q.group(1)),
                "q": clean_text(match_q.group(2)),
                "opts": [],
                "c": -1
            }
        
        elif current_q:
            # Це або продовження тексту питання, або варіант відповіді
            
            # ЕВРИСТИКА: Як відрізнити продовження питання від варіанту?
            # 1. Якщо рядок починається з малої літери -> це точно продовження попереднього
            # 2. Якщо рядок жирний -> це точно варіант відповіді (правильний)
            # 3. Якщо ми вже почали записувати варіанти -> це наступний варіант
            
            starts_lower = line[0].islower()
            has_options_already = len(current_q["opts"]) > 0
            
            if starts_lower and not has_options_already and not is_bold_flag:
                # Приклеюємо до тексту питання
                current_q["q"] += " " + clean_text(line)
            else:
                # Це варіант відповіді
                # Чистимо від маркерів типу "A)", "-", "+"
                clean_opt = re.sub(r'^[a-zA-Zа-яА-Я][\)\.]\s*', '', line)
                clean_opt = re.sub(r'^[\+\-]\s*', '', clean_opt)
                clean_opt = clean_text(clean_opt)
                
                # Якщо варіант починається з малої літери, але ми вже в списку варіантів,
                # то це, скоріше за все, розірваний варіант. Приклеюємо до останнього.
                if starts_lower and has_options_already:
                     current_q["opts"][-1] += " " + clean_opt
                else:
                    current_q["opts"].append(clean_opt)
                    # Якщо жирний - запам'ятовуємо індекс
                    if is_bold_flag:
                        current_q["c"] = len(current_q["opts"]) - 1

    # Додаємо останнє питання
    if current_q:
        if current_q['c'] == -1 and current_q['opts']:
            current_q['c'] = 0
        questions.append(current_q)

    return questions

if __name__ == "__main__":
    try:
        # ВАЖЛИВО: Назва файлу має бути base.pdf на GitHub
        data = parse_pdf('base.pdf')
        print(f"Успішно сформовано {len(data)} питань.")
        
        with open('questions.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Критична помилка: {e}")
        # Створюємо пустий файл, щоб збірка не впала, але ми побачили помилку в логах
        with open('questions.json', 'w', encoding='utf-8') as f:
            json.dump([], f)
