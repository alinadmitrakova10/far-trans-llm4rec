# HW9: кодирование истории пользователя в FAR-Trans

Сравниваем признаки профиля, TF-IDF и замороженный Qwen3-Embedding-0.6B с одним user-kNN (`k=20`) на общем июньском срезе. В абляции перераспределяем Qwen-векторы между пользователями с близким числом прошлых Buy-событий, включая повторы. Для каждой из десяти перестановок (`seed` 42–51) истории и июньские метки остаются у исходных пользователей.

## Входные файлы

Команды запускаются из корня репозитория. Для проверки и локального прогона понадобятся:

- Четыре исходных CSV из [FAR-Trans](https://researchdata.gla.ac.uk/1658/) в `data/raw/FAR-Trans/FAR-Trans/`.
- `hw8/outputs/hw8_t4_encoder_outputs.zip` и его содержимое в `hw8/outputs/colab_gpu/`, с папками `baseline/` и `encoders/`.
- `hw8/reference/starter/starter.py` из исходного загрузочного архива HW8 `workflow_bundle.zip`. Скрипт проверяет SHA-256 `bf6b7c0b0b271e057e82547eff23738e65bc9cdbb626703d13d1801ff99aab80`.

## Локальная проверка и сравнение

Окружение локального CPU-прогона зафиксировано в `requirements-local.txt` (Python 3.14.3).

```powershell
python -m pip install -r hw9/requirements-local.txt
python -m unittest discover -s hw9 -p test_local.py -v
python hw9/verify_hw8.py --output-dir hw9/outputs/hw8_reproduction_20261126
python hw9/run.py --output-dir hw9/outputs/local_saved_hw8_20261126
python hw9/summarize.py --output-dir hw9/outputs/local_saved_hw8_20261126
```

`verify_hw8.py` сверяет исходные данные и артефакты и повторно оценивает сохранённые представления. `run.py` использует эти представления и считает TF-IDF и перестановки. Для повторного запуска укажите новую папку результатов. Если `verification.json` находится по другому пути, передайте его через `--verification`.

## Свежий Qwen-инференс в Colab

1. После проверки HW8 соберите загрузочный архив командой `python hw9/build_colab_bundle.py`.
2. Откройте [ноутбук](notebooks/hw9_fresh_qwen_t4.ipynb) в Colab со средой Python 3.11 или 3.12 и Tesla T4. Загрузите `hw9/outputs/hw9_colab_bundle.zip` в ячейку 1.
3. Установите зависимости в ячейке 2, перезапустите сеанс Python и продолжите с ячейки 3. В ячейке 4 загрузите исходный `FAR-Trans.zip`.
4. Запустите ячейки 5–8. Последняя скачает архив результатов. В этом прогоне перестановки используют свежие Qwen-векторы.

В выходных папках сохраняются Top-10, nDCG@10 по каждому пользователю, диагностика и раздельные замеры построения представлений и скоринга. `comparison_summary.csv` содержит средние по всем 100 пользователям и по 11 пользователям с июньскими покупками.
