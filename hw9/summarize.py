"""Build a readable summary from completed local HW9 run artifacts."""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

from verify_hw8 import load
from protocol import digest
from experiment import csv_save, read_csv, save


def summarize(out):
    manifest = load(out / 'manifest.json')
    assert manifest['status'] == 'completed'
    main = [load(out / method / 'metrics.json') for method in ('structured_knn', 'qwen_knn', 'tfidf_knn')]
    seeds = read_csv(out / 'shuffle_summary.csv')
    aggregate = load(out / 'shuffle_aggregate.json')
    paired = load(out / 'paired_comparisons.json')
    rows = [dict(method=m['method'], ndcg_at_10=m['ndcg_at_10'],
                 ndcg_at_10_nonempty=m['ndcg_at_10_nonempty'], users=100, nonempty_truth_users=11)
            for m in main]
    rows.append(dict(method='qwen_shuffle_seed_mean',
                     ndcg_at_10=aggregate['ndcg_at_10']['mean'],
                     ndcg_at_10_nonempty=aggregate['ndcg_at_10_nonempty']['mean'], users=100, nonempty_truth_users=11))
    csv_save(out / 'comparison_summary.csv', rows)
    fresh = manifest['mode'] == 'fresh_qwen_cuda'
    lines = ['# HW9 — ' + ('свежий Qwen CUDA' if fresh else 'локальный прогон на сохранённых векторах HW8'), '',
             f"Дата завершения: {manifest['completed_utc']}. Development-срез, не официальный benchmark. " +
             ('Выполнен новый Qwen inference.' if fresh else 'Новый Qwen inference не выполнялся.'), '',
             '| Метод | nDCG@10, все 100 | nDCG@10, 11 с покупками |', '|---|---:|---:|']
    for row in rows:
        lines.append(f"| {row['method']} | {row['ndcg_at_10']:.4f} | {row['ndcg_at_10_nonempty']:.4f} |")
    lines += ['', '## Десять перестановок', '',
              '| Seed | nDCG все 100 | nDCG по 11 | Изменённые векторы / 10404 | Изменённые векторы / 100 |',
              '|---|---:|---:|---:|---:|']
    for r in seeds:
        lines.append(f"| {r['seed']} | {float(r['ndcg_at_10']):.4f} | {float(r['ndcg_at_10_nonempty']):.4f} | "
                     f"{r['changed_vectors']} | {r['changed_evaluation_vectors']} |")
    lines += ['', 'Во всех seed донор сменился у всех 10404 пользователей и всех 100 оценочных пользователей. '
              'Меньшее число изменённых векторов связано с совпадающими векторами у разных доноров.', '']
    for key, value in aggregate.items():
        lines.append(f"- {key}: среднее {value['mean']:.4f}; диапазон "
                     f"{value['minimum']:.4f}–{value['maximum']:.4f}; Qwen − shuffle {value['original_qwen_minus_mean']:+.4f}.")
    lines += ['', '## Парные разности', '']
    for key, p in paired.items():
        lines.append(f"- {key}: {p['delta_all']:+.4f} / {p['delta_nonempty']:+.4f}; "
                     f"среди 11 Qwen лучше / хуже / равен: {p['improved']} / {p['worsened']} / {p['tied']}.")
    cases = load(out / 'relevant_pair_analysis.json')
    failure = next((c for c in cases if c['ISIN'] == 'GRS372003004' and c['methods']['structured_knn']['rank'] == 6), None)
    improvement = next((c for c in cases if c['methods']['tfidf_knn']['rank'] is not None and c['methods']['qwen_knn']['rank'] is None), None)
    for title, c in (('Случай HW8: сопоставление представлений', failure), ('TF-IDF вернул купленный актив в Top-10', improvement)):
        if c is None:
            continue
        lines += ['', '## ' + title, '', f"Пользователь `{c['user_id']}`, июньский Buy `{c['ISIN']}`. "
                  f"Прошлых покупок: {c['past_buy_events']}; строк профиля до/после обрезки: "
                  f"{c['truncation']['original_rows']}/{c['truncation']['retained_rows']}.", '',
                  '| Метод | Ранг в Top-10 | Голосующих соседей | Сумма весов за актив | nDCG пользователя |',
                  '|---|---:|---:|---:|---:|']
        for method, details in c['methods'].items():
            rank = details['rank'] if details['rank'] is not None else 'вне Top-10'
            lines.append(f"| {method} | {rank} | {len(details['voters'])} | "
                         f"{details['sum_vote_weights']:.6f} | {details['ndcg_at_10']:.4f} |")
        lines += ['', 'Пересечение наборов из 20 соседей: ' +
                  '; '.join(f'{key}: {n}' for key, n in c['neighbor_overlap'].items()) + '.',
                  'Сумма весов показана как диагностическая сумма cosine; scorer накапливает оценки в float32.']
    lines += ['', '## Диагностика', '',
              '- Релевантных пар пользователь–актив: 18; попадания в Top-10: ' +
              ', '.join(f"{m['method']}: {m['hit_pairs']}" for m in main) + '.',
              '- Диагностика каждой ветки (invalid vectors/queries/outputs, repairs, fallback): `metrics.json`; '
              'ошибки inference: `qwen_knn/inference.json` для свежего прогона.',
              '- Истории и метки сохранились; исходная Qwen-матрица неизменна. Все перестановки воспроизводимы и биективны внутри групп.',
              '- Только 11 пользователей имеют июньские покупки; 89 остальных дают нули во всех методах. '
              'Разброс seed описывает выбранные перестановки на этом срезе, а не доверительный интервал.',
              '- Результаты и расчёт manual_check.json проверены автоматически агентом; личная ручная проверка автора ещё предстоит.', '']
    (out / 'RESULTS.md').write_text('\n'.join(lines), encoding='utf-8')
    # Include this reporting code and update the archive with the generated tables.
    snapshot = out / 'code/hw9/summarize.py'
    snapshot.write_bytes(Path(__file__).read_bytes())
    save(out / 'report_metadata.json', dict(report_code_sha256=digest(Path(__file__)),
                                           source_manifest_sha256=digest(out / 'manifest.json')))
    shutil.make_archive(str(out), 'zip', root_dir=out)
    with zipfile.ZipFile(str(out) + '.zip') as archive:
        assert archive.testzip() is None
    print('\n'.join(lines))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    summarize(parser.parse_args().output_dir)
