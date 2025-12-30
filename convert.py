import json
import re
import pdfplumber

def is_bold(font_name):
    if not font_name: return False
    name = font_name.lower()
    return "bold" in name or "bld" in name or "black" in name or "heavy" in name

def parse_pdf(filename):
    questions = []
    current_q = None
    
    with pdfplumber.open(filename) as pdf:
        full_text_lines = []
        
        for page in pdf.pages:
            width = page.width
            height = page.height
            
            # 1. ОБРІЗКА ПОЛІВ (ігноруємо верхні 50px і нижні 50px)
            # Це видалить більшість колонтитулів і номерів сторінок
            cropped = page.crop((0, 50, width, height - 50))
            if not cropped: continue # Якщо сторінка пуста після обрізки

            words = cropped.extract_words(keep_blank_chars=True, extra_attrs=["fontname"])
            if not words: continue
            
            # Сортуємо слова
            words.sort(key=lambda w: (int(w['top']), w['x0']))
            
            line_buffer = []
            last_top = words[0]['top']
            bold_chars = 0
            total_chars = 0
            
            for w in words:
                if abs(w['top'] - last_top) > 5:
                    # Зберігаємо рядок
                    text = " ".join([wb['text'] for wb in line_buffer])
                    is_line_bold = (bold_chars / total_chars) > 0.5 if total_chars > 0 else False
                    full_text_lines.append({"text": text, "is_bold": is_line_bold})
                    
                    line_buffer = []
                    bold_chars = 0
                    total_chars = 0
                    last_top = w['top']
                
                line_buffer.append(w)
                total_chars += len(w['text'])
                if is_bold(w['fontname']):
                    bold_chars += len(w['text'])
            
            if line_buffer:
                text = " ".join([wb['text'] for wb in line_buffer])
                is_line_bold = (bold_chars / total_chars) > 0.5 if total_chars > 0 else False
                full_text_lines.append({"text": text, "is_bold": is_line_bold})

    # 2. ОБРОБКА РЯДКІВ
    for line_obj in full_text_lines:
        line = line_obj["text"].strip()
        is_bold_flag = line_obj["is_bold"]
        
        # ДОДАТКОВА ЧИСТКА СМІТТЯ
        if not line: continue
        if line.isdigit(): continue # Якщо рядок це просто цифра (номер сторінки)
        if "кафедра анатомії" in line.lower(): continue
        if "сторінка" in line.lower(): continue
        
        # Пошук нового питання (1. Текст...)
        match_q = re.match(r'^(\d+)\.\s+(.*)', line)
        
        if match_q:
            if current_q:
                # Якщо правильна відповідь не знайдена, ставимо першу
                if current_q['c'] == -1 and current_q['opts']:
                    current_q['c'] = 0
                questions.append(current_q)
            
            current_q = {
                "id": int(match_q.group(1)),
                "q": match_q.group(2),
                "opts": [],
                "c": -1
            }
        elif current_q:
            # Це варіант відповіді
            # Прибираємо маркери списку
            clean_opt = re.sub(r'^[a-zA-Zа-яА-Я][\)\.]\s*', '', line)
            clean_opt = re.sub(r'^[\+\-]\s*', '', clean_opt)
            
            # Якщо це продовження попереднього варіанту (не починається з великої літери)
            # Це евристика, можна вимкнути, якщо будуть помилки
            # if current_q['opts'] and not line[0].isupper() and not is_bold_flag:
            #    current_q['opts'][-1] += " " + clean_opt
            # else:
            current_q["opts"].append(clean_opt)
            
            if is_bold_flag:
                current_q["c"] = len(current_q["opts"]) - 1

    if current_q:
        if current_q['c'] == -1 and current_q['opts']:
            current_q['c'] = 0
        questions.append(current_q)

    return questions

if __name__ == "__main__":
    try:
        # Вказуємо ім'я вашого PDF файлу
        # ВАЖЛИВО: Переконайтеся, що файл на GitHub називається саме base.pdf
        # Або змініть назву тут на вашу (база анат_unlocked.pdf)
        data = parse_pdf('base.pdf') 
        print(f"Успішно знайдено {len(data)} питань.")
        
        with open('questions.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Помилка: {e}")
        with open('questions.json', 'w', encoding='utf-8') as f:
            json.dump([], f)
