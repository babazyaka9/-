import flet as ft
import json
import os


# --- ЗАВАНТАЖЕННЯ ДАНИХ ---
def load_data():
    if os.path.exists("questions.json"):
        with open("questions.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# --- ЗБЕРЕЖЕННЯ ПРОГРЕСУ ---
def load_progress():
    if os.path.exists("progress.json"):
        try:
            with open("progress.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"wrong_indices": [], "chunk_results": {}}


def save_progress(progress):
    with open("progress.json", "w", encoding="utf-8") as f:
        json.dump(progress, f)


QUESTIONS = load_data()
CHUNK_SIZE = 40


def main(page: ft.Page):
    page.title = "Анатомія Тест"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.ADAPTIVE

    # Змінні стану
    user_progress = load_progress()

    # --- ЕКРАНИ ---

    def show_menu(e=None):
        page.clean()

        # Заголовок
        header = ft.Row([
            ft.Text("Анатомія", size=30, weight="bold"),
            # IconButton використовує параметр icon=, тут все ок
            ft.IconButton(icon="autorenew", icon_color="red", on_click=reset_app_data, tooltip="Скинути прогрес")
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        page.add(header)

        # Кнопка помилок
        wrongs_count = len(user_progress.get("wrong_indices", []))
        if wrongs_count > 0:
            page.add(
                ft.Container(
                    content=ft.Row([
                        # ВИПРАВЛЕНО: прибрано name=
                        ft.Icon("warning", color="white"),
                        ft.Text(f"Робота над помилками ({wrongs_count})", color="white", weight="bold")
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    bgcolor="purple", padding=15, border_radius=10,
                    on_click=lambda _: start_quiz("review"),
                    margin=ft.margin.only(bottom=20)
                )
            )

        # Список тестів
        total_q = len(QUESTIONS)
        tests_column = ft.Column(spacing=10)

        for i in range(0, total_q, CHUNK_SIZE):
            end = min(i + CHUNK_SIZE, total_q)
            key = f"{i}-{end}"
            res = user_progress["chunk_results"].get(key)

            chunk_num = (i // CHUNK_SIZE) + 1

            if res:
                percent = res['percent']
                icon_name = "check_circle" if percent >= 60 else "cancel"
                color = "green100" if percent >= 60 else "red100"
                text_info = f"{res['score']}/{res['total']} ({int(percent)}%)"
            else:
                icon_name = "circle_outlined"
                color = "grey100"
                text_info = "Не пройдено"

            card = ft.Container(
                content=ft.Row([
                    # ВИПРАВЛЕНО: прибрано name=
                    ft.Icon(icon_name),
                    ft.Column([
                        ft.Text(f"Тест {chunk_num}", weight="bold"),
                        ft.Text(text_info, size=12, color="grey")
                    ])
                ]),
                bgcolor=color, padding=15, border_radius=10,
                on_click=lambda _, s=i, e=end, k=key: start_quiz("chunk", s, e, k)
            )
            tests_column.controls.append(card)

        page.add(tests_column)
        page.update()

    def start_quiz(mode, start=0, end=0, key=None):
        page.clean()

        if mode == "chunk":
            quiz_questions = QUESTIONS[start:end]
        else:
            wrong_ids = user_progress["wrong_indices"]
            quiz_questions = [q for q in QUESTIONS if q['id'] in wrong_ids]

        if not quiz_questions:
            page.add(ft.Text("Помилок немає! 🎉", size=20))
            page.add(ft.ElevatedButton("Назад в меню", on_click=show_menu))
            page.update()
            return

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

        def next_question(e):
            state["idx"] += 1
            if state["idx"] >= len(quiz_questions):
                finish_quiz(state, key, mode, len(quiz_questions))
            else:
                load_q()

        btn_next.on_click = next_question

        def check_answer(e, selected_idx, correct_idx, q_id):
            for ctrl in opts_column.controls:
                ctrl.disabled = True

            is_correct = (selected_idx == correct_idx)

            e.control.bgcolor = "green" if is_correct else "red"
            e.control.content.color = "white"
            if not is_correct:
                opts_column.controls[correct_idx].bgcolor = "green"
                opts_column.controls[correct_idx].content.color = "white"

            if is_correct:
                state["score"] += 1
                state["correct_ids"].append(q_id)
            else:
                state["new_wrongs"].append(q_id)

            btn_next.visible = True
            page.update()

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

        page.add(
            ft.Row([
                ft.IconButton(icon="arrow_back", on_click=show_menu),
                txt_progress
            ]),
            txt_question,
            opts_column,
            ft.Container(height=20),
            btn_next
        )
        load_q()

    def finish_quiz(state, key, mode, total_q):
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

        save_progress(user_progress)

        page.clean()
        percent = (state["score"] / total_q) * 100
        color = "green" if percent >= 60 else "red"
        icon_name = "check_circle" if percent >= 60 else "cancel"

        page.add(
            ft.Column([
                # ВИПРАВЛЕНО: прибрано name=
                ft.Icon(icon_name, size=100, color=color),
                ft.Text(f"{int(percent)}%", size=40, color=color, weight="bold"),
                ft.Text(f"Правильно: {state['score']} з {total_q}", size=20),
                ft.Container(height=50),
                ft.ElevatedButton("В меню", on_click=show_menu, width=200),
                ft.ElevatedButton("Робота над помилками", on_click=lambda _: start_quiz("review"), width=200,
                                  bgcolor="purple", color="white")
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
        page.update()

    def reset_app_data(e):
        user_progress["wrong_indices"] = []
        user_progress["chunk_results"] = {}
        save_progress(user_progress)
        show_menu()

    show_menu()


ft.run(main)