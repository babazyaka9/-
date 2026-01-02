import json
import re
import pdfplumber

def is_bold(font_name):
    if not font_name: return False
    name = font_name.lower()
    return "bold" in name or "bld" in name or "black" in name or "heavy" in name

def clean_text(text):
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_pdf(filename):
    questions = []
    
    print(f"Обробляю файл: {filename}")
    
    with pdfplumber.open(filename) as pdf:
        # ОБРОБЛЯЄМО ВСІ СТОРІНКИ
        raw_lines = []

        for i, page in enumerate(pdf.pages):
            width = page.width
            height = page.height
            
            # Мінімальна обрізка (10px), щоб прибрати технічні поля, але читати весь текст
            try:
                cropped = page.crop((0, 10, width, height - 10))
            except:
                # Якщо кроп не вдався, беремо сторінку як є
                cropped = page

            words = cropped.extract_words(keep_blank_chars=True, extra_attrs=["fontname"])
            if not words: continue
            
            # Сортуємо слова: зверху вниз, зліва направо
            words.sort(key=lambda w: (int(w['top']), w['x0']))
            
            line_buffer = []
            last_top = words[0]['top']
            bold_chars = 0
            total_chars = 0
            
            for w in words:
                # Якщо новий рядок (відступ > 5 пікселів)
                if abs(w['top'] - last_top) > 5:
                    text_str = " ".join([wb['text'] for wb in line_buffer])
                    is_line_bold = (bold_chars / total_chars) > 0.5 if total_chars > 0 else False
                    
                    if text_str.strip():
                        raw_lines.append({"text": text_str, "is_bold": is_line_bold})
                    
                    line_buffer = []
                    bold_chars = 0
                    total_chars = 0
                    last_top = w['top']
                
                line_buffer.append(w)
                total_chars += len(w['text'])
                if is_bold(w['fontname']):
                    bold_chars += len(w['text'])
            
            # Останній рядок на сторінці
            if line_buffer:
                text_str = " ".join([wb['text'] for wb in line_buffer])
                is_line_bold = (bold_chars / total_chars) > 0.5 if total_chars > 0 else False
                if text_str.strip():
                    raw_lines.append({"text": text_str, "is_bold": is_line_bold})

    # 2. АЛГОРИТМ РОЗБОРУ (STATE MACHINE)
    current_q = None
    
    # Регулярка для варіантів: А., В., С., D., E. (Латиниця + Кирилиця)
    # ^\s* - можливі пробіли на початку
    # [A-EА-Еa-e] - літера
    # [\.\)] - крапка або дужка
    opt_pattern = re.compile(r'^\s*([A-EА-Еa-e])[\.\)]\s*(.*)', re.IGNORECASE)
    
    # Регулярка для питань: 1., 24.
    q_pattern = re.compile(r'^\s*(\d+)\.\s*(.*)')

    for line_data in raw_lines:
        text = clean_text(line_data["text"])
        is_bold_flag = line_data["is_bold"]
        
        if not text: continue

        # 1. ПЕРЕВІРКА НА ВАРІАНТ ВІДПОВІДІ (А., В., С...)
        match_opt = opt_pattern.match(text)
        
        # Перевіряємо, чи це варіант, ТІЛЬКИ якщо ми вже маємо відкрите питання (current_q)
        if match_opt and current_q:
            opt_text = match_opt.group(2).strip()
            # Якщо текст варіанту пустий (наприклад рядок "A."), беремо все крім літери
            if not opt_text: opt_text = text[2:].strip()
            
            current_q["opts"].append(opt_text)
            
            # Якщо жирний шрифт - це правильна відповідь
            if is_bold_flag:
                current_q["c"] = len(current_q["opts"]) - 1
            continue

        # 2. ПЕРЕВІРКА НА НОВЕ ПИТАННЯ (1., 2...)
        match_q = q_pattern.match(text)
        
        if match_q:
            # Зберігаємо попереднє питання
            if current_q:
                # Валідація: якщо є варіанти, додаємо в базу
                if current_q['opts']:
                    # Якщо правильну відповідь не знайшли по жирному, ставимо першу (0)
                    if current_q['c'] == -1: current_q['c'] = 0
                    questions.append(current_q)
            
            # Створюємо нове
            current_q = {
                "id": int(match_q.group(1)),
                "q": match_q.group(2).strip(),
                "opts": [],
                "c": -1
            }
            continue
        
        # 3. ПРОДОВЖЕННЯ ТЕКСТУ (якщо це не варіант і не номер)
        if current_q:
            # Якщо варіанти вже почалися -> це довгий варіант відповіді
            if current_q["opts"]:
                current_q["opts"][-1] += " " + text
            else:
                # Якщо варіантів ще немає -> це довге питання
                current_q["q"] += " " + text

    # Додаємо останнє питання після циклу
    if current_q and current_q['opts']:
        if current_q['c'] == -1: current_q['c'] = 0
        questions.append(current_q)

    return questions

if __name__ == "__main__":
    try:
        # Назва файлу має бути base.pdf
        data = parse_pdf('base.pdf')
        print(f"Знайдено {len(data)} питань.")
        
        with open('questions.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Помилка: {e}")
        # Створюємо пустий файл, щоб збірка не впала
        with open('questions.json', 'w', encoding='utf-8') as f:
            json.dump([], f)
