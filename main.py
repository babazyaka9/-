import flet as ft
import json
import os
import traceback

# Цей код спеціально написаний так, щоб показати помилку на екрані,
# якщо щось піде не так, замість білого екрану.

def main(page: ft.Page):
    page.title = "Анатомія Тест"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.ADAPTIVE

    # --- ПАСТКА ДЛЯ ПОМИЛОК ---
    try:
        # 1. Визначаємо правильний шлях до файлів на телефоні
        basedir = os.path.dirname(__file__)
        questions_path = os.path.join(basedir, "questions.json")
        progress_path = os.path.join(basedir, "progress.json")

        # 2. Завантажуємо дані
        questions = []
        if os.path.exists(questions_path):
            with open(questions_path, "r", encoding="utf-8") as f:
                questions = json.load(f)
        
        # Якщо питань немає - показуємо помилку
        if not questions:
            page.add(ft.Text(f"Помилка: Файл питань не знайдено!\nШукав тут: {questions_path}", color="red", size=20))
            page.update()
            return

        # 3. Завантажуємо прогрес
        user_progress = {"wrong_indices": [], "chunk_results": {}}
        if os.path.exists(progress_path):
            try:
                with open(progress_path, "r", encoding="utf-8") as f:
                    user_progress = json.load(f)
            except:
                pass

        def save_progress():
            try:
                with open(progress_path, "w", encoding="utf-8") as f:
                    json.dump(user_progress, f)
            except:
                pass # Якщо не вдалося зберегти, не ламаємо програму

        # --- ЛОГІКА ІНТЕРФЕЙСУ ---
        
        # Функція запуску тесту (оголошена раніше, щоб бачити змінні)
        def start_quiz(mode, start_idx=0, end_idx=0, key=None):
            page.clean()
            
            # Вибір питань
            if mode == "chunk":
                quiz_data = questions[start_idx:end_idx]
            else:
                # Режим роботи над помилками
                wrong_ids = user_progress["wrong_indices"]
                quiz_data = [q for q in questions if q['id'] in wrong_ids]
            
            if not quiz_data:
                page.add(ft.Text("Немає питань для відображення!", size=20))
                page.add(ft.ElevatedButton("На головну", on_click=lambda _: show_menu()))
                page.update()
                return

            # Стан тесту
            state = {"idx": 0, "score": 0, "correct_ids": [], "new_wrongs": []}
            
            # Елементи UI
            txt_progress = ft.Text(value="", color="grey")
            txt_q = ft.Text(value="", size=18, weight="bold")
            col_opts = ft.Column(spacing=10)
            btn_next = ft.ElevatedButton("Далі", visible=False)

            def finish():
                # Оновлення помилок
                current_wrongs = set(user_progress["wrong_indices"])
                for w in state["new_wrongs"]: current_wrongs.add(w)
                for c in state["correct_ids"]: 
                    if c in current_wrongs: current_wrongs.remove(c)
                user_progress["wrong_indices"] = list(current_wrongs)

                # Оновлення статистики
                if mode == "chunk":
                    percent = (state["score"] / len(quiz_data)) * 100
                    user_progress["chunk_results"][key] = {
                        "score": state["score"], "total": len(quiz_data), "percent": percent
                    }
                save_progress()

                # Екран результату
                page.clean()
                pct = (state["score"] / len(quiz_data)) * 100
                color = "green" if pct >= 60 else "red"
                icon = "check_circle" if pct >= 60 else "cancel"
                
                page.add(ft.Column([
                    ft.Icon(icon, size=100, color=color),
                    ft.Text(f"{int(pct)}%", size=40, color=color, weight="bold"),
                    ft.ElevatedButton("В меню", on_click=lambda _: show_menu())
                ], alignment="center", horizontal_alignment="center"))
                page.update()

            def check(e, i, correct_i, q_id):
                for c in col_opts.controls: c.disabled = True
                
                is_right = (i == correct_i)
                e.control.bgcolor = "green" if is_right else "red"
                e.control.content.color = "white"
                
                if not is_right:
                    col_opts.controls[correct_i].bgcolor = "green"
                    col_opts.controls[correct_i].content.color = "white"
                
                if is_right: 
                    state["score"] += 1
                    state["correct_ids"].append(q_id)
                else: 
                    state["new_wrongs"].append(q_id)
                
                btn_next.visible = True
                page.update()

            def next_q(e):
                state["idx"] += 1
                if state["idx"] >= len(quiz_data): finish()
                else: load_ui()

            btn_next.on_click = next_q

            def load_ui():
                q = quiz_data[state["idx"]]
                txt_progress.value = f"Питання {state['idx'] + 1} з {len(quiz_data)}"
                txt_q.value = q["q"]
                col_opts.controls.clear()
                btn_next.visible = False
                
                for i, opt in enumerate(q["opts"]):
                    btn = ft.Container(
                        content=ft.Text(opt, color="black"),
                        padding=15, border=ft.border.all(1, "grey"), border_radius=8,
                        on_click=lambda e, idx=i: check(e, idx, q["c"], q["id"]),
                        bgcolor="white", ink=True
                    )
                    col_opts.controls.append(btn)
                page.update()

            # Збірка екрану тесту
            back_btn = ft.Container(
                content=ft.Icon("arrow_back"), 
                padding=10, 
                on_click=lambda _: show_menu()
            )
            page.add(ft.Row([back_btn, txt_progress]), txt_q, col_opts, ft.Container(height=20), btn_next)
            load_ui()

        # Функція головного меню
        def show_menu():
            page.clean()
            
            # Кнопка скидання
            def reset(e):
                user_progress["wrong_indices"] = []
                user_progress["chunk_results"] = {}
                save_progress()
                show_menu()

            btn_reset = ft.Container(
                content=ft.Icon("autorenew", color="red"),
                padding=10, on_click=reset
            )
            
            page.add(ft.Row([
                ft.Text("Анатомія", size=30, weight="bold"), 
                btn_reset
            ], alignment="spaceBetween"))

            # Кнопка помилок
            wrongs = len(user_progress.get("wrong_indices", []))
            if wrongs > 0:
                page.add(ft.Container(
                    content=ft.Text(f"Робота над помилками ({wrongs})", color="white"),
                    bgcolor="purple", padding=15, border_radius=10,
                    on_click=lambda _: start_quiz("review")
                ))

            # Список тестів
            CHUNK = 40
            col_tests = ft.Column(spacing=10)
            
            for i in range(0, len(questions), CHUNK):
                end = min(i + CHUNK, len(questions))
                key = f"{i}-{end}"
                res = user_progress["chunk_results"].get(key)
                
                num = (i // CHUNK) + 1
                icon = "circle_outlined"
                color = "grey100"
                info = "Не пройдено"
                
                if res:
                    icon = "check_circle" if res['percent'] >= 60 else "cancel"
                    color = "green100" if res['percent'] >= 60 else "red100"
                    info = f"{res['score']}/{res['total']} ({int(res['percent']) }%)"

                card = ft.Container(
                    content=ft.Row([
                        ft.Icon(icon),
                        ft.Column([ft.Text(f"Тест {num}", weight="bold"), ft.Text(info, size=12)])
                    ]),
                    bgcolor=color, padding=15, border_radius=10,
                    on_click=lambda _, s=i, e=end, k=key: start_quiz("chunk", s, e, k)
                )
                col_tests.controls.append(card)
            
            page.add(col_tests)
            page.update()

        # Запускаємо меню
        show_menu()

    except Exception as e:
        # ЯКЩО СТАЛАСЯ ПОМИЛКА - ВОНА БУДЕ ТУТ
        page.clean()
        page.add(ft.Text("Упс! Сталася помилка:", color="red", size=30, weight="bold"))
        page.add(ft.Text(f"{e}", color="red", size=20))
        page.add(ft.Text(traceback.format_exc(), color="red", size=12))
        page.update()

ft.app(main)
