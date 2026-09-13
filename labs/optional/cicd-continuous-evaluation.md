# Optional — CI/CD と継続的評価

## ゴール

Portal で検証済みの Hosted Agent source と evaluation assets を、GitHub Actions の
review / deploy / evaluate gate に接続する設計を学びます。本編 resources は手動作成済み RG への
Bicep / ARM template が管理するため、workflow は infrastructure と data-plane deployment を分離します。
この付録は参加者の RG 手動作成 / custom template / GitHub 共通教材の利用を置き換えません。

## Security baseline

- long-lived client secret ではなく GitHub OIDC / workload identity federation
- environment approval と least-privilege resource scopes
- logs / artifacts に token、device code、`.workshop/context.json` を保存しない
- production data を synthetic evaluation dataset へコピーしない
- immutable source revision と Hosted Agent version を記録

## Suggested gates

1. Markdown / contract / unit validation
2. target resource names、project endpoint、model deployments、connections の read-only check
3. human approval
4. Hosted Agent data-plane deployment
5. 7-row synthetic smoke evaluation
6. scoreだけでなく errors / reasons / traces を review
7. approved version promotion

template が定義した scoped RBAC や resource settings を pipeline が勝手に拡張しないようにします。
評価と deployment は課金対象です。同一 run の再送を避け、retention と concurrency を制限します。

## Cleanup

workflow が作成した Hosted Agent versions、evaluation runs、federated credentials、
environment secrets/variables を inventory し、不要なものを削除します。本編の Lab 9 では
optional subscription / organization objects まで削除されません。
