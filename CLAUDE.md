# Claude Code 実行メモ

## 🎯 プロジェクト概要
富山県イベント情報の自動収集・Google Calendar同期システム

## 🔧 重要な設定情報

### GitHub Secrets設定済み
- `GOOGLE_TOKEN_B64`: OAuth認証トークン（Base64エンコード済み）
- `GOOGLE_CREDENTIALS_B64`: Google Cloud Console認証情報（Base64エンコード済み）

### 認証ファイルパス
- 元ファイル: `/Users/user/Library/Mobile Documents/com~apple~CloudDocs/code/event-toyama_backup/`
- `credentials.json`: Google Cloud Console認証情報
- `token.json`: OAuth認証済みトークン

## 🚀 実行方法

### GitHub Actions手動実行
1. https://github.com/sasayosh1/sasayosh1-event-toyama2/actions/workflows/sync.yml
2. 「Run workflow」ボタンクリック
3. ブランチ「main」で実行

### ローカルデバッグ
```bash
# 重複排除テスト
python3 scrape.py --test-dedup

# 日付解析テスト  
python3 scrape.py --test-dates

# 全イベントスクレイピング（デバッグ付き）
python3 scrape.py --debug

# Calendar同期実行
python3 gcal_sync.py
```

## 📊 実行時の期待値

### 正常実行時のログパターン
```
Starting authentication...
GOOGLE_TOKEN_B64 found: True
Attempting to decode token...
Token decoded successfully
Credentials created successfully
Processing event: [イベント名]
Final dates - Start: [日付], End: [日付]
Inserted X, updated Y events to Google Calendar.
```

### 重複排除効果
- **削減率**: 約14%（77→66イベント）
- **統合例**: 複数ソースからの情報統合

## 🐛 トラブルシューティング

### 認証エラー
```
GOOGLE_TOKEN_B64 or GOOGLE_CREDENTIALS_B64 not found in environment variables.
```
**対処**: GitHub Secrets設定を確認

### 日付解析エラー
```
Could not parse date string: '[日付文字列]'
```
**対処**: `--test-dates`でテスト、必要に応じてパターン追加

### Calendar API エラー
```
The specified time range is empty
```
**対処**: 日付バリデーション強化済み（自動修正）

## 📈 改善履歴要約

### 日付解析改善
- ✅ 複雑な日本語形式対応（㈮㈯㈰、隣接日付等）
- ✅ スマート年推論（過去日付→来年）
- ✅ 特殊文字・説明文の自動除去

### 重複排除システム
- ✅ タイトル正規化による高精度検出
- ✅ 多基準類似度判定（完全一致、包含、類似度）
- ✅ 情報統合と複数ソース追跡

### エラーハンドリング
- ✅ 個別イベントエラー処理（全体継続）
- ✅ 詳細デバッグログ出力
- ✅ CI環境対応と認証自動化

## 🎯 実行時チェックポイント

### 成功指標
1. **認証成功**: "Credentials created successfully"
2. **イベント処理**: 66個前後のイベント処理
3. **重複排除**: "Sources: [複数サイト]"表示
4. **Calendar同期**: "Inserted X, updated Y events"

### 失敗時の確認事項
1. **Secrets設定**: GitHub リポジトリ設定確認
2. **認証期限**: トークン有効期限確認
3. **ネットワーク**: スクレイピング対象サイトアクセス確認
4. **API制限**: Google Calendar API制限確認

## 📝 定期メンテナンス

### 毎月チェック
- [ ] GitHub Actions実行ログ確認
- [ ] イベント数の変動確認
- [ ] エラー率の監視

### 四半期チェック
- [ ] Google認証トークン更新
- [ ] スクレイピングサイト構造変更確認
- [ ] 新しい日付形式パターン確認

## 🚀 拡張予定

### 短期
- 他県イベントサイト追加検討
- 通知機能実装（Discord/Slack）

### 中期  
- 機械学習による重複検出精度向上
- Webダッシュボード開発
- イベント分析機能追加

## 💡 重要な学習内容

### Pythonライブラリ活用
- `difflib.SequenceMatcher`: 文字列類似度
- `dateutil.parser`: 柔軟な日付解析
- `beautifulsoup4`: Webスクレイピング
- `google-api-python-client`: Calendar API

### GitHub Actions最適化
- Secrets管理とBase64エンコード
- 環境変数による制御
- デバッグログ戦略

### 実用的パターン
- エラー復旧設計
- 情報統合アルゴリズム
- 日付推論ロジック

---

## 🔄 次回実行時の注意点

1. **ultrathink必須**: 毎回思考過程を詳細に分析
2. **エラー対応**: 個別対処でシステム全体継続
3. **改善提案**: 実行結果を基に継続的改善
4. **ドキュメント更新**: 新しい改善は必ずmd記録

---

*最終更新: 2025-07-08*
*実行環境: Python 3.9, GitHub Actions, Google Calendar API v3*
*メンテナー: Claude Code with ultrathink*