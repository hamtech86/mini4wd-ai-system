# Fixed Motor Firmware Archive

このディレクトリを、固定版モーターFWの入口とする。今後はここから版別の固定ソース・ビルド識別子・関連PR・検証証拠へ移動する。

## 固定版一覧

| Version | Fixed source | Build ID | Firmware history |
|---|---|---|---|
| [3.01](3.01.md) | [MotoreRev.ino @ be3d024](https://github.com/hamtech86/mini4wd-ai-system/blob/be3d02429755460386a0c41b32746e5a3bfcc3df/firmware/motor/MotoreRev.ino) | `STOP-SAFETY-20261021-01` | [PR #102](https://github.com/hamtech86/mini4wd-ai-system/pull/102) |
| [3.03](3.03.md) | [MotoreRev.ino @ 798e4dc](https://github.com/hamtech86/mini4wd-ai-system/blob/798e4dc5296a1f5b6e0c50441168b45fde2df0a1/firmware/motor/MotoreRev.ino) | `ARM-STOP-ACK-ACS712-RAIL-20261023-01` | [PR #118](https://github.com/hamtech86/mini4wd-ai-system/pull/118), [PR #125](https://github.com/hamtech86/mini4wd-ai-system/pull/125) |

## 運用ルール

- このディレクトリを固定版の一覧・参照起点として維持する。
- 固定ソースは必ず完全なコミットSHAに固定したリンクで参照し、`main` や可変ブランチのリンクを固定版の根拠にしない。
- 履歴PR、ソース一致、ビルド成功、HEX SHA-256、実機書き込み、実機INFO照合、実機動作確認を別々に記録する。
- 固定版ファイルは履歴保全用。通常開発中の `firmware/motor/MotoreRev.ino` で上書きしない。
- 新しい版を追加するときは、版別ページとこの一覧を同じPRで更新する。
- このアーカイブへの追加は、固定版の再書き込みや実機試験の許可を意味しない。

## 重要

「固定版」は再現可能なソース参照を意味する。実機に現在書き込まれている版を保証するものではない。書き込み前には対象HEXのハッシュと実機INFOのBUILDを別途照合する。
