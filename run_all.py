"""全コレクターを実行し、統合・フィルタして site/data/data.json を更新する。

各コレクターは独立に実行し、1つ失敗しても他とビルドは止めない（仕様書 第8章）。
失敗したソースは前回の data/raw/<source>.json がそのまま使われる。
"""
import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

COLLECTORS = [
    ("jgrants", "collectors.fetch_subsidies"),
    ("jetro", "collectors.fetch_jetro"),
    ("curated", "collectors.fetch_curated"),
    ("manual", "collectors.fetch_manual"),
]


def main() -> int:
    results = {}
    failed = []
    for name, module_name in COLLECTORS:
        print(f"[{name}] 収集を開始します...")
        try:
            module = importlib.import_module(module_name)
            results[name] = module.run()
            print(f"[{name}] {results[name]}件を取得しました")
        except ModuleNotFoundError:
            print(f"[{name}] コレクター未実装のためスキップします")
        except Exception:
            failed.append(name)
            print(f"[{name}] 失敗しました（前回データを維持します）:")
            traceback.print_exc()

    from pipeline import merge_and_filter
    data = merge_and_filter.run()

    print("=" * 50)
    print(f"取得件数: {sum(results.values())}件 ({', '.join(f'{k}:{v}' for k, v in results.items())})")
    print(f"フィルタ後件数: {data['count']}件")
    print(f"失敗ソース: {', '.join(failed) if failed else 'なし'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
