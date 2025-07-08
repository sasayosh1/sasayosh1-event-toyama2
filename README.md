# Toyama Events Sync System

富山県のイベント情報を自動収集し、Google Calendarに同期するシステム

## 🌟 概要

このシステムは以下の3つの富山県イベント情報サイトから自動的にイベントデータを収集し、Google Calendarに同期します：

- [info-toyama.com](https://www.info-toyama.com/events)
- [toyama-life.com](https://toyama-life.com/event-calendar-toyama/)
- [toyamadays.com](https://toyamadays.com/event/)

## 🔧 機能

### ✅ 高精度日付解析
- 複雑な日本語日付形式に対応
- スマートな年推論（過去日付→来年として処理）
- 複数日付、範囲、隣接日付の正確な解析

### ✅ インテリジェント重複排除
- タイトル正規化による高精度重複検出
- 複数条件での類似度判定
- 情報統合による品質向上

### ✅ 自動同期
- GitHub Actions による毎日自動実行（JST 07:00）
- Google Calendar API との統合
- エラー復旧とログ出力

## 🚀 自動実行

### スケジュール
- **実行時間**: 毎日 07:00 JST (22:00 UTC)
- **処理内容**: 
  1. 3サイトからイベント情報を収集
  2. 日付解析と重複排除
  3. Google Calendarに同期

### 手動実行
手動でテスト実行する場合：
1. [GitHub Actions](https://github.com/sasayosh1/sasayosh1-event-toyama2/actions/workflows/sync.yml) にアクセス
2. 「Run workflow」ボタンをクリック
3. ブランチ「main」を選択して実行

## 📊 処理結果

### 重複排除効果
- **削減率**: 約14%（77→66イベント）
- **統合例**: 
  - 「戸出七夕まつり」: 複数ソースから統合
  - 「おわら風の盆」: 変種タイトルを統合

### 日付解析改善
- ✅ `2025年8月1日㈮、2日㈯、3日㈰` → 2025-08-01 to 2025-08-03
- ✅ `2025年7月26日（土）27日（日）` → 2025-07-26 to 2025-07-27
- ✅ `1/15` → 2026-01-15 (過去日付の適切な年推論)

## 🔧 技術詳細

### 依存関係
```
requests
beautifulsoup4
python-dateutil
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
```

### 認証設定
GitHub Secrets で以下を設定：
- `GOOGLE_TOKEN_B64`: OAuth トークン（Base64）
- `GOOGLE_CREDENTIALS_B64`: 認証情報（Base64）

## 📈 改善履歴

詳細な改善内容は [IMPROVEMENTS.md](./IMPROVEMENTS.md) を参照してください。

## 🐛 トラブルシューティング

### 認証エラー
- GitHub Secrets の設定を確認
- トークンの有効期限を確認

### 日付解析エラー
- `--debug` フラグでデバッグログを確認
- `--test-dates` で特定の日付形式をテスト

### 重複検出のテスト
```bash
python3 scrape.py --test-dedup
```

## 📞 開発者向け

### ローカル実行
```bash
# 依存関係インストール
pip install -r requirements.txt

# スクレイピングテスト
python3 scrape.py --debug

# 日付解析テスト
python3 scrape.py --test-dates

# 同期実行
python3 gcal_sync.py
```

### デバッグ
- スクレイピング: `python3 scrape.py --debug`
- 重複検出: `python3 scrape.py --test-dedup`
- 日付解析: `python3 scrape.py --test-dates`