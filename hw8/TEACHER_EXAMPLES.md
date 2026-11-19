# Примеры преподавателя для HW8
## Комментарий преподавателя

> Выполнено. Пожалуйста, ознакомьтесь с репозиторием Git. Там уже есть примеры выполнения домашних заданий №7 (сессия 1) и №8 (сессия 2).

Ссылки из комментария:

- [Примеры FAR-Trans LLM для HW7/HW8](https://github.com/dryjins/RecSys-LLMs/tree/main/project/far-trans-llm)
- [Инструкция Homework 2 / Session 2](https://github.com/dryjins/RecSys-LLMs/blob/main/project/far-trans/instructions/homework2.md)

OpenCode: ознакомься с этими Git-материалами и локальными копиями в `hw8/reference/`. Используй их как примеры и требования; результаты из чужого репозитория не выдавай за наши.

## Git-источники

- [FAR-Trans starter: baselines, протокол и оценка](https://github.com/dryjins/RecSys-LLMs/tree/main/project/far-trans)
  - [README starter](https://github.com/dryjins/RecSys-LLMs/blob/main/project/far-trans/README.md)
  - [Код starter](https://github.com/dryjins/RecSys-LLMs/blob/main/project/far-trans/starter.py)
- [LLM Encoder и Ranker примеры](https://github.com/dryjins/RecSys-LLMs/tree/main/project/far-trans-llm)
  - [README с запуском и ограничениями](https://github.com/dryjins/RecSys-LLMs/blob/main/project/far-trans-llm/README.md)
  - [Как перейти от HW7-вопроса к HW8-эксперименту](https://github.com/dryjins/RecSys-LLMs/blob/main/project/far-trans-llm/HW1_TO_HW2.md)
  - [Демонстрационные результаты HW2](https://github.com/dryjins/RecSys-LLMs/blob/main/project/far-trans-llm/HW2_RESULTS.md)
  - [Encoder implementation](https://github.com/dryjins/RecSys-LLMs/blob/main/project/far-trans-llm/encoder.py)
  - [Ranker implementation](https://github.com/dryjins/RecSys-LLMs/blob/main/project/far-trans-llm/ranker.py)
- [Официальная инструкция Homework 2](https://github.com/dryjins/RecSys-LLMs/blob/main/project/far-trans/instructions/homework2.md)

Локальные копии кода и материалов преподавателя находятся в `hw8/reference/`. Они исключены из Git; эта заметка с Git-ссылками находится в репозитории и должна быть видна OpenCode.

## Что делает пример Encoder

Пример преподавателя перефразирует доступные на cutoff атрибуты **актива**. Исходное и сгенерированное описания затем сравниваются как TF-IDF views в content-based фильтрации. Это LLM-Rec-inspired адаптация. Она не реализует исследовательский вопрос HW7 про представление **истории пользователя** в user-kNN.

## Что делает пример Ranker

Пример получает историю покупок и фиксированный список CBF-кандидатов, после чего LLM переставляет кандидатов. Этот вариант решает отдельный Ranker-вопрос и не требуется для моего индивидуального Encoder-эксперимента.

## Демонстрационные результаты из репозитория

В `HW2_RESULTS.md` приведены результаты учебного прогона преподавателя на 100 пользователях, а не результаты Team 5 или Алины. Там Qwen3-1.7B Encoder дал nDCG@10 `0.0254` по всем пользователям против `0.0235` у его original-text TF-IDF CBF контроля; оба значения ниже четырёх обязательных baseline. Результат Ranker совпал с CBF-контролем; 22 из 100 ответов перешли на fallback из-за невалидного вывода. Эти цифры нужны только для понимания примеров и не должны попадать в нашу таблицу как собственные результаты.

## Связь с моим экспериментом

Мой HW7-вопрос сохраняется: сравнить structured encoding истории пользователя и frozen Qwen embedding истории пользователя при одном и том же user-kNN и одинаковых данных. Планируемая модель — `Qwen/Qwen3-Embedding-0.6B` с зафиксированным revision. Код преподавателя можно изучать для структуры проекта и воспроизводимого запуска, но нельзя называть его готовым решением моего user-history Encoder.