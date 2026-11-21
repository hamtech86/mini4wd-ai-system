# UUIDv5 Canonical Binary Name v2 — 不採用決定・歴史監査メモ

> **Decision Overlay:** §19によりUUIDv5 / Canonical Binary Name v2 / Namespaceはv0.8.3で不採用。§1〜§18は過去候補方式の監査記録であり、現在のID発行仕様ではない。

- 基準日: 2026-11-21
- 対象: `COMMON_DB_LOGICAL_DESIGN_v0.8.3_REMEDIATION_DRAFT.md` §5.2〜5.5
- 対象ブランチ: `docs/db-logical-design-v0.8.3-remediation-20261120`
- 状態: **独立監査メモ・未承認**
- 制約: 本メモは論理仕様の検証資料。Namespace採用、実装合格、DDL/DB/実装移行を承認しない。

## 1. 監査結論

**提示済みCanonical byte golden vector 7件は、記載された文法に従って独立再計算した結果、7件すべて一致した。**

| Case | 結果 | 検証内容 |
|---|---|---|
| DB_RUN | 一致 | Entity Type長、Field Count、UUID tag/length/network-order |
| RUN_SCOPE | 一致 | 2 Fieldの順序、UUID、ASCII ScopeKey payload |
| NULL | 一致 | tag 0x00 / length 0 |
| EMPTY | 一致 | tag 0x01 / length 0 |
| DELIMITER_PERCENT_NUL | 一致 | 6 bytes: 41 7C 42 25 00 43 |
| NFC | 一致 | U+00E9 → C3 A9 |
| NFD input | 一致 | U+0065 U+0301をNFC化しC3 A9 |

この結果は、上記7件のName byte列の正しさだけを示す。UUIDv5出力、全Entity Schema、境界値、既存IDとの互換性、Namespaceは未検証・未承認であり、Canonicalization仕様全体の完成を意味しない。

## 2. 重要な未確定事項

### CBN-01 — Entity Schemaごとのgolden vector（BASELINE COMPLETE / EXTENDED COVERAGE INCOMPLETE）

§5.3に定義された11 Entityすべてについて、正常値のCanonical Name byte vectorを§5.5および§6に用意した。したがって「正常値vectorがない」という初期指摘は解消した。

ただし、11 Entityはv0.8.3 §5.3に列挙された範囲に限る。Entity Inventoryの全論理Entityを網羅したものではなく、各FieldのNULL/空/境界/不正入力vectorも未完了である。

次のEntityについては正常値vectorを追加済みである:

- SESSION
- OPERATION_EVENT
- RECEIPT
- RECEIPT_EVENT
- RAWLOG_REFERENCE
- SAMPLE_REFERENCE
- MEASUREMENT_SAMPLE_LINK
- ARTIFACT_INPUT
- AGGREGATE_RESULT_REVISION

TEST_VALUEは汎用文法の試験であり、Entity別Schemaの検証を代替しない。今後は各EntityのFieldごとに、許可されるNULL/空/境界値/Unicode/byte-orderと拒否ケースを追加すること。

### CBN-02 — Field型ごとの厳密な受入・拒否規則不足（BLOCKER）

次を明記する必要がある。

- UTF-8: strict encoding/decodingとし、不正UTF-8、孤立サロゲート、BOMの扱いを定義する。
- NFC: Unicode Normalization Form Cを適用することは定義済みだが、Unicodeデータ版と未割当コードポイントの扱いが未定義。
- ASCII string: RUN_SCOPE.ScopeKeyはASCIIと明記されている。非ASCII入力を拒否することを明記する。
- Integer: canonical decimalのほか、各Fieldの許容範囲、最大桁数、負数の範囲、`-0`拒否、先頭ゼロ拒否を定義する。
- Timestamp: signed 64-bit nanosecondsの範囲、UTC変換、sub-nanosecond拒否に加え、入力から整数nsへの変換規則、overflow拒否、Unix epochの定義を固定する。
- Boolean: payloadは厳密に1 byteの00または01のみ許可する。
- Byte String: 任意byteを許すか、長さ上限、空byte列の扱いを定義する。
- NULL: NULLを許可するFieldと禁止するFieldをEntity Schema側で個別に固定する。tag 0x00以外でNULLを表現しない。

### CBN-03 — 長さ・カウントの上限とoverflow動作不足（BLOCKER）

Entity Type lengthはu16、Field Countはu16、Payload Lengthはu32である。各最大値を超えた場合は符号化前に拒否し、切り詰め・wrap・暗黙拡張をしないことを明記する。Entity TypeのASCII大文字限定、空文字禁止、未知Entity拒否も固定する。

### CBN-04 — Canonicalization VersionとSchema変更の関係不足（BLOCKER）

Headerの`M4ID\0 2`がCanonicalization Versionを識別することは読み取れるが、Field順・Field型・Entity名・NFC規則等を変更する場合のVersion更新規則がない。同じVersionのままSchemaを変更すると既存IDとの衝突・再現不能を招くため、Canonical byteに影響する変更はVersionを上げる規則を定義すること。

### CBN-05 — Timestamp / Integer / Boolean / Byte Stringの境界vector不足（MAJOR）

§7にInteger 0/正/負、Timestamp epoch/±1ns、Boolean false/true、Byte String empty/NULの汎用vectorを追加済み。ただし、最大・最小値、overflow、拒否入力、UUID API byte-orderの受入/拒否境界は未完了。最低限、以下を追加する。

- Integer: 0、正数、負数、最大許容値、最小許容値、`-0`・先頭ゼロ拒否
- Timestamp: epoch 0、epoch前の負値、正値、signed 64-bit境界、sub-nanosecond拒否、overflow拒否
- Boolean: false / true、長さ0・2以上の拒否
- Byte String: empty / NUL含有 / 任意byte、最大長境界
- UUID: 16-byte network orderと、little-endian誤実装を明確に区別するvector

### CBN-06 — Collision pairのEntity適用・domain uniqueness不足（MAJOR）

汎用文法の具体pairは§9で追加済み。残課題は、各Entityの実Field Schemaでの適用可能性確認と、byte-level distinctionとdomain uniquenessの分離である。

- NULL と empty string
- `A|B` と別Fieldに分割した`A`, `B`
- `A%00B`という文字列と、U+0000を含む文字列
- Integer 1 と文字列`1`
- UUIDのnetwork-orderとlittle-endian表現
- Field順を入れ替えた入力

### CBN-07 — NUL表記の明確化（RESOLVED IN DOCUMENTATION）

Main draft §5.5 now expresses the input as the Unicode scalar sequence U+0041 U+007C U+0042 U+0025 U+0000 U+0043 and the UTF-8 bytes `41 7C 42 25 00 43`. This removes ambiguity between a literal backslash + digit and an actual U+0000 scalar. Expected Hex remains unchanged and encodes a 6-byte payload.

### CBN-08 — UUIDv5手順の実装境界（MAJOR）

Namespaceが承認された後、RFC 9562準拠のUUIDv5について次を固定する。

- Namespace UUIDの16-byte network order
- Name bytesを正規化後に追加連結すること
- SHA-1 digestの先頭16 bytesを使用すること
- Version 5 / RFC variant bitの設定
- UUID文字列表記への変換
- Namespace + Nameの既知RFC test vectorとの照合

Namespace未承認の現時点でUUID期待値を未設定にする判断は妥当。候補Namespaceを実装採用・既存正本として扱ってはならない。

## 3. Namespace既存利用調査の現時点の範囲

2026-11-21時点で次を確認した。

- GitHub Code Searchで候補UUID文字列を検索したが、検索対象はdefault branchの索引であり、該当結果は得られなかった。
- GitHub Commit Searchで候補UUID文字列および`Canonicalization UUIDv5`を検索したが、該当コミットは得られなかった。
- GitHub Branch Searchでは少なくとも181件のbranch名をページング取得した。ただし全branchの全ファイル内容を走査したわけではない。
- したがって「既存利用なし」とは結論できない。未調査branch、過去commit、削除済みファイル、Issue/PR本文、過去の生成済みID資産が残る。

Namespace採用判断には、全branch・全commit履歴・Issue/PR・過去のID生成資産を対象とした検索記録と、統括承認が別途必要である。

## 4. 統括再審査への回答状況

| 要求 | 状態 |
|---|---|
| Canonical Binary文法 | 骨格は提示済み |
| 提示済み7 vectorの独立計算 | **7/7一致** |
| v0.8.3 §5.3の11 Entity正常値vector | 作成済み。Entity Inventory全体は未網羅 |
| NULL/empty/区切り/NUL/NFC/NFD | 汎用vectorの範囲で確認 |
| Integer/Timestamp/Boolean/Byte String汎用vector | 基本vector追加済み。境界/overflow/拒否vectorは未完了 |
| Collision pair具体vector | 汎用pair追加済み。Entity別domain uniquenessは未完了 |
| 全入力範囲・overflow・拒否規則 | 未完了 |
| Namespace既存利用の全履歴調査 | 未完了 |
| Namespace採用 | 未承認 |
| UUIDv5実装試験 | 未実施 |

## 5. 次の修正条件

1. CBN-02〜04の型境界・overflow・Version更新規則を確定する。
2. 11 EntityのFieldごとのNULL/空/境界/拒否vectorを追加し、Entity Inventoryの残りEntityとのCanonical Identity/Content Hash方針を定義する。
3. 汎用Collision pairを実Entity Schemaに適用可能か照合し、Entity domain uniquenessを定義する。
4. Namespace既存利用調査の検索範囲・未調査範囲を明示し、統括判断を受ける。
5. Namespace承認後にのみUUIDv5期待値を確定し、RFC既知vectorおよび独立実装試験を行う。

**結論:** 現行7 vectorのバイト列計算は正しい。一方、Issue #209 DB-RV-06の再提出条件はまだ満たしていない。Canonicalization全体は未完成・未承認であり、実装移行不可。


## 6. 追加のEntity別Canonical byte vector（Namespace非依存）

CBN-01を進めるため、§5.3の残り9 Entityについて、固定サンプル値を使ったCanonical Name byte列を追加計算した。これはNamespace非依存のName byte vectorであり、UUIDv5期待値ではない。全Fieldは§5.2の型tag / length規則で符号化し、文字列はNFC後UTF-8、UUIDは16-byte network order、Integerはcanonical decimal ASCIIとした。

サンプルUUID:
- U1 = `00000000-0000-4000-8000-000000000001`
- U2 = `00000000-0000-4000-8000-000000000002`
- U3 = `00000000-0000-4000-8000-000000000003`
- U4 = `00000000-0000-4000-8000-000000000004`
- U5 = `00000000-0000-4000-8000-000000000005`
- U6 = `00000000-0000-4000-8000-000000000006`
- U7 = `00000000-0000-4000-8000-000000000007`

| Entity | Fixed sample input | Expected Name Bytes (hex) |
|---|---|---|
| SESSION | PhysicalRunID=U1, ScopeKey=`BATTERY:CH1` | `4D3449440032000753455353494F4E0002020000001000000000000040008000000000000001010000000B424154544552593A434831` |
| OPERATION_EVENT | OperationID=U2, EventOrdinal=7 | `4D3449440032000F4F5045524154494F4E5F4556454E540002020000001000000000000040008000000000000002030000000137` |
| RECEIPT | OperationID=U2 | `4D34494400320007524543454950540001020000001000000000000040008000000000000002` |
| RECEIPT_EVENT | ReceiptID=U3, EventOrdinal=2 | `4D3449440032000D524543454950545F4556454E540002020000001000000000000040008000000000000003030000000132` |
| RAWLOG_REFERENCE | PhysicalRunID=U1, ScopeKey=`BATTERY:CH1`, LogID=`rawlog-0001` | `4D344944003200105241574C4F475F5245464552454E43450003020000001000000000000040008000000000000001010000000B424154544552593A434831010000000B7261776C6F672D30303031` |
| SAMPLE_REFERENCE | RawLogReferenceID=U4, SampleLocator=`sample:0001` | `4D3449440032001053414D504C455F5245464552454E43450002020000001000000000000040008000000000000004010000000B73616D706C653A30303031` |
| MEASUREMENT_SAMPLE_LINK | MeasurementID=U5, SampleReferenceID=U4, Role=`PRIMARY`, Ordinal=0 | `4D344944003200174D4541535552454D454E545F53414D504C455F4C494E4B000402000000100000000000004000800000000000000502000000100000000000004000800000000000000401000000075052494D415259030000000130` |
| ARTIFACT_INPUT | ArtifactID=U6, InputType=`MEASUREMENT`, InputReferenceID=U5, Role=`SOURCE`, Ordinal=1 | `4D3449440032000E41525449464143545F494E5055540005020000001000000000000040008000000000000006010000000B4D4541535552454D454E540200000010000000000000400080000000000000050100000006534F55524345030000000131` |
| AGGREGATE_RESULT_REVISION | DBRunID=U7, Revision=3 | `4D344944003200194147475245474154455F524553554C545F5245564953494F4E0002020000001000000000000040008000000000000007030000000133` |

この追加により、§5.3の11 Entityすべてに少なくとも1件のName byte vectorが存在する（DB_RUN / RUN_SCOPEは§5.5、残り9 Entityは本節）。ただし、これは独立実装との相互試験やEntityごとの全境界試験を代替しない。特にEntityごとのNULL許可・Field domain・一意制約は未確定であり、上表は単一の正常サンプルに限る。

## 7. 汎用Field型の追加byte vector

| Type | Sample | Expected Name Bytes (hex) |
|---|---|---|
| Integer | 0 | `4D3449440032000A544553545F56414C55450001030000000130` |
| Integer | +123 | `4D3449440032000A544553545F56414C554500010300000003313233` |
| Integer | -123 | `4D3449440032000A544553545F56414C5545000103000000042D313233` |
| Timestamp | epoch 0 ns | `4D3449440032000A544553545F56414C5545000104000000080000000000000000` |
| Timestamp | epoch -1 ns | `4D3449440032000A544553545F56414C554500010400000008FFFFFFFFFFFFFFFF` |
| Timestamp | epoch +1 ns | `4D3449440032000A544553545F56414C5545000104000000080000000000000001` |
| Boolean | false | `4D3449440032000A544553545F56414C55450001050000000100` |
| Boolean | true | `4D3449440032000A544553545F56414C55450001050000000101` |
| Byte String | empty bytes | `4D3449440032000A544553545F56414C554500010600000000` |
| Byte String | one NUL byte | `4D3449440032000A544553545F56414C55450001060000000100` |

Integer vectorはcanonical decimal ASCIIのtag/length/payload、Timestamp vectorはsigned 64-bit big-endian nanoseconds、Boolean vectorは1-byte payload、Byte String vectorはraw bytesを示す。許容範囲・overflow拒否・不正payload拒否は、§2 CBN-02/03/05の未完了条件として残る。

## 8. Entity vector追加後の更新状況

| 要件 | 更新後 |
|---|---|
| 11 Entityすべての正常Name byte vector | **作成済み（計算上の期待値）** |
| 汎用Integer/Timestamp/Boolean/Byte String vector | 追加済み |
| 全EntityのFieldごとの境界/NULL/空/不正入力vector | 未完了 |
| EntityごとのNULL許可・Field domain確定 | 未完了 |
| Collision pairの汎用vector | 追加済み。Entity別domain uniquenessは未完了 |
| UTF-8/NFC/Unicode version/ASCII拒否/overflow仕様 | 未完了 |
| UUIDv5 Namespace | 未承認 |
| 独立した2実装間のvector照合 | 未実施 |


## 9. Collision pairの具体的な期待値

CBN-06に対して、同一Entity Typeで入力構造・Field Type・Field順が異なる具体pairを追加する。各pairは異なるCanonical Name byte列になることを期待する。

| Pair | Case A | Expected Hex A | Case B | Expected Hex B |
|---|---|---|---|---|
| Field境界 / delimiter | 1 Field: string `A|B` | `4D3449440032000A544553545F56414C554500010100000003417C42` | 2 Fields: string `A`, string `B` | `4D3449440032000A544553545F56414C55450002010000000141010000000142` |
| Percent text / NUL scalar | string `%00` | `4D3449440032000A544553545F56414C554500010100000003253030` | string containing U+0000 | `4D3449440032000A544553545F56414C55450001010000000100` |
| Type separation | Integer 1 | `4D3449440032000A544553545F56414C55450001030000000131` | UTF-8 string `1` | `4D3449440032000A544553545F56414C55450001010000000131` |
| Field order | 2 Fields: `A`, `B` | `4D3449440032000A544553545F56414C55450002010000000141010000000142` | 2 Fields: `B`, `A` | `4D3449440032000A544553545F56414C55450002010000000142010000000141` |
| UUID byte order | UUID `00112233-4455-6677-8899-aabbccddeeff`, network order | `4D3449440032000A544553545F56414C55450001020000001000112233445566778899AABBCCDDEEFF` | Same UUID, little-endian first fields (invalid encoding) | `4D3449440032000A544553545F56414C55450001020000001033221100554477668899AABBCCDDEEFF` |

NULL / empty-string pair is already in §5.5. Unicode NFC/NFD equivalence is also already in §5.5: those two source inputs intentionally produce the same normalized bytes, rather than a collision failure.

The pairs above demonstrate byte-level distinction. They do not define semantic uniqueness constraints: whether two different canonical Names may refer to equivalent domain values remains governed by each Entity's unique-key rules, which are not yet fully specified.

## 10. Collision vector update status

- Generic byte-level collision pairs: added for delimiter/field boundary, percent/NUL, type tag, field order, UUID network/little-endian order.
- NULL vs empty: existing vector.
- NFC vs NFD: existing equivalence vector.
- Invalid UUID little-endian encoding: shown as a deliberately different byte sequence; actual encoder must always use network order and reject alternate byte-order APIs.
- Entity-level uniqueness and domain collision policy: still unresolved and must be specified separately.


## 11. 追加の機械的構造検査（2026-11-21）

監査メモ内のExpected Hex表記29件を、Canonical Binary Name v2の外形文法で機械的に走査した。

- Header `M4ID\0 2`の一致
- Entity Type Length（u16）でEntity Typeを過不足なく切り出せること
- Field Count（u16）分のFieldが存在すること
- 各FieldのType Tag + Payload Length（u32）でPayloadを過不足なく切り出せること
- 末尾に余剰byteが残らないこと

結果: **29/29件が構造解析を通過し、構造解析エラー0件。**

この検査は、文書内Hex列の長さ・境界・構文を確認したもの。EntityごとのField値が正しいか、NULL/domain制約に適合するか、UUIDv5出力が正しいか、2つの独立実装で一致するかは証明しない。

## 12. 文書内の更新後ステータス

| 項目 | 更新後 |
|---|---|
| §5.3の11 Entity正常値vector | 作成済み |
| 29 Expected Hexの構造解析 | 29/29通過 |
| 11 Entity全FieldのNULL/空/境界/拒否vector | 未完了 |
| Entity Inventory全論理EntityのCanonical identity coverage | 未完了 |
| UTF-8/NFC/Unicode version/ASCII拒否/overflow仕様 | 未完了 |
| Entity domain uniqueness | 未完了 |
| Namespace既存利用の全履歴調査・統括承認 | 未完了 |
| UUIDv5 RFC vector / 2実装相互照合 | 未実施 |


## 13. Entity Inventory 23種とのCanonical Identity照合（2026-11-21）

Entity Inventory 23種とMain draft §5.3を個別照合した結果:

- Inventory: 23 logical entities.
- §5.3: 11 Entity Schema rows（うち `OPERATION_EVENT` はInventoryへの対応が未確定。TEST_VALUEは汎用vector用でEntity Inventory外）。
- Inventoryと直接対応するSchema: 10種。
- Schema未定義: 13種。
- Inventoryへの対応が未確定のSchema: `OPERATION_EVENT` 1種。

「Schema未定義」はUUIDv5を追加すべきという意味ではない。Entityごとに、Identity UUID / Composite identity / Content Hash / Derived Pointer / External event identityのいずれで識別するかを決める必要がある。

特に以下を混同しない:
- Physical Run ManifestとPhysicalRunID（UUIDv4候補）。
- RawLog ObjectのContent HashとRawLog Reference ID。
- Measurement Envelope IDとEnvelope Hash。
- Artifact IDとResult Payload Content Hash。
- Operation Journal IntentとOperation Event（`OPERATION_EVENT` schemaの候補だが未確定）。
- Aggregate Pointer（派生参照であり、独立IDを持たない可能性）。
- Recovery Operation IDとIntegrity Report ID / report Content Hash。

Entityごとの照合結果・未決事項は `V083_ENTITY_INVENTORY_GAP_REGISTER_DRAFT.md` §6を参照する。Main draft §5.3の11 SchemaをInventory全体へ一般化してはならない。

## 14. CBN-01 / CBN-02 coverage status update

| 項目 | 状態 |
|---|---|
| §5.3 11 Schema rowの正常値byte vector | 既存の作成記録あり（OPERATION_EVENTのInventory対応は未確定） |
| Inventory 23 Entityとの対応表 | 今回作成 |
| 23 Entity全体のIdentity方式分類 | 未完了 |
| UUIDv5対象Entityの確定 | 未完了 |
| UUIDv5対象Field Schema / domain uniqueness | 未完了 |
| Content Hash / Composite identity / Derived Pointerとの境界 | 未完了 |
| Namespace既存利用全履歴調査・統括承認 | 未完了 |
| UUIDv5 RFC vector / 2実装相互照合 | 未実施 |

**監査結論:** Canonical Nameの正常値vector作成済み範囲と、Entity Inventory全体のIdentity設計完成は別工程である。v0.8.3は引き続き未完成・未承認。


## 15. §5.5 / §6 Entity vector independent recalculation (2026-11-21)

The fixed sample inputs for all 11 §5.3 Schema rows were independently re-encoded from the documented v2 grammar (Header, Entity Type length/name, Field Count, Type Tag, Payload Length, and payload bytes).

| Vector group | Cases | Result |
|---|---:|---|
| §5.5 baseline | DB_RUN, RUN_SCOPE | 2/2 exact match |
| §6 Entity additions | SESSION, OPERATION_EVENT, RECEIPT, RECEIPT_EVENT, RAWLOG_REFERENCE, SAMPLE_REFERENCE, MEASUREMENT_SAMPLE_LINK, ARTIFACT_INPUT, AGGREGATE_RESULT_REVISION | 9/9 exact match |
| **Total** | **11 Entity Schema rows** | **11/11 exact match** |

The recalculation confirms the byte strings for the documented sample inputs. It does not validate the appropriateness or completeness of each Entity Field Schema, field-domain restrictions, UUIDv5 output, Namespace, uniqueness, or full Entity Inventory coverage.

The Inventory coverage matrix is now in `V083_ENTITY_INVENTORY_GAP_REGISTER_DRAFT.md` §6. It identifies 10 direct mappings, 13 Inventory entities without a defined Schema, and one `OPERATION_EVENT` Schema whose Inventory mapping remains unresolved. This reconciles the apparent difference between 11 schema rows and 23 logical entities without inventing UUIDv5 identities.

## 16. CBN-02〜04 closure proposal — version freeze and strict field handling (DRAFT ONLY)

The following is a proposed acceptance contract to close the current blockers. It is not yet normative and must be reviewed before it is copied into the main logical design.

### 16.1 Canonicalization Version freeze

A Canonicalization Version MUST freeze all byte-affecting behavior:
- Header bytes and version identifier encoding.
- Entity Type registry, spelling, and case rules.
- Field count, fixed field order, field names, field type tags, and payload encoding.
- NULL allowance per field.
- String encoding and Unicode normalization algorithm/data version.
- Integer domain/decimal encoding and timestamp epoch/precision/range.
- UUID byte order and accepted UUID variant/version policy.
- Maximum lengths/counts and overflow/rejection behavior.

Any change to a frozen item that can change a Name byte sequence, accepted identity domain, or interpretation of an existing identity requires a new Canonicalization Version. A version MUST NOT be silently redefined in place. An implementation MUST reject unknown versions and unknown Entity Type / Field Schema rather than guessing.

A schema-only extension that adds a field, changes field order/type, changes normalization data version, or changes a previously accepted value's canonical representation is a new version. Existing IDs are never silently regenerated; compatibility or migration requires separate approval and evidence.

### 16.2 Proposed strict input rules

| Type | Proposed acceptance / rejection |
|---|---|
| UTF-8 string | Strict Unicode scalar input and strict UTF-8 encoding. Reject malformed UTF-8, overlong encodings, surrogate code points, and values above U+10FFFF. Never replace invalid input with U+FFFD. |
| BOM | Do not strip a leading U+FEFF as an encoding signature. Treat it as a scalar value subject to the field's domain rule. |
| NFC | Normalize with one pinned Unicode data version. Record the exact version in the Canonicalization profile. Reject code points unassigned in that pinned version unless a future version explicitly defines another rule. |
| ASCII string | Reject every non-ASCII scalar. Field-specific grammar (allowed characters, case, length) remains separately defined. |
| Integer | Accept an integer value only (not bool, float, or permissively parsed text). Encode canonical decimal ASCII: `0`, positive digits without leading zero, negative sign plus nonzero magnitude. Reject `+`, leading zero, and `-0`. Numeric min/max is field-specific and remains to be declared. |
| Timestamp | Accept timezone-aware input only; convert to UTC Unix epoch nanoseconds exactly. Reject naive timestamps, float-based lossy conversion, sub-nanosecond precision, and signed-64-bit overflow. Leap-second handling must be explicitly fixed before approval. |
| Boolean | Exactly one payload byte: `00` or `01`; reject all other lengths/values. |
| Byte String | Preserve bytes exactly; empty is valid and distinct from NULL. Reject payloads above the u32 length limit before allocation/encoding. |
| NULL | Only accepted on fields explicitly marked nullable in the Entity Schema; encode only as tag `00` / length 0. |
| Lengths / counts | Entity Type length and Field Count must fit u16; Payload Length must fit u32. Reject overflow before serialization; never truncate or wrap. |

### 16.3 Remaining decisions before adoption

- Pin the Unicode data version and publish test vectors for newly assigned / unassigned / normalization-sensitive code points.
- Set exact per-Field integer ranges, string grammars, nullability, and maximum payload lengths.
- Define Timestamp leap-second behavior and exact supported input representation.
- Confirm the Entity Type registry and complete Inventory-to-Schema mapping.
- Define Entity-level uniqueness separately from byte-level collision distinction.
- Obtain Namespace full-history clearance and explicit central approval.
- Verify RFC UUIDv5 known-answer vectors and two independent implementations after Namespace approval.

**Status:** candidate remediation text only. CBN-02 / CBN-03 / CBN-04 remain OPEN until central review and all Entity domain schemas are complete.


## 17. CBN-07 notation correction verification

Read-back check confirms Main draft §5.5 uses the explicit Unicode scalar sequence and six UTF-8 bytes. CBN-07 is resolved as a documentation ambiguity only; no encoding rule or Expected Hex changed.


## 18. Independent semantic recalculation of all audit vectors (2026-11-21)

Beyond the Entity sample checks in §15, the 10 generic Field-type vectors in §7 and 10 collision-pair encodings in §9 were independently reconstructed from their documented typed inputs.

| Group | Cases | Result |
|---|---:|---|
| Entity-specific vectors in §6 | 9 | 9/9 exact match |
| Generic Field vectors in §7 | 10 | 10/10 exact match |
| Collision-pair encodings in §9 | 10 | 10/10 exact match |
| **Total Expected Hex occurrences in this audit memo** | **29** | **29/29 exact match** |

The two DB_RUN / RUN_SCOPE vectors in Main draft §5.5 were separately recalculated and matched exactly (2/2). The additional NULL / EMPTY / delimiter / NFC / NFD examples in Main draft §5.5 remain byte-consistent with the previously recorded independent check.

This is byte-level reproduction of published sample inputs only. It does not prove that the Entity schemas are semantically correct, that every Inventory entity has a schema, that values meet per-Field domains, that Namespace is safe/approved, or that UUIDv5 implementations interoperate.

## 19. Canonical Identity方式の最終決定（2026-11-21）

**決定: UUIDv5 / Canonical Binary Name v2 / Namespaceはv0.8.3で不採用。**

- 新規独立Entity IDは暗号学的乱数源によるUUIDv4。IDは作成時に外部正本へ記録し、Restore時に再発行しない。
- Receipt IDもUUIDv4としてIntentに固定する。Operation IDからの決定的導出は廃止。
- 構造化Payloadの整合性HashはMain §5.2のM4W-JCS-1 / SHA-256。RawLogは原本全byteのSHA-256。
- §6〜§18の既存Canonical byte vectorsは候補方式の監査記録として保管するが、UUIDv5採用・実装のPASS根拠にはしない。
- Namespace既存利用調査とUUIDv5 RFC vectorsはv0.8.3の承認条件から除外。M4W-JCS-1のJCS conformance testとPayload schema testは実装前の受入試験として残す。

CBN-01〜08の未解決表現は、UUIDv5を採用しないことでv0.8.3のIdentity設計判断から切り離す。
