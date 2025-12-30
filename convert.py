import json
import re
import pdfplumber

def is_bold(font_name):
    if not font_name: return False
    name = font_name.lower()
    return "bold" in name or "bld" in name or "black" in name or "heavy" in name

def clean_text(text):
    # Видаляє зайві пробіли
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_pdf(filename):
    questions = []
    
    print(f"Обробляю файл: {filename}")
    
    with pdfplumber.open(filename) as pdf:
        total_pages = len(pdf.pages)
        # 1. ІГНОРУВАННЯ СТОРІНОК (перші 3 і останні 3)
        start_page = 3
        end_page = total_pages - 3
        
        print(f"Всього сторінок: {total_pages}. Обробляю з {start_page+1} по {end_page}.")

        raw_lines = []

        for i in range(start_page, end_page):
            page = pdf.pages[i]
            width = page.width
            height = page.height
            
            # Обрізка колонтитулів (про всяк випадок залишаємо, щоб прибрати сміття зверху/знизу)
            try:
                cropped = page.crop((0, 60, width, height - 60))
            except:
                continue 

            words = cropped.extract_words(keep_blank_chars=True, extra_attrs=["fontname"])
            if not words: continue
            
            words.sort(key=lambda w: (int(w['top']), w['x0']))
            
            line_buffer = []
            last_top = words[0]['top']
            bold_chars = 0
            total_chars = 0
            
            for w in words:
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
            
            if line_buffer:
                text_str = " ".join([wb['text'] for wb in line_buffer])
                is_line_bold = (bold_chars / total_chars) > 0.5 if total_chars > 0 else False
                if text_str.strip():
                    raw_lines.append({"text": text_str, "is_bold": is_line_bold})

    # 2. ОБРОБКА ЗА ВАШИМ АЛГОРИТМОМ
    current_q = None
    # Регулярка для варіантів: А., В., С., D., E. (латиниця та кирилиця)
    opt_pattern = re.compile(r'^([A-EА-Е])\.\s*(.*)', re.IGNORECASE)
    # Регулярка для питань: 1., 24.
    q_pattern = re.compile(r'^(\d+)\.\s*(.*)')

    for line_data in raw_lines:
        text = clean_text(line_data["text"])
        is_bold_flag = line_data["is_bold"]
        
        if not text: continue

        # Перевірка: чи це варіант відповіді (A., B., C...)?
        match_opt = opt_pattern.match(text)
        
        if match_opt:
            if current_q:
                # Це варіант. Очищаємо від літери "A." і додаємо в список.
                opt_text = match_opt.group(2).strip()
                # Якщо текст варіанту пустий (буває просто "A."), беремо весь рядок без перших 2 символів
                if not opt_text: opt_text = text[2:].strip()
                
                current_q["opts"].append(opt_text)
                
                # Якщо жирний - це правильна відповідь
                if is_bold_flag:
                    current_q["c"] = len(current_q["opts"]) - 1
            continue

        # Перевірка: чи це нове питання (1., 24.)?
        match_q = q_pattern.match(text)
        
        if match_q:
            # Зберігаємо попереднє питання
            if current_q:
                # Якщо варіанти є, а правильного не знайшли -> ставимо перший
                if current_q['opts']:
                    if current_q['c'] == -1: current_q['c'] = 0
                    questions.append(current_q)
            
            # Створюємо нове
            current_q = {
                "id": int(match_q.group(1)),
                "q": match_q.group(2).strip(),
                "opts": [],
                "c": -1
            }
        
        elif current_q:
            # Це не варіант і не нове питання.
            # Якщо ми ще не почали збирати варіанти -> це продовження тексту питання
            if not current_q["opts"]:
                current_q["q"] += " " + text
            else:
                # Якщо варіанти вже почалися, але цей рядок не має літери "A."
                # Це продовження останнього варіанту відповіді
                current_q["opts"][-1] += " " + text

    # Додаємо останнє питання
    if current_q and current_q['opts']:
        if current_q['c'] == -1: current_q['c'] = 0
        questions.append(current_q)

    return questions

if __name__ == "__main__":
    try:
        data = parse_pdf('base.pdf')
        print(f"Знайдено {len(data)} питань.")
        with open('questions.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Помилка: {e}")
        with open('questions.json', 'w', encoding='utf-8') as f:
            json.dump([], f)
