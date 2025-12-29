import flet as ft
import json
import os

# --- ГЛОБАЛЬНІ ЗМІННІ ---
QUESTIONS = []
CHUNK_SIZE = 40
user_progress = {"wrong_indices": [], "chunk_results": {}}

# --- ЗАВАНТАЖЕННЯ ДАНИХ ---
def load_data():
    global QUESTIONS
    if os.path.exists("questions.json"):
        with open("questions.json", "r", encoding="utf-8") as f:
            QUESTIONS = json.load(f)
    else:
        QUESTIONS = []

def load_progress():
    global user_progress
    if os.path.exists("progress.json"):
        try:
            with open("progress.json", "r", encoding="utf-8") as f:
                user_progress = json.load(f)
        except:
            user_progress = {"wrong_indices": [], "chunk_results": {}}

def save_progress():
    with open("progress.json", "w", encoding="utf-8") as f:
        json.dump(user_progress, f)

# --- ЕКРАНИ ---
def show_menu(page):
    page.clean()
    
    # Кнопка скидання
    reset_btn = ft.Container(
        content=ft.Icon(ft.icons.AUTORENEW, color="red"),
        on_click=lambda e: reset_app_data(page),
        padding=10,
        border_radius=50,
        ink=True
    )

    header = ft.Row([
        ft.Text("Анатомія", size=30, weight="bold"),
        reset_btn
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    
    page.add(header)
    
    # Кнопка помилок
    wrongs_count = len(user_progress.get("wrong_indices", []))
    if wrongs_count > 0:
        btn_errors = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.WARNING, color="white"),
                ft.Text(f"Робота над помилками ({wrongs_count})", color="white", weight="bold")
            ], alignment=ft.MainAxisAlignment.CENTER),
            bgcolor="purple", padding=15, border_radius=10,
            on_click=lambda _: start_quiz(page, "review"),
            margin=ft.margin.only(bottom=20)
        )
        page.add(btn_errors)

    # Список тестів
    tests_column = ft.Column(spacing=10)
    total_q = len(QUESTIONS)
    
    for i in range(0, total_q, CHUNK_SIZE):
        end_val = min(i + CHUNK_SIZE, total_q)
        key_val = f"{i}-{end_val}"
        res = user_progress["chunk_results"].get(key_val)
        
        chunk_num = (i // CHUNK_SIZE) + 1
        
        if res:
            percent = res['percent']
            icon_name = ft.icons.CHECK_CIRCLE if percent >= 60 else ft.icons.CANCEL
            color = "green100" if percent >= 60 else "red100"
            text_info = f"{res['score']}/{res['total']} ({int(percent)}%)"
        else:
            icon_name = ft.icons.CIRCLE_OUTLINED
            color = "grey100"
            text_info = "Не пройдено"

        card = ft.Container(
            content=ft.Row([
                ft.Icon(icon_name),
                ft.Column([
                    ft.Text(f"Тест {chunk_num}", weight="bold"),
                    ft.Text(text_info, size=12, color="grey")
                ])
            ]),
            bgcolor=color, padding=15, border_radius=10,
            on_click=lambda _, s=i, e=end_val, k=key_val: start_quiz(page, "chunk", s, e, k)
        )
        tests_column.controls.append(card)
        
    page.add(tests_column)
    page.update()

def start_quiz(page, mode, start=0, end=0, key=None):
    page.clean()
    
    if mode == "chunk":
        quiz_questions = QUESTIONS[start:end]
    else: 
        wrong_ids = user_progress["wrong_indices"]
        quiz_questions = [q for q in QUESTIONS if q['id'] in wrong_ids]
    
    if not quiz_questions:
        page.add(ft.Text("Помилок немає! 🎉", size=20))
        page.add(ft.ElevatedButton("Назад в меню", on_click=lambda _: show_menu(page)))
        page.update()
        return

    # Стан вікторини зберігаємо в об'єкті (словнику)
    state = {
        "idx": 0,
        "score": 0,
        "correct_ids": [],
        "new_wrongs": []
    }

    txt_progress = ft.Text(size=14, color="grey")
    txt_question = ft.Text(size=18, weight="bold")
    opts_column = ft.Column(spacing=10)
    btn_next = ft.ElevatedButton("Далі", visible=False, width=page.width)

    # Функція перевірки відповіді
    def check_answer(e, selected_idx, correct_idx, q_id):
        for ctrl in opts_column.controls:
            ctrl.disabled = True
        
        is_correct = (selected_idx == correct_idx)
        
        e.control.bgcolor = "green" if is_correct else "red"
        e.control.content.color = "white"
        
        if not is_correct:
            # Підсвітити правильну відповідь
            opts_column.controls[correct_idx].bgcolor = "green"
            opts_column.controls[correct_idx].content.color = "white"
        
        if is_correct:
            state["score"] += 1
            state["correct_ids"].append(q_id)
        else:
            state["new_wrongs"].append(q_id)
        
        btn_next.visible = True
        page.update()

    # Завантаження питання
    def load_q():
        q = quiz_questions[state["idx"]]
        txt_progress.value = f"Питання {state['idx'] + 1} з {len(quiz_questions)}"
        txt_question.value = q["q"]
        
        opts_column.controls.clear()
        btn_next.visible = False
        
        for i, opt_text in enumerate(q["opts"]):
            btn = ft.Container(
                content=ft.Text(opt_text, color="black"),
                padding=15,
                border=ft.border.all(1, "grey"),
                border_radius=8,
                on_click=lambda e, idx=i: check_answer(e, idx, q["c"], q["id"]),
                ink=True,
                bgcolor="white"
            )
            opts_column.controls.append(btn)
        
        page.update()

    # Перехід до наступного
    def next_question(e):
        state["idx"] += 1
        if state["idx"] >= len(quiz_questions):
            finish_quiz(page, state, key, mode, len(quiz_questions))
        else:
            load_q()

    btn_next.on_click = next_question

    back_btn = ft.Container(
        content=ft.Icon(ft.icons.ARROW_BACK),
        on_click=lambda _: show_menu(page),
        padding=10
    )

    page.add(
        ft.Row([back_btn, txt_progress]),
        txt_question,
        opts_column,
        ft.Container(height=20),
        btn_next
    )
    load_q()

def finish_quiz(page, state, key, mode, total_q):
    current_wrongs = set(user_progress["wrong_indices"])
    
    for wid in state["new_wrongs"]:
        current_wrongs.add(wid)
    for cid in state["correct_ids"]:
        if cid in current_wrongs:
            current_wrongs.remove(cid)
    
    user_progress["wrong_indices"] = list(current_wrongs)
    
    if mode == "chunk":
        percent = (state["score"] / total_q) * 100
        user_progress["chunk_results"][key] = {
            "score": state["score"],
            "total": total_q,
            "percent": percent
        }
    
    save_progress()
    
    page.clean()
    percent = (state["score"] / total_q) * 100
    color = "green" if percent >= 60 else "red"
    icon_name = ft.icons.CHECK_CIRCLE if percent >= 60 else ft.icons.CANCEL
    
    page.add(
        ft.Column([
            ft.Icon(icon_name, size=100, color=color),
            ft.Text(f"{int(percent)}%", size=40, color=color, weight="bold"),
            ft.Text(f"Правильно: {state['score']} з {total_q}", size=20),
            ft.Container(height=50),
            ft.ElevatedButton("В меню", on_click=lambda _: show_menu(page), width=200),
            ft.ElevatedButton("Робота над помилками", on_click=lambda _: start_quiz(page, "review"), width=200, bgcolor="purple", color="white")
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )
    page.update()

def reset_app_data(page):
    global user_progress
    user_progress["wrong_indices"] = []
    user_progress["chunk_results"] = {}
    save_progress()
    show_menu(page)

# --- GOOGLE ---
def main(page: ft.Page):
    page.title = "Анатомія Тест"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.ADAPTIVE
    
    load_data()
    load_progress()
    show_menu(page)

ft.app(main)
